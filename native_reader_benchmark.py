"""Türkçe Native Reader için bütçe kontrollü, kör A/B değerlendirmesi.

Doğallık kontrol listesi, MIT lisanslı `oguzhankayan/turkish-native`
projesindeki genel fikirlerden altyazı güvenliği sınırlarıyla uyarlanmıştır.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path
from types import SimpleNamespace

from app_state import atomic_write_json, atomic_write_text
from hybrid_translate import _safe_chat_create, native_reader_style_rules

_CASES_PATH = Path(__file__).with_name("tests") / "regression_corpus" / "native_reader_cases.json"


def build_native_reader_corpus(path=None):
    return json.loads(Path(path or _CASES_PATH).read_text(encoding="utf-8"))


def validate_corpus(cases):
    bad = [r for r in cases if r.get("kind") == "translationese"]
    good = [r for r in cases if r.get("kind") == "positive_control"]
    ids = [str(r.get("id", "")) for r in cases]
    required = {"id", "kind", "source", "current", "diagnostic", "required_meaning"}
    if (len(cases), len(bad), len(good)) != (35, 20, 15):
        raise ValueError("Korpus tam olarak 20 yapay ve 15 doğal örnek içermeli")
    if len(set(ids)) != len(ids) or any(not i for i in ids):
        raise ValueError("Korpus kimlikleri boş veya tekrarlı")
    if any(required - set(r) or not r["required_meaning"] for r in cases):
        raise ValueError("Korpus satırında zorunlu alan eksik")
    return {"case_count": 35, "translationese": 20, "positive_controls": 15}


class BudgetedClient:
    """Her çağrı öncesinde kötümser maliyet payı ayırır."""

    def __init__(self, client, model, limit, input_price, output_price, ledger=None):
        self._client, self.model = client, model
        self.limit, self.input_price, self.output_price = limit, input_price, output_price
        self.ledger = ledger if ledger is not None else {"reserved_usd": 0.0, "attempts": 0}
        self.base_url = getattr(client, "base_url", "")
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def __getattr__(self, name):
        return getattr(self._client, name)

    def with_options(self, **options):
        if any(k not in {"timeout", "max_retries"} for k in options):
            raise ValueError("benchmark_route_or_key_change_forbidden")
        options["max_retries"] = 0
        return BudgetedClient(self._client.with_options(**options), self.model,
                              self.limit, self.input_price, self.output_price, self.ledger)

    def _create(self, **body):
        if body.get("model") != self.model:
            raise ValueError("benchmark_model_change_forbidden")
        output = int(body.get("max_completion_tokens") or body.get("max_tokens") or 0)
        if output <= 0:
            raise ValueError("benchmark_output_limit_required")
        prompt_bytes = len(json.dumps(body.get("messages", []), ensure_ascii=False).encode("utf-8")) + 4096
        reserve = (prompt_bytes * self.input_price + output * self.output_price) / 1_000_000
        if self.ledger["reserved_usd"] + reserve > self.limit:
            raise ValueError("benchmark_budget_exhausted")
        self.ledger["reserved_usd"] += reserve
        self.ledger["attempts"] += 1
        return self._client.chat.completions.create(**body)


def build_variant_prompt(cases, *, enhanced):
    rows = [{"id": r["id"], "source": r["source"], "tr": r["current"]} for r in cases]
    extra = ("\n" + native_reader_style_rules("Turkish")) if enhanced else ""
    return (
        "Sen Türkçe altyazı son-kontrol editörüsün. Kaynakla karşılaştırarak yalnız gerçekten "
        "yapay veya bozuk Türkçe satırları düzelt. Anlamı, tonu, hitabı ve bilgiyi koru. "
        "Zaten doğal olan satırı aynen bırak. Her id için bir sonuç döndür; cue birleştirme, "
        f"bölme veya kimlik değiştirme yapma.{extra}\n\n"
        f"Girdiler:\n{json.dumps(rows, ensure_ascii=False)}\n\n"
        'Yalnız JSON array döndür: [{"id":"B01","text":"..."}]. Açıklama yazma.'
    )


def _extract_rows(response, expected_ids):
    content = str(response.choices[0].message.content or "").strip()
    start, end = content.find("["), content.rfind("]")
    if start < 0 or end < start:
        raise ValueError("benchmark_invalid_json")
    parsed = json.loads(content[start:end + 1])
    result = {}
    if not isinstance(parsed, list):
        raise ValueError("benchmark_invalid_schema")
    for row in parsed:
        if not isinstance(row, dict):
            raise ValueError("benchmark_invalid_schema")
        case_id, value = str(row.get("id", "")), row.get("text")
        if case_id not in expected_ids or not isinstance(value, str) or case_id in result:
            raise ValueError("benchmark_invalid_schema")
        result[case_id] = value.strip()
    if set(result) != set(expected_ids):
        raise ValueError("benchmark_incomplete_response")
    usage = getattr(response, "usage", None)
    stats = {k: int(getattr(usage, k, 0) or 0)
             for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    return result, stats


def _enhanced_is_x(case_id, seed):
    return bool(hashlib.sha256(f"{seed}:{case_id}".encode()).digest()[0] & 1)


def build_blind_review(cases, baseline, enhanced, seed="native-reader-v1"):
    review = []
    for row in cases:
        eid = _enhanced_is_x(row["id"], seed)
        review.append({
            **row,
            "X": enhanced[row["id"]] if eid else baseline[row["id"]],
            "Y": baseline[row["id"]] if eid else enhanced[row["id"]],
            "fidelity_X_1_to_5": None, "fidelity_Y_1_to_5": None,
            "naturalness_X_1_to_5": None, "naturalness_Y_1_to_5": None,
            "preferred": "", "notes": "", "_enhanced_side": "X" if eid else "Y",
        })
    return review


def score_review(review):
    totals = {v: {"fidelity": [], "naturalness": [], "wins": 0}
              for v in ("baseline", "enhanced")}
    positive = {"baseline_changed": 0, "enhanced_changed": 0, "count": 0}
    for row in review:
        side = str(row.get("_enhanced_side", ""))
        if side not in {"X", "Y"}:
            raise ValueError("Körleme anahtarı eksik")
        mapping = {side: "enhanced", "Y" if side == "X" else "X": "baseline"}
        for shown, variant in mapping.items():
            for metric in ("fidelity", "naturalness"):
                value = row.get(f"{metric}_{shown}_1_to_5")
                if value is not None:
                    value = float(value)
                    if not 1 <= value <= 5:
                        raise ValueError("Puanlar 1 ile 5 arasında olmalı")
                    totals[variant][metric].append(value)
        preferred = str(row.get("preferred", "")).upper()
        if preferred in mapping:
            totals[mapping[preferred]]["wins"] += 1
        if row.get("kind") == "positive_control":
            positive["count"] += 1
            for shown, variant in mapping.items():
                positive[f"{variant}_changed"] += int(row.get(shown) != row.get("current"))
    result = {"reviewed_cases": len(review), "positive_controls": positive}
    for variant, values in totals.items():
        result[variant] = {
            "fidelity_mean": round(sum(values["fidelity"]) / len(values["fidelity"]), 3)
            if values["fidelity"] else None,
            "naturalness_mean": round(sum(values["naturalness"]) / len(values["naturalness"]), 3)
            if values["naturalness"] else None,
            "preferred_wins": values["wins"],
        }
    return result


def prepare(output_dir):
    cases = build_native_reader_corpus()
    manifest = validate_corpus(cases)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "corpus.json", cases)
    atomic_write_json(output_dir / "manifest.json", {
        **manifest, "live_api_used": False,
        "metrics": ["fidelity", "naturalness", "positive_control_changes", "cost", "duration"]})
    return manifest


def run_live_ab(output_dir, model, endpoint, api_key, max_usd,
                input_price, output_price, seed="native-reader-v1"):
    """Aynı modelde eski/yeni istemi çalıştır; bütçe tavanı olmadan ağa çıkmaz."""
    if not all(math.isfinite(v) and v > 0 for v in (max_usd, input_price, output_price)):
        raise ValueError("Pozitif --max-usd ve milyon-token fiyatları zorunludur")
    cases = build_native_reader_corpus()
    validate_corpus(cases)
    prompts = [build_variant_prompt(cases, enhanced=False),
               build_variant_prompt(cases, enhanced=True)]
    max_output = len(cases) * 120
    estimate = sum((len(p.encode("utf-8")) + 4096) * input_price
                   + max_output * output_price for p in prompts) / 1_000_000
    if estimate > max_usd:
        raise RuntimeError(
            f"Hesaplanan üst sınır USD {estimate:.4f}, izin USD {max_usd:.4f}; hiçbir API çağrılmadı")

    from openai import OpenAI
    raw = OpenAI(api_key=api_key, base_url=endpoint or None, max_retries=0)
    client = BudgetedClient(raw, model, max_usd, input_price, output_price)
    outputs, usage_rows = [], []
    for label, prompt in zip(("baseline", "enhanced"), prompts):
        started = time.monotonic()
        response = _safe_chat_create(
            client, model=model, messages=[{"role": "user", "content": prompt}],
            max_tokens=max_output, temperature=0.0)
        output, usage = _extract_rows(response, {r["id"] for r in cases})
        usage["duration_seconds"] = round(time.monotonic() - started, 3)
        usage["cost_usd"] = round(
            usage["prompt_tokens"] * input_price / 1_000_000
            + usage["completion_tokens"] * output_price / 1_000_000, 6)
        usage["variant"] = label
        outputs.append(output)
        usage_rows.append(usage)

    baseline, enhanced = outputs
    review = build_blind_review(cases, baseline, enhanced, seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "corpus.json", cases)
    atomic_write_json(output_dir / "baseline.json", baseline)
    atomic_write_json(output_dir / "enhanced.json", enhanced)
    atomic_write_text(output_dir / "blind_review.jsonl", "\n".join(
        json.dumps(r, ensure_ascii=False) for r in review) + "\n", encoding="utf-8")
    result = {
        "model": model, "endpoint": endpoint, "approved_limit_usd": max_usd,
        "estimated_upper_usd": round(estimate, 6), "usage": usage_rows,
        "reserved_budget": dict(client.ledger),
        "automatic": {
            "positive_controls": 15,
            "baseline_changed": sum(baseline[r["id"]] != r["current"]
                                    for r in cases if r["kind"] == "positive_control"),
            "enhanced_changed": sum(enhanced[r["id"]] != r["current"]
                                    for r in cases if r["kind"] == "positive_control"),
        },
        "human_review_required": True,
    }
    atomic_write_json(output_dir / "run.json", result)
    return result


def load_review(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Türkçe Native Reader kör A/B değerlendirmesi")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--score", metavar="REVIEW_JSONL")
    parser.add_argument("--output", default="native_reader_benchmark_output")
    parser.add_argument("--model", default="")
    parser.add_argument("--endpoint", default="https://api.openai.com/v1")
    parser.add_argument("--max-usd", type=float, default=0.0)
    parser.add_argument("--input-usd-per-million", type=float, default=-1.0)
    parser.add_argument("--output-usd-per-million", type=float, default=-1.0)
    parser.add_argument("--seed", default="native-reader-v1")
    args = parser.parse_args(argv)
    if args.prepare:
        print(json.dumps(prepare(args.output), ensure_ascii=False, indent=2))
        return 0
    if args.score:
        result = score_review(load_review(args.score))
        Path(args.output).mkdir(parents=True, exist_ok=True)
        atomic_write_json(Path(args.output) / "scores.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    key = os.environ.get("SUBTITLE_TRANSLATOR_BENCHMARK_API_KEY", "")
    if not key or not args.model:
        parser.error("--model ve SUBTITLE_TRANSLATOR_BENCHMARK_API_KEY zorunlu")
    result = run_live_ab(args.output, args.model, args.endpoint, key, args.max_usd,
                         args.input_usd_per_million, args.output_usd_per_million, args.seed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
