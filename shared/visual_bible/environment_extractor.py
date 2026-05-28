"""Deterministic environment hints for visual bible prompts."""

from __future__ import annotations

import re


LOCATION_PATTERN = re.compile(r"\b(?:INT|EXT|INT/EXT|INT\.?/EXT\.?)\.\s+([^\n#]+)")
JSON_LOCATION_PATTERN = re.compile(r'"location"\s*:\s*"([^"]+)"')


def extract_environment_hints(text: str) -> list[str]:
    """Return likely locations from sluglines and storyboard location fields."""

    locations: set[str] = set()
    for match in LOCATION_PATTERN.finditer(text):
        locations.add(match.group(1).strip(" -").title())
    for match in JSON_LOCATION_PATTERN.finditer(text):
        locations.add(match.group(1).strip().title())
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Location:"):
            _, _, value = stripped.partition(":")
            locations.add(value.strip().title())
    return sorted(location for location in locations if location)
