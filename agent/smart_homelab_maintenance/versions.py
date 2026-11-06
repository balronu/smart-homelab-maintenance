"""Conservative version parsing and comparison."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ValidationError

_VERSION = re.compile(r"^(?:v)?(0|[1-9]\d*)(?:\.(0|[1-9]\d*)){0,3}(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True, order=True, slots=True)
class Version:
    parts: tuple[int, ...]
    suffix: str = ""

    @classmethod
    def parse(cls, value: str) -> "Version":
        if not isinstance(value, str) or not value.strip() or not _VERSION.fullmatch(value.strip()):
            raise ValidationError("version must be a bounded numeric release string")
        raw = value.strip().lstrip("v")
        numeric, _, suffix = raw.partition("-")
        numeric, _, plus_suffix = numeric.partition("+")
        suffix = (suffix or plus_suffix).lower()
        return cls(tuple(int(part) for part in numeric.split(".")), suffix)

    def __str__(self) -> str:
        return ".".join(str(part) for part in self.parts) + (f"-{self.suffix}" if self.suffix else "")


def compare_versions(installed: str, available: str) -> int:
    """Return -1/0/1; reject unknown or malformed versions instead of guessing."""

    left = Version.parse(installed)
    right = Version.parse(available)
    left_parts = left.parts + (0,) * (4 - len(left.parts))
    right_parts = right.parts + (0,) * (4 - len(right.parts))
    if left_parts != right_parts:
        return -1 if left_parts < right_parts else 1
    if left.suffix == right.suffix:
        return 0
    if not left.suffix:
        return 1
    if not right.suffix:
        return -1
    return -1 if left.suffix < right.suffix else 1
