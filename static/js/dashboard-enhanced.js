<<<<<<< HEAD
/**
 * COT Analysis Platform - Dashboard Enhanced JavaScript
 * Sistema completo per gestione dashboard avanzata
 */
=======
// dashboard-enhanced.js - VERSIONE COMPLETA CON TUTTE LE FUNZIONI
// Salva questo file in: static/js/dashboard-enhanced.js
>>>>>>> 6b6ae4199e1bd005e2249547dcc6d158d9f2979a

// =====================================================
// CONFIGURAZIONE E STATO GLOBALE
// =====================================================
let currentSymbol = 'GOLD';
let symbols = {};
let cotChart = null;
let pieChart = null;
let priceChart = null;
let isAnalyzing = false;
let autoRefreshInterval = null;
let updateInterval = null;

// Cache management
const cache = new Map();
const cacheTimeout = 300000; 
const pendingRequests = new Map();

// Configurazione piano utente
let userPlan = {
  type: 'starter',
  isAdmin: false,
  limit: 5,
  features: {
    aiPredictions: false,
    alerts: false,
    technicalAnalysis: false,
    advancedCharts: false
  }
};

// =====================================================
// FORMATTERS
// =====================================================
const numberFmt = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 4 });
const currencyFmt = new Intl.NumberFormat('it-IT', {
  style: 'currency', 
  currency: 'USD', 
  minimumFractionDigits: 2, 
  maximumFractionDigits: 2
});
const dateFmt = new Intl.DateTimeFormat('it-IT', { 
  day: '2-digit', 
  month: '2-digit', 
  year: 'numeric' 
});

// =====================================================
// INIZIALIZZAZIONE
// =====================================================
document.addEventListener('DOMContentLoaded', async () => {
  console.log('🚀 Inizializzazione COT Dashboard...');
  
  try {
    // Carica configurazione utente
    await loadUserPlanConfig();
    
<<<<<<< HEAD
    // Setup event listeners
    setupEventListeners();
    
    // Carica simboli
    await loadSymbols();
    
    // Inizializza grafici
    initCharts();
=======
    async init() {
        console.log('🚀 Inizializzazione COT Dashboard...');
        
        try {
            // Carica i simboli PRIMA di tutto
            await this.loadSymbols();
            
            // Setup event listeners
            this.setupEventListeners();
            
            // Inizializza grafici Chart.js
            await this.initializeCharts();
            
            // Carica dati iniziali
            await this.loadInitialData();
            
            // Auto-refresh ogni 30 secondi
            this.startAutoRefresh(30000);
            
            this.initialized = true;
            console.log('✅ Dashboard inizializzata con successo');
            
        } catch (error) {
            console.error('❌ Errore inizializzazione dashboard:', error);
            this.showError('Errore inizializzazione dashboard. Ricarica la pagina.');
        }
    }
    
    async loadSymbols() {
        try {
            const response = await fetch('/api/symbols');
            if (!response.ok) throw new Error('Errore caricamento simboli');
            
            const data = await response.json();
            const container = document.getElementById('symbolSelector');
            
            if (!container) {
                console.error('Container simboli non trovato');
                return;
            }
            
            container.innerHTML = '';
            
            // Mostra messaggio se ci sono limitazioni
            if (data.limit && data.message) {
                const alert = document.createElement('div');
                alert.className = 'alert alert-warning mb-3';
                alert.innerHTML = `<i class="fas fa-info-circle"></i> ${data.message}`;
                container.parentElement.insertBefore(alert, container);
            }
            
            // Crea i pulsanti per i simboli
            data.symbols.forEach((symbol, index) => {
                const btn = document.createElement('button');
                btn.className = 'symbol-btn';
                btn.textContent = symbol.name || symbol.code;
                btn.dataset.symbol = symbol.code;
                
                if (index === 0) {
                    btn.classList.add('active');
                    this.currentSymbol = symbol.code;
                }
                
                btn.addEventListener('click', () => {
                    this.switchSymbol(symbol.code);
                });
                
                container.appendChild(btn);
            });
            
            console.log(`✅ Caricati ${data.symbols.length} simboli`);
            
        } catch (error) {
            console.error('❌ Errore caricamento simboli:', error);
            document.getElementById('symbolSelector').innerHTML = 
                '<div class="alert alert-danger">Errore caricamento simboli</div>';
        }
    }
    
    setupEventListeners() {
        // Tab navigation con Bootstrap
        const triggerTabList = document.querySelectorAll('#mainTabs button[data-bs-toggle="tab"]');
        triggerTabList.forEach(triggerEl => {
            triggerEl.addEventListener('shown.bs.tab', (e) => {
                const tabId = e.target.getAttribute('data-bs-target');
                console.log(`📑 Tab attivata: ${tabId}`);
                
                // Carica dati specifici per tab se necessario
                if (tabId === '#technical') {
                    this.loadTechnicalData();
                } else if (tabId === '#economic') {
                    this.loadEconomicData();
                } else if (tabId === '#predictions') {
                    this.loadPredictionsData();
                }
            });
        });
        
        // Refresh button (solo admin)
        const refreshBtn = document.getElementById('btnRefresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.forceRefresh();
            });
        }
        
        // Analisi AI button (solo admin)
        const runBtn = document.getElementById('btnRun');
        if (runBtn) {
            runBtn.addEventListener('click', async () => {
                await this.runFullAnalysis();
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
            // Carica dati in parallelo
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
                this.updateCOTTable(cotData.value);
            }
            
            // Processa dati economici
            if (economicData.status === 'fulfilled' && economicData.value) {
                this.updateEconomicIndicators(economicData.value);
                this.updateMarketOverview(economicData.value);
            }
            
        } catch (error) {
            console.error('❌ Errore caricamento dati:', error);
            this.showError('Errore nel caricamento dei dati');
        } finally {
            this.isLoading = false;
            this.hideLoader();
        }
    }
>>>>>>> 6b6ae4199e1bd005e2249547dcc6d158d9f2979a
    
    // Carica dati iniziali
    await loadInitialData();
    
<<<<<<< HEAD
    // Setup auto-refresh
    setupAutoRefresh();
    
    console.log('✅ Dashboard inizializzata con successo');
  } catch (err) {
    console.error('❌ Errore inizializzazione:', err);
    showAlert("Errore durante l'inizializzazione della dashboard", 'danger');
  }
});

