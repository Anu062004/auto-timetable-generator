"""Domain-aware patch operations for editing a TimetableRequest.

The LLM emits a small list of operation objects and the backend applies them
server-side. This avoids forcing the LLM to echo the entire (>20k token)
TimetableRequest for every edit, which (a) is slow, (b) burns tokens, and
(c) hits per-request token limits on free LLM tiers.

Each operation has an ``op`` discriminator and a handful of fields. Faculty
and section identifiers can be passed as ids OR partial name matches.
"""
from __future__ import annotations

import copy
from typing import Any

from ..models.domain import (
    Assignment,
    Course,
    LockedSlot,
    TimetableRequest,
    UnavailableSlot,
)


DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT"}


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------
def _match_faculty(req: TimetableRequest, needle: str) -> list[int]:
    """Return indices of faculty whose id or name matches the needle."""
    n = needle.lower().strip()
    if not n:
        return []
    out: list[int] = []
    for i, f in enumerate(req.faculty):
        if f.id.lower() == n:
            return [i]
        if n in f.name.lower():
            out.append(i)
    return out


def _match_course(req: TimetableRequest, needle: str) -> int | None:
    n = needle.lower().strip()
    for i, c in enumerate(req.courses):
        if c.code.lower() == n or n in c.name.lower():
            return i
    return None


def _norm_day(v: Any) -> str:
    s = str(v).upper()[:3]
    if s not in DAYS:
        raise ValueError(f"unknown day {v!r}")
    return s


def _norm_slots(v: Any) -> list[int]:
    if isinstance(v, int):
        return [v]
    if isinstance(v, list):
        return [int(x) for x in v]
    raise ValueError(f"slots must be int or list, got {v!r}")


# ---------------------------------------------------------------------------
# Operation handlers
# ---------------------------------------------------------------------------
def op_faculty_unavailable(req: TimetableRequest, *, faculty: str, day: str, slots: Any) -> str:
    idxs = _match_faculty(req, faculty)
    if not idxs:
        return f"No faculty matched {faculty!r}"
    d = _norm_day(day)
    ss = _norm_slots(slots)
    touched = []
    for i in idxs:
        f = req.faculty[i]
        existing = {(u.day, u.slot) for u in f.unavailable_slots}
        for s in ss:
            if (d, s) not in existing:
                f.unavailable_slots.append(UnavailableSlot(day=d, slot=s))
        touched.append(f.name)
    return f"Marked unavailable {d} slot(s) {ss} for: {', '.join(touched)}"


def op_clear_faculty_unavailable(req: TimetableRequest, *, faculty: str) -> str:
    idxs = _match_faculty(req, faculty)
    if not idxs:
        return f"No faculty matched {faculty!r}"
    touched = []
    for i in idxs:
        req.faculty[i].unavailable_slots = []
        touched.append(req.faculty[i].name)
    return f"Cleared unavailability for: {', '.join(touched)}"


def op_set_max_per_day(req: TimetableRequest, *, faculty: str, cap: int) -> str:
    idxs = _match_faculty(req, faculty)
    if not idxs:
        return f"No faculty matched {faculty!r}"
    for i in idxs:
        req.faculty[i].max_per_day = int(cap)
    return f"Set max-per-day={cap} for {len(idxs)} faculty"


def op_lock_course(
    req: TimetableRequest,
    *,
    course: str,
    day: str,
    slots: Any,
) -> str:
    ci = _match_course(req, course)
    if ci is None:
        return f"No course matched {course!r}"
    c = req.courses[ci]
    c.locked_day = _norm_day(day)
    c.locked_slots = _norm_slots(slots)
    return f"Locked {c.code} to {c.locked_day} slot(s) {c.locked_slots}"


def op_unlock_course(req: TimetableRequest, *, course: str) -> str:
    ci = _match_course(req, course)
    if ci is None:
        return f"No course matched {course!r}"
    c = req.courses[ci]
    c.locked_day = None
    c.locked_slots = None
    return f"Unlocked {c.code}"


