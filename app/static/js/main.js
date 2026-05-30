// ─────────────────────────────────────────────
// TOAST NOTIFICATIONS
// ─────────────────────────────────────────────

function showToast(message, type = 'success') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Map raw backend/network errors to human-friendly messages
function friendlyError(err) {
    const msg = (err && err.message) ? err.message : String(err);
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError'))
        return 'Network error — is the server running?';
    if (msg.includes('401') || msg.includes('Unauthorized'))
        return 'Session expired. Please log in again.';
    if (msg.includes('500'))
        return 'Server error — check the Logs page for details.';
    if (msg.includes('timeout') || msg.includes('Timeout'))
        return 'Request timed out — the AI model may be busy. Try again.';
    if (msg.includes('Ollama') || msg.includes('ollama'))
        return 'AI model is not responding. Make sure Ollama is running.';
    return msg || 'Something went wrong. Check the Logs page.';
}

// Safe wrapper for async API calls — catches errors and shows toast
async function safeFetch(url, options) {
    try {
        const res = await fetch(url, options);
        if (res.status === 401) { window.location.href = '/login'; return null; }
        return res;
    } catch (e) {
        showToast(friendlyError(e), 'error');
        if (typeof hideOverlay === 'function') hideOverlay();
        return null;
    }
}

// ─────────────────────────────────────────────
// PIPELINE PROGRESS BAR
// ─────────────────────────────────────────────

function updatePipelineProgress() {
    const steps = ['/upload', '/nlp', '/ranking', '/scheduling', '/interview', '/reports'];
    const path  = window.location.pathname;
    const index = steps.indexOf(path);
    const pct   = index >= 0 ? Math.round(((index + 1) / steps.length) * 100) : 0;
    const fill  = document.getElementById('pipelineProgress');
    if (fill) fill.style.width = pct + '%';
}

// ─────────────────────────────────────────────
// ACTIVE NAV HIGHLIGHT
// ─────────────────────────────────────────────

function highlightNav() {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.getAttribute('href') === path);
    });
}

// ─────────────────────────────────────────────
// SCORE BARS — apply widths from data-score attribute
// Avoids Jinja2 inline style linter warnings in VS Code
// ─────────────────────────────────────────────

function applyScoreBars() {
    document.querySelectorAll('.score-fill[data-score]').forEach(el => {
        el.style.width = el.dataset.score + '%';
    });
}

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    updatePipelineProgress();
    highlightNav();
    applyScoreBars();
});