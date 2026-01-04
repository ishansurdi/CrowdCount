/**
 * User Portal - JavaScript
 * Shows only areas with visible_to_users=true
 */
const API_BASE = 'http://127.0.0.1:5000';
const AREA_NAMES = {
    'entrance': 'Mall Entrance',
    'retail': 'Retail Area',
    'foodcourt': 'Food Court'
};

let token = null;
let currentUser = null;
let visibleAreas = [];
let charts = {};
let globalThreshold = 50;
let alertedAreas = new Set();

// Auth check
function checkAuth() {
    token = localStorage.getItem('crowdcount_token');
    const userStr = localStorage.getItem('crowdcount_user');
    
    if (!token || !userStr) {
        window.location.href = '/login.html';
        return false;
    }
    
    currentUser = JSON.parse(userStr);
    
    if (currentUser.role === 'admin') {
        window.location.href = '/admin.html';
        return false;
    }
    
    document.getElementById('user-name').textContent = currentUser.name;
    return true;
}

function logout() {
    localStorage.removeItem('crowdcount_token');
    localStorage.removeItem('crowdcount_user');
    window.location.href = '/login.html';
}

// Initialize
window.addEventListener('DOMContentLoaded', async () => {
    if (!checkAuth()) return;
    
    await loadVisibleAreas();
    await loadThreshold();
    await loadViolationHistory();
    renderAreaCards();
    setupCharts();
    startDataFetching();
    
    // Refresh violation history every 30 seconds
    setInterval(loadViolationHistory, 30000);
});

// Load areas that are visible to users (admin configured)
async function loadVisibleAreas() {
    try {
        // Get user's assigned areas from API
        const userAreasResponse = await fetch(`${API_BASE}/api/live/areas`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const userAreasData = await userAreasResponse.json();
        visibleAreas = (userAreasData.areas || []).map(a => a.area_name);
        
        document.getElementById('visible-areas').textContent = visibleAreas.length;
        
    } catch (error) {
        console.error('Error loading visible areas:', error);
        visibleAreas = [];
    }
}

// Load global threshold
async function loadThreshold() {
    try {
        const response = await fetch(`${API_BASE}/api/live/threshold`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            globalThreshold = data.global_threshold || 50;
            document.getElementById('threshold-value').textContent = globalThreshold;
        }
    } catch (error) {
        console.error('Error loading threshold:', error);
        globalThreshold = 50; // fallback
    }
}

// Load threshold violation history
async function loadViolationHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/live/threshold/history?limit=20`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            displayViolations(data.violations || []);
        }
    } catch (error) {
        console.error('Error loading violation history:', error);
    }
}

function displayViolations(violations) {
    const container = document.getElementById('violations-list');
    
    if (violations.length === 0) {
        container.innerHTML = `
            <p style="text-align: center; color: var(--text-secondary); padding: 2rem;">
                ✅ No threshold violations recorded
            </p>
        `;
        return;
    }
    
    container.innerHTML = violations.map(v => {
        const time = new Date(v.violation_time);
        const timeStr = time.toLocaleString();
        const exceeded = v.people_count - v.threshold;
        
        return `
            <div style="padding: 1rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 1rem;">
                <div style="flex-shrink: 0; width: 48px; height: 48px; background: var(--danger-bg); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">
                    ⚠️
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; color: var(--text-primary);">
                        ${AREA_NAMES[v.area_name] || v.area_name}
                    </div>
                    <div style="font-size: 0.875rem; color: var(--text-secondary); margin-top: 0.25rem;">
                        <span style="color: var(--danger); font-weight: 600;">${v.people_count} people</span>
                        (exceeded by ${exceeded}) • Threshold: ${v.threshold}
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-tertiary); margin-top: 0.25rem;">
                        ${timeStr}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Render area cards
function renderAreaCards() {
    const container = document.getElementById('areas-container');
    
    if (visibleAreas.length === 0) {
        container.innerHTML = `
            <div class="card col-12" style="text-align: center; padding: 3rem;">
                <h3>No Areas Available</h3>
                <p style="color: var(--text-secondary); margin-top: 0.5rem;">No areas are currently visible. Contact your administrator.</p>
            </div>
        `;
        return;
    }
    
    const colClass = visibleAreas.length === 1 ? 'col-12' : (visibleAreas.length === 2 ? 'col-6' : 'col-4');
    
    container.innerHTML = visibleAreas.map(area => `
        <div class="card ${colClass}">
            <div class="card-header">
                <h2>${AREA_NAMES[area]}</h2>
                <span class="status-badge" id="badge-${area}" style="background: var(--success-bg); color: var(--success);">Normal</span>
            </div>
            <div class="metric-main" id="count-${area}">--</div>
            <div class="metric-sub">Current Occupancy</div>
            <div class="zone-mini-list" id="zones-${area}">
                <div class="zone-item"><span class="zone-name">Loading...</span></div>
            </div>
        </div>
    `).join('');
}

