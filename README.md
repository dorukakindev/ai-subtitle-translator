# AI Subtitle Translator

[![Tests](https://github.com/dorukakindev/ai-subtitle-translator/actions/workflows/tests.yml/badge.svg)](https://github.com/dorukakindev/ai-subtitle-translator/actions/workflows/tests.yml) [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE) [![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)

[Türkçe README](README.tr.md) · [User guide (Turkish)](KILAVUZ.md) · [Architecture](Architecture.md) · [Privacy](PRIVACY.md) · [Security](SECURITY.md)

A Windows desktop application that translates `.srt`, `.vtt`, `.ass`, and `.ssa`
subtitles through OpenAI or OpenAI-compatible providers while preserving context
across cues. The interface defaults to English and can be switched to Turkish
from the language control in the header.

Instead of treating cues as isolated strings, the application can supply nearby
dialogue, scene transitions, prior translation decisions, character relations,
and project terminology to the model. Output still requires human review; this
is an assistant, not a replacement for a professional translator.

## Contents

- [Highlights](#highlights)
- [Requirements](#requirements)
- [Installation](#installation)
- [First run](#first-run)
- [Providers and modes](#providers-and-modes)
- [Environment variables](#environment-variables)
- [Privacy and credentials](#privacy-and-credentials)
- [Local data](#local-data)
- [Settings, development, and tests](#settings-development-and-tests)
- [Limitations](#limitations)
- [Licence](#licence)

## Highlights

- English-first interface with a persistent English/Türkçe switch
- 60 translation-language choices and 74 content-type schemas
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
been verified with Python 3.13. The app also starts on Linux/X with a
Tk-enabled Python (`python3-tk`), but Windows is the supported target —
Tkinterdnd2 drag-and-drop and credential storage behave differently there.

## Installation

Run in PowerShell:

```powershell
git clone https://github.com/dorukakindev/ai-subtitle-translator.git
cd ai-subtitle-translator
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

## Environment variables

API keys belong in provider profiles (stored in the credential store), not the
environment. The app reads only a few optional variables:

| Name | Required | Default | Description |
| --- | --- | --- | --- |
| `SUBTITLE_TRANSLATOR_STATE_DIR` | no | repo directory | Redirects where settings, caches, and memory files are kept. Used by tests and pilot runs. |
| `AWS_DEFAULT_REGION` / `AWS_REGION` | no | `eu-north-1` | Region for AWS Bedrock helper profiles. |

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

The interface is available in English and Turkish. Translation reports and some
diagnostic output remain Turkish. Quality depends on selected models, and
automated checks cannot detect every meaning error. Human review is needed
before publishing subtitles.

## Licence

[GNU General Public License v3.0](LICENSE). GPLv3 source-availability
requirements apply to distributed derivatives.
