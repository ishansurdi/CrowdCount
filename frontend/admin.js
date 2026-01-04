/**
 * Admin Portal - JavaScript
 */
const API_BASE = 'http://127.0.0.1:5000';
const AREA_NAMES = {
    'entrance': 'Mall Entrance',
    'retail': 'Retail Area',
    'foodcourt': 'Food Court'
};

let token = null;
let currentUser = null;
let charts = {};
let allUsers = [];
let allCameras = [];
let currentZoneArea = null;
let globalThreshold = 50;
let lastAlertedAreas = new Set();

// Cache for zone data to reduce API calls
let zoneDataCache = {
    entrance: null,
    retail: null,
    foodcourt: null,
    lastUpdate: {}
};

const ZONE_CACHE_TTL = 10000; // Cache for 10 seconds

// Auth check
function checkAuth() {
    token = localStorage.getItem('crowdcount_token');
    const userStr = localStorage.getItem('crowdcount_user');
    
    if (!token || !userStr) {
        window.location.href = '/login.html';
        return false;
    }
    
    currentUser = JSON.parse(userStr);
    
    if (currentUser.role !== 'admin') {
        window.location.href = '/user.html';
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
    
    setupCharts();
    loadCameras();
    loadZonesForAllAreas();
    loadUsers();
    loadThreshold();
    startDataFetching();
});

// Tab switching
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.style.background = 'var(--surface)';
        tab.style.color = 'var(--text-primary)';
        tab.classList.remove('active');
    });
    document.getElementById(`tab-${tabName}`).style.background = 'var(--accent)';
    document.getElementById(`tab-${tabName}`).style.color = 'white';
    document.getElementById(`tab-${tabName}`).classList.add('active');
    
    // Hide all sections
    document.getElementById('section-cameras').style.display = 'none';
    document.getElementById('section-zones').style.display = 'none';
    document.getElementById('section-users').style.display = 'none';
    document.getElementById('section-settings').style.display = 'none';
    document.getElementById('section-analytics').style.display = 'none';
    document.getElementById('section-analytics-2').style.display = 'none';
    document.getElementById('section-analytics-3').style.display = 'none';
    document.getElementById('section-analytics-chart').style.display = 'none';
    document.getElementById('section-analytics-diag').style.display = 'none';
    document.getElementById('section-analytics-history').style.display = 'none';
    document.getElementById('section-analytics-heatmaps').style.display = 'none';
    
    // Show selected section
    if (tabName === 'cameras') {
        document.getElementById('section-cameras').style.display = 'block';
    } else if (tabName === 'zones') {
        document.getElementById('section-zones').style.display = 'block';
    } else if (tabName === 'users') {
        document.getElementById('section-users').style.display = 'block';
    } else if (tabName === 'analytics') {
        document.getElementById('section-analytics').style.display = 'block';
        document.getElementById('section-analytics-2').style.display = 'block';
        document.getElementById('section-analytics-3').style.display = 'block';
        document.getElementById('section-analytics-chart').style.display = 'block';
        document.getElementById('section-analytics-diag').style.display = 'block';
        document.getElementById('section-analytics-history').style.display = 'block';
        document.getElementById('section-analytics-heatmaps').style.display = 'block';
        // Update heatmaps when analytics tab is opened
        updateHeatmaps();
    } else if (tabName === 'settings') {
        document.getElementById('section-settings').style.display = 'block';
    }
}

// Charts
function setupCharts() {
    // Zone Chart
    const ctxZone = document.getElementById('zoneChart').getContext('2d');
    charts.zone = new Chart(ctxZone, {
        type: 'bar',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true } }
        }
    });
    
    // History Chart
    const ctxHistory = document.getElementById('historyChart').getContext('2d');
    charts.history = new Chart(ctxHistory, {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

// Data fetching
function startDataFetching() {
    fetchLiveData();
    setInterval(fetchLiveData, 1500); // Smoother at 1.5s
    
    fetchHistoricalData();
    setInterval(fetchHistoricalData, 10000);
    
    // Poll zones only when zones tab is active
    setInterval(() => {
        const zonesTabActive = document.getElementById('section-zones-management').style.display !== 'none';
        if (zonesTabActive) {
            loadZonesForAllAreas();
        }
    }, 5000); // Check every 5 seconds when zones tab is active
}

// Load zones for all areas
let isLoadingZones = false;
async function loadZonesForAllAreas() {
    if (isLoadingZones) return; // Prevent concurrent calls
    
    isLoadingZones = true;
    const areas = ['entrance', 'retail', 'foodcourt'];
    
    // Load all in parallel for speed
    await Promise.all(areas.map(area => loadZonesForArea(area)));
    
    isLoadingZones = false;
}

async function loadZonesForArea(area) {
    try {
        const response = await fetch(`${API_BASE}/api/admin/zones/by-name/${area}`, {
            headers: { 
                'Authorization': `Bearer ${token}`,
                'Cache-Control': 'no-cache'
            }
        });
        
        if (response.status === 401) {
            console.warn('Auth token expired, skipping zone load');
            return;
        }
        
        if (!response.ok) {
            console.error(`Failed to load zones for ${area}: ${response.status}`);
            return;
        }
        
        const data = await response.json();
        const zones = data.zones || [];
        renderZonesForArea(area, zones);
    } catch (error) {
        console.error(`Error loading zones for ${area}:`, error);
        document.getElementById(`zones-${area}`).innerHTML = '<p style="color: var(--danger); padding: 1rem;">Failed to load zones</p>';
    }
}

function renderZonesForArea(area, zones) {
    const container = document.getElementById(`zones-${area}`);
    
    if (!zones.length) {
        container.innerHTML = '<p style="color: var(--text-tertiary); padding: 1rem;">No zones configured yet</p>';
        return;
    }
    
    container.innerHTML = `
        <table style="width: 100%;">
            <thead>
                <tr>
                    <th style="text-align: left; padding: 0.75rem; background: var(--bg-main); font-weight: 600; font-size: 0.875rem; color: var(--text-secondary);">Zone ID</th>
                    <th style="text-align: left; padding: 0.75rem; background: var(--bg-main); font-weight: 600; font-size: 0.875rem; color: var(--text-secondary);">Coordinates</th>
                    <th style="text-align: center; padding: 0.75rem; background: var(--bg-main); font-weight: 600; font-size: 0.875rem; color: var(--text-secondary);">Visible to Users</th>
                    <th style="text-align: right; padding: 0.75rem; background: var(--bg-main); font-weight: 600; font-size: 0.875rem; color: var(--text-secondary);">Actions</th>
                </tr>
            </thead>
            <tbody>
                ${zones.map(zone => `
                    <tr style="border-bottom: 1px solid var(--border);">
                        <td style="padding: 1rem;"><strong style="color: var(--accent);">Zone ${zone.zone_id}</strong></td>
                        <td style="padding: 1rem; font-family: monospace; font-size: 0.85rem; color: var(--text-tertiary);">${formatCoordinates(zone.coordinates)}</td>
                        <td style="padding: 1rem; text-align: center;">
                            <label class="switch" style="display: inline-block;">
                                <input type="checkbox" ${zone.visible_to_users !== false ? 'checked' : ''} onchange="toggleZoneVisibility('${area}', ${zone.zone_id}, this.checked)">
                                <span class="slider"></span>
                            </label>
                        </td>
                        <td style="padding: 1rem; text-align: right;">
                            <button onclick="deleteZone('${area}', ${zone.zone_id})" class="btn-outline" style="padding: 0.5rem 1rem; background: var(--danger-bg); color: var(--danger);">Delete</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function formatCoordinates(coords) {
    if (!coords || coords.length === 0) return 'N/A';
    return `[${coords.map(c => `(${c[0]},${c[1]})`).join(', ')}]`;
}

async function toggleZoneVisibility(area, zoneId, visible) {
    try {
        const response = await fetch(`${API_BASE}/api/admin/zones/by-name/${area}/${zoneId}/visibility`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ visible_to_users: visible })
        });
        
        if (!response.ok) throw new Error('Failed to update zone visibility');
        
        // Invalidate cache to force fresh data
        zoneDataCache[area] = null;
        
        console.log(`Zone ${zoneId} visibility updated to ${visible}`);
    } catch (error) {
        console.error('Error toggling zone visibility:', error);
        alert('Failed to update zone visibility');
        // Reload zones to revert the toggle
        await loadZonesForArea(area);
    }
}

