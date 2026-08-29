# Altyazı Çevirisi — Subtitle Translator

*[Türkçe README](README.md)*

A Windows desktop application that translates subtitle files (`.srt`, `.vtt`,
`.ass`/`.ssa`) through the OpenAI API — into Turkish, or any of 60 languages.

Most tools translate a subtitle line at a time. This one is built around a
single observation: **a subtitle line does not mean anything on its own.** How
you translate "Get him." depends on who is saying it to whom, what was said two
lines earlier, and whether this character has been addressed formally since the
beginning of the film. The program shows the model all of it.

The interface, logs and reports are in **Turkish**. The code is not.

<!-- Add a screenshot here: docs/screenshot.png -->

---

## What it does

**Translates with context.** Each chunk is sent with the lines before it, the
lines after it (read-ahead), a bridge across scene cuts, and — most
importantly — **how the previous lines were actually translated**. That last
one is why a character's name or a form of address does not change at a chunk
boundary.

**Reads the file first.** An optional pre-pass analyses the whole subtitle:
who the characters are, who addresses whom formally, which terms recur, the
emotional register of each scene. That analysis is then injected into every
translation prompt.

**Knows the genre.** 74 content-type schemas (documentary, anime, tabletop RPG,
comedy, history…), each with its own translation rules — narrator register for
a documentary, honorifics for anime, military terminology for a war film. An
"automatic" option detects the genre from the file itself.

**Remembers a series.** Decisions made in one episode — how a name is spelled,
what a term maps to, who addresses whom formally — carry into later episodes.
An optional end-of-season pass looks for drift between episodes.

**Audits its own output.** The delivered file is compared against the source
and searched for **39 classes of finding**: missing dialogue, untranslated
fragments, garbled words, cue numbers leaked into the text, residual
hearing-impaired tags, foreign scripts, an echo between neighbouring cues, a
translator's gloss the source never had. Every finding is addressed by cue
number and timestamp — the report tells you which line to look at.

**Says what it did.** Every run produces a quality report and a findings log:
which passes ran, what they changed, what they skipped and why.

**Tries not to break things.** Because quality passes can rewrite text, the
state before those passes is backed up separately, and the content difference
between the backup and the delivery is audited on its own. In "report only"
mode no automatic corrector touches the delivered text — findings are written
down and the decision is yours.

---

## Install

Requires **Windows** and **Python 3.11+** (developed on 3.14).

```bash
pip install -r requirements.txt
python subtitle_translator_gui.py
```

### API key

Keys are **never written to the settings file**. They live in the Windows
Credential Manager via `keyring`; if that is unavailable the program falls back
to an obfuscated local file.

One OpenAI key is enough. The main translation can optionally be routed through
a third-party OpenAI-compatible endpoint; those fields are entirely separate
from the real OpenAI key field and cannot corrupt it.

---

## Three modes

| mode | when | note |
|---|---|---|
| **Synchronous** | Normal use | Best consistency; chained context works fully |
| **Batch** | Many files, no hurry | 50% cheaper, can take hours |
| **Assisted analysis** | Quality first | Pre-analysis plus quality passes |

An interrupted batch is not lost — the batch id is recorded and the program
offers to resume on startup. The same is true after a crash or a power cut:
unfinished files are queued rather than retranslated from scratch.

---

## Settings

The in-app **Help** window documents every setting: what it does, its default,
and when to turn it on. Hovering a switch shows a one-line version.

Full reference: [KILAVUZ.md](KILAVUZ.md) (Turkish). That file is generated from
`kilavuz.py` and is not edited by hand.

Three worth knowing:

- **Report only** (default on) — automatic correctors do not modify the
  delivered text, they only report. Keep this on if a human or another model
  will review the translation.
- **Chained context** (default on) — the single strongest tool for consistency.
- **Raw translation backup** (default on) — the state before quality passes. If
  a pass damages a line, the good version is still there.

---

## Tests

376 test modules, roughly 4,800 tests. No network access required.

```bash
python -m unittest discover -s tests
```

Most tests exercise pure functions and run without constructing the interface —
a deliberate choice that keeps the logic separate and testable.

Some tests lock the **false-positive rate** of a detection rule. In this project
a detection rule is not added until it has been measured against real delivered
files in both directions: what it catches *and* what it wrongly flags.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) (Turkish). The three rules that matter:
measure a detector in both directions before adding it, guard anything that
rewrites text with an invariant, and never compute one decision in two places.
Each of those comes from a bug this repository actually shipped.

---

## Licence

GNU General Public License v3.0 — see [LICENSE](LICENSE).

You may use, modify and redistribute this program, including commercially, but
anything you distribute that is derived from it must also be free software
under the same licence, with source available.

---

## Worth knowing

- Translation quality depends on the model you choose. Cheaper models drift on
  terminology and can desynchronise on long files; the program catches much of
  that but cannot repair all of it.
- This is a **translation assistant**, not a translator. Work intended for
  publication is expected to be reviewed — the reports exist for exactly that.
