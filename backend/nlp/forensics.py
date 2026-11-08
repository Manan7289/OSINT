"""backend/nlp/forensics.py - PDF, DOCX, Image EXIF & File Forensics.

M04: Two-Tier Hybrid NLP Extractor (Defang/Regex + ONNX GLiNER) & File Forensics.
"""

from __future__ import annotations

import hashlib
import io
from typing import Any, Dict, Optional, Tuple

import docx
import pypdf
from PIL import ExifTags, Image

from backend.nlp.extractor import compute_simhash_64, extractor


def _convert_dms_to_decimal(dms: Any, ref: str) -> Optional[float]:
    """Converts EXIF Degrees/Minutes/Seconds tuple to signed decimal degrees."""
    try:
        deg = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])
        dec = deg + (minutes / 60.0) + (seconds / 3600.0)
        if ref.upper() in ("S", "W"):
            dec = -dec
        return round(dec, 6)
    except Exception:
        return None


def extract_pdf_metadata(file_bytes: bytes) -> Dict[str, Any]:
    """Extracts PDF metadata (Author, Producer, CreationDate) and embedded text."""
    meta: Dict[str, Any] = {}
    extracted_text: List[str] = []

    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        doc_info = reader.metadata
        if doc_info:
            for k, v in doc_info.items():
                clean_k = str(k).lstrip("/").lower()
                meta[clean_k] = str(v)

        meta["page_count"] = len(reader.pages)
        # Extract text from first 50 pages max
        for page in reader.pages[:50]:
            t = page.extract_text()
            if t:
                extracted_text.append(t)
    except Exception as e:
        meta["error"] = f"PDF parsing error: {e}"

    full_text = "\n".join(extracted_text)
    return {
        "metadata": meta,
        "extracted_text": full_text,
        "entities": extractor.extract_all(full_text) if full_text else {},
    }


def extract_docx_metadata(file_bytes: bytes) -> Dict[str, Any]:
    """Extracts Microsoft Word DOCX core properties and body text."""
    meta: Dict[str, Any] = {}
    extracted_text: List[str] = []

    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        cp = doc.core_properties
        for attr in ["author", "last_modified_by", "created", "modified", "title", "subject", "category", "comments"]:
            val = getattr(cp, attr, None)
            if val is not None:
                meta[attr] = str(val)

        for p in doc.paragraphs:
            if p.text:
                extracted_text.append(p.text)
    except Exception as e:
        meta["error"] = f"DOCX parsing error: {e}"

    full_text = "\n".join(extracted_text)
    return {
        "metadata": meta,
        "extracted_text": full_text,
        "entities": extractor.extract_all(full_text) if full_text else {},
    }


def extract_image_exif(file_bytes: bytes) -> Dict[str, Any]:
    """Extracts Image EXIF tags, Camera Model, Software, and GPS Coordinates."""
    meta: Dict[str, Any] = {}
    gps_info: Dict[str, Any] = {}
    lat: Optional[float] = None
    lon: Optional[float] = None

    try:
        img = Image.open(io.BytesIO(file_bytes))
        meta["format"] = img.format
        meta["size"] = f"{img.width}x{img.height}"

        exif = img.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if tag_name == "GPSInfo":
                    gps_dict = value
                    if isinstance(gps_dict, dict):
                        for g_id, g_val in gps_dict.items():
                            g_name = ExifTags.GPSTAGS.get(g_id, str(g_id))
                            gps_info[g_name] = g_val
                elif isinstance(value, (str, int, float)):
                    meta[tag_name] = value

            # Parse GPS if available
            if "GPSLatitude" in gps_info and "GPSLatitudeRef" in gps_info:
                lat = _convert_dms_to_decimal(gps_info["GPSLatitude"], gps_info["GPSLatitudeRef"])
            if "GPSLongitude" in gps_info and "GPSLongitudeRef" in gps_info:
                lon = _convert_dms_to_decimal(gps_info["GPSLongitude"], gps_info["GPSLongitudeRef"])

    except Exception as e:
        meta["error"] = f"Image EXIF parsing error: {e}"

    return {
        "metadata": meta,
        "latitude": lat,
        "longitude": lon,
        "gps_raw": {k: str(v) for k, v in gps_info.items()},
    }


def analyze_file(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Unified file forensics pipeline.
    
    Computes cryptographic SHA-256 and SimHash-64, extracts format-specific metadata,
    and extracts embedded observables and IOCs.
    """
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    fn_lower = filename.lower()

    res: Dict[str, Any] = {
        "filename": filename,
        "file_size": len(file_bytes),
        "sha256": sha256,
        "metadata": {},
        "entities": {},
        "latitude": None,
        "longitude": None,
        "simhash_64": "0000000000000000",
        "extracted_text_preview": "",
    }

    if fn_lower.endswith(".pdf"):
        pdf_res = extract_pdf_metadata(file_bytes)
        res["file_type"] = "PDF"
        res["metadata"] = pdf_res["metadata"]
        res["entities"] = pdf_res["entities"]
        text = pdf_res["extracted_text"]
        res["simhash_64"] = compute_simhash_64(text)
        res["extracted_text_preview"] = text[:500]

    elif fn_lower.endswith(".docx"):
        docx_res = extract_docx_metadata(file_bytes)
        res["file_type"] = "DOCX"
        res["metadata"] = docx_res["metadata"]
        res["entities"] = docx_res["entities"]
        text = docx_res["extracted_text"]
        res["simhash_64"] = compute_simhash_64(text)
        res["extracted_text_preview"] = text[:500]

    elif any(fn_lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".tiff", ".webp")):
        img_res = extract_image_exif(file_bytes)
        res["file_type"] = "IMAGE"
        res["metadata"] = img_res["metadata"]
        res["latitude"] = img_res["latitude"]
        res["longitude"] = img_res["longitude"]

    else:
        # Plain text / HTML / Log file
        res["file_type"] = "TEXT"
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            res["entities"] = extractor.extract_all(text)
            res["simhash_64"] = compute_simhash_64(text)
            res["extracted_text_preview"] = text[:500]
        except Exception:
            pass

    return res
