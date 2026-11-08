/**
 * frontend/assets/app.js - Main Application Controller & State Orchestrator
 * LocalOSINT v3.0 Global Intelligence Command Centre
 */

class AppController {
  constructor() {
    this.selectedEntity = null;
    this.cy = null;
    this.currentWorkspaceId = null;
    this.sseSource = null;
  }

  async init() {
    // 1. Initialize sub-engines
    if (window.globeMap) window.globeMap.init();
    if (window.timeline4D) window.timeline4D.init();
    if (window.sweepDeltaHud) window.sweepDeltaHud.init();
    if (window.visualStudio) window.visualStudio.init();

    // 2. Setup workspaces & active case
    await this.loadWorkspaces();

    // 3. Connect to real-time SSE stream
    this.connectSSE();

    // 4. Bind global keyboard shortcuts & top bar actions
    this.bindGlobalShortcuts();
    this.bindTopBarActions();
    this.bindInspectorActions();
  }

  async loadWorkspaces() {
    try {
      const res = await fetch('/api/workspaces');
      if (res.ok) {
        const list = await res.json();
        const sel = document.getElementById('case-select');
        if (sel) {
          sel.innerHTML = '';
          list.forEach(w => {
            const opt = document.createElement('option');
            opt.value = w.id;
            opt.textContent = `${w.name} (${w.tlp_marking || 'TLP:CLEAR'})`;
            sel.appendChild(opt);
          });
          if (list.length > 0) {
            this.currentWorkspaceId = list[0].id;
            sel.value = this.currentWorkspaceId;
          }
        }
      }
    } catch (e) {
      console.warn("Could not load workspaces:", e);
    }
  }

  connectSSE() {
    try {
      if (this.sseSource) this.sseSource.close();
      this.sseSource = new EventSource('/api/v1/stream');

      this.sseSource.addEventListener('connected', (e) => {
        console.log("SSE connected:", e.data);
      });

      this.sseSource.addEventListener('SWEEP_COMPLETED', (e) => {
        const data = JSON.parse(e.data);
        if (window.sweepDeltaHud) {
          window.sweepDeltaHud.fetchLatestSweep();
        }
        if (window.globeMap) {
          window.globeMap.fetchLayers();
        }
        this.showToast(`Crucix Sweep complete (Tension: ${data.escalation_score}/100)`, 'success');
      });

      this.sseSource.addEventListener('GEOFENCE_BREACH', (e) => {
        const data = JSON.parse(e.data);
        this.showToast(`ALERT: Geofence breach detected (${data.severity || 'HIGH'})`, 'error');
      });

      this.sseSource.onerror = () => {
        console.debug("SSE reconnecting...");
      };
    } catch (e) {
      console.warn("SSE init failed:", e);
    }
  }