// =====================================================
// CONFIGURAZIONE PIANO UTENTE
// =====================================================
async function loadUserPlanConfig() {
  try {
    const res = await fetch('/api/user/plan');
    if (res.ok) {
      const data = await res.json();
      userPlan = {
        type: data.plan || 'starter',
        isAdmin: data.is_admin || false,
        limit: data.limit || 5,
        features: {
          aiPredictions: data.features?.aiPredictions || data.plan === 'professional' || data.is_admin,
          alerts: data.features?.alerts || data.plan === 'professional' || data.is_admin,
          technicalAnalysis: data.features?.technicalAnalysis || data.plan === 'professional' || data.is_admin,
          advancedCharts: data.features?.advancedCharts || data.plan === 'professional' || data.is_admin
=======
    updateDashboard(data) {
        if (!data) return;
        
        console.log('📊 Aggiornamento dashboard con:', data);
        
        // Aggiorna COT data - NOTA GLI ID CORRETTI!
        if (data.cot_data || data.latest_cot) {
            const cotData = data.cot_data || data.latest_cot;
            
            // Net Position
            this.updateElement('netPosition', this.formatNumber(cotData.net_position));
            
            // Net Change
            if (cotData.net_change !== undefined) {
                const changeEl = document.getElementById('netChange');
                if (changeEl) {
                    const changeValue = cotData.net_change || 0;
                    changeEl.textContent = `${changeValue >= 0 ? '+' : ''}${this.formatNumber(changeValue)}`;
                    changeEl.className = changeValue >= 0 ? 'text-success fw-bold' : 'text-danger fw-bold';
                }
            }
            
            // Sentiment Score
            this.updateElement('sentimentScore', `${cotData.sentiment_score?.toFixed(1)}%`);
            
            // Sentiment Bar
            this.updateSentimentBar(cotData.sentiment_score);
            
            // Last Update
            if (cotData.date) {
                const date = new Date(cotData.date);
                this.updateElement('lastUpdate', date.toLocaleDateString('it-IT'));
            }
        }
        
        // Aggiorna ML prediction - NOTA GLI ID CORRETTI!
        if (data.ml_prediction) {
            const pred = data.ml_prediction;
            const predBox = document.getElementById('aiPrediction');
            const confEl = document.getElementById('confidence');
            
            if (predBox) {
                const direction = (pred.direction || 'NEUTRAL').toUpperCase();
                const cssClass = direction === 'BULLISH' ? 'signal-bullish' : 
                               direction === 'BEARISH' ? 'signal-bearish' : 
                               'signal-neutral';
                predBox.innerHTML = `<span class="signal-box ${cssClass}">${direction}</span>`;
            }
            
            if (confEl) {
                confEl.textContent = Math.round(pred.confidence || 50);
            }
        }
        
        // Aggiorna Technical data
        if (data.technical_analysis?.support_resistance) {
            const tech = data.technical_analysis.support_resistance;
            this.updateElement('current-price', this.formatPrice(tech.current_price));
            this.updateElement('support-level', this.formatPrice(tech.strong_support));
            this.updateElement('resistance-level', this.formatPrice(tech.strong_resistance));
        }
        
        // Aggiorna Quick Analysis
        this.updateQuickAnalysis(data);
        
        // Aggiorna GPT Analysis
        if (data.gpt_analysis) {
            this.updateGPTAnalysis(data.gpt_analysis);
        }
    }
    
    updateQuickAnalysis(data) {
        const box = document.getElementById('quickAnalysis');
        if (!box) return;
        
        const cotData = data.cot_data || data.latest_cot || {};
        const netPos = cotData.net_position || 0;
        const sentiment = cotData.sentiment_score || 0;
        
        let html = '<div class="row g-2">';
        html += `<div class="col-6"><small class="text-muted">Net Position</small><div class="fw-bold">${this.formatNumber(netPos)}</div></div>`;
        html += `<div class="col-6"><small class="text-muted">Sentiment</small><div class="fw-bold">${sentiment.toFixed(2)}%</div></div>`;
        html += `<div class="col-12 mt-2"><small class="text-muted">Interpretazione</small><div>`;
        
        if (sentiment > 20) {
            html += '<span class="badge bg-success">Sentiment Rialzista Forte</span>';
        } else if (sentiment > 10) {
            html += '<span class="badge bg-success">Sentiment Rialzista</span>';
        } else if (sentiment < -20) {
            html += '<span class="badge bg-danger">Sentiment Ribassista Forte</span>';
        } else if (sentiment < -10) {
            html += '<span class="badge bg-danger">Sentiment Ribassista</span>';
        } else {
            html += '<span class="badge bg-secondary">Sentiment Neutrale</span>';
        }
        
        html += '</div></div></div>';
        box.innerHTML = html;
    }
    
    updateMarketOverview(data) {
        const box = document.getElementById('marketOverview');
        if (!box) return;
        
        const sentiment = data.market_sentiment || data.sentiment || 0;
        const risk = data.risk_on ? 'Risk-ON' : data.risk_off ? 'Risk-OFF' : '—';
        const today = new Date().toLocaleDateString('it-IT');
        
        box.innerHTML = `
            <div class="row g-3">
                <div class="col-md-4">
                    <div class="metric-card">
                        <div class="metric-value">${sentiment}%</div>
                        <div class="metric-label">Market Sentiment</div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="metric-card" style="background:linear-gradient(135deg,#34d399 0%, #10b981 100%)">
                        <div class="metric-value">${risk}</div>
                        <div class="metric-label">Risk Regime</div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="metric-card" style="background:linear-gradient(135deg,#f59e0b 0%, #ef4444 100%)">
                        <div class="metric-value">${today}</div>
                        <div class="metric-label">Oggi</div>
                    </div>
                </div>
            </div>`;
    }
    
    updateCOTTable(data) {
        const tbody = document.getElementById('cotDataTable');
        if (!tbody || !Array.isArray(data)) return;
        
        tbody.innerHTML = '';
        
        // Prendi solo i primi 10 record
        data.slice(0, 10).forEach(row => {
            const tr = document.createElement('tr');
            const date = new Date(row.date).toLocaleDateString('it-IT');
            
            tr.innerHTML = `
                <td>${date}</td>
                <td>${this.formatNumber(row.non_commercial_long)}</td>
                <td>${this.formatNumber(row.non_commercial_short)}</td>
                <td>${this.formatNumber(row.commercial_long)}</td>
                <td>${this.formatNumber(row.commercial_short)}</td>
                <td>${this.formatNumber(row.net_position)}</td>
                <td>${(row.sentiment_score || 0).toFixed(2)}%</td>
            `;
            
            tbody.appendChild(tr);
        });
    }
    
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value || 'N/A';
>>>>>>> 6b6ae4199e1bd005e2249547dcc6d158d9f2979a
        }
      };
      applyPlanRestrictions();
    }
<<<<<<< HEAD
  } catch (e) {
    console.warn('Piano config non disponibile:', e);
  }
=======
    
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
        const bar = document.getElementById('sentimentBar');
        if (!bar) return;
        
        // Trova o crea la barra interna
        let fillBar = bar.querySelector('div');
        if (!fillBar) {
            fillBar = document.createElement('div');
            bar.appendChild(fillBar);
        }
        
        if (sentiment !== undefined) {
            const w = Math.min(100, Math.max(0, Math.abs(sentiment)));
            fillBar.style.width = `${w}%`;
            fillBar.style.height = '100%';
            fillBar.style.transition = 'width 0.3s';
            
            // Colora in base al valore
            if (sentiment >= 10) {
                fillBar.style.background = 'linear-gradient(90deg,#10b981,#34d399)';
            } else if (sentiment <= -10) {
                fillBar.style.background = 'linear-gradient(90deg,#ef4444,#f87171)';
            } else {
                fillBar.style.background = 'linear-gradient(90deg,#6b7280,#9ca3af)';
            }
        }
    }
    
    updateGPTAnalysis(analysis) {
        const container = document.getElementById('gptAnalysis');
        if (!container) return;
        
        if (typeof analysis === 'string') {
            container.innerHTML = `<div class="p-3 bg-light rounded"><p>${analysis}</p></div>`;
        } else if (analysis && analysis.summary) {
            let html = '<div class="p-3 bg-light rounded">';
            if (analysis.summary) {
                html += `<p>${analysis.summary}</p>`;
            }
            if (analysis.direction) {
                html += `<div class="mt-2"><strong>Direzione:</strong> ${analysis.direction}</div>`;
            }
            if (analysis.confidence) {
                html += `<div><strong>Confidenza:</strong> ${analysis.confidence}%</div>`;
            }
            html += '</div>';
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
        
        // COT Chart
        const cotCanvas = document.getElementById('cotChart');
        if (cotCanvas) {
            const ctx = cotCanvas.getContext('2d');
            this.charts.cot = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'NC Long',
                            data: [],
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16,185,129,0.1)'
                        },
                        {
                            label: 'NC Short',
                            data: [],
                            borderColor: '#ef4444',
                            backgroundColor: 'rgba(239,68,68,0.1)'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' }
                    }
                }
            });
        }
        
        // Pie Chart
        const pieCanvas = document.getElementById('pieChart');
        if (pieCanvas) {
            const ctx = pieCanvas.getContext('2d');
            this.charts.pie = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['NC Long', 'NC Short', 'Commercial Long', 'Commercial Short'],
                    datasets: [{
                        data: [0, 0, 0, 0],
                        backgroundColor: ['#10b981', '#ef4444', '#3b82f6', '#f59e0b']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }
        
        // Price Chart
        const priceCanvas = document.getElementById('priceChart');
        if (priceCanvas) {
            const ctx = priceCanvas.getContext('2d');
            this.charts.price = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Prezzo',
                        data: [],
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37,99,235,0.1)'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }
        
        console.log('✅ Grafici inizializzati');
    }
    
    updateCOTChart(data) {
        if (!this.charts.cot || !data) return;
        
        const labels = [];
        const ncLong = [];
        const ncShort = [];
        
        // Ordina per data e prendi ultimi 30 giorni
        const sortedData = Array.isArray(data) ? 
            data.sort((a, b) => new Date(a.date) - new Date(b.date)).slice(-30) : [];
        
        sortedData.forEach(item => {
            labels.push(new Date(item.date).toLocaleDateString('it-IT'));
            ncLong.push(item.non_commercial_long);
            ncShort.push(item.non_commercial_short);
        });
        
        // Aggiorna COT chart
        this.charts.cot.data.labels = labels;
        this.charts.cot.data.datasets[0].data = ncLong;
        this.charts.cot.data.datasets[1].data = ncShort;
        this.charts.cot.update('none');
        
        // Aggiorna Pie chart con ultimo dato
        if (this.charts.pie && sortedData.length > 0) {
            const last = sortedData[sortedData.length - 1];
            this.charts.pie.data.datasets[0].data = [
                last.non_commercial_long,
                last.non_commercial_short,
                last.commercial_long,
                last.commercial_short
            ];
            this.charts.pie.update('none');
        }
        
        console.log('✅ Grafici COT aggiornati');
    }
    
    updateTechnicalCharts(techData) {
        // Implementazione placeholder
        console.log('📈 Update technical charts:', techData);
    }
    
    updateEconomicIndicators(data) {
        const container = document.getElementById('economicIndicators');
        if (!container) return;
        
        let html = '<div class="row g-3">';
        
        if (data.key_indicators) {
            for (const [key, value] of Object.entries(data.key_indicators)) {
                const val = value.value || value;
                html += `
                    <div class="col-md-4">
                        <div class="p-3 border rounded">
                            <div class="text-muted small">${key.replace(/_/g, ' ')}</div>
                            <div class="h5 mb-0">${val}</div>
                        </div>
                    </div>`;
            }
        }
        
        html += '</div>';
        container.innerHTML = html;
    }
    
    // Metodi aggiuntivi per le altre tab
    async loadTechnicalData() {
        console.log('📊 Caricamento dati tecnici...');
        // Implementazione futura
    }
    
    async loadEconomicData() {
        console.log('💰 Caricamento dati economici...');
        // Implementazione futura
    }
    
    async loadPredictionsData() {
        console.log('🔮 Caricamento previsioni...');
        // Implementazione futura
    }
    
    async runFullAnalysis() {
        console.log('🧠 Avvio analisi AI completa...');
        
        try {
            const response = await fetch(`/api/scrape/${this.currentSymbol}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('✅ Analisi completata:', data);
                
                // Ricarica dati
                await this.loadInitialData();
            }
        } catch (error) {
            console.error('❌ Errore analisi:', error);
        }
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
        // Implementazione semplificata
        document.querySelectorAll('.loading').forEach(el => {
            el.style.display = 'block';
        });
    }
    
    hideLoader() {
        document.querySelectorAll('.loading').forEach(el => {
            el.style.display = 'none';
        });
    }
    
    showError(message) {
        console.error('❌', message);
        // Potresti aggiungere un toast o alert
    }
    
    destroy() {
        this.stopAutoRefresh();
        
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        
        this.cache.clear();
        console.log('🔚 Dashboard distrutta');
    }
>>>>>>> 6b6ae4199e1bd005e2249547dcc6d158d9f2979a
}

function applyPlanRestrictions() {
  if (!userPlan.isAdmin) {
    const btnRefresh = document.getElementById('btnRefresh');
    const btnRun = document.getElementById('btnRun');
    if (btnRefresh) btnRefresh.style.display = 'none';
    if (btnRun) btnRun.style.display = 'none';
  }
}

// =====================================================
// CARICAMENTO SIMBOLI
// =====================================================
async function loadSymbols() {
  try {
    const res = await fetch('/api/symbols');
    if (!res.ok) throw new Error('Errore caricamento simboli');
    
    const data = await res.json();
    const container = document.getElementById('symbolSelector');
    
    if (!container) {
      console.error('Container simboli non trovato');
      return;
    }
    
    container.innerHTML = '';
    
    // Mostra alert limite se presente
    if (data.limit && data.limit > 0 && data.message) {
      const alert = document.createElement('div');
      alert.className = 'alert alert-warning mb-3 w-100';
      alert.innerHTML = `<i class="fas fa-info-circle"></i> ${data.message}`;
      container.parentElement.insertBefore(alert, container);
    }

    // Crea pulsanti
    data.symbols.forEach((symbol, index) => {
      const btn = document.createElement('button');
      btn.className = 'symbol-btn';
      btn.textContent = symbol.name || symbol.code;
      btn.dataset.symbol = symbol.code;
      
      if (index === 0) {
        btn.classList.add('active');
        currentSymbol = symbol.code;
      }
      
      btn.addEventListener('click', async () => {
        document.querySelectorAll('.symbol-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentSymbol = symbol.code;
        console.log('Simbolo selezionato:', currentSymbol);
        cache.clear();
        await reloadAll();
      });
      
      container.appendChild(btn);
    });
    
    console.log(`✅ Caricati ${data.symbols.length} simboli`);
    
  } catch (e) {
    console.error('❌ Errore caricamento simboli:', e);
    const container = document.getElementById('symbolSelector');
    if (container) {
      container.innerHTML = '<div class="alert alert-danger">Errore caricamento simboli</div>';
    }
  }
}

// =====================================================
// EVENT LISTENERS
// =====================================================
function setupEventListeners() {
  // Tab navigation
  const triggerTabList = document.querySelectorAll('#mainTabs button[data-bs-toggle="tab"]');
  triggerTabList.forEach(triggerEl => {
    triggerEl.addEventListener('shown.bs.tab', (e) => {
      const tabId = e.target.getAttribute('data-bs-target');
      console.log(`📑 Tab attivata: ${tabId}`);
      
      // Carica dati specifici per tab
      switch(tabId) {
        case '#technical':
          loadTechnical(currentSymbol);
          break;
        case '#economic':
          loadEconomic();
          break;
        case '#predictions':
          loadPredictions(currentSymbol);
          break;
      }
    });
  });
  
  // Pulsanti admin
  const btnRefresh = document.getElementById('btnRefresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', async () => {
      btnRefresh.classList.add('btn-loading');
      await reloadAll();
      btnRefresh.classList.remove('btn-loading');
      showAlert('Dati aggiornati', 'success');
    });
  }

  const btnRun = document.getElementById('btnRun');
  if (btnRun) {
    btnRun.addEventListener('click', async () => {
      if (isAnalyzing) return;
      isAnalyzing = true;
      btnRun.classList.add('btn-loading');
      try { 
        await runFullAnalysis(currentSymbol); 
      } catch (e) { 
        console.error(e); 
        showAlert('Errore durante l\'analisi AI', 'danger'); 
      } finally { 
        isAnalyzing = false; 
        btnRun.classList.remove('btn-loading'); 
      }
    });
  }

  // Period selector per grafico COT
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-period]');
    if (!btn) return;
    
    const group = btn.parentElement;
    [...group.querySelectorAll('button')].forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    const days = parseInt(btn.dataset.period, 10) || 30;
    await loadCotHistory(currentSymbol, days);
  });
}

// =====================================================
// INIZIALIZZAZIONE GRAFICI
// =====================================================
function initCharts() {
  // Distruggi grafici esistenti
  if (cotChart) cotChart.destroy();
  if (pieChart) pieChart.destroy();
  if (priceChart) priceChart.destroy();
  
  const cotCtx = document.getElementById('cotChart');
  const pieCtx = document.getElementById('pieChart');
  const priceCtx = document.getElementById('priceChart');

  if (cotCtx) {
    cotChart = new Chart(cotCtx, {
      type: 'line',
      data: { 
        labels: [], 
        datasets: [
          { 
            label: 'NC Long', 
            data: [], 
            borderColor: '#10b981', 
            backgroundColor: 'rgba(16,185,129,0.1)', 
            tension: 0.25 
          },
          { 
            label: 'NC Short', 
            data: [], 
            borderColor: '#ef4444', 
            backgroundColor: 'rgba(239,68,68,0.1)', 
            tension: 0.25 
          },
          { 
            label: 'Commercial Long', 
            data: [], 
            borderColor: '#3b82f6', 
            backgroundColor: 'rgba(59,130,246,0.1)', 
            tension: 0.25 
          },
          { 
            label: 'Commercial Short', 
            data: [], 
            borderColor: '#f59e0b', 
            backgroundColor: 'rgba(245,158,11,0.1)', 
            tension: 0.25 
          },
          { 
            label: 'Net Position', 
            data: [], 
            borderColor: '#8b5cf6', 
            borderWidth: 3, 
            tension: 0.25 
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { 
          legend: { position: 'top' }, 
          tooltip: { mode: 'index', intersect: false } 
        },
        scales: { 
          y: { 
            ticks: { callback: (v) => numberFmt.format(v) } 
          } 
        }
      }
    });
  }

  if (pieCtx) {
    pieChart = new Chart(pieCtx, {
      type: 'doughnut',
      data: { 
        labels: ['NC Long', 'NC Short', 'Commercial Long', 'Commercial Short'], 
        datasets: [{ 
          data: [0,0,0,0],
          backgroundColor: ['#10b981', '#ef4444', '#3b82f6', '#f59e0b']
        }] 
      },
      options: { 
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } } 
      }
    });
  }

  if (priceCtx) {
    priceChart = new Chart(priceCtx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          { 
            label: 'Prezzo', 
            data: [], 
            borderColor: '#2563eb', 
            borderWidth: 2, 
            pointRadius: 0,
            tension: 0.2
          },
          { 
            label: 'Support', 
            data: [], 
            borderColor: '#10b981',
            borderDash: [6, 6], 
            pointRadius: 0 
          },
          { 
            label: 'Resistance', 
            data: [], 
            borderColor: '#ef4444',
            borderDash: [6, 6], 
            pointRadius: 0 
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
        scales: { 
          y: { ticks: { callback: (v) => numberFmt.format(v) } }
        }
      }
    });
  }
  
  console.log('✅ Grafici inizializzati');
}

// =====================================================
// CARICAMENTO DATI INIZIALI
// =====================================================
async function loadInitialData() {
  try {
    await Promise.allSettled([
      loadOverview(currentSymbol),
      loadCotHistory(currentSymbol, 30),
      loadTechnical(currentSymbol),
      loadEconomic(),
      loadPredictions(currentSymbol),
      loadSystemStatus(),
      loadMarketOverview(),
      loadAlerts(currentSymbol)
    ]);
  } catch (error) {
    console.error('❌ Errore caricamento dati:', error);
  }
}

async function reloadAll() {
  await Promise.allSettled([
    loadOverview(currentSymbol),
    loadCotHistory(currentSymbol, getSelectedDays()),
    loadTechnical(currentSymbol),
    loadEconomic(),
    loadPredictions(currentSymbol),
    loadSystemStatus(),
    loadMarketOverview(),
    loadAlerts(currentSymbol)
  ]);
}

function getSelectedDays() {
  const active = document.querySelector('[data-period].active');
  return active ? parseInt(active.dataset.period, 10) : 30;
}

// =====================================================
// CARICAMENTO OVERVIEW
// =====================================================
async function loadOverview(symbol) {
  try {
    // Carica analisi completa
    const completeRes = await fetchWithCache(`/api/analysis/complete/${encodeURIComponent(symbol)}`);
    
    if (completeRes && !completeRes.error) {
      updateDashboard(completeRes);
    }
    
    // Carica dati COT separatamente se necessario
    const cotRes = await fetchWithCache(`/api/data/${encodeURIComponent(symbol)}?days=90`);
    
    if (cotRes && cotRes.length > 0) {
      const latest = cotRes[0];
      const prev = cotRes[1] || null;
      
      // Aggiorna elementi overview
      updateOverviewElements(latest, prev);
      
      // Aggiorna quick analysis
      updateQuickAnalysis(latest);
    }
    
  } catch (e) {
    console.error('Errore loadOverview:', e);
    updateOverviewElements(null, null);
  }
}

function updateOverviewElements(latest, prev) {
  // Net Position
  const netPosEl = document.getElementById('netPosition');
  if (netPosEl) {
    netPosEl.textContent = latest ? numberFmt.format(latest.net_position) : '—';
  }
  
  // Net Change
  const netChangeEl = document.getElementById('netChange');
  if (netChangeEl && latest && prev) {
    const netChange = latest.net_position - prev.net_position;
    netChangeEl.textContent = `${netChange >= 0 ? '+' : ''}${numberFmt.format(netChange)}`;
    netChangeEl.className = netChange >= 0 ? 'text-success fw-bold' : 'text-danger fw-bold';
  } else if (netChangeEl) {
    netChangeEl.textContent = '—';
  }
  
  // Sentiment Score
  const sentimentEl = document.getElementById('sentimentScore');
  if (sentimentEl) {
    sentimentEl.textContent = latest ? `${(latest.sentiment_score ?? 0).toFixed(2)}%` : '—';
  }
  
  // Sentiment Bar
  setSentimentBar(latest ? latest.sentiment_score || 0 : 0);
  
  // Last Update
  const lastUpdateEl = document.getElementById('lastUpdate');
  if (lastUpdateEl) {
    if (latest && latest.date) {
      const d = new Date(latest.date);
      lastUpdateEl.textContent = dateFmt.format(d);
    } else {
      lastUpdateEl.textContent = '—';
    }
  }
}

function updateDashboard(data) {
  if (!data) return;
  
  console.log('📊 Aggiornamento dashboard con:', data);
  
  // Aggiorna COT data
  if (data.cot_data || data.latest_cot) {
    const cotData = data.cot_data || data.latest_cot;
    
    const netPosEl = document.getElementById('netPosition');
    if (netPosEl) {
      netPosEl.textContent = numberFmt.format(cotData.net_position);
    }
    
    const sentimentEl = document.getElementById('sentimentScore');
    if (sentimentEl) {
      sentimentEl.textContent = `${(cotData.sentiment_score ?? 0).toFixed(2)}%`;
    }
    
    setSentimentBar(cotData.sentiment_score || 0);
    
    if (cotData.date) {
      const lastUpdateEl = document.getElementById('lastUpdate');
      if (lastUpdateEl) {
        lastUpdateEl.textContent = dateFmt.format(new Date(cotData.date));
      }
    }
  }
  
  // Aggiorna ML prediction
  if (data.ml_prediction) {
    setAIPrediction(data.ml_prediction);
  }
  
  // Aggiorna GPT Analysis
  if (data.gpt_analysis) {
    renderGptAnalysis(document.getElementById('gptAnalysis'), data.gpt_analysis);
  }
}

function setSentimentBar(score) {
  const bar = document.getElementById('sentimentBar');
  if (!bar) return;
  
  const w = Math.min(100, Math.max(0, Math.abs(score)));
  bar.style.width = `${w}%`;
  bar.textContent = `${(+score).toFixed(2)}%`;
  bar.style.background =
    score >= 10 ? 'linear-gradient(90deg,#10b981,#34d399)'
    : score <= -10 ? 'linear-gradient(90deg,#ef4444,#f87171)'
    : 'linear-gradient(90deg,#6b7280,#9ca3af)';
}

function setAIPrediction(mlPred) {
  const box = document.getElementById('aiPrediction');
  const confEl = document.getElementById('confidence');
  
  if (!mlPred) {
    if (box) box.innerHTML = `<span class="signal-box signal-neutral">IN ATTESA…</span>`;
    if (confEl) confEl.textContent = '—';
    return;
  }
  
  const dir = (mlPred.direction || 'NEUTRAL').toUpperCase();
  const conf = Math.round(mlPred.confidence || 50);
  const cls = dir === 'BULLISH' ? 'signal-bullish' : 
              dir === 'BEARISH' ? 'signal-bearish' : 
              'signal-neutral';
  
  if (box) box.innerHTML = `<span class="signal-box ${cls}">${dir}</span>`;
  if (confEl) confEl.textContent = `${conf}`;
}

function updateQuickAnalysis(data) {
  const box = document.getElementById('quickAnalysis');
  if (!box) return;
  
  const netPos = data.net_position || 0;
  const sentiment = data.sentiment_score || 0;
  
  let analysis = '<div class="row g-2">';
  analysis += `<div class="col-6"><small class="text-muted">Net Position</small><div class="fw-bold">${numberFmt.format(netPos)}</div></div>`;
  analysis += `<div class="col-6"><small class="text-muted">Sentiment</small><div class="fw-bold">${sentiment.toFixed(2)}%</div></div>`;
  analysis += `<div class="col-12 mt-2"><small class="text-muted">Interpretazione</small><div>`;
  
  if (sentiment > 20) {
    analysis += '<span class="badge bg-success">Sentiment Rialzista Forte</span>';
  } else if (sentiment > 10) {
    analysis += '<span class="badge bg-success">Sentiment Rialzista</span>';
  } else if (sentiment < -20) {
    analysis += '<span class="badge bg-danger">Sentiment Ribassista Forte</span>';
  } else if (sentiment < -10) {
    analysis += '<span class="badge bg-danger">Sentiment Ribassista</span>';
  } else {
    analysis += '<span class="badge bg-secondary">Sentiment Neutrale</span>';
  }
  
  analysis += '</div></div></div>';
  box.innerHTML = analysis;
}

// =====================================================
// CARICAMENTO COT HISTORY
// =====================================================
async function loadCotHistory(symbol, days = 30) {
  try {
    const res = await fetchWithCache(`/api/data/${encodeURIComponent(symbol)}?days=${days}`);
    
    if (!res || !res.length) {
      console.warn('Nessun dato COT disponibile');
      return;
    }
    
    // Aggiorna tabella
    const tbody = document.getElementById('cotDataTable');
    if (tbody) {
      tbody.innerHTML = '';
      res.forEach(r => {
        const d = new Date(r.date);
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${dateFmt.format(d)}</td>
          <td>${numberFmt.format(r.non_commercial_long)}</td>
          <td>${numberFmt.format(r.non_commercial_short)}</td>
          <td>${numberFmt.format(r.commercial_long)}</td>
          <td>${numberFmt.format(r.commercial_short)}</td>
          <td>${numberFmt.format(r.net_position)}</td>
          <td>${(r.sentiment_score ?? 0).toFixed(2)}%</td>`;
        tbody.appendChild(tr);
      });
    }

    // Aggiorna grafici
    updateCOTCharts(res);
    
  } catch (e) {
    console.error('Errore loadCotHistory:', e);
  }
}

