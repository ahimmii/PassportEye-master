from django.core.management.base import BaseCommand, CommandError
from pathlib import Path
import json
import os

from mrzapp.pdf_filler import create_filled_form, fill_existing_pdf
from mrzapp.morocco import read_morocco_id


class Command(BaseCommand):
    help = "Extract MRZ and create a filled PDF form."

    def add_arguments(self, parser):
        parser.add_argument("input_path", type=str, help="Path to image/PDF with MRZ")
        parser.add_argument("--output", type=str, help="Output PDF path (default: input_name_filled.pdf)")
        parser.add_argument("--no-legacy", action="store_true", help="Disable legacy OCR engine")
        parser.add_argument("--morocco", action="store_true", help="Use Moroccan ID reader")
        parser.add_argument("--template", type=str, help="Path to PDF template (not implemented)")

    def handle(self, *args, **options):
        input_path = Path(options["input_path"]).expanduser().resolve()
        if not input_path.exists():
            raise CommandError(f"File not found: {input_path}")
        
        # Determine output path
        if options["output"]:
            output_path = Path(options["output"]).expanduser().resolve()
        else:
            output_path = input_path.parent / f"{input_path.stem}_filled.pdf"
        
        use_legacy = not options["no_legacy"]
        
        try:
            # Extract MRZ data
            if options["morocco"]:
                mrz_data = read_morocco_id(str(input_path), use_legacy=use_legacy, require_mar=False)
            else:
                from passporteye import read_mrz
                extra = "--oem 0" if use_legacy else ""
                mrz = read_mrz(str(input_path), extra_cmdline_params=extra)
                if mrz is None:
                    raise CommandError("No MRZ detected")
                mrz_data = mrz.to_dict()
                
                # Add formatted dates
                from mrzapp.views import _format_date_dmy
                if mrz_data.get("date_of_birth"):
                    mrz_data["date_of_birth_formatted"] = _format_date_dmy(mrz_data["date_of_birth"]) or mrz_data["date_of_birth"]
                if mrz_data.get("expiration_date"):
                    mrz_data["expiration_date_formatted"] = _format_date_dmy(mrz_data["expiration_date"]) or mrz_data["expiration_date"]
            
            # Create filled PDF
            if options["template"]:
                success = fill_existing_pdf(mrz_data, options["template"], str(output_path))
                if not success:
                    raise CommandError("Failed to fill template PDF")
            else:
                pdf_bytes = create_filled_form(mrz_data)
                with open(output_path, 'wb') as f:
                    f.write(pdf_bytes)
            
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created filled PDF: {output_path}")
            )
            self.stdout.write("MRZ Data:")
            self.stdout.write(json.dumps(mrz_data, indent=2))
            
        except Exception as e:
            raise CommandError(f"Error: {e}")

