"""Lightweight helpers for extracting candidate visual beats from screenplay text."""

from __future__ import annotations

import re


SLUGLINE_PATTERN = re.compile(r"^##\s+(?:INT|EXT|INT/EXT|INT\.?/EXT\.?)\.", re.IGNORECASE)


def extract_candidate_beats(screenplay_markdown: str) -> list[str]:
    """Return compact screenplay chunks that may become storyboard shots."""

    beats: list[str] = []
    current: list[str] = []
    for raw_line in screenplay_markdown.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("# ESCENA"):
            continue
        if SLUGLINE_PATTERN.match(line) and current:
            beats.append("\n".join(current).strip())
            current = [line]
            continue
        current.append(line)
        if len(" ".join(current).split()) >= 80:
            beats.append("\n".join(current).strip())
            current = []
    if current:
        beats.append("\n".join(current).strip())
    return [beat for beat in beats if beat]
