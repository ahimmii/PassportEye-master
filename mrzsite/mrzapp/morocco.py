from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from passporteye import read_mrz


def _format_date_dmy(yymmdd: Optional[str]) -> Optional[str]:
    if not yymmdd:
        return None
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


def read_morocco_id(file_path: str, use_legacy: bool = True, require_mar: bool = True) -> Dict[str, Any]:
    """Read a Moroccan national ID (CIN) MRZ from an image/PDF.

    Args:
        file_path: Path to the input file.
        use_legacy: Whether to invoke Tesseract legacy engine (recommended for MRZ).
        require_mar: If True, ensure country or nationality is 'MAR'.

    Returns:
        A dictionary with parsed MRZ fields and formatted dates.

    Raises:
        ValueError: If no MRZ is detected or document does not appear Moroccan when require_mar is True.
    """
    extra = "--oem 0" if use_legacy else ""
    mrz = read_mrz(file_path, extra_cmdline_params=extra)
    if mrz is None:
        raise ValueError("No MRZ detected in the provided file")

    data = mrz.to_dict()

    # Validate Moroccan document if requested (either issuing country or nationality MAR)
    if require_mar and not (str(data.get("country", "")).upper() == "MAR" or str(data.get("nationality", "")).upper() == "MAR"):
        raise ValueError("The MRZ does not correspond to a Moroccan document (country/nationality != MAR)")

    # Enrich with formatted dates
    data["date_of_birth_formatted"] = _format_date_dmy(data.get("date_of_birth")) or data.get("date_of_birth")
    data["expiration_date_formatted"] = _format_date_dmy(data.get("expiration_date")) or data.get("expiration_date")
    return data


