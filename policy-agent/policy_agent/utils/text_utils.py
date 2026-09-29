from __future__ import annotations

import re

WHITESPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def clean_text(text: str) -> str:
    cleaned = text.replace("\x00", " ").replace("\ufeff", " ")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]
