# 14 — LOCAL SETUP AND DEPLOYMENT (`LocalOSINT v3.0`)

**Target Repository:** [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git)  
**Target OS:** Windows 11 (Primary) & Linux / macOS (Cross-Platform Compatible)  
**Runtime:** Python 3.11+ (Zero Docker, Zero Node.js Build Step, Zero External DBMS Required)

---

## 1. Hardware & Software Prerequisites

- **Operating System:** Windows 11 (64-bit) — also runs natively on Windows 10, Ubuntu 22.04+, and macOS 13+.
- **Python:** Python 3.11 or 3.12 (`python --version`).
- **RAM:** 8 GB minimum (16 GB recommended when running local Ollama LLMs).
- **Disk Space:** ~500 MB for Python virtual environment, SQLite WAL database, bootstrap datasets, and OpenCV ONNX models (`YuNet` 337 KB + `SFace` 36.9 MB).
- **API Keys Required:** **None (0 keys required to launch and use all 18 default layers!).** Optional keys can be entered in the UI Vault or `.env`.

---

## 2. Updated `requirements.txt` Specification

Antigravity must update `requirements.txt` in the root of `https://github.com/Manan7289/OSINT.git` to include the v3.0 orbital and visual intelligence packages (all of which have pre-built `win_amd64` wheels on PyPI requiring no C++ compiler):

```text
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pydantic>=2.7.0
httpx>=0.27.0
numpy>=1.26.0
scipy>=1.13.0
scikit-learn>=1.4.2
hdbscan>=0.8.33
igraph>=0.11.4
leidenalg>=0.10.2
cryptography>=42.0.5
sgp4>=2.23
Pillow>=10.3.0
imagehash>=4.3.1
opencv-python-headless>=4.9.0.80
python-multipart>=0.0.9
pytest>=8.1.1
```

---

## 3. Windows 11 One-Click Installation (`install.bat`)

```bat
@echo off
SETLOCAL EnableDelayedExpansion
TITLE LocalOSINT v3.0 — Next-Generation Global Intelligence Command Centre Installer

echo ============================================================================
echo   LocalOSINT v3.0 — Automated Windows 11 Setup ^& Model Bootstrapper
echo ============================================================================

python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python 3.11+ is not installed or not on PATH.
    pause
    exit /b 1
)

IF NOT EXIST ".venv" (
    echo [1/4] Creating Python virtual environment (.venv)...
    python -m venv .venv
)

echo [2/4] Activating virtual environment and upgrading pip...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip wheel

echo [3/4] Installing LocalOSINT v3.0 Python dependencies...
pip install -r requirements.txt

echo [4/4] Creating data directories and verifying offline bootstrap assets...
if not exist "data\models" mkdir "data\models"
if not exist "data\bootstrap" mkdir "data\bootstrap"
python -c "from backend.core.database import DatabaseManager; db = DatabaseManager(); print('[OK] 20-Table SQLite WAL Database initialized at', db.db_path)"

echo ============================================================================
echo   Installation Complete! Run start.bat to launch LocalOSINT v3.0.
echo ============================================================================
pause
```

---

## 4. Windows 11 One-Click Launcher (`start.bat`)

```bat
@echo off
TITLE LocalOSINT v3.0 — Global Intelligence Command Centre
IF NOT EXIST ".venv\Scripts\activate.bat" (
    echo Virtual environment not found. Running install.bat first...
    call install.bat
)
call .venv\Scripts\activate.bat
echo Starting LocalOSINT v3.0 Command Centre on http://127.0.0.1:8420 ...
start "" http://127.0.0.1:8420
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8420
```

---

## 5. Optional `.env.example` Template

```ini
# LocalOSINT v3.0 Optional Configuration (All features work keylessly out-of-the-box!)
LOCALOSINT_HOST=127.0.0.1
LOCALOSINT_PORT=8420
LOCALOSINT_SWEEP_INTERVAL_MINUTES=15

# Optional Enhanced Feeds
OPENSKY_USERNAME=
OPENSKY_PASSWORD=
AISSTREAM_API_KEY=
NASA_FIRMS_MAP_KEY=
NVD_API_KEY=

# Optional 3D Photorealistic Globe Tiles (Falls back to Keyless Esri World Imagery + OSM)
CESIUM_ION_TOKEN=

# Optional Alerting Channels (Crucix-Style Sweep-Delta Notifications)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=

# Optional Local LLM Endpoint
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b
```
