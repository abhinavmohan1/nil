from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import hashlib
from decimal import Decimal
from courses.utils import calculate_trainer_monthly_hours
import logging

logger = logging.getLogger(__name__)

def load_font():
    font_name = 'Helvetica'  # Default fallback font
    try:
        # Try to load Arial Unicode
        arial_unicode_path = os.path.join(os.path.dirname(__file__), 'fonts', 'Arial Unicode.ttf')
        if os.path.exists(arial_unicode_path):
            pdfmetrics.registerFont(TTFont('ArialUnicode', arial_unicode_path))
            font_name = 'ArialUnicode'
        else:
            # Try to load DejaVu Sans (comes with ReportLab)
            pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
            font_name = 'DejaVu'
    except Exception as e:
        logger.warning(f"Failed to load custom fonts: {str(e)}. Using Helvetica as fallback.")
    
    return font_name

# Load the font
FONT_NAME = load_font()

def calculate_salary(user, year, month):
    if user.role == 'STUDENT':
        return None, None

    base_salary = Decimal('0.00')
    total_hours = Decimal('0.00')
    hourly_rate = Decimal('0.00')
    
    if user.role == 'TRAINER':
        total_hours = calculate_trainer_monthly_hours(user, year, month)
        trainer_profile = user.trainer
        if trainer_profile and trainer_profile.salary and trainer_profile.approved_hours:
            hourly_rate = trainer_profile.salary / trainer_profile.approved_hours / Decimal('22')
            base_salary = hourly_rate * Decimal(str(total_hours))
    else:  # ADMIN or MANAGER
        base_salary = user.fixed_salary or Decimal('0.00')

    # Calculate additions
    additions = {
        'group_class_compensation': user.group_class_compensation or Decimal('0.00'),
        'performance_incentive': user.performance_incentive or Decimal('0.00'),
        'arrears': user.arrears or Decimal('0.00'),
        'advance': user.advance or Decimal('0.00')
    }
    total_additions = sum(additions.values())

    # Calculate deductions
    deductions = {
        'performance_depreciation': user.performance_depreciation or Decimal('0.00'),
        'tds': user.tds or Decimal('0.00'),
        'pf': user.pf or Decimal('0.00'),
        'advance_recovery': user.advance_recovery or Decimal('0.00'),
        'loss_recovery': user.loss_recovery or Decimal('0.00')
    }
    total_deductions = sum(deductions.values())

    total_earnings = base_salary + total_additions
    total_salary = total_earnings - total_deductions

    calculation_details = {
        'base_salary': f"₹{base_salary:.2f}",
        'additions': {k: f"₹{v:.2f}" for k, v in additions.items()},
        'deductions': {k: f"₹{v:.2f}" for k, v in deductions.items()},
        'total_earnings': f"₹{total_earnings:.2f}",
        'total_deductions': f"₹{total_deductions:.2f}",
        'total_salary': f"₹{total_salary:.2f}"
    }

    if user.role == 'TRAINER':
        calculation_details['trainer_details'] = {
            'total_hours': f"{total_hours:.2f}",
            'hourly_rate': f"₹{hourly_rate:.2f}"
        }

    return total_salary, calculation_details

def generate_salary_slip_pdf(user, month, year, calculation_details):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontName=FONT_NAME)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName=FONT_NAME)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontName=FONT_NAME, fontSize=8)
    
    # Company logo and details
    try:
        logo = Image('https://nationalinstituteoflanguage.in/wp-content/uploads/2024/10/Edutech.png', width=2*inch, height=1*inch)
        elements.append(logo)
    except Exception as e:
        logger.warning(f"Failed to load company logo: {str(e)}")
        elements.append(Paragraph("NIL Edutech (P) Limited", title_style))
    
    company_details = [
        Paragraph("NIL Edutech (P) Limited", title_style),
        Paragraph("L-43, Sec E, LDA, Kanpur Road, Lucknow : 226012", normal_style),
        Paragraph("Reg No. 151255 | CIN: U80902UP2021PTC151255", normal_style),
        Paragraph("Phone: +91 9569 285 185", normal_style),
    ]
    for detail in company_details:
        elements.append(detail)

    # Title
    elements.append(Paragraph(f"Salary Slip - {month}/{year}", title_style))

    # Employee details
    employee_id_prefix = "TN" if user.role == 'TRAINER' else "CN"
    employee_id = f"{employee_id_prefix}{year}{user.id}"
    elements.append(Paragraph(f"Employee Name: {user.get_full_name()}", normal_style))
    elements.append(Paragraph(f"Employee ID: {employee_id}", normal_style))

    # Salary details
    data = [
        ["Component", "Earnings (₹)", "Deductions (₹)"],
        ["Base Salary", calculation_details['base_salary'], ""],
        ["Group Class Compensation", calculation_details['additions']['group_class_compensation'], ""],
        ["Performance Incentive", calculation_details['additions']['performance_incentive'], ""],
        ["Arrears", calculation_details['additions']['arrears'], ""],
        ["Advance", calculation_details['additions']['advance'], ""],
        ["Performance Depreciation", "", calculation_details['deductions']['performance_depreciation']],
        ["TDS", "", calculation_details['deductions']['tds']],
        ["PF", "", calculation_details['deductions']['pf']],
        ["Advance Recovery", "", calculation_details['deductions']['advance_recovery']],
        ["Loss Recovery", "", calculation_details['deductions']['loss_recovery']],
        ["Total", calculation_details['total_earnings'], calculation_details['total_deductions']],
        ["Net Salary", calculation_details['total_salary'], ""]
    ]

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)

    if user.role == 'TRAINER':
        elements.append(Paragraph("Trainer Details", styles['Heading2']))
        elements.append(Paragraph(f"Total Hours Worked: {calculation_details['trainer_details']['total_hours']}", normal_style))
        elements.append(Paragraph(f"Hourly Rate: ₹{calculation_details['trainer_details']['hourly_rate']}", normal_style))

    # Footer
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph("This is a computer generated document. It does not require signatures.", small_style))
    
    # Generate hash
    content_for_hash = f"{user.get_full_name()}{employee_id}{month}{year}{calculation_details['total_salary']}"
    document_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
    elements.append(Paragraph(f"Hash: {document_hash}", small_style))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf