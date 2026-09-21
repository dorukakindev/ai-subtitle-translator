# -*- coding: utf-8 -*-
"""Kalite/teslim BAŞARISIZLIĞI sonrası yan etkiler — dört akışı GERÇEKTEN
koşturan davranış testleri (2026-09-19 denetimi).

`inspect.getsource`/AST yerine akışlar küçük sentetik SRT'ler ve sahte
sağlayıcılarla uçtan uca çalıştırılır:

- Düz senkron : ``App._run_sync``      (sahte ``openai.OpenAI``)
- Düz batch   : ``App._run_batch``     (sahte batches/files uçları)
- Senkron hibrit: ``App._run_sync_hybrid`` (sahte client + dondurulmuş analiz)
- Batch hibrit  : ``App._run_hybrid``      (sahte submit/wait/save_results)

Kanıt noktaları: diske yazılan dosyalar (final/kısmi/karantina), kalite
raporu satırları, TM/Series-Memory/Auto-Glossary yan etki çağrı sayaçları,
dosya-durum kayıtları. Hiçbir ücretli API çağrısı yapılmaz.
"""
import copy
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS_DIR)
for _p in (TESTS_DIR, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import openai  # tests/openai.py stub'ı ya da gerçek paket — attr patch'lenir
import subtitle_translator_gui as gui
import hybrid_translate as ht
from _gui_app import make_app


# ── Sahte sağlayıcı ──────────────────────────────────────────────────────────

def _ns(**kw):
    return types.SimpleNamespace(**kw)


class _Missing:
    """Stub ``_DummyWidget.__getattr__`` eksik attr'a çıplak lambda veriyor;
    ``getattr(self, x, default)`` bir fonksiyon dönünce `for`, `if not`,
    `len` gibi veri kullanımları patlıyor (gerçek App'te AttributeError
    olurdu → default). Bu nesne hem callable hem falsy hem boş-iterable:
    widget çağrıları no-op olur, veri erişimleri güvenli davranır."""

    __slots__ = ()

    def __call__(self, *a, **k):
        return _MISSING

    def __getattr__(self, name):
        return _MISSING

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __contains__(self, item):
        return False

    def __getitem__(self, key):
        return _MISSING

    # Sayaç/ücret alanları `getattr(self, "_cost_total", 0.0) + x` gibi
    # kullanır: eksik attr gerçekte default dönerdi; burada 0-saydavran.
    def __add__(self, other):
        return other if isinstance(other, (int, float)) else 0.0

    def __radd__(self, other):
        return other if isinstance(other, (int, float)) else 0.0

    def __sub__(self, other):
        return 0.0

    def __rsub__(self, other):
        return other if isinstance(other, (int, float)) else 0.0

    def __mul__(self, other):
        return 0.0

    def __rmul__(self, other):
        return 0.0

    def __truediv__(self, other):
        return 0.0

    def __rtruediv__(self, other):
        return 0.0

    def __floordiv__(self, other):
        return 0

    def __mod__(self, other):
        return 0

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __index__(self):
        return 0

    def __eq__(self, other):
        return other is _MISSING

    def __ne__(self, other):
        return other is not _MISSING

    def __lt__(self, other):
        return False

    def __le__(self, other):
        return False

    def __gt__(self, other):
        return False

    def __ge__(self, other):
        return False

    def __hash__(self):
        return id(self)

    def __str__(self):
        return ""

    def __repr__(self):
        return "<missing>"

    def __format__(self, spec):
        return ""


_MISSING = _Missing()

# write_srt sahtesi için modül-yüzeyi referans (patch sarmalayıcıdan çağrılır).
_real_write_srt = None  # _make_app ilk çağrıda doldurulur (import zamanı erken)


def _app_missing(self, name):
    return _MISSING


def _write_srt_patch_factory(fail_prefixes=(), raise_always=False):
    """`gui.write_srt` için seçici sahte: listeli köklerde OSError verir."""
    real = gui.write_srt

    def _fake(path, *a, **k):
        name = Path(str(path)).name
        if raise_always or any(name.startswith(p) for p in fail_prefixes):
            raise OSError("teslim yazımı hatası (fake)")
        return real(path, *a, **k)
    return _fake


def _chat_resp(content: str, finish_reason: str = "stop"):
    return _ns(
        choices=[_ns(message=_ns(content=content), finish_reason=finish_reason)],
        usage=_ns(total_tokens=10, prompt_tokens=6, completion_tokens=4,
                  prompt_tokens_details=None),
        usage_available=True,
    )


def _request_items(body: dict) -> list:
    """İstek gövdesindeki user mesajının {"tr": [...]} yükünü çöz."""
    for msg in body.get("messages", []):
        if msg.get("role") != "user":
            continue
        try:
            payload = json.loads(msg.get("content") or "{}")
        except Exception:
            continue
        items = payload.get("tr")
        if isinstance(items, list):
            return items
    return []


class FakeClient:
    """chat.completions.create + files + batches uçlarını taklit eder.

    ``translate(text)`` varsayılanı "TR::<kaynak>" döndürür; ``drop_ids``
    yanıttan cue düşürür (eksik çeviri işareti senaryosu); ``fail_cids``
    belirtilen custom_id'lerde create() hata verir.
    """

    def __init__(self, translate=None, drop_ids=(), fail_cids=(),
                 batch_outputs=None, fail_files_create=False):
        self.api_key = "sk-fake"
        self.base_url = ""
        self._translate = translate or (lambda text: "TR::" + str(text or ""))
        self._drop_ids = {str(i) for i in drop_ids}
        self._fail_cids = set(fail_cids)
        self._fail_files_create = fail_files_create
        # custom_id -> JSONL ham içerik (batch akışları için)
        self._batch_outputs = dict(batch_outputs or {})
        self.chat_calls = []       # her ana çeviri isteğinin gövdesi
        self.create_calls = []     # batches.create kwargs
        self.files_created = 0
        self._files = {}           # file_id -> text
        self._seq = 0
        self.chat = _ns(completions=_ns(create=self._chat_create))
        self.files = _ns(create=self._files_create, content=self._files_content)
        self.batches = _ns(create=self._batch_create,
                           retrieve=self._batch_retrieve,
                           cancel=lambda *a, **k: _ns(id="batch-x"))

    # ── chat.completions.create ──────────────────────────────────────────
    def _chat_create(self, **kwargs):
        model = str(kwargs.get("model") or "")
        msgs = kwargs.get("messages") or []
        user = next((m for m in msgs if m.get("role") == "user"), {})
        user_text = str(user.get("content") or "")
        items = _request_items(kwargs)
        # İçerik türü / ön-bağlam gibi çeviri olmayan yardımcı çağrılar:
        # "tr" yükü yoksa jenerik ama geçerli JSON döndür.
        if not items:
            try:
                json.loads(user_text)
            except Exception:
                pass
            return _chat_resp(json.dumps(
                {"category": "Dizi", "confidence": 0.9,
                 "summary": "t", "terms": {}, "characters": [],
                 "pronouns": {}}, ensure_ascii=False))
        self.chat_calls.append(kwargs)
        out = []
        for it in items:
            iid = str(it.get("i"))
            if iid in self._drop_ids:
                continue
            out.append({"i": iid, "t": self._translate(it.get("t"))})
        return _chat_resp(json.dumps(out, ensure_ascii=False))

    # ── files.create / files.content ──────────────────────────────────────
    def _files_create(self, file=None, purpose=None, **kw):
        if self._fail_files_create:
            raise RuntimeError("upload failed (fake)")
        text = ""
        try:
            raw = file.read() if hasattr(file, "read") else file
            text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        except Exception:
            pass
        self.files_created += 1
        self._seq += 1
        fid = f"file-{self._seq}"
        self._files[fid] = text
        return _ns(id=fid)

    def _files_content(self, file_id):
        return _ns(text=self._files.get(file_id, ""))

    # ── batches.create / retrieve ─────────────────────────────────────────
    def _batch_create(self, input_file_id=None, **kw):
        self.create_calls.append(kw)
        self._seq += 1
        bid = f"batch-{self._seq}"
        # Girdi JSONL'sini oku; her custom_id için kayıtlı yanıt varsa onu,
        # yoksa translate() ile üretilmiş çıktıyı yaz.
        lines = []
        for raw in (self._files.get(input_file_id, "") or "").splitlines():
            try:
                req = json.loads(raw)
            except Exception:
                continue
            cid = str(req.get("custom_id") or "")
            if not cid:
                continue
            body = req.get("body") or {}
            if cid in self._fail_cids:
                lines.append(json.dumps({
                    "custom_id": cid, "error": {"message": "fake failure"},
                    "response": {"status_code": 500, "body": {}}}))
                continue
            if cid in self._batch_outputs:
                content = self._batch_outputs[cid]
            else:
                out = [{"i": str(it.get("i")), "t": self._translate(it.get("t"))}
                       for it in _request_items(body)
                       if str(it.get("i")) not in self._drop_ids]
                content = json.dumps(out, ensure_ascii=False)
            lines.append(json.dumps({
                "custom_id": cid,
                "response": {"status_code": 200, "body": {
                    "choices": [{"message": {"content": content},
                                 "finish_reason": "stop"}],
                    "usage": {"total_tokens": 10, "prompt_tokens": 6,
                              "completion_tokens": 4}}},
                "error": None}))
        out_fid = f"file-out-{self._seq}"
        self._files[out_fid] = "\n".join(lines)
        n = max(1, len(lines))
        self._batches = getattr(self, "_batches", {})
        self._batches[bid] = _ns(
            id=bid, status="completed",
            request_counts=_ns(total=n, completed=n, failed=0),
            output_file_id=out_fid, error_file_id=None)
        return self._batches[bid]

    def _batch_retrieve(self, batch_id):
        batches = getattr(self, "_batches", {})
        if batch_id in batches:
            return batches[batch_id]
        return _ns(id=batch_id, status="completed",
                   request_counts=_ns(total=1, completed=1, failed=0),
                   output_file_id=None, error_file_id=None)


# ── Akış sürücüsü ─────────────────────────────────────────────────────────────

_SRT = """1
00:00:01,000 --> 00:00:02,000
Hello world.

2
00:00:03,000 --> 00:00:04,000
How are you today?

3
00:00:05,000 --> 00:00:06,000
See you soon.
"""

_OFF_VARS = [
    "critic_var", "polish_var", "native_var", "qc_var", "condense_var",
    "backtrans_var", "term_normalize_var", "review_pass_var", "twowave_var",
    "repair_missing_var", "precontext_var", "hybrid_var", "merge_cues_var",
    "ai_segment_var", "deep_delivery_semantic_var", "semantic_reconcile_var",
    "cue_fill_move_var", "term_normalize_apply_var", "season_canon_var",
]


def _off_all(app):
    """Ücretli/yardımcı geçişleri kapat; offline dosya geçişleri çalışsın."""
    for name in _OFF_VARS:
        var = getattr(app, name, None)
        if var is not None:
            try:
                var.set(False)
            except Exception:
                pass


class FlowRun:
    """Bir akış koşusunun gözlemlenebilir yan etki kaydı."""

    def __init__(self, app, inp, out):
        self.app = app
        self.inp = inp
        self.out = out
        self.calls = {"auto_glossary": 0, "glossary_api": 0, "tm_store": 0,
                      "series_memory": 0, "project_memory": []}
        self.report_rows = []
        self.file_status = []
        self.errors = []


def _instrument(app):
    run = FlowRun(app, Path(app.input_var.get()), Path(app.output_var.get()))
    orig_ag = gui.App._run_auto_glossary
    orig_tm = gui.App._store_tm_pairs
    orig_sm = gui.App._commit_precontext_series_memory
    orig_sm2 = gui.App._update_series_memory_from_analysis
    orig_rep = gui.App._save_quality_report
    orig_rfs = gui.App._record_file_status

    def _ag(self, *a, **k):
        run.calls["auto_glossary"] += 1
        return orig_ag(self, *a, **k)

    def _tm(self, *a, **k):
        run.calls["tm_store"] += 1
        return orig_tm(self, *a, **k)

    def _sm(self, *a, **k):
        run.calls["series_memory"] += 1
        return orig_sm(self, *a, **k)

    def _sm2(self, *a, **k):
        run.calls["series_memory"] += 1
        return orig_sm2(self, *a, **k)

    def _rep(self, rows, output_dir, *a, **k):
        run.report_rows = copy.deepcopy(list(rows))
        return orig_rep(self, rows, output_dir, *a, **k)

    def _rfs(self, fp, phase, status, *a, **k):
        run.file_status.append((str(fp), str(phase), str(status)))
        return orig_rfs(self, fp, phase, status, *a, **k)

    patch.object(app, "_run_auto_glossary", _ag.__get__(app)).start()
    patch.object(app, "_store_tm_pairs", _tm.__get__(app)).start()
    patch.object(app, "_commit_precontext_series_memory", _sm.__get__(app)).start()
    patch.object(app, "_update_series_memory_from_analysis",
                 _sm2.__get__(app)).start()
    patch.object(app, "_save_quality_report", _rep.__get__(app)).start()
    patch.object(app, "_record_file_status", _rfs.__get__(app)).start()
    # Ücretli yardımcı gerçekten çağrılırsa say (çağrılmasın diye stub);
    # status_out'u gerçek fonksiyon gibi doldur ki rapor satırı doğru oluşsun.
    def _fake_suggest(*a, **k):
        run.calls["glossary_api"] += 1
        status_out = k.get("status_out")
        if isinstance(status_out, dict):
            status_out.update({"status": "completed", "changed": 0,
                               "successful_chunks": 1, "failed_chunks": 0,
                               "total_chunks": 1})
        return []
    patch.object(ht, "build_glossary_suggestions", _fake_suggest).start()
    return run


def _make_app(tmp, report_only=False, auto_glossary=False):
    patch.object(gui.App, "__getattr__", _app_missing).start()
    app = make_app(gui)
    inp = Path(tmp) / "in"
    out = Path(tmp) / "out"
    inp.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    app.input_var.set(str(inp))
    app.output_var.set(str(out))
    app.src_var.set("English")
    app.tgt_var.set("Turkish")
    app.content_type_var.set("Dizi")
    # Snapshot string .strip()/.get() varsının None kalmasını önle.
    for name, value in (("glossary_var", ""), ("ext_project_path_var", ""),
                        ("style_var", "natural"), ("analysis_depth_var", "Standart"),
                        ("media_mode_var", "Dizi"), ("workflow_profile_var", "Özel")):
        var = getattr(app, name, None)
        if var is not None:
            try:
                var.set(value)
            except Exception:
                pass
    # Yardımcı-rol anahtar/url/model var'ları None .strip() patlatıyor.
    for dic_name in ("helper_role_key_vars", "helper_role_url_vars",
                     "helper_role_model_vars"):
        for var in (getattr(app, dic_name, None) or {}).values():
            try:
                var.set("")
            except Exception:
                pass
    _off_all(app)
    if auto_glossary:
        # Ücretli öneri çağrısına gerçekten ulaşılması için: yardımcı anahtar +
        # geçerli JSON sözlük dosyası (build_glossary_suggestions stub'da sayılır).
        kvar = (getattr(app, "helper_role_key_vars", None) or {}).get("analysis")
        if kvar is not None:
            kvar.set("sk-helper-fake")
        gpath = Path(tmp) / "sozluk.json"
        gpath.write_text("{}", encoding="utf-8")
        var = getattr(app, "glossary_var", None)
        if var is not None:
            var.set(str(gpath))
    app.auto_glossary_var.set(auto_glossary)
    var = getattr(app, "quality_report_only_var", None)
    if var is not None:
        var.set(report_only)
    app._stop_flag = False
    app._pause_btw_files.set()
    app._file_schema_vars = {}
    app._current_file_path = ""
    # Gerçek koşu başlangıcı: run-state, iptalci, snapshot ve var-dondurma
    # burada kurulur; elle _is_running=True bırakmak _set_running(False)
    # sırasında yarım durum patlatıyordu.
    app._set_running(True)
    snap = dict(getattr(app, "_active_snapshot", {}) or {})
    snap["quality_report_only"] = report_only
    snap["main_api_base_url"] = ""
    app._active_snapshot = snap
    return app, inp, out


def _report_path(out):
    return Path(out) / "Raporlar" / "ceviri_raporu.txt"


def _write_src(inp, name="bolum.srt", text=_SRT):
    fp = Path(inp) / name
    fp.write_text(text, encoding="utf-8")
    return str(fp)


def _write_srcs(inp, names):
    return [_write_src(inp, n) for n in names]


def _rows_by_name(run):
    return {r.get("name"): r for r in run.report_rows}


class _FlowCase(unittest.TestCase):
    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        patch.stopall()
        tmp = getattr(self, "_tmp_obj", None)
        if tmp is not None:
            tmp.cleanup()


# ── Düz senkron ───────────────────────────────────────────────────────────────

class SyncFlowTest(_FlowCase):
    def _drive(self, client, auto_glossary=False, report_only=False,
               extra=None, names=("bolum.srt",)):
        self._tmp_obj = tempfile.TemporaryDirectory()
        tmp = self._tmp_obj.name
        if True:
            self.app, inp, out = _make_app(
                tmp, report_only=report_only, auto_glossary=auto_glossary)
            self.app.mode_var.set("sync")
            fps = _write_srcs(inp, names)
            fp = fps[0]
            self.app._selected_files = list(fps)
            self.app._input_folder_explicitly_selected = True
            run = _instrument(self.app)
            if extra:
                extra(self.app, fp)
            with patch.object(gui, "OpenAI", lambda *a, **k: client), \
                 patch.object(openai, "OpenAI", lambda *a, **k: client), \
                 patch.object(gui, "messagebox", _ns(
                     askyesno=lambda *a, **k: False,
                     showinfo=lambda *a, **k: None,
                     showerror=lambda *a, **k: None)), \
                 patch.object(self.app, "_notify", lambda *a, **k: None):
                try:
                    self.app._run_sync("sk-fake")
                except Exception as exc:
                    run.errors.append(exc)
            run.inp, run.out = inp, out
            run.report_file = _report_path(out)
            run.fps = fps
            run.fp = fp
            run.fname = Path(fp).name
            self.run = run
            return run

    def test_sync_success_delivers_and_stores_side_effects(self):
        run = self._drive(FakeClient(), auto_glossary=False)
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "done")
        out_path = Path(row["output_path"])
        self.assertTrue(out_path.exists(), f"final çıktı yok: {out_path}")
        text = out_path.read_text(encoding="utf-8")
        self.assertIn("TR::Hello world.", text)
        self.assertNotIn("[HATA", text)
        self.assertGreaterEqual(run.calls["tm_store"], 1)
        self.assertEqual(run.calls["auto_glossary"], 0)
        self.assertEqual(run.calls["glossary_api"], 0)

    def test_sync_missing_marker_partial_only_no_side_effects(self):
        run = self._drive(FakeClient(drop_ids={"2"}), auto_glossary=True)
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "error")
        self.assertGreater(row["hata"], 0)
        # Raporda gösterilen çıktı [HATA işareti içermemeli.
        shown = Path(row["output_path"])
        if shown.exists():
            self.assertNotIn("[HATA", shown.read_text(
                encoding="utf-8", errors="replace"))
        self.assertEqual(run.calls["tm_store"], 0)
        self.assertEqual(run.calls["auto_glossary"], 0)
        self.assertEqual(run.calls["glossary_api"], 0)
        ps = row.get("pass_status") or {}
        self.assertEqual(
            (ps.get("Series-Memory") or {}).get("reason"), "unresolved_markers")
        self.assertEqual(
            (ps.get("Auto-Glossary") or {}).get("reason"), "unresolved_markers")
        statuses = [s for f, _p, s in run.file_status if f == run.fp]
        self.assertIn("error", statuses)
        self.assertTrue(run.report_file.exists())

    def test_sync_quality_hard_fail_quarantines_and_skips_side_effects(self):
        # Final-Semantic hard-fail → kalite kapısı → karantina.
        def _boom(self, *a, status_out=None, **k):
            if isinstance(status_out, dict):
                status_out.update({"status": "failed", "error": "boom"})
        self._tmp_obj = tempfile.TemporaryDirectory()
        tmp = self._tmp_obj.name
        if True:
            self.app, inp, out = _make_app(tmp, auto_glossary=True)
            self.app.mode_var.set("sync")
            fp = _write_src(inp)
            self.app._selected_files = [fp]
            self.app._input_folder_explicitly_selected = True
            run = _instrument(self.app)
            with patch.object(gui, "OpenAI", lambda *a, **k: FakeClient()), \
                 patch.object(gui.App, "_run_final_semantic_checks", _boom), \
                 patch.object(gui, "messagebox", _ns(
                     askyesno=lambda *a, **k: False,
                     showinfo=lambda *a, **k: None,
                     showerror=lambda *a, **k: None)), \
                 patch.object(self.app, "_notify", lambda *a, **k: None):
                self.app._run_sync("sk-fake")
            run.report_file = _report_path(out)
            run.fp = fp
            run.fname = Path(fp).name
            run.out = out
            row = _rows_by_name(run)[run.fname]
            self.assertEqual(row["run_status"], "error")
            self.assertEqual(run.calls["tm_store"], 0)
            self.assertEqual(run.calls["auto_glossary"], 0)
            self.assertEqual(run.calls["glossary_api"], 0)
            ps = row.get("pass_status") or {}
            self.assertEqual(
                (ps.get("Auto-Glossary") or {}).get("status"), "skipped")
            self.assertEqual(
                (ps.get("Auto-Glossary") or {}).get("reason"), "quality_failed")
            self.assertEqual(
                (ps.get("Series-Memory") or {}).get("status"), "skipped")
            # Çıktı karantinaya alınmış veya rapor-only'de yerinde bırakılmış
            # olmalı; raporun output_path'i gösterilenle uyuşmalı.
            shown = Path(row["output_path"])
            self.assertTrue(
                "Kurtarma" in str(shown) or shown.exists()
                or ".incomplete" in shown.name,
                f"output_path şaşırtıcı: {shown}")

    def test_sync_source_change_mid_run_blocks_write(self):
        # source_hashes'e bayat hash → guard 'source_changed'.
        run_holder = {}
        self._tmp_obj = tempfile.TemporaryDirectory()
        tmp = self._tmp_obj.name
        if True:
            self.app, inp, out = _make_app(tmp)
            self.app.mode_var.set("sync")
            fp = _write_src(inp)
            self.app._selected_files = [fp]
            self.app._input_folder_explicitly_selected = True
            run = _instrument(self.app)
            orig_write = gui.App._write_results

            def _tamper(self, raw_map, file_map, output_dir, **kw):
                # Teslim anında kaynak değişmiş gibi: dosyayı yeniden yaz.
                Path(fp).write_text(
                    _SRT + "\n4\n00:00:07,000 --> 00:00:08,000\nNew line.\n",
                    encoding="utf-8")
                return orig_write(self, raw_map, file_map, output_dir, **kw)

            with patch.object(gui, "OpenAI", lambda *a, **k: FakeClient()), \
                 patch.object(gui.App, "_write_results", _tamper), \
                 patch.object(gui, "messagebox", _ns(
                     askyesno=lambda *a, **k: False,
                     showinfo=lambda *a, **k: None,
                     showerror=lambda *a, **k: None)), \
                 patch.object(self.app, "_notify", lambda *a, **k: None):
                self.app._run_sync("sk-fake")
            run.out = out
            finals = [p for p in out.rglob("*.srt")
                      if "Hello" in p.read_text(encoding="utf-8", errors="replace")
                      or "TR::" in p.read_text(encoding="utf-8", errors="replace")]
            self.assertEqual(finals, [],
                             "kaynak değişmişken eski sonuç yazıldı")
            self.assertEqual(run.calls["tm_store"], 0)
            statuses = [s for f, _p, s in run.file_status if f == fp]
            self.assertIn("error", statuses)

    def test_sync_report_only_mode_leaves_output_no_quarantine(self):
        run = self._drive(FakeClient(drop_ids={"2"}), report_only=True)
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "error")
        # Rapor-only: karantina Klasörü oluşmamalı.
        self.assertFalse((run.out / "Raporlar" / "Kurtarma").exists())

    def test_sync_auto_glossary_on_success_reaches_paid_call(self):
        # Başarılı dosya + anahtar/sözlük hazır → ücretli öneri çağrısına
        # ulaşılır (stub'da sayılır, gerçek istek atılmaz).
        run = self._drive(FakeClient(), auto_glossary=True)
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "done")
        self.assertGreaterEqual(run.calls["auto_glossary"], 1)
        self.assertGreaterEqual(run.calls["glossary_api"], 1)
        self.assertEqual(
            (row.get("pass_status") or {}).get("Auto-Glossary", {})
            .get("status"), "completed")

    def test_sync_write_error_isolates_file_others_survive(self):
        # Dosya 1'in teslim yazımı patlarsa koşu ÖLMEMELİ: dosya 2 hâlâ
        # teslim edilmeli, dosya 1 'error' satırıyla rapora düşmeli.
        with patch.object(gui, "write_srt",
                          _write_srt_patch_factory(fail_prefixes=("bolum1",))):
            run = self._drive(FakeClient(),
                              names=("bolum1.srt", "bolum2.srt"))
        self.assertEqual(run.errors, [])
        rows = _rows_by_name(run)
        self.assertEqual(rows["bolum1.srt"]["run_status"], "error")
        self.assertEqual(rows["bolum2.srt"]["run_status"], "done")
        self.assertTrue(Path(rows["bolum2.srt"]["output_path"]).exists())
        self.assertEqual(run.calls["tm_store"], 1,
                         "patlayan dosya TM'e yazmamalı, sağlam dosya yazmalı")
        self.assertTrue(run.report_file.exists())

    def test_sync_quarantine_error_does_not_kill_run(self):
        # Karantina taşıması patlarsa koşu devam etmeli; satır 'error'.
        run = self._drive(
            FakeClient(drop_ids={"2"}), auto_glossary=True,
            extra=lambda app, fp: patch.object(
                gui, "_quarantine_incomplete_final",
                lambda *a, **k: (_ for _ in ()).throw(
                    OSError("karantina hatası (fake)"))).start())
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "error")
        self.assertEqual(run.calls["tm_store"], 0)
        self.assertEqual(run.calls["glossary_api"], 0)
        self.assertTrue(run.report_file.exists())

    def test_sync_report_write_error_is_contained(self):
        # ceviri_raporu.txt yazımı patlarsa teslim edilmiş dosyalar korunmalı;
        # koşu ya uyarır ya da raporu atlar — ama _run_sync çökmemeli.
        real_write = gui.atomic_write_text

        def _fragile(path, *a, **k):
            if Path(str(path)).name == "ceviri_raporu.txt":
                raise OSError("rapor yazılamadı (fake)")
            return real_write(path, *a, **k)

        run = self._drive(
            FakeClient(),
            extra=lambda app, fp: patch.object(
                gui, "atomic_write_text", _fragile).start())
        row = _rows_by_name(run).get(run.fname)
        self.assertIsNotNone(row)
        self.assertEqual(row["run_status"], "done")
        self.assertTrue(Path(row["output_path"]).exists(),
                        "rapor yazım hatası teslim edilmiş çıktıyı kaybettirmemeli")

    def test_sync_missing_helper_key_still_completes(self):
        # Yardımcı anahtar yok + tüm yardımcı geçişler kapalı → düz akış etkilenmez.
        run = self._drive(FakeClient())
        # Yardımcı anahtar yok + tüm yardımcı geçişler kapalı → düz akış etkilenmez.
        run = self._drive(FakeClient())
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "done")

    def test_sync_stop_flag_aborts_before_write(self):
        self._tmp_obj = tempfile.TemporaryDirectory()
        tmp = self._tmp_obj.name
        if True:
            self.app, inp, out = _make_app(tmp)
            self.app.mode_var.set("sync")
            fp = _write_src(inp)
            self.app._selected_files = [fp]
            self.app._input_folder_explicitly_selected = True
            run = _instrument(self.app)
            app = self.app

            def _stop_translate(text):
                app._stop_flag = True
                return "TR::" + str(text or "")

            client = FakeClient(translate=_stop_translate)
            with patch.object(gui, "OpenAI", lambda *a, **k: client), \
                 patch.object(gui, "messagebox", _ns(
                     askyesno=lambda *a, **k: False,
                     showinfo=lambda *a, **k: None,
                     showerror=lambda *a, **k: None)), \
                 patch.object(app, "_notify", lambda *a, **k: None):
                app._run_sync("sk-fake")
            # Durdurulan koşu çıktı üretmemeli (kısmi dosya dahil).
            finals = [p for p in out.rglob("*.srt")]
            self.assertEqual(finals, [], "stop sonrası çıktı yazıldı")