async function deleteZone(area, zoneId) {
    if (!confirm(`Are you sure you want to delete Zone ${zoneId}?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/zones/by-name/${area}/${zoneId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Failed to delete zone');
        
        // Invalidate cache to force fresh data
        zoneDataCache[area] = null;
        
        alert('Zone deleted successfully!');
        await loadZonesForArea(area);
    } catch (error) {
        console.error('Error deleting zone:', error);
        alert('Failed to delete zone');
    }
}


async function fetchLiveData() {
    try {
        const areas = ['entrance', 'retail', 'foodcourt'];
        const responses = await Promise.all(
            areas.map(area => fetch(`${API_BASE}/live/${area}`).then(r => r.json()))
        );
        
        // Check for threshold violations
        const exceededAreas = [];
        responses.forEach((data, i) => {
            const area = areas[i];
            const count = data.live_people || 0;
            updateAreaCard(area, data);
            
            // Check if count exceeds threshold
            if (count > globalThreshold) {
                const alertKey = `${area}-${count}`;
                if (!lastAlertedAreas.has(area)) {
                    exceededAreas.push({ area: AREA_NAMES[area], count });
                    lastAlertedAreas.add(area);
                }
            } else {
                // Remove from alerted set if count is back to normal
                lastAlertedAreas.delete(area);
            }
        });
        
        // Show alert for exceeded areas
        if (exceededAreas.length > 0) {
            const message = exceededAreas.map(a => 
                `⚠️ ${a.area}: ${a.count} people (threshold: ${globalThreshold})`
            ).join(' | ');
            showThresholdAlert(message);
        }
        
        updateZoneChart(responses, areas);
        document.getElementById('api-status').textContent = 'Connected';
        document.getElementById('api-status').style.color = 'var(--success)';
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
    if (count > 50) {
        badge.textContent = 'High';
        badge.style.background = 'var(--danger-bg)';
        badge.style.color = 'var(--danger)';
    } else if (count > 30) {
        badge.textContent = 'Moderate';
        badge.style.background = 'var(--warning-bg)';
        badge.style.color = 'var(--warning)';
    } else {
        badge.textContent = 'Normal';
        badge.style.background = 'var(--success-bg)';
        badge.style.color = 'var(--success)';
    }
    
    // Update zone breakdown in analytics section
    const zonesEl = document.getElementById(`zone-breakdown-${area}`);
    if (zonesEl) {
        if (Object.keys(zones).length > 0) {
            zonesEl.innerHTML = Object.entries(zones).map(([id, val]) => 
                `<div class="zone-item"><span class="zone-name">Zone ${id}</span><span class="zone-val">${val}</span></div>`
            ).join('');
        } else {
            zonesEl.innerHTML = '<div class="zone-item"><span class="zone-name">No zones configured</span></div>';
        }
    }
}

function updateZoneChart(dataArray, areas) {
    const allZones = new Set();
    dataArray.forEach(d => Object.keys(d.zone_counts || {}).forEach(z => allZones.add(`Zone ${z}`)));
    
    charts.zone.data.labels = Array.from(allZones);
    charts.zone.data.datasets = areas.map((area, i) => ({
        label: AREA_NAMES[area],
        data: Array.from(allZones).map(z => {
            const zoneId = z.replace('Zone ', '');
            return dataArray[i].zone_counts?.[zoneId] || 0;
        }),
        backgroundColor: ['#444ce7', '#10b981', '#f59e0b'][i]
    }));
    charts.zone.update('none');
}

async function fetchHistoricalData() {
    try {
        const areas = ['entrance', 'retail', 'foodcourt'];
        const responses = await Promise.all(
            areas.map(area => 
                fetch(`${API_BASE}/api/history/${area}?limit=50&hours=1`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                })
                .then(r => r.json())
                .catch(err => {
                    console.error(`History fetch error for ${area}:`, err);
                    return { history: [] };
                })
            )
        );
        
        // Collect all unique timestamps
        const timestamps = new Set();
        responses.forEach(r => {
            if (r.history) {
                r.history.forEach(h => {
                    if (h.recorded_at) {
                        timestamps.add(h.recorded_at);
                    }
                });
            }
        });
        
        const sorted = Array.from(timestamps).sort();
        
        if (sorted.length === 0) {
            console.log('No historical data available yet');
            return;
        }
        
        // Update chart labels (show time only)
        charts.history.data.labels = sorted.map(ts => {
            const date = new Date(ts);
            return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        });
        
        // Update datasets for each area
        charts.history.data.datasets = areas.map((area, i) => ({
            label: AREA_NAMES[area],
            data: sorted.map(ts => {
                const record = responses[i].history?.find(h => h.recorded_at === ts);
                return record?.total_count || 0;
            }),
            borderColor: ['#444ce7', '#10b981', '#f59e0b'][i],
            backgroundColor: ['rgba(68, 76, 231, 0.1)', 'rgba(16, 185, 129, 0.1)', 'rgba(245, 158, 11, 0.1)'][i],
            borderWidth: 2,
            tension: 0.3,
            fill: true
        }));
        
        charts.history.update('none');
        
        // Update total records count
        const totalRecords = responses.reduce((sum, r) => sum + (r.history?.length || 0), 0);
        document.getElementById('total-records').textContent = totalRecords;
        
        console.log(`Historical data updated: ${sorted.length} timestamps, ${totalRecords} total records`);
    } catch (error) {
        console.error('History fetch error:', error);
    }
}

// User Management
async function loadUsers() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/users`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();
        allUsers = data.users || [];
        renderUsersTable();
    } catch (error) {
        console.error('Load users error:', error);
    }
}

function renderUsersTable() {
    const tbody = document.getElementById('users-table-body');
    if (!allUsers.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 2rem;">No users found</td></tr>';
        return;
    }
    
    tbody.innerHTML = allUsers.map(u => `
        <tr>
            <td>${u.name}</td>
            <td>${u.email}</td>
            <td><span style="background: ${u.role === 'admin' ? 'var(--accent-soft)' : 'var(--success-bg)'}; color: ${u.role === 'admin' ? 'var(--accent)' : 'var(--success)'}; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">${u.role}</span></td>
            <td>${u.areas?.map(a => AREA_NAMES[a]).join(', ') || 'None'}</td>
            <td>
                <button onclick="editUser(${u.user_id})" class="btn-outline" style="padding: 0.5rem 1rem; margin-right: 0.5rem;">Edit</button>
                <button onclick="deleteUser(${u.user_id})" class="btn-outline" style="padding: 0.5rem 1rem; background: var(--danger-bg); color: var(--danger);">Delete</button>
            </td>
        </tr>
    `).join('');
}

function openUserModal(userId = null) {
    const modal = document.getElementById('user-modal');
    const form = document.getElementById('user-form');
    form.reset();
    document.getElementById('user-id').value = '';
    
    if (userId) {
        const user = allUsers.find(u => u.user_id === userId);
        document.getElementById('modal-title').textContent = 'Edit User';
        document.getElementById('user-id').value = user.user_id;
        document.getElementById('modal-user-name').value = user.name;
        document.getElementById('modal-user-email').value = user.email;
        document.getElementById('modal-user-role').value = user.role;
        document.querySelectorAll('input[name="area"]').forEach(cb => {
            cb.checked = user.areas?.includes(cb.value);
        });
        document.getElementById('modal-user-password').removeAttribute('required');
    } else {
        document.getElementById('modal-title').textContent = 'Add New User';
        document.getElementById('modal-user-password').setAttribute('required', 'required');
    }
    
    modal.classList.add('visible');
}

function closeUserModal() {
    document.getElementById('user-modal').classList.remove('visible');
}

async function saveUser(e) {
    e.preventDefault();
    
    const userId = document.getElementById('user-id').value;
    const name = document.getElementById('modal-user-name').value.trim();
    const email = document.getElementById('modal-user-email').value.trim();
    const password = document.getElementById('modal-user-password').value;
    const role = document.getElementById('modal-user-role').value;
    const areas = Array.from(document.querySelectorAll('input[name="area"]:checked')).map(cb => cb.value);
    
    // Validate required fields for new users
    if (!userId && !password) {
        alert('Password is required for new users');
        return;
    }
    
    const userData = { name, email, role, areas };
    // Include password if provided (required for new users, optional for updates)
    if (password) {
        userData.password = password;
    }
    
    try {
        const url = userId ? `${API_BASE}/api/admin/users/${userId}` : `${API_BASE}/api/admin/users`;
        const response = await fetch(url, {
            method: userId ? 'PUT' : 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(userData)
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || 'Save failed');
        }
        
        alert(userId ? 'User updated!' : 'User created!');
        closeUserModal();
        await loadUsers();
    } catch (error) {
        console.error('Save user error:', error);
        alert('Error: ' + error.message);
    }
}

function editUser(userId) {
    openUserModal(userId);
}

async function deleteUser(userId) {
    if (!confirm('Delete this user?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/users/${userId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Delete failed');
        
        alert('User deleted!');
        await loadUsers();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Threshold
async function loadThreshold() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/threshold`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();
        const thresholdValue = data.threshold || 50;
        globalThreshold = thresholdValue; // Store in global variable
        document.getElementById('threshold-global').value = thresholdValue;
        document.getElementById('current-threshold-display').textContent = thresholdValue;
    } catch (error) {
        console.error('Load threshold error:', error);
        showThresholdStatus('Failed to load threshold', 'error');
    }
}

async function updateThreshold() {
    const value = parseInt(document.getElementById('threshold-global').value);
    if (!value || value < 1) {
        showThresholdStatus('Please enter a valid threshold value (minimum 1)', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/threshold`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ threshold: value })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Update failed');
        }
        
        // Update global threshold and reset alerts
        globalThreshold = value;
        lastAlertedAreas.clear();
        
        // Update display
        document.getElementById('current-threshold-display').textContent = value;
        showThresholdStatus(`Threshold successfully updated to ${value} people`, 'success');
        
    } catch (error) {
        console.error('Update threshold error:', error);
        showThresholdStatus(`Error: ${error.message}`, 'error');
    }
}

