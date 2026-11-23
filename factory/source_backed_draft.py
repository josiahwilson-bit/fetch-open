"""Source-backed draft builder + missing-field checker +
owner review screen (sandbox).

Built 2026-11-22 from Factory idea 077, approved by the
owner by tapped option in chat ("077 Yes — build it"):

- Draft builder: turns supplied photos, listing copy, and
  links into a short promo for each subject; every factual
  claim in the draft links back to its source.
- Missing-field checker: extends the missing-field idea
  behind idea 075 — unknown fields stay blank, and missing,
  stale, or conflicting details are flagged for review.
- Owner review screen: shows the draft, its evidence, and
  what changed since the last version; it records the
  owner's decision on that exact version (bound by the
  draft's version hash); the workflow stays SIMULATION_ONLY.

Definitions, held in code:
- A SUBJECT is a dict handed in by the caller:
    {"subject_id": str, "title": str,
     "fields": {field_name: [claim, ...]},
     "required_fields": [field_name, ...]   (optional;
        defaults to every field named in "fields"),
     "photos": [claim, ...], "links": [claim, ...]}
  A CLAIM is {"value": ..., "source": str,
  "observed_at": "YYYY-MM-DD" (optional)}.
  Claims are the ONLY source of facts. Nothing is inferred
  from a title, a photo filename, or another subject.
- A field's value is RESOLVED only when its claims agree on
  exactly one distinct non-blank value. Two or more distinct
  non-blank values are a CONFLICT: the draft leaves the
  field blank and flags every competing value with its
  source — it never picks a winner.
- A required field with no claims, or only blank claims, is
  MISSING: the draft leaves it blank and flags it. A missing
  value is never zero-filled or invented.
- A resolved claim whose `observed_at` is older than the
  caller-supplied `stale_days` window (measured against the
  caller-supplied `as_of` date) is flagged STALE; its value
  still shows, with its source, for the owner to judge.
- Evidence is per-subject: a draft carries only the sources
  handed in with that subject. Building two subjects in one
  call never mixes their evidence.

Rules this build holds:
- Read-only on inputs: drafts are built from deep copies;
  handed-in subjects are never modified.
- Every draft carries a `version_hash` (SHA-256 of its
  canonical content). An owner decision records against
  that exact hash; a decision offered for a different hash
  is refused, not applied.
- The review screen's diff compares field values, statuses,
  and evidence against a previous draft of the SAME subject;
  a previous draft of another subject is refused.
- No differential is claimed: DIFFERENTIAL kind is
  UNDEFINED (no measured saving exists yet; never
  zero-filled or estimated here).
- Everything is stamped SIMULATION_ONLY and authorizes:
  False. No network, fetch, send, publish, or deployment
  path; subjects are only ever handed in by the caller.
"""
import copy
import hashlib
import json
from datetime import date

__all__ = ["build_draft", "build_drafts", "check_fields",
           "review_screen", "record_owner_decision",
           "UNDEFINED", "MISSING", "CONFLICT", "STALE", "OK"]

UNDEFINED = "UNDEFINED"
OK = "OK"
MISSING = "MISSING"
CONFLICT = "CONFLICT"
STALE = "STALE"

DIFFERENTIAL = {
    "kind": UNDEFINED,
    "basis": "No measured operator saving exists for the "
             "draft builder yet; a differential stays "
             "UNDEFINED, never estimated or zero-filled.",
}


def _parse_date(value):
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _distinct_values(claims):
    seen = []
    for claim in claims:
        value = claim.get("value")
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        if value is None:
            continue
        if value not in seen:
            seen.append(value)
    return seen


def _evidence_for(claims):
    out = []
    for claim in claims:
        value = claim.get("value")
        if isinstance(value, str):
            value = value.strip()
        out.append({"value": value,
                    "source": claim.get("source"),
                    "observed_at": claim.get("observed_at")})
    return out


def check_fields(subject, as_of=None, stale_days=None):
    """Check one handed-in subject's fields. Returns a list
    of per-field results in required-field order, then any
    extra fields handed in, each:
    {"field", "status", "value", "evidence", "flags"}.
    status is OK, MISSING, CONFLICT, or STALE (a resolved
    value flagged stale). value is None for MISSING and
    CONFLICT — the field stays blank, never filled in."""
    fields = subject.get("fields") or {}
    required = subject.get("required_fields")
    if required is None:
        ordered = list(fields.keys())
    else:
        ordered = list(required) + [f for f in fields.keys()
                                     if f not in required]
    as_of_date = _parse_date(as_of)
    results = []
    for field in ordered:
        claims = fields.get(field) or []
        if not isinstance(claims, list):
            claims = [claims]
        evidence = _evidence_for(claims)
        distinct = _distinct_values(claims)
        flags = []
        if not distinct:
            status = MISSING
            value = None
            flags.append(
                "MISSING: %s was not supplied; it stays blank "
                "and is never invented" % field)
        elif len(distinct) > 1:
            status = CONFLICT
            value = None
            flags.append(
                "CONFLICT: %s has %d distinct supplied values "
                "(%s); the draft leaves it blank and picks "
                "no winner" % (field, len(distinct),
                               ", ".join(repr(v) for v in distinct)))
        else:
            status = OK
            value = distinct[0]
            if as_of_date is not None and stale_days is not None:
                stale_sources = []
                for claim in claims:
                    seen_on = _parse_date(claim.get("observed_at"))
                    if seen_on is not None and \
                            (as_of_date - seen_on).days > stale_days:
                        stale_sources.append(claim.get("source"))
                if stale_sources:
                    status = STALE
                    flags.append(
                        "STALE: %s evidence from %s is older "
                        "than %s days as of %s; flagged for "
                        "review, value shown with its source"
                        % (field, ", ".join(str(s) for s in stale_sources),
                           stale_days, as_of))
        results.append({"field": field, "status": status,
                        "value": value, "evidence": evidence,
                        "flags": flags})
    return results


