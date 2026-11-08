# M09 — 4D Spatiotemporal Analytics, SGP4 Orbit Propagator & Anomaly Detection

- **Target File:** `backend/core/spatiotemporal.py`
- **Action:** Retain HDBSCAN clustering and Kleinberg burst detection; add:
  1. `propagate_satellite_tle(line1, line2, target_dt_utc)` using `sgp4.api.Satrec` + GMST conversion to WGS84 `(lat, lon, alt_km, velocity_kms, footprint_radius_km)`.
  2. `detect_maritime_dark_gaps(tracks)` and `detect_sts_rendezvous(vessel_tracks)` for maritime anomaly detection.
  3. `compute_gps_interference_zones(aircraft_states)` aggregating low-`NACp` aircraft reports into GeoJSON hex polygons.
