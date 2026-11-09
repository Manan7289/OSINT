/**
 * frontend/assets/globe_map.js - Dual 2D Tactical Map & 3D Orbital Globe Engine
 * LocalOSINT v3.0 Global Intelligence Command Centre
 */

class GlobeMapEngine {
  constructor() {
    this.currentMode = '2D'; // '2D' or '3D'
    this.map2D = null;
    this.globe3D = null;
    this.layersData = {
      features: [],
      timestamp: null
    };
    this.activeLayers = {
      AIRCRAFT: true,
      MILITARY_AIRCRAFT: true,
      VESSEL: true,
      SATELLITE: true,
      EARTHQUAKE: true,
      CAMERA: true,
      GPS_JAMMING: true,
      GEOFENCES: true
    };
    this.filterMode = 'ALL';
    this.maxAltitudeFilter = 60000;
    this.minSpeedFilter = 0;
    this.proximityCircle = null;
    this.markerGroups = {};
    this.kineticMap = new Map();
    this.geofenceLayerGroup = null;
    this.satellitesTimer = null;
    this.telemetryTimer = null;
    this.kineticAnimTimer = null;
    this.currentCenter = [20.0, 0.0];
    this.currentZoom = 3;
    
    this.regionPresets = {
      GLOBAL: { center: [20.0, 0.0], zoom: 2.5 },
      HORMUZ: { center: [26.56, 56.25], zoom: 8 },
      TAIWAN: { center: [24.0, 121.0], zoom: 7.5 },
      REDSEA: { center: [13.5, 42.7], zoom: 7 },
      BLACKSEA: { center: [44.5, 34.0], zoom: 6.5 },
      NORAM: { center: [38.0, -97.0], zoom: 4.5 },
      INDIA: { center: [19.0, 78.0], zoom: 5 }
    };
  }

  init() {
    this.init2DMap();
    this.init3DGlobe();
    this.initEventListeners();
    this.fetchLayers();
    this.fetchAndRenderGeofences();
    this.startLiveSatelliteLoop();
    this.startLiveTelemetryLoop();
    this.startKineticAnimationLoop();
  }