// Global variable to track notification timeout
let notificationTimeout = null;
let notificationFadeTimeout = null;
let alertTimeout = null;
let alertFadeTimeout = null;

function showThresholdAlert(message) {
    const statusDiv = document.getElementById('threshold-status');
    const statusText = document.getElementById('threshold-status-text');
    
    if (!statusDiv || !statusText) return;
    
    // Clear any existing timeouts
    if (alertTimeout) clearTimeout(alertTimeout);
    if (alertFadeTimeout) clearTimeout(alertFadeTimeout);
    
    // Set alert styles (red/warning)
    statusText.textContent = message;
    statusDiv.style.background = '#f8d7da';
    statusDiv.style.color = '#721c24';
    statusDiv.style.border = '3px solid #dc3545';
    statusDiv.style.transition = 'none';
    statusDiv.style.display = 'block';
    statusDiv.style.opacity = '1';
    
    // Auto-hide after 10 seconds
    alertFadeTimeout = setTimeout(() => {
        statusDiv.style.transition = 'opacity 0.3s ease';
        statusDiv.style.opacity = '0';
        alertTimeout = setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 300);
    }, 10000);
}

function showThresholdStatus(message, type) {
    const statusDiv = document.getElementById('threshold-status');
    const statusText = document.getElementById('threshold-status-text');
    
    console.log('showThresholdStatus called:', message, type);
    
    if (!statusDiv || !statusText) {
        console.error('Threshold status elements not found!');
        alert(message);
        return;
    }
    
    // Clear any existing timeouts to prevent interference
    if (notificationTimeout) {
        clearTimeout(notificationTimeout);
        notificationTimeout = null;
    }
    if (notificationFadeTimeout) {
        clearTimeout(notificationFadeTimeout);
        notificationFadeTimeout = null;
    }
    
    // Set content and styles
    statusText.textContent = message;
    
    if (type === 'success') {
        statusDiv.style.background = '#d4edda';
        statusDiv.style.color = '#155724';
        statusDiv.style.border = '3px solid #28a745';
    } else {
        statusDiv.style.background = '#f8d7da';
        statusDiv.style.color = '#721c24';
        statusDiv.style.border = '3px solid #dc3545';
    }
    
    // Force display and opacity immediately
    statusDiv.style.transition = 'none';
    statusDiv.style.display = 'block';
    statusDiv.style.opacity = '1';
    
    console.log('Final opacity:', window.getComputedStyle(statusDiv).opacity);
    console.log('Final display:', window.getComputedStyle(statusDiv).display);
    
    // Auto-hide after 5 seconds
    notificationFadeTimeout = setTimeout(() => {
        statusDiv.style.transition = 'opacity 0.3s ease';
        statusDiv.style.opacity = '0';
        notificationTimeout = setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 300);
    }, 5000);
}

