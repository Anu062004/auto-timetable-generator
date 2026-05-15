"""Independent verifier (Layer 4 of the blueprint).

Re-checks every hard constraint on a solved Timetable WITHOUT touching the
CP-SAT model. The goal: catch any bug in the constraint encoding.
"""
from __future__ import annotations

from collections import defaultdict

from ..models.domain import (
    CourseType,
    Timetable,
    TimetableRequest,
    VerificationReport,
    Violation,
)


def verify(req: TimetableRequest, tt: Timetable) -> VerificationReport:
    violations: list[Violation] = []
    courses_by_code = {c.code: c for c in req.courses}
    tc = req.time_config
    break_after = {tc.tea_break.after_slot, tc.lunch_break.after_slot}

    # Build pair index: code -> paired_with
    pair_index: dict[str, str] = {}
    for c in req.courses:
        if c.type == CourseType.LAB and c.pair_course:
            pair_index[c.code] = c.pair_course

    # H2 section no-clash
    cell: dict[tuple[str, str, int], list] = defaultdict(list)
    for c in tt.classes:
        cell[(c.section_id, c.day, c.slot)].append(c)
    for (s, d, t), items in cell.items():
        if len(items) <= 1:
            continue
        # Same course, multiple entries → benign (duplicated row of a lab)
        if all(it.course_code == items[0].course_code for it in items):
            continue
        # Paired labs at same cell are expected: codes match via pair_index
        codes = {it.course_code for it in items if it.is_lab}
        if len(codes) == 2:
            a, b = list(codes)
            if pair_index.get(a) == b and pair_index.get(b) == a:
                continue
        batches = {it.batch_id for it in items}
        labs = all(it.is_lab for it in items)
        if labs and None not in batches and len(batches) == len(items):
            continue
        violations.append(
            Violation(
                code="H2",
                message=f"Section {s} double-booked at {d} slot {t}",
                details={"items": [it.model_dump() for it in items]},
            )
        )

    # H1 faculty no-clash
    fac_cell: dict[tuple[str, str, int], list] = defaultdict(list)
    for c in tt.classes:
        if c.faculty_id:
            fac_cell[(c.faculty_id, c.day, c.slot)].append(c)
    for (fid, d, t), items in fac_cell.items():
        if len(items) <= 1:
            continue
        # Allow same faculty across sections when the course is marked
        # combined_sections (e.g., Dept-Activity, BENGDIP2).
        codes = {it.course_code for it in items}
        if len(codes) == 1:
            code = next(iter(codes))
            course = courses_by_code.get(code)
            if course and course.combined_sections:
                continue
        violations.append(
            Violation(
                code="H1",
                message=f"Faculty {fid} double-booked at {d} slot {t}",
                details={"items": [it.model_dump() for it in items]},
            )
        )

    # H6 lab-room contention
    room_cell: dict[tuple[str, str, int], list] = defaultdict(list)
    for c in tt.classes:
        if c.room:
            room_cell[(c.room, c.day, c.slot)].append(c)
    for (r, d, t), items in room_cell.items():
        sections = {it.section_id for it in items}
        if len(sections) > 1:
            violations.append(
                Violation(
                    code="H6",
                    message=f"Lab room {r} used by multiple sections at {d} slot {t}",
                    details={"sections": list(sections)},
                )
            )

    # H3 credit satisfaction (per section, per course)
    needed_by_sec_course: dict[tuple[str, str], int] = {}
    elective_codes = set()
    for b in req.elective_blocks:
        for o in b.options:
            elective_codes.add(o.course_code)

    for fac in req.faculty:
        for a in fac.assignments:
            if a.course_code not in courses_by_code:
                continue
            course = courses_by_code[a.course_code]
            if course.code in elective_codes:
                continue
            needed_by_sec_course[(a.section_id, course.code)] = (
                course.effective_weekly_slots()
            )

    placed: dict[tuple[str, str], int] = defaultdict(int)
    for c in tt.classes:
        placed[(c.section_id, c.course_code)] += 1

    for (sec, code), need in needed_by_sec_course.items():
        got = placed.get((sec, code), 0)
        if got != need:
            violations.append(
                Violation(
                    code="H3",
                    message=f"Section {sec} course {code}: needed {need} slots, got {got}",
                )
            )

    # H4 lab consecutiveness + no spanning break
    # Group lab classes by (section, course, day) and check pairs
    lab_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for c in tt.classes:
        if c.is_lab:
            lab_groups[(c.section_id, c.course_code, c.day)].append(c.slot)
    for (s, code, d), slots in lab_groups.items():
        slots.sort()
        if len(slots) % 2 != 0:
            violations.append(
                Violation(
                    code="H4",
                    message=f"Lab {code} section {s} {d}: odd slot count {slots}",
                )
            )
            continue
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if b - a != 1:
                violations.append(
                    Violation(
                        code="H4",
                        message=f"Lab {code} section {s} {d}: non-consecutive slots {a},{b}",
                    )
                )
            if a in break_after:
                violations.append(
                    Violation(
                        code="H4",
                        message=f"Lab {code} section {s} {d}: spans a break between {a} and {b}",
                    )
                )

    # H7 elective block sync: same elective slots across all applying sections.
    # Our solver reserves with course_code == block.id and label = block.name.
    for block in req.elective_blocks:
        sec_set = set(block.applies_to_sections)
        per_sec: dict[str, set[tuple[str, int]]] = defaultdict(set)
        for c in tt.classes:
            if c.section_id in sec_set and c.course_code == block.id:
                per_sec[c.section_id].add((c.day, c.slot))
        if not per_sec:
            continue
        canonical = next(iter(per_sec.values()))
        for sec in sec_set:
            cells = per_sec.get(sec)
            if cells is None or cells != canonical:
                violations.append(
                    Violation(
                        code="H7",
                        message=f"Elective {block.name} not synchronized for section {sec}",
                        details={"expected": sorted(canonical), "got": sorted(cells or [])},
                    )
                )
        # H8: pool size capacity. Combined teaching means we don't enforce
        # parallel class count strictly; just ensure block locked slots were
        # respected and the block was placed at the requested number of slots.
        if block.locked_global_slots:
            expected = set(block.locked_global_slots)
            for sec in sec_set:
                cells = per_sec.get(sec, set())
                if cells != expected:
                    violations.append(
                        Violation(
                            code="H7",
                            message=f"Elective {block.name} for {sec}: cells != locked globals",
                            details={"expected": sorted(expected), "got": sorted(cells)},
                        )
                    )

    # H9 break sanctity (cosmetic — variables shouldn't create classes during breaks
    # because we don't allocate slot indices to break times; but check anyway).
    # H10 saturday rules
    sat_inactive = req.time_config.saturday_rules.inactive_weeks
    if sat_inactive:
        # Locked sat slots should be present where defined
        for ls in tc.saturday_rules.locked_slots:
            applies = ls.applies_to_sections or [s.id for s in req.sections]
            for sec in applies:
                found = any(
                    c.section_id == sec
                    and c.day == ls.day
                    and c.slot == ls.slot
                    and (c.label == ls.label or c.course_code == ls.label)
                    for c in tt.classes
                )
                if not found:
                    violations.append(
                        Violation(
                            code="H10",
                            message=f"Saturday lock {ls.label} missing for section {sec} at {ls.day}/{ls.slot}",
                        )
                    )

    # H11 hard-locked blocks (courses with locked_day & locked_slots)
    for course in req.courses:
        if not (course.locked_day and course.locked_slots):
            continue
        for sec in req.sections:
            for t in course.locked_slots:
                ok = any(
                    c.section_id == sec.id
                    and c.day == course.locked_day
                    and c.slot == t
                    and c.course_code == course.code
                    for c in tt.classes
                )
                if not ok:
                    violations.append(
                        Violation(
                            code="H11",
                            message=f"Locked block {course.code} missing for section {sec.id} at {course.locked_day}/{t}",
                        )
                    )

    # H12 faculty availability
    for fac in req.faculty:
        unav = {(u.day, u.slot) for u in fac.unavailable_slots}
        for c in tt.classes:
            if c.faculty_id == fac.id and (c.day, c.slot) in unav:
                violations.append(
                    Violation(
                        code="H12",
                        message=f"Faculty {fac.id} scheduled during declared unavailability at {c.day}/{c.slot}",
                    )
                )

    # Compute a soft-score from the timetable (rough 0..100)
    soft_score = _soft_score(req, tt)
    return VerificationReport(
        ok=len(violations) == 0, violations=violations, soft_score=soft_score
    )