# ── Senkron hibrit ────────────────────────────────────────────────────────────

class SyncHybridFlowTest(_FlowCase):
    def _drive(self, client, auto_glossary=False, report_only=False,
               missing_key=False, names=("bolum.srt",)):
        self._tmp_obj = tempfile.TemporaryDirectory()
        tmp = self._tmp_obj.name
        if True:
            self.app, inp, out = _make_app(
                tmp, report_only=report_only, auto_glossary=auto_glossary)
            self.app.hybrid_var.set(True)
            fps = _write_srcs(inp, names)
            fp = fps[0]
            self.app._selected_files = list(fps)
            self.app._input_folder_explicitly_selected = True
            run = _instrument(self.app)
            cached = ht.empty_analysis_result("en")
            patches = ExitStack()
            patches.enter_context(
                patch.object(self.app, "_project_memory_for",
                             lambda *a, **k: None))
            patches.enter_context(
                patch.object(self.app, "_show_progress_board",
                             lambda *a, **k: None))
            patches.enter_context(
                patch.object(self.app, "_hide_progress_board",
                             lambda *a, **k: None))
            patches.enter_context(
                patch.object(self.app, "_notify", lambda *a, **k: None))
            patches.enter_context(
                patch.object(gui, "messagebox", _ns(
                    askyesno=lambda *a, **k: False,
                    showinfo=lambda *a, **k: None,
                    showerror=lambda *a, **k: None)))
            if missing_key:
                patches.enter_context(patch.object(
                    self.app, "_load_context_cache_for_file",
                    lambda *a, **k: None))
                def _no_key(*a, **k):
                    raise RuntimeError("missing helper api key")
                patches.enter_context(
                    patch.object(ht, "analyze_with_helper", _no_key))
            else:
                patches.enter_context(patch.object(
                    self.app, "_load_context_cache_for_file",
                    lambda *a, **k: cached))
            with patches:
                try:
                    self.app._run_sync_hybrid(
                        "sk-fake", client, list(fps), "English", "Turkish",
                        "gpt-5-mini", str(out))
                except Exception as exc:
                    run.errors.append(exc)
            run.inp, run.out = inp, out
            run.fps = fps
            run.fp, run.fname = fp, Path(fp).name
            run.report_file = _report_path(out)
            self.run = run
            return run

    def test_sync_hybrid_success_side_effects(self):
        run = self._drive(FakeClient())
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "done")
        self.assertGreaterEqual(run.calls["tm_store"], 1)

    def test_sync_hybrid_missing_marker_skip_statuses_written(self):
        run = self._drive(FakeClient(drop_ids={"2"}), auto_glossary=True)
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "error")
        self.assertEqual(run.calls["tm_store"], 0)
        self.assertEqual(run.calls["auto_glossary"], 0)
        self.assertEqual(run.calls["glossary_api"], 0)
        ps = row.get("pass_status") or {}
        self.assertEqual(
            (ps.get("Series-Memory") or {}).get("reason"), "unresolved_markers")
        self.assertEqual(
            (ps.get("Auto-Glossary") or {}).get("reason"), "unresolved_markers")

    def test_sync_hybrid_missing_helper_key_fails_file_not_run(self):
        run = self._drive(FakeClient(), missing_key=True)
        self.assertEqual(run.errors, [])
        # Analiz zorunlu: dosya atlanır, TM/sözlük yan etkisi olmaz.
        self.assertEqual(run.calls["tm_store"], 0)
        self.assertEqual(run.calls["auto_glossary"], 0)
        self.assertEqual(run.calls["glossary_api"], 0)
        statuses = [s for f, _p, s in run.file_status if f == run.fp]
        self.assertIn("error", statuses)

    def test_sync_hybrid_write_error_isolates_file_others_survive(self):
        with patch.object(gui, "write_srt",
                          _write_srt_patch_factory(fail_prefixes=("h1",))):
            run = self._drive(FakeClient(), names=("h1.srt", "h2.srt"))
        self.assertEqual(run.errors, [])
        rows = _rows_by_name(run)
        self.assertEqual(rows["h1.srt"]["run_status"], "error")
        self.assertEqual(rows["h2.srt"]["run_status"], "done")
        self.assertTrue(Path(rows["h2.srt"]["output_path"]).exists())
        self.assertEqual(run.calls["tm_store"], 1)
        self.assertTrue(run.report_file.exists())

    def test_sync_hybrid_auto_glossary_raise_is_isolated(self):
        # Ücretli sözlük geçişi patlarsa dosya 'done' + Auto-Glossary 'failed'
        # ile rapora düşmeli; koşu ölmemeli (düz akışlarla parite).
        self._tmp_obj = tempfile.TemporaryDirectory()
        tmp = self._tmp_obj.name
        self.app, inp, out = _make_app(tmp, auto_glossary=True)
        self.app.hybrid_var.set(True)
        fp = _write_src(inp)
        self.app._selected_files = [fp]
        self.app._input_folder_explicitly_selected = True
        run = _instrument(self.app)
        cached = ht.empty_analysis_result("en")
        mb = _ns(askyesno=lambda *a, **k: False, showinfo=lambda *a, **k: None,
                 showerror=lambda *a, **k: None)

        def _boom_glossary(*a, **k):
            raise RuntimeError("glossary patladi (fake)")

        with patch.object(self.app, "_project_memory_for",
                          lambda *a, **k: None), \
             patch.object(self.app, "_show_progress_board",
                          lambda *a, **k: None), \
             patch.object(self.app, "_hide_progress_board",
                          lambda *a, **k: None), \
             patch.object(self.app, "_notify", lambda *a, **k: None), \
             patch.object(self.app, "_load_context_cache_for_file",
                          lambda *a, **k: cached), \
             patch.object(gui, "messagebox", mb), \
             patch.object(self.app, "_run_auto_glossary", _boom_glossary):
            try:
                self.app._run_sync_hybrid(
                    "sk-fake", FakeClient(), [fp], "English", "Turkish",
                    "gpt-5-mini", str(out))
            except Exception as exc:
                run.errors.append(exc)
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[Path(fp).name]
        self.assertEqual(row["run_status"], "done")
        ag = (row.get("pass_status") or {}).get("Auto-Glossary") or {}
        self.assertEqual(ag.get("status"), "failed")
        self.assertTrue((out / "Raporlar" / "ceviri_raporu.txt").exists())