function exportCSV(area) {
    window.location.href = `${API_BASE}/export/csv/${area}`;
}

// === Camera Feed Management ===

async function loadCameras() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/cameras`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            console.error('Failed to load cameras:', response.status);
            // Show existing areas from live data as fallback
            allCameras = await loadDefaultCamerasWithZoneCounts();
            renderCamerasTable();
            return;
        }
        
        const data = await response.json();
        allCameras = data.cameras || [];
        
        // If no cameras returned but we have live data, populate with default areas
        if (allCameras.length === 0) {
            allCameras = await loadDefaultCamerasWithZoneCounts();
        }
        
        // Fetch zone counts for each camera
        await fetchZoneCountsForCameras();
        
        renderCamerasTable();
    } catch (error) {
        console.error('Load cameras error:', error);
        // Show existing areas as fallback
        allCameras = await loadDefaultCamerasWithZoneCounts();
        renderCamerasTable();
    }
}

async function loadDefaultCamerasWithZoneCounts() {
    const defaultCameras = [
        { area_id: 1, area_name: 'entrance', video_source: 'youtube-videos/enterance.mp4', zone_count: 0 },
        { area_id: 2, area_name: 'retail', video_source: 'youtube-videos/retail.mp4', zone_count: 0 },
        { area_id: 3, area_name: 'foodcourt', video_source: 'youtube-videos/foodcourt.mp4', zone_count: 0 }
    ];
    
    // Fetch all zone counts in parallel
    const zoneCounts = await fetchAllZoneCounts();
    
    // Update cameras with zone counts from cache
    defaultCameras.forEach(camera => {
        camera.zone_count = zoneCounts[camera.area_name] || 0;
    });
    
    return defaultCameras;
}

// Fetch and cache zone counts for all areas in parallel
async function fetchAllZoneCounts() {
    const areas = ['entrance', 'retail', 'foodcourt'];
    const now = Date.now();
    const counts = {};
    
    // Check which areas need fresh data
    const areasToFetch = areas.filter(area => {
        const cacheAge = now - (zoneDataCache.lastUpdate[area] || 0);
        return !zoneDataCache[area] || cacheAge > ZONE_CACHE_TTL;
    });
    
    if (areasToFetch.length === 0) {
        // Return cached data
        areas.forEach(area => {
            counts[area] = zoneDataCache[area] ? zoneDataCache[area].length : 0;
        });
        return counts;
    }
    
    // Fetch fresh data in parallel
    const responses = await Promise.all(
        areasToFetch.map(area =>
            fetch(`${API_BASE}/api/admin/zones/by-name/${area}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            .then(r => r.ok ? r.json() : { zones: [] })
            .catch(err => {
                console.error(`Error loading zones for ${area}:`, err);
                return { zones: [] };
            })
        )
    );
    
    // Update cache
    areasToFetch.forEach((area, i) => {
        const zones = responses[i].zones || [];
        zoneDataCache[area] = zones;
        zoneDataCache.lastUpdate[area] = now;
        counts[area] = zones.length;
    });
    
    // Fill in cached data for areas not fetched
    areas.forEach(area => {
        if (!areasToFetch.includes(area)) {
            counts[area] = zoneDataCache[area] ? zoneDataCache[area].length : 0;
        }
    });
    
    return counts;
}

async function fetchZoneCountsForCameras() {
    const zoneCounts = await fetchAllZoneCounts();
    
    // Update all cameras with new zone counts
    allCameras.forEach(camera => {
        camera.zone_count = zoneCounts[camera.area_name] || 0;
    });
}

function renderCamerasTable() {
    const tbody = document.getElementById('cameras-table-body');
    if (!allCameras.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem;">No cameras configured</td></tr>';
        return;
    }
    
    tbody.innerHTML = allCameras.map(c => `
        <tr>
            <td><strong>${c.area_name}</strong></td>
            <td style="font-family: monospace; font-size: 0.85rem;">${c.video_source || 'Not set'}</td>
            <td><span style="background: var(--success-bg); color: var(--success); padding: 4px 8px; border-radius: 4px; font-size: 0.75rem;">Active</span></td>
            <td>${c.zone_count || 0} zones</td>
            <td>
                <label class="switch" style="display: inline-block;">
                    <input type="checkbox" ${c.visible_to_users !== false ? 'checked' : ''} onchange="toggleCameraVisibility(${c.area_id}, this.checked)">
                    <span class="slider"></span>
                </label>
            </td>
            <td>
                <button onclick="editCamera(${c.area_id})" class="btn-outline" style="padding: 0.5rem 1rem; margin-right: 0.5rem;">Edit</button>
                <button onclick="configureZones(${c.area_id}, '${c.area_name}')" class="btn-outline" style="padding: 0.5rem 1rem; margin-right: 0.5rem;">Zones</button>
                <button onclick="deleteCamera(${c.area_id})" class="btn-outline" style="padding: 0.5rem 1rem; background: var(--danger-bg); color: var(--danger);">Delete</button>
            </td>
        </tr>
    `).join('');
}

function openCameraModal(cameraId = null) {
    const modal = document.getElementById('camera-modal');
    const form = document.getElementById('camera-form');
    form.reset();
    document.getElementById('camera-id').value = '';
    
    if (cameraId) {
        const camera = allCameras.find(c => c.area_id === cameraId);
        document.getElementById('camera-modal-title').textContent = 'Edit Camera Feed';
        document.getElementById('camera-id').value = camera.area_id;
        document.getElementById('camera-area').value = camera.area_name;
        document.getElementById('camera-display').value = camera.display_name || camera.area_name;
        document.getElementById('camera-source').value = camera.video_source || '';
        document.getElementById('camera-model').value = camera.model_type || 'yolo';
        document.getElementById('camera-area').disabled = true; // Can't change area name
    } else {
        document.getElementById('camera-modal-title').textContent = 'Add Camera Feed';
        document.getElementById('camera-area').disabled = false;
    }
    
    modal.classList.add('visible');
}

function closeCameraModal() {
    document.getElementById('camera-modal').classList.remove('visible');
}

