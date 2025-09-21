from django.core.management.base import BaseCommand, CommandError
from pathlib import Path
import json

from mrzapp.morocco import read_morocco_id


class Command(BaseCommand):
    help = "Extract MRZ from a Moroccan national ID (CIN)."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to image/PDF")
        parser.add_argument("--no-legacy", action="store_true", help="Disable legacy OCR engine")
        parser.add_argument("--allow-non-mar", action="store_true", help="Do not enforce MAR country/nationality")

    def handle(self, *args, **options):
        p = Path(options["path"]).expanduser().resolve()
        if not p.exists():
            raise CommandError(f"File not found: {p}")
        use_legacy = not options["no_legacy"]
        require_mar = not options["allow_non_mar"]
        try:
            data = read_morocco_id(str(p), use_legacy=use_legacy, require_mar=require_mar)
        except ValueError as e:
            raise CommandError(str(e))
        self.stdout.write(json.dumps(data, indent=2))



