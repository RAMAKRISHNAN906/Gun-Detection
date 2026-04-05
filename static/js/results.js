/**
 * Results Page JavaScript
 * Loads detection results, populates stats, comparison view,
 * detection details, and AI interpretation.
 */

document.addEventListener('DOMContentLoaded', () => {
    const section = document.querySelector('.results-section');
    if (!section) return;

    const jobId = section.dataset.jobId;
    if (!jobId) return;

    loadResults(jobId);

    // Download PDF
    const dlBtn = document.getElementById('downloadReport');
    if (dlBtn) {
        dlBtn.addEventListener('click', () => {
            window.location.href = `/api/report/${jobId}`;
        });
    }
});

async function loadResults(jobId) {
    try {
        const res = await fetch(`/api/results/${jobId}`);
        const data = await res.json();

        if (data.error) {
            console.error('Results error:', data.error);
            return;
        }

        populateResults(data);
    } catch (e) {
        console.error('Failed to load results:', e);
    }
}

function populateResults(data) {
    const isVideo = data.file_type === 'video';

    // ── Alert Banner ───────────────────────────────────────────
    const banner = document.getElementById('alertBanner');
    const alertText = document.getElementById('alertText');
    const threatLevel = isVideo ? data.max_threat_level : data.threat_level;
    const weaponCount = isVideo ? data.total_weapons : data.weapon_count;

    banner.style.display = 'flex';
    if (threatLevel !== 'SAFE' && weaponCount > 0) {
        banner.classList.add('alert-danger');
        alertText.innerHTML = `<strong>WARNING: WEAPON DETECTED - ${threatLevel} RISK</strong> &mdash; ${weaponCount} weapon(s) identified`;
    } else {
        banner.classList.add('alert-safe');
        alertText.innerHTML = '<strong>SAFE</strong> &mdash; No weapons detected in the analyzed content';
    }

    // ── Stats ──────────────────────────────────────────────────
    const threatEl = document.getElementById('statThreat');
    threatEl.textContent = threatLevel;
    const threatColors = { HIGH: '#ff0040', MEDIUM: '#ff8800', LOW: '#ffcc00', SAFE: '#00cc66' };
    threatEl.style.color = threatColors[threatLevel] || '#00cc66';

    document.getElementById('statWeapons').textContent = weaponCount || 0;

    const conf = data.avg_confidence || 0;
    document.getElementById('statConfidence').textContent = (conf * 100).toFixed(1) + '%';

    if (isVideo) {
        document.getElementById('statSpeed').textContent = (data.processing_fps || 0).toFixed(1) + ' FPS';
        document.getElementById('statPersons').textContent = data.total_persons || 0;
        document.getElementById('statFrames').textContent = data.total_frames || 0;
    } else {
        document.getElementById('statSpeed').textContent = (data.inference_ms || 0).toFixed(0) + ' ms';
        document.getElementById('statPersons').textContent = data.person_count || 0;
        document.getElementById('statFrames').textContent = '1';
    }

    // ── Comparison View ────────────────────────────────────────
    const originalPanel = document.getElementById('originalPanel');
    const detectedPanel = document.getElementById('detectedPanel');

    originalPanel.innerHTML = '';
    detectedPanel.innerHTML = '';

    if (isVideo) {
        originalPanel.innerHTML = `<video src="${data.original_url}" controls muted style="max-width:100%;max-height:400px;border-radius:8px;"></video>`;
        detectedPanel.innerHTML = `<video src="${data.output_url}" controls muted style="max-width:100%;max-height:400px;border-radius:8px;"></video>`;
    } else {
        originalPanel.innerHTML = `<img src="${data.original_url}" alt="Original" style="max-width:100%;max-height:400px;border-radius:8px;">`;
        detectedPanel.innerHTML = `<img src="${data.output_url}" alt="Detected" style="max-width:100%;max-height:400px;border-radius:8px;">`;
    }

    // ── Detection Details (for images) ─────────────────────────
    if (!isVideo && data.detections && data.detections.length > 0) {
        const listEl = document.getElementById('detectionsList');
        const bodyEl = document.getElementById('detectionsBody');
        listEl.style.display = 'block';
        bodyEl.innerHTML = '';

        data.detections.forEach((det, i) => {
            const item = document.createElement('div');
            item.className = 'detection-item';
            item.style.animationDelay = `${i * 0.1}s`;

            const isWeapon = det.type === 'weapon';
            item.innerHTML = `
                <span class="detection-badge ${isWeapon ? 'badge-weapon' : 'badge-person'}">${det.type}</span>
                <span class="detection-label">${det.label}</span>
                <span class="detection-conf">${(det.confidence * 100).toFixed(1)}%</span>
            `;
            bodyEl.appendChild(item);
        });
    }

    // ── AI Interpretation ──────────────────────────────────────
    const interp = data.interpretation || {};
    if (interp.messages && interp.messages.length > 0) {
        const interpCard = document.getElementById('interpretationCard');
        const interpBody = document.getElementById('interpretationBody');
        interpCard.style.display = 'block';
        interpBody.innerHTML = '';

        interp.messages.forEach((msg, i) => {
            const div = document.createElement('div');
            div.className = 'interp-message';
            div.style.animationDelay = `${i * 0.12}s`;

            let iconCls, msgCls;
            if (msg.includes('CRITICAL') || msg.includes('HIGH')) {
                iconCls = 'fa-triangle-exclamation';
                msgCls = 'msg-critical';
            } else if (msg.includes('No weapon') || msg.includes('safe')) {
                iconCls = 'fa-check-circle';
                msgCls = 'msg-safe';
            } else if (msg.includes('Low') || msg.includes('low')) {
                iconCls = 'fa-info-circle';
                msgCls = 'msg-info';
            } else {
                iconCls = 'fa-info-circle';
                msgCls = 'msg-warning';
            }

            div.classList.add(msgCls);
            div.innerHTML = `<i class="fas ${iconCls}"></i><span>${msg}</span>`;
            interpBody.appendChild(div);
        });

        // Add threat details for images
        if (!isVideo && data.threat_details && data.threat_details.length > 0) {
            data.threat_details.forEach((detail, i) => {
                const div = document.createElement('div');
                div.className = 'interp-message msg-warning';
                div.style.animationDelay = `${(interp.messages.length + i) * 0.12}s`;
                div.innerHTML = `<i class="fas fa-crosshairs"></i><span>${detail}</span>`;
                interpBody.appendChild(div);
            });
        }
    }

    // Animate stat values
    animateStatValues();
}

function animateStatValues() {
    document.querySelectorAll('.stat-card-value').forEach(el => {
        const text = el.textContent;
        if (text === '--' || text === '0') return;

        // Extract number
        const match = text.match(/[\d.]+/);
        if (!match) return;
        const target = parseFloat(match[0]);
        const suffix = text.replace(match[0], '');
        const isFloat = text.includes('.');

        const duration = 1500;
        const start = performance.now();

        function update(now) {
            const p = Math.min((now - start) / duration, 1);
            const ease = 1 - Math.pow(1 - p, 3);
            const current = ease * target;
            el.textContent = (isFloat ? current.toFixed(1) : Math.floor(current)) + suffix;
            if (p < 1) requestAnimationFrame(update);
            else el.textContent = text;
        }
        requestAnimationFrame(update);
    });
}