def op_set_elective_slots(
    req: TimetableRequest,
    *,
    block: str | None = None,
    slots: list[dict] | list[list],
) -> str:
    """Set locked_global_slots for an elective block.

    Accepts slots as [{day, slot}] or [[day, slot], ...]. If only one block
    exists, ``block`` may be omitted.
    """
    if not req.elective_blocks:
        return "No elective blocks defined"
    target_idx = 0
    if block:
        n = block.lower()
        for i, b in enumerate(req.elective_blocks):
            if b.id.lower() == n or n in b.name.lower():
                target_idx = i
                break
        else:
            return f"No elective block matched {block!r}"
    normalised: list[tuple[str, int]] = []
    for entry in slots:
        if isinstance(entry, dict):
            d, s = entry.get("day"), entry.get("slot")
        else:
            d, s = entry[0], entry[1]
        normalised.append((_norm_day(d), int(s)))
    b = req.elective_blocks[target_idx]
    b.locked_global_slots = normalised
    b.weekly_slot_count = len(normalised)
    return f"Set elective {b.name} slots to {normalised}"


def op_add_assignment(
    req: TimetableRequest,
    *,
    faculty: str,
    course: str,
    section: str,
    is_lab: bool = False,
) -> str:
    idxs = _match_faculty(req, faculty)
    if not idxs:
        return f"No faculty matched {faculty!r}"
    ci = _match_course(req, course)
    if ci is None:
        return f"No course matched {course!r}"
    code = req.courses[ci].code
    sec = section.strip().upper()
    f = req.faculty[idxs[0]]
    existing = {(a.course_code, a.section_id, a.is_lab) for a in f.assignments}
    if (code, sec, bool(is_lab)) in existing:
        return f"{f.name} already teaches {code} for section {sec}"
    f.assignments.append(Assignment(course_code=code, section_id=sec, is_lab=bool(is_lab)))
    return f"Assigned {f.name} → {code} ({sec})"


def op_remove_assignment(
    req: TimetableRequest,
    *,
    faculty: str,
    course: str,
    section: str | None = None,
) -> str:
    idxs = _match_faculty(req, faculty)
    if not idxs:
        return f"No faculty matched {faculty!r}"
    ci = _match_course(req, course)
    if ci is None:
        return f"No course matched {course!r}"
    code = req.courses[ci].code
    sec = section.strip().upper() if section else None
    f = req.faculty[idxs[0]]
    before = len(f.assignments)
    f.assignments = [
        a
        for a in f.assignments
        if not (a.course_code == code and (sec is None or a.section_id == sec))
    ]
    return f"Removed {before - len(f.assignments)} assignment(s) from {f.name}"


def op_add_locked_slot(
    req: TimetableRequest,
    *,
    day: str,
    slot: int,
    label: str,
    sections: list[str] | None = None,
) -> str:
    d = _norm_day(day)
    rules = req.time_config.saturday_rules
    rules.locked_slots.append(
        LockedSlot(
            day=d,
            slot=int(slot),
            label=label,
            applies_to_sections=[s.upper() for s in sections] if sections else None,
        )
    )
    return f"Locked {label} at {d} slot {slot}"


def op_pin_class(
    req: TimetableRequest,
    *,
    section: str,
    course: str,
    day: str,
    slot: int,
    faculty: str | None = None,
) -> str:
    """Pin a specific class to a (section, day, slot) cell.

    Adds a LockedSlot reservation for the section that the solver treats as
    immovable. The matching course's normal workload is decremented by one so
    we don't end up with too many instances scheduled.
    """
    ci = _match_course(req, course)
    if ci is None:
        return f"No course matched {course!r}"
    code = req.courses[ci].code
    d = _norm_day(day)
    s = int(slot)
    sec = section.strip().upper()
    if sec not in {x.id for x in req.sections}:
        return f"Unknown section {sec}"
    fac_id: str | None = None
    if faculty:
        idxs = _match_faculty(req, faculty)
        if idxs:
            fac_id = req.faculty[idxs[0]].id
    req.time_config.saturday_rules.locked_slots.append(
        LockedSlot(
            day=d,
            slot=s,
            label=code,
            faculty_id=fac_id,
            applies_to_sections=[sec],
        )
    )
    return f"Pinned {code} → section {sec} at {d} slot {s}"