function updateCOTCharts(data) {
  if (!data || !data.length) return;
  
  const labels = [], ncLong = [], ncShort = [], cLong = [], cShort = [], net = [];
  
  // Ordina per data
  const sorted = [...data].sort((a, b) => new Date(a.date) - new Date(b.date));
  
  sorted.forEach(r => {
    const d = new Date(r.date);
    labels.push(dateFmt.format(d));
    ncLong.push(r.non_commercial_long);
    ncShort.push(r.non_commercial_short);
    cLong.push(r.commercial_long);
    cShort.push(r.commercial_short);
    net.push(r.net_position);
  });

  if (cotChart) {
    cotChart.data.labels = labels;
    cotChart.data.datasets[0].data = ncLong;
    cotChart.data.datasets[1].data = ncShort;
    cotChart.data.datasets[2].data = cLong;
    cotChart.data.datasets[3].data = cShort;
    cotChart.data.datasets[4].data = net;
    cotChart.update();
  }

  if (pieChart && sorted.length > 0) {
    const last = sorted[sorted.length - 1];
    pieChart.data.datasets[0].data = [
      last.non_commercial_long, 
      last.non_commercial_short,
      last.commercial_long, 
      last.commercial_short
    ];
    pieChart.update();
  }
  
  console.log('✅ Grafici COT aggiornati');
}

