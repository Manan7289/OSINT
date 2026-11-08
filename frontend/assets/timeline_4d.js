/**
 * frontend/assets/timeline_4d.js - 4D Spatiotemporal Time Scrubber Engine
 * LocalOSINT v3.0 Global Intelligence Command Centre
 */

class Timeline4DEngine {
  constructor() {
    this.isPlaying = false;
    this.playbackSpeed = 1; // 1x, 10x, 60x
    this.timerId = null;
    this.totalMinutesSpan = 24 * 60; // 24 hours
    this.currentOffsetMinutes = 0; // 0 = now (LIVE), -60 = 1 hour ago
    this.nowAnchor = new Date();
    this.isHistorical = false;
  }

  init() {
    this.nowAnchor = new Date();
    this.bindControls();
    this.updateReadout();
  }

  bindControls() {
    const slider = document.getElementById('scrubber-slider');
    const btnPlay = document.getElementById('btn-timeline-play');
    const selectSpeed = document.getElementById('select-playback-speed');
    const btnLive = document.getElementById('btn-timeline-live');

    if (slider) {
      slider.min = -this.totalMinutesSpan;
      slider.max = 0;
      slider.value = 0;

      slider.addEventListener('input', (e) => {
        this.currentOffsetMinutes = parseInt(e.target.value, 10);
        this.handleSliderChange();
      });
    }

    if (btnPlay) {
      btnPlay.addEventListener('click', () => {
        this.togglePlay();
      });
    }

    if (selectSpeed) {
      selectSpeed.addEventListener('change', (e) => {
        this.playbackSpeed = parseInt(e.target.value, 10) || 1;
      });
    }

    if (btnLive) {
      btnLive.addEventListener('click', () => {
        this.returnToLive();
      });
    }
  }

  togglePlay() {
    this.isPlaying = !this.isPlaying;
    const btnPlay = document.getElementById('btn-timeline-play');
    if (btnPlay) {
      btnPlay.innerHTML = this.isPlaying ? '❚❚' : '▶';
      btnPlay.classList.toggle('active', this.isPlaying);
    }

    if (this.isPlaying) {
      this.startPlaybackLoop();
    } else {
      this.stopPlaybackLoop();
    }
  }

  startPlaybackLoop() {
    this.stopPlaybackLoop();
    this.timerId = setInterval(() => {
      if (this.currentOffsetMinutes >= 0) {
        // Reached live now
        this.returnToLive();
        return;
      }
      // Step forward by 1 minute * (playbackSpeed / 2)
      this.currentOffsetMinutes = Math.min(0, this.currentOffsetMinutes + Math.max(1, Math.round(this.playbackSpeed * 0.5)));
      const slider = document.getElementById('scrubber-slider');
      if (slider) slider.value = this.currentOffsetMinutes;
      this.handleSliderChange();
    }, 1000);
  }

  stopPlaybackLoop() {
    if (this.timerId) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
  }

  handleSliderChange() {
    this.isHistorical = this.currentOffsetMinutes < -1;
    this.updateReadout();
    this.debounceFetchReplay();
  }

  returnToLive() {
    this.isPlaying = false;
    this.stopPlaybackLoop();
    this.currentOffsetMinutes = 0;
    this.isHistorical = false;
    
    const slider = document.getElementById('scrubber-slider');
    if (slider) slider.value = 0;
    
    const btnPlay = document.getElementById('btn-timeline-play');
    if (btnPlay) {
      btnPlay.innerHTML = '▶';
      btnPlay.classList.remove('active');
    }

    this.updateReadout();
    if (window.globeMap) {
      window.globeMap.fetchLayers();
    }
  }

  debounceFetchReplay() {
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(() => {
      this.fetchReplayData();
    }, 350);
  }

  async fetchReplayData() {
    if (!this.isHistorical) {
      if (window.globeMap) window.globeMap.fetchLayers();
      return;
    }

    const targetDate = new Date(this.nowAnchor.getTime() + this.currentOffsetMinutes * 60 * 1000);
    const targetIso = targetDate.toISOString();

    try {
      const res = await fetch(`/api/v1/geospatial/replay?timestamp_iso=${encodeURIComponent(targetIso)}&window_minutes=30`);
      if (res.ok) {
        const replayGeoJson = await res.json();
        if (window.globeMap) {
          window.globeMap.layersData = replayGeoJson;
          window.globeMap.renderLayers();
          window.globeMap.updateLayerCounters();
        }
      }
    } catch (e) {
      console.error("Replay fetch error:", e);
    }
  }

  updateReadout() {
    const targetDate = new Date(this.nowAnchor.getTime() + this.currentOffsetMinutes * 60 * 1000);
    const timeStr = targetDate.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';

    const timeReadout = document.getElementById('timeline-time-display');
    if (timeReadout) timeReadout.textContent = timeStr;

    const badge = document.getElementById('timeline-status-badge');
    if (badge) {
      if (this.isHistorical) {
        badge.textContent = 'HISTORICAL REPLAY';
        badge.className = 'badge-telemetry historical';
      } else {
        badge.textContent = 'LIVE TELEMETRY';
        badge.className = 'badge-telemetry live';
      }
    }
  }
}

window.timeline4D = new Timeline4DEngine();