def op_unpin_class(
    req: TimetableRequest,
    *,
    section: str | None = None,
    course: str | None = None,
    day: str | None = None,
    slot: int | None = None,
) -> str:
    """Remove pin(s) matching the given filters. All-None unpins nothing."""
    if not any([section, course, day, slot]):
        return "Refusing to unpin everything — specify at least one filter."
    sec = section.strip().upper() if section else None
    code: str | None = None
    if course:
        ci = _match_course(req, course)
        if ci is not None:
            code = req.courses[ci].code
    d = _norm_day(day) if day else None
    s = int(slot) if slot is not None else None
    rules = req.time_config.saturday_rules
    kept: list[LockedSlot] = []
    removed = 0
    for ls in rules.locked_slots:
        match = True
        if sec and (not ls.applies_to_sections or sec not in ls.applies_to_sections):
            match = False
        if code and ls.label != code:
            match = False
        if d and ls.day != d:
            match = False
        if s is not None and ls.slot != s:
            match = False
        if match:
            removed += 1
        else:
            kept.append(ls)
    rules.locked_slots = kept
    return f"Unpinned {removed} reservation(s)"


def op_set_time_limit(req: TimetableRequest, *, seconds: int) -> str:
    req.time_limit_sec = int(seconds)
    return f"Solver time limit set to {seconds}s"


# ---------------------------------------------------------------------------
# Applicator
# ---------------------------------------------------------------------------
OPERATIONS = {
    "faculty_unavailable": op_faculty_unavailable,
    "clear_faculty_unavailable": op_clear_faculty_unavailable,
    "set_max_per_day": op_set_max_per_day,
    "lock_course": op_lock_course,
    "unlock_course": op_unlock_course,
    "set_elective_slots": op_set_elective_slots,
    "add_assignment": op_add_assignment,
    "remove_assignment": op_remove_assignment,
    "add_locked_slot": op_add_locked_slot,
    "pin_class": op_pin_class,
    "unpin_class": op_unpin_class,
    "set_time_limit": op_set_time_limit,
}


def apply_patch(
    req: TimetableRequest, ops: list[dict]
) -> tuple[TimetableRequest, list[str], list[str]]:
    """Apply a list of operation dicts to a copy of req.

    Returns (new_req, applied_messages, errors).
    """
    new_req = copy.deepcopy(req)
    applied: list[str] = []
    errors: list[str] = []
    for raw in ops:
        if not isinstance(raw, dict):
            errors.append(f"op is not a dict: {raw!r}")
            continue
        name = raw.get("op")
        handler = OPERATIONS.get(name) if isinstance(name, str) else None
        if not handler:
            errors.append(f"unknown op {name!r}")
            continue
        kwargs = {k: v for k, v in raw.items() if k != "op"}
        try:
            msg = handler(new_req, **kwargs)
            applied.append(msg)
        except TypeError as e:
            errors.append(f"{name}: bad args ({e})")
        except Exception as e:  # pragma: no cover
            errors.append(f"{name}: {e}")
    return new_req, applied, errors


# Used in the LLM system prompt — keep this short.
OPS_HELP = """
Available patch operations (each item in `ops` is one of these):

  {"op":"faculty_unavailable","faculty":"<name or id>","day":"MON|TUE|...","slots":[1,2]}
  {"op":"clear_faculty_unavailable","faculty":"<name or id>"}
  {"op":"set_max_per_day","faculty":"<name or id>","cap":4}
  {"op":"lock_course","course":"<code or name>","day":"FRI","slots":[5,6,7]}
  {"op":"unlock_course","course":"<code or name>"}
  {"op":"set_elective_slots","block":"<block id or name optional>","slots":[{"day":"MON","slot":2},...]}
  {"op":"add_assignment","faculty":"...","course":"...","section":"A","is_lab":false}
  {"op":"remove_assignment","faculty":"...","course":"...","section":"A"}
  {"op":"add_locked_slot","day":"SAT","slot":5,"label":"Sports","sections":["A","B"]}
  {"op":"pin_class","section":"A","course":"BBOK407","day":"MON","slot":1}
  {"op":"unpin_class","section":"A","course":"BBOK407"}
  {"op":"set_time_limit","seconds":60}

`faculty`, `course`, `block` are fuzzy: partial-name matching is allowed.
""".strip()