# ── Düz batch ─────────────────────────────────────────────────────────────────

class BatchFlowTest(_FlowCase):
    def _drive(self, client, auto_glossary=False, report_only=False,
               names=("bolum.srt",)):
        self._tmp_obj = tempfile.TemporaryDirectory()
        tmp = self._tmp_obj.name
        if True:
            self.app, inp, out = _make_app(
                tmp, report_only=report_only, auto_glossary=auto_glossary)
            self.app.mode_var.set("batch")
            fps = _write_srcs(inp, names)
            fp = fps[0]
            self.app._selected_files = list(fps)
            self.app._input_folder_explicitly_selected = True
            run = _instrument(self.app)
            with patch.object(gui, "OpenAI", lambda *a, **k: client), \
                 patch.object(openai, "OpenAI", lambda *a, **k: client), \
                 patch.object(gui, "messagebox", _ns(
                     askyesno=lambda *a, **k: False,
                     showinfo=lambda *a, **k: None,
                     showerror=lambda *a, **k: None)), \
                 patch.object(self.app, "_notify", lambda *a, **k: None):
                try:
                    self.app._run_batch("sk-fake")
                except Exception as exc:
                    run.errors.append(exc)
            run.inp, run.out = inp, out
            run.fps = fps
            run.fp, run.fname = fp, Path(fp).name
            run.report_file = _report_path(out)
            self.run = run
            return run

    def test_batch_success_side_effects(self):
        run = self._drive(FakeClient())
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run).get(run.fname)
        self.assertIsNotNone(row, "rapor satırı yok")
        self.assertEqual(row["run_status"], "done")
        self.assertGreaterEqual(run.calls["tm_store"], 1)

    def test_batch_missing_marker_partial_only_no_side_effects(self):
        run = self._drive(FakeClient(drop_ids={"2"}), auto_glossary=True)
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "error")
        self.assertEqual(run.calls["tm_store"], 0)
        self.assertEqual(run.calls["auto_glossary"], 0)
        self.assertEqual(run.calls["glossary_api"], 0)
        ps = row.get("pass_status") or {}
        self.assertEqual(
            (ps.get("Series-Memory") or {}).get("reason"), "unresolved_markers")
        self.assertEqual(
            (ps.get("Auto-Glossary") or {}).get("reason"), "unresolved_markers")

    def test_batch_write_error_isolates_file_others_survive(self):
        # Düz batch de aynı _write_results kuyruğunu kullanır: tek dosyanın
        # teslim yazım hatası ikinci dosyayı öldürmemeli.
        with patch.object(gui, "write_srt",
                          _write_srt_patch_factory(fail_prefixes=("bolum1",))):
            run = self._drive(FakeClient(),
                              names=("bolum1.srt", "bolum2.srt"))
        self.assertEqual(run.errors, [])
        rows = _rows_by_name(run)
        self.assertEqual(rows["bolum1.srt"]["run_status"], "error")
        self.assertEqual(rows["bolum2.srt"]["run_status"], "done")
        self.assertEqual(run.calls["tm_store"], 1)
        self.assertTrue(run.report_file.exists())


