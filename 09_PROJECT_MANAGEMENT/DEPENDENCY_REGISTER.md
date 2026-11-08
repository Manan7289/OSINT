# DEPENDENCY_REGISTER.md — Verified Python & Frontend Dependency Register

All packages below have prebuilt 64-bit wheels (`win_amd64`, `manylinux`, `macosx`) for Python 3.10–3.12 and require **zero C++ compiler toolchains** on Windows 11:

| Package | Version Range | License | Required vs. Optional | Owning Module(s) | Purpose |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `fastapi` | `>=0.92.0,<1.0.0` | MIT | **Required** | `M09` | REST & WebSocket API framework |
| `uvicorn` | `>=0.17.6,<1.0.0` | BSD-3 | **Required** | `M09` | ASGI HTTP server |
| `pydantic` | `>=1.10.4,<3.0.0` | MIT | **Required** | `M02`, `M09` | Schema validation (write models compatible with v1/v2) |
| `httpx` | `>=0.23.3,<1.0.0` | BSD-3 | **Required** | `M03`, `M08` | Async/sync HTTP client with timeout & redirect control |
| `dnspython` | `>=2.3.0,<3.0.0` | ISC | **Required** | `M03` | DNS resolution & record parsing |
| `cryptography` | `>=38.0.0` | Apache-2.0 / BSD | **Required** | `M01` | Fernet AES-128-CBC + HMAC-SHA256 API key vault |
| `beautifulsoup4` | `>=4.12.0` | MIT | **Required** | `M03`, `M04` | HTML DOM & meta-tag parsing |
| `lxml` | `>=4.9.0` | BSD-3 | **Required** | `M03`, `M04` | Fast HTML/XML/RSS parser |
| `pypdf` | `>=3.0.0` | BSD-3 | **Required** | `M04` | PDF metadata & text forensics |
| `python-docx` | `>=1.0.0` | MIT | **Required** | `M04` | Microsoft Word `.docx` core metadata extraction |
| `Pillow` | `>=9.0.0` | HPND | **Required** | `M04` | Image EXIF & GPS tag forensics |
| `numpy` | `>=1.24.0` | BSD-3 | **Required** | `M05`, `M07`, `M08` | Vectorized Fellegi-Sunter EM & INT8 cosine similarity |
| `scipy` | `>=1.10.0` | BSD-3 | **Required** | `M07` | Sparse matrix PageRank, Haversine distance & spatial clustering |
| `python-multipart` | `>=0.0.5` | Apache-2.0 | **Required** | `M09` | Multipart document upload handling |
| `idna` | `>=3.4` | BSD-3 | **Required** | `M02` | Internationalized Domain Name (Punycode) normalization |
| `onnxruntime` | `>=1.16.0` | MIT | **Optional (Enhanced)** | `M04`, `M08` | Local CPU INT8 inference for GLiNER & embeddings |
| `rustworkx` | `>=0.14.0` | Apache-2.0 | **Optional (Accelerator)** | `M07` | Rust-accelerated graph algorithms (SciPy fallback included) |
| `duckdb` | `>=0.10.0` | MIT | **Optional (Accelerator)** | `M02`, `M05` | Vectorized OLAP SQL analytics |
