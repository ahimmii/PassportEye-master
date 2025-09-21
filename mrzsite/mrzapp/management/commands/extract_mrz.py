from django.core.management.base import BaseCommand, CommandError
from passporteye import read_mrz
from pathlib import Path
import json


class Command(BaseCommand):
    help = "Extract MRZ from a given image or PDF file and print JSON."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to image/PDF")
        parser.add_argument("--legacy", action="store_true", help="Use legacy OCR engine (--oem 0)")

    def handle(self, *args, **options):
        p = Path(options["path"]).expanduser().resolve()
        if not p.exists():
            raise CommandError(f"File not found: {p}")
        extra = "--oem 0" if options["legacy"] else ""
        mrz = read_mrz(str(p), extra_cmdline_params=extra)
        if mrz is None:
            raise CommandError("No MRZ detected")
        data = mrz.to_dict()
        self.stdout.write(json.dumps(data, indent=2))