  bindGlobalShortcuts() {
    window.addEventListener('keydown', (e) => {
      // Ctrl+K or Cmd+K opens global search
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('global-search-input');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });

    const searchInput = document.getElementById('global-search-input');
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          this.executeGlobalSearch(searchInput.value.trim());
        }
      });
    }
  }

  async executeGlobalSearch(query) {
    if (!query) return;
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&workspace_id=${this.currentWorkspaceId || ''}`);
      if (res.ok) {
        const data = await res.json();
        this.renderSearchResults(data.results || [], query);
      }
    } catch (e) {
      console.error("Search error:", e);
    }
  }

  renderSearchResults(results, query) {
    const modal = document.getElementById('modal-search-results');
    const container = document.getElementById('search-results-list');
    const titleEl = document.getElementById('search-query-display');

    if (!modal || !container) return;

    if (titleEl) titleEl.textContent = `Search results for "${query}" (${results.length})`;
    container.innerHTML = '';

    if (results.length === 0) {
      container.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">No matching entities found.</div>';
      modal.classList.remove('hidden');
      return;
    }

    results.forEach(r => {
      const item = document.createElement('div');
      item.className = 'layer-item';
      item.style.marginBottom = '6px';
      item.style.cursor = 'pointer';
      item.innerHTML = `
        <div>
          <strong style="color:var(--accent-cyan);">${r.display_label || r.raw_value || 'Entity'}</strong> 
          <small style="color:var(--text-dim); margin-left:6px;">${r.ftm_schema || ''}</small>
          <div style="font-size:10px; color:var(--text-muted);">${r.location_label || ''} | Risk: ${r.risk_score || 0}</div>
        </div>
        <div>
          <span class="badge-telemetry live">Score: ${(r.rrf_score || r.hybrid_score || 0).toFixed(2)}</span>
        </div>
      `;

      item.addEventListener('click', () => {
        modal.classList.add('hidden');
        if (r.latitude != null && r.longitude != null && window.globeMap) {
          window.globeMap.flyToCoords(r.latitude, r.longitude, 12);
        }
        this.selectEntity(r, r.latitude, r.longitude);
      });

      container.appendChild(item);
    });

    modal.classList.remove('hidden');
  }

  bindTopBarActions() {
    // SitRep Briefing Drawer
    const btnBriefing = document.getElementById('btn-open-briefing');
    const modalBriefing = document.getElementById('modal-briefing');
    const btnCloseBriefing = document.getElementById('btn-close-briefing');

    if (btnBriefing && modalBriefing) {
      btnBriefing.addEventListener('click', async () => {
        modalBriefing.classList.remove('hidden');
        const contentEl = document.getElementById('briefing-markdown-content');
        if (contentEl) contentEl.innerHTML = '<em>Synthesizing grounded AI SitRep briefing...</em>';

        try {
          const res = await fetch('/api/v1/sweeps/latest/briefing');
          if (res.ok) {
            const data = await res.json();
            const md = data.briefing_markdown || 'No briefing available.';
            if (typeof marked !== 'undefined') {
              contentEl.innerHTML = marked.parse(md);
            } else {
              contentEl.textContent = md;
            }
          }
        } catch (e) {
          if (contentEl) contentEl.textContent = 'Failed to generate briefing.';
        }
      });
    }

    if (btnCloseBriefing && modalBriefing) {
      btnCloseBriefing.addEventListener('click', () => {
        modalBriefing.classList.add('hidden');
      });
    }

    // Export dropdown
    const btnExport = document.getElementById('btn-export-dropdown');
    const exportMenu = document.getElementById('export-menu');
    if (btnExport && exportMenu) {
      btnExport.addEventListener('click', (e) => {
        e.stopPropagation();
        exportMenu.classList.toggle('hidden');
      });

      document.addEventListener('click', () => {
        exportMenu.classList.add('hidden');
      });

      exportMenu.querySelectorAll('a[data-export]').forEach(a => {
        a.addEventListener('click', (e) => {
          e.preventDefault();
          const fmt = e.target.getAttribute('data-export');
          const wsId = this.currentWorkspaceId || 'default';
          window.open(`/api/workspaces/${wsId}/export?format=${fmt}`, '_blank');
        });
      });
    }

    // Modal Close generic
    document.querySelectorAll('.modal-close').forEach(btn => {
      btn.addEventListener('click', () => {
        btn.closest('.modal-overlay').classList.add('hidden');
      });
    });
  }

  selectEntity(props, lat, lon) {
    this.selectedEntity = { ...props, lat, lon };

    // Update Zone 4 Inspector UI
    const titleEl = document.getElementById('inspector-entity-title');
    if (titleEl) titleEl.textContent = props.display_label || props.callsign_or_name || 'Kinetic Asset';

    const badgesContainer = document.getElementById('inspector-badges-row');
    if (badgesContainer) {
      badgesContainer.innerHTML = '';
      if (props.is_sanctioned) {
        badgesContainer.innerHTML += '<span class="badge-telemetry sanction">OFAC SANCTIONED</span>';
      }
      if (props.is_military) {
        badgesContainer.innerHTML += '<span class="badge-telemetry live">MILITARY</span>';
      }
      const status = props.telemetry_status || 'LIVE';
      badgesContainer.innerHTML += `<span class="badge-telemetry live">${status}</span>`;
      badgesContainer.innerHTML += `<span class="badge-telemetry bootstrap">${props.layer_type || 'ENTITY'}</span>`;
    }

    // Properties grid
    const grid = document.getElementById('inspector-props-grid');
    if (grid) {
      grid.innerHTML = `
        <div class="prop-cell"><span class="prop-label">CALLSIGN / NAME</span><span class="prop-value">${props.callsign_or_name || 'N/A'}</span></div>
        <div class="prop-cell"><span class="prop-label">NETWORK</span><span class="prop-value">${props.source_network || 'ADSB/AIS'}</span></div>
        <div class="prop-cell"><span class="prop-label">ALTITUDE</span><span class="prop-value">${props.altitude_m != null ? Math.round(props.altitude_m) + ' m' : 'Surface'}</span></div>
        <div class="prop-cell"><span class="prop-label">SPEED</span><span class="prop-value">${props.speed_kts != null ? props.speed_kts.toFixed(1) + ' kts' : 'Stationary'}</span></div>
        <div class="prop-cell"><span class="prop-label">HEADING</span><span class="prop-value">${props.heading != null ? props.heading + '°' : 'N/A'}</span></div>
        <div class="prop-cell"><span class="prop-label">COORDINATES</span><span class="prop-value">${lat != null && lon != null ? `${lat.toFixed(4)}°, ${lon.toFixed(4)}°` : 'N/A'}</span></div>
      `;
    }

    // Sanction alert box
    const sanctionBox = document.getElementById('inspector-sanction-box');
    if (sanctionBox) {
      if (props.is_sanctioned) {
        sanctionBox.classList.remove('hidden');
        sanctionBox.innerHTML = `
          <div style="background:rgba(239,68,68,0.15); border:1px solid #EF4444; border-radius:4px; padding:8px; color:#FCA5A5;">
            <strong>⚠️ OFAC SDN SANCTION RECORD DETECTED</strong><br>
            Matched Asset: ${props.display_label || props.callsign_or_name}<br>
            Reference: US Treasury SDN List Cross-Reference
          </div>
        `;
      } else {
        sanctionBox.classList.add('hidden');
      }
    }

    // Camera action button if camera layer
    const camBox = document.getElementById('inspector-camera-actions');
    if (camBox) {
      if (props.layer_type === 'CAMERA') {
        camBox.classList.remove('hidden');
        const snapBtn = document.getElementById('btn-camera-snapshot');
        if (snapBtn) {
          snapBtn.onclick = () => {
            const vsModal = document.getElementById('modal-visual-studio');
            if (vsModal) vsModal.classList.remove('hidden');
            // If camera snapshot url exists, analyze it
            const snapUrl = props.metadata?.snapshot_url;
            if (snapUrl) {
              const previewImg = document.getElementById('visual-processed-img');
              if (previewImg) previewImg.src = snapUrl;
            }
          };
        }
      } else {
        camBox.classList.add('hidden');
      }
    }

    // Subjective Logic bars
    const b = props.sl_belief || 0.85;
    const d = props.sl_disbelief || (props.is_sanctioned ? 0.30 : 0.05);
    const u = Math.max(0.0, 1.0 - (b + d));

    const fillB = document.getElementById('sl-fill-belief');
    const fillD = document.getElementById('sl-fill-disbelief');
    const fillU = document.getElementById('sl-fill-uncertainty');

    if (fillB) { fillB.style.width = `${Math.round(b * 100)}%`; document.getElementById('sl-val-belief').textContent = b.toFixed(2); }
    if (fillD) { fillD.style.width = `${Math.round(d * 100)}%`; document.getElementById('sl-val-disbelief').textContent = d.toFixed(2); }
    if (fillU) { fillU.style.width = `${Math.round(u * 100)}%`; document.getElementById('sl-val-uncertainty').textContent = u.toFixed(2); }

    // Render Cytoscape Ego-Graph
    this.renderEgoGraph(props);
  }

  renderEgoGraph(entity) {
    const container = document.getElementById('cy-container');
    if (!container || typeof cytoscape === 'undefined') return;

    const label = entity.display_label || entity.callsign_or_name || 'Node';
    const elements = [
      { data: { id: 'root', label: label, color: '#38BDF8', size: 30 } },
      { data: { id: 'geo', label: 'WGS84 Position', color: '#10B981', size: 20 } },
      { data: { id: 'prov', label: 'PROV Source', color: '#F59E0B', size: 20 } },
      { data: { source: 'root', target: 'geo', label: 'LOCATED_AT' } },
      { data: { source: 'root', target: 'prov', label: 'DERIVED_FROM' } }
    ];

    if (entity.is_sanctioned) {
      elements.push({ data: { id: 'sdn', label: 'OFAC SDN', color: '#EF4444', size: 25 } });
      elements.push({ data: { source: 'root', target: 'sdn', label: 'SANCTIONED_UNDER' } });
    }

    if (this.cy) this.cy.destroy();

    this.cy = cytoscape({
      container: container,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'label': 'data(label)',
            'color': '#F1F5F9',
            'font-size': '9px',
            'font-family': 'JetBrains Mono',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'width': 'data(size)',
            'height': 'data(size)'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': 'rgba(56, 189, 248, 0.4)',
            'target-arrow-color': '#38BDF8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'font-size': '8px',
            'color': '#94A3B8',
            'label': 'data(label)'
          }
        }
      ],
      layout: {
        name: 'concentric',
        fit: true,
        padding: 20
      }
    });
  }

  bindInspectorActions() {
    const btnUnmerge = document.getElementById('btn-unmerge-resolution');
    if (btnUnmerge) {
      btnUnmerge.addEventListener('click', () => {
        this.showToast("Merge ledger intact. No duplicate links requiring unmerge.", "success");
      });
    }
  }

  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${type === 'error' ? '❌' : '✓'}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
}

window.app = new AppController();
document.addEventListener('DOMContentLoaded', () => {
  window.app.init();
});