// Charts
function setupCharts() {
    // Bar Chart for current counts
    const ctxBar = document.getElementById('barChart').getContext('2d');
    charts.bar = new Chart(ctxBar, {
        type: 'bar',
        data: {
            labels: visibleAreas.map(a => AREA_NAMES[a]),
            datasets: [{
                label: 'Current People Count',
                data: [],
                backgroundColor: [
                    'rgba(68, 76, 231, 0.6)',
                    'rgba(6, 118, 71, 0.6)',
                    'rgba(181, 71, 8, 0.6)'
                ],
                borderColor: [
                    'rgb(68, 76, 231)',
                    'rgb(6, 118, 71)',
                    'rgb(181, 71, 8)'
                ],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Real-time Occupancy Levels'
                }
            },
            scales: {
                y: { 
                    beginAtZero: true,
                    ticks: { stepSize: 10 }
                }
            }
        }
    });
    
    // Line Chart removed from user view
    // Only bar chart for current occupancy is shown
}

// Data fetching
function startDataFetching() {
    if (visibleAreas.length === 0) return;
    
    fetchLiveData();
    setInterval(fetchLiveData, 2000);
    
    fetchHistoricalData();
    setInterval(fetchHistoricalData, 10000);
}

async function fetchLiveData() {
    try {
        const responses = await Promise.all(
            visibleAreas.map(area => 
                fetch(`${API_BASE}/live/${area}`)
                    .then(r => r.json())
                    .catch(err => ({ live_people: 0, zone_counts: {} }))
            )
        );
        
        const counts = [];
        const exceededAreas = [];
        
        responses.forEach((data, i) => {
            const area = visibleAreas[i];
            const count = data.live_people || 0;
            counts.push(count);
            
            // Update area card
            updateAreaCard(area, data);
            
            // Check threshold
            if (count > globalThreshold) {
                if (!alertedAreas.has(area)) {
                    exceededAreas.push({ area: AREA_NAMES[area], count });
                    alertedAreas.add(area);
                }
            } else {
                alertedAreas.delete(area);
            }
        });
        
        // Show alert if needed
        if (exceededAreas.length > 0) {
            showThresholdAlert(exceededAreas);
        } else if (alertedAreas.size === 0) {
            dismissAlert();
        }
        
        // Update bar chart
        charts.bar.data.datasets[0].data = counts;
        charts.bar.update('none');
        
        // Update status
        document.getElementById('api-status').textContent = 'Connected';
        document.getElementById('api-status').style.color = 'var(--success)';
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        
    } catch (error) {
        console.error('Fetch error:', error);
        document.getElementById('api-status').textContent = 'Error';
        document.getElementById('api-status').style.color = 'var(--danger)';
    }
}

function updateAreaCard(area, data) {
    const count = data.live_people || 0;
    const zones = data.zone_counts || {};
    
    document.getElementById(`count-${area}`).textContent = count;
    
    const badge = document.getElementById(`badge-${area}`);
    if (count > globalThreshold) {
        badge.textContent = 'High';
        badge.style.background = 'var(--danger-bg)';
        badge.style.color = 'var(--danger)';
    } else if (count > globalThreshold * 0.7) {
        badge.textContent = 'Moderate';
        badge.style.background = 'var(--warning-bg)';
        badge.style.color = 'var(--warning)';
    } else {
        badge.textContent = 'Normal';
        badge.style.background = 'var(--success-bg)';
        badge.style.color = 'var(--success)';
    }
    
    // Update zones
    const zonesEl = document.getElementById(`zones-${area}`);
    if (Object.keys(zones).length > 0) {
        zonesEl.innerHTML = Object.entries(zones)
            .map(([id, val]) => `
                <div class="zone-item">
                    <span class="zone-name">Zone ${id}</span>
                    <span class="zone-val">${val}</span>
                </div>
            `).join('');
    } else {
        zonesEl.innerHTML = '<div class="zone-item"><span class="zone-name">No zone data</span></div>';
    }
}



async function fetchHistoricalData() {
    try {
        const responses = await Promise.all(
            visibleAreas.map(area =>
                fetch(`${API_BASE}/api/history/${area}?limit=20&hours=1`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                })
                    .then(r => r.json())
                    .catch(err => ({ history: [] }))
            )
        );
        
        // Collect all unique timestamps from all visible areas
        const timestampSet = new Set();
        responses.forEach(r => {
            (r.history || []).forEach(h => {
                if (h.recorded_at) {
                    timestampSet.add(h.recorded_at);
                }
            });
        });
        
        // Line chart removed - historical data can be accessed via admin portal
        
    } catch (error) {
        console.error('History fetch error:', error);
    }
}

function showThresholdAlert(exceededAreas) {
    const alertBanner = document.getElementById('threshold-alert');
    const messageEl = document.getElementById('threshold-message');
    
    const message = exceededAreas.map(a => 
        `${a.area}: ${a.count} people (Threshold: ${globalThreshold})`
    ).join(' | ');
    
    messageEl.textContent = message;
    alertBanner.style.display = 'block';
}

function dismissAlert() {
    document.getElementById('threshold-alert').style.display = 'none';
}