async function saveCamera(e) {
    e.preventDefault();
    
    const cameraId = document.getElementById('camera-id').value;
    const areaName = document.getElementById('camera-area').value.toLowerCase().trim();
    const displayName = document.getElementById('camera-display').value.trim();
    const videoSource = document.getElementById('camera-source').value.trim();
    const modelType = document.getElementById('camera-model').value;
    
    const cameraData = {
        area_name: areaName,
        display_name: displayName,
        video_source: videoSource,
        model_type: modelType
    };
    
    try {
        const url = cameraId 
            ? `${API_BASE}/api/admin/cameras/${cameraId}` 
            : `${API_BASE}/api/admin/cameras`;
        
        const response = await fetch(url, {
            method: cameraId ? 'PUT' : 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(cameraData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Save failed');
        }
        
        alert(cameraId ? 'Camera updated! Restart backend to apply changes.' : 'Camera added! Restart backend to apply changes.');
        closeCameraModal();
        await loadCameras();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function editCamera(cameraId) {
    openCameraModal(cameraId);
}

async function deleteCamera(cameraId) {
    if (!confirm('Delete this camera feed? This will also remove all associated zones and data.')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/cameras/${cameraId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) throw new Error('Delete failed');
        
        alert('Camera deleted! Restart backend to apply changes.');
        await loadCameras();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// === Zone Configuration ===

async function configureZones(areaId, areaName) {
    currentZoneArea = { id: areaId, name: areaName };
    document.getElementById('zone-area-name').textContent = areaName;
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/zones/${areaId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();
        const zones = data.zones || [];
        renderZonesList(zones);
        document.getElementById('zone-modal').classList.add('visible');
    } catch (error) {
        console.error('Load zones error:', error);
        renderZonesList([]);
        document.getElementById('zone-modal').classList.add('visible');
    }
}

function renderZonesList(zones) {
    const container = document.getElementById('zones-list');
    
    if (zones.length === 0) {
        container.innerHTML = `
            <div style="padding: 2rem; text-align: center; background: var(--bg-main); border-radius: var(--radius-sm);">
                <p style="color: var(--text-secondary);">No zones configured. Add zones to track specific areas.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = zones.map((zone, index) => `
        <div class="zone-row" data-zone-id="${zone.zone_id}" style="display: flex; gap: 1rem; align-items: center; padding: 1rem; background: var(--bg-main); border-radius: var(--radius-sm);">
            <div class="input-group" style="flex: 1; margin: 0;">
                <label style="font-size: 0.75rem;">Zone ID</label>
                <input type="text" class="zone-id" value="${zone.zone_id}" placeholder="e.g., 1, 2, A, B" style="padding: 0.5rem;">
            </div>
            <div class="input-group" style="flex: 2; margin: 0;">
                <label style="font-size: 0.75rem;">Zone Name</label>
                <input type="text" class="zone-name" value="${zone.zone_name || ''}" placeholder="e.g., Entrance Queue" style="padding: 0.5rem;">
            </div>
            <div class="input-group" style="flex: 1; margin: 0;">
                <label style="font-size: 0.75rem;">Coordinates</label>
                <input type="text" class="zone-coords" value="${zone.polygon_coords || ''}" placeholder="x1,y1,x2,y2..." style="padding: 0.5rem;">
            </div>
            <button onclick="removeZoneRow(this)" class="btn-outline" style="padding: 0.5rem 1rem; background: var(--danger-bg); color: var(--danger); margin-top: 1.5rem;">Delete</button>
        </div>
    `).join('');
}

function addZoneRow() {
    const container = document.getElementById('zones-list');
    
    // Remove "no zones" message if present
    if (container.querySelector('.zone-row') === null && container.textContent.includes('No zones')) {
        container.innerHTML = '';
    }
    
    const newRow = document.createElement('div');
    newRow.className = 'zone-row';
    newRow.style.cssText = 'display: flex; gap: 1rem; align-items: center; padding: 1rem; background: var(--bg-main); border-radius: var(--radius-sm);';
    newRow.innerHTML = `
        <div class="input-group" style="flex: 1; margin: 0;">
            <label style="font-size: 0.75rem;">Zone ID</label>
            <input type="text" class="zone-id" placeholder="e.g., 1, 2, A, B" style="padding: 0.5rem;">
        </div>
        <div class="input-group" style="flex: 2; margin: 0;">
            <label style="font-size: 0.75rem;">Zone Name</label>
            <input type="text" class="zone-name" placeholder="e.g., Entrance Queue" style="padding: 0.5rem;">
        </div>
        <div class="input-group" style="flex: 1; margin: 0;">
            <label style="font-size: 0.75rem;">Coordinates</label>
            <input type="text" class="zone-coords" placeholder="x1,y1,x2,y2..." style="padding: 0.5rem;">
        </div>
        <button onclick="removeZoneRow(this)" class="btn-outline" style="padding: 0.5rem 1rem; background: var(--danger-bg); color: var(--danger); margin-top: 1.5rem;">Delete</button>
    `;
    container.appendChild(newRow);
}

function removeZoneRow(button) {
    button.closest('.zone-row').remove();
    
    // Show "no zones" message if all removed
    const container = document.getElementById('zones-list');
    if (!container.querySelector('.zone-row')) {
        renderZonesList([]);
    }
}

async function saveZones() {
    if (!currentZoneArea) {
        alert('No area selected');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/zones/by-name/${currentZoneArea}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ zones })
        });
        
        if (!response.ok) throw new Error('Save failed');
        
        alert('Zones saved successfully!');
        closeZoneModal();
        await loadZonesForArea(currentZoneArea);
    } catch (error) {
        console.error('Error saving zones:', error);
        alert('Error: ' + error.message);
    }
}

function closeZoneModal() {
    document.getElementById('zone-modal').classList.remove('visible');
    currentZoneArea = null;
    if (zoneCanvas) {
        zoneCanvas.removeEventListener('click', handleZoneCanvasClick);
        zoneCanvas.removeEventListener('mousemove', handleZoneCanvasMouseMove);
    }
    // Reload cameras to update zone counts
    loadCameras();
    // Reload zones in the zones management section
    loadZonesForAllAreas();
}

// Toggle camera visibility for users
async function toggleCameraVisibility(areaId, visible) {
    try {
        const response = await fetch(`${API_BASE}/api/admin/cameras/${areaId}/visibility`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ visible_to_users: visible })
        });
        
        if (!response.ok) throw new Error('Failed to update visibility');
        
        const camera = allCameras.find(c => c.area_id === areaId);
        if (camera) camera.visible_to_users = visible;
    } catch (error) {
        console.error('Error toggling visibility:', error);
        alert('Failed to update camera visibility');
    }
}

// ========== VISUAL ZONE EDITOR ==========
let zoneCanvas = null;
let zoneCtx = null;
let zoneImage = new Image();
let zones = [];
let currentZone = null;
let drawingMode = false;
let tempPoints = [];
let selectedZone = null;
let dragPoint = null;

async function configureZones(areaName) {
    currentZoneArea = areaName;
    document.getElementById('zone-area-name').textContent = AREA_NAMES[areaName];
    
    // Load existing zones from database
    try {
        const response = await fetch(`${API_BASE}/api/admin/zones/by-name/${areaName}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            // Convert database format to editor format
            zones = (data.zones || []).map(z => ({
                id: z.zone_id,
                name: z.zone_name || `Zone_${z.zone_id}`,
                points: (z.coordinates || []).map(coord => ({ x: coord[0], y: coord[1] }))
            }));
        } else {
            zones = [];
        }
    } catch (error) {
        console.error('Load zones error:', error);
        zones = [];
    }
    
    // Setup canvas and video
    zoneCanvas = document.getElementById('zone-canvas');
    zoneCtx = zoneCanvas.getContext('2d');
    const zoneVideoPlayer = document.getElementById('zone-video-player');
    
    // Set video source based on area
    const videoSources = {
        'entrance': 'http://127.0.0.1:5000/videos/enterance.mp4',
        'retail': 'http://127.0.0.1:5000/videos/retail.mp4',
        'foodcourt': 'http://127.0.0.1:5000/videos/foodcourt.mp4'
    };
    
    zoneVideoPlayer.src = videoSources[areaName];
    
    // Wait for video to load
    zoneVideoPlayer.addEventListener('loadeddata', () => {
        zoneCanvas.width = 1280;
        zoneCanvas.height = 720;
        drawZones();
        updateZonesList();
    }, { once: true });
    
    // Add event listeners
    zoneCanvas.addEventListener('click', handleZoneCanvasClick);
    zoneCanvas.addEventListener('mousemove', handleZoneCanvasMouseMove);
    document.addEventListener('keydown', handleZoneKeyDown);
    
    document.getElementById('zone-modal').classList.add('visible');
}

function parseCoordinates(coordsStr) {
    if (!coordsStr) return [];
    const coords = coordsStr.split(',').map(n => parseInt(n.trim()));
    const points = [];
    for (let i = 0; i < coords.length; i += 2) {
        points.push({ x: coords[i], y: coords[i + 1] });
    }
    return points;
}

function drawZones() {
    if (!zoneCanvas || !zoneCtx) return;
    
    // Redraw base image
    zoneCtx.clearRect(0, 0, zoneCanvas.width, zoneCanvas.height);
    if (zoneImage.complete) {
        zoneCtx.drawImage(zoneImage, 0, 0);
    } else {
        zoneCtx.fillStyle = '#222';
        zoneCtx.fillRect(0, 0, zoneCanvas.width, zoneCanvas.height);
    }
    
    // Draw all zones
    zones.forEach((zone, idx) => {
        const isSelected = selectedZone === zone;
        zoneCtx.strokeStyle = isSelected ? '#00ff00' : '#ff0000';
        zoneCtx.lineWidth = isSelected ? 3 : 2;
        zoneCtx.fillStyle = isSelected ? 'rgba(0, 255, 0, 0.2)' : 'rgba(255, 0, 0, 0.2)';
        
        if (zone.points.length >= 2) {
            zoneCtx.beginPath();
            zoneCtx.moveTo(zone.points[0].x, zone.points[0].y);
            zone.points.forEach(p => zoneCtx.lineTo(p.x, p.y));
            zoneCtx.closePath();
            zoneCtx.fill();
            zoneCtx.stroke();
            
            // Draw corner points
            zone.points.forEach(p => {
                zoneCtx.fillStyle = isSelected ? '#00ff00' : '#ff0000';
                zoneCtx.beginPath();
                zoneCtx.arc(p.x, p.y, 5, 0, Math.PI * 2);
                zoneCtx.fill();
            });
            
            // Draw label
            const centerX = zone.points.reduce((sum, p) => sum + p.x, 0) / zone.points.length;
            const centerY = zone.points.reduce((sum, p) => sum + p.y, 0) / zone.points.length;
            zoneCtx.fillStyle = isSelected ? '#00ff00' : '#ffffff';
            zoneCtx.font = '14px Arial';
            zoneCtx.fillText(zone.name, centerX - 20, centerY);
        }
    });
    
    // Draw temp points during drawing
    if (drawingMode && tempPoints.length > 0) {
        zoneCtx.strokeStyle = '#ffff00';
        zoneCtx.lineWidth = 2;
        zoneCtx.beginPath();
        zoneCtx.moveTo(tempPoints[0].x, tempPoints[0].y);
        tempPoints.forEach(p => zoneCtx.lineTo(p.x, p.y));
        zoneCtx.stroke();
        
        tempPoints.forEach(p => {
            zoneCtx.fillStyle = '#ffff00';
            zoneCtx.beginPath();
            zoneCtx.arc(p.x, p.y, 5, 0, Math.PI * 2);
            zoneCtx.fill();
        });
    }
}

function handleZoneCanvasClick(event) {
    const rect = zoneCanvas.getBoundingClientRect();
    const scaleX = zoneCanvas.width / rect.width;
    const scaleY = zoneCanvas.height / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;
    
    if (drawingMode) {
        tempPoints.push({ x, y });
        
        if (tempPoints.length === 4) {
            // Find max zone ID and increment
            const maxId = zones.length > 0 ? Math.max(...zones.map(z => parseInt(z.id))) : 0;
            const zoneId = maxId + 1;
            const zoneName = `Zone ${zoneId}`;
            zones.push({ id: zoneId, name: zoneName, points: [...tempPoints] });
            tempPoints = [];
            drawingMode = false;
            updateZonesList();
        }
        
        drawZones();
    } else {
        // Check if clicked on existing zone
        selectedZone = null;
        for (let zone of zones) {
            if (isPointInPolygon({ x, y }, zone.points)) {
                selectedZone = zone;
                break;
            }
        }
        drawZones();
        updateZonesList();
    }
}

function handleZoneCanvasMouseMove(event) {
    if (!zoneCanvas) return;
    const rect = zoneCanvas.getBoundingClientRect();
    const scaleX = zoneCanvas.width / rect.width;
    const scaleY = zoneCanvas.height / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;
    
    // Highlight if hovering over zone
    zoneCanvas.style.cursor = zones.some(z => isPointInPolygon({ x, y }, z.points)) ? 'pointer' : 'crosshair';
}

function handleZoneKeyDown(event) {
    if (event.key === 'Delete' && selectedZone) {
        zones = zones.filter(z => z !== selectedZone);
        selectedZone = null;
        drawZones();
        updateZonesList();
    }
}

function isPointInPolygon(point, polygon) {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].x, yi = polygon[i].y;
        const xj = polygon[j].x, yj = polygon[j].y;
        const intersect = ((yi > point.y) !== (yj > point.y)) &&
            (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}

function startDrawingZone() {
    drawingMode = true;
    tempPoints = [];
    selectedZone = null;
    alert('Click 4 corners on the video to create a rectangular zone');
}

function clearSelectedZone() {
    if (selectedZone) {
        zones = zones.filter(z => z !== selectedZone);
        selectedZone = null;
        drawZones();
        updateZonesList();
    } else {
        alert('No zone selected. Click on a zone to select it first.');
    }
}

function clearAllZones() {
    if (confirm('Are you sure you want to delete all zones?')) {
        zones = [];
        selectedZone = null;
        drawZones();
        updateZonesList();
    }
}

function updateZonesList() {
    const container = document.getElementById('zones-list-items');
    if (zones.length === 0) {
        container.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem;">No zones yet. Click "Draw New Zone" to start.</div>';
        return;
    }
    
    container.innerHTML = zones.map(zone => {
        const coords = zone.points.map(p => `${p.x},${p.y}`).join(',');
        const isSelected = selectedZone === zone;
        return `
            <div onclick="selectZoneFromList('${zone.id}')" style="padding: 0.75rem; background: ${isSelected ? 'var(--primary-bg)' : 'var(--bg-secondary)'}; border-radius: 5px; margin-bottom: 0.5rem; cursor: pointer; border: ${isSelected ? '2px solid var(--primary)' : '1px solid var(--border-color)'};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong style="color: ${isSelected ? 'var(--primary)' : 'var(--text-primary)'};">${zone.name}</strong>
                    <button onclick="event.stopPropagation(); editZoneName('${zone.id}')" style="padding: 4px 8px; font-size: 0.75rem; background: none; border: 1px solid var(--border-color); border-radius: 3px; cursor: pointer;">✏️</button>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem; font-family: monospace;">${zone.points.length} points</div>
            </div>
        `;
    }).join('');
}

function selectZoneFromList(zoneId) {
    selectedZone = zones.find(z => z.id == zoneId);
    drawZones();
    updateZonesList();
}

function editZoneName(zoneId) {
    const zone = zones.find(z => z.id == zoneId);
    if (zone) {
        const newName = prompt('Enter zone name:', zone.name);
        if (newName && newName.trim()) {
            zone.name = newName.trim();
            updateZonesList();
            drawZones();
        }
    }
}

async function saveZones() {
    if (!currentZoneArea) {
        alert('No area selected!');
        return;
    }
    
    if (zones.length === 0) {
        alert('No zones to save. Draw at least one zone first.');
        return;
    }
    
    try {
        // Convert zones to the format expected by the API
        const zonesData = zones.map(z => ({
            id: parseInt(z.id),
            name: z.name,
            points: z.points.map(p => [Math.round(p.x), Math.round(p.y)])
        }));
        
        console.log('Saving zones:', zonesData);
        
        // Use the by-name endpoint which syncs to both DB and JSON
        const response = await fetch(`${API_BASE}/api/admin/zones/by-name/${currentZoneArea}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ zones: zonesData })
        });
        
        const responseData = await response.json();
        console.log('Save response:', responseData);
        
        if (!response.ok) {
            throw new Error(responseData.error || 'Failed to save zones');
        }
        
        // Show success message with zone count
        const zonesCount = responseData.zones_saved || zones.length;
        alert(`✅ Success! ${zonesCount} zone(s) saved to database and synced to file.\n\nThe zones will be automatically loaded by the video processing system within 5 seconds.`);
        closeZoneModal();
        
        // Reload zones list and cameras
        await loadZonesForAllAreas();
        await loadCameras();
    } catch (error) {
        console.error('Save zones error:', error);
        alert('❌ Error saving zones: ' + error.message);
    }
}

// ========== VIDEO PLAYER ==========
let videoCanvas = null;
let videoCtx = null;
let videoPlayer = null;
let currentVideoArea = 'entrance';
let videoUpdateInterval = null;

const VIDEO_SOURCES = {
    'entrance': 'http://127.0.0.1:5000/videos/enterance.mp4',
    'retail': 'http://127.0.0.1:5000/videos/retail.mp4',
    'foodcourt': 'http://127.0.0.1:5000/videos/foodcourt.mp4'
};

function switchVideoFeed() {
    currentVideoArea = document.getElementById('video-area-selector').value;
    document.getElementById('current-area-display').textContent = currentVideoArea;
    
    // Change video source
    if (videoPlayer) {
        videoPlayer.src = VIDEO_SOURCES[currentVideoArea];
        videoPlayer.play();
    }
    
    // Update immediately
    updateVideoFrame();
}

function startVideoPlayer() {
    console.log('🎥 Starting video player...');
    
    // Get video element
    videoPlayer = document.getElementById('video-player');
    videoCanvas = document.getElementById('video-canvas');
    
    if (!videoPlayer || !videoCanvas) {
        console.log('❌ Video elements not found, retrying in 500ms...');
        setTimeout(startVideoPlayer, 500);
        return;
    }
    
    videoCtx = videoCanvas.getContext('2d');
    console.log('✅ Video player and canvas initialized!');
    
    // Add error handlers
    videoPlayer.onerror = (e) => {
        console.error('❌ VIDEO ERROR:', e);
        console.error('Video source:', videoPlayer.src);
        console.error('Video error code:', videoPlayer.error ? videoPlayer.error.code : 'unknown');
    };
    
    videoPlayer.onloadeddata = () => {
        console.log('✅ VIDEO LOADED SUCCESSFULLY!');
        console.log('Video dimensions:', videoPlayer.videoWidth, 'x', videoPlayer.videoHeight);
    };
    
    videoPlayer.onplay = () => {
        console.log('▶️ VIDEO IS PLAYING');
    };
    
    // Force video to be visible
    videoPlayer.style.display = 'block';
    videoPlayer.style.visibility = 'visible';
    videoPlayer.style.opacity = '1';
    videoPlayer.style.width = '100%';
    videoPlayer.style.height = 'auto';
    videoPlayer.style.minHeight = '400px';
    videoPlayer.style.background = '#000';
    
    console.log('Video element styles set:', {
        display: videoPlayer.style.display,
        visibility: videoPlayer.style.visibility,
        opacity: videoPlayer.style.opacity,
        src: videoPlayer.src
    });
    
    // Start video
    videoPlayer.src = VIDEO_SOURCES[currentVideoArea];
    videoPlayer.load();
    videoPlayer.play().then(() => {
        console.log('✅ Video play() promise resolved');
    }).catch(err => {
        console.error('❌ Video play() failed:', err);
    });
    
    // Start fetching detection data
    if (videoUpdateInterval) clearInterval(videoUpdateInterval);
    videoUpdateInterval = setInterval(updateVideoFrame, 500);
    
    // Update immediately
    setTimeout(updateVideoFrame, 500);
}

async function updateVideoFrame() {
    if (!videoCanvas || !videoCtx) return;
    
    try {
        const response = await fetch(`${API_BASE}/live/${currentVideoArea}`);
        const data = await response.json();
        
        // Update info display
        const peopleEl = document.getElementById('people-display');
        const fpsEl = document.getElementById('fps-display');
        if (peopleEl) peopleEl.textContent = data.count || 0;
        if (fpsEl) fpsEl.textContent = '2 FPS';
        
        // Clear canvas for new frame
        videoCtx.clearRect(0, 0, 1280, 720);
        
        // Draw detection boxes and zones on overlay
        if (data.zones) {
            const zoneEntries = Object.entries(data.zones);
            
            zoneEntries.forEach(([zoneId, count], index) => {
                const x = 50 + index * 200;
                const y = 100;
                const width = 180;
                const height = 120;
                
                // Draw zone box
                videoCtx.shadowColor = count > 0 ? '#ff0000' : '#444ce7';
                videoCtx.shadowBlur = 20;
                videoCtx.strokeStyle = count > 0 ? '#ff0000' : '#444ce7';
                videoCtx.lineWidth = 4;
                videoCtx.strokeRect(x, y, width, height);
                
                // Fill with semi-transparent color
                videoCtx.fillStyle = count > 0 ? 'rgba(255, 0, 0, 0.2)' : 'rgba(68, 76, 231, 0.2)';
                videoCtx.fillRect(x, y, width, height);
                
                videoCtx.shadowBlur = 0;
                
                // Draw zone label
                videoCtx.fillStyle = '#ffffff';
                videoCtx.font = 'bold 20px Arial';
                videoCtx.textAlign = 'center';
                videoCtx.fillText(`Zone ${zoneId}`, x + width / 2, y + 35);
                
                // Draw count
                videoCtx.font = 'bold 40px Arial';
                videoCtx.fillStyle = count > 0 ? '#ff3333' : '#00ff00';
                videoCtx.fillText(count.toString(), x + width / 2, y + 80);
                
                videoCtx.font = '14px Arial';
                videoCtx.fillStyle = '#ffffff';
                videoCtx.fillText('people', x + width / 2, y + 105);
            });
        }
        
        // Draw total count badge (large, bottom right)
        const badgeX = 1280 - 250;
        const badgeY = 720 - 120;
        
        videoCtx.fillStyle = 'rgba(0, 0, 0, 0.85)';
        videoCtx.fillRect(badgeX, badgeY, 230, 100);
        
        videoCtx.strokeStyle = '#00ff00';
        videoCtx.lineWidth = 3;
        videoCtx.strokeRect(badgeX, badgeY, 230, 100);
        
        videoCtx.fillStyle = '#ffffff';
        videoCtx.font = 'bold 18px Arial';
        videoCtx.textAlign = 'center';
        videoCtx.fillText('TOTAL', badgeX + 115, badgeY + 30);
        
        videoCtx.font = 'bold 48px Arial';
        videoCtx.fillStyle = '#00ff00';
        videoCtx.fillText((data.count || 0).toString(), badgeX + 115, badgeY + 75);
        
        videoCtx.textAlign = 'left';
        
    } catch (error) {
        console.error('❌ Error updating video overlay:', error);
    }
}

// ========== HEATMAPS ==========
let heatmapData = {
    entrance: {},
    retail: {},
    foodcourt: {}
};

async function updateHeatmaps() {
    const areas = ['entrance', 'retail', 'foodcourt'];
    
    for (const area of areas) {
        try {
            const response = await fetch(`${API_BASE}/live/${area}`);
            const data = await response.json();
            heatmapData[area] = data.zone_counts || {};
            await renderHeatmap(area);
        } catch (error) {
            console.error(`Error updating heatmap for ${area}:`, error);
        }
    }
}

async function renderHeatmap(area) {
    const canvas = document.getElementById(`heatmap-${area}`);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, width, height);
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/zones/by-name/${area}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            drawNoDataMessage(ctx, width, height);
            return;
        }
        
        const data = await response.json();
        const zones = data.zones || [];
        
        if (zones.length === 0) {
            drawNoDataMessage(ctx, width, height);
            return;
        }
        
        const counts = Object.values(heatmapData[area]);
        const maxCount = Math.max(...counts, 1);
        
        zones.forEach(zone => {
            const zoneCount = heatmapData[area][zone.zone_id] || 0;
            const intensity = maxCount > 0 ? zoneCount / maxCount : 0;
            const coords = zone.coordinates || [];
            if (coords.length < 3) return;
            
            const scaleX = width / 1280;
            const scaleY = height / 720;
            
            ctx.beginPath();
            ctx.moveTo(coords[0][0] * scaleX, coords[0][1] * scaleY);
            coords.forEach(coord => {
                ctx.lineTo(coord[0] * scaleX, coord[1] * scaleY);
            });
            ctx.closePath();
            
            ctx.fillStyle = getHeatColor(intensity);
            ctx.fill();
            
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            const centerX = coords.reduce((sum, c) => sum + c[0], 0) / coords.length * scaleX;
            const centerY = coords.reduce((sum, c) => sum + c[1], 0) / coords.length * scaleY;
            
            ctx.fillStyle = 'white';
            ctx.font = 'bold 16px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`Zone ${zone.zone_id}`, centerX, centerY - 10);
            
            ctx.font = 'bold 20px Arial';
            ctx.fillText(`${zoneCount}`, centerX, centerY + 10);
        });
    } catch (error) {
        console.error(`Error rendering heatmap for ${area}:`, error);
        drawNoDataMessage(ctx, width, height);
    }
}

function getHeatColor(intensity) {
    if (intensity < 0.25) {
        return `rgba(0, 255, 0, ${0.3 + intensity * 0.4})`;
    } else if (intensity < 0.5) {
        return `rgba(128, 255, 0, ${0.4 + intensity * 0.4})`;
    } else if (intensity < 0.75) {
        return `rgba(255, 200, 0, ${0.5 + intensity * 0.3})`;
    } else {
        const red = 255;
        const green = Math.round(255 * (1 - intensity));
        return `rgba(${red}, ${green}, 0, ${0.6 + intensity * 0.3})`;
    }
}

function drawNoDataMessage(ctx, width, height) {
    ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
    ctx.font = '16px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('No zones configured', width / 2, height / 2);
}

// Update heatmaps only when analytics tab is visible - more efficient
setInterval(() => {
    const analyticsVisible = document.getElementById('section-analytics-heatmaps').style.display !== 'none';
    if (analyticsVisible) {
        updateHeatmaps();
    }
}, 5000); // Reduced from 3s to 5s for better performance

// ========== ZONE SYNC FUNCTIONS ==========
async function syncAllZones() {
    if (!confirm('Sync all zones from database to JSON files?\n\nThis will ensure the video processing system has the latest zone configurations.')) {
        return;
    }
    
    try {
        console.log('Syncing all zones...', { token: token ? 'present' : 'missing' });
        
        const response = await fetch(`${API_BASE}/api/admin/zones/sync-all`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        console.log('Sync response status:', response.status);
        
        // Check content type to ensure we got JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            console.error('Unexpected content type:', contentType);
            const textResponse = await response.text();
            console.error('Response body (first 500 chars):', textResponse.substring(0, 500));
            throw new Error('Server returned non-JSON response. Please check if backend is running and endpoint exists.');
        }
        
        const data = await response.json();
        console.log('Sync response data:', data);
        
        if (!response.ok) {
            throw new Error(data.error || `Server error: ${response.status}`);
        }
        
        const summary = Object.entries(data.areas_synced || {})
            .map(([area, count]) => `  • ${area}: ${count} zones`)
            .join('\n');
        
        alert(`✅ All zones synced successfully!\n\n${summary}\n\nZones will be loaded by the video system within 5 seconds.`);
        
        // Reload the zones display
        await loadZonesForAllAreas();
        
    } catch (error) {
        console.error('Sync error:', error);
        alert('❌ Error syncing zones: ' + error.message);
    }
}

