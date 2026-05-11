async function fetchJSON(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(resp.statusText);
    return resp.json();
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

/* ── Dashboard ── */
function renderActiveSessions(sessions) {
    const tbody = document.getElementById('active-sessions-body');
    if (!tbody) return;
    if (!sessions || sessions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#666;padding:2rem;">No active streams</td></tr>';
        return;
    }
    tbody.innerHTML = sessions.map(s => `
        <tr>
            <td>${escapeHtml(s.user)}</td>
            <td><a href="/media/${s.id}" class="nav-link" style="display:inline;padding:0">${escapeHtml(s.media)}</a></td>
            <td>${escapeHtml(s.device || '\u2014')}</td>
            <td><span class="badge ${s.play_method === 'Transcode' ? 'badge-transcode' : s.play_method ? 'badge-direct' : 'badge-unknown'}">${escapeHtml(s.play_method || '\u2014')}</span></td>
        </tr>
    `).join('');
}

function renderHistory(sessions) {
    const tbody = document.getElementById('history-body');
    if (!tbody) return;
    if (!sessions || sessions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#666;padding:2rem;">No playback history</td></tr>';
        return;
    }
    tbody.innerHTML = sessions.map(s => {
        const dur = s.duration ? Math.round(s.duration / 60) + 'm' : '\u2014';
        const link = s.media_id ? `/media/${s.media_id}` : '#';
        return `
        <tr>
            <td>${escapeHtml(s.user)}</td>
            <td><a href="${link}" class="nav-link" style="display:inline;padding:0">${escapeHtml(s.media)}</a></td>
            <td>${escapeHtml(s.device || '\u2014')}</td>
            <td>${dur}</td>
            <td><span class="badge ${s.play_method === 'Transcode' ? 'badge-transcode' : s.play_method ? 'badge-direct' : 'badge-unknown'}">${escapeHtml(s.play_method || '\u2014')}</span></td>
        </tr>`;
    }).join('');
}

function renderStats(stats) {
    const el = (id) => document.getElementById(id);
    if (el('stat-users')) el('stat-users').textContent = stats.total_users;
    if (el('stat-media')) el('stat-media').textContent = stats.total_media;
    if (el('stat-active')) el('stat-active').textContent = stats.active_sessions;
}

/* ── Charts ── */
let playsChart = null;
let topMediaChart = null;

function buildPlaysChart(data) {
    const canvas = document.getElementById('playsChart');
    if (!canvas) return;
    if (playsChart) playsChart.destroy();
    playsChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                label: 'Plays',
                data: data.map(d => d.plays),
                borderColor: '#6c63ff',
                backgroundColor: '#6c63ff33',
                fill: true,
                tension: 0.3,
                pointRadius: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#8888aa', maxTicksLimit: 10 }, grid: { color: '#2a2b4a' } },
                y: { ticks: { color: '#8888aa', precision: 0 }, grid: { color: '#2a2b4a' } },
            }
        }
    });
}

function buildTopMediaChart(data) {
    const canvas = document.getElementById('topMediaChart');
    if (!canvas) return;
    if (topMediaChart) topMediaChart.destroy();
    topMediaChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: data.map(d => d.title.length > 25 ? d.title.substring(0, 22) + '...' : d.title),
            datasets: [{
                label: 'Plays',
                data: data.map(d => d.plays),
                backgroundColor: '#6c63ff',
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#8888aa', precision: 0 }, grid: { color: '#2a2b4a' } },
                y: { ticks: { color: '#8888aa', font: { size: 11 } }, grid: { display: false } },
            }
        }
    });
}

/* ── Page Dispatchers ── */
async function refreshDashboard() {
    const [stats, sessions, history, plays, topMedia] = await Promise.all([
        fetchJSON('/api/stats/overview'),
        fetchJSON('/api/sessions/active'),
        fetchJSON('/api/sessions/history?limit=10'),
        fetchJSON('/api/stats/plays-over-time?days=30'),
        fetchJSON('/api/stats/top-media?limit=10'),
    ]);
    renderStats(stats);
    renderActiveSessions(sessions);
    renderHistory(history.items);
    buildPlaysChart(plays);
    buildTopMediaChart(topMedia);
}

/* ── History Page ── */
let historyPage = 1;
let historyTotal = 0;
let historyQuery = { user: '', media: '' };

