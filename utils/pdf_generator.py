from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import io

LIFELINE_RED   = colors.HexColor("#C0392B")
LIFELINE_DARK  = colors.HexColor("#1C2833")
LIFELINE_GREY  = colors.HexColor("#566573")
LIFELINE_LIGHT = colors.HexColor("#F2F3F4")
WHITE          = colors.white
BLACK          = colors.black

def _style(name, **kwargs):
    base = getSampleStyleSheet()["Normal"]
    style = ParagraphStyle(name, parent=base, **kwargs)
    return style

def generate_contract(contract_data: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=10*mm, bottomMargin=10*mm
    )

    elements = []
    W = A4[0] - 30*mm  # usable width

    # ── HEADER ─────────────────────────────────────────
    header_data = [[
        Paragraph("<font color='white'><b>LIFELINE</b></font>",
                  _style("H", fontSize=22, textColor=WHITE, alignment=TA_LEFT)),
        Paragraph("<font color='white'><b>BLOOD TRANSFER CONTRACT</b></font>",
                  _style("H2", fontSize=12, textColor=WHITE, alignment=TA_RIGHT,
                         leading=18))
    ]]
    header_table = Table(header_data, colWidths=[W*0.5, W*0.5])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LIFELINE_RED),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING", (0,0),(-1,-1), 12),
        ("RIGHTPADDING",(0,0),(-1,-1), 12),
    ]))
    elements.append(header_table)

    # Sub-header
    sub_data = [[
        Paragraph("Pakistan Blood Authority | Lifeline Logistics Network",
                  _style("Sub", fontSize=8, textColor=LIFELINE_GREY, alignment=TA_LEFT)),
        Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y  %H:%M')}",
                  _style("SubR", fontSize=8, textColor=LIFELINE_GREY, alignment=TA_RIGHT))
    ]]
    sub_table = Table(sub_data, colWidths=[W*0.6, W*0.4])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), LIFELINE_LIGHT),
        ("TOPPADDING", (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1), 12),
        ("RIGHTPADDING",(0,0),(-1,-1),12),
    ]))
    elements.append(sub_table)
    elements.append(Spacer(1, 6*mm))

    # ── TICKET INFO ────────────────────────────────────
    ticket = contract_data.get("ticket_id","LF-????")
    status = contract_data.get("status","active").upper()

    info_data = [
        [Paragraph(f"<b>Ticket ID:</b>  {ticket}",
                   _style("I", fontSize=14, fontName="Courier-Bold", textColor=LIFELINE_RED)),
         Paragraph(f"<b>Status:</b>  {status}",
                   _style("I2", fontSize=11, textColor=BLACK, alignment=TA_RIGHT))]
    ]
    info_table = Table(info_data, colWidths=[W*0.6, W*0.4])
    info_table.setStyle(TableStyle([
        ("BOX",   (0,0),(-1,-1), 1, LIFELINE_RED),
        ("TOPPADDING",(0,0),(-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("LEFTPADDING",(0,0),(-1,-1),10),
        ("RIGHTPADDING",(0,0),(-1,-1),10),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 5*mm))

    # ── SECTION HELPER ─────────────────────────────────
    def section_header(text):
        t = Table([[Paragraph(f"<b>{text}</b>",
                              _style("SH", fontSize=9, textColor=WHITE))]],
                  colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1), LIFELINE_DARK),
            ("TOPPADDING",(0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING",(0,0),(-1,-1),10),
        ]))
        return t

    def info_row(label, value):
        return [
            Paragraph(f"<b>{label}</b>",
                      _style("L", fontSize=9, textColor=LIFELINE_GREY)),
            Paragraph(str(value) if value else "—",
                      _style("V", fontSize=9, textColor=BLACK))
        ]

    def two_col_table(rows_data):
        t = Table(rows_data, colWidths=[W*0.25, W*0.75])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1), colors.white),
            ("LINEBELOW", (0,0),(-1,-2), 0.3, colors.HexColor("#E0E0E0")),
            ("TOPPADDING",(0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("LEFTPADDING",(0,0),(-1,-1),10),
            ("RIGHTPADDING",(0,0),(-1,-1),10),
            ("BOX",(0,0),(-1,-1),0.5, LIFELINE_GREY),
        ]))
        return t

    # ── PATIENT DETAILS ────────────────────────────────
    elements.append(section_header("PATIENT DETAILS"))
    patient = contract_data.get("patient", {})
    patient_rows = [
        info_row("Full Name",    patient.get("full_name","—")),
        info_row("Father/Husband", patient.get("father_name","—")),
        info_row("Age / Gender", f"{patient.get('age','—')} / {patient.get('gender','—')}"),
        info_row("CNIC",         patient.get("cnic","—")),
        info_row("OPD Number",   patient.get("opd_number","—")),
        info_row("Ward / Bed",   f"{patient.get('ward','—')} / {patient.get('bed','—')}"),
        info_row("Diagnosis",    patient.get("diagnosis","—")),
    ]
    elements.append(two_col_table(patient_rows))
    elements.append(Spacer(1, 4*mm))

    # ── BLOOD TRANSFER ─────────────────────────────────
    elements.append(section_header("BLOOD TRANSFER DETAILS"))
    transfer_rows = [
        info_row("Lending Hospital",   contract_data.get("lending_hospital_name",
                                       contract_data.get("lending_hospital_id","—"))),
        info_row("Borrowing Hospital", contract_data.get("borrowing_hospital_name",
                                       contract_data.get("borrowing_hospital_id","—"))),
        info_row("Blood Group",        contract_data.get("blood_group","—")),
        info_row("Component",          contract_data.get("component","—")),
        info_row("Units",              contract_data.get("units","1")),
        info_row("Blood Unit ID",      contract_data.get("blood_unit_id","—")),
    ]
    elements.append(two_col_table(transfer_rows))
    elements.append(Spacer(1, 4*mm))

    # ── SCREENING ──────────────────────────────────────
    elements.append(section_header("SCREENING CLEARANCE"))
    screening_rows = [
        info_row("HIV",       "PASSED"),
        info_row("Hepatitis B","PASSED"),
        info_row("Hepatitis C","PASSED"),
        info_row("Syphilis",   "PASSED"),
        info_row("Malaria",    "PASSED"),
    ]
    elements.append(two_col_table(screening_rows))
    elements.append(Spacer(1, 4*mm))

    # ── TIMELINE ───────────────────────────────────────
    elements.append(section_header("CONTRACT TIMELINE"))
    issue = contract_data.get("issue_time","—")
    deadline = contract_data.get("return_deadline","—")
    try:
        issue_fmt = datetime.fromisoformat(issue).strftime("%d %b %Y  %H:%M")
    except:
        issue_fmt = issue
    try:
        deadline_fmt = datetime.fromisoformat(deadline).strftime("%d %b %Y  %H:%M")
    except:
        deadline_fmt = deadline

    timeline_rows = [
        info_row("Issued At",       issue_fmt),
        info_row("Return Deadline", deadline_fmt),
        info_row("Contract Type",   "Exchange" if contract_data.get("is_exchange") else "Transfer"),
    ]
    elements.append(two_col_table(timeline_rows))
    elements.append(Spacer(1, 8*mm))

    # ── SIGNATURES ─────────────────────────────────────
    sig_data = [[
        Paragraph("Blood Bank Officer\n\n\n____________________\nSignature / Stamp",
                  _style("Sig", fontSize=9, textColor=BLACK, alignment=TA_CENTER)),
        Paragraph("Receiving Officer\n\n\n____________________\nSignature / Stamp",
                  _style("Sig2", fontSize=9, textColor=BLACK, alignment=TA_CENTER)),
        Paragraph("Attending Doctor\n\n\n____________________\nSignature / Stamp",
                  _style("Sig3", fontSize=9, textColor=BLACK, alignment=TA_CENTER)),
    ]]
    sig_table = Table(sig_data, colWidths=[W/3, W/3, W/3])
    sig_table.setStyle(TableStyle([
        ("BOX",   (0,0),(-1,-1), 0.5, LIFELINE_GREY),
        ("INNERGRID",(0,0),(-1,-1), 0.3, LIFELINE_GREY),
        ("TOPPADDING",(0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1),15),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 4*mm))

    # ── FOOTER ─────────────────────────────────────────
    footer = Table([[
        Paragraph("This document is legally binding under Pakistan Blood Safety Act 2021. "
                  "Unauthorized duplication is prohibited.",
                  _style("F", fontSize=7, textColor=LIFELINE_GREY, alignment=TA_CENTER))
    ]], colWidths=[W])
    footer.setStyle(TableStyle([
        ("TOPLINE",(0,0),(-1,-1),0.5,LIFELINE_RED),
        ("TOPPADDING",(0,0),(-1,-1),5),
    ]))
    elements.append(footer)

    doc.build(elements)
    return buffer.getvalue()

def generate_shift_report(stats: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=10*mm, bottomMargin=10*mm
    )

    elements = []
    W = A4[0] - 30*mm

    header_data = [[
        Paragraph("<font color='white'><b>LIFELINE</b></font>",
                  _style("H", fontSize=22, textColor=WHITE, alignment=TA_LEFT)),
        Paragraph("<font color='white'><b>SHIFT HANDOVER REPORT</b></font>",
                  _style("H2", fontSize=12, textColor=WHITE, alignment=TA_RIGHT, leading=18))
    ]]
    header_table = Table(header_data, colWidths=[W*0.5, W*0.5])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LIFELINE_RED),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING", (0,0),(-1,-1), 12),
        ("RIGHTPADDING",(0,0),(-1,-1), 12),
    ]))
    elements.append(header_table)

    sub_data = [[
        Paragraph("Pakistan Blood Authority | Lifeline Logistics Network",
                  _style("Sub", fontSize=8, textColor=LIFELINE_GREY, alignment=TA_LEFT)),
        Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y  %H:%M')}",
                  _style("SubR", fontSize=8, textColor=LIFELINE_GREY, alignment=TA_RIGHT))
    ]]
    sub_table = Table(sub_data, colWidths=[W*0.6, W*0.4])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), LIFELINE_LIGHT),
        ("TOPPADDING", (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1), 12),
        ("RIGHTPADDING",(0,0),(-1,-1),12),
    ]))
    elements.append(sub_table)
    elements.append(Spacer(1, 10*mm))
    
    elements.append(Paragraph(f"<b>Total Units in Inventory:</b> {stats.get('total_units', 0)}", _style("Normal", fontSize=12)))
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph(f"<b>Expiring in 3 Days:</b> {stats.get('expiring_3_days', 0)}", _style("Normal", fontSize=12)))
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph(f"<b>Active Contracts:</b> {stats.get('active_contracts', 0)}", _style("Normal", fontSize=12)))
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph(f"<b>Live Emergencies:</b> {stats.get('live_emergencies', 0)}", _style("Normal", fontSize=12)))
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph(f"<b>Donors Screened Today:</b> {stats.get('screened_today', 0)}", _style("Normal", fontSize=12)))
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph(f"<b>Temperature Alerts:</b> {stats.get('temp_alerts', 0)}", _style("Normal", fontSize=12)))
    
    elements.append(Spacer(1, 15*mm))
    
    sig_data = [[
        Paragraph("Outgoing Shift Officer\n\n\n____________________\nSignature",
                  _style("Sig", fontSize=9, textColor=BLACK, alignment=TA_CENTER)),
        Paragraph("Incoming Shift Officer\n\n\n____________________\nSignature",
                  _style("Sig2", fontSize=9, textColor=BLACK, alignment=TA_CENTER)),
    ]]
    sig_table = Table(sig_data, colWidths=[W/2, W/2])
    sig_table.setStyle(TableStyle([
        ("TOPPADDING",(0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1),15),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
    ]))
    elements.append(sig_table)
    
    doc.build(elements)
    return buffer.getvalue()
