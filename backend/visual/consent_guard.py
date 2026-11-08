"""backend/visual/consent_guard.py - Ethical Gate for Authorized Face Verification.

Strictly enforces:
  1. Mandatory legal consent attestation (consent_attestation == True).
  2. Documented investigation purpose & automatic 90-day gallery expiration.
  3. Laplacian variance & resolution Quality Gate (rejects blurry / low-res images).
  4. Tamper-evident SHA-256 audit log tracking for every biometric matching attempt.
  5. SFace 128-D cosine similarity matching (threshold >= 0.363).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.core.database import DatabaseManager, db
from backend.visual.vision_engine import vision_engine

logger = logging.getLogger(__name__)

SFACE_MATCH_THRESHOLD = 0.363  # OpenCV SFace official FAR 1e-3 threshold


class ConsentViolationError(Exception):
    """Raised when an unconsented biometric identification attempt is made."""
    pass


class QualityGateRejectionError(Exception):
    """Raised when biometric matching is attempted on an image failing the Quality Gate."""
    pass


class ConsentGuard:
    """Enforces ethical boundaries and consent requirements on facial verification."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database

    def enroll_subject(
        self,
        image_bytes: bytes,
        subject_name: str,
        consent_purpose: str,
        consent_attestation: bool,
        expiration_days: int = 90,
    ) -> Dict[str, Any]:
        """Enrolls an authorized reference individual into consented_face_gallery."""
        if not consent_attestation:
            raise ConsentViolationError(
                "Consent attestation is False. Biometric enrollment without explicit documented consent is strictly prohibited."
            )

        if not subject_name.strip():
            raise ValueError("subject_name must not be empty.")

        if not consent_purpose.strip():
            raise ValueError("consent_purpose must document the authorized case or legal basis.")

        # Check image quality before enrollment
        analysis = vision_engine.analyze_image(image_bytes, blur_bystanders=False)
        sharpness = analysis["laplacian_sharpness"]
        if sharpness < 40.0:
            raise QualityGateRejectionError(
                f"Cannot enroll blurry reference image (Laplacian variance {sharpness} < 40.0). Provide a sharp reference image."
            )

        # Extract 128-D embedding
        emb = vision_engine.extract_face_embedding(image_bytes)
        emb_bytes = emb.tobytes()
        image_sha256 = hashlib.sha256(image_bytes).hexdigest()

        # Calculate expiration (max 90 days)
        valid_days = min(90, max(1, expiration_days))
        expires_at = (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=valid_days)
        ).isoformat()

        gallery_id = self.db.enroll_consented_face(
            subject_name=subject_name.strip(),
            consent_purpose=consent_purpose.strip(),
            consent_attestation=consent_attestation,
            embedding_blob=emb_bytes,
            image_sha256=image_sha256,
            laplacian_sharpness=sharpness,
            expires_at=expires_at,
        )

        # Append to audit ledger
        self.db.append_audit_log(
            action="CONSENT_GALLERY_ENROLL",
            details=f"Enrolled subject '{subject_name}' under purpose '{consent_purpose}'. Expires: {expires_at}",
        )

        return {
            "gallery_id": gallery_id,
            "subject_name": subject_name,
            "laplacian_sharpness": sharpness,
            "quality_grade": analysis["quality_grade"],
            "expires_at": expires_at,
            "status": "ENROLLED",
        }

    def verify_against_gallery(
        self,
        probe_image_bytes: bytes,
        consent_reason: str,
        bbox: Optional[List[int]] = None,
        min_cosine_threshold: float = SFACE_MATCH_THRESHOLD,
    ) -> Dict[str, Any]:
        """Performs 1:N consent-gated verification against active enrolled subjects."""
        if not consent_reason or not consent_reason.strip():
            raise ConsentViolationError(
                "consent_reason is required. Unconsented stranger matching is architecturally blocked."
            )

        # 1. Quality Gate Check
        analysis = vision_engine.analyze_image(probe_image_bytes, blur_bystanders=False)
        sharpness = analysis["laplacian_sharpness"]
        width, height = analysis["dimensions"]

        crop_w = bbox[2] if bbox else width
        crop_h = bbox[3] if bbox else height

        if sharpness < 40.0 or crop_w < 48 or crop_h < 48:
            raise QualityGateRejectionError(
                f"Image or face crop failed Quality Gate (sharpness={sharpness}, res={crop_w}x{crop_h}px). "
                "Biometric matching blocked to prevent low-resolution false positives."
            )

        # 2. Extract probe embedding
        probe_emb = vision_engine.extract_face_embedding(probe_image_bytes, bbox=bbox)

        # 3. Load non-expired gallery entries
        gallery = self.db.list_consented_faces(non_expired_only=True)
        if not gallery:
            return {
                "matches_found": 0,
                "best_match": None,
                "quality_grade": analysis["quality_grade"],
                "laplacian_sharpness": sharpness,
                "message": "Gallery is empty or all enrollments have expired.",
            }

        candidates = []
        for subject in gallery:
            blob = subject.get("embedding_blob")
            if not blob:
                continue
            ref_emb = np.frombuffer(blob, dtype=np.float32)
            cos_sim = vision_engine.cosine_similarity(probe_emb, ref_emb)
            is_match = cos_sim >= min_cosine_threshold

            candidates.append({
                "gallery_id": subject["gallery_id"],
                "subject_name": subject["subject_name"],
                "consent_purpose": subject["consent_purpose"],
                "cosine_similarity": round(float(cos_sim), 4),
                "is_match": is_match,
                "expires_at": subject["expires_at"],
            })

        candidates.sort(key=lambda x: x["cosine_similarity"], reverse=True)
        best = candidates[0] if candidates else None
        matches = [c for c in candidates if c["is_match"]]

        # 4. Audit logging
        self.db.append_audit_log(
            action="CONSENT_GATED_FACE_VERIFY",
            details=f"Verified face against {len(gallery)} gallery subjects for reason: '{consent_reason}'. Best match: {best.get('subject_name') if best else 'None'} ({best.get('cosine_similarity') if best else 0.0})",
        )

        return {
            "matches_found": len(matches),
            "best_match": best,
            "matches": matches,
            "all_evaluated": candidates,
            "quality_grade": analysis["quality_grade"],
            "laplacian_sharpness": sharpness,
            "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


# Singleton
consent_guard = ConsentGuard()
