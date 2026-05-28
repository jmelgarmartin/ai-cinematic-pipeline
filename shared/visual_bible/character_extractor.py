"""Deterministic character hints for visual bible prompts."""

from __future__ import annotations

import re


CHARACTER_PATTERN = re.compile(r"\b[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ]{2,}\b")


def extract_character_hints(text: str) -> list[str]:
    """Return likely character names mentioned in screenplay/storyboard text."""

    ignored = {
        "ESCENA",
        "SHOT",
        "INT",
        "EXT",
        "OPEN",
        "JSON",
        "MODEL",
        "TRUE",
        "FALSE",
        "CAFETERIA",
        "CAFETERÍA",
        "LOCAL",
        "MILETOWN",
        "PEQUEÑO",
        "SUR",
        "TARDE",
        "ZONA",
    }
    names = {
        match.group(0).title()
        for match in CHARACTER_PATTERN.finditer(text)
        if match.group(0) not in ignored
    }
    return sorted(names)