  init2DMap() {
    const mapEl = document.getElementById('map-2d');
    if (!mapEl || typeof L === 'undefined') return;

    this.map2D = L.map('map-2d', {
      center: this.currentCenter,
      zoom: this.currentZoom,
      zoomControl: false,
      attributionControl: false
    });

    // Dark base layer (CartoDB Dark Matter)
    const darkTileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      subdomains: 'abcd'
    });

    // Satellite imagery layer (Esri World Imagery)
    const satTileLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19
    });

    satTileLayer.addTo(this.map2D);

    // Layer control toggle if needed
    L.control.zoom({ position: 'bottomright' }).addTo(this.map2D);

    // Initialize layer groups
    this.markerGroups = {
      AIRCRAFT: L.layerGroup().addTo(this.map2D),
      VESSEL: L.layerGroup().addTo(this.map2D),
      SATELLITE: L.layerGroup().addTo(this.map2D),
      EARTHQUAKE: L.layerGroup().addTo(this.map2D),
      CAMERA: L.layerGroup().addTo(this.map2D),
      GPS_JAMMING: L.layerGroup().addTo(this.map2D)
    };
    this.geofenceLayerGroup = L.layerGroup().addTo(this.map2D);

    // Update coordinates on move
    this.map2D.on('moveend', () => {
      const center = this.map2D.getCenter();
      this.currentCenter = [center.lat, center.lng];
      this.currentZoom = this.map2D.getZoom();
      this.updateCoordDisplay(center.lat, center.lng, this.currentZoom);
    });

    this.map2D.on('mousemove', (e) => {
      this.updateCursorCoordDisplay(e.latlng.lat, e.latlng.lng);
    });
  }

  init3DGlobe() {
    const globeEl = document.getElementById('globe-3d');
    if (!globeEl || typeof Globe === 'undefined') return;

    try {
      this.globe3D = Globe()
        (globeEl)
        .globeImageUrl('//unpkg.com/three-globe/example/img/earth-night.jpg')
        .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
        .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
        .pointOfView({ lat: this.currentCenter[0], lng: this.currentCenter[1], altitude: 2.2 });
    } catch (e) {
      console.warn("Globe.gl 3D initialization fallback to 2D:", e);
    }
  }

  switchMode(mode) {
    this.currentMode = mode;
    const map2DEl = document.getElementById('map-2d');
    const globe3DEl = document.getElementById('globe-3d');
    const btn2D = document.getElementById('btn-mode-2d');
    const btn3D = document.getElementById('btn-mode-3d');

    if (mode === '3D') {
      if (map2DEl) map2DEl.classList.add('hidden');
      if (globe3DEl) {
        globe3DEl.classList.remove('hidden');
        if (this.globe3D) {
          this.globe3D.pointOfView({
            lat: this.currentCenter[0],
            lng: this.currentCenter[1],
            altitude: Math.max(0.6, 3.5 / this.currentZoom)
          }, 600);
          this.render3DGlobeData();
        }
      }
      if (btn2D) btn2D.classList.remove('active');
      if (btn3D) btn3D.classList.add('active');
    } else {
      if (globe3DEl) globe3DEl.classList.add('hidden');
      if (map2DEl) {
        map2DEl.classList.remove('hidden');
        if (this.map2D) {
          this.map2D.invalidateSize();
          this.map2D.setView(this.currentCenter, this.currentZoom);
        }
      }
      if (btn3D) btn3D.classList.remove('active');
      if (btn2D) btn2D.classList.add('active');
    }
  }

  flyToPreset(presetKey) {
    const preset = this.regionPresets[presetKey];
    if (!preset) return;
    this.currentCenter = preset.center;
    this.currentZoom = preset.zoom;

    if (this.currentMode === '2D' && this.map2D) {
      this.map2D.flyTo(preset.center, preset.zoom, { duration: 1.2 });
    } else if (this.globe3D) {
      this.globe3D.pointOfView({
        lat: preset.center[0],
        lng: preset.center[1],
        altitude: Math.max(0.5, 3.5 / preset.zoom)
      }, 1200);
    }
  }

  flyToCoords(lat, lon, zoom = 10) {
    this.currentCenter = [lat, lon];
    this.currentZoom = zoom;
    if (this.currentMode === '2D' && this.map2D) {
      this.map2D.flyTo([lat, lon], zoom, { duration: 1.0 });
    } else if (this.globe3D) {
      this.globe3D.pointOfView({ lat, lng: lon, altitude: 0.8 }, 1000);
    }
  }

  async fetchLayers(sinceIso = null) {
    try {
      const url = sinceIso 
        ? `/api/v1/geospatial/layers?since=${encodeURIComponent(sinceIso)}`
        : '/api/v1/geospatial/layers';
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch layers");
      const data = await res.json();
      this.layersData = data;
      this.renderLayers();
      this.updateLayerCounters();
    } catch (err) {
      console.error("Error fetching geospatial layers:", err);
    }
  }

  renderLayers() {
    if (!this.map2D) return;

    // Clear existing markers and kinetic tracking cache
    Object.values(this.markerGroups).forEach(group => group.clearLayers());
    this.kineticMap.clear();

    const features = this.layersData.features || [];

    features.forEach(f => {
      const geom = f.geometry;
      const props = f.properties || {};
      const layerType = props.layer_type;

      // Filter based on active toggles
      if (layerType === 'AIRCRAFT' && props.is_military && !this.activeLayers.MILITARY_AIRCRAFT) return;
      if (layerType === 'AIRCRAFT' && !props.is_military && !this.activeLayers.AIRCRAFT) return;
      if (layerType === 'VESSEL' && !this.activeLayers.VESSEL) return;
      if (layerType === 'SATELLITE' && !this.activeLayers.SATELLITE) return;
      if (layerType === 'EARTHQUAKE' && !this.activeLayers.EARTHQUAKE) return;
      if (layerType === 'CAMERA' && !this.activeLayers.CAMERA) return;
      if (layerType === 'GPS_JAMMING' && !this.activeLayers.GPS_JAMMING) return;

      // Quick filter check
      if (this.filterMode === 'MILITARY' && !props.is_military) return;
      if (this.filterMode === 'SANCTIONED' && !props.is_sanctioned) return;
      if (this.filterMode === 'AIR' && layerType !== 'AIRCRAFT') return;
      if (this.filterMode === 'SEA' && layerType !== 'VESSEL') return;

      // Sliders check: max altitude and min speed
      if (props.altitude_m != null && (props.altitude_m * 3.28084) > this.maxAltitudeFilter) return;
      if (props.speed_kts != null && props.speed_kts < this.minSpeedFilter) return;

      if (geom.type === 'Point') {
        const [lon, lat] = geom.coordinates;
        if (lat == null || lon == null) return;
        const marker = this.createEntityMarker(lat, lon, props);
        if (marker) {
          const targetGroup = this.markerGroups[layerType] || this.markerGroups.AIRCRAFT;
          targetGroup.addLayer(marker);
        }
      } else if (geom.type === 'Polygon' && layerType === 'GPS_JAMMING') {
        // Draw GPS Interference polygon
        const latLngs = geom.coordinates[0].map(c => [c[1], c[0]]);
        const poly = L.polygon(latLngs, {
          color: props.severity === 'CRITICAL' ? '#EF4444' : '#F59E0B',
          fillColor: props.severity === 'CRITICAL' ? '#EF4444' : '#F59E0B',
          fillOpacity: 0.22,
          weight: 2,
          dashArray: '4, 4'
        }).bindPopup(`<b>${props.display_label}</b><br>NACp: ${props.avg_nacp} | Affected: ${props.aircraft_count}`);
        this.markerGroups.GPS_JAMMING.addLayer(poly);
      }
    });

    if (this.currentMode === '3D') {
      this.render3DGlobeData();
    }
  }

  createEntityMarker(lat, lon, props) {
    const isSanctioned = Boolean(props.is_sanctioned);
    const isMilitary = Boolean(props.is_military);
    const layerType = props.layer_type;
    const heading = parseFloat(props.heading != null ? props.heading : 0);

    let iconHtml = '';
    let markerClass = 'tactical-marker';

    if (isSanctioned) {
      markerClass += ' marker-sanctioned';
      iconHtml = `<div class="marker-pulse-crimson" title="OFAC SANCTIONED: ${props.display_label || props.callsign_or_name}"><span class="marker-icon">⛔</span></div>`;
    } else if (layerType === 'AIRCRAFT') {
      const color = isMilitary ? '#F59E0B' : '#38BDF8';
      iconHtml = `<div class="marker-plane" style="transform: rotate(${heading}deg); color: ${color};">✈</div>`;
    } else if (layerType === 'VESSEL') {
      iconHtml = `<div class="marker-vessel">
        <span class="vessel-arrow" style="transform: rotate(${heading}deg);">▲</span>
      </div>`;
    } else if (layerType === 'SATELLITE') {
      iconHtml = `<div class="marker-satellite" style="color: #A855F7;">◈</div>`;
    } else if (layerType === 'EARTHQUAKE') {
      const mag = props.metadata ? props.metadata.magnitude || 4.5 : 4.5;
      const size = Math.min(32, Math.max(12, mag * 4));
      iconHtml = `<div class="marker-quake" style="width:${size}px; height:${size}px; background: rgba(249,115,22,0.4); border: 2px solid #F97316; border-radius: 50%;"></div>`;
    } else if (layerType === 'CAMERA') {
      iconHtml = `<div class="marker-cam" style="color: #22D3EE;">📷</div>`;
    } else {
      iconHtml = `<div class="marker-default">●</div>`;
    }

    const customIcon = L.divIcon({
      html: iconHtml,
      className: markerClass,
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });

    const marker = L.marker([lat, lon], { icon: customIcon });

    // Interactive tooltip
    const speedStr = props.speed_kts ? `${Math.round(props.speed_kts)} kts` : 'Stationary';
    const altStr = props.altitude_m ? `${Math.round(props.altitude_m)}m` : 'Surface';
    marker.bindTooltip(
      `<div style="font-weight:700; color:#38BDF8;">${props.display_label || props.callsign_or_name || 'Asset'}</div>` +
      `<div style="font-size:10px; color:#94A3B8;">${props.layer_type} · ${speedStr} · ${altStr} · ${Math.round(heading)}°</div>`,
      { className: 'tactical-tooltip', direction: 'top', offset: [0, -12] }
    );

    marker.on('click', () => {
      this.renderProximityCircle(lat, lon, 50);
      if (window.app && window.app.selectEntityWithProximity) {
        window.app.selectEntityWithProximity(props, lat, lon);
      } else if (window.app && window.app.selectEntity) {
        window.app.selectEntity(props, lat, lon);
      }
    });

    // Register kinetic tracking for forward dead reckoning
    const velMps = props.velocity_mps || (props.speed_kts ? props.speed_kts * 0.514444 : 0);
    if (velMps > 1.0 && (layerType === 'AIRCRAFT' || layerType === 'VESSEL')) {
      const trackId = props.track_id || `${props.entity_id}_${lat}_${lon}`;
      this.kineticMap.set(trackId, {
        marker,
        lat: parseFloat(lat),
        lon: parseFloat(lon),
        heading,
        velocity_mps: velMps,
        lastExtrapolated: performance.now()
      });
    }

    return marker;
  }

    return marker;
  }

  renderProximityCircle(lat, lon, radiusKm = 50) {
    this.clearProximityCircle();
    if (!this.map2D || typeof L === 'undefined') return;
    this.proximityCircle = L.circle([lat, lon], {
      radius: radiusKm * 1000,
      color: '#38BDF8',
      fillColor: '#38BDF8',
      fillOpacity: 0.08,
      weight: 1.5,
      dashArray: '6, 6'
    }).addTo(this.map2D);
  }

  clearProximityCircle() {
    if (this.proximityCircle && this.map2D) {
      this.map2D.removeLayer(this.proximityCircle);
      this.proximityCircle = null;
    }
  }

  async fetchAndRenderGeofences() {
    if (!this.map2D || !this.geofenceLayerGroup) return;
    try {
      const res = await fetch('/api/v1/geofences');
      if (res.ok) {
        const zones = await res.json();
        this.geofenceLayerGroup.clearLayers();
        zones.forEach(z => {
          let poly = z.polygon_geojson;
          if (typeof poly === 'string') {
            try { poly = JSON.parse(poly); } catch (e) { poly = null; }
          }
          if (poly && poly.coordinates) {
            const latLngs = poly.coordinates[0].map(c => [c[1], c[0]]);
            const lPoly = L.polygon(latLngs, {
              color: '#38BDF8',
              fillColor: '#38BDF8',
              fillOpacity: 0.12,
              weight: 2,
              dashArray: '5, 5'
            }).bindTooltip(`<b>⬟ ${z.name}</b><br>Severity: ${z.min_severity}`, { sticky: true });
            this.geofenceLayerGroup.addLayer(lPoly);
          }
        });
      }
    } catch (e) {
      console.warn("Could not load geofences for map:", e);
    }
  }

  render3DGlobeData() {
    if (!this.globe3D) return;
    const features = this.layersData.features || [];
    const pointsData = [];

    features.forEach(f => {
      if (f.geometry && f.geometry.type === 'Point') {
        const [lng, lat] = f.geometry.coordinates;
        const p = f.properties || {};
        let color = '#38BDF8';
        if (p.is_sanctioned) color = '#EF4444';
        else if (p.is_military) color = '#F59E0B';
        else if (p.layer_type === 'VESSEL') color = '#10B981';
        else if (p.layer_type === 'SATELLITE') color = '#A855F7';
        else if (p.layer_type === 'EARTHQUAKE') color = '#F97316';

        pointsData.push({
          lat,
          lng,
          size: p.layer_type === 'SATELLITE' ? 0.35 : 0.2,
          color,
          name: p.display_label || p.callsign_or_name || 'Asset',
          props: p
        });
      }
    });

    this.globe3D
      .pointsData(pointsData)
      .pointAltitude(d => d.props.layer_type === 'SATELLITE' ? 0.25 : 0.02)
      .pointColor('color')
      .pointRadius('size')
      .onPointClick(point => {
        if (window.app && window.app.selectEntity) {
          window.app.selectEntity(point.props, point.lat, point.lng);
        }
      });
  }

  updateLayerCounters() {
    const features = this.layersData.features || [];
    const counts = {
      AIRCRAFT: 0,
      MILITARY_AIRCRAFT: 0,
      VESSEL: 0,
      SATELLITE: 0,
      EARTHQUAKE: 0,
      CAMERA: 0,
      GPS_JAMMING: 0,
      SANCTIONS: 0
    };

    features.forEach(f => {
      const p = f.properties || {};
      const t = p.layer_type;
      if (p.is_sanctioned) counts.SANCTIONS++;
      if (t === 'AIRCRAFT') {
        if (p.is_military) counts.MILITARY_AIRCRAFT++;
        else counts.AIRCRAFT++;
      } else if (counts[t] !== undefined) {
        counts[t]++;
      }
    });

    const setCounter = (id, count) => {
      const el = document.getElementById(id);
      if (el) el.textContent = count.toLocaleString();
    };

    setCounter('count-aircraft', counts.AIRCRAFT);
    setCounter('count-military', counts.MILITARY_AIRCRAFT);
    setCounter('count-vessels', counts.VESSEL);
    setCounter('count-satellites', counts.SATELLITE);
    setCounter('count-quakes', counts.EARTHQUAKE);
    setCounter('count-cameras', counts.CAMERA);
    setCounter('count-jamming', counts.GPS_JAMMING);
    setCounter('count-sanctions', counts.SANCTIONS);
  }

  toggleLayer(layerKey, isChecked) {
    this.activeLayers[layerKey] = isChecked;
    this.renderLayers();
  }

  startLiveSatelliteLoop() {
    if (this.satellitesTimer) clearInterval(this.satellitesTimer);
    // Poll satellite positions every 15s to propagate orbital step
    this.satellitesTimer = setInterval(async () => {
      if (!this.activeLayers.SATELLITE) return;
      try {
        const res = await fetch('/api/v1/geospatial/satellites');
        if (res.ok) {
          const sats = await res.json();
          // Merge satellite points into current layer view
          if (this.markerGroups.SATELLITE) {
            this.markerGroups.SATELLITE.clearLayers();
            sats.forEach(s => {
              if (s.lat != null && s.lon != null) {
                const marker = this.createEntityMarker(s.lat, s.lon, {
                  layer_type: 'SATELLITE',
                  display_label: `${s.satellite_name} (${s.norad_cat_id})`,
                  callsign_or_name: s.satellite_name,
                  altitude_m: (s.alt_km || 0) * 1000,
                  speed_kts: (s.velocity_kms || 0) * 1943.84,
                  telemetry_status: 'SGP4',
                  source_network: 'CelesTrak SGP4',
                  metadata: s
                });
                if (marker) this.markerGroups.SATELLITE.addLayer(marker);
              }
            });
          }
        }
      } catch (e) {
        console.debug("Satellite background step:", e);
      }
    }, 15000);
  }

  startLiveTelemetryLoop() {
    if (this.telemetryTimer) clearInterval(this.telemetryTimer);
    // Refresh live aviation and maritime tracks every 12 seconds
    this.telemetryTimer = setInterval(async () => {
      await this.fetchLayers();
    }, 12000);
  }

  startKineticAnimationLoop() {
    if (this.kineticAnimTimer) clearInterval(this.kineticAnimTimer);
    // Smooth forward dead-reckoning extrapolation for active airplanes and vessels
    this.kineticAnimTimer = setInterval(() => {
      if (this.currentMode !== '2D') return;
      const now = performance.now();
      this.kineticMap.forEach((entry, trackId) => {
        if (!entry.marker || !entry.velocity_mps || entry.velocity_mps <= 0) return;
        const dtSec = (now - entry.lastExtrapolated) / 1000.0;
        if (dtSec <= 0.2 || dtSec > 40) return;

        // Kinematic forward projection: dist = v * dt
        const distM = entry.velocity_mps * dtSec;
        const headingRad = (entry.heading * Math.PI) / 180.0;
        const dLat = (distM * Math.cos(headingRad)) / 111320.0;
        const cosLat = Math.cos((entry.lat * Math.PI) / 180.0);
        const dLon = Math.abs(cosLat) > 0.001 ? (distM * Math.sin(headingRad)) / (111320.0 * cosLat) : 0;

        entry.lat += dLat;
        entry.lon += dLon;
        entry.lastExtrapolated = now;

        entry.marker.setLatLng([entry.lat, entry.lon]);
      });
    }, 1000);
  }

  updateCoordDisplay(lat, lon, zoom) {
    const el = document.getElementById('footer-coords');
    if (el) el.textContent = `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E | ZOOM ${zoom.toFixed(1)}`;
  }

  updateCursorCoordDisplay(lat, lon) {
    const el = document.getElementById('footer-cursor-coords');
    if (el) el.textContent = `CURSOR: ${lat.toFixed(4)}°, ${lon.toFixed(4)}°`;
  }

  initEventListeners() {
    const btn2D = document.getElementById('btn-mode-2d');
    const btn3D = document.getElementById('btn-mode-3d');
    if (btn2D) btn2D.addEventListener('click', () => this.switchMode('2D'));
    if (btn3D) btn3D.addEventListener('click', () => this.switchMode('3D'));

    document.querySelectorAll('.preset-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const preset = e.target.getAttribute('data-preset');
        if (preset) this.flyToPreset(preset);
      });
    });

    // Quick filter pills
    document.querySelectorAll('.filter-pill').forEach(pill => {
      pill.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
        e.target.classList.add('active');
        this.filterMode = e.target.getAttribute('data-filter') || 'ALL';
        this.renderLayers();
      });
    });

    // Altitude filter slider
    const altSlider = document.getElementById('slider-altitude-filter');
    const altVal = document.getElementById('altitude-filter-val');
    if (altSlider) {
      altSlider.addEventListener('input', (e) => {
        this.maxAltitudeFilter = parseInt(e.target.value, 10);
        if (altVal) altVal.textContent = `${this.maxAltitudeFilter.toLocaleString()} FT`;
        this.renderLayers();
      });
    }

    // Speed filter slider (minimum speed)
    const spdSlider = document.getElementById('slider-speed-filter');
    const spdVal = document.getElementById('speed-filter-val');
    if (spdSlider) {
      spdSlider.addEventListener('input', (e) => {
        this.minSpeedFilter = parseInt(e.target.value, 10);
        if (spdVal) spdVal.textContent = `${this.minSpeedFilter} KTS`;
        this.renderLayers();
      });
    }
  }
    }
  }
}

window.globeMap = new GlobeMapEngine();
