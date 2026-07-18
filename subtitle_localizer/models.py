from dataclasses import dataclass, field
from typing import Any


@dataclass
class CharacterVoice:
    name: str
    speaking_style: str = ""


@dataclass
class ContextMemory:
    source_language: str = ""
    summary: str = ""
    setting: str = ""
    tone: str = ""
    characters: list[CharacterVoice] = field(default_factory=list)
    recurring_terms: dict[str, str] = field(default_factory=dict)
    scene_notes: list[str] = field(default_factory=list)


@dataclass
class ContextAnalysisRequest:
    cues: list[Any]
    glossary: dict[str, str] = field(default_factory=dict)
    style: str = "natural"
    source_language_hint: str | None = None
    target_language: str = "tr"

    @property
    def source_language(self) -> str:
        return self.source_language_hint or "en"
