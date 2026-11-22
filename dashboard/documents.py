from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe(value):
    return escape(str(value or "—")).replace("\n", "<br/>")


def build_quote_pdf(quote):
    """Build a customer quotation from sales fields only; procurement data stays internal."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=13 * mm, leftMargin=13 * mm,
        topMargin=15 * mm, bottomMargin=17 * mm, pageCompression=0,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "QuoteTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=18, leading=22, textColor=colors.HexColor("#17324d"), alignment=0,
    )
    small = ParagraphStyle("QuoteSmall", parent=styles["BodyText"], fontSize=8, leading=10)
    right = ParagraphStyle("QuoteRight", parent=small, alignment=TA_RIGHT)
    story = [
        Paragraph("STEEL QUOTATION", title),
        Spacer(1, 5 * mm),
    ]

    customer = quote.rfq.customer
    customer_details = [customer.name]
    if customer.company_name:
        customer_details.append(customer.company_name)
    if customer.billing_address:
        customer_details.append(customer.billing_address)
    quote_details = [
        f"Quote: {quote.number} · Revision {quote.revision}",
        f"Issue date: {quote.issue_date:%d %b %Y}",
        f"Valid until: {quote.valid_until:%d %b %Y}",
        f"Enquiry: {quote.rfq.reference or quote.rfq}",
    ]
    header = Table([
        [Paragraph("<b>Prepared for</b><br/>" + "<br/>".join(map(_safe, customer_details)), small),
         Paragraph("<br/>".join(map(_safe, quote_details)), right)],
    ], colWidths=[91 * mm, 93 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f6f8")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e1e7")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([header, Spacer(1, 7 * mm)])

    line_rows = [[
        Paragraph("<b>Item</b>", small), Paragraph("<b>Specification</b>", small),
        Paragraph("<b>Quantity</b>", right), Paragraph("<b>Rate</b>", right),
        Paragraph("<b>Amount</b>", right),
    ]]
    for line in quote.lines.all():
        rfq_line = line.rfq_line
        product = rfq_line.product
        item_name = product.name if product else (rfq_line.description or "Steel item")
        specification = " · ".join(part for part in (rfq_line.grade, rfq_line.dimensions) if part)
        line_rows.append([
            Paragraph(_safe(item_name), small),
            Paragraph(_safe(specification), small),
            Paragraph(f"{line.quantity:,.3f} {_safe(line.get_unit_display())}", right),
            Paragraph(f"INR {line.selling_price_per_unit:,.4f}", right),
            Paragraph(f"INR {line.total_selling_price:,.2f}", right),
        ])
    line_table = Table(line_rows, colWidths=[37 * mm, 50 * mm, 34 * mm, 31 * mm, 32 * mm], repeatRows=1)
    line_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eff3")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17324d")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9e1e7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([line_table, Spacer(1, 5 * mm)])

    totals = [
        [Paragraph("Subtotal", small), Paragraph(f"INR {quote.total_selling_price:,.2f}", right)],
    ]
    tax_label = "GST / tax"
    if quote.tax_rate_percent:
        tax_label += f" @ {quote.tax_rate_percent}%"
    totals.append([Paragraph(_safe(tax_label), small), Paragraph(f"INR {quote.tax_amount:,.2f}", right)])
    totals.append([Paragraph("<b>Total payable</b>", small), Paragraph(f"<b>INR {quote.grand_total:,.2f}</b>", right)])
    total_table = Table(totals, colWidths=[53 * mm, 40 * mm], hAlign="RIGHT")
    total_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("LINEABOVE", (0, 2), (-1, 2), 0.8, colors.HexColor("#17324d")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(total_table)

    if quote.payment_terms:
        story.extend([Spacer(1, 5 * mm), Paragraph("<b>Payment terms</b>", small), Paragraph(_safe(quote.payment_terms), small)])
    if quote.delivery_terms:
        story.extend([Spacer(1, 3 * mm), Paragraph("<b>Delivery terms</b>", small), Paragraph(_safe(quote.delivery_terms), small)])
    story.extend([
        Spacer(1, 5 * mm),
        Paragraph("Tax rate and commercial terms are shown as configured for this quotation.", small),
    ])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d9e1e7"))
        canvas.line(13 * mm, 12 * mm, A4[0] - 13 * mm, 12 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#52616d"))
        canvas.drawString(13 * mm, 7 * mm, "Steel Quotes")
        canvas.drawRightString(A4[0] - 13 * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
