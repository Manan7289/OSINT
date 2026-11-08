/**
 * frontend/assets/sweep_delta_hud.js - Crucix Sweep-Delta Ticker & Geofence Manager
 * LocalOSINT v3.0 Global Intelligence Command Centre
 */

class SweepDeltaHudEngine {
  constructor() {
    this.latestSweep = null;
    this.isDrawingGeofence = false;
    this.drawingPoints = [];
    this.tempPolygon = null;
    this.tempMarkers = [];
  }

  init() {
    this.bindTabSwitchers();
    this.bindLayerCheckboxes();
    this.bindSweepControls();
    this.bindGeofenceControls();
    this.fetchLatestSweep();
  }

  bindTabSwitchers() {
    document.querySelectorAll('.panel-tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const tab = e.target.getAttribute('data-tab');
        document.querySelectorAll('.panel-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content-panel').forEach(p => p.classList.add('hidden'));

        e.target.classList.add('active');
        const targetPanel = document.getElementById(tab);
        if (targetPanel) targetPanel.classList.remove('hidden');
      });
    });
  }

  bindLayerCheckboxes() {
    const layerMap = {
      'layer-toggle-aircraft': 'AIRCRAFT',
      'layer-toggle-military': 'MILITARY_AIRCRAFT',
      'layer-toggle-vessels': 'VESSEL',
      'layer-toggle-satellites': 'SATELLITE',
      'layer-toggle-quakes': 'EARTHQUAKE',
      'layer-toggle-cameras': 'CAMERA',
      'layer-toggle-jamming': 'GPS_JAMMING'
    };

    Object.entries(layerMap).forEach(([id, layerKey]) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', (e) => {
          if (window.globeMap) {
            window.globeMap.toggleLayer(layerKey, e.target.checked);
          }
        });
      }
    });
  }

  bindSweepControls() {
    const btnRunSweep = document.getElementById('btn-run-sweep');
    if (btnRunSweep) {
      btnRunSweep.addEventListener('click', () => {
        this.runSweepNow();
      });
    }

    const badgeTension = document.getElementById('escalation-gauge');
    if (badgeTension) {
      badgeTension.addEventListener('click', () => {
        // Switch to Crucix tab
        const crucixTabBtn = document.querySelector('[data-tab="tab-crucix"]');
        if (crucixTabBtn) crucixTabBtn.click();
      });
    }
  }

  async fetchLatestSweep() {
    try {
      const res = await fetch('/api/v1/sweeps/latest');
      if (res.ok) {
        const data = await res.json();
        this.renderSweep(data);
      }
    } catch (e) {
      console.error("Error fetching latest sweep:", e);
    }
  }

  async runSweepNow() {
    const btnRunSweep = document.getElementById('btn-run-sweep');
    if (btnRunSweep) {
      btnRunSweep.disabled = true;
      btnRunSweep.textContent = 'Sweeping...';
    }

    try {
      const res = await fetch('/api/v1/sweeps/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ investigation_id: 'default' })
      });
      if (res.ok) {
        const data = await res.json();
        this.renderSweep(data);
        if (window.globeMap) {
          window.globeMap.fetchLayers();
        }
        if (window.app && window.app.showToast) {
          window.app.showToast(`Sweep completed: ${data.deltas?.length || 0} deltas detected. Tension: ${data.escalation_score}/100`, 'success');
        }
      }
    } catch (e) {
      console.error("Error running sweep:", e);
      if (window.app && window.app.showToast) {
        window.app.showToast("Sweep execution failed.", "error");
      }
    } finally {
      if (btnRunSweep) {
        btnRunSweep.disabled = false;
        btnRunSweep.textContent = '⚡ Run Sweep Now';
      }
    }
  }

  renderSweep(sweepData) {
    this.latestSweep = sweepData;
    const score = Math.round(sweepData.escalation_score || 0);

    // Update Escalation Gauge in Header
    const gaugeEl = document.getElementById('escalation-gauge');
    if (gaugeEl) {
      gaugeEl.innerHTML = `Tension: <strong>${score}</strong>/100`;
      gaugeEl.className = 'escalation-badge';
      if (score >= 60) gaugeEl.classList.add('critical');
      else if (score >= 35) gaugeEl.classList.add('medium');
      else gaugeEl.classList.add('low');
    }

    // Update Sweep stats in tab
    const statsEl = document.getElementById('sweep-stats-summary');
    if (statsEl) {
      statsEl.innerHTML = `
        <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:4px;">
          <span>Sweep ID: <code>${sweepData.sweep_id ? sweepData.sweep_id.substring(0, 16) : 'N/A'}...</code></span>
          <span>Sources: ${sweepData.sources_succeeded || sweepData.stats?.sources_succeeded || 5}</span>
        </div>
        <div style="font-size:10px; color:var(--text-muted);">
          New Entities: ${sweepData.new_entities_count || sweepData.stats?.new_entities_count || 0} | 
          Sanctions: ${sweepData.sanction_matches_count || sweepData.stats?.sanction_matches_count || 0} | 
          Geofences: ${sweepData.geofence_alerts_count || sweepData.stats?.geofence_alerts_count || 0}
        </div>
      `;
    }

    // Render deltas list
    const deltasContainer = document.getElementById('sweep-deltas-list');
    if (!deltasContainer) return;

    deltasContainer.innerHTML = '';
    const deltas = sweepData.deltas || [];

    if (deltas.length === 0) {
      deltasContainer.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:15px;">No active delta shifts detected in this sweep cycle.</div>';
      return;
    }

    deltas.forEach(d => {
      const card = document.createElement('div');
      card.className = `delta-card ${d.severity || 'MEDIUM'}`;
      card.innerHTML = `
        <div class="delta-header">
          <span class="delta-type">${d.delta_type}</span>
          <span class="delta-time">${d.created_at ? d.created_at.substring(11, 16) : 'Just now'}</span>
        </div>
        <div class="delta-title">${d.title}</div>
        <div class="delta-desc">${d.description}</div>
      `;

      card.addEventListener('click', () => {
        if (d.lat != null && d.lon != null && window.globeMap) {
          window.globeMap.flyToCoords(d.lat, d.lon, 9);
        }
        if (d.entity_id && window.app && window.app.fetchAndSelectEntity) {
          window.app.fetchAndSelectEntity(d.entity_id);
        }
      });

      deltasContainer.appendChild(card);
    });
  }

  bindGeofenceControls() {
    const btnDraw = document.getElementById('btn-draw-geofence');
    if (btnDraw) {
      btnDraw.addEventListener('click', () => {
        this.toggleGeofenceDrawMode();
      });
    }

    const btnSaveGeofence = document.getElementById('btn-save-geofence');
    if (btnSaveGeofence) {
      btnSaveGeofence.addEventListener('click', () => {
        this.saveDrawnGeofence();
      });
    }

    const btnCancelGeofence = document.getElementById('btn-cancel-geofence');
    if (btnCancelGeofence) {
      btnCancelGeofence.addEventListener('click', () => {
        this.cancelGeofenceDrawing();
      });
    }
  }

  toggleGeofenceDrawMode() {
    if (!window.globeMap || !window.globeMap.map2D) {
      alert("Geofence polygon drawing requires 2D Map view.");
      return;
    }

    // Switch to 2D if in 3D
    if (window.globeMap.currentMode !== '2D') {
      window.globeMap.switchMode('2D');
    }

    this.isDrawingGeofence = !this.isDrawingGeofence;
    const btnDraw = document.getElementById('btn-draw-geofence');

    if (this.isDrawingGeofence) {
      if (btnDraw) {
        btnDraw.classList.add('primary');
        btnDraw.textContent = 'Click Map Vertices (Double-Click Done)';
      }
      this.drawingPoints = [];
      window.globeMap.map2D.on('click', this.onMapClickForGeofence, this);
      window.globeMap.map2D.on('dblclick', this.onMapDblClickForGeofence, this);
    } else {
      this.cancelGeofenceDrawing();
    }
  }

  onMapClickForGeofence(e) {
    if (!this.isDrawingGeofence) return;
    const pt = [e.latlng.lat, e.latlng.lng];
    this.drawingPoints.push(pt);

    // Draw temporary point marker
    const marker = L.circleMarker(pt, { radius: 4, color: '#38BDF8', fillColor: '#38BDF8', fillOpacity: 0.8 });
    marker.addTo(window.globeMap.map2D);
    this.tempMarkers.push(marker);

    // Update polyline
    if (this.drawingPoints.length >= 2) {
      if (this.tempPolygon) {
        this.tempPolygon.setLatLngs(this.drawingPoints);
      } else {
        this.tempPolygon = L.polygon(this.drawingPoints, {
          color: '#38BDF8',
          weight: 2,
          dashArray: '4, 4',
          fillColor: '#38BDF8',
          fillOpacity: 0.15
        }).addTo(window.globeMap.map2D);
      }
    }
  }

  onMapDblClickForGeofence(e) {
    if (!this.isDrawingGeofence || this.drawingPoints.length < 3) return;
    L.DomEvent.stop(e);

    // Open Save Geofence modal
    const modal = document.getElementById('modal-save-geofence');
    if (modal) modal.classList.remove('hidden');
  }

  async saveDrawnGeofence() {
    const nameInput = document.getElementById('geofence-name-input');
    const name = nameInput ? nameInput.value.trim() : 'Tactical Watch Zone';
    if (!name) return;

    // Convert drawingPoints [lat, lng] to GeoJSON [[lon, lat], ...]
    const coords = this.drawingPoints.map(p => [p[1], p[0]]);
    // Close polygon
    coords.push([coords[0][0], coords[0][1]]);

    const geoJsonPoly = {
      type: "Polygon",
      coordinates: [coords]
    };

    try {
      const res = await fetch('/api/v1/geofences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          polygon_geojson: geoJsonPoly,
          monitored_layers: ["AIRCRAFT", "VESSEL", "EARTHQUAKE"],
          min_severity: "MEDIUM",
          notify_channels: ["SSE"]
        })
      });

      if (res.ok) {
        if (window.app && window.app.showToast) {
          window.app.showToast(`Geofence '${name}' saved and actively monitored!`, 'success');
        }
      }
    } catch (e) {
      console.error("Error saving geofence:", e);
    } finally {
      this.cancelGeofenceDrawing();
      const modal = document.getElementById('modal-save-geofence');
      if (modal) modal.classList.add('hidden');
    }
  }

  cancelGeofenceDrawing() {
    this.isDrawingGeofence = false;
    this.drawingPoints = [];
    const btnDraw = document.getElementById('btn-draw-geofence');
    if (btnDraw) {
      btnDraw.classList.remove('primary');
      btnDraw.textContent = '⬟ Draw Geofence';
    }

    if (window.globeMap && window.globeMap.map2D) {
      window.globeMap.map2D.off('click', this.onMapClickForGeofence, this);
      window.globeMap.map2D.off('dblclick', this.onMapDblClickForGeofence, this);
      this.tempMarkers.forEach(m => window.globeMap.map2D.removeLayer(m));
      if (this.tempPolygon) window.globeMap.map2D.removeLayer(this.tempPolygon);
    }
    this.tempMarkers = [];
    this.tempPolygon = null;
  }
}

window.sweepDeltaHud = new SweepDeltaHudEngine();
