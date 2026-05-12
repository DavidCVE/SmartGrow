
        // Configuration
        const API_BASE_URL = 'http://127.0.0.1:5000';
        const REFRESH_INTERVAL = 3000; // 3 seconds

        // DOM Elements
        const tempValueEl = document.getElementById('tempValue');
        const humidityValueEl = document.getElementById('humidityValue');
        const soilValueEl = document.getElementById('soilValue');
        const pumpValueEl = document.getElementById('pumpValue');
        const pumpToggleEl = document.getElementById('pumpToggle');
        const pumpIconEl = document.getElementById('pumpIcon');
        const pumpStatusLabelEl = document.getElementById('pumpStatusLabel');
        const connectionDotEl = document.getElementById('connectionDot');
        const connectionTextEl = document.getElementById('connectionText');
        const lastUpdatedEl = document.getElementById('lastUpdated');

        // State
        let isConnected = false;
        let fullHistoryData = [];
        let currentChartTimeframe = '24h';

        /**
         * Fetch current status from backend API
         */
        async function fetchCurrentStatus() {
            try {
                const response = await fetch(`${API_BASE_URL}/api/current-status`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                updateDashboard(data);
                setConnectionStatus(true);

            } catch (error) {
                console.error('Error fetching status:', error);
                setConnectionStatus(false);
            }
        }

        /**
         * Update dashboard with fetched data
         */
        function updateDashboard(data) {
            // Update temperature (supports both English and Romanian field names)
            if (data.temperature !== undefined || data.temperatura !== undefined) {
                const temp = data.temperature ?? data.temperatura;
                tempValueEl.textContent = parseFloat(temp).toFixed(1);
                tempValueEl.classList.remove('loading');
            }

            // Update air humidity
            if (data.humidity !== undefined || data.umiditate_aer !== undefined) {
                const humidity = data.humidity ?? data.umiditate_aer;
                humidityValueEl.textContent = parseFloat(humidity).toFixed(1);
                humidityValueEl.classList.remove('loading');
            }

            // Update soil moisture
            if (data.soil_moisture !== undefined || data.umiditate_sol !== undefined) {
                const soil = data.soil_moisture ?? data.umiditate_sol;
                soilValueEl.textContent = parseFloat(soil).toFixed(1);
                soilValueEl.classList.remove('loading');
            }

            // Update pump status
            const pumpStatus = data.pump_status ?? data.pompa_pornita;
            if (pumpStatus !== undefined) {
                const pumpOn = pumpStatus === true || pumpStatus === 'ON' || pumpStatus === 1;
                pumpValueEl.textContent = pumpOn ? 'ON' : 'OFF';
                pumpValueEl.classList.remove('loading');
                pumpValueEl.style.color = pumpOn ? '#2d6a4f' : '#6c757d';
                
                // Sync toggle button
                pumpToggleEl.checked = pumpOn;
                updatePumpUI(pumpOn);
            }

            // Update last updated time
            const now = new Date();
            lastUpdatedEl.textContent = `Last updated: ${now.toLocaleTimeString()}`;

            // Check for alerts
            generateAlerts(data);
        }

        /**
         * Dynamically generate alerts based on the latest data
         */
        function generateAlerts(data) {
            const tbody = document.getElementById('alertsTableBody');
            if (tbody) {
                tbody.innerHTML = '';
                
                const temp = data.temperature ?? data.temperatura;
                const soil = data.soil_moisture ?? data.umiditate_sol;
                let hasAlerts = false;

                if (temp !== undefined && parseFloat(temp) > 30) {
                    hasAlerts = true;
                    tbody.innerHTML += `
                        <tr>
                            <td><span class="alert-badge warning"><i class="fas fa-thermometer-full me-1"></i>Temperature</span></td>
                            <td>Temperature exceeded 30°C threshold (${parseFloat(temp).toFixed(1)}°C)</td>
                            <td>Just now</td>
                            <td><span class="badge bg-danger">Active</span></td>
                        </tr>
                    `;
                }

                if (soil !== undefined && parseFloat(soil) < 20) {
                    hasAlerts = true;
                    tbody.innerHTML += `
                        <tr>
                            <td><span class="alert-badge danger"><i class="fas fa-tint-slash me-1"></i>Soil</span></td>
                            <td>Soil moisture critically low (${parseFloat(soil).toFixed(1)}%)</td>
                            <td>Just now</td>
                            <td><span class="badge bg-danger">Active</span></td>
                        </tr>
                    `;
                }

                if (!hasAlerts) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="4" class="text-center text-muted py-3">
                                <i class="fas fa-check-circle text-success me-2"></i>All systems normal
                            </td>
                        </tr>
                    `;
                }
            }
        }

        /**
         * Set connection status indicator
         */
        function setConnectionStatus(connected) {
            isConnected = connected;
            if (connected) {
                connectionDotEl.classList.add('connected');
                connectionTextEl.textContent = 'Connected';
            } else {
                connectionDotEl.classList.remove('connected');
                connectionTextEl.textContent = 'Disconnected';
            }
        }

        /**
         * Toggle pump manually
         */
        /**
         * Toggle pump manually
         */
        async function togglePump() {
            const isOn = pumpToggleEl.checked;
            updatePumpUI(isOn);

            try {
                // Aici am corectat link-ul si formatul datelor pentru Python
                const response = await fetch(`${API_BASE_URL}/api/toggle-pump`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ state: isOn })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                console.log('Pump status updated:', isOn ? 'ON' : 'OFF');

            } catch (error) {
                console.error('Error toggling pump:', error);
                // Revert toggle on error
                pumpToggleEl.checked = !isOn;
                updatePumpUI(!isOn);
                alert('Eroare de conexiune cu serverul Python. Asigura-te ca e pornit!');
            }
        }

        /**
         * Update pump UI elements
         */
        function updatePumpUI(isOn) {
            if (isOn) {
                pumpIconEl.classList.add('active');
                pumpStatusLabelEl.textContent = 'ON';
                pumpStatusLabelEl.classList.add('on');
            } else {
                pumpIconEl.classList.remove('active');
                pumpStatusLabelEl.textContent = 'OFF';
                pumpStatusLabelEl.classList.remove('on');
            }
        }

        /**
         * Toggle sidebar for mobile
         */
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('active');
        }

        // Chart instance reference
        let historyChart = null;

        /**
         * Load and render the history chart
         */
        async function loadHistoryChart() {
            try {
                const response = await fetch(`${API_BASE_URL}/api/history`);

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();

                if (!data || data.length === 0) {
                    console.log('No history data available');
                    return;
                }

                fullHistoryData = data;
                updateQuickStats(fullHistoryData);
                renderChartBasedOnTimeframe();

                console.log('History chart loaded successfully');

            } catch (error) {
                console.error('Error loading history chart:', error);
            }
        }

        function updateQuickStats(dataArray) {
            if (!dataArray || dataArray.length === 0) return;
            
            let totalTemp = 0;
            let tempCount = 0;
            let pumpOnCount = 0;

            dataArray.forEach(entry => {
                const temp = entry.temperature ?? entry.temperatura;
                if (temp !== undefined && temp !== null) {
                    totalTemp += parseFloat(temp);
                    tempCount++;
                }
                const pump = entry.pump_status ?? entry.pompa_pornita;
                if (pump === true || pump === 'ON' || pump === 1) {
                    pumpOnCount++;
                }
            });

            if (tempCount > 0) {
                const avgTemp = (totalTemp / tempCount).toFixed(1);
                document.getElementById('avgTemp').textContent = `${avgTemp} °C`;
            }
            
            document.getElementById('wateringCount').textContent = `${pumpOnCount} times`;
            document.getElementById('uptime').textContent = '99.9%'; // Simulated uptime
        }

        function renderChartBasedOnTimeframe() {
            if (!fullHistoryData || fullHistoryData.length === 0) return;

            let filteredData = fullHistoryData;

            // Simplified time-based filtering depending on array length assumptions
            if (currentChartTimeframe === '24h') {
                filteredData = fullHistoryData.slice(Math.max(fullHistoryData.length - 24, 0));
            } else if (currentChartTimeframe === '7d') {
                filteredData = fullHistoryData.slice(Math.max(fullHistoryData.length - 168, 0)); 
            } else if (currentChartTimeframe === '30d') {
                filteredData = fullHistoryData.slice(Math.max(fullHistoryData.length - 720, 0)); 
            }

            // Map data to arrays
            const labels = filteredData.map((entry, index) => {
                // Use timestamp if available, otherwise use index
                if (entry.timestamp) {
                    const date = new Date(entry.timestamp);
                    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                }
                return `#${index + 1}`;
            });

            const temperatures = filteredData.map(entry => 
                entry.temperature ?? entry.temperatura ?? null
            );

            const humidities = filteredData.map(entry => 
                entry.humidity ?? entry.umiditate_aer ?? null
            );

            // Get the canvas context
            const ctx = document.getElementById('historyChart').getContext('2d');

            // Destroy existing chart if it exists
            if (historyChart) {
                historyChart.destroy();
            }

            // Create the chart
                historyChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'Temperature (°C)',
                                data: temperatures,
                                borderColor: 'rgba(255, 99, 132, 1)',
                                backgroundColor: 'rgba(255, 99, 132, 0.1)',
                                borderWidth: 2,
                                fill: true,
                                tension: 0.4,
                                pointRadius: 3,
                                pointBackgroundColor: 'rgba(255, 99, 132, 1)',
                                pointHoverRadius: 5
                            },
                            {
                                label: 'Air Humidity (%)',
                                data: humidities,
                                borderColor: 'rgba(54, 162, 235, 1)',
                                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                                borderWidth: 2,
                                fill: true,
                                tension: 0.4,
                                pointRadius: 3,
                                pointBackgroundColor: 'rgba(54, 162, 235, 1)',
                                pointHoverRadius: 5
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        plugins: {
                            legend: {
                                position: 'top',
                                labels: {
                                    usePointStyle: true,
                                    padding: 20,
                                    font: {
                                        family: "'Inter', sans-serif",
                                        size: 12
                                    }
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                padding: 12,
                                titleFont: {
                                    family: "'Inter', sans-serif",
                                    size: 14
                                },
                                bodyFont: {
                                    family: "'Inter', sans-serif",
                                    size: 13
                                },
                                cornerRadius: 8
                            }
                        },
                        scales: {
                            x: {
                                grid: {
                                    display: false
                                },
                                ticks: {
                                    font: {
                                        family: "'Inter', sans-serif",
                                        size: 11
                                    },
                                    maxRotation: 45,
                                    minRotation: 0
                                }
                            },
                            y: {
                                beginAtZero: false,
                                grid: {
                                    color: 'rgba(0, 0, 0, 0.05)'
                                },
                                ticks: {
                                    font: {
                                        family: "'Inter', sans-serif",
                                        size: 11
                                    }
                                }
                            }
                        }
                    }
                });
        }

        /**
         * Setup Analytics Chart timeframe buttons
         */
        function setupChartButtons() {
            const btn24h = document.getElementById('btn-24h');
            const btn7d = document.getElementById('btn-7d');
            const btn30d = document.getElementById('btn-30d');
            const btns = [btn24h, btn7d, btn30d];

            btns.forEach(btn => {
                if (!btn) return;
                btn.addEventListener('click', (e) => {
                    btns.forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    
                    if (e.target.id === 'btn-24h') currentChartTimeframe = '24h';
                    if (e.target.id === 'btn-7d') currentChartTimeframe = '7d';
                    if (e.target.id === 'btn-30d') currentChartTimeframe = '30d';
                    
                    renderChartBasedOnTimeframe();
                });
            });
        }

        /**
         * Initialize the dashboard
         */
        function init() {
            // Initial fetch
            fetchCurrentStatus();

            // Load history chart
            loadHistoryChart();
            
            // Set up timeframe buttons
            setupChartButtons();

            // Set up periodic refresh
            setInterval(fetchCurrentStatus, REFRESH_INTERVAL);

            console.log('Smart Greenhouse Dashboard initialized');
            console.log(`API endpoint: ${API_BASE_URL}/api/current-status`);
            console.log(`Refresh interval: ${REFRESH_INTERVAL}ms`);
        }

        // Start the dashboard when DOM is loaded
        document.addEventListener('DOMContentLoaded', init);
    