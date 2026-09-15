# Subtitle Translator

[Türkçe](README.md) · [User guide (Turkish)](KILAVUZ.md) · [Privacy](PRIVACY.md) · [Security](SECURITY.md)

A Turkish-language Windows desktop application that translates `.srt`, `.vtt`,
`.ass`, and `.ssa` subtitles through OpenAI or OpenAI-compatible providers
while preserving context across cues.

Instead of treating cues as isolated strings, the application can supply nearby
dialogue, scene transitions, prior translation decisions, character relations,
and project terminology to the model. Output still requires human review; this
is an assistant, not a replacement for a professional translator.

## Highlights

- 60 language choices and 74 content-type schemas
- Encoding-aware SRT, WebVTT, and ASS/SSA support
- Chained context carrying earlier translations into later chunks
- Optional character, register, terminology, and scene analysis
- Approved term, name, and formal/informal address preferences
- Local translation memory plus Critic, Polish, Native Reader, and QC passes
- 39 addressable semantic and structural finding classes
- Source-preserving backups, recovery records, and report-only operation
- Optional OpenAI Batch API and embedded-subtitle extraction through FFmpeg
- Pilot translation and per-pass review/rollback tools

## Requirements

- Windows 10 or 11
- A stable Python 3.11 or newer release with Tk support
- An account/key for each remote provider, or a running local Ollama/LM Studio server
- FFmpeg and ffprobe only for subtitle extraction from video files

CI runs on Python 3.11 and 3.13. The local development environment has also
been verified with Python 3.13.

## Installation

Run in PowerShell:

```powershell
git clone https://github.com/dorukakindev/openai-altyazi-cevirisi.git
cd openai-altyazi-cevirisi
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe subtitle_translator_gui.py
```

Use `Başlat.bat` for later launches. It does not install packages at runtime;
it stops with an installation command if a required dependency is missing.
For video subtitle extraction, put `ffmpeg.exe` and `ffprobe.exe` on PATH or
under `tools/ffmpeg/`. FFmpeg is not needed for normal subtitle translation.

## First run

1. Create a provider profile under **API Anahtarları → Yeni Profil**.
2. Select profiles and models for the main and optional helper roles.
3. Add files or a folder and choose source and target languages.
4. Select a content type or keep automatic detection enabled.
5. Review the estimate, start translation, and inspect the quality report.

Removing a queue item never deletes its source file from disk.

## Providers and modes

Presets cover OpenAI, Google AI Studio, OpenRouter, Groq, DeepSeek, Mistral,
xAI, Together, Cerebras, Fireworks, Nebius, and Anthropic, with custom
OpenAI-compatible endpoints plus local Ollama and LM Studio profiles. Model
lists are fetched dynamically.

| Mode | Intended use | Important note |
| --- | --- | --- |
| Synchronous | Normal translation | Uses the complete chained-context flow. |
| Batch | Large queues | Official OpenAI Batch API only. |
| Assisted analysis | Quality first | Runs enabled analysis and quality passes. |

Each helper role may use a different profile. A local main model does not make
the entire workflow local when Critic, Polish, QC, or another helper role uses
a remote provider.

## Privacy and credentials

Subtitle text, context, and enabled analysis data may be sent to selected remote
providers. Batch mode uploads a request file to OpenAI. Read [PRIVACY.md](PRIVACY.md)
before processing confidential material.

Keys are normally stored in Windows Credential Manager through `keyring`. If
that service is unavailable, the application falls back to a user-restricted
but merely **obfuscated** local file. This is not cryptographic encryption. Do
not use the fallback for sensitive keys on a shared computer.

Report vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue.

## Local data

The application may retain subtitle text or run information in
`translation_memory.db`, `.context_cache/`, `.precontext.json`, `Raporlar/`,
`logs/`, and recovery records. These are excluded from Git. Remove personal
content before attaching diagnostics to a public issue.

## Settings, development, and tests

The full settings reference is [KILAVUZ.md](KILAVUZ.md) in Turkish.

```powershell
.\.venv\Scripts\python.exe belge_uret.py --kontrol
.\.venv\Scripts\python.exe -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Tests require no paid API calls. Read [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

## Limitations

The interface and reports are in Turkish. Quality depends on selected models,
and automated checks cannot detect every meaning error. Human review is needed
before publishing subtitles.

## Licence

[GNU General Public License v3.0](LICENSE). GPLv3 source-availability
requirements apply to distributed derivatives.
