# Contributing

Thank you for improving AI Subtitle Translator. The project values measured,
reproducible changes over broad claims. Please keep subtitle integrity, privacy,
and API cost in mind throughout a contribution.

## Before opening a pull request

1. Open an issue for substantial behavior or architecture changes.
2. Use synthetic or redistributable subtitle samples. Never commit API keys,
   private subtitles, personal paths, raw user logs, caches, or databases.
3. Update both the English UI catalog and its Turkish source copy for user-facing
   interface changes; keep code identifiers in English.
4. Preserve cue IDs, timestamps, cue boundaries, formatting tags, and source
   backups unless the change explicitly targets one of those structures.
5. Apply shared behavior to every relevant translation flow and keep the sync
   and assisted-analysis prompts semantically aligned.

## Detection rules

A new detector must be measured on representative subtitle data. Report both
true findings and false positives. Do not raise a finding to a blocking severity
without evidence that its precision justifies blocking delivery.

## Automatic text changes

Any code that rewrites subtitle text needs:

- a narrow scope or allowlist;
- an invariant such as stable cue count, timestamps, and line boundaries;
- tests for legitimate text that resembles the targeted error;
- human-readable before/after examples.

Avoid computing the same decision independently in several flows. Extract a
shared pure helper where practical, then add a thin call site to each flow.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe subtitle_translator_gui.py
```

Run the offline checks:

```powershell
.\.venv\Scripts\python.exe belge_uret.py --kontrol
.\.venv\Scripts\python.exe -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

After a GUI change, also run the headless smoke test when no live translation is
using the same working directory:

```powershell
.\.venv\Scripts\python.exe -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"
```

The generated Turkish user guide is sourced from `kilavuz.py`. Do not edit
`KILAVUZ.md` by hand; regenerate it with `python belge_uret.py`.

## Pull request checklist

- Explain the user-visible problem and root cause.
- List the affected translation flows and settings.
- Include tests and the exact commands/results.
- State any checks you could not run.
- Keep the pull request focused; do not mix unrelated cleanup.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
