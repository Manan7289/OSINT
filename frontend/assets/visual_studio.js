/**
 * frontend/assets/visual_studio.js - Privacy-Preserving Visual Intelligence Studio
 * LocalOSINT v3.0 Global Intelligence Command Centre
 */

class VisualStudioEngine {
  constructor() {
    this.currentImageBase64 = null;
    this.currentAnalysisResult = null;
    this.currentFilename = "uploaded_photo.jpg";
  }

  init() {
    this.bindDropzone();
    this.bindActionButtons();
    this.bindVerificationForms();
    this.bindWebcamCapture();
    this.fetchAndRenderGallery();
  }

  bindDropzone() {
    const dropzone = document.getElementById('visual-dropzone');
    const fileInput = document.getElementById('visual-file-input');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        this.handleFileSelected(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        this.handleFileSelected(e.target.files[0]);
      }
    });
  }

  handleFileSelected(file) {
    if (!file.type.startsWith('image/')) {
      alert("Please upload an image file (JPEG, PNG, WebP).");
      return;
    }
    this.currentFilename = file.name;
    const reader = new FileReader();
    reader.onload = (e) => {
      this.currentImageBase64 = e.target.result;
      this.analyzeCurrentImage();
    };
    reader.readAsDataURL(file);
  }

  bindActionButtons() {
    const btnOpen = document.getElementById('btn-open-visual-studio');
    const modal = document.getElementById('modal-visual-studio');
    const btnClose = document.getElementById('btn-close-visual-studio');

    if (btnOpen && modal) {
      btnOpen.addEventListener('click', () => {
        modal.classList.remove('hidden');
        this.fetchAndRenderGallery();
      });
    }

    if (btnClose && modal) {
      btnClose.addEventListener('click', () => {
        modal.classList.add('hidden');
      });
    }

    const toggleBlur = document.getElementById('toggle-bystander-blur');
    if (toggleBlur) {
      toggleBlur.addEventListener('change', () => {
        if (this.currentImageBase64) {
          this.analyzeCurrentImage();
        }
      });
    }
  }

  async analyzeCurrentImage() {
    if (!this.currentImageBase64) return;

    const toggleBlur = document.getElementById('toggle-bystander-blur');
    const blurBystanders = toggleBlur ? toggleBlur.checked : true;

    const statusEl = document.getElementById('visual-analysis-status');
    if (statusEl) statusEl.textContent = 'Extracting EXIF forensics & running YuNet face detection...';

    try {
      const res = await fetch(`/api/v1/visual/analyze?blur_bystanders=${blurBystanders}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_b64: this.currentImageBase64,
          filename: this.currentFilename,
          blur_bystanders: blurBystanders
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Analysis failed");
      }

      const data = await res.json();
      this.currentAnalysisResult = data;
      this.renderAnalysisResult(data);
    } catch (e) {
      console.error("Visual analysis error:", e);
      if (statusEl) statusEl.textContent = `Analysis error: ${e.message}`;
    }
  }

  renderAnalysisResult(data) {
    const statusEl = document.getElementById('visual-analysis-status');
    if (statusEl) statusEl.textContent = 'Analysis complete.';

    const previewContainer = document.getElementById('visual-preview-container');
    if (previewContainer) previewContainer.classList.remove('hidden');

    // Redacted Image Preview
    const imgEl = document.getElementById('visual-processed-img');
    if (imgEl) {
      imgEl.src = `data:image/jpeg;base64,${data.redacted_image_b64 || ''}`;
    }

    // Quality Scorecard
    const v = data.vision || {};
    const f = data.forensics || {};

    const sharpnessEl = document.getElementById('metric-sharpness');
    if (sharpnessEl) sharpnessEl.textContent = (v.laplacian_sharpness || 0).toFixed(1);

    const gradeBadge = document.getElementById('badge-quality-grade');
    if (gradeBadge) {
      gradeBadge.textContent = v.quality_grade || 'MODERATE';
      gradeBadge.className = 'badge-telemetry';
      if (v.quality_grade === 'HIGH_SHARPNESS') gradeBadge.classList.add('live');
      else if (v.quality_grade === 'MODERATE') gradeBadge.classList.add('bootstrap');
      else gradeBadge.classList.add('sanction');
    }

    const facesCountEl = document.getElementById('metric-faces-count');
    if (facesCountEl) facesCountEl.textContent = `${v.faces_detected || 0} faces (${v.bystanders_blurred ? 'Redacted' : 'Raw'})`;

    // Forensics table
    const tableBody = document.getElementById('forensics-table-body');
    if (tableBody) {
      const gps = f.gps || {};
      const exif = f.exif || {};
      tableBody.innerHTML = `
        <tr><td>Filename</td><td>${data.filename}</td></tr>
        <tr><td>SHA-256</td><td style="word-break:break-all;"><code>${f.sha256_hash ? f.sha256_hash.substring(0, 24) : 'N/A'}...</code></td></tr>
        <tr><td>pHash (64-bit DCT)</td><td><code>${f.phash_64 || '0000000000000000'}</code></td></tr>
        <tr><td>Camera Model</td><td>${exif.Model || exif.Make || 'Not Present'}</td></tr>
        <tr><td>DateTime Original</td><td>${exif.DateTimeOriginal || 'Not Present'}</td></tr>
        <tr><td>C2PA JUMBF Manifest</td><td>${f.c2pa?.present ? '✓ Valid Provenance Manifest' : 'None Detected'}</td></tr>
        <tr>
          <td>GPS Coordinates</td>
          <td>
            ${gps.lat != null && gps.lon != null 
              ? `${gps.lat.toFixed(5)}°, ${gps.lon.toFixed(5)}° <button id="btn-fly-exif-gps" class="btn btn-sm btn-outline" style="margin-left:6px;">Fly to Location</button>` 
              : 'No GPS EXIF Tags'}
          </td>
        </tr>
      `;

      const btnFlyGps = document.getElementById('btn-fly-exif-gps');
      if (btnFlyGps && gps.lat != null && gps.lon != null) {
        btnFlyGps.addEventListener('click', () => {
          if (window.globeMap) {
            window.globeMap.flyToCoords(gps.lat, gps.lon, 14);
            const modal = document.getElementById('modal-visual-studio');
            if (modal) modal.classList.add('hidden');
          }
        });
      }
    }
  }

  bindVerificationForms() {
    // Gallery Enroll Form
    const btnEnroll = document.getElementById('btn-enroll-gallery');
    if (btnEnroll) {
      btnEnroll.addEventListener('click', async () => {
        const nameInput = document.getElementById('enroll-subject-name');
        const purposeInput = document.getElementById('enroll-consent-purpose');
        const consentCheckbox = document.getElementById('enroll-consent-checkbox');

        const name = nameInput ? nameInput.value.trim() : '';
        const purpose = purposeInput ? purposeInput.value.trim() : '';
        const attested = consentCheckbox ? consentCheckbox.checked : false;

        if (!name || !purpose) {
          alert("Subject Name and Documented Consent Purpose are required.");
          return;
        }

        if (!attested) {
          alert("Explicit Consent Attestation checkbox is mandatory for biometric enrollment.");
          return;
        }

        if (!this.currentImageBase64) {
          alert("Please upload a reference image first.");
          return;
        }

        try {
          const res = await fetch('/api/v1/visual/gallery/enroll', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              image_b64: this.currentImageBase64,
              subject_name: name,
              consent_purpose: purpose,
              consent_attestation: attested,
              expiration_days: 90
            })
          });

          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Enrollment failed");
          }

          const out = await res.json();
          alert(`Subject '${out.subject_name}' enrolled successfully into Gallery (Expires in 90 days).`);
          await this.fetchAndRenderGallery();
        } catch (e) {
          alert(`Enrollment rejected: ${e.message}`);
        }
      });
    }

    const btnRefresh = document.getElementById('btn-refresh-gallery');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', () => this.fetchAndRenderGallery());
    }

    // Probe Verify Form
    const btnVerify = document.getElementById('btn-verify-probe');
    if (btnVerify) {
      btnVerify.addEventListener('click', async () => {
        const reasonInput = document.getElementById('verify-consent-reason');
        const consentCheckbox = document.getElementById('verify-consent-checkbox');

        const reason = reasonInput ? reasonInput.value.trim() : '';
        const attested = consentCheckbox ? consentCheckbox.checked : false;

        if (!attested || !reason) {
          alert("Legal Consent Attestation and Justification Reason are mandatory to perform biometric matching.");
          return;
        }

        if (!this.currentImageBase64) {
          alert("Please upload a probe photo first.");
          return;
        }

        const outContainer = document.getElementById('verify-result-output');
        if (outContainer) outContainer.textContent = 'Running SFace 128-D cosine verification...';

        try {
          const res = await fetch('/api/v1/visual/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              probe_image_b64: this.currentImageBase64,
              consent_reason: reason
            })
          });

          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Verification failed");
          }

          const data = await res.json();
          if (outContainer) {
            if (data.matched) {
              outContainer.innerHTML = `
                <div style="background:rgba(16,185,129,0.15); border:1px solid #10B981; padding:10px; border-radius:4px; color:#6EE7B7;">
                  <strong>✓ MATCH CONFIRMED</strong><br>
                  Subject: <strong>${data.subject_name}</strong><br>
                  Cosine Similarity: <strong>${(data.similarity_score || 0).toFixed(4)}</strong> (Threshold: ${data.match_threshold})<br>
                  Audit Ref: <code>${data.audit_log_id}</code>
                </div>
              `;
            } else {
              outContainer.innerHTML = `
                <div style="background:rgba(245,158,11,0.15); border:1px solid #F59E0B; padding:10px; border-radius:4px; color:#FCD34D;">
                  <strong>NO MATCH FOUND</strong><br>
                  Closest similarity: ${(data.best_similarity || 0).toFixed(4)} below match threshold ${data.match_threshold}.
                </div>
              `;
            }
          }
        } catch (e) {
          if (outContainer) {
            outContainer.innerHTML = `
              <div style="background:rgba(239,68,68,0.15); border:1px solid #EF4444; padding:10px; border-radius:4px; color:#FCA5A5;">
                <strong>MATCHING BLOCKED</strong><br>
                ${e.message}
              </div>
            `;
          }
        }
      });
    }
  }

  bindWebcamCapture() {
    const btn = document.getElementById('btn-webcam-capture');
    if (!btn) return;

    btn.addEventListener('click', async () => {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          alert("Webcam capture is not supported in this browser environment.");
          return;
        }
        btn.textContent = '⏳ Accessing Camera...';
        btn.disabled = true;

        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
        const video = document.createElement('video');
        video.srcObject = stream;
        video.play();

        await new Promise(resolve => {
          video.onloadedmetadata = () => resolve();
        });

        // Capture frame to canvas
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Stop stream tracks
        stream.getTracks().forEach(track => track.stop());

        this.currentImageBase64 = canvas.toDataURL('image/jpeg', 0.92);
        this.currentFilename = `webcam_frame_${Date.now()}.jpg`;

        btn.textContent = '📷 Live Webcam Frame Capture';
        btn.disabled = false;

        await this.analyzeCurrentImage();
      } catch (err) {
        console.warn("Webcam capture error:", err);
        btn.textContent = '📷 Live Webcam Frame Capture';
        btn.disabled = false;
        alert(`Webcam access error: ${err.message || 'Permission denied or no camera device found.'}`);
      }
    });
  }

  async fetchAndRenderGallery() {
    const container = document.getElementById('gallery-subjects-container');
    if (!container) return;

    try {
      const res = await fetch('/api/v1/visual/gallery');
      if (!res.ok) throw new Error("Failed to load consented gallery");
      const subjects = await res.json();

      container.innerHTML = '';
      if (!subjects || subjects.length === 0) {
        container.innerHTML = '<div style="color:var(--text-dim); font-size:11px; padding:10px;">No enrolled reference subjects in consented gallery.</div>';
        return;
      }

      subjects.forEach(sub => {
        const card = document.createElement('div');
        card.className = 'gallery-subject-card';
        
        let daysLeft = 90;
        if (sub.enrolled_at) {
          const enrolledDate = new Date(sub.enrolled_at);
          const diffDays = Math.max(0, 90 - Math.floor((Date.now() - enrolledDate.getTime()) / (1000 * 60 * 60 * 24)));
          daysLeft = diffDays;
        }

        card.innerHTML = `
          <div class="gallery-card-header">
            <div>
              <strong style="color:var(--text-main); font-size:12px;">${sub.subject_name || 'Authorized Subject'}</strong>
              <div style="font-size:10px; color:var(--text-muted);">${sub.consent_purpose || 'General OSINT Verification'}</div>
            </div>
            <button class="btn-revoke-consent" data-id="${sub.gallery_id}" title="Revoke biometric enrollment">Revoke</button>
          </div>
          <div class="gallery-card-body">
            <span>Enrolled: <strong>${(sub.enrolled_at || '').substring(0, 10)}</strong></span>
            <span>Retention: <strong style="color:${daysLeft < 15 ? '#EF4444' : '#10B981'};">${daysLeft} days left</strong></span>
            <div style="font-size:9px; color:var(--text-dim); word-break:break-all; margin-top:2px;">
              ID: <code>${sub.gallery_id ? sub.gallery_id.substring(0, 18) : ''}...</code>
            </div>
          </div>
        `;

        const revokeBtn = card.querySelector('.btn-revoke-consent');
        if (revokeBtn) {
          revokeBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (confirm(`Revoke biometric enrollment for '${sub.subject_name}'? This will permanently delete their embedding.`)) {
              await this.revokeGallerySubject(sub.gallery_id);
            }
          });
        }

        container.appendChild(card);
      });
    } catch (e) {
      console.warn("Gallery fetch error:", e);
      container.innerHTML = '<div style="color:var(--text-dim); font-size:11px;">Consented gallery status unavailable.</div>';
    }
  }

  async revokeGallerySubject(galleryId) {
    try {
      const res = await fetch(`/api/v1/visual/gallery/${galleryId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error("Revocation failed");
      if (window.app) window.app.showToast("Biometric consent revoked and record deleted.", "success");
      await this.fetchAndRenderGallery();
    } catch (e) {
      alert(`Revocation failed: ${e.message}`);
    }
  }
}

window.visualStudio = new VisualStudioEngine();
