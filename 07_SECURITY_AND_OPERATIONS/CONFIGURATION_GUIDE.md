# CONFIGURATION_GUIDE.md — Environment Variables, Application Settings & Connector Tuning

## 1. Environment Variables (`.env` / `.env.example`)
All environment variables are optional and have safe local defaults:

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `LOCALOSINT_HOST` | `127.0.0.1` | Local bind address (keep `127.0.0.1` for single-machine security). |
| `LOCALOSINT_PORT` | `8000` | Local TCP port for FastAPI and Workstation UI. |
| `LOCALOSINT_DATA_DIR` | `./data` | Directory storing SQLite database, vault key, and logs. |
| `LOCALOSINT_DB_PATH` | `./data/localosint.db` | Path to SQLite 3 WAL database file. |
| `LOCALOSINT_SECRET_KEY` | *(Auto-generated in `data/.vault_key`)* | Custom passphrase for Fernet API Key Vault encryption. |
| `LOCALOSINT_OLLAMA_URL` | `http://127.0.0.1:11434` | Optional local Ollama server endpoint. |
| `LOCALOSINT_OLLAMA_MODEL` | `llama3.1:8b` | Default local Ollama model tag when AI provider is set to `ollama`. |

---

## 2. Runtime Database Settings (`app_settings` Table)
Editable live via `PUT /api/settings` or View 11 in the UI:
- `opsec_mode`: `"STANDARD"` or `"PASSIVE_ONLY"` (blocks direct HTTP connections to target web servers).
- `offline_mode`: `"false"` or `"true"` (disables all outbound network requests and uses cached/local analysis).
- `ai_provider`: `"local_graphrag"` (default deterministic CPU compiler) or `"ollama"`.
- `staging_threshold`: `"50"` (maximum child entities auto-promoted to visual graph per collector run before staging).
- `user_agent`: `"LocalOSINT-Workstation/2.0 (Defensive-Research; +http://localhost:8000)"`.
