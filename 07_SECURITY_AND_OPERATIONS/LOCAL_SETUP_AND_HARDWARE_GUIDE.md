# LOCAL_SETUP_AND_HARDWARE_GUIDE.md — Windows 11 Hardware Budgets, Setup Commands & Troubleshooting

## 1. Hardware Requirements & Empirical Resource Envelope

| Tier | Minimum Hardware | Recommended Hardware | Measured / Expected RAM | GPU Requirement |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Core Mode (Default)** | Dual-core x86_64 CPU, 4 GB RAM, 2 GB free SSD | 4–8 core CPU (Windows 11), 16 GB RAM, NVMe SSD | **~85 MB idle / ~260 MB active** *(Measured on VM)* | **None (100% CPU)** |
| **Tier 2: Enhanced ONNX Mode** | 4-core AVX2 CPU, 8 GB RAM | 8-core CPU (Windows 11), 16 GB RAM | **~140 MB idle / ~520 MB active** | **None (ONNX CPU INT8)** |
| **Tier 3: Optional Local LLM (Ollama)** | 8-core CPU, 16 GB RAM | 8+ core CPU, 16–32 GB RAM (or optional GPU) | **+1.9 GB (3B Q4)** to **+4.8 GB (8B Q4)** | Optional (CPU GGUF works) |

### Empirical Benchmarks Measured on Target CPU (`Python 3.11.2`, `SQLite 3.40.1`)
- **Sorted Neighborhood Blocking ($w=15$) on 2,000 entities:** **3.06 ms** (`27,895` candidate pairs vs. `1,999,000` naive pairs = **71.7× reduction**).
- **SQLite FTS5 Bulk Ingest (10,000 records):** **51.80 ms** (`193,050 docs/sec`).
- **SQLite FTS5 `bm25()` Ranked Query (10,000 records):** **11.15 ms**.
- **384-d Dense Vector Cosine Search (10,000 records, INT8 Quantized):** **7.00 ms** (**3.66 MB** RAM vs. 14.65 MB in FP32).

---

## 2. Local vs. External Connectivity Matrix

| Feature / Workflow | Works 100% Offline (`offline_mode=true`)? | Works with Free Public Internet (Zero API Keys)? | Requires Paid / BYO API Key? |
| :--- | :---: | :---: | :---: |
| Workspace Management, Entity Explorer, Graph & Map UI | **YES** | **YES** | No |
| Document, PDF (`pypdf`), DOCX & Image EXIF (`Pillow`) Forensics | **YES** | **YES** | No |
| Defanged IOC & Regex/Aho-Corasick Extraction + DGA Entropy | **YES** | **YES** | No |
| Unsupervised Fellegi-Sunter EM Entity Resolution & Unmerge | **YES** | **YES** | No |
| W3C PROV Lineage & Subjective Logic Belief Fusion | **YES** | **YES** | No |
| Leiden Communities, IEF-PageRank, Adamic-Adar, HDBSCAN & Burst | **YES** | **YES** | No |
| Hybrid RRF Search (FTS5 BM25 + INT8 Vectors) & GraphRAG Reports | **YES** | **YES** | No |
| 18 Core Live OSINT Collectors (DoH, RDAP, crt.sh, RIPEstat, InternetDB, NVD, CISA KEV, EPSS, GLEIF, SEC, OpenSanctions, Wayback, GDELT, GitHub, Nominatim) | Uses cached/deterministic offline fallback | **YES (Live Queries)** | No |
| 6 Optional Commercial Connectors (Shodan Pro, VirusTotal v3, GreyNoise, SecurityTrails, Censys, OTX) | Graceful `SKIPPED` | Graceful `SKIPPED` | **YES (Configured in Vault)** |

---

## 3. Exact Windows 11 Installation & Execution Commands

### Step 1: Clone Official Repository
```powershell
git clone https://github.com/Manan7289/OSINT.git
cd OSINT
```

### Step 2: Run Windows 11 Automated Installer
```cmd
install.bat
```
*(Or via PowerShell: `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1`)*

### Step 3: Launch the Workstation (`http://127.0.0.1:8000`)
```cmd
start.bat
```

### Step 4: Run Automated Verification Suite
```cmd
.venv\Scripts\activate
pytest -v
```
*(Or `python -m unittest discover -s tests -p "test_*.py" -v`)*