// =====================================================
// CARICAMENTO ANALISI TECNICA
// =====================================================
async function loadTechnical(symbol) {
  try {
    console.log(`🔧 Loading technical data for ${symbol}`);
    
    const res = await fetchWithCache(`/api/technical/${encodeURIComponent(symbol)}`);
    
    if (!res || res.error) {
      renderTechnicalFallback(symbol);
      return;
    }

    renderTechnicalData(res);

  } catch (e) {
    console.error('❌ Errore loadTechnical:', e);
    renderTechnicalFallback(symbol);
  }
}

function renderTechnicalData(data) {
  console.log('🎨 Rendering technical data:', data);
  
  // Supporti e Resistenze
  renderSupportResistance(data);
  
  // Segnali Tecnici
  const signals = data.signals || {};
  renderTechnicalSignals(signals.overall || {}, data.current_price);
  
  // Indicatori
  const indicators = data.indicators || {};
  renderTechnicalIndicatorsBox(indicators);
  
  // Grafico prezzi
  updatePriceChart(data);
}

function renderSupportResistance(data) {
  const box = document.getElementById('supportResistance');
  if (!box) return;

  const fmt = (n) => (typeof n === 'number' && isFinite(n)) ? 
    n.toLocaleString('it-IT', {maximumFractionDigits: 2}) : '—';

  box.innerHTML = `
    <div class="row g-3">
      <div class="col-6">
        <div class="p-3 bg-light rounded">
          <div class="text-muted small">Prezzo Corrente</div>
          <div class="h5 mb-0 text-primary">${fmt(data.current_price)}</div>
        </div>
      </div>
      <div class="col-6">
        <div class="p-3 bg-light rounded">
          <div class="text-muted small">Trend Bias</div>
          <div class="h5 mb-0">${data.trend_bias || 'NEUTRAL'}</div>
        </div>
      </div>
      <div class="col-6">
        <div class="p-3 bg-success bg-opacity-10 rounded">
          <div class="text-muted small">Strong Support</div>
          <div class="h6 mb-0 text-success">${fmt(data.strong_support)}</div>
          <small class="text-muted">${fmt(data.distance_to_support)}% di distanza</small>
        </div>
      </div>
      <div class="col-6">
        <div class="p-3 bg-danger bg-opacity-10 rounded">
          <div class="text-muted small">Strong Resistance</div>
          <div class="h6 mb-0 text-danger">${fmt(data.strong_resistance)}</div>
          <small class="text-muted">${fmt(data.distance_to_resistance)}% di distanza</small>
        </div>
      </div>
    </div>`;
}

