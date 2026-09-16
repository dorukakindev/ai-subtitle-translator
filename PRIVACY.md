# Privacy Notice

AI Subtitle Translator is a locally run desktop client. The project maintainer
does not operate a central service that collects your subtitles. However, the
model providers you select and files retained on your computer may process or
store data.

## Data that may be sent to remote providers

Depending on enabled settings and role profiles, the following may be sent to
the main translation, analysis, Critic, Polish, Native Reader, or QC provider:

- subtitle text and cue identifiers;
- surrounding dialogue and scene context;
- earlier translations, glossaries, and approved terminology;
- character, address, tone, scene, and consistency analyses;
- source and translated excerpts used for quality review.

Batch mode uploads a request file to the official OpenAI Batch API. Each helper
role can use a separate provider profile, so selecting a local main model does
not make the whole workflow local. Review every enabled role before processing
confidential material. Provider retention, training, and privacy practices are
governed by that provider's terms.

## Data stored locally

The application may create:

- interface settings that do not contain API keys;
- credentials in Windows Credential Manager;
- a user-restricted obfuscated credential file if keyring is unavailable;
- a SQLite translation-memory database containing source/translation pairs;
- analysis caches, reports, logs, backups, and recovery records;
- series/project preferences and approved terminology.

The fallback credential file is obfuscated, not cryptographically encrypted.
Do not rely on it for sensitive credentials on a shared computer.

## Your controls

- To reduce remote transfer, use Ollama or LM Studio and select local profiles
  for every helper role, or disable those roles.
- Review translation memory, reports, logs, and caches before sharing them.
- Revoke and rotate a provider key immediately if you suspect exposure.
- Close the application and active writes before manually moving or deleting
  SQLite files.

This document is a technical summary of application data flow, not a legal
privacy agreement. Report discrepancies through [SECURITY.md](SECURITY.md).
