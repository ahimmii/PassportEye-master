from django.shortcuts import render
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from passporteye import read_mrz
from .forms import UploadForm
from datetime import datetime
import os
import mimetypes
from django.http import HttpResponse

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
except Exception:  # pragma: no cover
    canvas = None
    A4 = None


def _format_date_dmy(yymmdd: str):
    try:
        # ICAO MRZ dates are YYMMDD
        # Handle 2-digit year: 00-30 = 2000s, 31-99 = 1900s
        year = int(yymmdd[:2])
        if year <= 30:
            year += 2000
        else:
            year += 1900
        month = int(yymmdd[2:4])
        day = int(yymmdd[4:6])
        dt = datetime(year, month, day).date()
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None


def upload_view(request):
    context = {"result": None, "error": None}
    # Direct PDF request using last MRZ in session
    if request.method == "POST" and request.POST.get("action") == "pdf_from_mrz":
        last = request.session.get("last_mrz") or {}
        data = {
            "nom": last.get("surname", "").strip(),
            "prenome": last.get("names", "").strip(),
            "date_naissance": last.get("date_of_birth_formatted", last.get("date_of_birth", "")),
            "nationalite": last.get("nationality", ""),
            "numero": last.get("number", ""),
            "cin": "",
            "carte_sejour": "",
            "entree_maroc": "",
            "passeport_num": last.get("number", ""),
            "domicile": "",
            "domicile2": "",
            "domicile3": "",
            "date_arrivee": "",
            "num_chambre": "",
            "nb_enfants": "",
            "provenance": "",
            "destination": "",
            "fait_a": "Tanger",
            "fait_le": datetime.now().strftime("%d/%m/%Y"),
        }
        pdf_bytes = _generate_hotel_pdf(data)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = "attachment; filename=hotel_form_yougata6.pdf"
        return resp

    # PDF request using inline edited fields on the Result section
    if request.method == "POST" and request.POST.get("action") == "pdf_from_form":
        data = {
            "nom": request.POST.get("nom", ""),
            "prenome": request.POST.get("prenome", ""),
            "date_naissance": request.POST.get("date_naissance", ""),
            "nationalite": request.POST.get("nationalite", ""),
            "numero": request.POST.get("numero", ""),
            "cin": request.POST.get("cin", ""),
            "carte_sejour": request.POST.get("carte_sejour", ""),
            "entree_maroc": request.POST.get("entree_maroc", ""),
            "passeport_num": request.POST.get("passeport_num", ""),
            "domicile": request.POST.get("domicile", ""),
            "domicile2": request.POST.get("domicile2", ""),
            "domicile3": request.POST.get("domicile3", ""),
            "date_arrivee": request.POST.get("date_arrivee", ""),
            "num_chambre": request.POST.get("num_chambre", ""),
            "nb_enfants": request.POST.get("nb_enfants", ""),
            "provenance": request.POST.get("provenance", ""),
            "destination": request.POST.get("destination", ""),
            "fait_a": request.POST.get("fait_a", "Tanger"),
            "fait_le": request.POST.get("fait_le", datetime.now().strftime("%d/%m/%Y")),
        }
        # persist latest edits
        request.session["hotel_form_data"] = data
        pdf_bytes = _generate_hotel_pdf(data)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = "attachment; filename=hotel_form_yougata6.pdf"
        return resp

    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        legacy = form.cleaned_data.get("legacy")
        f = form.cleaned_data["image"]
        data = f.read()
        filename = default_storage.save(os.path.join("uploads", f.name), ContentFile(data))
        full_path = os.path.join(settings.MEDIA_ROOT, filename)
        uploaded_url = default_storage.url(filename)
        mime, _ = mimetypes.guess_type(uploaded_url)
        is_image = bool(mime and mime.startswith("image/"))
        extra = "--oem 0" if legacy else ""
        mrz = None
        # If Moroccan mode requested, try that first
        if request.POST.get("morocco"):
            try:
                from .morocco import read_morocco_id
                d = read_morocco_id(full_path, use_legacy=legacy, require_mar=False)
                mrz = type("Obj", (), {"to_dict": lambda self, _d=d: _d})()
            except Exception:
                # Try front-side fallback OCR if MRZ not present
                try:
                    from .morocco_front import read_morocco_front
                    d = read_morocco_front(full_path)
                    mrz = type("Obj", (), {"to_dict": lambda self, _d=d: _d})()
                except Exception:
                    mrz = None
        if mrz is None:
            mrz = read_mrz(full_path, extra_cmdline_params=extra)
        # Absolute last resort: attempt Moroccan front fallback unconditionally
        if mrz is None:
            try:
                from .morocco_front import read_morocco_front
                d = read_morocco_front(full_path)
                # If fallback produced at least one key field, accept
                if any(d.get(k) for k in ("date_of_birth_formatted", "expiration_date_formatted", "number", "surname", "names")):
                    mrz = type("Obj", (), {"to_dict": lambda self, _d=d: _d})()
            except Exception:
                mrz = None
        if mrz is None:
            context["error"] = "No MRZ detected"
        else:
            d = mrz.to_dict()
            # Normalize keys so templates don't break when fields are missing (e.g., front fallback)
            for key in [
                "date_of_birth",
                "expiration_date",
                "nationality",
                "number",
                "sex",
                "names",
                "surname",
            ]:
                if key not in d:
                    d[key] = ""
            # Backfill formatted dates if only raw is present, or vice versa
            if d.get("date_of_birth") and not d.get("date_of_birth_formatted"):
                d["date_of_birth_formatted"] = _format_date_dmy(d["date_of_birth"]) or d["date_of_birth"]
            if d.get("expiration_date") and not d.get("expiration_date_formatted"):
                d["expiration_date_formatted"] = _format_date_dmy(d["expiration_date"]) or d["expiration_date"]
            context["result"] = d
            context["uploaded_file"] = filename
            context["uploaded_url"] = uploaded_url
            context["is_image"] = is_image
            context["used_legacy"] = legacy
            # Persist last MRZ in session for subsequent hotel form
            request.session["last_mrz"] = d
            request.session["last_uploaded_url"] = uploaded_url
            # Reset inline hotel form data to match the newly extracted passport
            today_dmy = datetime.now().strftime("%d/%m/%Y")
            hotel_default_new = {
                "nom": d.get("surname", "").strip(),
                "prenome": d.get("names", "").strip(),
                "date_naissance": d.get("date_of_birth_formatted", d.get("date_of_birth", "")),
                "nationalite": d.get("nationality", ""),
                "numero": d.get("number", ""),
                "cin": "",
                "carte_sejour": "",
                "entree_maroc": "",
                "passeport_num": d.get("number", ""),
                "domicile": "",
                "domicile2": "",
                "domicile3": "",
                "date_arrivee": "",
                "num_chambre": "",
                "nb_enfants": "",
                "provenance": "",
                "destination": "",
                "fait_a": "Tanger",
                "fait_le": today_dmy,
            }
            request.session["hotel_form_data"] = hotel_default_new
            request.session["hotel_form_source_id"] = d.get("number") or d.get("raw_text") or ""
    else:
        context["error"] = None if request.method == "GET" else "Invalid form submission"
    # Build default hotel data for inline edit section
    last = request.session.get("last_mrz") or {}
    basis = context.get("result") or last or {}
    hotel_default = {
        "nom": basis.get("surname", "").strip(),
        "prenome": basis.get("names", "").strip(),
        "date_naissance": basis.get("date_of_birth_formatted", basis.get("date_of_birth", "")),
        "nationalite": basis.get("nationality", ""),
        "numero": basis.get("number", ""),
        "cin": "",
        "carte_sejour": "",
        "entree_maroc": "",
        "passeport_num": basis.get("number", ""),
        "domicile": "",
        "domicile2": "",
        "domicile3": "",
        "date_arrivee": "",
        "num_chambre": "",
        "nb_enfants": "",
        "provenance": "",
        "destination": "",
        "fait_a": "Tanger",
        "fait_le": datetime.now().strftime("%d/%m/%Y"),
    }
    # prefer any previously edited, but if MRZ source changed, reset to defaults
    prev = request.session.get("hotel_form_data")
    prev_source = request.session.get("hotel_form_source_id")
    current_source = (basis.get("number") or basis.get("raw_text") or "")
    if prev is not None and prev_source == current_source:
        context["hotel"] = prev
    else:
        context["hotel"] = hotel_default
    # Provide ISO date variants for HTML date inputs
    def _to_iso_date(dmy: str):
        try:
            return datetime.strptime(dmy, "%d/%m/%Y").date().isoformat()
        except Exception:
            return ""
    h = context["hotel"]
    h["date_naissance_iso"] = _to_iso_date(h.get("date_naissance", ""))
    h["date_arrivee_iso"] = _to_iso_date(h.get("date_arrivee", ""))
    h["fait_le_iso"] = _to_iso_date(h.get("fait_le", ""))
    context["form"] = form
    return render(request, "mrzapp/upload.html", context)


