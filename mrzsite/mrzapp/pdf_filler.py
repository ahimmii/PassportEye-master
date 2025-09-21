from __future__ import annotations

from typing import Dict, Any, Optional
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import black
import io
import os


def create_filled_form(mrz_data: Dict[str, Any], template_path: Optional[str] = None) -> bytes:
    """Create a filled PDF form from MRZ data.
    
    Args:
        mrz_data: Dictionary containing MRZ fields
        template_path: Optional path to existing PDF template (not implemented yet)
        
    Returns:
        PDF bytes
    """
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "Passport/ID Information Form")
    
    # Form fields
    y_pos = height - 100
    line_height = 25
    
    def add_field(label: str, value: Any, x: int = 50):
        nonlocal y_pos
        p.setFont("Helvetica", 10)
        p.drawString(x, y_pos, f"{label}:")
        p.setFont("Helvetica-Bold", 10)
        p.drawString(x + 120, y_pos, str(value) if value else "")
        y_pos -= line_height
    
    # Personal Information
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y_pos, "Personal Information")
    y_pos -= line_height
    
    add_field("Document Type", mrz_data.get("type", ""))
    add_field("Country", mrz_data.get("country", ""))
    add_field("Document Number", mrz_data.get("number", ""))
    add_field("Surname", mrz_data.get("surname", ""))
    add_field("Given Names", mrz_data.get("names", ""))
    add_field("Sex", mrz_data.get("sex", ""))
    add_field("Nationality", mrz_data.get("nationality", ""))
    
    # Dates
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y_pos, "Dates")
    y_pos -= line_height
    
    add_field("Date of Birth", mrz_data.get("date_of_birth_formatted", mrz_data.get("date_of_birth", "")))
    add_field("Expiration Date", mrz_data.get("expiration_date_formatted", mrz_data.get("expiration_date", "")))
    
    # Additional fields
    if mrz_data.get("personal_number"):
        add_field("Personal Number", mrz_data.get("personal_number", ""))
    
    # Validation
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y_pos, "Validation")
    y_pos -= line_height
    
    add_field("Valid Score", mrz_data.get("valid_score", ""))
    add_field("Valid Number", "Yes" if mrz_data.get("valid_number") else "No")
    add_field("Valid DOB", "Yes" if mrz_data.get("valid_date_of_birth") else "No")
    add_field("Valid Expiration", "Yes" if mrz_data.get("valid_expiration_date") else "No")
    
    p.save()
    buffer.seek(0)
    return buffer.getvalue()


def fill_existing_pdf(mrz_data: Dict[str, Any], input_pdf_path: str, output_pdf_path: str) -> bool:
    """Fill an existing PDF form with MRZ data.
    
    Note: This is a placeholder - would need to identify form field names
    and use a library like PyPDF2 or pdfrw to fill them.
    
    Args:
        mrz_data: Dictionary containing MRZ fields
        input_pdf_path: Path to input PDF template
        output_pdf_path: Path to save filled PDF
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # This would require knowing the exact field names in the PDF
        # For now, we'll create a new form instead
        pdf_bytes = create_filled_form(mrz_data)
        with open(output_pdf_path, 'wb') as f:
            f.write(pdf_bytes)
        return True
    except Exception as e:
        print(f"Error filling PDF: {e}")
        return False

