"""PDF + Excel + JSON + iCal exporters for a Timetable."""
from __future__ import annotations

import io
import json
from collections import defaultdict
from datetime import datetime, timedelta

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models.domain import Timetable, TimetableRequest


# ---------------------------------------------------------------------------
# Grid building
# ---------------------------------------------------------------------------
def _section_grid(tt: Timetable, sec_id: str, days: list[str], slots: list[int]):
    grid: dict[tuple[str, int], list[str]] = defaultdict(list)
    for c in tt.classes:
        if c.section_id != sec_id:
            continue
        cell = grid[(c.day, c.slot)]
        label = c.label or c.course_code
        batch = f" ({c.batch_id})" if c.batch_id else ""
        if label not in cell[0] if cell else True:
            cell.append(f"{label}{batch}")
    return grid


def _faculty_grid(tt: Timetable, faculty_id: str, days: list[str], slots: list[int]):
    grid: dict[tuple[str, int], list[str]] = defaultdict(list)
    for c in tt.classes:
        if c.faculty_id != faculty_id:
            continue
        cell = grid[(c.day, c.slot)]
        text = f"{c.section_id}: {c.label or c.course_code}"
        if text not in cell:
            cell.append(text)
    return grid


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def render_pdf(req: TimetableRequest, tt: Timetable) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title="Timetable")
    styles = getSampleStyleSheet()
    elements: list = []

    days = req.time_config.days
    slots = list(range(1, req.time_config.slots_per_day + 1))

    for sec in req.sections:
        elements.append(Paragraph(f"<b>{sec.name}</b> — {sec.classroom}", styles["Title"]))
        elements.append(Spacer(1, 8))
        grid = _section_grid(tt, sec.id, days, slots)
        header = ["Day"] + [f"Slot {t}" for t in slots]
        data = [header]
        for d in days:
            row = [d]
            for t in slots:
                cell = grid.get((d, t))
                if cell:
                    row.append("\n".join(cell))
                else:
                    if d == "SAT":
                        row.append("—")
                    else:
                        row.append("")
            data.append(row)
        tbl = Table(data, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ]
            )
        )
        elements.append(tbl)
        elements.append(PageBreak())

    if not elements:
        elements.append(Paragraph("No data", styles["Normal"]))
    doc.build(elements)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------
def render_xlsx(req: TimetableRequest, tt: Timetable) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    days = req.time_config.days
    slots = list(range(1, req.time_config.slots_per_day + 1))
    header_fill = PatternFill("solid", fgColor="1F2937")
    header_font = Font(bold=True, color="FFFFFF")

    for sec in req.sections:
        ws = wb.create_sheet(title=f"Sec {sec.id}")
        ws.cell(row=1, column=1, value="Day")
        for j, t in enumerate(slots, start=2):
            ws.cell(row=1, column=j, value=f"Slot {t}")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        grid = _section_grid(tt, sec.id, days, slots)
        for i, d in enumerate(days, start=2):
            ws.cell(row=i, column=1, value=d).font = Font(bold=True)
            for j, t in enumerate(slots, start=2):
                cell = grid.get((d, t))
                txt = "\n".join(cell) if cell else ("—" if d == "SAT" else "")
                c = ws.cell(row=i, column=j, value=txt)
                c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        for col in range(1, len(slots) + 2):
            ws.column_dimensions[chr(64 + col)].width = 22 if col > 1 else 8

    # Faculty sheet
    fws = wb.create_sheet(title="Faculty view")
    fws.append(["Faculty", "Day", "Slot", "Section", "Course"])
    for c in tt.classes:
        if c.faculty_id:
            fws.append([c.faculty_id, c.day, c.slot, c.section_id, c.label or c.course_code])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------
def render_json(req: TimetableRequest, tt: Timetable) -> bytes:
    return json.dumps(
        {
            "request": req.model_dump(),
            "timetable": tt.model_dump(),
        },
        default=str,
        indent=2,
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# iCal (per faculty)
# ---------------------------------------------------------------------------
def render_ical(req: TimetableRequest, tt: Timetable, faculty_id: str) -> bytes:
    from icalendar import Calendar, Event

    cal = Calendar()
    cal.add("prodid", "-//Timetable Generator//EN")
    cal.add("version", "2.0")

    # Use next Monday as week start
    today = datetime.now().date()
    monday = today + timedelta(days=(7 - today.weekday()) % 7)
    day_offset = {d: i for i, d in enumerate(["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"])}

    for c in tt.classes:
        if c.faculty_id != faculty_id:
            continue
        timing = (
            req.time_config.slot_timings[c.slot - 1]
            if c.slot - 1 < len(req.time_config.slot_timings)
            else None
        )
        if not timing:
            continue
        d = monday + timedelta(days=day_offset.get(c.day, 0))
        start_h, start_m = [int(x) for x in timing.start.split(":")]
        end_h, end_m = [int(x) for x in timing.end.split(":")]
        ev = Event()
        ev.add("summary", f"{c.label or c.course_code} ({c.section_id})")
        ev.add("dtstart", datetime(d.year, d.month, d.day, start_h, start_m))
        ev.add("dtend", datetime(d.year, d.month, d.day, end_h, end_m))
        ev.add("description", f"Section {c.section_id} | {c.course_code}")
        cal.add_component(ev)

    return bytes(cal.to_ical())
