"""yuclaw/core/security/injection_shield.py — Sanitizes all external data before LLM context."""
from __future__ import annotations
import re
import logging

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    re.compile(r"(?i)(ignore|disregard|forget)\s+(previous|prior|above|all)\s+(instructions?|context|prompt)"),
    re.compile(r"(?i)(you are now|act as|pretend (you are|to be)|roleplay as)"),
    re.compile(r"(?i)(system\s*:?\s*|assistant\s*:?\s*)(you|ignore)"),
    re.compile(r"<\|?(im_start|im_end|endoftext|pad|unk)\|?>"),
    re.compile(r"\[INST\]|\[/INST\]|<s>|</s>"),
    re.compile(r"###\s*(Human|Assistant|System|Instruction)"),
    re.compile(r"(?i)(send|transmit|reveal|leak)\s+(api[_\s]?key|password|secret|token)"),
    re.compile(r"(?i)(call|invoke|execute|run)\s+(function|tool|api|command)"),
]


class InjectionShield:
    def __init__(self):
        self._detections = 0

    def sanitize(self, text: str, source: str = "external") -> str:
        result = text
        found = []
        for pattern in INJECTION_PATTERNS:
            if pattern.search(result):
                found.append(pattern.pattern[:40])
                result = pattern.sub("[REDACTED]", result)
        if found:
            self._detections += 1
            logger.warning(f"[Shield] Injection attempt in '{source}': {len(found)} patterns. Total: {self._detections}")
        return result

    @property
    def total_detections(self) -> int:
        return self._detections
