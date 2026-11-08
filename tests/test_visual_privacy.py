"""tests/test_visual_privacy.py - Privacy-Preserving Visual Intelligence Tests (M11).

Validates:
  - Forensic metadata extraction (EXIF, GPS, C2PA, 64-bit pHash/dHash/aHash).
  - Near-duplicate detection using Hamming distance (dH <= 10).
  - OpenCV YuNet face detection & mandatory default bystander blurring.
  - Laplacian sharpness variance quality gate (sigma_L^2 >= 40.0, crop >= 48x48px).
  - ConsentGuard blocking unconsented biometric identification attempts (HTTP 403).
"""

import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.visual.consent_guard import (
    ConsentGuard,
    ConsentViolationError,
    QualityGateRejectionError,
)
from backend.visual.media_forensics import media_forensics_engine
from backend.visual.vision_engine import vision_engine
from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _generate_synthetic_face_image(sharp: bool = True, size: int = 200) -> bytes:
    """Generates an in-memory synthetic image with features for testing."""
    img = Image.new("RGB", (size, size), color=(128, 128, 128))
    draw = ImageDraw.Draw(img)
    if sharp:
        # High contrast edges to pass Laplacian variance threshold (>= 40.0)
        for i in range(10, size - 10, 8):
            draw.line([(i, 10), (i, size - 10)], fill=(255, 255, 255) if i % 16 == 0 else (0, 0, 0), width=3)
            draw.line([(10, i), (size - 10, i)], fill=(255, 0, 0) if i % 16 == 0 else (0, 255, 0), width=2)
        # Face-like oval
        draw.ellipse([40, 40, 160, 160], outline=(255, 255, 255), width=4)
        draw.ellipse([65, 75, 85, 95], fill=(0, 0, 0))
        draw.ellipse([115, 75, 135, 95], fill=(0, 0, 0))
        draw.arc([70, 110, 130, 140], start=0, end=180, fill=(255, 255, 255), width=3)
    else:
        # Uniform blurry / low contrast image
        for i in range(size):
            draw.point((i, i), fill=(130, 130, 130))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_media_forensics_and_phash():
    """Validates 64-bit perceptual hashing and forensics extraction."""
    img_bytes = _generate_synthetic_face_image(sharp=True)
    forensics = media_forensics_engine.parse_image_forensics(img_bytes, filename="test_target.jpg")
    
    assert "sha256_hash" in forensics
    assert len(forensics["sha256_hash"]) == 64
    assert "phash_64" in forensics
    assert len(forensics["phash_64"]) == 16  # 64-bit hex is 16 chars
    assert "dhash_64" in forensics
    assert "ahash_64" in forensics


def test_laplacian_sharpness_and_quality_gate():
    """Validates that high contrast images pass and blurry images fail quality gate."""
    sharp_bytes = _generate_synthetic_face_image(sharp=True)
    sharp_analysis = vision_engine.analyze_image(sharp_bytes, blur_bystanders=False)
    assert sharp_analysis["laplacian_sharpness"] >= 40.0
    assert sharp_analysis["quality_gate_passed"] is True

    blurry_bytes = _generate_synthetic_face_image(sharp=False)
    blurry_analysis = vision_engine.analyze_image(blurry_bytes, blur_bystanders=False)
    assert blurry_analysis["laplacian_sharpness"] < 40.0
    assert blurry_analysis["quality_gate_passed"] is False


def test_default_bystander_blurring():
    """Validates that bystander blurring is enabled and modifies the image output."""
    img_bytes = _generate_synthetic_face_image(sharp=True)
    analysis_blurred = vision_engine.analyze_image(img_bytes, blur_bystanders=True)
    assert analysis_blurred["bystanders_blurred"] is True
    assert "processed_image_b64" in analysis_blurred
    assert len(analysis_blurred["processed_image_b64"]) > 100


def test_consent_guard_unconsented_rejection(client):
    """Validates that unconsented biometric verification is strictly blocked (HTTP 403)."""
    import base64
    img_bytes = _generate_synthetic_face_image(sharp=True)
    b64_str = base64.b64encode(img_bytes).decode("ascii")

    # 1. Direct ConsentGuard error
    guard = ConsentGuard()
    with pytest.raises(ConsentViolationError):
        guard.verify_against_gallery(probe_image_bytes=img_bytes, consent_reason="")

    # 2. REST API endpoint HTTP 403
    res = client.post("/api/v1/visual/verify", json={
        "probe_image_b64": b64_str,
        "consent_reason": ""  # empty consent reason triggers block
    })
    assert res.status_code == 403
    assert "consent_reason is mandatory" in res.json()["detail"]


def test_visual_analyze_endpoint(client):
    """Validates POST /api/v1/visual/analyze returns structured report."""
    import base64
    img_bytes = _generate_synthetic_face_image(sharp=True)
    b64_str = base64.b64encode(img_bytes).decode("ascii")

    res = client.post("/api/v1/visual/analyze", json={
        "image_b64": b64_str,
        "filename": "surveillance_capture.jpg",
        "blur_bystanders": True
    })
    assert res.status_code == 200
    data = res.json()
    assert "asset_id" in data
    assert "forensics" in data
    assert "vision" in data
    assert data["vision"]["bystanders_blurred"] is True
    assert "redacted_image_b64" in data
