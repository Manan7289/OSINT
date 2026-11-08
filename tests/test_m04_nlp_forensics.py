"""tests/test_m04_nlp_forensics.py - Comprehensive Unit Tests for M04.

Validates Defanging/Refanging, Regex IOC Extraction, Shannon Entropy DGA Detection,
SimHash-64 Text Similarity, and PDF/DOCX/Image File Forensics.
"""

from __future__ import annotations

import io
import docx
import pypdf
import pytest
from PIL import Image

from backend.nlp.extractor import (
    compute_simhash_64,
    defang,
    extractor,
    is_dga_domain,
    refang,
    shannon_entropy,
)
from backend.nlp.forensics import analyze_file
from backend.core.provenance_fusion import simhash_hamming_distance


def test_refanging_and_defanging():
    """Test normalization of defanged network indicators."""
    defanged_input = "Sample C2 at hxxps://evil-c2[.]threat[.]net/beacon from IP 185.220.101[.]34 contact admin[@]evil[.]com"
    refanged = refang(defanged_input)

    assert "https://evil-c2.threat.net/beacon" in refanged
    assert "185.220.101.34" in refanged
    assert "admin@evil.com" in refanged

    # Test defang
    clean = "https://target.com"
    defanged = defang(clean)
    assert defanged == "hxxps://target[.]com"


def test_regex_ioc_extraction():
    """Test comprehensive technical observable extraction from unstructured text."""
    sample_text = """
    Incident Report: APT-41 activity detected.
    Host connecting to 198.51.100.45 and resolving c2.darkshadow.net.
    Autonomous System: AS13335 (Cloudflare).
    Vulnerability exploited: CVE-2024-3400 in PAN-OS.
    Attacker email: adversary_ops@shadow-corp.io.
    Bitcoin ransom address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
    Ethereum address: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F
    File SHA256: 2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae
    """
    results = extractor.extract_all(sample_text)

    assert "198.51.100.45" in results["IPv4Address"]
    assert "adversary_ops@shadow-corp.io" in results["Email"]
    assert "CVE-2024-3400" in results["Vulnerability"]
    assert "AS13335" in results["AutonomousSystem"]
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in results["CryptoWallet"]
    assert "0x71C7656EC7ab88b098defB751B7401B5f6d8976F" in results["CryptoWallet"]
    assert "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae" in results["SHA256"]
    assert "c2.darkshadow.net" in results["Domain"]


def test_shannon_entropy_and_dga_detection():
    """Test Shannon entropy calculation and DGA domain classification."""
    # Low entropy standard domain
    dga_legit, score_legit = is_dga_domain("google.com")
    assert dga_legit is False
    assert score_legit < 3.0

    # High entropy DGA domain
    dga_mal, score_mal = is_dga_domain("xkjhqwe87293jsdf.biz")
    assert dga_mal is True
    assert score_mal >= 3.8


def test_simhash_near_duplicates():
    """Test 64-bit SimHash near-duplicate detection."""
    text1 = "Security incident detected on server alpha in datacenter us-east with unauthorized access"
    text2 = "Security incident detected on server alpha in datacenter us-east with unauthorized logins"
    text3 = "Completely unrelated text discussing international economic trade policies and tariffs"

    h1 = compute_simhash_64(text1)
    h2 = compute_simhash_64(text2)
    h3 = compute_simhash_64(text3)

    # Near duplicates should have small Hamming distance (<= 6)
    dist_1_2 = simhash_hamming_distance(h1, h2)
    assert dist_1_2 <= 6

    # Completely different texts should have large Hamming distance
    dist_1_3 = simhash_hamming_distance(h1, h3)
    assert dist_1_3 > 12


def test_pdf_forensics_extraction():
    """Test synthetic PDF metadata and IOC extraction."""
    # Build synthetic in-memory PDF
    writer = pypdf.PdfWriter()
    writer.add_metadata({
        "/Author": "Investigator Zero",
        "/Producer": "LocalOSINT-TestWriter",
        "/Title": "Threat Briefing 2026",
    })
    page = writer.add_blank_page(width=612, height=792)
    # Note: pypdf blank page doesn't have text by default; let's test metadata extraction
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    res = analyze_file("briefing.pdf", pdf_bytes)
    assert res["file_type"] == "PDF"
    assert res["metadata"].get("author") == "Investigator Zero"
    assert res["metadata"].get("producer") == "LocalOSINT-TestWriter"
    assert len(res["sha256"]) == 64


def test_docx_forensics_extraction():
    """Test synthetic DOCX document metadata and text extraction."""
    doc = docx.Document()
    doc.core_properties.author = "Forensic Analyst"
    doc.core_properties.title = "IOC Summary Document"
    doc.add_paragraph("Suspicious C2 observed at 203.0.113.88 contacting CVE-2023-38606 exploit broker.")

    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    res = analyze_file("analysis.docx", docx_bytes)
    assert res["file_type"] == "DOCX"
    assert res["metadata"].get("author") == "Forensic Analyst"
    assert "203.0.113.88" in res["entities"]["IPv4Address"]
    assert "CVE-2023-38606" in res["entities"]["Vulnerability"]


def test_image_forensics_extraction():
    """Test image metadata extraction."""
    # Create simple 100x100 RGB JPEG
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    res = analyze_file("evidence.jpg", img_bytes)
    assert res["file_type"] == "IMAGE"
    assert res["metadata"].get("format") == "JPEG"
    assert res["metadata"].get("size") == "100x100"