def _version_hash(payload):
    canonical = json.dumps(payload, sort_keys=True,
                           default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_draft(subject, as_of=None, stale_days=None):
    """Build one source-backed draft for one handed-in
    subject. Every resolved line carries its evidence;
    MISSING and CONFLICT fields render blank in the promo
    text and appear in "flags". The draft carries only this
    subject's evidence. Inputs are never modified."""
    subject = copy.deepcopy(subject)
    checks = check_fields(subject, as_of=as_of,
                          stale_days=stale_days)
    lines = []
    promo_parts = []
    if subject.get("title"):
        promo_parts.append(str(subject["title"]))
    for check in checks:
        shown = "" if check["value"] is None else str(check["value"])
        lines.append({"field": check["field"],
                      "status": check["status"],
                      "value": check["value"],
                      "text": shown,
                      "evidence": check["evidence"],
                      "flags": check["flags"],
                      "simulation_only": True,
                      "authorizes": False})
        promo_parts.append("%s: %s" % (check["field"], shown))
    media = {"photos": _evidence_for(subject.get("photos") or []),
             "links": _evidence_for(subject.get("links") or [])}
    core = {"subject_id": subject.get("subject_id"),
            "title": subject.get("title"),
            "lines": [{"field": l["field"], "status": l["status"],
                       "value": l["value"],
                       "evidence": l["evidence"]} for l in lines],
            "media": media}
    return {
        "subject_id": subject.get("subject_id"),
        "title": subject.get("title"),
        "lines": lines,
        "promo_text": "\n".join(promo_parts),
        "media": media,
        "flags": [flag for l in lines for flag in l["flags"]],
        "missing_fields": [l["field"] for l in lines
                           if l["status"] == MISSING],
        "conflict_fields": [l["field"] for l in lines
                            if l["status"] == CONFLICT],
        "stale_fields": [l["field"] for l in lines
                         if l["status"] == STALE],
        "version_hash": _version_hash(core),
        "differential": dict(DIFFERENTIAL),
        "simulation_only": True,
        "authorizes": False,
    }


def build_drafts(subjects, as_of=None, stale_days=None):
    """Build drafts for several handed-in subjects in one
    call. Each draft is built from its own subject alone, so
    evidence never crosses between subjects."""
    return [build_draft(s, as_of=as_of, stale_days=stale_days)
            for s in subjects]


def _diff(previous, current):
    changes = []
    prev = {l["field"]: l for l in previous.get("lines", [])}
    curr = {l["field"]: l for l in current.get("lines", [])}
    for field in sorted(set(prev) | set(curr)):
        if field not in prev:
            changes.append({"field": field, "change": "ADDED",
                            "from": None, "to": curr[field]["value"]})
        elif field not in curr:
            changes.append({"field": field, "change": "REMOVED",
                            "from": prev[field]["value"], "to": None})
        elif prev[field]["value"] != curr[field]["value"] or \
                prev[field]["status"] != curr[field]["status"] or \
                prev[field]["evidence"] != curr[field]["evidence"]:
            changes.append({"field": field, "change": "CHANGED",
                            "from": prev[field]["value"],
                            "to": curr[field]["value"],
                            "from_status": prev[field]["status"],
                            "to_status": curr[field]["status"]})
    return changes


def review_screen(draft, previous_draft=None):
    """The owner review screen for one draft, as data: the
    draft itself, its full evidence, the diff since the
    previous version of the SAME subject (empty when there
    is no previous version), and an empty decision slot to
    be filled by record_owner_decision. A previous draft of
    a different subject raises ValueError — evidence and
    history never cross subjects."""
    if previous_draft is not None and \
            previous_draft.get("subject_id") != draft.get("subject_id"):
        raise ValueError(
            "previous_draft is for subject %r, not %r; a "
            "review screen never mixes subjects"
            % (previous_draft.get("subject_id"),
               draft.get("subject_id")))
    return {
        "subject_id": draft.get("subject_id"),
        "version_hash": draft.get("version_hash"),
        "draft": copy.deepcopy(draft),
        "evidence": {l["field"]: l["evidence"] for l in draft["lines"]},
        "flags": list(draft["flags"]),
        "changes_since_last": (_diff(previous_draft, draft)
                                if previous_draft is not None else []),
        "decision": None,
        "simulation_only": True,
        "authorizes": False,
    }


def record_owner_decision(screen, decision, version_hash):
    """Record the owner's decision on the exact version a
    review screen shows. The decision binds only when
    `version_hash` matches the screen's draft hash; a
    mismatch raises ValueError and records nothing. Returns
    a copy of the screen with "decision" filled:
    {"decision", "version_hash", "simulation_only",
    "authorizes"} — recording a decision authorizes
    nothing by itself."""
    if version_hash != screen.get("version_hash"):
        raise ValueError(
            "decision was offered for version %r but the "
            "screen shows %r; nothing recorded"
            % (version_hash, screen.get("version_hash")))
    out = copy.deepcopy(screen)
    out["decision"] = {"decision": decision,
                       "version_hash": version_hash,
                       "simulation_only": True,
                       "authorizes": False}
    return out
