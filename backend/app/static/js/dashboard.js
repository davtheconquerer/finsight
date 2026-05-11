async function fetchJSON(url) {
    const resp = await fetch(url);
    return resp.json();
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function renderActiveSessions(sessions) {
    const tbody = document.getElementById('active-sessions-body');
    if (!sessions || sessions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#666;padding:2rem;">No active streams</td></tr>';
        return;
    }
    tbody.innerHTML = sessions.map(s => `
        <tr>
            <td>${escapeHtml(s.user)}</td>
            <td>${escapeHtml(s.media)}</td>
            <td>${escapeHtml(s.device || '\u2014')}</td>
            <td><span class="badge ${s.play_method === 'Transcode' ? 'badge-transcode' : s.play_method ? 'badge-direct' : 'badge-unknown'}">${escapeHtml(s.play_method || '\u2014')}</span></td>
            <td>${s.is_transcoding ? `<span class="badge badge-transcode" title="${escapeHtml(s.transcode_reason || '')}">Transcoding</span>` : '\u2014'}</td>
        </tr>
    `).join('');
}

function renderHistory(sessions) {
    const tbody = document.getElementById('history-body');
    if (!sessions || sessions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#666;padding:2rem;">No playback history</td></tr>';
        return;
    }
    tbody.innerHTML = sessions.map(s => {
        const dur = s.duration ? Math.round(s.duration / 60) + 'm' : '\u2014';
        return `
        <tr>
            <td>${escapeHtml(s.user)}</td>
            <td>${escapeHtml(s.media)}</td>
            <td>${escapeHtml(s.device || '\u2014')}</td>
            <td>${dur}</td>
            <td><span class="badge ${s.play_method === 'Transcode' ? 'badge-transcode' : s.play_method ? 'badge-direct' : 'badge-unknown'}">${escapeHtml(s.play_method || '\u2014')}</span></td>
        </tr>`;
    }).join('');
}

function renderStats(stats) {
    document.getElementById('stat-users').textContent = stats.total_users;
    document.getElementById('stat-media').textContent = stats.total_media;
    document.getElementById('stat-active').textContent = stats.active_sessions;
}

async function refresh() {
    try {
        const [stats, sessions, history] = await Promise.all([
            fetchJSON('/api/stats/overview'),
            fetchJSON('/api/sessions/active'),
            fetchJSON('/api/sessions/history?limit=10'),
        ]);
        renderStats(stats);
        renderActiveSessions(sessions);
        renderHistory(history);
    } catch (err) {
        console.error('Refresh failed:', err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    refresh();
    setInterval(refresh, 10000);
});
