# M11 — Privacy-Preserving Visual Intelligence & Media Forensics Studio

- **Target Files:** `backend/visual/vision_engine.py`, `backend/visual/media_forensics.py`, `backend/visual/consent_guard.py`
- **Action:** Implement the complete specification in `AI_AND_ALGORITHMS/VISUAL_INTELLIGENCE_SPECIFICATION.md`:
  - EXIF/GPS/XMP/C2PA metadata parser (`Pillow`).
  - 64-bit `pHash`, `dHash`, `aHash` computation and Hamming distance search ($d_H \le 10$).
  - `OpenCV YuNet` face detection (with automatic Haar Cascade fallback if ONNX weights are missing).
  - Laplacian variance $\sigma_L^2$ sharpness quality gate ($\sigma_L^2 < 40.0$ or face $< 48	imes 48	ext{ px}$ triggers `LOW_QUALITY_WARNING` and blocks biometric matching).
  - Default automatic bystander face blurring (`blur_bystanders=True`).
  - Consent-gated `SFace` 128-D verification against `consented_face_gallery` enforced by `ConsentGuard` + SHA-256 audit logging.