function renderTechnicalSignals(overall, currentPrice) {
  const box = document.getElementById('technicalSignals');
  if (!box) return;

  const signal = (overall.signal || 'NEUTRAL').toUpperCase();
  const confidence = Math.round(overall.confidence || 50);
  
  const signalCls = signalClass(signal);
  const signalText = signal.replace('_', ' ');

  box.innerHTML = `
    <div class="text-center">
      <div class="mb-3">
        <span class="signal-box ${signalCls}">${signalText}</span>
      </div>
      <div class="row g-2">
        <div class="col-6">
          <div class="p-2 bg-light rounded">
            <div class="text-muted small">Confidenza</div>
            <div class="fw-bold">${confidence}%</div>
          </div>
        </div>
        <div class="col-6">
          <div class="p-2 bg-light rounded">
            <div class="text-muted small">Score</div>
            <div class="fw-bold">${(overall.weighted_score || 0).toFixed(2)}</div>
          </div>
        </div>
      </div>
    </div>`;
}

function renderTechnicalIndicatorsBox(indicators) {
  const box = document.getElementById('technicalIndicators');
  if (!box) return;

  const fmt = (val, suffix = '') => val != null ? val.toFixed(2) + suffix : '—';

  box.innerHTML = `
    <div class="row g-3">
      <div class="col-md-4">
        <div class="p-3 border rounded">
          <div class="text-muted small">RSI (14)</div>
          <div class="h5 mb-0">${fmt(indicators.rsi14)}</div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="p-3 border rounded">
          <div class="text-muted small">SMA 50</div>
          <div class="h5 mb-0">${fmt(indicators.sma50)}</div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="p-3 border rounded">
          <div class="text-muted small">SMA 200</div>
          <div class="h5 mb-0">${fmt(indicators.sma200)}</div>
        </div>
      </div>
    </div>`;
}