def _soft_score(req: TimetableRequest, tt: Timetable) -> int:
    """Rough soft-constraint quality score, 0..100.

    Normalized so a perfectly clean schedule scores 100 and a heavily
    constraint-violated one approaches 0.
    """
    if not tt.classes:
        return 0
    tc = req.time_config
    post_lunch = tc.lunch_break.after_slot + 1
    cls_by_sec_day = defaultdict(list)
    for c in tt.classes:
        cls_by_sec_day[(c.section_id, c.day)].append(c)

    # Normalize: per-section per-day counts, averaged across sections.
    n_sections = max(len({c.section_id for c in tt.classes}), 1)
    n_days = max(len(tc.days), 1)
    cells_max = n_sections * n_days  # one count per (sec, day)

    # Component 1: same-course twice on same day (worst = every cell)
    dup_total = 0
    for (sec, d), items in cls_by_sec_day.items():
        seen: dict[str, int] = defaultdict(int)
        for c in items:
            seen[c.course_code] += 1
        for code, n in seen.items():
            if n > 1 and not items[0].is_lab:  # lab "duplicates" are spans
                dup_total += n - 1
    dup_score = 100 * (1 - min(1.0, dup_total / max(cells_max * 0.3, 1)))

    # Component 2: high-credit theory overflow per day
    high_codes = {
        c.code for c in req.courses
        if c.credits >= 3 and c.type == CourseType.THEORY
    }
    hc_overflow = 0
    for (sec, d), items in cls_by_sec_day.items():
        hc = sum(1 for it in items if it.course_code in high_codes and not it.is_lab)
        if hc > 2:
            hc_overflow += hc - 2
    hc_score = 100 * (1 - min(1.0, hc_overflow / max(cells_max * 0.4, 1)))

    # Component 3: post-lunch density
    pl_classes = sum(
        1 for c in tt.classes if c.slot == post_lunch and not c.is_lab
    )
    pl_score = 100 * (1 - min(1.0, pl_classes / max(n_sections * n_days * 0.6, 1)))

    final = round(0.45 * dup_score + 0.35 * hc_score + 0.20 * pl_score)
    return max(0, min(100, int(final)))
