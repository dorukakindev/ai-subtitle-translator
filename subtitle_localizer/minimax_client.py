import json

from openai import OpenAI

from .models import CharacterVoice, ContextMemory


class MiniMaxAPIError(RuntimeError):
    pass


class MiniMaxProvider:
    """Eski MiniMax arayüzüyle uyumlu, OpenAI-compatible analiz sağlayıcısı."""

    def __init__(self, api_key: str, api_url: str, model: str):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

    def analyze_context(self, request):
        sample = [
            {"i": c.index, "t": c.text}
            for c in (request.cues or [])[:500]
            if getattr(c, "text", "").strip()
        ]
        prompt = (
            "Analyze these subtitles for translation context. Return ONLY JSON with keys: "
            "source_language, summary, setting, tone, characters, recurring_terms, scene_notes.\n"
            f"Source language: {request.source_language}\n"
            f"Target language: {request.target_language}\n"
            f"Style: {request.style}\n"
            f"Glossary: {json.dumps(request.glossary or {}, ensure_ascii=False)}\n"
            f"Subtitles: {json.dumps(sample, ensure_ascii=False)}"
        )
        client = OpenAI(api_key=self.api_key, base_url=self.api_url)
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=2000,
            )
        except Exception as exc:
            raise MiniMaxAPIError(str(exc)) from exc

        raw = resp.choices[0].message.content if resp.choices else "{}"
        try:
            data = json.loads(raw)
        except Exception as exc:
            snippet = (raw or "")[:300]
            tail = (raw or "")[-300:] if len(raw or "") > 600 else ""
            msg = (
                f"context analysis returned invalid JSON "
                f"[raw head: {snippet}]" + (f" [raw tail: {tail}]" if tail else "")
            )
            raise MiniMaxAPIError(msg) from exc

        return ContextMemory(
            source_language=str(data.get("source_language") or request.source_language or ""),
            summary=str(data.get("summary") or ""),
            setting=str(data.get("setting") or ""),
            tone=str(data.get("tone") or ""),
            characters=[
                CharacterVoice(str(c.get("name", "")).strip(), str(c.get("speaking_style", "")).strip())
                for c in data.get("characters", [])
                if isinstance(c, dict) and c.get("name")
            ],
            recurring_terms={
                str(k): str(v)
                for k, v in (data.get("recurring_terms") or {}).items()
            } if isinstance(data.get("recurring_terms"), dict) else {},
            scene_notes=[
                str(x)
                for x in (data.get("scene_notes") or [])
            ] if isinstance(data.get("scene_notes"), list) else [],
        )
