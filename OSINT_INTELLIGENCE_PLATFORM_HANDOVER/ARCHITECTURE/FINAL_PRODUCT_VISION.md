# FINAL_PRODUCT_VISION.md — The Unified Global Intelligence Command Centre (`LocalOSINT v3.0`)

## 1. Executive Product Vision
**LocalOSINT v3.0** combines the live multi-domain crisis and sanctions-flagged asset map of **Argos Atlas**, the autonomous 15-minute **Sweep-Delta** and two-way Telegram/Discord alerting engine of **Crucix**, the keyless 2D/3D orbital/aviation/camera globe of **God's Eye View**, and a **Privacy-Preserving Visual Intelligence & Probabilistic Graph Workstation**—all running locally on a consumer Windows 11 PC (~16 GB RAM, CPU-only) inside [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git).

---

## 2. Core User Workflows (What Opening the Application Feels Like)

### Workflow 1: Global Operational Picture & Region-Box Intelligence Dive
1. The analyst launches `start.bat` (`http://127.0.0.1:8000`). The workstation opens directly into the **Global Command Centre**: a full-viewport interactive **2D/3D Map & Globe** flanked by a **Collapsible Layer Manager (left)**, a **Live Sweep-Delta & Intelligence Ticker (top/bottom)**, and a **Context Inspector & AI Analyst Dock (right)**.
2. The analyst toggles on live layers: **Aviation (`OpenSky` + `ADSB.lol` military)**, **Maritime (`Digitraffic` / `AISStream`)**, **Satellites (`CelesTrak SGP4`)**, **Earthquakes (`USGS`)**, **Wildfires (`NASA EONET/FIRMS`)**, **Severe Weather (`NOAA` / `Open-Meteo`)**, **Public Cameras (`DOT / OSM`)**, and **Global News (`GDELT 2.0`)**.
3. The analyst draws a **Region Bounding Box / Polygon** (e.g., around the Red Sea, Taiwan Strait, or a major port) and clicks **"Analyze Region"**:
   - The **Region Intelligence Drawer** immediately lists all aircraft, vessels (highlighting any **OpenSanctions/OFAC-flagged hulls** in crimson), overhead satellites with their ground footprint cones, nearby public traffic/port cameras, infrastructure entities, and news articles inside that polygon.
   - The **Spatiotemporal Correlator** highlights co-occurring anomalies (e.g., a sanctioned vessel whose AIS speed dropped to 0.5 knots within 15 km of an undersea cable or port event), explicitly badged with its provenance, timestamp, and epistemic status.

### Workflow 2: Autonomous Sweep-Delta Monitoring & Geofence Alerting
1. The background **Sweep Scheduler** polls configured feeds on a user-selectable interval (e.g., every 15 minutes, or on-demand via the **"Run Sweep Now"** button).
2. The **Sweep-Delta Panel** displays a structured diff: `+4 New Military Flights`, `+1 Escalated M5.4 Earthquake`, `+2 Sanctioned Vessels Entered Watchbox Alpha`.
3. When a rule in the **Alerting Engine** triggers (e.g., *"Alert if any OFAC-sanctioned vessel or M5.0+ earthquake occurs inside Polygon Alpha"*), the platform logs a persistent alert in the UI and optionally dispatches a formatted Markdown alert with source links to the user's configured **Telegram Bot, Discord Webhook, or SMTP Email**.

### Workflow 3: Privacy-Preserving Visual Intelligence & Geolocation Verification
1. The analyst switches to the **Visual Intelligence Studio** tab (or drags an image/frame captured from a public event or camera directly into the inspector).
2. The engine automatically:
   - Extracts **EXIF GPS coordinates**, camera model, timestamps, C2PA manifest status, and **Error Level Analysis (ELA)** compression anomalies, plotting geolocated photos onto the global map.
   - Computes **64-bit `pHash` and `dHash`** perceptual fingerprints, checking the workspace for cropped, resized, or watermarked duplicates.
   - Runs **OpenCV `YuNet` ONNX Face Detection** and **Image Quality Assessment (Laplacian sharpness + face resolution)**:
     - Offers one-click **"Blur All Faces / Bystander Privacy Redaction"** before saving or exporting evidence.
     - Allows 1:$N$ face verification (`SFace` ONNX) **strictly against the local `consented_face_gallery` table** (requiring an explicit consent record and displaying a quality warning if the image is blurry).

### Workflow 4: Deep Link Analysis, Entity Resolution & Evidence-Backed Briefings
1. Clicking **"Pivot to Graph"** on any vessel, aircraft, company, domain, or IP transitions seamlessly into the **Relationship Graph & Fellegi-Sunter EM Entity Resolution View** (built on the proven `M02`/`M05`/`M06`/`M07` foundation already in `Manan7289/OSINT.git`).
2. The analyst asks the **AI Intelligence Assistant**: *"Summarize all activity and infrastructure changes in Watchbox Alpha over the last 24 hours."* The GraphRAG engine compiles a regional briefing separating **Observed Facts (`[ev_id]`)**, **Corroborated Facts**, **Spatiotemporal Coincidences**, and **Inferences**.

---

## 3. Mandatory Data-Freshness & Honesty Badges
Every marker on the map and every card in the feed MUST display one of five explicit telemetry badges:
- **`[LIVE_STREAM]`** (Real-time API/WebSocket capture `< 5 min` old, e.g., live OpenSky, Digitraffic AIS, USGS, CelesTrak)
- **`[DELAYED_FEED]`** (Periodic public feed `5 min – 24 hr` old, e.g., NASA FIRMS satellite pass, GDELT news)
- **`[ORBITAL_PROPAGATED]`** (Mathematically propagated from authoritative CelesTrak TLE via `SGP4`)
- **`[HISTORICAL_ARCHIVE]`** (Replayed from SQLite `spatiotemporal_tracks` or Wayback CDX)
- **`[OFFLINE_BOOTSTRAP]`** (Bundled fallback/cached snapshot used when internet connectivity is disabled or an upstream API is unreachable — never misrepresented as live traffic)
