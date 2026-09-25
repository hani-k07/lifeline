"""PII handling: mask for display, scrub before anything is sent to an external LLM."""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

# Pakistani CNIC: 13 digits, usually written 12345-1234567-1.
_CNIC = re.compile(r"(?<!\d)\d{5}-?\d{7}-?\d(?!\d)")
# Mobile (03xx-xxxxxxx, +92 3xx…) and landline (0xx-xxxxxxx); separators optional.
_PHONE = re.compile(r"(?<!\d)(?:\+92|0092|0)[-\s]?\d{2,3}[-\s]?\d{7,8}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PARENS = re.compile(r"\s*\([^)]*\)")


def mask_cnic(value: object) -> str:
    """35202-1234567-1 -> 35202-*******-1. Anything that is not a 13-digit CNIC is fully masked."""
    if value in (None, ""):
        return "—"
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 13:
        return "*" * 8
    return f"{digits[:5]}-*******-{digits[12]}"


def _name_variants(names: Iterable[str | None]) -> list[str]:
    variants: set[str] = set()
    for name in names:
        if not name:
            continue
        for candidate in (name.strip(), _PARENS.sub("", name).strip()):
            if len(candidate) >= 3:
                variants.add(candidate)
    return sorted(variants, key=len, reverse=True)          # longest first so "Ali Hassan" beats "Ali"


def scrub_text(text: str, names: Iterable[str | None] = ()) -> str:
    """Replace CNICs, emails, phone numbers and any known person name with placeholders.

    Free text can still carry a partial or misspelt name; callers avoid sending free text where they can.
    """
    out = _CNIC.sub("[CNIC]", text)
    out = _EMAIL.sub("[EMAIL]", out)
    out = _PHONE.sub("[PHONE]", out)
    for name in _name_variants(names):
        out = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "[NAME]", out, flags=re.IGNORECASE)
    return out


def scrub_rows(
    rows: Sequence[Mapping[str, Any]],
    keep: Iterable[str],
    text_fields: Iterable[str] = (),
    names: Iterable[str | None] = (),
) -> list[dict[str, Any]]:
    """Allow-list projection of DB rows for an LLM: only `keep` fields survive, and `text_fields`
    (free text) are scrubbed. Anything not listed — names, phones, CNICs — never leaves the app."""
    known = list(names)
    text = set(text_fields)
    result = []
    for row in rows:
        item = {k: row.get(k) for k in keep if k in row}
        for field in text:
            if isinstance(row.get(field), str):
                item[field] = scrub_text(row[field], known)
        result.append(item)
    return result
