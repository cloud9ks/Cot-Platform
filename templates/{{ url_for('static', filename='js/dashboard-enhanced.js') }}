// dashboard-enhanced.js - VERSIONE OTTIMIZZATA CON FIX
// Salva questo file in: static/js/dashboard-enhanced.js

class COTDashboard {
    constructor() {
        this.currentSymbol = 'GOLD';
        this.charts = {};
        this.updateInterval = null;
        this.cache = new Map();
        this.cacheTimeout = 60000; // 1 minuto
        this.isLoading = false;
        this.debounceTimer = null;
        this.debounceDelay = 300;
        
        // Flag per controllo inizializzazione
        this.initialized = false;
        
        this.init();
    }
    
    async init() {
        console.log('🚀 Inizializzazione COT Dashboard...');
        
        try {
            // Setup event listeners
            this.setupEventListeners();
            
            // Inizializza grafici Chart.js
            await this.initializeCharts();
            
            // Carica dati iniziali
            await this.loadInitialData();
            
            // Auto-refresh ogni 30 secondi (non 5!)
            this.startAutoRefresh(30000);
            
            this.initialized = true;
            console.log('✅ Dashboard inizializzata con successo');
            
        } catch (error) {
            console.error('❌ Errore inizializzazione dashboard:', error);
            this.showError('Errore inizializzazione dashboard. Ricarica la pagina.');
        }
    }
    
