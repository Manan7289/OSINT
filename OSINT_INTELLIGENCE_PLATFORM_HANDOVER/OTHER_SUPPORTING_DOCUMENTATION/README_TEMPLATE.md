# LocalOSINT v3.0 — Next-Generation Global Intelligence Command Centre

**Official Repository:** [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git)

`LocalOSINT v3.0` is a local-first, privacy-preserving **Global Geospatial, Cyber, and Visual Intelligence Command Centre** built in Python 3.11+ and FastAPI. It fuses the capabilities of **Argos Atlas** (real-time aviation/maritime tracking, OFAC sanctions cross-referencing, GPS interference zones, public cameras), **Crucix** (15-minute scheduled parallel sweeps, Sweep-Delta escalation analysis, multi-channel alerting, grounded AI SitReps), and **God's Eye View** (keyless 2D/3D globe, real-time `SGP4` satellite orbital propagation, 4D historical time scrubber, and honest telemetry status badges) with a **Privacy-Preserving Visual Intelligence Studio** (`OpenCV YuNet`, automatic bystander face blurring, 64-bit `pHash` deduplication, EXIF/C2PA forensics, and consent-gated `SFace` verification).

## Quick Start (Windows 11)
1. Double-click `install.bat` (creates `.venv`, installs dependencies, and initializes the 20-table SQLite WAL database).
2. Double-click `start.bat` (launches the server and opens `http://127.0.0.1:8420`).
3. Run the automated verification suite at any time via `pytest -v`.