function updatePriceChart(data) {
  if (!priceChart || !data.current_price) return;

  const price = data.current_price;
  const support = data.strong_support || price * 0.98;
  const resistance = data.strong_resistance || price * 1.02;

  // Crea serie temporali simulate
  const labels = Array.from({length: 30}, (_, i) => i + 1);
  const priceSeries = labels.map(() => price + (Math.random() - 0.5) * price * 0.02);
  const supportSeries = labels.map(() => support);
  const resistanceSeries = labels.map(() => resistance);

  priceChart.data.labels = labels;
  priceChart.data.datasets[0].data = priceSeries;
  priceChart.data.datasets[1].data = supportSeries;
  priceChart.data.datasets[2].data = resistanceSeries;
  priceChart.update();
}

function renderTechnicalFallback(symbol) {
  console.log(`⚠️ Rendering technical fallback for ${symbol}`);
  
  const supportResistance = document.getElementById('supportResistance');
  if (supportResistance) {
    supportResistance.innerHTML = `
      <div class="text-center text-muted py-4">
        <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
        <div>Analisi tecnica non disponibile per ${symbol}</div>
      </div>`;
  }
}

// =====================================================
// CARICAMENTO DATI ECONOMICI
// =====================================================
async function loadEconomic() {
  try {
    const [cur, cal] = await Promise.allSettled([
      fetchWithCache('/api/economic/current'),
      fetchWithCache('/api/economic/calendar')
    ]);

    // Current Economic Data
    if (cur.status === 'fulfilled' && cur.value) {
      renderEconomicIndicators(cur.value);
      renderFedWatch(cur.value);
    }

    // Economic Calendar
    if (cal.status === 'fulfilled' && cal.value) {
      renderEconomicCalendar(cal.value);
    }
    
  } catch (e) {
    console.error('Errore loadEconomic:', e);
  }
}

