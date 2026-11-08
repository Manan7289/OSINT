"""backend/visual/vision_engine.py - OpenCV YuNet Face Detection, Blur Redaction & Quality Gate.

Executes CPU-optimized YuNet face detection (with graceful fallback), Laplacian variance
sharpness scoring, mandatory default bystander face blurring (Gaussian + mosaic pixelation),
and SFace 128-D facial feature embedding.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"
YUNET_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"


class VisionEngine:
    """Privacy-preserving computer vision engine."""

    def __init__(self) -> None:
        self.yunet_model_path = YUNET_PATH
        self.sface_model_path = SFACE_PATH
        self._sface_recognizer = None

    def analyze_image(
        self,
        image_bytes: bytes,
        blur_bystanders: bool = True,
        min_confidence: float = 0.75,
    ) -> Dict[str, Any]:
        """Detects faces, evaluates Laplacian sharpness, applies bystander blurring, and returns report."""
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image bytes into valid CV2 frame.")

        height, width = img.shape[:2]

        # 1. Image Quality Assessment (Laplacian Variance Sharpness)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian_val = cv2.Laplacian(gray, cv2.CV_64F).var()
        laplacian_sharpness = round(float(laplacian_val), 2)

        if laplacian_sharpness < 40.0:
            quality_grade = "POOR_BLURRY"
        elif laplacian_sharpness < 120.0:
            quality_grade = "MODERATE"
        else:
            quality_grade = "HIGH_SHARPNESS"

        # 2. Face Detection
        faces, detector_mode = self._detect_faces_raw(img, min_confidence=min_confidence)

        # 3. Quality Gate per face
        face_records: List[Dict[str, Any]] = []
        redacted_img = img.copy()

        for idx, f in enumerate(faces):
            x, y, w, h = f["bbox"]
            conf = f["confidence"]
            # Ensure within image bounds
            x1 = max(0, int(x))
            y1 = max(0, int(y))
            x2 = min(width, int(x + w))
            y2 = min(height, int(y + h))
            crop_w = max(1, x2 - x1)
            crop_h = max(1, y2 - y1)

            # Measure face crop sharpness
            face_roi_gray = gray[y1:y2, x1:x2]
            face_sharpness = float(cv2.Laplacian(face_roi_gray, cv2.CV_64F).var()) if face_roi_gray.size > 0 else 0.0

            # Quality gate: min 48x48 px and laplacian >= 40.0
            passed_gate = (crop_w >= 48 and crop_h >= 48 and face_sharpness >= 40.0 and laplacian_sharpness >= 40.0)

            rec = {
                "face_id": idx + 1,
                "bbox": [x1, y1, crop_w, crop_h],
                "confidence": round(float(conf), 3),
                "resolution": (crop_w, crop_h),
                "face_sharpness": round(face_sharpness, 2),
                "verification_allowed": passed_gate,
                "quality_warning": (
                    None if passed_gate
                    else "LOW_QUALITY_IMAGE_WARNING: Face crop lacks sufficient resolution (<48px) or sharpness (<40.0) for reliable biometric matching."
                ),
                "landmarks": f.get("landmarks", []),
            }
            face_records.append(rec)

            # 4. Bystander Face Blurring (Gaussian + Mosaic Pixelation)
            if blur_bystanders and crop_w > 0 and crop_h > 0:
                roi = redacted_img[y1:y2, x1:x2]
                if roi.size > 0:
                    # Adaptive kernel size
                    k_size = 2 * (max(crop_w, crop_h) // 6) + 1
                    k_size = max(15, min(99, k_size))
                    blurred_roi = cv2.GaussianBlur(roi, (k_size, k_size), 25)

                    # 8x8 block mosaic pixelation to prevent unblurring
                    mosaic_w = max(4, crop_w // 8)
                    mosaic_h = max(4, crop_h // 8)
                    small = cv2.resize(blurred_roi, (mosaic_w, mosaic_h), interpolation=cv2.INTER_LINEAR)
                    pixelated = cv2.resize(small, (crop_w, crop_h), interpolation=cv2.INTER_NEAREST)

                    redacted_img[y1:y2, x1:x2] = pixelated

        # Encode redacted image to Base64
        _, buffer = cv2.imencode(".jpg", redacted_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        redacted_base64 = base64.b64encode(buffer).decode("utf-8")

        return {
            "dimensions": (width, height),
            "laplacian_sharpness": laplacian_sharpness,
            "quality_grade": quality_grade,
            "quality_gate_passed": (laplacian_sharpness >= 40.0),
            "detector_mode": detector_mode,
            "faces_detected": len(face_records),
            "bystanders_blurred": blur_bystanders,
            "faces": face_records,
            "processed_image_b64": redacted_base64,
            "redacted_image_b64": redacted_base64,
            "redacted_image_base64": f"data:image/jpeg;base64,{redacted_base64}",
        }

    def _detect_faces_raw(
        self, img: np.ndarray, min_confidence: float = 0.75
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Runs YuNet ONNX detector if present, or falls back to contour skin-tone detection."""
        height, width = img.shape[:2]

        if self.yunet_model_path.exists():
            try:
                detector = cv2.FaceDetectorYN.create(
                    str(self.yunet_model_path),
                    "",
                    (width, height),
                    score_threshold=min_confidence,
                    nms_threshold=0.3,
                    top_k=500,
                )
                _, detected = detector.detect(img)
                faces = []
                if detected is not None:
                    for d in detected:
                        x, y, w, h = d[0:4]
                        conf = d[14]
                        # 5 landmarks: right eye, left eye, nose, right mouth, left mouth
                        landmarks = [[float(d[4 + 2*i]), float(d[5 + 2*i])] for i in range(5)]
                        faces.append({
                            "bbox": [float(x), float(y), float(w), float(h)],
                            "confidence": float(conf),
                            "landmarks": landmarks,
                        })
                return faces, "YUNET_ONNX"
            except Exception as e:
                logger.warning(f"YuNet ONNX detector execution failed: {e}; using fallback")

        # Fallback skin-tone & contour detector when ONNX is absent
        faces = self._detect_faces_fallback(img)
        return faces, "HAAR_FALLBACK"

    def _detect_faces_fallback(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """Lightweight color/contour fallback face detector for offline environments."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Skin color range in HSV
        lower_skin = np.array([0, 20, 70], dtype=np.uint8)
        upper_skin = np.array([20, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower_skin, upper_skin)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        faces = []
        h, w = img.shape[:2]
        min_area = (w * h) * 0.005  # At least 0.5% of image

        for c in contours:
            area = cv2.contourArea(c)
            if area > min_area:
                x, y, cw, ch = cv2.boundingRect(c)
                aspect = float(cw) / float(ch)
                # Face aspect ratio roughly 0.6 to 1.4
                if 0.5 <= aspect <= 1.5:
                    faces.append({
                        "bbox": [float(x), float(y), float(cw), float(ch)],
                        "confidence": 0.80,
                        "landmarks": [],
                    })
        return faces[:10]

    def extract_face_embedding(self, image_bytes: bytes, bbox: Optional[List[int]] = None) -> np.ndarray:
        """Extracts a 128-D L2-normalized face embedding."""
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image for embedding extraction.")

        if bbox:
            x, y, w, h = bbox
            h_img, w_img = img.shape[:2]
            crop = img[max(0, y):min(h_img, y + h), max(0, x):min(w_img, x + w)]
        else:
            crop = img

        if crop.size == 0:
            crop = img

        # Try SFace ONNX if present
        if self.sface_model_path.exists():
            try:
                if self._sface_recognizer is None:
                    self._sface_recognizer = cv2.FaceRecognizerSF.create(str(self.sface_model_path), "")
                aligned = cv2.resize(crop, (112, 112))
                emb = self._sface_recognizer.feature(aligned)
                norm = np.linalg.norm(emb)
                if norm > 1e-6:
                    return (emb / norm).flatten().astype(np.float32)
            except Exception as e:
                logger.debug(f"SFace execution error: {e}")

        # Deterministic 128-D embedding fallback (DCT-based 128-D vector)
        resized = cv2.resize(crop, (64, 64))
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY).astype(np.float32)
        dct_vals = cv2.dct(gray)
        # Extract 128 low-frequency coefficients
        sub = dct_vals[:12, :12].flatten()[:128]
        if len(sub) < 128:
            sub = np.pad(sub, (0, 128 - len(sub)))
        norm = np.linalg.norm(sub)
        return (sub / norm).astype(np.float32) if norm > 1e-6 else np.zeros(128, dtype=np.float32)

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Computes cosine similarity between two 128-D embeddings."""
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))


# Singleton
vision_engine = VisionEngine()
