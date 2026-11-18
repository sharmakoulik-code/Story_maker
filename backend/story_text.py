"""Small offline text primitives. No tokenizer, language model, or network required."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TERMINALS = ".!?…。।॥"
ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "prof", "st", "vs", "jr", "sr"}
OPEN_QUOTES = {'"': '"', '“': '”', '«': '»'}
QUOTED = re.compile(r'"([^"\n]+)"|“([^”\n]+)”|«([^»\n]+)»')
SPEAKER_LINE = re.compile(r"^([^:：]{1,36})[:：]\s+(.+)$")
EN_NAME = r"[A-Z][a-z]+(?:[ -][A-Z][a-z]+)?"
TAGS = r"(?:said|says|asked|asks|whispered|whispers|replied|replies|shouted|called|murmured|answered|cried)"
BEFORE_QUOTE = re.compile(rf"\b({EN_NAME}|[Hh]e|[Ss]he|[Tt]hey|[Ii])\s+(?i:{TAGS})\s*[, :—]*$")
AFTER_QUOTE = re.compile(rf"\s*[,—-]?\s*(?:({EN_NAME}|[Hh]e|[Ss]he|[Tt]hey|[Ii])\s+(?i:{TAGS})|(?i:{TAGS})\s+({EN_NAME}|he|she|they))\b")


@dataclass(frozen=True)
class Line:
    speaker: str
    text: str


def words(text: str) -> list[str]:
    """Keep Devanagari and Bengali combining marks in the corresponding word."""
    result, start = [], None
    for index, char in enumerate(text):
        if char.isalnum():
            if start is None:
                start = index
        elif start is not None:
            if unicodedata.category(char).startswith("M") or char in "\u200c\u200d":
                continue
            if char in "'’-" and index + 1 < len(text) and text[index + 1].isalnum():
                continue
            result.append(text[start:index])
            start = None
    if start is not None:
        result.append(text[start:])
    return result


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[:limit - 1]
    boundary = head.rfind(" ")
    return (head[:boundary] if boundary > limit * 0.75 else head).rstrip() + "…"


def script_hint(text: str) -> str:
    scripts = {"Latin": 0, "Devanagari": 0, "Bengali": 0, "other": 0}
    for char in text:
        if char.isalpha():
            point = ord(char)
            name = ("Devanagari" if 0x0900 <= point <= 0x097F else "Bengali" if 0x0980 <= point <= 0x09FF
                    else "Latin" if char.isascii() or "LATIN" in unicodedata.name(char, "") else "other")
            scripts[name] += 1
    total = sum(scripts.values())
    if not total:
        return "unknown"
    script, count = max(scripts.items(), key=lambda entry: entry[1])
    return ("mixed" if count * 5 < total * 4 else "unknown" if script == "other" else script)


def speaker_line(line: str) -> tuple[str, str] | None:
    match = SPEAKER_LINE.match(line)
    if not match:
        return None
    speaker, spoken = match.groups()
    tokens = words(speaker)
    if not 1 <= len(tokens) <= 3 or any(any(char.isdigit() for char in token) for token in tokens):
        return None
    blocked = {"chapter", "scene", "title", "story", "note", "part", "act", "ending", "অধ্যায়", "अध्याय"}
    if {word.casefold() for word in tokens} & blocked:
        return None
    # Latin prose before a colon is not usually a cast label. Other scripts have no case.
    if script_hint(speaker) == "Latin" and not all(token[0].isupper() for token in tokens):
        return None
    return speaker.strip(), spoken.strip()


def passages(story: str) -> list[str]:
    chunks: list[str] = []
    for raw in story.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        if speaker_line(line):
            chunks.append(line)
            continue
        start, index, closer = 0, 0, None
        while index < len(line):
            char = line[index]
            if closer:
                if char == closer:
                    closer = None
                index += 1
                continue
            if char in OPEN_QUOTES and closer_for(line, index, char):
                closer = OPEN_QUOTES[char]
                index += 1
                continue
            if char not in TERMINALS:
                index += 1
                continue
            if char == ".":
                left = re.search(r"([A-Za-z]+)$", line[max(start, index - 12):index])
                if ((left and left[1].casefold() in ABBREVIATIONS) or
                        (index and index + 1 < len(line) and line[index-1].isdigit() and line[index+1].isdigit())):
                    index += 1
                    continue
            end = index + 1
            while end < len(line) and line[end] in TERMINALS:
                end += 1
            if end == len(line) or line[end].isspace() or char in "।॥。":
                chunks.append(line[start:end].strip())
                start = end
            index = end
        if line[start:].strip():
            chunks.append(line[start:].strip())
    return [part for part in chunks if any(char.isalnum() for char in part)]


def closer_for(line: str, index: int, opener: str) -> bool:
    return line.find(OPEN_QUOTES[opener], index + 1) != -1


def separate_speech(passage: str) -> tuple[str, list[Line]]:
    labelled = speaker_line(passage)
    if labelled:
        speaker, text = labelled
        text = text.strip('"“”«»').strip()
        if speaker.casefold() in {"narrator", "voiceover", "বর্ণনাকারী", "वाचक"}:
            return text, []
        return "", [Line(speaker, text)]
    pieces, dialogue, end_previous = [], [], 0
    for match in QUOTED.finditer(passage):
        before = passage[end_previous:match.start()]
        tag = BEFORE_QUOTE.search(before)
        after = AFTER_QUOTE.match(passage, match.end())
        speaker = tag[1] if tag else next((name for name in after.groups() if name), "") if after else ""
        dialogue.append(Line(speaker, next(part for part in match.groups() if part is not None)))
        pieces.append(before[:tag.start()] if tag else before)
        end_previous = after.end() if after and not tag else match.end()
    if not dialogue:
        return passage, []
    remaining = " ".join((" ".join(pieces) + " " + passage[end_previous:]).split()).strip(" ,:—;.!?।")
    return remaining if words(remaining) else "", dialogue
