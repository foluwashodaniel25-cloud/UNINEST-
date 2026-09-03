"""
Generates a branded PDF receipt for any succeeded Payment.

Usage:
    from .receipts import build_receipt_pdf
    pdf_bytes = build_receipt_pdf(payment)
"""

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_RIGHT

TEAL = HexColor("#0d9488")
DARK = HexColor("#1f2937")
GREY = HexColor("#6b7280")
LIGHT_BG = HexColor("#f0fdfa")


def build_receipt_pdf(payment) -> bytes:
    """
    payment: a Uninest.models.Payment instance with status="succeeded".
    Returns raw PDF bytes -- caller decides whether to stream, save, or email it.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    brand_style = ParagraphStyle(
        "Brand", parent=styles["Title"], fontSize=20, textColor=TEAL, spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "Sub", parent=styles["Normal"], fontSize=9, textColor=GREY,
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"], fontSize=9, textColor=GREY,
    )
    value_style = ParagraphStyle(
        "Value", parent=styles["Normal"], fontSize=11, textColor=DARK,
    )
    amount_style = ParagraphStyle(
        "Amount", parent=styles["Title"], fontSize=26, textColor=DARK, alignment=TA_RIGHT,
    )
    status_style = ParagraphStyle(
        "Status", parent=styles["Normal"], fontSize=10, textColor=TEAL, alignment=TA_RIGHT,
    )

    story = []

    # ── Header ──
    story.append(Paragraph("UNINEST", brand_style))
    story.append(Paragraph("Verified Student Housing", sub_style))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", color=TEAL, thickness=1.2))
    story.append(Spacer(1, 6 * mm))

    # ── Title row: "Payment Receipt" + amount ──
    title_row = Table(
        [[
            Paragraph("Payment Receipt", ParagraphStyle(
                "ReceiptTitle", parent=styles["Heading1"], fontSize=16, textColor=DARK
            )),
            Paragraph(f"₦{payment.amount:,.2f}", amount_style),
        ]],
        colWidths=[95 * mm, 75 * mm],
    )
    title_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(title_row)
    story.append(Paragraph("PAID", status_style))
    story.append(Spacer(1, 8 * mm))

    # ── Details table ──
    reference = payment.paystack_reference or "—"
    payment_type_label = dict(payment.PAYMENT_TYPES).get(payment.payment_type, payment.payment_type)
    customer_name = payment.user.get_full_name() or payment.user.username

    rows = [
        [_label("Receipt No."), _value(f"UN-{payment.pk:06d}")],
        [_label("Date"), _value(payment.created_at.strftime("%d %B %Y, %I:%M %p"))],
        [_label("Paid By"), _value(customer_name)],
        [_label("Email"), _value(payment.user.email or "—")],
        [_label("Payment For"), _value(payment_type_label)],
    ]

    if payment.payment_type == "rent" and payment.listing_id:
        rows.append([_label("Listing"), _value(payment.listing.general_location)])
        if payment.listing.school_name:
            rows.append([_label("School"), _value(payment.listing.school_name)])

    rows.append([_label("Paystack Reference"), _value(reference)])

    details_table = Table(rows, colWidths=[45 * mm, 125 * mm])
    details_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, HexColor("#e5e7eb")),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 10 * mm))

    # ── Footer note ──
    note_box = Table(
        [[Paragraph(
            "This receipt confirms a verified payment made through UNINEST via Paystack. "
            "Keep it for your records. Questions about this payment can be sent to "
            "support via WhatsApp from the app.",
            ParagraphStyle("Note", parent=styles["Normal"], fontSize=8.5, textColor=GREY, leading=13)
        )]],
        colWidths=[170 * mm],
    )
    note_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#99f6e4")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(note_box)
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", color=HexColor("#e5e7eb"), thickness=0.6))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "UNINEST · Generated automatically · This is a system-generated receipt and does not require a signature.",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7.5, textColor=GREY)
    ))

    doc.build(story)
    return buffer.getvalue()


def _label(text):
    return Paragraph(text, ParagraphStyle("L", fontSize=9, textColor=GREY))


def _value(text):
    return Paragraph(str(text), ParagraphStyle("V", fontSize=10.5, textColor=DARK))