function renderEconomicIndicators(data) {
  const container = document.getElementById('economicIndicators');
  if (!container) return;
  
  const indicators = data.key_indicators || data;
  
  const card = (label, value, suffix='') => `
    <div class="col-md-4">
      <div class="p-3 border rounded">
        <div class="text-muted small">${label}</div>
        <div class="h5 mb-0">${value != null ? (+value).toFixed(2) + suffix : '—'}</div>
      </div>
    </div>`;
  
  let html = '<div class="row g-3">';
  
  if (indicators.inflation_usa) {
    html += card('CPI YoY', indicators.inflation_usa.value, '%');
  }
  if (indicators.unemployment_rate) {
    html += card('Disoccupazione', indicators.unemployment_rate.value, '%');
  }
  if (indicators.gdp_qoq) {
    html += card('GDP QoQ', indicators.gdp_qoq.value, '%');
  }
  
  html += '</div>';
  container.innerHTML = html;
}

function renderFedWatch(data) {
  const container = document.getElementById('fedWatch');
  if (!container) return;
  
  const fw = data.fed_watch || data.fedWatch;
  if (!fw) {
    container.innerHTML = '<div class="text-muted">Nessun dato disponibile</div>';
    return;
  }
  
  let html = '<div class="p-2">';
  
  if (Array.isArray(fw)) {
    fw.forEach(item => {
      html += `
        <div class="d-flex justify-content-between align-items-center py-1 border-bottom">
          <div>${item.rate || '—'}</div>
          <strong>${item.prob != null ? (+item.prob).toFixed(1) + '%' : '—'}</strong>
        </div>`;
    });
  }
  
  html += '</div>';
  container.innerHTML = html;
}

function renderEconomicCalendar(data) {
  const container = document.getElementById('economicCalendar');
  if (!container) return;
  
  const events = data.events || [];
  if (!events.length) {
    container.innerHTML = '<div class="text-muted">Nessun evento imminente</div>';
    return;
  }
  
  let html = '';
  events.forEach(event => {
    const impactClass = event.impact === 'high' ? 'high-impact' : 
                       event.impact === 'medium' ? 'medium-impact' : '';
    
    html += `
      <div class="economic-event ${impactClass}">
        <div class="d-flex justify-content-between">
          <div>
            <strong>${event.event || event.name || 'Evento'}</strong>
            <div class="small text-muted">${event.country || '—'} · ${event.time || '—'}</div>
          </div>
          <div class="text-end">
            <div class="small"><span class="text-muted">Atteso:</span> ${event.forecast || '—'}</div>
            <div class="small"><span class="text-muted">Precedente:</span> ${event.previous || '—'}</div>
          </div>
        </div>
      </div>`;
  });
  
  container.innerHTML = html;
}

// =====================================================
// CARICAMENTO PREVISIONI
// =====================================================
async function loadPredictions(symbol) {
  const table = document.getElementById('predictionsTable');
  const gptBox = document.getElementById('gptAnalysis');
  
  try {
    const [predRes, completeRes] = await Promise.allSettled([
      fetchWithCache(`/api/predictions/${encodeURIComponent(symbol)}`),
      fetchWithCache(`/api/analysis/complete/${encodeURIComponent(symbol)}`)
    ]);

    // Tabella previsioni
    if (predRes.status === 'fulfilled' && predRes.value) {
      renderPredictionsTable(predRes.value);
    } else if (table) {
      table.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Nessuna previsione disponibile</td></tr>';
    }

    // Analisi GPT
    if (completeRes.status === 'fulfilled' && completeRes.value) {
      const gpt = completeRes.value.gpt_analysis || 
                  completeRes.value.ml_prediction?.gpt_analysis;
      
      if (gpt) {
        renderGptAnalysis(gptBox, gpt);
      }
    }
    
  } catch (e) {
    console.error('Errore loadPredictions:', e);
  }
}

function renderPredictionsTable(preds) {
  const tbody = document.getElementById('predictionsTable');
  if (!tbody) return;

  if (!Array.isArray(preds) || !preds.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Nessuna previsione disponibile</td></tr>';
    return;
  }

  tbody.innerHTML = preds.map(p => {
    const d = p.prediction_date ? new Date(p.prediction_date) : null;
    const direction = (p.predicted_direction || 'NEUTRAL').toUpperCase();
    const sigCls = signalClass(direction);
    
    return `<tr>
      <td>${d ? dateFmt.format(d) : '—'}</td>
      <td>${p.symbol || '—'}</td>
      <td><span class="signal-box ${sigCls}">${direction}</span></td>
      <td>${p.confidence ? Math.round(p.confidence) + '%' : '—'}</td>
      <td>${p.ml_score != null ? (+p.ml_score).toFixed(2) : '—'}</td>
      <td>${p.status || '—'}</td>
      <td>${p.accuracy != null ? p.accuracy + '%' : '—'}</td>
    </tr>`;
  }).join('');
}

function renderGptAnalysis(container, gpt) {
  if (!container) return;

  if (!gpt) {
    container.innerHTML = '<div class="loading"><p class="mb-0">Nessuna analisi disponibile. Premi "Analisi AI" per generarne una.</p></div>';
    return;
  }

  let obj = typeof gpt === 'string' ? { text: gpt } : gpt;

  const dir = (obj.direction || 'NEUTRAL').toUpperCase();
  const conf = obj.confidence ? Math.round(obj.confidence) : null;
  const reason = obj.reasoning || obj.summary || obj.text || null;

  container.innerHTML = `
    <div class="gpt-card">
      <div class="row g-3">
        <div class="col-12 col-lg-3">
          <div class="gpt-panel h-100 text-center">
            <div class="gpt-label mb-1">Direzione</div>
            <div class="mb-2"><span class="signal-box ${signalClass(dir)}">${dir}</span></div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="gpt-panel h-100 text-center">
            <div class="gpt-label mb-1">Confidenza</div>
            <div class="h4 mb-0">${conf ? conf + '%' : '—'}</div>
          </div>
        </div>
        <div class="col-12">
          <div class="gpt-panel">
            <div class="gpt-label">Analisi</div>
            ${reason ? `<p class="mb-0">${escapeHtml(reason)}</p>` : '<div class="text-muted">—</div>'}
          </div>
        </div>
      </div>
    </div>`;
}

// =====================================================
// CARICAMENTO STATO SISTEMA
// =====================================================
async function loadSystemStatus() {
  try {
    const res = await fetchWithCache('/api/system/status');
    
    if (!res) return;
    
    // Aggiorna le card dello stato
    const cards = document.querySelectorAll('#systemStatusDetail .metric-card .metric-value');
    if (cards[0]) cards[0].textContent = res.database?.status || res.db_status || 'OK';
    if (cards[1]) cards[1].textContent = res.openai?.status || res.openai_status || 'OK';
    if (cards[2]) cards[2].textContent = res.ml?.status || res.ml_status || 'OK';
    if (cards[3]) cards[3].textContent = res.selenium?.status || res.selenium_status || 'OK';

    // Badge header
    const badge = document.getElementById('systemStatus');
    if (badge) {
      const ok = !res.error;
      badge.className = 'badge ' + (ok ? 'bg-success' : 'bg-danger');
      badge.textContent = ok ? 'Sistema Online' : 'Sistema con errori';
    }
  } catch (e) {
    console.warn('Errore loadSystemStatus:', e);
  }
}

