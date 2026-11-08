# 06 — DATA SOURCE AND INTEGRATION PLAN (`LocalOSINT v3.0`)

**Target Repository:** [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git)  
**Scope:** Complete specification of all 18 Live OSINT & Geospatial Connectors, Authentication Rules, Rate-Limit Budgets, Caching Policies, Telemetry Status Badges, Normalization Schemas, and Offline Bootstrap Fallbacks

---

## 1. Zero-Key-First Philosophy & Honest Telemetry Badges

A major architectural requirement of `LocalOSINT v3.0` (inspired by [`bilawalsidhu/gods-eye-view`](https://github.com/bilawalsidhu/gods-eye-view) and [`calesthio/Crucix`](https://github.com/calesthio/Crucix)) is that the platform must launch out-of-the-box with **zero API keys required** while immediately rendering live global intelligence across aviation, maritime, orbital satellites, natural disasters, cyber threats, sanctions, and public cameras.

Every layer and entity in the UI and API response must carry an explicit **Telemetry Status Badge (`telemetry_status`)**:
1. **`LIVE`**: Fetched from a real-time upstream API within the active TTL window (`< 5 min` for kinetic tracks, `< 15 min` for events).
2. **`DELAYED`**: Upstream source is live but delayed or serving from local SQLite TTL cache due to rate limiting.
3. **`ORBITAL_PROPAGATED`**: Satellite position mathematically propagated in real time via `SGP4` from the latest verified CelesTrak GP/TLE elements.
4. **`HISTORICAL`**: Replayed from the local SQLite `geo_tracks` archive via the 4D Time Scrubber.
5. **`OFFLINE_BOOTSTRAP`**: Loaded from `data/bootstrap/` when the machine has no outbound internet connectivity or an upstream endpoint is unreachable. **Never label offline bootstrap data as `LIVE`.**

---

## 2. Master Data-Source Catalog (18 Connectors)

| # | Connector Name | Category | Endpoint URL | Auth Required? | Polling / Cache TTL | Normalization Target |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **OpenSky Network** | Live Aviation | `https://opensky-network.org/api/states/all` | **No** (Optional OAuth2) | 30s (BBox) / 60s (Global) | `AIRCRAFT` entity + `geo_tracks` |
| **2** | **ADSB.lol** | Military & Global Aviation | `https://api.adsb.lol/v2/mil` & `/v2/lat/{lat}/lon/{lon}/dist/{nm}` | **No** | 30s | `AIRCRAFT` entity (`is_military=True`) + `geo_tracks` |
| **3** | **Digitraffic Marine AIS** | Live Maritime Vessels | `https://meri.digitraffic.fi/api/ais/v1/locations` | **No** | 60s | `VESSEL` entity + `geo_tracks` |
| **4** | **AISStream.io** | Global Maritime WebSocket | `wss://stream.aisstream.io/v0/stream` | Optional (`AISSTREAM_API_KEY`) | Streaming (5s batch flush) | `VESSEL` entity + `geo_tracks` |
| **5** | **CelesTrak GP/TLE** | Orbital Satellites | `https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json` | **No** | 6 hours (TLE cache); 1s `SGP4` tick | `SATELLITE` entity + `geo_tracks` |
| **6** | **The Space Devs (LL2)** | Rocket Launches | `https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=20` | **No** (15 req/hr free) | 30 min | `EVENT` (`LAUNCH`) + `LOCATION` |
| **7** | **US Treasury OFAC SDN** | Sanctions Cross-Ref | `https://www.treasury.gov/ofac/downloads/sdn.csv` | **No** | 24 hours (+ local bootstrap) | `SANCTIONED_ENTITY` + cross-ref index |
| **8** | **USGS Earthquakes** | Seismic Disasters | `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson` | **No** | 5 min | `EVENT` (`EARTHQUAKE`) + R*Tree point |
| **9** | **NASA EONET v3** | Wildfires, Storms, Volcanoes | `https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100` | **No** | 15 min | `EVENT` (`NATURAL_DISASTER`) + R*Tree |
| **10** | **NOAA NWS Alerts** | Severe Weather Polygons | `https://api.weather.gov/alerts/active` | **No** (`User-Agent` header) | 10 min | `EVENT` (`WEATHER_ALERT`) + Polygon |
| **11** | **Open-Meteo** | Local Weather Telemetry | `https://api.open-meteo.com/v1/forecast` | **No** | 15 min per queried coord | Enriches `LOCATION` / `EVENT` context |
| **12** | **Caltrans / DOT / OSM Cams** | Public Traffic/Weather Cams | `https://cwwp2.dot.ca.gov/data/d7/cctv/cctvStatusD07.json` + Overpass `man_made=surveillance` | **No** | 15 min | `CAMERA` entity + snapshot/stream URL |
| **13** | **GDELT GeoJSON v2** | Global Conflict & Crisis News | `https://api.gdeltproject.org/api/v2/geo/geo?query=...&format=geojson` | **No** | 15 min | `EVENT` (`CONFLICT_NEWS`) + `DOCUMENT` |
| **14** | **CISA KEV** | Exploited Vulnerabilities | `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` | **No** | 6 hours | `VULNERABILITY` + `ORGANIZATION` |
| **15** | **NIST NVD CVE v2** | CVE Vulnerability Intelligence | `https://services.nvd.nist.gov/rest/json/cves/2.0` | **No** (Optional API key) | 1 hour | `VULNERABILITY` |
| **16** | **CRT.sh & HackerTarget** | Certificate & DNS OSINT | `https://crt.sh/?q={domain}&output=json` | **No** | 1 hour per domain | `DOMAIN`, `IP_ADDRESS`, `CERTIFICATE` |
| **17** | **abuse.ch URLHaus** | Malware Distribution Infrastructure | `https://urlhaus-api.abuse.ch/v1/urls/recent/` | **No** | 30 min | `MALWARE_URL`, `DOMAIN`, `IP_ADDRESS` |
| **18** | **RDAP / Ipwho.is / Nominatim** | Network & Geocoding Enrichment | `https://rdap.org/`, `https://ipwho.is/`, `https://nominatim.openstreetmap.org/` | **No** | 24 hours per indicator | `IP_ADDRESS`, `ASN`, `LOCATION` |

---

## 3. Detailed Connector Implementation Specifications

### 3.1 Aviation Collector (`backend/collectors/aviation_adapter.py`)
- **Primary Upstream:** OpenSky Network `/api/states/all` (or bounding box `/api/states/all?lamin=...&lomin=...&lamax=...&lomax=...`) and ADSB.lol `/v2/mil` (military aircraft worldwide).
- **Extracted Fields:**
  - `icao24` (24-bit hex transponder address, canonical ID `aircraft:{icao24}`)
  - `callsign` (trimmed string, e.g., `RCH412`, `BAW117`)
  - `origin_country` (string)
  - `longitude`, `latitude` (WGS84 float)
  - `baro_altitude_m`, `geo_altitude_m` (float, meters)
  - `velocity_mps` (float, m/s), `true_track_deg` (0–360 float), `vertical_rate_mps` (float)
  - `squawk` (4-digit octal string; emergency squawks `7500` Hijack, `7600` Radio Failure, `7700` General Emergency automatically trigger a `HIGH` severity alert!)
  - `nav_integrity_cat` (`NIC` / `NACp` from ADSB.lol v2 when available): when multiple aircraft in a 50km hex cell report `NACp <= 4` or `NIC <= 4`, flag the cell as a **GPS/GNSS Interference Zone** (mirroring Argos Atlas's GPS jamming detection).
- **Sanctions Cross-Referencing:**
  - Every ingested `icao24` and `callsign`/registration tail number is looked up in O(1) time against the in-memory `SanctionsIndex` loaded by `sanctions_loader.py`. If matched, `is_sanctioned = True`, `sanction_program = row.program`, and a `SANCTION_MATCH_DETECTED` delta event is emitted.

### 3.2 Maritime Collector (`backend/collectors/maritime_adapter.py`)
- **Primary Upstream:**
  1. **Digitraffic Marine AIS (`https://meri.digitraffic.fi/api/ais/v1/locations`):** Keyless GeoJSON FeatureCollection of live vessel AIS reports.
  2. **AISStream.io (`wss://stream.aisstream.io/v0/stream`):** Optional global WebSocket feed when `AISSTREAM_API_KEY` is configured in the Vault or `.env`.
  3. **Offline/Regional Bootstrap (`data/bootstrap/maritime_bootstrap.json`):** Contains realistic historical snapshots of major global choke points (Strait of Hormuz, Bab el-Mandeb, Suez Canal, Taiwan Strait, Baltic Sea, English Channel) clearly tagged `telemetry_status="OFFLINE_BOOTSTRAP"` when live AIS for a non-European basin is unconfigured.
- **Extracted Fields:**
  - `mmsi` (9-digit Maritime Mobile Service Identity, canonical ID `vessel:{mmsi}`)
  - `imo` (7-digit IMO number when available)
  - `vessel_name`, `ship_type`, `flag_country` (derived from MMSI MID prefix digits 1–3)
  - `sog_knots` (Speed Over Ground), `cog_deg` (Course Over Ground), `heading_deg`, `nav_status`
- **Dark-Ship & Sanctions Analytics:**
  - Cross-references `mmsi`, `imo`, and normalized `vessel_name` against `SanctionsIndex` (`OFAC SDN`).
  - **AIS Dark-Ship Gap Detector:** If a tracked vessel previously moving at `sog_knots > 3.0` stops reporting for `> 2 hours` outside port and reappears `> 15 km` away, emit an `AIS_DARK_GAP` anomaly event.

### 3.3 Orbital Satellite Collector (`backend/collectors/satellite_adapter.py`)
- **Primary Upstream:** CelesTrak GP JSON (`https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json` or curated groups `stations`, `visual`, `military`, `weather`, `starlink`).
- **Real-Time SGP4 Propagation (`sgp4` library):**
  - Instead of polling an external API every second, `satellite_adapter.py` caches the GP/TLE orbital elements in SQLite for 6 hours and uses `sgp4.api.Satrec` to compute exact ECI $(x, y, z)$ and Geodetic WGS84 $(	ext{lat}, 	ext{lon}, 	ext{alt\_km}, 	ext{vel\_kms})$ at any timestamp $t$ (live or historical 4D scrubber time!).
  - Computes the satellite's **ground nadir sub-point**, **footprint horizon circle** ($R_{	ext{footprint}} = R_E rccos(rac{R_E}{R_E + h})$), and **90-minute future ground-track polyline**.

### 3.4 Public Camera Collector (`backend/collectors/camera_adapter.py`)
- **Primary Upstreams:**
  1. **Caltrans CCTV JSON (`https://cwwp2.dot.ca.gov/data/d7/cctv/cctvStatusD07.json`, `d4`, `d11`, `d12`)**: Keyless JSON providing camera coordinates, road name, direction, live JPEG snapshot URL (`currentImageURL`), and HLS stream URL (`streamingVideoURL`).
  2. **OpenStreetMap Overpass API (`node["man_made"="surveillance"]`)**: Queries public camera metadata within the active viewport bounding box (cached 24h per bbox tile).
  3. **Curated Global Public Webcams (`data/bootstrap/public_cameras.json`)**: Verified public DOT/port/weather camera endpoints across major world capitals, ports, and choke points.
- **Privacy Enforcement:** Public camera streams are strictly read-only infrastructure feeds; if an analyst sends a camera snapshot to the Visual Intelligence Studio (`M11`), automatic bystander face detection and blurring are applied by default.
