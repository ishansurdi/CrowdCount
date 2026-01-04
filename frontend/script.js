/**
 * CrowdCount Premium Dashboard - Real Backend Integration with Role-Based Access
 */
const dashboard = (() => {
    const API_BASE = 'http://127.0.0.1:5000';
    const AREAS = ['entrance', 'retail', 'foodcourt'];
    const AREA_NAMES = {
        'entrance': 'Mall Entrance',
        'retail': 'Retail Area',
        'foodcourt': 'Food Court'
    };
    
    let charts = {};
    let globalThreshold = 50;
    let alertCooldown = false;
    let cooldownTimer = null;
    let historyData = { labels: [], entrance: [], retail: [], foodcourt: [] };
    let lastFetchTime = Date.now();
    let totalRecords = 0;
    let currentUser = null;
    let authToken = null;
    let userAreas = []; // Areas assigned to current user
    let allUsers = []; // For admin user management

    // Check authentication on page load
    const checkAuth = () => {
        authToken = localStorage.getItem('crowdcount_token');
        const userStr = localStorage.getItem('crowdcount_user');
        
        if (!authToken || !userStr) {
            // No credentials, redirect to login
            window.location.href = '/login.html';
            return false;
        }
        
        try {
            currentUser = JSON.parse(userStr);
            console.log(`✅ Logged in as: ${currentUser.name} (${currentUser.role})`);
            
            // Update UI based on role
            updateUIForRole();
            return true;
        } catch (e) {
            console.error('Invalid user data');
            window.location.href = '/login.html';
            return false;
        }
    };

    const updateUIForRole = () => {
        // Add user info to header if element exists
        const header = document.querySelector('header');
        if (header && currentUser) {
            const userInfo = document.createElement('div');
            userInfo.style.cssText = 'display: flex; align-items: center; gap: 12px;';
            userInfo.innerHTML = `
                <span style="color: var(--text-secondary); font-size: 0.875rem;">
                    ${currentUser.name} <span style="background: var(--accent-soft); color: var(--accent); padding: 2px 8px; border-radius: 4px; font-weight: 600; text-transform: uppercase; font-size: 0.7rem;">${currentUser.role}</span>
                </span>
                <button onclick="dashboard.logout()" style="
                    padding: 0.5rem 1rem;
                    background: var(--danger);
                    color: white;
                    border: none;
                    border-radius: var(--radius-sm);
                    cursor: pointer;
                    font-size: 0.875rem;
                    font-weight: 500;
                ">Logout</button>
            `;
            header.appendChild(userInfo);
        }
        
        // Get user's assigned areas from localStorage
        userAreas = currentUser.areas || [];
        
        // Show/hide elements based on role
        if (currentUser && currentUser.role === 'admin') {
            // Admin: Show all areas and admin-only features
            document.querySelectorAll('[data-role=\"admin\"]').forEach(el => {
                el.style.display = '';
            });
            userAreas = AREAS; // Admin sees all areas
            
            // Load users for admin panel
            loadUsers();
        } else {
            // User: Hide admin features and filter areas
            document.querySelectorAll('[data-role=\"admin\"]').forEach(el => {
                el.style.display = 'none';
            });
            
            // Hide areas not assigned to user
            document.querySelectorAll('[data-area]').forEach(el => {
                const area = el.getAttribute('data-area');
                if (!userAreas.includes(area)) {
                    el.style.display = 'none';
                }
            });
        }
        
        // Generate export buttons based on user's areas
        generateExportButtons();
        
        console.log(`✅ UI configured for ${currentUser.role}: ${userAreas.length} area(s)`);
    };

    const logout = () => {
        localStorage.removeItem('crowdcount_token');
        localStorage.removeItem('crowdcount_user');
        document.cookie = 'crowdcount_token=; path=/; max-age=0';
        window.location.href = '/login.html';
    };

    const init = () => {
        // Check authentication first
        if (!checkAuth()) {
            return;
        }
        
        setupCharts();
        startDataFetching();
        setupEventListeners();
    };

    const setupCharts = () => {
        // Bar Chart for Zone Distribution
        const ctxBar = document.getElementById('zoneBarChart').getContext('2d');
        charts.bar = new Chart(ctxBar, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [] // Will be populated dynamically based on user areas
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { 
                        position: 'bottom', 
                        labels: { boxWidth: 12, usePointStyle: true, padding: 15 } 
                    } 
                },
                scales: { 
                    y: { 
                        beginAtZero: true, 
                        grid: { borderDash: [4, 4], color: '#eaecf0' },
                        ticks: { stepSize: 1 }
                    }, 
                    x: { grid: { display: false } } 
                }
            }
        });

        // Line Chart for Historical Data
        const ctxLine = document.getElementById('historyLineChart').getContext('2d');
        charts.line = new Chart(ctxLine, {
            type: 'line',
            data: {
                labels: [],
                datasets: [] // Will be populated dynamically based on user areas
            },                        pointRadius: 2,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: { 
                    legend: { 
                        position: 'bottom',
                        labels: { boxWidth: 12, usePointStyle: true, padding: 15 }
                    } 
                },
                scales: { 
                    y: { 
                        grid: { color: '#eaecf0' },
                        beginAtZero: true
                    }, 
                    x: { grid: { display: false } } 
                }
            }
        });
    };

    const startDataFetching = () => {
        // Fetch only user's assigned areas data every 2 seconds
        fetchAllAreasData();
        setInterval(() => {
            fetchAllAreasData();
        }, 2000);

        // Fetch historical data every 10 seconds
        fetchHistoricalData();
        setInterval(() => {
            fetchHistoricalData();
        }, 10000);
    };

    const fetchAllAreasData = async () => {
        const startTime = Date.now();
        
        try {
            // Only fetch data for areas assigned to current user
            const promises = userAreas.map(area => 
                fetch(`${API_BASE}/live/${area}`).then(r => r.json())
            );
            
            const results = await Promise.all(promises);
            
            results.forEach((data, index) => {
                const area = userAreas[index];
                updateAreaMetrics(area, data);
            });

            // Update charts with all data
            updateZoneChart(results);
            
            // Calculate latency
            const latency = Date.now() - startTime;
            document.getElementById('diag-latency').textContent = `${latency}ms`;
            
            // Update status
            updateUIStatus(true);
            
            // Update last update time
            const now = new Date();
            document.getElementById('last-update').textContent = now.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit' 
            });

            totalRecords++;
            document.getElementById('diag-records').textContent = totalRecords;

            // Check thresholds
            checkAllThresholds(results);
            
        } catch (error) {
            console.error('Failed to fetch data:', error);
            updateUIStatus(false);
        }
    };

    const updateAreaMetrics = (area, data) => {
        // Update live count
        const countEl = document.getElementById(`live-count-${area}`);
        if (countEl) {
            countEl.textContent = data.live_people || 0;
        }

        // Update zone breakdown
        const zonesEl = document.getElementById(`zones-${area}`);
        if (zonesEl && data.zone_counts) {
            const zoneEntries = Object.entries(data.zone_counts);
            
            if (zoneEntries.length > 0) {
                zonesEl.innerHTML = zoneEntries.map(([zoneId, count]) => `
                    <div class="zone-item">
                        <span class="zone-name">Zone ${zoneId}</span>
                        <span class="zone-val">${count}</span>
                    </div>
                `).join('');
            } else {
                zonesEl.innerHTML = '<div class="zone-item"><span class="zone-name">No zones configured</span></div>';
            }
        }

        // Update badge status
        const badge = document.getElementById(`badge-${area}`);
        if (badge) {
            const count = data.live_people || 0;
            if (count > globalThreshold) {
                badge.style.color = 'var(--danger)';
                badge.style.background = 'var(--danger-bg)';
                badge.textContent = 'High Density';
            } else if (count > globalThreshold * 0.7) {
                badge.style.color = 'var(--warning)';
                badge.style.background = 'var(--warning-bg)';
                badge.textContent = 'Moderate';
            } else {
                badge.style.color = 'var(--success)';
                badge.style.background = 'var(--success-bg)';
                badge.textContent = 'Optimal';
            }
        }
    };

    const updateZoneChart = (areasData) => {
        // Collect all zones from user's assigned areas
        const zoneLabels = new Set();
        const areaZones = {};

        areasData.forEach((data, index) => {
            const area = userAreas[index];
            areaZones[area] = data.zone_counts || {};
            Object.keys(areaZones[area]).forEach(zoneId => {
                zoneLabels.add(`Zone ${zoneId}`);
            });
        });

        const labels = Array.from(zoneLabels).sort();
        
        // Update datasets - only show user's areas
        charts.bar.data.labels = labels;
        
        // Clear all datasets first
        charts.bar.data.datasets = [];
        
        // Add dataset for each user area
        const colors = {
            'entrance': '#444ce7',
            'retail': '#7f56d9',
            'foodcourt': '#067647'
        };
        
        userAreas.forEach(area => {
            charts.bar.data.datasets.push({
                label: AREA_NAMES[area],
                data: labels.map(label => {
                    const zoneId = label.replace('Zone ', '');
                    return areaZones[area] ? (areaZones[area][zoneId] || 0) : 0;
                }),
                backgroundColor: colors[area] || '#667085',
                borderRadius: 6
            });
        });

        charts.bar.update('none');
    };

    const fetchHistoricalData = async () => {
        try {
            // Fetch only for user's assigned areas
            const promises = userAreas.map(area => 
                fetch(`${API_BASE}/history/${area}?limit=30`).then(r => r.json())
            );
            
            const results = await Promise.all(promises);
            
            // Combine historical data
            const maxLength = 30;
            const combinedTimestamps = new Set();
            
            results.forEach(data => {
                if (data.history && data.history.length > 0) {
                    data.history.forEach(record => {
                        combinedTimestamps.add(record.timestamp);
                    });
                }
            });

            const timestamps = Array.from(combinedTimestamps).sort().slice(-maxLength);
            
            // Build data arrays
            const labels = timestamps.map(ts => {
                const date = new Date(ts);
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            });

            // Clear all datasets
            charts.line.data.datasets = [];
            
            // Add dataset for each user area
            const colors = {
                'entrance': { border: '#444ce7', bg: 'rgba(68, 76, 231, 0.1)' },
                'retail': { border: '#7f56d9', bg: 'rgba(127, 86, 217, 0.1)' },
                'foodcourt': { border: '#067647', bg: 'rgba(6, 118, 71, 0.1)' }
            };
            
            userAreas.forEach((area, index) => {
                const areaData = timestamps.map(ts => {
                    const record = results[index].history?.find(r => r.timestamp === ts);
                    return record ? record.total : 0;
                });
                
                charts.line.data.datasets.push({
                    label: AREA_NAMES[area],
                    data: areaData,
                    borderColor: colors[area]?.border || '#667085',
                    backgroundColor: colors[area]?.bg || 'rgba(102, 112, 133, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    pointRadius: 2,
                    fill: true
                });
            });

            // Update line chart
            charts.line.data.labels = labels;
            charts.line.update('none');

        } catch (error) {
            console.error('Failed to fetch historical data:', error);
        }
    };

    const checkAllThresholds = (areasData) => {
        if (alertCooldown) return;

        const exceededAreas = [];
        
        areasData.forEach((data, index) => {
            const area = AREAS[index];
            const count = data.live_people || 0;
            if (count > globalThreshold) {
                exceededAreas.push({
                    area: area,
                    count: count,
                    name: data.name || area
                });
            }
        });

        if (exceededAreas.length > 0) {
            triggerAlert(exceededAreas);
        }
    };

    const triggerAlert = (exceededAreas) => {
        const popup = document.getElementById('alert-popup');
        const messageEl = document.getElementById('alert-message');
        
        let message = `The following area${exceededAreas.length > 1 ? 's have' : ' has'} exceeded the threshold (${globalThreshold}):\n\n`;
        
        exceededAreas.forEach(area => {
            message += `• ${area.name}: ${area.count} people\n`;
        });

        messageEl.innerHTML = message.replace(/\n/g, '<br>');
        popup.classList.add('visible');
        alertCooldown = true;

        // Start 20-second cooldown animation
        const progress = document.getElementById('cooldown-progress');
        progress.style.transition = 'none';
        progress.style.width = '100%';
        
        setTimeout(() => {
            progress.style.transition = 'width 20s linear';
            progress.style.width = '0%';
        }, 100);

        // Auto-hide and reset after 20 seconds
        cooldownTimer = setTimeout(() => {
            alertCooldown = false;
            // Don't auto-close, wait for user acknowledgment
        }, 20000);
    };

    const updateUIStatus = (online) => {
        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');
        const apiStatus = document.getElementById('diag-api');
        
        if (online) {
            dot.classList.add('active');
            text.textContent = "Systems Live";
            apiStatus.textContent = "Responsive";
            apiStatus.style.color = "var(--success)";
        } else {
            dot.classList.remove('active');
            text.textContent = "Offline";
            apiStatus.textContent = "Disconnected";
            apiStatus.style.color = "var(--danger)";
        }
    };

    const setupEventListeners = () => {
        document.getElementById('close-alert-btn').addEventListener('click', () => {
            const popup = document.getElementById('alert-popup');
            popup.classList.remove('visible');
            
            // Reset cooldown progress
            const progress = document.getElementById('cooldown-progress');
            progress.style.transition = 'none';
            progress.style.width = '100%';
        });
    };

    const updateGlobalThreshold = async () => {
        const input = document.getElementById('threshold-global');
        const value = parseInt(input.value);

        if (!value || value < 1) {
            alert('Please enter a valid threshold (minimum 1)');
            return;
        }

        globalThreshold = value;

        // Set global threshold in backend (Milestone-4)
        try {
            const token = localStorage.getItem('crowdcount_token');
            const response = await fetch(`${API_BASE}/api/admin/threshold`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ threshold: value })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to update threshold');
            }
            
            const result = await response.json();
            
            // Show success feedback
            const btn = document.querySelector('button.btn-primary');
            const originalText = btn.textContent;
            btn.textContent = '✓ Applied';
            btn.style.background = 'var(--success)';
            
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = 'var(--accent)';
            }, 2000);

            console.log(`Global threshold set to ${value} for all areas`);
        } catch (error) {
            console.error('Failed to set threshold:', error);
            alert('Failed to update threshold: ' + error.message);
        }
    };

    const exportData = (area) => {
        const btn = event.currentTarget;
        const originalText = btn.innerHTML;
        btn.innerHTML = '<span style="opacity: 0.7;">Processing...</span>';
        btn.disabled = true;

        // Trigger CSV download
        window.location.href = `${API_BASE}/export/csv/${area}`;

        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
            
            // Show success toast
            showToast(`✓ ${area.charAt(0).toUpperCase() + area.slice(1)} CSV exported successfully`);
        }, 1500);
    };

    const showToast = (message) => {
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: var(--text-primary);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: var(--radius-md);
            font-size: 0.875rem;
            font-weight: 600;
            box-shadow: var(--shadow-md);
            z-index: 9999;
            animation: slideInRight 0.3s ease;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    // === User Management Functions (Admin Only) ===
    
    const generateExportButtons = () => {
        const container = document.getElementById('export-buttons-container');
        if (!container) return;
        
        container.innerHTML = userAreas.map(area => `
            <button class="btn-outline" onclick="dashboard.exportData('${area}')">
                📥 Export ${AREA_NAMES[area]} CSV
            </button>
        `).join('');
    };

    const loadUsers = async () => {
        try {
            const response = await fetch(`${API_BASE}/api/admin/users`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            
            if (!response.ok) throw new Error('Failed to load users');
            
            const data = await response.json();
            allUsers = data.users || [];
            renderUsersTable();
        } catch (error) {
            console.error('Failed to load users:', error);
            showToast('Failed to load users');
        }
    };

    const renderUsersTable = () => {
        const tbody = document.getElementById('users-table-body');
        if (!tbody || allUsers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 2rem; color: var(--text-tertiary);">No users found</td></tr>';
            return;
        }
        
        tbody.innerHTML = allUsers.map(user => `
            <tr style="border-bottom: 1px solid var(--border);">
                <td style="padding: 1rem;">${user.name}</td>
                <td style="padding: 1rem;">${user.email}</td>
                <td style="padding: 1rem;">
                    <span style="background: ${user.role === 'admin' ? 'var(--accent-soft)' : 'var(--success-bg)'}; 
                                 color: ${user.role === 'admin' ? 'var(--accent)' : 'var(--success)'}; 
                                 padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">
                        ${user.role}
                    </span>
                </td>
                <td style="padding: 1rem;">
                    ${user.areas && user.areas.length > 0 
                        ? user.areas.map(a => AREA_NAMES[a] || a).join(', ') 
                        : '<span style="color: var(--text-tertiary);">No areas assigned</span>'}
                </td>
                <td style="padding: 1rem;">
                    <button onclick="dashboard.editUser(${user.user_id})" class="btn-outline" style="padding: 0.5rem 1rem; margin-right: 0.5rem;">Edit</button>
                    <button onclick="dashboard.deleteUser(${user.user_id})" class="btn-outline" style="padding: 0.5rem 1rem; background: var(--danger-bg); color: var(--danger);">Delete</button>
                </td>
            </tr>
        `).join('');
    };

    const openUserModal = (userId = null) => {
        const modal = document.getElementById('user-modal');
        const title = document.getElementById('user-modal-title');
        const form = document.getElementById('user-form');
        
        // Reset form
        form.reset();
        document.getElementById('user-id').value = '';
        
        if (userId) {
            // Edit mode
            const user = allUsers.find(u => u.user_id === userId);
            if (!user) return;
            
            title.textContent = 'Edit User';
            document.getElementById('user-id').value = user.user_id;
            document.getElementById('user-name').value = user.name;
            document.getElementById('user-email').value = user.email;
            document.getElementById('user-role').value = user.role;
            
            // Check assigned areas
            document.querySelectorAll('input[name=\"area\"]').forEach(checkbox => {
                checkbox.checked = user.areas && user.areas.includes(checkbox.value);
            });
            
            // Hide password requirement for edit
            document.getElementById('password-field').querySelector('input').removeAttribute('required');
        } else {
            // Create mode
            title.textContent = 'Add New User';
            document.getElementById('password-field').querySelector('input').setAttribute('required', 'required');
        }
        
        modal.classList.add('visible');
    };

    const closeUserModal = () => {
        document.getElementById('user-modal').classList.remove('visible');
    };

    const saveUser = async (event) => {
        event.preventDefault();
        
        const userId = document.getElementById('user-id').value;
        const name = document.getElementById('user-name').value;
        const email = document.getElementById('user-email').value;
        const password = document.getElementById('user-password').value;
        const role = document.getElementById('user-role').value;
        
        // Get selected areas
        const selectedAreas = Array.from(document.querySelectorAll('input[name=\"area\"]:checked'))
            .map(cb => cb.value);
        
        const userData = {
            name,
            email,
            role,
            areas: selectedAreas
        };
        
        // Only include password if provided
        if (password) {
            userData.password = password;
        }
        
        try {
            const url = userId 
                ? `${API_BASE}/api/admin/users/${userId}` 
                : `${API_BASE}/api/admin/users`;
            
            const response = await fetch(url, {
                method: userId ? 'PUT' : 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify(userData)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to save user');
            }
            
            showToast(userId ? '✓ User updated successfully' : '✓ User created successfully');
            closeUserModal();
            await loadUsers();
        } catch (error) {
            console.error('Failed to save user:', error);
            alert('Failed to save user: ' + error.message);
        }
    };

    const editUser = (userId) => {
        openUserModal(userId);
    };

    const deleteUser = async (userId) => {
        const user = allUsers.find(u => u.user_id === userId);
        if (!user) return;
        
        if (!confirm(`Are you sure you want to delete user "${user.name}"?`)) {
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/admin/users/${userId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to delete user');
            }
            
            showToast('✓ User deleted successfully');
            await loadUsers();
        } catch (error) {
            console.error('Failed to delete user:', error);
            alert('Failed to delete user: ' + error.message);
        }
    };

    // Public API
    return { 
        init, 
        updateGlobalThreshold, 
        exportData,
        logout,
        openUserModal,
        closeUserModal,
        saveUser,
        editUser,
        deleteUser
    };
})();

// Initialize on page load
window.addEventListener('DOMContentLoaded', dashboard.init);