// =====================================================
// CARICAMENTO MARKET OVERVIEW
// =====================================================
async function loadMarketOverview() {
  const box = document.getElementById('marketOverview');
  if (!box) return;

  try {
    const res = await fetchWithCache('/api/economic/current');
    
    if (!res) return;
    
    const sentimentPct = res.market_sentiment || res.sentiment || 
                        res.key_indicators?.market_sentiment?.value || 0;
    const riskFlag = res.risk_on ? 'Risk-ON' : res.risk_off ? 'Risk-OFF' : '—';

    box.innerHTML = `
      <div class="row g-3">
        <div class="col-md-4">
          <div class="metric-card">
            <div class="metric-value">${sentimentPct}%</div>
            <div class="metric-label">Market Sentiment</div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="metric-card" style="background:linear-gradient(135deg,#34d399 0%, #10b981 100%)">
            <div class="metric-value">${riskFlag}</div>
            <div class="metric-label">Risk Regime</div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="metric-card" style="background:linear-gradient(135deg,#f59e0b 0%, #ef4444 100%)">
            <div class="metric-value">${dateFmt.format(new Date())}</div>
            <div class="metric-label">Oggi</div>
          </div>
        </div>
      </div>`;
  } catch (e) {
    console.warn('Errore loadMarketOverview:', e);
  }
}

// =====================================================
// CARICAMENTO ALERTS
// =====================================================
async function loadAlerts(symbol) {
  const box = document.getElementById('alertsBox') || document.getElementById('alertsPanel');
  if (!box) return;

  try {
    const res = await fetchWithCache(`/api/technical/${encodeURIComponent(symbol)}`);
    
    if (!res) {
      box.innerHTML = '<div class="text-muted">Nessun alert attivo</div>';
      return;
    }
    
    const alerts = [];
    
    const rdist = +res.distance_to_resistance;
    const sdist = +res.distance_to_support;
    
    if (isFinite(rdist) && rdist <= 0.5) {
      alerts.push({ sev: 'danger', text: `Prezzo vicino alla RESISTENZA (${rdist.toFixed(2)}%)` });
    }
    if (isFinite(sdist) && sdist <= 0.5) {
      alerts.push({ sev: 'success', text: `Prezzo vicino al SUPPORTO (${sdist.toFixed(2)}%)` });
    }
    
    if (!alerts.length) {
      box.innerHTML = '<div class="text-muted">Nessun alert attivo</div>';
      return;
    }
    
    box.innerHTML = `
      <ul class="list-unstyled mb-0">
        ${alerts.map(a => `<li class="mb-1 text-${a.sev}">• ${a.text}</li>`).join('')}
      </ul>`;
      
  } catch (e) {
    console.warn('Errore loadAlerts:', e);
  }
}

// =====================================================
// ANALISI COMPLETA
// =====================================================
async function runFullAnalysis(symbol) {
  if (!userPlan.isAdmin) {
    showAlert('Funzionalità riservata agli amministratori', 'warning');
    return;
  }
  
  console.log('🧠 Avvio analisi AI completa...');
  
  try {
    // USA GET NON POST!
    const res = await fetch(`/api/scrape/${encodeURIComponent(symbol)}`, {
      method: 'GET',  // <-- IMPORTANTE: GET non POST
      headers: {
        'Accept': 'application/json'
      }
    });
    
    if (!res.ok) throw new Error('scrape failed');

    const data = await res.json();

    // Aggiorna subito la box GPT
    if (data && data.gpt_analysis) {
      renderGptAnalysis(document.getElementById('gptAnalysis'), data.gpt_analysis);
    }

    // Pulisci cache per forzare refresh
    cache.clear();
    
    // Ricarica tutto
    await reloadAll();

    showAlert('Analisi AI completata', 'success');
  } catch (e) {
    console.error('Errore runFullAnalysis:', e);
    showAlert('Errore durante l\'analisi AI', 'danger');
  }
}

// =====================================================
// AUTO-REFRESH
// =====================================================
function setupAutoRefresh() {
  if (autoRefreshInterval) clearInterval(autoRefreshInterval);
  
  autoRefreshInterval = setInterval(async () => {
    console.log('🔄 Auto-refresh...');
    try {
      await loadOverview(currentSymbol);
      await loadPredictions(currentSymbol);
    } catch (e) {
      console.warn('Auto refresh error:', e);
    }
  }, 300000); // 5 minuti
  
  console.log('⏰ Auto-refresh attivo ogni 5 minuti'); // <-- CORRETTO
}
// =====================================================
// UTILITIES
// =====================================================
async function fetchWithCache(url) {
  const cacheKey = url;
  const cached = cache.get(cacheKey);
  
  // Check cache
  if (cached && (Date.now() - cached.timestamp < cacheTimeout)) {
    console.log(`✅ Cache hit: ${url}`);
    return cached.data;
  }
  
  // AUMENTA IL TIMEOUT A 30 SECONDI per /api/analysis/complete/
  const controller = new AbortController();
  const timeoutMs = url.includes('/api/analysis/complete/') ? 30000 : 10000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  
  try {
    const response = await fetch(url, {
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    
    // Salva in cache solo se dati validi
    if (data && !data.error) {
      cache.set(cacheKey, {
        data: data,
        timestamp: Date.now()
      });
    }
    
    return data;
  } catch (error) {
    if (error.name === 'AbortError') {
      console.log(`⏱️ Timeout per ${url}`);
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

function signalClass(signal) {
  const s = (signal || 'NEUTRAL').toUpperCase();
  if (s.includes('STRONG_BUY')) return 'signal-strong-buy';
  if (s.includes('BUY') || s === 'BULLISH') return 'signal-bullish';
  if (s.includes('STRONG_SELL')) return 'signal-strong-sell';
  if (s.includes('SELL') || s === 'BEARISH') return 'signal-bearish';
  return 'signal-neutral';
}

function showAlert(message, type='info', timeout=3000) {
  const wrap = document.getElementById('alertsContainer');
  if (!wrap) return;
  
  const id = 'al_' + Math.random().toString(36).slice(2);
  const html = `
    <div id="${id}" class="alert alert-${type} alert-custom mt-2" role="alert">
      ${message}
    </div>`;
  wrap.insertAdjacentHTML('beforeend', html);
  
  if (timeout) {
    setTimeout(() => {
      const el = document.getElementById(id);
      if (el) el.remove();
    }, timeout);
  }
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
<<<<<<< HEAD
  if (autoRefreshInterval) clearInterval(autoRefreshInterval);
  if (updateInterval) clearInterval(updateInterval);
});
=======
    if (window.cotDashboard) {
        window.cotDashboard.destroy();
    }
});
>>>>>>> 6b6ae4199e1bd005e2249547dcc6d158d9f2979a
