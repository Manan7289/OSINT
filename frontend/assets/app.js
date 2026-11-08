/**
 * LocalOSINT v2.0 — Dual-Engine WebGL/Canvas Analyst Workstation Frontend
 * Zero external CDN dependencies (100% self-contained local bundle).
 */

(function () {
  'use strict';

  // --- Global Application State ---
  const state = {
    currentWorkspaceId: null,
    currentView: 'view-dashboard',
    workspaces: [],
    graph: {
      nodes: [],
      edges: [],
      nodeMap: new Map(),
      engine: 'canvas', // 'canvas' or 'svg'
      transform: { x: 0, y: 0, k: 1 },
      isDragging: false,
      draggedNode: null,
      dragStart: { x: 0, y: 0 },
      hoveredNode: null,
      selectedNode: null,
      simulationRunning: false,
      hideShared: false,
      asOfDate: ''
    },
    connectors: [],
    settings: {}
  };

  // --- Utility Functions ---

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  async function apiRequest(url, options = {}) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || `HTTP Error ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      console.error(`API Error on ${url}:`, err);
      showToast(err.message, 'danger');
      throw err;
    }
  }

  // --- Initialization ---

  document.addEventListener('DOMContentLoaded', async () => {
    initNavigation();
    initExportDropdown();
    initModal();
    initGraphControls();
    initForensicsHandlers();
    initAiHandlers();
    initSettingsHandlers();

    // Load initial workspaces
    await loadWorkspaces();
  });

  // --- Navigation & Views ---

  function initNavigation() {
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const targetViewId = tab.getAttribute('data-view');
        switchView(targetViewId);
      });
    });

    // Global Search trigger
    const btnSearch = document.getElementById('btn-global-search');
    const inputSearch = document.getElementById('global-search-input');
    if (btnSearch && inputSearch) {
      btnSearch.addEventListener('click', () => executeGlobalSearch(inputSearch.value.trim()));
      inputSearch.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') executeGlobalSearch(inputSearch.value.trim());
      });
    }
  }

  function switchView(viewId) {
    state.currentView = viewId;

    // Update sidebar active state
    document.querySelectorAll('.nav-tab').forEach((tab) => {
      tab.classList.toggle('active', tab.getAttribute('data-view') === viewId);
    });

    // Update view panels
    document.querySelectorAll('.view-panel').forEach((panel) => {
      panel.classList.toggle('active', panel.id === viewId);
    });

    // Trigger view-specific data refresh
    loadActiveViewData();
  }

  function loadActiveViewData() {
    if (!state.currentWorkspaceId) return;

    switch (state.currentView) {
      case 'view-dashboard':
        loadDashboardData();
        break;
      case 'view-collect':
        loadCollectData();
        break;
      case 'view-entities':
        loadEntitiesData();
        break;
      case 'view-graph':
        loadGraphData();
        break;
      case 'view-resolution':
        loadResolutionData();
        break;
      case 'view-timeline':
        loadTimelineData();
        break;
      case 'view-geospatial':
        loadGeospatialData();
        break;
      case 'view-provenance':
        loadProvenanceData();
        break;
      case 'view-ai-reports':
        // Ready for queries
        break;
      case 'view-tasks':
        loadTasksData();
        break;
      case 'view-settings':
        loadSettingsData();
        break;
    }
  }

  // --- Workspaces & Case Management ---

  async function loadWorkspaces() {
    try {
      const workspaces = await apiRequest('/api/workspaces');
      state.workspaces = workspaces;
      const select = document.getElementById('workspace-select');
      select.innerHTML = '';

      if (workspaces.length === 0) {
        select.innerHTML = '<option value="">No Active Cases</option>';
        return;
      }

      workspaces.forEach((ws) => {
        const opt = document.createElement('option');
        opt.value = ws.id;
        opt.textContent = `${ws.name} (${ws.tlp_marking || 'TLP:AMBER'})`;
        select.appendChild(opt);
      });

      // Restore saved or select first
      const savedWs = localStorage.getItem('localosint_active_workspace');
      if (savedWs && workspaces.some((w) => w.id === savedWs)) {
        select.value = savedWs;
        state.currentWorkspaceId = savedWs;
      } else {
        select.value = workspaces[0].id;
        state.currentWorkspaceId = workspaces[0].id;
      }

      select.addEventListener('change', () => {
        state.currentWorkspaceId = select.value;
        localStorage.setItem('localosint_active_workspace', select.value);
        loadActiveViewData();
      });

      // Update Header Badges
      const activeWsObj = workspaces.find((w) => w.id === state.currentWorkspaceId);
      if (activeWsObj) {
        const badgeOpsec = document.getElementById('badge-opsec');
        if (badgeOpsec) {
          badgeOpsec.textContent = `OPSEC: ${activeWsObj.opsec_mode || 'STANDARD'}`;
          badgeOpsec.className = activeWsObj.opsec_mode === 'PASSIVE_ONLY' ? 'badge badge-warning' : 'badge badge-success';
        }
      }

      loadActiveViewData();
    } catch (err) {
      console.error('Failed to load workspaces:', err);
    }
  }

  function initModal() {
    const modal = document.getElementById('modal-new-workspace');
    const btnOpen = document.getElementById('btn-new-workspace-modal');
    const btnClose = document.getElementById('btn-close-modal');
    const btnCancel = document.getElementById('btn-cancel-modal');
    const btnConfirm = document.getElementById('btn-create-workspace-confirm');

    if (!modal) return;

    const closeModal = () => modal.classList.add('hidden');
    btnOpen?.addEventListener('click', () => modal.classList.remove('hidden'));
    btnClose?.addEventListener('click', closeModal);
    btnCancel?.addEventListener('click', closeModal);

    btnConfirm?.addEventListener('click', async () => {
      const name = document.getElementById('modal-ws-name')?.value.trim();
      const description = document.getElementById('modal-ws-desc')?.value.trim();
      const tlp = document.getElementById('modal-ws-tlp')?.value;
      const opsec = document.getElementById('modal-ws-opsec')?.value;

      if (!name) {
        showToast('Please enter a case name.', 'warning');
        return;
      }

      try {
        const newWs = await apiRequest('/api/workspaces', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, description, tlp_marking: tlp, opsec_mode: opsec })
        });
        showToast(`Case "${newWs.name}" created successfully!`, 'success');
        closeModal();
        await loadWorkspaces();
        state.currentWorkspaceId = newWs.id;
        document.getElementById('workspace-select').value = newWs.id;
        loadActiveViewData();
      } catch (err) {
        showToast('Failed to create case: ' + err.message, 'danger');
      }
    });
  }

  function initExportDropdown() {
    const btn = document.getElementById('btn-export-dropdown');
    const menu = document.getElementById('export-menu');
    if (!btn || !menu) return;

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.classList.toggle('show');
    });

    document.addEventListener('click', () => menu.classList.remove('show'));

    menu.querySelectorAll('a[data-export]').forEach((link) => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const exportType = link.getAttribute('data-export');
        if (!state.currentWorkspaceId) {
          showToast('Select an active case first', 'warning');
          return;
        }
        window.open(`/api/export/${state.currentWorkspaceId}/${exportType}`, '_blank');
      });
    });
  }

  // --- VIEW 1: Command Dashboard ---

  async function loadDashboardData() {
    try {
      const data = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/dashboard`);
      document.getElementById('kpi-entities').textContent = data.entities_count || 0;
      document.getElementById('kpi-claims').textContent = data.claims_count || 0;
      document.getElementById('kpi-staged').textContent = data.staged_count || 0;
      document.getElementById('kpi-evidence').textContent = data.evidence_count || 0;
      document.getElementById('kpi-conflicts').textContent = data.contradiction_alerts_count || 0;

      const sidebarBadge = document.getElementById('sidebar-staged-badge');
      if (sidebarBadge) sidebarBadge.textContent = data.staged_count || 0;

      // Centrality Hubs Table
      const hubsTbody = document.querySelector('#table-dashboard-hubs tbody');
      if (hubsTbody) {
        hubsTbody.innerHTML = '';
        if (data.top_hubs && data.top_hubs.length > 0) {
          data.top_hubs.forEach((h) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td><strong>${escapeHtml(h.label || h.canonical_value)}</strong></td>
              <td><span class="badge badge-info">${escapeHtml(h.schema)}</span></td>
              <td><code>${(h.pagerank || 0).toFixed(4)}</code></td>
              <td>${h.degree || 0}</td>
            `;
            hubsTbody.appendChild(tr);
          });
        } else {
          hubsTbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No graph entities recorded yet.</td></tr>';
        }
      }

      // Latest Evidence Table
      const evTbody = document.querySelector('#table-dashboard-evidence tbody');
      if (evTbody) {
        evTbody.innerHTML = '';
        if (data.latest_evidence && data.latest_evidence.length > 0) {
          data.latest_evidence.forEach((ev) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td>${escapeHtml(ev.source_name)}</td>
              <td><span class="badge badge-primary">${escapeHtml(ev.admiralty_code || 'B2')}</span></td>
              <td>${escapeHtml(ev.title || 'OSINT Evidence Artifact')}</td>
              <td>${escapeHtml(ev.observed_at ? ev.observed_at.substring(0, 19).replace('T', ' ') : 'N/A')}</td>
            `;
            evTbody.appendChild(tr);
          });
        } else {
          evTbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No evidence artifacts recorded yet.</td></tr>';
        }
      }
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    }
  }

  // --- VIEW 2: Collect & Triage Buffer + Forensics ---

  async function loadCollectData() {
    // Populate 24 connectors in grid
    const container = document.getElementById('playbook-connectors-list');
    if (container && container.children.length === 0) {
      const connectors = [
        'dns_rdap', 'crt_sh', 'bgp_view', 'ip_api', 'alienvault_otx',
        'wayback_archive', 'threatminer', 'cve_circl', 'github_recon',
        'open_sanctions', 'wikidata_recon', 'urlhaus', 'abuseipdb_free',
        'hackertarget', 'leakix_public', 'pulsedive_free', 'fullcontact_free',
        'hunter_free', 'shodan', 'censys', 'virustotal', 'securitytrails',
        'greynoise', 'fofa'
      ];
      container.innerHTML = '';
      connectors.forEach((conn) => {
        const item = document.createElement('div');
        item.className = 'connector-item';
        const isKeyed = ['shodan', 'censys', 'virustotal', 'securitytrails', 'greynoise', 'fofa'].includes(conn);
        item.innerHTML = `
          <input type="checkbox" id="chk-conn-${conn}" value="${conn}" ${isKeyed ? '' : 'checked'}>
          <label for="chk-conn-${conn}">${conn} ${isKeyed ? '<small class="text-warning">[Keyed]</small>' : '<small class="text-success">[Keyless]</small>'}</label>
        `;
        container.appendChild(item);
      });
    }

    // Load Staging Buffer
    loadStagingBuffer();

    // Setup Playbook button
    const btnRunPlaybook = document.getElementById('btn-run-playbook');
    if (btnRunPlaybook && !btnRunPlaybook._hasListener) {
      btnRunPlaybook._hasListener = true;
      btnRunPlaybook.addEventListener('click', async () => {
        const target = document.getElementById('playbook-target-input')?.value.trim();
        const schema = document.getElementById('playbook-schema-select')?.value;
        const depth = parseInt(document.getElementById('playbook-depth-select')?.value || '1', 10);

        if (!target) {
          showToast('Enter a target observable (e.g. domain, IP).', 'warning');
          return;
        }

        const selectedConnectors = [];
        container.querySelectorAll('input[type="checkbox"]:checked').forEach((chk) => {
          selectedConnectors.push(chk.value);
        });

        btnRunPlaybook.disabled = true;
        btnRunPlaybook.textContent = 'Running Collection Tasks...';

        try {
          const res = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/collect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              target,
              schema_type: schema === 'AUTO' ? null : schema,
              depth,
              connectors: selectedConnectors
            })
          });

          showToast(`Playbook executed! Staged: ${res.staged_count || 0}, Claims: ${res.claims_count || 0}`, 'success');
          loadStagingBuffer();
          loadDashboardData();
        } catch (err) {
          showToast('Playbook execution failed: ' + err.message, 'danger');
        } finally {
          btnRunPlaybook.disabled = false;
          btnRunPlaybook.textContent = 'Execute Collection Playbook';
        }
      });
    }

    // Setup Promote buttons
    const btnPromoteSelected = document.getElementById('btn-promote-selected');
    if (btnPromoteSelected && !btnPromoteSelected._hasListener) {
      btnPromoteSelected._hasListener = true;
      btnPromoteSelected.addEventListener('click', async () => {
        const checked = document.querySelectorAll('#table-staging-buffer input[type="checkbox"]:checked');
        const entityIds = Array.from(checked).map((c) => c.value);
        if (entityIds.length === 0) {
          showToast('Select staged entities to promote.', 'warning');
          return;
        }

        try {
          const res = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/staging/promote`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ entity_ids: entityIds })
          });
          showToast(`Promoted ${res.promoted_count} entities to active graph!`, 'success');
          loadStagingBuffer();
          loadDashboardData();
        } catch (err) {
          showToast('Promotion failed: ' + err.message, 'danger');
        }
      });
    }

    const btnPromoteHighRisk = document.getElementById('btn-promote-high-risk');
    if (btnPromoteHighRisk && !btnPromoteHighRisk._hasListener) {
      btnPromoteHighRisk._hasListener = true;
      btnPromoteHighRisk.addEventListener('click', async () => {
        try {
          const res = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/staging/promote-high-risk?threshold=50`, {
            method: 'POST'
          });
          showToast(`Promoted ${res.promoted_count} high-risk entities (Risk ≥ 50)!`, 'success');
          loadStagingBuffer();
          loadDashboardData();
        } catch (err) {
          showToast('Failed to promote high-risk entities: ' + err.message, 'danger');
        }
      });
    }
  }

  async function loadStagingBuffer() {
    try {
      const staged = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/staging`);
      const tbody = document.querySelector('#table-staging-buffer tbody');
      if (!tbody) return;
      tbody.innerHTML = '';

      if (staged.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Staging triage buffer is empty.</td></tr>';
        return;
      }

      staged.forEach((item) => {
        const tr = document.createElement('tr');
        const riskClass = item.risk_score >= 50 ? 'text-danger font-bold' : 'text-muted';
        tr.innerHTML = `
          <td><input type="checkbox" value="${item.id}"></td>
          <td><span class="badge badge-info">${escapeHtml(item.ftm_schema)}</span></td>
          <td><strong>${escapeHtml(item.canonical_value)}</strong></td>
          <td class="${riskClass}">${item.risk_score || 0}</td>
          <td>
            <button class="btn btn-xs btn-outline btn-promote-single" data-id="${item.id}">Promote</button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      tbody.querySelectorAll('.btn-promote-single').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const id = btn.getAttribute('data-id');
          try {
            await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/staging/promote`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ entity_ids: [id] })
            });
            showToast('Entity promoted to graph!', 'success');
            loadStagingBuffer();
            loadDashboardData();
          } catch (err) {
            showToast('Promotion failed: ' + err.message, 'danger');
          }
        });
      });
    } catch (err) {
      console.error('Failed to load staging buffer:', err);
    }
  }

  function initForensicsHandlers() {
    const btnPaste = document.getElementById('btn-extract-paste');
    const btnUpload = document.getElementById('btn-upload-file');
    const resultBox = document.getElementById('forensics-result-box');

    btnPaste?.addEventListener('click', async () => {
      const text = document.getElementById('forensics-paste-text')?.value.trim();
      if (!text) {
        showToast('Please paste advisory or IOC text.', 'warning');
        return;
      }
      try {
        const res = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/forensics/paste`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        resultBox.classList.remove('hidden');
        resultBox.innerHTML = `
          <h4>Refanged & Extracted Observables (${res.observables ? res.observables.length : 0} found)</h4>
          <pre>${escapeHtml(JSON.stringify(res, null, 2))}</pre>
        `;
        showToast('Observables successfully extracted!', 'success');
      } catch (err) {
        showToast('Paste extraction failed: ' + err.message, 'danger');
      }
    });

    btnUpload?.addEventListener('click', async () => {
      const fileInput = document.getElementById('forensics-file-input');
      if (!fileInput || !fileInput.files[0]) {
        showToast('Please choose a file to analyze.', 'warning');
        return;
      }
      const formData = new FormData();
      formData.append('file', fileInput.files[0]);

      try {
        const res = await fetch(`/api/workspaces/${state.currentWorkspaceId}/forensics/upload`, {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        resultBox.classList.remove('hidden');
        resultBox.innerHTML = `
          <h4>File Forensics Results (${escapeHtml(data.filename || fileInput.files[0].name)})</h4>
          <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
        `;
        showToast('File analyzed successfully!', 'success');
      } catch (err) {
        showToast('File upload analysis failed: ' + err.message, 'danger');
      }
    });
  }

  // --- VIEW 3: Entity Explorer & Hybrid RRF Search ---

  async function loadEntitiesData(searchQuery = '') {
    try {
      const schemaFilter = document.getElementById('entity-schema-filter')?.value || '';
      const includeStaged = document.getElementById('entity-include-staged')?.checked ? '1' : '0';

      let entities = [];
      if (searchQuery) {
        const res = await apiRequest(`/api/search?q=${encodeURIComponent(searchQuery)}&workspace_id=${state.currentWorkspaceId}&mode=hybrid`);
        entities = res.results || [];
      } else {
        let url = `/api/workspaces/${state.currentWorkspaceId}/entities?limit=100&include_staged=${includeStaged}`;
        if (schemaFilter) url += `&schema_type=${encodeURIComponent(schemaFilter)}`;
        entities = await apiRequest(url);
      }

      const tbody = document.querySelector('#table-entities tbody');
      if (!tbody) return;
      tbody.innerHTML = '';

      if (entities.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No entities found.</td></tr>';
        return;
      }

      entities.forEach((ent) => {
        const tr = document.createElement('tr');
        const b = (ent.belief_score || 0).toFixed(2);
        const d = (ent.disbelief_score || 0).toFixed(2);
        const u = (ent.uncertainty_score || 1).toFixed(2);

        tr.innerHTML = `
          <td><span class="badge badge-info">${escapeHtml(ent.ftm_schema)}</span></td>
          <td><strong>${escapeHtml(ent.display_label || ent.canonical_value)}</strong></td>
          <td><span class="badge badge-primary">${escapeHtml(ent.admiralty_code || 'B2')}</span></td>
          <td>
            <div class="belief-bar">
              <span class="belief-part b" style="width: ${b * 100}%" title="Belief: ${b}"></span>
              <span class="belief-part d" style="width: ${d * 100}%" title="Disbelief: ${d}"></span>
              <span class="belief-part u" style="width: ${u * 100}%" title="Uncertainty: ${u}"></span>
            </div>
            <small class="text-muted">b:${b} d:${d} u:${u}</small>
          </td>
          <td><span class="badge ${ent.risk_score >= 50 ? 'badge-danger' : 'badge-warning'}">${ent.risk_score || 0}</span></td>
          <td><code>${ent.leiden_community_id !== undefined ? ent.leiden_community_id : '0'}</code></td>
          <td>${ent.independent_source_count || 1}</td>
          <td>${escapeHtml(ent.last_seen ? ent.last_seen.substring(0, 10) : 'N/A')}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error('Failed to load entities:', err);
    }
  }

  function executeGlobalSearch(query) {
    if (!query) {
      loadEntitiesData();
      return;
    }
    switchView('view-entities');
    loadEntitiesData(query);
  }

  // --- VIEW 4: Dual-Engine Relationship Graph ---

  function initGraphControls() {
    const btnToggleEngine = document.getElementById('btn-engine-toggle');
    const dateInput = document.getElementById('graph-as-of-date');
    const chkHideShared = document.getElementById('graph-hide-shared');
    const btnResetLayout = document.getElementById('btn-reset-layout');
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');

    btnToggleEngine?.addEventListener('click', () => {
      state.graph.engine = state.graph.engine === 'canvas' ? 'svg' : 'canvas';
      btnToggleEngine.textContent = `Engine: ${state.graph.engine === 'canvas' ? 'Canvas/WebGL' : 'SVG Tactical'}`;
      document.getElementById('graph-canvas')?.classList.toggle('hidden', state.graph.engine !== 'canvas');
      document.getElementById('graph-svg')?.classList.toggle('hidden', state.graph.engine !== 'svg');
      renderGraph();
    });

    dateInput?.addEventListener('change', () => {
      state.graph.asOfDate = dateInput.value;
      loadGraphData();
    });

    chkHideShared?.addEventListener('change', () => {
      state.graph.hideShared = chkHideShared.checked;
      loadGraphData();
    });

    btnResetLayout?.addEventListener('click', () => {
      resetGraphTransform();
      startGraphSimulation();
    });

    btnZoomIn?.addEventListener('click', () => {
      state.graph.transform.k *= 1.25;
      renderGraph();
    });

    btnZoomOut?.addEventListener('click', () => {
      state.graph.transform.k /= 1.25;
      renderGraph();
    });

    // Canvas Mouse Interaction (Pan & Drag)
    const canvas = document.getElementById('graph-canvas');
    if (canvas) {
      canvas.addEventListener('mousedown', onGraphMouseDown);
      window.addEventListener('mousemove', onGraphMouseMove);
      window.addEventListener('mouseup', onGraphMouseUp);
      canvas.addEventListener('wheel', onGraphWheel, { passive: false });
    }
  }

  function resetGraphTransform() {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas) return;
    state.graph.transform = {
      x: canvas.width / 2,
      y: canvas.height / 2,
      k: 1
    };
  }

  async function loadGraphData() {
    try {
      let url = `/api/workspaces/${state.currentWorkspaceId}/graph?`;
      if (state.graph.asOfDate) url += `as_of=${encodeURIComponent(state.graph.asOfDate)}&`;
      if (state.graph.hideShared) url += `hide_shared=true&`;

      const data = await apiRequest(url);
      const rawNodes = data.nodes || [];
      const rawEdges = data.edges || [];

      // Initialize Node positions and simulation structures
      const canvas = document.getElementById('graph-canvas');
      if (canvas) {
        canvas.width = canvas.parentElement.clientWidth || 900;
        canvas.height = canvas.parentElement.clientHeight || 650;
      }
      resetGraphTransform();

      state.graph.nodeMap.clear();
      state.graph.nodes = rawNodes.map((n, idx) => {
        const angle = (idx / rawNodes.length) * 2 * Math.PI;
        const radius = 120 + Math.random() * 220;
        const nodeObj = {
          ...n,
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
          vx: 0,
          vy: 0,
          radius: Math.max(10, Math.min(28, 8 + (n.degree || 1) * 3))
        };
        state.graph.nodeMap.set(nodeObj.id, nodeObj);
        return nodeObj;
      });

      state.graph.edges = rawEdges
        .map((e) => ({
          ...e,
          sourceNode: state.graph.nodeMap.get(e.source),
          targetNode: state.graph.nodeMap.get(e.target)
        }))
        .filter((e) => e.sourceNode && e.targetNode);

      startGraphSimulation();
    } catch (err) {
      console.error('Failed to load graph data:', err);
    }
  }

  function startGraphSimulation() {
    let iterations = 100;
    function step() {
      if (iterations <= 0) {
        state.graph.simulationRunning = false;
        renderGraph();
        return;
      }
      state.graph.simulationRunning = true;
      applyForceSimulationStep();
      iterations--;
      renderGraph();
      requestAnimationFrame(step);
    }
    step();
  }

  function applyForceSimulationStep() {
    const nodes = state.graph.nodes;
    const edges = state.graph.edges;
    const kRepulsion = 1800;
    const kAttraction = 0.04;
    const centerAttraction = 0.005;

    // Repulsion between all node pairs
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const u = nodes[i];
        const v = nodes[j];
        const dx = v.x - u.x;
        const dy = v.y - u.y;
        const distSq = dx * dx + dy * dy || 1;
        const dist = Math.sqrt(distSq);
        if (dist < 400) {
          const force = kRepulsion / distSq;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          u.vx -= fx;
          u.vy -= fy;
          v.vx += fx;
          v.vy += fy;
        }
      }
    }

    // Edge spring attraction
    for (const edge of edges) {
      const u = edge.sourceNode;
      const v = edge.targetNode;
      const dx = v.x - u.x;
      const dy = v.y - u.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - 100) * kAttraction;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      u.vx += fx;
      u.vy += fy;
      v.vx -= fx;
      v.vy -= fy;
    }

    // Centering force & update
    for (const node of nodes) {
      if (node === state.graph.draggedNode) continue;
      node.vx -= node.x * centerAttraction;
      node.vy -= node.y * centerAttraction;

      // Dampening
      node.vx *= 0.85;
      node.vy *= 0.85;

      node.x += node.vx;
      node.y += node.vy;
    }
  }

  function renderGraph() {
    if (state.graph.engine === 'canvas') {
      renderGraphCanvas();
    } else {
      renderGraphSvg();
    }
  }

  function renderGraphCanvas() {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const { x: tx, y: ty, k } = state.graph.transform;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(tx, ty);
    ctx.scale(k, k);

    // Draw Edges
    for (const edge of state.graph.edges) {
      const u = edge.sourceNode;
      const v = edge.targetNode;
      ctx.beginPath();
      ctx.moveTo(u.x, u.y);
      ctx.lineTo(v.x, v.y);
      ctx.strokeStyle = '#38bdf8';
      ctx.globalAlpha = 0.35;
      ctx.lineWidth = Math.max(1, (edge.weight || 1) * 1.5);
      ctx.stroke();

      // Edge relationship label (LOD threshold)
      if (k > 0.8 && edge.schema) {
        const mx = (u.x + v.x) / 2;
        const my = (u.y + v.y) / 2;
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px Inter, sans-serif';
        ctx.fillText(edge.schema, mx, my);
      }
    }
    ctx.globalAlpha = 1.0;

    // Schema color map
    const schemaColors = {
      Domain: '#38bdf8',
      Subdomain: '#0284c7',
      IPv4Address: '#f59e0b',
      AutonomousSystem: '#8b5cf6',
      Company: '#10b981',
      Vulnerability: '#ef4444',
      Email: '#ec4899'
    };

    // Draw Nodes
    for (const node of state.graph.nodes) {
      const color = schemaColors[node.schema] || '#38bdf8';
      const isSelected = state.graph.selectedNode?.id === node.id;

      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      if (isSelected) {
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 3;
        ctx.stroke();
      } else {
        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Draw Node Label
      ctx.fillStyle = '#f8fafc';
      ctx.font = isSelected ? 'bold 12px Inter, sans-serif' : '11px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(node.label || node.id, node.x, node.y + node.radius + 14);
    }

    ctx.restore();
  }

  function renderGraphSvg() {
    const svg = document.getElementById('graph-svg');
    if (!svg) return;
    const { x: tx, y: ty, k } = state.graph.transform;
    svg.innerHTML = '';

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('transform', `translate(${tx}, ${ty}) scale(${k})`);

    // Edges
    for (const edge of state.graph.edges) {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', edge.sourceNode.x);
      line.setAttribute('y1', edge.sourceNode.y);
      line.setAttribute('x2', edge.targetNode.x);
      line.setAttribute('y2', edge.targetNode.y);
      line.setAttribute('stroke', '#38bdf8');
      line.setAttribute('stroke-opacity', '0.4');
      line.setAttribute('stroke-width', '1.5');
      g.appendChild(line);
    }

    // Nodes
    for (const node of state.graph.nodes) {
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', node.x);
      circle.setAttribute('cy', node.y);
      circle.setAttribute('r', node.radius);
      circle.setAttribute('fill', '#38bdf8');
      circle.setAttribute('stroke', '#0f172a');
      circle.setAttribute('stroke-width', '2');
      circle.style.cursor = 'pointer';
      circle.addEventListener('click', () => inspectNode(node));
      g.appendChild(circle);

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', node.x);
      text.setAttribute('y', node.y + node.radius + 12);
      text.setAttribute('fill', '#f8fafc');
      text.setAttribute('font-size', '10');
      text.setAttribute('text-anchor', 'middle');
      text.textContent = node.label || node.id;
      g.appendChild(text);
    }

    svg.appendChild(g);
  }

  function onGraphMouseDown(e) {
    const canvas = document.getElementById('graph-canvas');
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const { x: tx, y: ty, k } = state.graph.transform;
    const worldX = (mouseX - tx) / k;
    const worldY = (mouseY - ty) / k;

    // Check if clicked a node
    let clickedNode = null;
    for (let i = state.graph.nodes.length - 1; i >= 0; i--) {
      const node = state.graph.nodes[i];
      const dist = Math.hypot(node.x - worldX, node.y - worldY);
      if (dist <= node.radius) {
        clickedNode = node;
        break;
      }
    }

    if (clickedNode) {
      state.graph.draggedNode = clickedNode;
      state.graph.selectedNode = clickedNode;
      inspectNode(clickedNode);
      renderGraph();
    } else {
      state.graph.isDragging = true;
      state.graph.dragStart = { x: mouseX - tx, y: mouseY - ty };
    }
  }

  function onGraphMouseMove(e) {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (state.graph.draggedNode) {
      const { x: tx, y: ty, k } = state.graph.transform;
      state.graph.draggedNode.x = (mouseX - tx) / k;
      state.graph.draggedNode.y = (mouseY - ty) / k;
      renderGraph();
    } else if (state.graph.isDragging) {
      state.graph.transform.x = mouseX - state.graph.dragStart.x;
      state.graph.transform.y = mouseY - state.graph.dragStart.y;
      renderGraph();
    }
  }

  function onGraphMouseUp() {
    state.graph.isDragging = false;
    state.graph.draggedNode = null;
  }

  function onGraphWheel(e) {
    e.preventDefault();
    const canvas = document.getElementById('graph-canvas');
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    const newK = Math.max(0.1, Math.min(6, state.graph.transform.k * zoomFactor));

    state.graph.transform.x = mouseX - (mouseX - state.graph.transform.x) * (newK / state.graph.transform.k);
    state.graph.transform.y = mouseY - (mouseY - state.graph.transform.y) * (newK / state.graph.transform.k);
    state.graph.transform.k = newK;

    renderGraph();
  }

  async function inspectNode(node) {
    const container = document.getElementById('inspector-content');
    if (!container) return;

    try {
      const details = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/graph/node/${node.id}`);
      const b = (details.belief_score || 0).toFixed(2);
      const d = (details.disbelief_score || 0).toFixed(2);
      const u = (details.uncertainty_score || 1).toFixed(2);

      let predictedLinksHtml = '<p class="text-sm text-muted">No high-probability missing links predicted.</p>';
      if (details.predicted_missing_links && details.predicted_missing_links.length > 0) {
        predictedLinksHtml = '<ul class="predicted-links-list">';
        details.predicted_missing_links.forEach((link) => {
          predictedLinksHtml += `
            <li>
              <span>${escapeHtml(link.target_label || link.target_id)}</span>
              <span class="badge badge-warning">AA: ${(link.score || 0).toFixed(2)}</span>
            </li>
          `;
        });
        predictedLinksHtml += '</ul>';
      }

      container.innerHTML = `
        <div class="inspector-item">
          <label>Display Label:</label>
          <h4>${escapeHtml(details.display_label || details.canonical_value)}</h4>
        </div>
        <div class="inspector-item">
          <label>FTM Schema:</label>
          <span class="badge badge-info">${escapeHtml(details.ftm_schema)}</span>
        </div>
        <div class="inspector-item">
          <label>Subjective Logic Belief Bar:</label>
          <div class="belief-bar">
            <span class="belief-part b" style="width: ${b * 100}%" title="Belief: ${b}"></span>
            <span class="belief-part d" style="width: ${d * 100}%" title="Disbelief: ${d}"></span>
            <span class="belief-part u" style="width: ${u * 100}%" title="Uncertainty: ${u}"></span>
          </div>
          <small class="text-muted">b: ${b} | d: ${d} | u: ${u} (a: 0.50)</small>
        </div>
        <div class="inspector-item">
          <label>Leiden Community / Centrality:</label>
          <p>Community ID: <code>${details.leiden_community_id || 0}</code> | IEF-PageRank: <code>${(details.pagerank || 0).toFixed(4)}</code></p>
        </div>
        <div class="inspector-item">
          <label>Adamic-Adar Predicted Missing Links:</label>
          ${predictedLinksHtml}
        </div>
        <button id="btn-pivot-node" class="btn btn-primary btn-sm btn-block mt-2">Pivot OSINT Playbook on Node</button>
      `;

      document.getElementById('btn-pivot-node')?.addEventListener('click', () => {
        switchView('view-collect');
        const targetInput = document.getElementById('playbook-target-input');
        if (targetInput) targetInput.value = details.canonical_value;
      });
    } catch (err) {
      console.error('Failed to load node details:', err);
    }
  }

  // --- VIEW 5: Entity Resolution Workbench ---

  async function loadResolutionData() {
    try {
      const candidates = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/resolution/candidates`);
      const tbodyCand = document.querySelector('#table-er-candidates tbody');
      if (tbodyCand) {
        tbodyCand.innerHTML = '';
        if (candidates.length === 0) {
          tbodyCand.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No duplicate candidate pairs found.</td></tr>';
        } else {
          candidates.forEach((cand) => {
            const tr = document.createElement('tr');
            let waterfallHtml = '<div class="waterfall-container">';
            if (cand.waterfall && cand.waterfall.factors) {
              cand.waterfall.factors.forEach((f) => {
                const isPos = f.log2_weight >= 0;
                waterfallHtml += `
                  <span class="waterfall-badge ${isPos ? 'pos' : 'neg'}" title="${escapeHtml(f.explanation)}">
                    ${f.feature}: ${isPos ? '+' : ''}${f.log2_weight.toFixed(1)}
                  </span>
                `;
              });
            }
            waterfallHtml += '</div>';

            tr.innerHTML = `
              <td><strong>${escapeHtml(cand.entity_a.label)}</strong></td>
              <td><strong>${escapeHtml(cand.entity_b.label)}</strong></td>
              <td><code>${(cand.fs_log2_weight || 0).toFixed(2)}</code></td>
              <td><strong>${((cand.match_probability || 0) * 100).toFixed(1)}%</strong></td>
              <td><span class="badge ${cand.classification === 'MATCH' ? 'badge-success' : 'badge-warning'}">${escapeHtml(cand.classification)}</span></td>
              <td>${waterfallHtml}</td>
              <td>
                <button class="btn btn-xs btn-primary btn-merge" data-winner="${cand.entity_a.id}" data-absorbed="${cand.entity_b.id}">Merge</button>
              </td>
            `;
            tbodyCand.appendChild(tr);
          });

          tbodyCand.querySelectorAll('.btn-merge').forEach((btn) => {
            btn.addEventListener('click', async () => {
              const winner_id = btn.getAttribute('data-winner');
              const absorbed_id = btn.getAttribute('data-absorbed');
              try {
                await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/resolution/merge`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ winner_id, absorbed_id })
                });
                showToast('Entities merged with 100% reversible ledger!', 'success');
                loadResolutionData();
                loadDashboardData();
              } catch (err) {
                showToast('Merge failed: ' + err.message, 'danger');
              }
            });
          });
        }
      }

      // Load Reversible Merge Ledger
      const ledger = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/resolution/ledger`);
      const tbodyLedger = document.querySelector('#table-er-ledger tbody');
      if (tbodyLedger) {
        tbodyLedger.innerHTML = '';
        if (ledger.length === 0) {
          tbodyLedger.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No merges recorded in ledger yet.</td></tr>';
        } else {
          ledger.forEach((entry) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td><code>${escapeHtml(entry.merge_id.substring(0, 8))}</code></td>
              <td>${escapeHtml(entry.winner_id)}</td>
              <td>${escapeHtml(entry.absorbed_id)}</td>
              <td>${((entry.match_probability || 1) * 100).toFixed(1)}%</td>
              <td><span class="badge ${entry.status === 'MERGED' ? 'badge-info' : 'badge-muted'}">${escapeHtml(entry.status)}</span></td>
              <td>${escapeHtml(entry.merged_at ? entry.merged_at.substring(0, 19).replace('T', ' ') : 'N/A')}</td>
              <td>
                ${entry.status === 'MERGED' ? `<button class="btn btn-xs btn-warning btn-unmerge" data-id="${entry.merge_id}">Unmerge</button>` : '<span class="text-muted">Unmerged</span>'}
              </td>
            `;
            tbodyLedger.appendChild(tr);
          });

          tbodyLedger.querySelectorAll('.btn-unmerge').forEach((btn) => {
            btn.addEventListener('click', async () => {
              const merge_id = btn.getAttribute('data-id');
              try {
                await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/resolution/unmerge`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ merge_id })
                });
                showToast('Merge reverted successfully!', 'success');
                loadResolutionData();
                loadDashboardData();
              } catch (err) {
                showToast('Unmerge failed: ' + err.message, 'danger');
              }
            });
          });
        }
      }
    } catch (err) {
      console.error('Failed to load resolution workbench:', err);
    }
  }

  // --- VIEW 6: Timeline & Bursts ---

  async function loadTimelineData() {
    try {
      const data = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/timeline`);
      const banner = document.getElementById('timeline-burst-banner');
      if (banner) {
        if (data.burst_detected) {
          banner.classList.remove('hidden');
          banner.innerHTML = `⚠️ <strong>Burst Intelligence Alert:</strong> Significant temporal activity burst detected on ${escapeHtml(data.burst_date)} with Kleinberg Z-score of <code>${(data.burst_z_score || 0).toFixed(2)}</code> (Threshold ≥ 2.5).`;
        } else {
          banner.classList.add('hidden');
        }
      }

      // Render Bar Chart Distribution
      const chartContainer = document.getElementById('timeline-chart-container');
      if (chartContainer) {
        chartContainer.innerHTML = '';
        const events = data.events || [];
        const maxCount = Math.max(...events.map((e) => e.count || 1), 5);

        events.forEach((ev) => {
          const bar = document.createElement('div');
          bar.className = 'timeline-bar-column';
          const heightPercent = Math.max(8, ((ev.count || 0) / maxCount) * 100);
          const isBurst = ev.burst_status === 'BURST';

          bar.innerHTML = `
            <div class="timeline-bar ${isBurst ? 'burst' : ''}" style="height: ${heightPercent}%" title="${ev.date}: ${ev.count} events (Z: ${(ev.z_score || 0).toFixed(1)})"></div>
            <div class="timeline-bar-label">${escapeHtml(ev.date ? ev.date.substring(5) : '')}</div>
          `;
          chartContainer.appendChild(bar);
        });
      }

      // Render Table
      const tbody = document.querySelector('#table-timeline-events tbody');
      if (tbody) {
        tbody.innerHTML = '';
        if (!data.events || data.events.length === 0) {
          tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No timeline events recorded yet.</td></tr>';
        } else {
          data.events.forEach((ev) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td><strong>${escapeHtml(ev.date)}</strong></td>
              <td>${ev.count || 0}</td>
              <td><code>${(ev.z_score || 0).toFixed(2)}</code></td>
              <td><span class="badge ${ev.burst_status === 'BURST' ? 'badge-danger' : 'badge-info'}">${escapeHtml(ev.burst_status || 'NORMAL')}</span></td>
            `;
            tbody.appendChild(tr);
          });
        }
      }
    } catch (err) {
      console.error('Failed to load timeline:', err);
    }
  }

  // --- VIEW 7: Geospatial & Clusters ---

  async function loadGeospatialData() {
    try {
      const data = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/geospatial`);
      const canvas = document.getElementById('geo-map-canvas');
      if (!canvas) return;
      canvas.width = canvas.parentElement.clientWidth || 600;
      canvas.height = 360;
      const ctx = canvas.getContext('2d');

      // Draw Equirectangular Graticule World Map
      ctx.fillStyle = '#0b1120';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Grid lines
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 1;
      for (let lon = -180; lon <= 180; lon += 30) {
        const x = ((lon + 180) / 360) * canvas.width;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let lat = -90; lat <= 90; lat += 30) {
        const y = ((90 - lat) / 180) * canvas.height;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Draw HDBSCAN Cluster Circles
      if (data.clusters) {
        data.clusters.forEach((cl) => {
          const cx = ((cl.center_lon + 180) / 360) * canvas.width;
          const cy = ((90 - cl.center_lat) / 180) * canvas.height;
          const r = Math.max(16, (cl.radius_km || 10) * 0.4);

          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, 2 * Math.PI);
          ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
          ctx.fill();
          ctx.strokeStyle = '#ef4444';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        });
      }

      // Draw Points
      if (data.entities) {
        data.entities.forEach((ent) => {
          const x = ((ent.longitude + 180) / 360) * canvas.width;
          const y = ((90 - ent.latitude) / 180) * canvas.height;

          ctx.beginPath();
          ctx.arc(x, y, 5, 0, 2 * Math.PI);
          ctx.fillStyle = '#38bdf8';
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1;
          ctx.stroke();
        });
      }

      // Populate Table
      const tbody = document.querySelector('#table-geo-entities tbody');
      if (tbody) {
        tbody.innerHTML = '';
        if (!data.entities || data.entities.length === 0) {
          tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">No geolocated observables recorded yet.</td></tr>';
        } else {
          data.entities.forEach((ent) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td><strong>${escapeHtml(ent.label || ent.canonical_value)}</strong></td>
              <td><code>${ent.latitude.toFixed(4)}, ${ent.longitude.toFixed(4)}</code></td>
              <td><span class="badge badge-info">Cluster #${ent.cluster_id !== undefined ? ent.cluster_id : '0'}</span></td>
            `;
            tbody.appendChild(tr);
          });
        }
      }
    } catch (err) {
      console.error('Failed to load geospatial data:', err);
    }
  }

  // --- VIEW 8: W3C PROV Lineage Ledger ---

  async function loadProvenanceData() {
    try {
      const artifacts = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/provenance`);
      const tbody = document.querySelector('#table-provenance tbody');
      if (!tbody) return;
      tbody.innerHTML = '';

      if (artifacts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No W3C PROV artifacts recorded yet.</td></tr>';
        return;
      }

      artifacts.forEach((art) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><code>${escapeHtml(art.id.substring(0, 10))}</code></td>
          <td><strong>${escapeHtml(art.source_name)}</strong></td>
          <td><span class="badge badge-info">${escapeHtml(art.upstream_lineage_family || 'Independent')}</span></td>
          <td><span class="badge badge-primary">${escapeHtml(art.admiralty_rating || 'B2')}</span></td>
          <td>${escapeHtml(art.title || art.summary || 'Evidence Capture')}</td>
          <td><code>${escapeHtml(art.payload_sha256 ? art.payload_sha256.substring(0, 16) : '')}...</code></td>
          <td>${escapeHtml(art.observed_at ? art.observed_at.substring(0, 19).replace('T', ' ') : 'N/A')}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error('Failed to load provenance:', err);
    }
  }

  // --- VIEW 9: GraphRAG & Formal Reports ---

  function initAiHandlers() {
    const btnAiQuery = document.getElementById('btn-ai-query');
    const btnReport = document.getElementById('btn-generate-report');
    const responseBox = document.getElementById('ai-response-box');

    btnAiQuery?.addEventListener('click', async () => {
      const query = document.getElementById('ai-query-input')?.value.trim();
      if (!query) {
        showToast('Please enter an intelligence query.', 'warning');
        return;
      }
      btnAiQuery.disabled = true;
      btnAiQuery.textContent = 'Compiling Subgraph & Verifying Citations...';
      try {
        const res = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/ai/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, provider: 'local_graphrag' })
        });
        renderMarkdownResponse(responseBox, res.response || res.briefing || 'No briefing returned.');
        showToast('Intelligence synthesis complete with verified citations!', 'success');
      } catch (err) {
        showToast('GraphRAG query failed: ' + err.message, 'danger');
      } finally {
        btnAiQuery.disabled = false;
        btnAiQuery.textContent = 'Generate Epistemically Stratified Briefing';
      }
    });

    btnReport?.addEventListener('click', async () => {
      const title = document.getElementById('report-title-input')?.value.trim() || 'Investigation Assessment Report';
      const query = document.getElementById('ai-query-input')?.value.trim() || 'Comprehensive investigation findings summary';

      btnReport.disabled = true;
      btnReport.textContent = 'Generating & Saving Report...';
      try {
        const res = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/ai/report`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, query, provider: 'local_graphrag' })
        });
        renderMarkdownResponse(responseBox, res.report_markdown || 'Report successfully compiled.');
        showToast('Report generated and saved to case file!', 'success');
      } catch (err) {
        showToast('Report generation failed: ' + err.message, 'danger');
      } finally {
        btnReport.disabled = false;
        btnReport.textContent = 'Save Formal Intelligence Report';
      }
    });
  }

  function renderMarkdownResponse(targetElement, markdownText) {
    if (!targetElement) return;
    // Simple markdown renderer for headers, bold, and citations
    let html = escapeHtml(markdownText)
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/gim, '<em>$1</em>')
      .replace(/\n\n/gim, '<p></p>')
      .replace(/\n/gim, '<br>');

    // Highlight [ev_xxxx] citations
    html = html.replace(/\[(ev_[a-zA-Z0-9_-]+)\]/g, '<span class="badge badge-success citation-badge">[$1]</span>');
    targetElement.innerHTML = html;
  }

  // --- VIEW 10: Tasks & Circuits ---

  async function loadTasksData() {
    try {
      const tasks = await apiRequest(`/api/workspaces/${state.currentWorkspaceId}/tasks`);
      const tbody = document.querySelector('#table-tasks tbody');
      if (!tbody) return;
      tbody.innerHTML = '';

      if (tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No collection tasks recorded yet.</td></tr>';
        return;
      }

      tasks.forEach((t) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><code>${escapeHtml(t.id ? t.id.substring(0, 8) : '')}</code></td>
          <td><strong>${escapeHtml(t.connector_name || 'modular_playbook')}</strong></td>
          <td><code>${escapeHtml(t.target_observable || 'N/A')}</code></td>
          <td>${t.pivot_depth !== undefined ? t.pivot_depth : 0}</td>
          <td><span class="badge ${t.status === 'COMPLETED' ? 'badge-success' : 'badge-warning'}">${escapeHtml(t.status || 'READY')}</span></td>
          <td>${t.entities_found || 0}</td>
          <td>${t.claims_found || 0}</td>
          <td>${t.staged_count || 0}</td>
          <td>${escapeHtml(t.started_at ? t.started_at.substring(0, 19).replace('T', ' ') : 'N/A')}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error('Failed to load tasks:', err);
    }
  }

  // --- VIEW 11: Vault & Settings ---

  async function loadSettingsData() {
    try {
      const settings = await apiRequest('/api/settings');
      state.settings = settings;

      const opsecSelect = document.getElementById('settings-opsec-select');
      const offlineSelect = document.getElementById('settings-offline-select');
      const aiSelect = document.getElementById('settings-ai-select');

      if (opsecSelect) opsecSelect.value = settings.opsec_mode || 'STANDARD';
      if (offlineSelect) offlineSelect.value = settings.offline_mode ? 'true' : 'false';
      if (aiSelect) aiSelect.value = settings.ai_provider || 'local_graphrag';

      // Load 24-connector vault
      const vault = await apiRequest('/api/vault');
      const tbody = document.querySelector('#table-connector-vault tbody');
      if (!tbody) return;
      tbody.innerHTML = '';

      vault.forEach((conn) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${escapeHtml(conn.name)}</strong></td>
          <td><span class="badge badge-info">${escapeHtml(conn.category || 'Recon')}</span></td>
          <td>${conn.requires_key ? '<span class="badge badge-warning">Required</span>' : '<span class="badge badge-success">Optional/No</span>'}</td>
          <td><code>${escapeHtml(conn.masked_key || 'None Configured')}</code></td>
          <td>
            <input type="password" class="form-input form-input-sm vault-key-input" placeholder="New API Key..." data-name="${conn.name}">
          </td>
          <td>${conn.rate_limit_rpm || 60}</td>
          <td><span class="badge ${conn.circuit_breaker_status === 'READY' ? 'badge-success' : 'badge-danger'}">${escapeHtml(conn.circuit_breaker_status || 'READY')}</span></td>
          <td>
            <button class="btn btn-xs btn-primary btn-save-key" data-name="${conn.name}">Update</button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      tbody.querySelectorAll('.btn-save-key').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const name = btn.getAttribute('data-name');
          const input = tbody.querySelector(`.vault-key-input[data-name="${name}"]`);
          const apiKey = input?.value.trim();
          if (!apiKey) {
            showToast('Enter an API key to save in the Fernet vault.', 'warning');
            return;
          }

          try {
            await apiRequest('/api/vault', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ connector_name: name, api_key: apiKey })
            });
            showToast(`Key for ${name} securely saved in 256-bit Fernet vault!`, 'success');
            loadSettingsData();
          } catch (err) {
            showToast('Failed to save vault key: ' + err.message, 'danger');
          }
        });
      });
    } catch (err) {
      console.error('Failed to load settings & vault:', err);
    }
  }

  function initSettingsHandlers() {
    const btnSaveSettings = document.getElementById('btn-save-settings');
    btnSaveSettings?.addEventListener('click', async () => {
      const opsec = document.getElementById('settings-opsec-select')?.value;
      const offline = document.getElementById('settings-offline-select')?.value === 'true';
      const ai = document.getElementById('settings-ai-select')?.value;

      try {
        await apiRequest('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            opsec_mode: opsec,
            offline_mode: offline,
            ai_provider: ai
          })
        });
        showToast('Runtime policies updated successfully!', 'success');
        loadSettingsData();
      } catch (err) {
        showToast('Failed to save settings: ' + err.message, 'danger');
      }
    });
  }

})();
