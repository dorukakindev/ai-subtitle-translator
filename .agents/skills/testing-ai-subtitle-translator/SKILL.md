---
name: testing-ai-subtitle-translator
description: How to launch and drive the CustomTkinter subtitle translator GUI on this Ubuntu X box, including how to trigger the provider live-check gate without real credentials
---

# Testing ai-subtitle-translator (CustomTkinter desktop app)

## Launch on this box

- The app DOES run on Linux despite the blueprint note claiming "uygulama Windows GUI'dir, Linux'ta çalıştırılmaz" — that note is stale. Windows-only code paths are guarded by `os.name`/`sys.platform` checks.
- Launch: `cd ~/repos/ai-subtitle-translator && PYTHONUTF8=1 .venv/bin/python subtitle_translator_gui.py` (venv is prebuilt; deps in requirements.txt already installed).
- The Tk window appears on `:0` titled "Subtitle Translator". Maximize with `wmctrl -i -r <winid> -b add,maximized_vert,maximized_horz`.
- First-run state can be reset by deleting `.gui_settings.json` (repo root, gitignored). Session logs are written to `logs/<date>_<pid>.log` — read them to verify log lines without relying on screenshots.
- Console stderr shows only a harmless `keyring` fallback warning on this box; credentials fall back to an obfuscated local file.

## UI map (English first-run language; DEFAULT_UI_LANGUAGE="English")

- Header: "+ Add files", "Add folder", and an "Interface" language OptionMenu (English/Türkçe) top-right — switching is in-place, no restart.
- Sidebar nav buttons (Connection/Translation/Language/Files/Quality/Tools) scroll to sections of a single scrollable panel — there are no real tabs.
- Known unlocalized leftovers in English mode (pre-existing, not bugs in your diff): phase strip "01 HAZIRLIK…04 TESLİM", a few TOOLS buttons ("Deneme çevirisi", "Onaylı tercihler"), file panel header "DOSYALAR", and all messagebox/session-log text (logs are Turkish by design).
- Start button: "▶ Çeviriyi başlat" / "Start translation" in the sidebar bottom.

## Triggering the provider live-check gate (`_provider_live_check`) without real API keys

The gate only fires for SHUAI_API hosts (api.shuaiapi.com, oai.sb, api.oai.sb, cdn.shuaiapi.com) and only inside the preflight chain:

1. Default config already qualifies: custom provider ON, route "CF optimize · api.shuaiapi.com", model "gpt-5.4".
2. Type any fake key ≥10 chars into the custom-provider "API key" field (masked entry under API SETTINGS).
3. Add a file via "+ Add files" (file dialog accepts typed paths; `test_input/dummy.srt` works). Newly added files default to content type "Otomatik" → the **content-type preflight** calls the gate. (Source-language preflight only fires if a file's language is "Otomatik"; default file language follows src_var = "English", so it's skipped.)
4. Press Start. File-integrity preflight auto-continues when clean; Turkish-source preflight passes silently for English files when target=Turkish; then the content-type preflight's gate runs `probe_api_key` against the real host.
5. With a fake key, api.shuaiapi.com returns a definitive 401 → gate logs "…başlatılmadı — sağlayıcı gerçek bir isteği karşılayamıyor" (err) and the run stops. If the host is unreachable the probe may retry up to ~160 s (4 routes × 2 turns × 20 s).
6. Pressing Start again must re-probe (a failure is never cached); only a real ok=True result caches for `_PROVIDER_LIVE_CHECK_TTL` = 120 s.

## Unit tests

- `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/bin/python -m unittest discover -s tests` — ~12 failures are expected on POSIX (Windows path semantics); tests/test_provider_live_check.py is platform-clean.
- To A/B a GUI-module change against old code without touching the checkout: `git worktree add /tmp/prefix HEAD^`, copy the new test file into it, run with the repo venv (`/home/ubuntu/repos/ai-subtitle-translator/.venv/bin/python -m unittest ...` from /tmp/prefix), then `git worktree remove --force /tmp/prefix`.

## Dialog quirks observed

- After "Add folder" picks a directory, a modal asks "Başka klasör eklemek ister misiniz?" (Yes/No) — answer No for a single folder.
- The file-integrity preflight may pop a Yes/No warnings dialog mid-run (e.g. duplicate content across selected files). If mouse clicks on Yes/No don't land (small buttons, modal grab), pressing Return activates the default (Yes).
- To widen the Stop window for mid-run cancel tests, add a folder of large .srt files (~340 KB each) — hundreds of tiny files scan in <1 s.

## Devin secrets needed

- None for gate/UI testing (fake keys suffice). A real translation run would need a valid OpenAI-compatible API key.