async function loadHistoryPage() {
    const params = new URLSearchParams({
        page: historyPage,
        limit: 20,
    });
    if (historyQuery.user) params.set('user', historyQuery.user);
    if (historyQuery.media) params.set('media', historyQuery.media);

    const data = await fetchJSON(`/api/sessions/history?${params}`);
    historyTotal = data.total;
    const tbody = document.getElementById('history-body');
    if (!tbody) return;
    if (!data.items || data.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#666;padding:2rem;">No results</td></tr>';
    } else {
        tbody.innerHTML = data.items.map(s => {
            const dur = s.duration ? Math.round(s.duration / 60) + 'm' : '\u2014';
            const link = s.media_id ? `/media/${s.media_id}` : '#';
            return `
            <tr>
                <td>${escapeHtml(s.user)}</td>
                <td><a href="${link}" class="nav-link" style="display:inline;padding:0">${escapeHtml(s.media)}</a></td>
                <td>${escapeHtml(s.device || '\u2014')}</td>
                <td>${dur}</td>
                <td><span class="badge ${s.play_method === 'Transcode' ? 'badge-transcode' : s.play_method ? 'badge-direct' : 'badge-unknown'}">${escapeHtml(s.play_method || '\u2014')}</span></td>
            </tr>`;
        }).join('');
    }

    document.getElementById('page-info').textContent = `Page ${historyPage} of ${Math.max(1, Math.ceil(historyTotal / 20))}`;
    document.getElementById('prev-page').disabled = historyPage <= 1;
    document.getElementById('next-page').disabled = historyPage * 20 >= historyTotal;
}

function setupHistoryPage() {
    const filterBtn = document.getElementById('filter-btn');
    if (!filterBtn) return;

    filterBtn.addEventListener('click', () => {
        historyQuery.user = document.getElementById('filter-user').value;
        historyQuery.media = document.getElementById('filter-media').value;
        historyPage = 1;
        loadHistoryPage();
    });

    document.getElementById('prev-page').addEventListener('click', () => {
        if (historyPage > 1) { historyPage--; loadHistoryPage(); }
    });
    document.getElementById('next-page').addEventListener('click', () => {
        historyPage++; loadHistoryPage();
    });

    loadHistoryPage();
}

/* ── Media Detail Page ── */
async function loadMediaDetail() {
    if (typeof MEDIA_ID === 'undefined') return;
    const data = await fetchJSON(`/api/media/${MEDIA_ID}`);

    document.getElementById('media-detail').innerHTML = `
        <div class="detail-header">
            <div class="detail-info">
                <h2>${escapeHtml(data.title)}</h2>
                <div class="detail-meta">
                    <span class="detail-tag">${escapeHtml(data.type)}</span>
                    ${data.year ? `<span class="detail-tag">${data.year}</span>` : ''}
                    ${data.community_rating ? `<span class="detail-tag">\u2605 ${data.community_rating}</span>` : ''}
                    ${data.runtime_ticks ? `<span class="detail-tag">${Math.round(data.runtime_ticks / 600000000)} min</span>` : ''}
                </div>
                <div>${(data.genres || []).map(g => `<span class="genre-tag">${escapeHtml(g)}</span>`).join(' ')}</div>
                <div class="detail-stats">
                    <div class="detail-stat"><div class="value">${data.total_plays}</div><div class="label">Plays</div></div>
                    <div class="detail-stat"><div class="value">${data.transcode_count}</div><div class="label">Transcodes</div></div>
                    <div class="detail-stat"><div class="value">${data.transcode_ratio}</div><div class="label">Transcode Ratio</div></div>
                </div>
            </div>
        </div>
    `;

    const tbody = document.getElementById('play-history-body');
    if (!data.play_history || data.play_history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#666;padding:2rem;">No plays recorded</td></tr>';
        return;
    }
    tbody.innerHTML = data.play_history.map(s => {
        const dur = s.duration ? Math.round(s.duration / 60) + 'm' : '\u2014';
        const date = s.ended_at ? new Date(s.ended_at).toLocaleString() : '\u2014';
        return `
        <tr>
            <td>${escapeHtml(s.user)}</td>
            <td>${date}</td>
            <td>${dur}</td>
            <td><span class="badge ${s.play_method === 'Transcode' ? 'badge-transcode' : s.play_method ? 'badge-direct' : 'badge-unknown'}">${escapeHtml(s.play_method || '\u2014')}</span></td>
            <td>${escapeHtml(s.device || '\u2014')}</td>
        </tr>`;
    }).join('');
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;

    if (path === '/' || path === '') {
        refreshDashboard();
        setInterval(refreshDashboard, 10000);
    } else if (path === '/history') {
        setupHistoryPage();
    } else if (path.startsWith('/media/')) {
        loadMediaDetail();
    }
});
