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

let reasonChart = null;
let topTranscodersChart = null;

function renderActiveTranscodes(data) {
    const tbody = document.getElementById('active-transcodes-body');
    if (!data.active || data.active.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#666;padding:2rem;">No active transcodes</td></tr>';
        return;
    }
    tbody.innerHTML = data.active.map(s => `
        <tr>
            <td>${escapeHtml(s.user)}</td>
            <td>${escapeHtml(s.media || '\u2014')}</td>
            <td>${escapeHtml(s.device || '\u2014')}</td>
            <td>${escapeHtml(s.client || '\u2014')}</td>
            <td><span class="badge badge-transcode">${escapeHtml(s.reason || 'Unknown')}</span></td>
        </tr>
    `).join('');
}

function renderLeaderboard(data) {
    const tbody = document.getElementById('transcoder-leaderboard-body');
    if (!data.top_transcoders || data.top_transcoders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2" style="text-align:center;color:#666;padding:2rem;">No transcode history</td></tr>';
        return;
    }
    tbody.innerHTML = data.top_transcoders.map(s => `
        <tr>
            <td>${escapeHtml(s.user)}</td>
            <td><span class="badge badge-transcode">${s.count}</span></td>
        </tr>
    `).join('');
}

function buildReasonChart(data) {
    const canvas = document.getElementById('reasonChart');
    if (!canvas) return;
    if (reasonChart) reasonChart.destroy();
    const reasons = data.reason_breakdown || [];
    if (reasons.length === 0) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        return;
    }
    const colors = ['#ff4757', '#ff6b81', '#ffa502', '#ffda79', '#70a1ff', '#5352ed', '#2ed573', '#7bed9f'];
    reasonChart = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: reasons.map(r => r.reason),
            datasets: [{
                data: reasons.map(r => r.count),
                backgroundColor: colors.slice(0, reasons.length),
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#aaa', font: { size: 11 } }
                }
            }
        }
    });
}

function buildTopTranscodersChart(data) {
    const canvas = document.getElementById('topTranscodersChart');
    if (!canvas) return;
    if (topTranscodersChart) topTranscodersChart.destroy();
    const users = data.top_transcoders || [];
    if (users.length === 0) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        return;
    }
    topTranscodersChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: users.map(u => u.user),
            datasets: [{
                label: 'Transcodes',
                data: users.map(u => u.count),
                backgroundColor: '#ff4757',
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

async function refreshTranscodes() {
    const data = await fetchJSON('/api/stats/transcode-breakdown');
    renderActiveTranscodes(data);
    renderLeaderboard(data);
    buildReasonChart(data);
    buildTopTranscodersChart(data);
}

document.addEventListener('DOMContentLoaded', () => {
    refreshTranscodes();
    setInterval(refreshTranscodes, 10000);
});
