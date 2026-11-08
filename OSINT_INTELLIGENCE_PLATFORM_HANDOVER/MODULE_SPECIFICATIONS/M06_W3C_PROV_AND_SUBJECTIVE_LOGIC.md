# M06 — W3C PROV-DM Lineage & Josang Subjective Logic Fusion

- **Target File:** `backend/core/provenance_fusion.py`
- **Action:** Retain existing Josang Subjective Logic cumulative ($\oplus$) and averaging ($	ilde{\oplus}$) fusion operators and NATO Admiralty (`A1`–`F6`) reliability mapping. Ensure all new geospatial collectors (`OpenSky`, `ADSB.lol`, `Digitraffic AIS`, `CelesTrak`, `USGS`, `NASA EONET`, `NOAA`, `OFAC SDN`) are registered in `sources` with appropriate Admiralty ratings (`A1` for `OFAC SDN`, `USGS`, `NOAA`, `CelesTrak`; `B2` for `OpenSky`, `Digitraffic AIS`, `ADSB.lol`).