def hotel_form_view(request):
    """Render an editable hotel form prefilled with last MRZ values and allow PDF download."""
    initial = {
        "nom": "",
        "prenome": "",
        "date_naissance": "",
        "nationalite": "",
        "numero": "",
        "cin": "",
        "carte_sejour": "",
        "entree_maroc": "",
        "passeport_num": "",
        "domicile": "",
        "domicile2": "",
        "domicile3": "",
        "date_arrivee": "",
        "num_chambre": "",
        "nb_enfants": "",
        "provenance": "",
        "destination": "",
        "fait_a": "Tanger",
        "fait_le": datetime.now().strftime("%d/%m/%Y"),
    }
    last = request.session.get("last_mrz") or {}
    if last:
        initial.update({
            "nom": last.get("surname", "").strip(),
            "prenome": last.get("names", "").strip(),
            "date_naissance": last.get("date_of_birth_formatted", last.get("date_of_birth", "")),
            "nationalite": last.get("nationality", ""),
            "numero": last.get("number", ""),
            "passeport_num": last.get("number", ""),
        })

    if request.method == "POST":
        data = {k: request.POST.get(k, "") for k in initial.keys()}
        # Generate PDF
        if request.POST.get("action") == "pdf":
            pdf_bytes = _generate_hotel_pdf(data)
            resp = HttpResponse(pdf_bytes, content_type="application/pdf")
            resp["Content-Disposition"] = "attachment; filename=hotel_form.pdf"
            return resp
        # Otherwise, re-render with edits persisted in session
        request.session["hotel_form_data"] = data
        return render(request, "mrzapp/hotel_form.html", {"data": data})

    # GET: use last edited state if present
    data = request.session.get("hotel_form_data") or initial
    return render(request, "mrzapp/hotel_form.html", {"data": data})


