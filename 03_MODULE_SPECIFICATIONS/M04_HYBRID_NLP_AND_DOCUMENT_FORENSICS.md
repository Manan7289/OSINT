# M04 — Two-Tier Hybrid NLP Extractor (Defang/Regex + ONNX GLiNER) & File Forensics

## 1. Module Name & Identifier
- **Module Title:** M04 — Two-Tier Hybrid NLP Extractor (Defang/Regex + ONNX GLiNER) & File Forensics
- **Target File Path(s):** `backend/nlp/extractor.py, backend/nlp/forensics.py`

## 2. Purpose
Extracts structured technical observables (including defanged IOCs) and zero-shot named entities (`Person`, `Company`, `Threat Actor`, `Malware`, `Location`) from text, HTML, PDFs, Office documents, and images.

## 3. User-Facing Functionality
Powers the Document & Paste Forensics panel in View 2 and enriches all web/news/document entities.

## 4. Internal Responsibilities
1. Refangs defanged indicators (`hxxps://` $\rightarrow$ `https://`, `[.]` $\rightarrow$ `.`, `[@]` $\rightarrow$ `@`).
2. Runs compiled regex + Aho-Corasick gazetteers.
3. Computes Shannon entropy $H(s)$ on hostnames to flag DGA domains.
4. Runs optional CPU INT8 ONNX `gliner_small-v2.1` span extraction when model weights are present.
5. Extracts PDF `/Author`, `/Creator`, `/Producer`, `/CreationDate` (`pypdf`), DOCX core properties (`python-docx`), and Image EXIF GPS/Camera tags (`Pillow`).

## 5. Inputs
`raw_text: str`, `filename: str`, `raw_bytes: bytes`.

## 6. Outputs
`ExtractionBundle` containing extracted observables, named entities, metadata dictionary, SHA-256, SimHash-64, and DGA entropy scores.

## 7. Required Algorithms & Mathematical Formulations
1. **Shannon Entropy:** $H(s) = -\sum_{c} \frac{\text{count}(c)}{|s|} \log_2 \frac{\text{count}(c)}{|s|}$ (flags DGA when $H > 3.8\text{ bits/char}$).
2. **SimHash 64-Bit:** Token shingle hashing into a 64-bit integer with Hamming distance $\le 3$ duplicate detection.
3. **GLiNER Bidirectional Span Scoring (ONNX INT8):** $\text{score}(s_{i,j}, t_k) = \sigma(\phi(h_i, h_j)^\top \psi(t_k))$.

## 8. Dependencies
`re`, `math`, `hashlib`, `pypdf`, `python-docx`, `Pillow`, `beautifulsoup4`, `onnxruntime` (optional model weights).

## 9. Backend Integration
Called by `M03` (`web_document_osint`) and `POST /api/collect/document-text` / `document-upload`.

## 10. Frontend Integration
Displays extracted metadata, EXIF coordinates, and linked entities in View 2 & View 3.

## 11. Data Storage Requirements
Persists `Document` entities, metadata attributes, and `EXTRACTED_FROM_DOC` claims in `M02`.

## 12. Error-Handling Requirements
Corrupt/encrypted PDFs or truncated images catch parser exceptions and still record file SHA-256 + raw byte strings.

## 13. Security, OPSEC & Privacy Requirements
Processes documents strictly in memory (`io.BytesIO`) without executing macros or external XML entities (`defusedxml` / safe `lxml` parser).

## 14. Testing Requirements
`tests/test_m04_nlp_forensics.py`: Verify defanged IOC extraction (`185.220.101[.]34`, `hxxps://c2[.]example[.]net`), Shannon entropy calculation, SimHash similarity, and PDF/EXIF metadata extraction.

## 15. Dependencies on Other Modules
Depends on `M02`.

## 16. Completion & Acceptance Criteria
100% pass rate on `test_m04_nlp_forensics.py`.
