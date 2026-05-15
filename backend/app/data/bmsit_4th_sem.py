"""BMSIT AIML 4th Sem Even (2025-26) reference data.

Mirrors the actual college PDF: 6 sections, DMS/OT/AGT elective at
MON-II, TUE-III, THU-III, FRI-III, labs with batch swap, Saturday is
only IIC + BENGDIP2 (V-VII empty), and slot 1 is always occupied.
"""
from __future__ import annotations

from ..models.domain import (
    Assignment,
    Batch,
    BreakConfig,
    Course,
    CourseType,
    ElectiveBlock,
    ElectiveOption,
    Faculty,
    LockedSlot,
    SaturdayRules,
    Section,
    TimeConfig,
    Timing,
    TimetableRequest,
)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def _sections() -> list[Section]:
    rooms = {
        "A": "BSN CR 503",
        "B": "BSN CR 504",
        "C": "BSN CR 508",
        "D": "TR-502",
        "E": "BSN CR 404",
        "F": "BSN CR 403",
    }
    out: list[Section] = []
    for sid in ["A", "B", "C", "D", "E", "F"]:
        out.append(
            Section(
                id=sid,
                name=f"4th Sem {sid}",
                semester=4,
                classroom=rooms[sid],
                batches=[
                    Batch(id=f"{sid}1", section_id=sid),
                    Batch(id=f"{sid}2", section_id=sid),
                ],
            )
        )
    return out


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------
def _courses() -> list[Course]:
    return [
        # ----- Core theory -----
        Course(code="BCS401", name="Analysis & Design of Algorithms", credits=3, weekly_slots=3, type=CourseType.THEORY),
        Course(code="BAI402", name="Artificial Intelligence", credits=3, weekly_slots=3, type=CourseType.THEORY),
        Course(code="BCS403", name="Database Management Systems", credits=3, weekly_slots=3, type=CourseType.THEORY),
        Course(code="BBOK407", name="Biology for Engineers", credits=2, weekly_slots=2, type=CourseType.THEORY),
        Course(code="BUHK408", name="Universal Human Values", credits=1, weekly_slots=1, type=CourseType.THEORY),

        # ----- Labs -----
        # lab_room intentionally left unset: the college runs multiple
        # physical AI / ADA / DBMS lab rooms in parallel for different
        # sections (manual assignment). The solver only ensures *time*
        # consistency; room booking is downstream.
        Course(
            code="BAI402_LAB",
            name="AI Lab",
            credits=1,
            weekly_slots=4,  # 2 sessions × 2 slots
            type=CourseType.LAB,
            pair_course="BCSL404",
            consecutive_required=True,
        ),
        Course(
            code="BCSL404",
            name="ADA Lab",
            credits=1,
            weekly_slots=4,
            type=CourseType.LAB,
            pair_course="BAI402_LAB",
            consecutive_required=True,
        ),
        Course(
            code="BCS403_LAB",
            name="DBMS Lab",
            credits=1,
            weekly_slots=2,  # 1 session × 2 slots
            type=CourseType.LAB,
            consecutive_required=True,
        ),
        Course(
            code="BAIL456B",
            name="MongoDB Lab",
            credits=1,
            weekly_slots=2,
            type=CourseType.LAB,
            pair_course="BAIL456C",
            consecutive_required=True,
        ),
        Course(
            code="BAIL456C",
            name="MERN Lab",
            credits=1,
            weekly_slots=2,
            type=CourseType.LAB,
            pair_course="BAIL456B",
            consecutive_required=True,
        ),

        # ----- Electives (placeholder; actual scheduling via ElectiveBlock) -----
        Course(code="BCS405A", name="Discrete Mathematical Structures (DMS)", credits=3, type=CourseType.THEORY),
        Course(code="BCS405C", name="Optimization Techniques (OT)", credits=3, type=CourseType.THEORY),
        Course(code="BAI405D", name="Algorithmic Game Theory (AGT)", credits=3, type=CourseType.THEORY),

        # ----- Locked activities (Friday afternoon Dept-Activity) -----
        Course(
            code="DEPT_ACT",
            name="Dept Activity",
            credits=0,
            weekly_slots=3,
            type=CourseType.ACTIVITY,
            locked_day="FRI",
            locked_slots=[5, 6, 7],
            combined_sections=True,
        ),

        # ----- Flexible activities (placed by the solver) -----
        Course(
            code="CRC",
            name="CRC",
            credits=0,
            weekly_slots=2,
            type=CourseType.ACTIVITY,
            combined_sections=True,
        ),
        Course(
            code="PROCTORING",
            name="Proctoring",
            credits=0,
            weekly_slots=1,
            type=CourseType.ACTIVITY,
            combined_sections=True,
        ),
        Course(
            code="TUTORIAL",
            name="Tutorial Class",
            credits=0,
            weekly_slots=1,
            type=CourseType.ACTIVITY,
            combined_sections=True,
        ),
        Course(
            code="REMEDIAL",
            name="Remedial Class",
            credits=0,
            weekly_slots=1,
            type=CourseType.ACTIVITY,
            combined_sections=True,
        ),
        Course(
            code="NCMC",
            name="NCMC - Cultural",
            credits=0,
            weekly_slots=2,
            type=CourseType.ACTIVITY,
            combined_sections=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Faculty
# ---------------------------------------------------------------------------
def _faculty() -> list[Faculty]:
    fac: list[Faculty] = []
    idx = 1

    def add(name: str, assignments: list[Assignment]) -> Faculty:
        nonlocal idx
        f = Faculty(id=f"FAC_{idx:03d}", name=name, assignments=assignments)
        fac.append(f)
        idx += 1
        return f

    # Theory faculty — one per (course, section). Faithful to the PDF roster.
    # BCS401 (ADA)
    add("Dr Sampath K", [Assignment(course_code="BCS401", section_id="A")])
    add("Dr Rajesh I S (B)", [Assignment(course_code="BCS401", section_id="B")])
    add("Prof Soumya V L", [Assignment(course_code="BCS401", section_id="C")])
    add("Prof Shobith T", [Assignment(course_code="BCS401", section_id="D")])
    add("Prof Balaraju G", [Assignment(course_code="BCS401", section_id="E")])
    add("Dr Manoj H M", [Assignment(course_code="BCS401", section_id="F")])

    # BAI402 (AI)
    add("Prof Kavitha D", [Assignment(course_code="BAI402", section_id="A")])
    add("Prof Salma Itagi", [Assignment(course_code="BAI402", section_id="B")])
    add("Dr Srivani P", [Assignment(course_code="BAI402", section_id="C")])
    add("Prof Shilpa Patil", [Assignment(course_code="BAI402", section_id="D")])
    add("Dr Vani Krishnaswamy", [Assignment(course_code="BAI402", section_id="E")])
    add("Prof Bhavika Rajora", [Assignment(course_code="BAI402", section_id="F")])

    # BCS403 (DBMS)
    add("Dr Archana Bhat", [Assignment(course_code="BCS403", section_id="A")])
    add("Prof Amitha S K", [Assignment(course_code="BCS403", section_id="B")])
    add("Prof Indumati", [Assignment(course_code="BCS403", section_id="C")])
    add("Dr Chidananda K", [Assignment(course_code="BCS403", section_id="D")])
    add("Prof Ashwini S", [Assignment(course_code="BCS403", section_id="E")])
    add("Prof Megha S", [Assignment(course_code="BCS403", section_id="F")])

    # BBOK407 — single faculty for all 6 sections (combined teaching)
    add(
        "Prof Nagi Teja Reddy",
        [Assignment(course_code="BBOK407", section_id=s) for s in "ABCDEF"],
    )
    # UHV — per section in PDF
    add("Dr Rajesh I S (UHV)", [Assignment(course_code="BUHK408", section_id="A")])
    add("Dr Chidananda K (UHV)", [Assignment(course_code="BUHK408", section_id="B")])
    add("Dr Hemamalini B H", [Assignment(course_code="BUHK408", section_id="C")])
    add("Dr Kantharaju V", [Assignment(course_code="BUHK408", section_id="D")])
    add("Dr Niranjanamurthy M", [Assignment(course_code="BUHK408", section_id="E")])
    add("Dr Vani Krishnaswamy (UHV)", [Assignment(course_code="BUHK408", section_id="F")])

    # Lab faculty — for simplicity reuse the section's theory teacher for the
    # corresponding lab. Production data should list explicit lab assistants.
    # AI Lab (paired with ADA)
    for sec_idx, sec in enumerate("ABCDEF"):
        ai_theory_id = f"FAC_{7 + sec_idx:03d}"
        ada_theory_id = f"FAC_{1 + sec_idx:03d}"
        dbms_theory_id = f"FAC_{13 + sec_idx:03d}"
        for f in fac:
            if f.id == ai_theory_id:
                f.assignments.append(Assignment(course_code="BAI402_LAB", section_id=sec, is_lab=True))
            if f.id == ada_theory_id:
                f.assignments.append(Assignment(course_code="BCSL404", section_id=sec, is_lab=True))
            if f.id == dbms_theory_id:
                f.assignments.append(Assignment(course_code="BCS403_LAB", section_id=sec, is_lab=True))

    # MongoDB / MERN lab — dedicated faculty per section
    for sec in "ABCDEF":
        add(
            f"Lab MongoDB ({sec})",
            [Assignment(course_code="BAIL456B", section_id=sec, is_lab=True)],
        )
        add(
            f"Lab MERN ({sec})",
            [Assignment(course_code="BAIL456C", section_id=sec, is_lab=True)],
        )

    # Dept Activity coordinator — combined teaching across all sections
    add(
        "Dept Activity Coord",
        [Assignment(course_code="DEPT_ACT", section_id=s) for s in "ABCDEF"],
    )

    # Flexible activities — one coordinator per activity, combined across sections.
    for code, name in [
        ("CRC", "CRC Coord"),
        ("PROCTORING", "Proctoring Coord"),
        ("TUTORIAL", "Tutorial Coord"),
        ("REMEDIAL", "Remedial Coord"),
    ]:
        add(name, [Assignment(course_code=code, section_id=s) for s in "ABCDEF"])

    # NCMC - Dr Soumya (per PDF)
    add(
        "Dr Soumya (NCMC)",
        [Assignment(course_code="NCMC", section_id=s) for s in "ABCDEF"],
    )

    # Elective pools — DMS, OT, AGT
    dms_pool: list[str] = []
    for name in ["Dr Sreelakshmi T K", "Dr Sumati Tareja", "Dr Nikki Kedia", "Dr Anitha Kiran"]:
        f = add(name, [])
        dms_pool.append(f.id)
    ot_pool: list[str] = []
    for name in ["Prof Sanjay M B", "Prof Pragathi M"]:
        f = add(name, [])
        ot_pool.append(f.id)
    agt_pool: list[str] = []
    for name in ["Prof Syed Owins Umair"]:
        f = add(name, [])
        agt_pool.append(f.id)

    # Saturday faculty (English / IIC)
    add("Prof Chaitanya K (BENGDIP2)", [])
    add("IIC Coord", [])
    return fac


# ---------------------------------------------------------------------------
# Elective block (DMS/OT/AGT)
# ---------------------------------------------------------------------------
def _elective_blocks(faculty: list[Faculty]) -> list[ElectiveBlock]:
    def pool_by(substr: str) -> list[str]:
        return [f.id for f in faculty if substr.lower() in f.name.lower()]

    dms_pool = [
        f.id for f in faculty
        if any(n in f.name for n in ["Sreelakshmi", "Sumati", "Nikki", "Anitha"])
    ]
    ot_pool = [f.id for f in faculty if "Sanjay" in f.name or "Pragathi" in f.name]
    agt_pool = [f.id for f in faculty if "Syed Owins" in f.name]

    return [
        ElectiveBlock(
            id="ELEC_BLOCK_DMS_OT_AGT",
            name="DMS/OT/AGT",
            weekly_slot_count=4,
            applies_to_sections=["A", "B", "C", "D", "E", "F"],
            applies_to_semesters=[4],
            # Lock to the exact slots used by the college PDF.
            locked_global_slots=[("MON", 2), ("TUE", 3), ("THU", 3), ("FRI", 3)],
            options=[
                ElectiveOption(
                    course_code="BCS405A",
                    course_name="Discrete Mathematical Structures",
                    faculty_pool=dms_pool,
                ),
                ElectiveOption(
                    course_code="BCS405C",
                    course_name="Optimization Techniques",
                    faculty_pool=ot_pool,
                ),
                ElectiveOption(
                    course_code="BAI405D",
                    course_name="Algorithmic Game Theory",
                    faculty_pool=agt_pool,
                ),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Time config — exact PDF slot timings + Saturday locks
# ---------------------------------------------------------------------------
def _time_config() -> TimeConfig:
    sat_locks: list[LockedSlot] = []
    for sec in "ABCDEF":
        # IIC-Activity occupies SAT slots 1 & 2
        sat_locks.append(LockedSlot(day="SAT", slot=1, label="IIC-Activity", applies_to_sections=[sec]))
        sat_locks.append(LockedSlot(day="SAT", slot=2, label="IIC-Activity", applies_to_sections=[sec]))
        # BENGDIP2 (English) occupies SAT slots 3 & 4
        sat_locks.append(LockedSlot(day="SAT", slot=3, label="BENGDIP2", applies_to_sections=[sec]))
        sat_locks.append(LockedSlot(day="SAT", slot=4, label="BENGDIP2", applies_to_sections=[sec]))

    return TimeConfig(
        days=["MON", "TUE", "WED", "THU", "FRI", "SAT"],
        slots_per_day=7,
        slot_timings=[
            Timing(start="08:30", end="09:25"),
            Timing(start="09:25", end="10:20"),
            Timing(start="10:40", end="11:35"),
            Timing(start="11:35", end="12:30"),
            Timing(start="13:25", end="14:20"),
            Timing(start="14:20", end="15:15"),
            Timing(start="15:15", end="16:10"),
        ],
        tea_break=BreakConfig(after_slot=2, duration_min=20),
        lunch_break=BreakConfig(after_slot=4, duration_min=55),
        saturday_rules=SaturdayRules(inactive_weeks=[1, 3], locked_slots=sat_locks),
    )


# ---------------------------------------------------------------------------
# Build request
# ---------------------------------------------------------------------------
def build_request(time_limit_sec: int = 20) -> TimetableRequest:
    fac = _faculty()
    return TimetableRequest(
        time_config=_time_config(),
        sections=_sections(),
        courses=_courses(),
        faculty=fac,
        elective_blocks=_elective_blocks(fac),
        time_limit_sec=time_limit_sec,
        seek_optimal=False,
    )