# ── Batch hibrit ──────────────────────────────────────────────────────────────

class BatchHybridFlowTest(_FlowCase):
    def _drive(self, client, auto_glossary=False, report_only=False,
               extra=None, names=("bolum.srt",)):
        self._tmp_obj = tempfile.TemporaryDirectory()
        tmp = self._tmp_obj.name
        if True:
            self.app, inp, out = _make_app(
                tmp, report_only=report_only, auto_glossary=auto_glossary)
            self.app.hybrid_var.set(True)
            fps = _write_srcs(inp, names)
            fp = fps[0]
            self.app._selected_files = list(fps)
            self.app._input_folder_explicitly_selected = True
            run = _instrument(self.app)
            if extra:
                extra(self.app, fp)
            cached = ht.empty_analysis_result("en")
            with patch.object(gui, "OpenAI", lambda *a, **k: client), \
                 patch.object(openai, "OpenAI", lambda *a, **k: client), \
                 patch.object(self.app, "_load_context_cache_for_file",
                              lambda *a, **k: cached), \
                 patch.object(self.app, "_project_memory_for",
                              lambda *a, **k: None), \
                 patch.object(self.app, "_notify", lambda *a, **k: None), \
                 patch.object(gui, "messagebox", _ns(
                     askyesno=lambda *a, **k: False,
                     showinfo=lambda *a, **k: None,
                     showerror=lambda *a, **k: None)):
                try:
                    self.app._run_hybrid("sk-fake", "", "")
                except Exception as exc:
                    run.errors.append(exc)
            run.inp, run.out = inp, out
            run.fps = fps
            run.fp, run.fname = fp, Path(fp).name
            run.report_file = _report_path(out)
            self.run = run
            return run

    def test_batch_hybrid_success_side_effects(self):
        run = self._drive(FakeClient())
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run).get(run.fname)
        self.assertIsNotNone(row, "rapor satırı yok")
        self.assertEqual(row["run_status"], "done")
        self.assertGreaterEqual(run.calls["tm_store"], 1)

    def test_batch_hybrid_missing_marker_records_skip_statuses(self):
        run = self._drive(FakeClient(drop_ids={"2"}), auto_glossary=True)
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "error")
        self.assertEqual(run.calls["tm_store"], 0)
        self.assertEqual(run.calls["auto_glossary"], 0)
        self.assertEqual(run.calls["glossary_api"], 0)
        ps = row.get("pass_status") or {}
        self.assertEqual(
            (ps.get("Series-Memory") or {}).get("reason"), "unresolved_markers",
            "batch hibrit eksik-işaret dalı Series-Memory atlamasını kaydetmiyor")
        self.assertEqual(
            (ps.get("Auto-Glossary") or {}).get("reason"), "unresolved_markers",
            "batch hibrit eksik-işaret dalı Auto-Glossary atlamasını kaydetmiyor")

    def test_batch_hybrid_write_error_isolates_file_others_survive(self):
        # Teslim yazımı tek dosyada patlarsa koşu ölmemeli; patlayan dosya
        # 'error' + Series-Memory/Auto-Glossary 'skipped/delivery_failed'
        # satırıyla rapora düşmeli, sağlam dosya teslim edilmeli.
        with patch.object(gui, "write_srt",
                          _write_srt_patch_factory(fail_prefixes=("bh1",))):
            run = self._drive(FakeClient(), auto_glossary=True,
                              names=("bh1.srt", "bh2.srt"))
        self.assertEqual(run.errors, [])
        rows = _rows_by_name(run)
        bad = rows.get("bh1.srt")
        self.assertIsNotNone(bad, "patlayan dosya raporda satır üretmeli")
        self.assertEqual(bad["run_status"], "error")
        self.assertEqual(rows["bh2.srt"]["run_status"], "done")
        self.assertTrue(Path(rows["bh2.srt"]["output_path"]).exists())
        ps = bad.get("pass_status") or {}
        self.assertEqual(
            (ps.get("Series-Memory") or {}).get("reason"), "delivery_failed",
            "yazım hatasında Series-Memory atlaması rapora düşmeli")
        self.assertEqual(
            (ps.get("Auto-Glossary") or {}).get("reason"), "delivery_failed",
            "yazım hatasında Auto-Glossary atlaması rapora düşmeli")
        self.assertEqual(run.calls["glossary_api"], 1,
                         "ücretli sözlük yalnız sağlam dosyada çağrılmalı")
        self.assertEqual(run.calls["tm_store"], 1,
                         "yalnız sağlam dosya TM'e yazmalı")
        self.assertTrue(run.report_file.exists())

    def test_batch_hybrid_auto_glossary_raise_is_isolated(self):
        # İsteğe bağlı sözlük patlaması başarılı teslimi 'error'a çevirmemeli;
        # satır 'done' + Auto-Glossary 'failed' ile rapora düşmeli.
        def _boom_glossary(*a, **k):
            raise RuntimeError("glossary patladi (fake)")

        run = self._drive(
            FakeClient(), auto_glossary=True,
            extra=lambda app, fp: patch.object(
                app, "_run_auto_glossary", _boom_glossary).start())
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "done",
                         "sözlük istisnası başarılı teslimi bozmamalı")
        ag = (row.get("pass_status") or {}).get("Auto-Glossary") or {}
        self.assertEqual(ag.get("status"), "failed")
        self.assertTrue(Path(row["output_path"]).exists())
        self.assertTrue(run.report_file.exists())

    def test_batch_hybrid_auto_glossary_only_on_success(self):
        # PR#2 regresyon bekçisi (çalışma-zamanı): başarılı dosyada ücretli
        # öneri denenir, eksik-işaretli dosyada denenmez.
        run = self._drive(FakeClient(), auto_glossary=True)
        self.assertEqual(run.errors, [])
        row = _rows_by_name(run)[run.fname]
        self.assertEqual(row["run_status"], "done")
        self.assertGreaterEqual(run.calls["auto_glossary"], 1)
        self.assertGreaterEqual(run.calls["glossary_api"], 1)


if __name__ == "__main__":
    unittest.main()
