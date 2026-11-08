# TECHNOLOGY_AND_ALGORITHM_RESEARCH.md — Deep Research on 2D/3D Geospatial Engines, Orbital/Kinetic Telemetry, Privacy-Preserving Computer Vision & Spatiotemporal Correlation

## 1. 2D/3D Geospatial & Globe Rendering Engines

### 1.1 Candidate Comparison
| Engine | Rendering Tech | License | Key Strengths | Limitations | Role in LocalOSINT v3.0 |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **[MapLibre GL JS](https://maplibre.org/)** | WebGL Vector Tiles + Custom Shader Layers + `globe` projection (v4+) | BSD-3 | Ultra-fast 60 FPS rendering of 50,000+ GeoJSON points, clusters, heatmaps, and polygons; supports both flat 2D Mercator and 3D spherical globe projection with **zero API keys** using free vector/raster tiles (Esri World Imagery, OpenStreetMap, CARTO Dark Matter). | Less suited than CesiumJS for true 3D altitude orbital curtains without custom layers. | **Primary 2D Tactical Map & Fast Clustering Engine** |
| **[CesiumJS](https://cesium.com/platform/cesiumjs/)** / **[Globe.gl](https://globe.gl/)** | WebGL 3D Ellipsoid WGS84 Globe + 3D Tiles | Apache-2.0 / MIT | True 3D altitude rendering for aircraft flight levels, satellite orbits (350 km–35,786 km), 3D buildings, and optional Google Photorealistic 3D Tiles ([as used in God's Eye View](https://github.com/bilawalsidhu/gods-eye-view)). | Heavier bundle if not lazy-loaded. | **Primary 3D Orbital & Global Situation Globe** (synchronized camera state `[lat, lon, altitude, pitch, bearing]` with MapLibre 2D view) |

### 1.2 Keyless Basemap & Tile Strategy (Zero Mandatory API Keys)
Following the proven approach in [`bilawalsidhu/gods-eye-view`](https://github.com/bilawalsidhu/gods-eye-view):
1. **Default Satellite Layer (Keyless):** Esri World Imagery (`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`).
2. **Default Dark Tactical Vector/Raster Layer (Keyless):** OpenStreetMap / CARTO Dark Matter tiles.
3. **Optional "Power-Up" Photorealistic 3D Tiles:** Configurable in the encrypted `CryptoVault` for users who add a free personal **Cesium ion token** or **Google Maps 3D Tiles key**.

---

## 2. Orbital Mechanics, Aviation & Maritime Telemetry Algorithms

1. **Satellite Orbital Propagation (`SGP4` / `SDP4`):**
   - **Data Source:** [CelesTrak GP/TLE API](https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle) (keyless public access).
   - **Algorithm:** **Simplified General Perturbations-4 (SGP4)** (`sgp4` Python library on backend / `satellite.js` on frontend) propagates Two-Line Element (TLE) sets to any target timestamp $t$ (past, present, or future scrub), converting Earth-Centered Inertial (TEME) coordinates $(x, y, z, \dot{x}, \dot{y}, \dot{z})$ into WGS84 geodetic $(	ext{lat}, 	ext{lon}, 	ext{alt\_km}, 	ext{velocity\_kms})$ and computing the ground sensor footprint radius $r_{	ext{footprint}} = R_{\oplus} rccos\left(rac{R_{\oplus}}{R_{\oplus} + h}ight)$.
2. **Aviation Tracking & Sanctioned Tail/ICAO24 Cross-Referencing:**
   - **Data Sources:** [OpenSky Network REST API](https://github.com/debjit450/skywatch-live) (`https://opensky-network.org/api/states/all`) + [ADSB.lol Military & Point API](https://github.com/alkeincodes/gods-eye) (`https://api.adsb.lol/v2/mil`).
   - **Algorithm:** Normalizes 24-bit ICAO hex addresses (`icao24`), callsigns, barometric altitudes, ground speeds, and headings (`true_track`). Cross-references every active `icao24` and registration tail number in $O(1)$ hash-join time against our local SQLite **OpenSanctions / OFAC Sanctioned Aircraft Index**.
3. **Maritime AIS Tracking & Sanctioned Vessel Cross-Referencing:**
   - **Data Sources:** **Digitraffic Marine AIS REST/GeoJSON API** (`https://meri.digitraffic.fi/api/ais/v1/locations` — **100% keyless public REST API** providing real-time global/European vessel AIS positions) + optional **[AISStream.io](https://grokipedia.com/page/AISStreamio) WebSocket API** (`wss://stream.aisstream.io/v0/stream` with free GitHub login key).
   - **Algorithm:** Parses 9-digit **MMSI** (Maritime Mobile Service Identity), **IMO** ship number, vessel type, speed over ground (`SOG`), course over ground (`COG`), and navigational status. Cross-references `MMSI` and `IMO` against the **OpenSanctions / OFAC Maritime Sanctions List**, and detects **Dark-Ship / Loitering Anomalies** (SOG $< 1.5	ext{ knots}$ offshore for $>4	ext{ hours}$ or unexpected AIS gap $>2	ext{ hours}$).

---

## 3. Privacy-Preserving Visual Intelligence & Computer Vision Research

To satisfy Requirement 1 & 3.C (*"facial detection, image quality analysis, face blurring, deduplication in user-provided datasets, and identity verification or matching only for explicitly enrolled and consenting individuals"*):

### 3.1 Candidate Computer Vision Models & Libraries Evaluated

| CV Task | Selected Algorithm / Model | Execution Engine & Footprint | Why Selected & Accuracy / Limitations |
| :--- | :--- | :--- | :--- |
| **1. Face Detection & 5-Point Landmarks** | **[OpenCV `YuNet` (`face_detection_yunet_2023mar.onnx`)](https://huggingface.co/opencv/face_detection_yunet)** + Haar/HOG fallback | `cv2.FaceDetectorYN` / `onnxruntime` (**Only 330 KB model weight!**, `<8 ms` per image on CPU) | 88.7% AP on WIDER FACE hard set while being 100× smaller than RetinaFace-ResNet50; runs natively in `opencv-python` (`4.11.0` pre-installed) and `onnxruntime`. |
| **2. Automatic Bystander Face Blurring (Privacy Redaction)** | **Elliptical Feather-Masked Gaussian Blur ($\sigma = 25$) & Pixelation Mosaic** over detected `YuNet` bounding boxes | `opencv-python` + `Pillow` (`<3 ms` per image) | Allows analysts to redact all faces (or all non-consented faces) before saving or exporting visual evidence into reports. |
| **3. Image Quality & Forensics Assessment (IQA)** | **Laplacian Variance (Sharpness/Blur)** + **Brenner Gradient** + **Shannon Histogram Entropy (Exposure/Contrast)** + **Face Resolution Check ($\ge 64	imes 64$ px)** | `numpy` + `opencv-python` (`<4 ms` per image) | Automatically warns the analyst when a face crop or evidence image is too blurry ($	ext{Var}(
abla^2 I) < 80$) or too low-resolution ($<50	ext{ px}$ inter-ocular distance) for reliable comparison, preventing false-positive AI claims. |
| **4. Consented-Gallery Face Verification (1:1 & 1:$N$ Enrolled Only)** | **[OpenCV `SFace` (`face_recognition_sface_2021dec.onnx`)](https://github.com/panahandeh79/ArcFace-YuNet)** / **[InsightFace `ArcFace` MobileFaceNet ONNX](https://github.com/deepinsight/insightface)** (5-point similarity transform alignment $ightarrow$ L2-normalized 128-d/512-d embedding $ightarrow$ Cosine similarity) | `cv2.FaceRecognizerSF` / `onnxruntime` (~36 MB weight, `<15 ms` on CPU) | **Strict Ethical Gate:** Enforces a mandatory `consent_attestation` database record (`consented_face_gallery`) before enrollment. Outputs calibrated cosine similarity ($\ge 0.363$ threshold for `SFace` at FAR $10^{-3}$) and explicitly warns when image quality is below threshold. |
| **5. Duplicate & Near-Duplicate Image Detection** | **64-bit Perceptual DCT Hash (`pHash`)** + **Difference Gradient Hash (`dHash`)** + **Average Hash (`aHash`)** + **SHA-256 Exact Hash** | Pure `numpy` / `scipy.fftpack.dct` (`<2 ms` per image) | Detects cropped, resized, re-compressed (JPEG), or watermarked duplicates across an investigation when Hamming distance $d_H(	ext{pHash}_1, 	ext{pHash}_2) \le 8$. |
| **6. Visual Provenance & Metadata Extraction** | **EXIF GPS/Camera Parser (`Pillow`) + XMP/IPTC + C2PA Content Credentials JUMBF Box Detector + Error Level Analysis (ELA)** | `Pillow` + `numpy` | Extracts GPS coordinates (plotting the photo directly onto the 2D/3D global map), camera serial/model, capture timestamps, C2PA cryptographic manifest presence, and JPEG re-compression ELA heatmaps. |

---

## 4. Crucix-Inspired Sweep-Delta & Spatiotemporal Correlation Algorithms

### 4.1 Mathematical Formulation of the Sweep-Delta Engine
Every scheduled or manual collection sweep $s_t$ for source $c$ produces a normalized set of keyed records $R_t = \{r_1, \dots, r_m\}$. Comparing $R_t$ against the most recent prior snapshot $R_{t-1}$ yields four disjoint delta sets in $O(|R_t| + |R_{t-1}|)$ time:
1. **$\Delta_{	ext{NEW}} = \{r \in R_t \mid r.	ext{key} 
otin R_{t-1}\}$:** Newly detected aircraft, vessels, earthquakes, fires, CVEs, or news events.
2. **$\Delta_{	ext{ESCALATED}} = \{r \in R_t \cap R_{t-1} \mid 	ext{severity}(r_t) > 	ext{severity}(r_{t-1}) \lor 	ext{entered\_geofence}(r_t)\}$:** Events whose magnitude/risk increased or moving assets that crossed into a watched polygon.
3. **$\Delta_{	ext{DEESCALATED}} = \{r \in R_t \cap R_{t-1} \mid 	ext{severity}(r_t) < 	ext{severity}(r_{t-1})\}$:** Subsiding alerts.
4. **$\Delta_{	ext{VANISHED}} = \{r \in R_{t-1} \mid r.	ext{key} 
otin R_t\}$:** Transponders or beacons that went dark within an active watch zone.

### 4.2 Spatiotemporal Cross-Source Event Correlation (Avoiding False Causation)
When an analyst selects a geographic region (or clicks an event at $(\phi_0, \lambda_0, t_0)$), the **Spatiotemporal Correlator** queries the SQLite `spatial_rtree` and `timeline_events` tables to compute a composite **Spatiotemporal & Graph Proximity Score** $S_{	ext{corr}}(e_1, e_2) \in [0, 1]$:
$$S_{	ext{corr}}(e_1, e_2) = w_{	ext{spatial}} \exp\left(-rac{d_{	ext{Haversine}}(e_1, e_2)}{D_0}ight) + w_{	ext{temporal}} \exp\left(-rac{|t_1 - t_2|}{T_0}ight) + w_{	ext{semantic}} 	ext{sim}_{	ext{RRF}}(e_1, e_2) + w_{	ext{graph}} \mathbb{I}_{	ext{path}(e_1, e_2) \le 2}$$
- **Strict Epistemic Labeling (No False Causation):** Any link created purely by spatiotemporal proximity ($d_{	ext{Haversine}} \le 25	ext{ km}, \Delta t \le 6	ext{h}$) without shared identifiers or direct source attribution is strictly labeled `epistemic_status = "SPATIOTEMPORAL_COINCIDENCE"` (*"Co-located in space and time — verify whether causally related"*), never presented as confirmed causation.
