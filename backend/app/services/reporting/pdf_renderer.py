"""
PDF rendering for project reports (reportlab / Platypus).

Pure-Python; no system libraries required. Produces a branded, paginated PDF
and returns it as bytes so the route can stream it as a download.
"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.report_schema import ProjectReport

# Brand palette (matches the frontend).
INK = colors.HexColor("#0F1E2E")
RECALL = colors.HexColor("#E8A23D")
SYNAPSE = colors.HexColor("#3A7CA5")
MERIT = colors.HexColor("#2E7D52")
DEMERIT = colors.HexColor("#B3471F")
MUTED = colors.HexColor("#5B6B7B")
LINE = colors.HexColor("#E3E7EC")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], textColor=INK, fontSize=20, spaceAfter=2
        ),
        "scope": ParagraphStyle(
            "scope", parent=base["Normal"], textColor=SYNAPSE, fontSize=11,
            spaceAfter=2,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base["Normal"], textColor=MUTED, fontSize=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], textColor=INK, fontSize=13,
            spaceBefore=14, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], textColor=INK, fontSize=9.5, leading=14,
            alignment=TA_LEFT,
        ),
        "merit": ParagraphStyle(
            "merit", parent=base["Normal"], textColor=INK, fontSize=9.5, leading=14,
            leftIndent=10,
        ),
        "evidence": ParagraphStyle(
            "evidence", parent=base["Normal"], textColor=MUTED, fontSize=8,
            leftIndent=10, leading=11, spaceAfter=4,
        ),
    }


def render_report(report: ProjectReport) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=report.title,
    )
    s = _styles()
    story: list = []

    # --- header ---
    story.append(Paragraph(report.title, s["title"]))
    story.append(Paragraph(report.scope_label, s["scope"]))
    story.append(
        Paragraph(
            f"Generated {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')} · "
            f"reasoning: {report.provider}",
            s["meta"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", color=LINE, thickness=1))
    story.append(Spacer(1, 8))

    # --- stat strip ---
    st = report.stats
    stat_data = [[
        _stat("MEETINGS", st.meetings),
        _stat("PEOPLE", st.people),
        _stat("TASKS", st.tasks),
        _stat("EDGES", st.graph_edges),
        _stat("DONE", st.done_action_items),
        _stat("OPEN", st.open_action_items),
    ]]
    stat_tbl = Table(stat_data, colWidths=[28 * mm] * 6)
    stat_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F8FA")),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(stat_tbl)

    # --- executive summary ---
    story.append(Paragraph("Executive summary", s["h2"]))
    story.append(Paragraph(_esc(report.executive_summary), s["body"]))

    # --- merits ---
    story.append(_section_heading("Merits — what's going well", MERIT, s))
    for m in report.merits:
        story.append(Paragraph(f"&#9679; {_esc(m.text)}", s["merit"]))
        if m.evidence:
            who = f"{m.source}: " if m.source else ""
            story.append(Paragraph(f"\u201c{_esc(who + m.evidence)}\u201d", s["evidence"]))

    # --- demerits ---
    story.append(_section_heading("Demerits — risks & gaps", DEMERIT, s))
    for d in report.demerits:
        story.append(Paragraph(f"&#9679; {_esc(d.text)}", s["merit"]))
        if d.evidence:
            who = f"{d.source}: " if d.source else ""
            story.append(Paragraph(f"\u201c{_esc(who + d.evidence)}\u201d", s["evidence"]))

    # --- responsibilities ---
    if report.responsibilities:
        story.append(Paragraph("Responsibilities", s["h2"]))
        rows = [["Owner", "Tasks"]]
        rows += [[r.owner, ", ".join(r.tasks)] for r in report.responsibilities]
        story.append(_grid(rows, [40 * mm, 134 * mm]))

    # --- action items ---
    if report.action_items:
        story.append(Paragraph("Action items", s["h2"]))
        rows = [["Owner", "Task", "Due", "Status", "Meeting"]]
        rows += [
            [a.owner or "—", a.task, a.due or "—", a.status, a.meeting_id]
            for a in report.action_items
        ]
        story.append(_grid(rows, [28 * mm, 60 * mm, 26 * mm, 24 * mm, 36 * mm]))

    # --- meetings covered ---
    if report.meetings:
        story.append(Paragraph("Meetings covered", s["h2"]))
        rows = [["ID", "Title", "Date"]]
        rows += [
            [m.meeting_id, m.title, m.date.strftime("%Y-%m-%d")]
            for m in report.meetings
        ]
        story.append(_grid(rows, [28 * mm, 110 * mm, 36 * mm]))

    doc.build(story)
    return buf.getvalue()


# --- helpers ---------------------------------------------------------------
def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _stat(label: str, value) -> Paragraph:
    return Paragraph(
        f'<para align="center">'
        f'<font size="16" color="#0F1E2E"><b>{value}</b></font><br/>'
        f'<font size="6.5" color="#5B6B7B">{label}</font></para>',
        getSampleStyleSheet()["Normal"],
    )


def _section_heading(text: str, color, s) -> Paragraph:
    return Paragraph(
        f'<font color="#{color.hexval()[2:]}">&#9632;</font>&nbsp;{_esc(text)}',
        ParagraphStyle("sh", parent=s["h2"]),
    )


def _grid(rows: list[list[str]], col_widths: list[float]) -> Table:
    body = getSampleStyleSheet()["Normal"]
    cell = ParagraphStyle("cell", parent=body, fontSize=8.5, leading=11, textColor=INK)
    head = ParagraphStyle(
        "head", parent=body, fontSize=8, leading=10, textColor=colors.white
    )
    data = [
        [Paragraph(_esc(str(c)), head if i == 0 else cell) for c in row]
        for i, row in enumerate(rows)
    ]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F8FA")]),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tbl


def _format_markdown_inline(text: str) -> str:
    import re
    escaped = _esc(text)
    
    # Bold: **text** or __text__ -> <b>text</b>
    bold_pattern = re.compile(r'\*\*(.*?)\*\*')
    escaped = bold_pattern.sub(r'<b>\1</b>', escaped)
    bold_pattern2 = re.compile(r'__(.*?)__')
    escaped = bold_pattern2.sub(r'<b>\1</b>', escaped)
    
    # Italics: *text* or _text_ -> <i>text</i>
    italic_pattern = re.compile(r'\*(.*?)\*')
    escaped = italic_pattern.sub(r'<i>\1</i>', escaped)
    italic_pattern2 = re.compile(r'_(.*?)_')
    escaped = italic_pattern2.sub(r'<i>\1</i>', escaped)
    
    return escaped


def render_markdown_to_pdf(title: str, markdown_content: str) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=title,
    )
    s = _styles()
    
    h1_style = ParagraphStyle(
        "md_h1", parent=s["title"], fontSize=18, spaceBefore=12, spaceAfter=6
    )
    h2_style = ParagraphStyle(
        "md_h2", parent=s["h2"], fontSize=13, spaceBefore=10, spaceAfter=6
    )
    h3_style = ParagraphStyle(
        "md_h3", parent=s["h2"], fontSize=11, spaceBefore=8, spaceAfter=4, textColor=SYNAPSE
    )
    body_style = s["body"]
    bullet_style = ParagraphStyle(
        "md_bullet", parent=s["body"], leftIndent=12, firstLineIndent=-8, spaceAfter=3
    )

    story: list = []
    
    # --- header ---
    story.append(Paragraph(title, s["title"]))
    story.append(HRFlowable(width="100%", color=LINE, thickness=1))
    story.append(Spacer(1, 10))

    lines = markdown_content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
            
        if line.startswith("# "):
            story.append(Paragraph(_format_markdown_inline(line[2:]), h1_style))
            i += 1
        elif line.startswith("## "):
            story.append(Paragraph(_format_markdown_inline(line[3:]), h2_style))
            i += 1
        elif line.startswith("### "):
            story.append(Paragraph(_format_markdown_inline(line[4:]), h3_style))
            i += 1
        elif line.startswith("#### "):
            story.append(Paragraph(_format_markdown_inline(line[5:]), h3_style))
            i += 1
        elif line.startswith("- ") or line.startswith("* "):
            story.append(Paragraph(f"&#9679; {_format_markdown_inline(line[2:])}", bullet_style))
            i += 1
        elif line.startswith("1. "):
            story.append(Paragraph(f"1. {_format_markdown_inline(line[3:])}", bullet_style))
            i += 1
        elif line.startswith("---") or line.startswith("___"):
            story.append(Spacer(1, 5))
            story.append(HRFlowable(width="100%", color=LINE, thickness=0.5))
            story.append(Spacer(1, 5))
            i += 1
        else:
            para_lines = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line or next_line.startswith("#") or next_line.startswith("-") or next_line.startswith("*") or next_line.startswith("---") or next_line.startswith("1. "):
                    break
                para_lines.append(next_line)
                i += 1
            para_text = " ".join(para_lines)
            story.append(Paragraph(_format_markdown_inline(para_text), body_style))
            story.append(Spacer(1, 6))

    doc.build(story)
    return buf.getvalue()