    setupEventListeners() {
        // Symbol selector con delegated events
        document.addEventListener('click', (e) => {
            if (e.target.matches('.symbol-btn') || e.target.closest('.symbol-btn')) {
                e.preventDefault();
                const btn = e.target.closest('.symbol-btn');
                if (btn && btn.dataset.symbol) {
                    this.switchSymbol(btn.dataset.symbol);
                }
            }
        });
        
        // Tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchTab(tab.dataset.tab);
            });
        });
        
        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.forceRefresh();
            });
        }
    }
    
    async loadInitialData() {
        if (this.isLoading) {
            console.log('⏳ Caricamento già in corso, skip...');
            return;
        }
        
        this.isLoading = true;
        this.showLoader();
        
        try {
            // Carica dati in parallelo con gestione errori individuali
            const [completeData, cotData, economicData] = await Promise.allSettled([
                this.fetchWithCache(`/api/analysis/complete/${this.currentSymbol}`),
                this.fetchWithCache(`/api/data/${this.currentSymbol}?days=90`),
                this.fetchWithCache('/api/economic/current')
            ]);
            
            // Processa analisi completa
            if (completeData.status === 'fulfilled' && completeData.value) {
                this.updateDashboard(completeData.value);
                
                // Aggiorna grafici se ci sono dati tecnici
                if (completeData.value.technical_analysis) {
                    this.updateTechnicalCharts(completeData.value.technical_analysis);
                }
            }
            
            // Processa dati COT
            if (cotData.status === 'fulfilled' && cotData.value) {
                this.updateCOTChart(cotData.value);
            }
            
            // Processa dati economici
            if (economicData.status === 'fulfilled' && economicData.value) {
                this.updateEconomicIndicators(economicData.value);
            }
            
        } catch (error) {
            console.error('❌ Errore caricamento dati:', error);
            this.showError('Errore nel caricamento dei dati');
        } finally {
            this.isLoading = false;
            this.hideLoader();
        }
    }
    
    async fetchWithCache(url) {
        const cacheKey = url;
        const cached = this.cache.get(cacheKey);
        
        // Check cache
        if (cached && (Date.now() - cached.timestamp < this.cacheTimeout)) {
            console.log(`✅ Cache hit: ${url}`);
            return cached.data;
        }
        
        // Fetch con timeout e gestione errori
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout
        
        try {
            const response = await fetch(url, {
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            // Salva in cache solo se dati validi
            if (data && !data.error) {
                this.cache.set(cacheKey, {
                    data: data,
                    timestamp: Date.now()
                });
            }
            
            return data;
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.error(`⏱️ Timeout per ${url}`);
            } else {
                console.error(`❌ Errore fetch ${url}:`, error);
            }
            
            // Ritorna dati cached anche se vecchi
            if (cached) {
                console.log(`⚠️ Usando cache stale per ${url}`);
                return cached.data;
            }
            
            throw error;
        }
    }
    
    updateDashboard(data) {
        if (!data) return;
        
        console.log('📊 Aggiornamento dashboard con:', data);
        
        // Aggiorna COT data
        if (data.cot_data || data.latest_cot) {
            const cotData = data.cot_data || data.latest_cot;
            this.updateElement('net-position', this.formatNumber(cotData.net_position));
            this.updateElement('sentiment-score', `${cotData.sentiment_score?.toFixed(1)}%`);
            
            // Aggiorna sentiment bar
            this.updateSentimentBar(cotData.sentiment_score);
        }
        
        // Aggiorna technical data
        if (data.technical_analysis?.support_resistance) {
            const tech = data.technical_analysis.support_resistance;
            this.updateElement('current-price', this.formatPrice(tech.current_price));
            this.updateElement('support-level', this.formatPrice(tech.strong_support));
            this.updateElement('resistance-level', this.formatPrice(tech.strong_resistance));
            
            // Indicatori
            if (tech.indicators) {
                this.updateElement('rsi-value', tech.indicators.rsi14?.toFixed(1) || 'N/A');
                this.updateElement('macd-value', tech.indicators.macd?.toFixed(2) || 'N/A');
            }
        }
        
        // Aggiorna ML prediction
        if (data.ml_prediction) {
            this.updateElement('prediction-direction', data.ml_prediction.direction);
            this.updateElement('prediction-confidence', `${data.ml_prediction.confidence?.toFixed(0)}%`);
            
            // Colora in base alla direzione
            const dirElement = document.getElementById('prediction-direction');
            if (dirElement) {
                dirElement.className = `prediction-${data.ml_prediction.direction.toLowerCase()}`;
            }
        }
        
        // Aggiorna GPT analysis
        if (data.gpt_analysis) {
            this.updateGPTAnalysis(data.gpt_analysis);
        }
    }
    
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value || 'N/A';
        }
    }
    
    formatNumber(num) {
        if (!num && num !== 0) return 'N/A';
        return new Intl.NumberFormat('it-IT').format(num);
    }
    
    formatPrice(price) {
        if (!price && price !== 0) return 'N/A';
        
        // Formatta in base al valore
        if (price > 1000) {
            return price.toFixed(2);
        } else if (price > 10) {
            return price.toFixed(3);
        } else {
            return price.toFixed(4);
        }
    }
    
    updateSentimentBar(sentiment) {
        const bar = document.querySelector('.sentiment-bar-fill');
        if (bar && sentiment !== undefined) {
            // Converti sentiment da -100/+100 a 0-100%
            const percentage = ((sentiment + 100) / 2);
            bar.style.width = `${percentage}%`;
            
            // Colora in base al valore
            bar.className = 'sentiment-bar-fill';
            if (sentiment > 30) {
                bar.classList.add('bullish');
            } else if (sentiment < -30) {
                bar.classList.add('bearish');
            } else {
                bar.classList.add('neutral');
            }
        }
    }
    
    updateGPTAnalysis(analysis) {
        const container = document.getElementById('gpt-analysis-content');
        if (!container) return;
        
        if (typeof analysis === 'string') {
            container.innerHTML = `<p>${analysis}</p>`;
        } else if (analysis) {
            let html = '';
            if (analysis.summary) {
                html += `<div class="gpt-summary">${analysis.summary}</div>`;
            }
            if (analysis.direction) {
                html += `<div class="gpt-direction">Direzione: <strong>${analysis.direction}</strong></div>`;
            }
            if (analysis.confidence) {
                html += `<div class="gpt-confidence">Confidenza: ${analysis.confidence}%</div>`;
            }
            container.innerHTML = html;
        }
    }
    
    async initializeCharts() {
        // Verifica che Chart.js sia caricato
        if (typeof Chart === 'undefined') {
            console.error('❌ Chart.js non trovato!');
            return;
        }
        
        // Distruggi grafici esistenti
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};
        
        // Inizializza COT Chart
        const cotCanvas = document.getElementById('cot-positions-chart');
        if (cotCanvas) {
            const ctx = cotCanvas.getContext('2d');
            this.charts.cot = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Net Position',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: true },
                        tooltip: { enabled: true }
                    },
                    scales: {
                        y: {
                            beginAtZero: false
                        }
                    }
                }
            });
        }
        
        // Inizializza Price Chart con supporti/resistenze
        const priceCanvas = document.getElementById('price-levels-chart');
        if (priceCanvas) {
            const ctx = priceCanvas.getContext('2d');
            this.charts.price = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Prezzo',
                        data: [],
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        annotation: {
                            annotations: {}
                        }
                    }
                }
            });
        }
        
        console.log('✅ Grafici inizializzati');
    }
    
    updateCOTChart(data) {
        if (!this.charts.cot || !data) return;
        
        // Trasforma dati per il grafico
        const labels = [];
        const netPositions = [];
        const sentiments = [];
        
        // Ordina per data
        const sortedData = Array.isArray(data) ? 
            data.sort((a, b) => new Date(a.date) - new Date(b.date)) : [];
        
        sortedData.forEach(item => {
            labels.push(new Date(item.date).toLocaleDateString('it-IT'));
            netPositions.push(item.net_position);
            sentiments.push(item.sentiment_score);
        });
        
        // Aggiorna grafico
        this.charts.cot.data.labels = labels;
        this.charts.cot.data.datasets[0].data = netPositions;
        
        // Aggiungi dataset sentiment se non esiste
        if (this.charts.cot.data.datasets.length === 1) {
            this.charts.cot.data.datasets.push({
                label: 'Sentiment',
                data: sentiments,
                borderColor: 'rgb(255, 99, 132)',
                backgroundColor: 'rgba(255, 99, 132, 0.1)',
                tension: 0.1,
                yAxisID: 'y1'
            });
            
            // Aggiungi secondo asse Y
            this.charts.cot.options.scales.y1 = {
                type: 'linear',
                display: true,
                position: 'right',
                grid: {
                    drawOnChartArea: false
                }
            };
        } else {
            this.charts.cot.data.datasets[1].data = sentiments;
        }
        
        this.charts.cot.update('none');
        console.log('✅ COT chart aggiornato');
    }
    
    updateTechnicalCharts(techData) {
        if (!techData || !this.charts.price) return;
        
        // Aggiorna livelli di prezzo
        if (techData.support_resistance) {
            const sr = techData.support_resistance;
            
            // Aggiungi prezzo corrente al grafico
            const now = new Date().toLocaleTimeString('it-IT');
            
            if (!this.charts.price.data.labels.includes(now)) {
                // Mantieni solo ultimi 50 punti
                if (this.charts.price.data.labels.length > 50) {
                    this.charts.price.data.labels.shift();
                    this.charts.price.data.datasets[0].data.shift();
                }
                
                this.charts.price.data.labels.push(now);
                this.charts.price.data.datasets[0].data.push(sr.current_price);
            }
            
            // Aggiorna annotazioni per supporto/resistenza
            if (this.charts.price.options.plugins.annotation) {
                this.charts.price.options.plugins.annotation.annotations = {
                    support: {
                        type: 'line',
                        yMin: sr.strong_support,
                        yMax: sr.strong_support,
                        borderColor: 'rgba(0, 255, 0, 0.5)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        label: {
                            content: `Support: ${this.formatPrice(sr.strong_support)}`,
                            enabled: true,
                            position: 'start'
                        }
                    },
                    resistance: {
                        type: 'line',
                        yMin: sr.strong_resistance,
                        yMax: sr.strong_resistance,
                        borderColor: 'rgba(255, 0, 0, 0.5)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        label: {
                            content: `Resistance: ${this.formatPrice(sr.strong_resistance)}`,
                            enabled: true,
                            position: 'start'
                        }
                    }
                };
            }
            
            this.charts.price.update('none');
        }
    }
    
    updateEconomicIndicators(data) {
        if (!data) return;
        
        const container = document.getElementById('economic-indicators');
        if (!container) return;
        
        let html = '<h4>Indicatori Economici</h4>';
        
        if (data.key_indicators) {
            for (const [key, value] of Object.entries(data.key_indicators)) {
                const trend = value.trend === 'DECLINING' ? '📉' : 
                             value.trend === 'RISING' ? '📈' : '➡️';
                
                html += `
                    <div class="indicator-item">
                        <span>${key.replace(/_/g, ' ')}</span>
                        <span>${value.value} ${trend}</span>
                    </div>
                `;
            }
        }
        
        container.innerHTML = html;
    }
    
    async switchSymbol(symbol) {
        if (symbol === this.currentSymbol || this.isLoading) return;
        
        // Debounce
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(async () => {
            console.log(`🔄 Cambio simbolo: ${this.currentSymbol} -> ${symbol}`);
            this.currentSymbol = symbol;
            
            // Aggiorna UI
            document.querySelectorAll('.symbol-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.symbol === symbol);
            });
            
            // Ricarica dati
            await this.loadInitialData();
            
        }, this.debounceDelay);
    }
    
    switchTab(tabName) {
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.style.display = 'none';
        });
        
        const selectedTab = document.getElementById(`${tabName}-tab`);
        if (selectedTab) {
            selectedTab.style.display = 'block';
        }
        
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
    }
    
    async forceRefresh() {
        console.log('🔄 Force refresh...');
        this.cache.clear();
        await this.loadInitialData();
    }
    
    startAutoRefresh(interval = 30000) {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        this.updateInterval = setInterval(() => {
            if (!this.isLoading) {
                console.log('🔄 Auto-refresh...');
                this.loadInitialData();
            }
        }, interval);
        
        console.log(`⏰ Auto-refresh attivo ogni ${interval/1000}s`);
    }
    
    stopAutoRefresh() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    showLoader() {
        const loader = document.getElementById('main-loader');
        if (loader) loader.style.display = 'flex';
        
        // Aggiungi classe loading ai containers
        document.querySelectorAll('.data-container').forEach(el => {
            el.classList.add('loading');
        });
    }
    
    hideLoader() {
        const loader = document.getElementById('main-loader');
        if (loader) loader.style.display = 'none';
        
        // Rimuovi classe loading
        document.querySelectorAll('.data-container').forEach(el => {
            el.classList.remove('loading');
        });
    }
    
    showError(message) {
        const errorContainer = document.getElementById('error-message');
        if (errorContainer) {
            errorContainer.textContent = message;
            errorContainer.style.display = 'block';
            
            setTimeout(() => {
                errorContainer.style.display = 'none';
            }, 5000);
        }
        console.error('❌', message);
    }
    
    destroy() {
        this.stopAutoRefresh();
        
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        
        this.cache.clear();
        console.log('🔚 Dashboard distrutta');
    }
}

// Inizializza quando DOM è pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOM Ready - Inizializzazione COT Dashboard');
        window.cotDashboard = new COTDashboard();
    });
} else {
    // DOM già caricato
    console.log('Inizializzazione immediata COT Dashboard');
    window.cotDashboard = new COTDashboard();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.cotDashboard) {
        window.cotDashboard.destroy();
    }
});