def _generate_hotel_pdf(data: dict) -> bytes:
    """Generate a simple A4 PDF matching the requested layout using reportlab."""
    if canvas is None:
        return b""
    from io import BytesIO
    buf = BytesIO()
    YOUGATA6 = (3.86 * inch, 7.48 * inch)
    p = canvas.Canvas(buf, pagesize=YOUGATA6)
    width, height = YOUGATA6
    y = height - 30
    lh = 22

    def line(label_left: str, label_right: str = None, value: str = "", align: str = "center"):
        nonlocal y
        p.setFont("Helvetica-Bold", 11)
        p.drawString(10, y, label_left)
        if label_right:
            p.setFont("Helvetica", 10)
            p.drawString(300, y, label_right)
        if value:
            p.setFont("Helvetica", 11)
            text_width = p.stringWidth(value, "Helvetica", 11)
            if align == "right":
                rx = width - 90 - text_width #date
                p.drawString(rx, y, value)
            elif align == "left":
                p.drawString(220, y, value)
            else:
                cx = (width - text_width) / 2.0
                p.drawString(cx, y, value)
        y -= lh

    def multiline(label_left: str, lines: list[str]):
        nonlocal y
        p.setFont("Helvetica-Bold", 11)
        p.drawString(10, y, label_left)
        y -= lh
        p.setFont("Helvetica", 11)
        for ln in lines:
            if not ln:
                y -= lh
                continue
            text_width = p.stringWidth(ln, "Helvetica", 11)
            cx = (width - text_width) / 2.0
            p.drawString(cx, y, ln)
            y -= lh

    def dual_line(label1: str, value1: str, label2: str, value2: str):
        nonlocal y
        # Left pair
        p.setFont("Helvetica-Bold", 11)
        x1 = 10
        p.drawString(x1, y, label1)
        p.setFont("Helvetica", 11)
        x1v = x1 + p.stringWidth(label1, "Helvetica-Bold", 11) + 6
        if value1:
            p.drawString(x1v, y, value1)
        # Right pair
        p.setFont("Helvetica-Bold", 11)
        x2 = max(width * 0.55, x1v + 90)
        if x2 > width - 120:
            x2 = width - 120
        p.drawString(x2, y, label2)
        p.setFont("Helvetica", 11)
        x2v = x2 + p.stringWidth(label2, "Helvetica-Bold", 11) + 6
        if value2:
            p.drawString(x2v, y, value2)
        y -= lh

    def _fmt_dmy(value: str) -> str:
        if not value:
            return ""
        try:
            # Accept DD/MM/YYYY
            return datetime.strptime(value, "%d/%m/%Y").strftime("%d/%m/%Y")
        except Exception:
            try:
                # Accept ISO YYYY-MM-DD
                return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                return value

    # Normalize date-like fields
    data["date_naissance"] = _fmt_dmy(data.get("date_naissance", ""))
    data["date_arrivee"] = _fmt_dmy(data.get("date_arrivee", ""))
    data["fait_le"] = _fmt_dmy(data.get("fait_le", ""))

    # Header
    p.setFont("Helvetica-Bold", 14)
    _title = "Hotel Palace - Tanger"
    _tw = p.stringWidth(_title, "Helvetica-Bold", 14)
    _tx = (width - _tw) / 2.0
    p.drawString(_tx, y, _title)
    y -= lh * 1.5
    p.drawString(30, y, "FICHE D'HÔTEL - HOTEL FORM")
    y -= lh * 1.5

    # Fields per user format (without dotted leaders)
    line("Nom :", "Name - Apellidos", data.get("nom", ""))
    y -= lh * 0.5
    line("Prenome :", "First name - Nombre", data.get("prenome", ""))
    y -= lh * 0.5
    line("Date de naissance :", "Date of Birth - Ficha de Nacimiento", data.get("date_naissance", ""), align="right")
    y -= lh * 0.5
    line("Nationalité :", "Nationality - Nacionalida", data.get("nationalite", ""))

    if data.get("cin"):
        y -= lh * 0.5
        line("C.I.N :", value=data.get("cin", ""))
    if data.get("carte_sejour"):
        y -= lh * 0.5
        line("Carte de séjour :", value=data.get("carte_sejour", ""))
    if data.get("entree_maroc"):
        y -= lh * 0.5
        dual_line("D’entrée Au Maroc :", data.get("entree_maroc", ""), "", "")
    if data.get("passeport_num"):
        y -= lh * 0.5
        line("Passeport N° :", value=data.get("passeport_num", ""))

    y -= lh * 0.5
    # dual_line("Domicile Habituel :", data.get("domicile", ""), "", "")
    multiline("Domicile Habituel :", [
        data.get("domicile", ""),
    ])

    y -= lh * 0.5
    dual_line("Date d’arrivée ", data.get('date_arrivee',''), "N° de chambre :", data.get('num_chambre',''))
    y -= lh * 0.5
    dual_line("N° d’enfants mineurs accompagnant le client :", data.get("nb_enfants", ""), "", "")
    y -= lh * 0.5
    dual_line("Lieu de Provenance :", data.get('provenance',''), "Destination :", data.get('destination',''))

    y -= lh * 1.5
    line("Fait à Tanger, le :", value=f"{data.get('fait_le','')}")

    p.showPage()
    p.save()
    buf.seek(0)
    return buf.getvalue()

