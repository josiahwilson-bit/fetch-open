"""FETCH completeness checker.

Stdlib-only. Checks one listing (a mapping) for:
- a nonblank title
- a valid source URL
- a valid deadline when the source states one

If the source explicitly confirms applications are rolling or that
there is no deadline, the listing can still pass on the deadline field.

Returns COMPLETE or NEEDS_REVIEW and names any fields that need
attention. Input records are never modified and missing or vague
values are never guessed: a vague deadline such as "spring" or
"Spring 2027" yields NEEDS_REVIEW for ``deadline`` and the parsed
date stays blank (empty string).
"""

from __future__ import annotations

import copy
import datetime
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

COMPLETE = "COMPLETE"
NEEDS_REVIEW = "NEEDS_REVIEW"

_ROLLING_STATUSES = {"rolling", "no_deadline", "no deadline", "none stated - rolling"}


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _valid_url(value: Any) -> bool:
    if _is_blank(value) or not isinstance(value, str):
        return False
    if any(ch.isspace() for ch in value):
        return False
    try:
        parsed = urlparse(value.strip())
        hostname = parsed.hostname
    except ValueError:
        # Malformed URLs (e.g. an invalid IPv6 literal) make
        # urlparse or the hostname accessor raise; treat them as
        # invalid instead of letting the error stop the batch.
        return False
    return parsed.scheme in ("http", "https") and bool(hostname)


def _parse_iso_date(value: str) -> str:
    """Return the ISO date string if *value* is a strict YYYY-MM-DD
    calendar date, otherwise return "" (blank -- never guessed)."""
    text = value.strip()
    # Strict shape check so vague or free-text values never parse.
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        return ""
    try:
        parsed = datetime.date.fromisoformat(text)
    except ValueError:
        return ""
    # fromisoformat in newer Pythons accepts some non-strict forms;
    # the round-trip check keeps only exact YYYY-MM-DD.
    return parsed.isoformat() if parsed.isoformat() == text else ""


def check_listing(listing: Mapping[str, Any]) -> dict:
    """Check one listing without modifying it.

    Recognised fields:
    - ``title``: str
    - ``source_url``: str
    - ``deadline``: str in YYYY-MM-DD form, a free-text value as
      stated by the source, or None/blank
    - ``deadline_status``: optional str; ``"rolling"`` or
      ``"no_deadline"`` means the source explicitly confirmed that
      status, so no dated deadline is required.
    """
    # Work on a deep copy so the caller's record is never touched.
    record = copy.deepcopy(dict(listing))
    fields: list[str] = []
    reasons: dict[str, str] = {}

    title = record.get("title")
    if _is_blank(title) or not isinstance(title, str):
        fields.append("title")
        reasons["title"] = "title is missing or blank"

    source_url = record.get("source_url")
    if not _valid_url(source_url):
        fields.append("source_url")
        reasons["source_url"] = "source_url is missing, blank, or not a valid http(s) URL"

    deadline = record.get("deadline")
    status_raw = record.get("deadline_status")
    status = status_raw.strip().lower() if isinstance(status_raw, str) else ""
    parsed_deadline = ""

    if status in _ROLLING_STATUSES:
        # Source-confirmed rolling / no deadline: passes, and no
        # date is invented.
        parsed_deadline = ""
    elif _is_blank(deadline):
        fields.append("deadline")
        reasons["deadline"] = (
            "deadline is missing or blank and the source has not "
            "confirmed rolling or no-deadline status"
        )
    elif not isinstance(deadline, str):
        fields.append("deadline")
        reasons["deadline"] = "deadline is not a date string as stated by the source"
    else:
        parsed_deadline = _parse_iso_date(deadline)
        if not parsed_deadline:
            fields.append("deadline")
            reasons["deadline"] = (
                "deadline is not a valid YYYY-MM-DD date as stated "
                "by the source; no date was guessed"
            )

    return {
        "status": COMPLETE if not fields else NEEDS_REVIEW,
        "fields_needing_attention": fields,
        "reasons": reasons,
        "parsed_deadline": parsed_deadline,
    }


def check_listings(listings: Sequence[Mapping[str, Any]]) -> list[dict]:
    return [check_listing(listing) for listing in listings]


def format_report(listings: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    for listing, result in zip(listings, check_listings(listings)):
        title = listing.get("title")
        label = title.strip() if isinstance(title, str) and title.strip() else "(untitled)"
        if result["status"] == COMPLETE:
            detail = f"parsed_deadline={result['parsed_deadline'] or '(none - rolling/no deadline)'}"
            lines.append(f"{result['status']}: {label} - {detail}")
        else:
            joined = ", ".join(result["fields_needing_attention"])
            lines.append(f"{result['status']}: {label} - needs attention: {joined}")
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys

    with open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin as fh:
        data = json.load(fh)
    print(format_report(data))
