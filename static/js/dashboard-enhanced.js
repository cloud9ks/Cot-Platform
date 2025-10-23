/**
 * COT Analysis Platform - Dashboard Enhanced JavaScript
 * Sistema completo per gestione dashboard avanzata
 */

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
const cacheTimeout = 30000; // 30 secondi invece di 5 minuti
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
const numberFmt = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 0,
  useGrouping: true
});
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

    // Setup event listeners
    setupEventListeners();

    // Carica simboli
    await loadSymbols();

    // Inizializza grafici
    initCharts();

    // Carica dati iniziali
    await loadInitialData();

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
        }
      };
      applyPlanRestrictions();
    }
  } catch (e) {
    console.warn('Piano config non disponibile:', e);
  }
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
        // Evita doppio click sullo stesso simbolo
        if (currentSymbol === symbol.code) {
          console.log('⚠️ Simbolo già selezionato:', symbol.code);
          return;
        }

        document.querySelectorAll('.symbol-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const oldSymbol = currentSymbol;
        currentSymbol = symbol.code;

        console.log(`🔄 Cambio simbolo: ${oldSymbol} → ${currentSymbol}`);

        // Forza il reload completo con bypass cache
        await reloadAll(true);
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
      console.log('🔄 Refresh manuale richiesto');
      btnRefresh.classList.add('btn-loading');
      btnRefresh.disabled = true;

      // Forza il reload completo bypassando la cache
      await reloadAll(true);

      btnRefresh.classList.remove('btn-loading');
      btnRefresh.disabled = false;
      showAlert('✅ Dati aggiornati con successo', 'success');
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
      type: 'bar',
      data: {
        labels: [],
        datasets: [
          {
            label: 'NC Long',
            data: [],
            backgroundColor: 'rgba(16,185,129,0.8)',
            borderColor: '#10b981',
            borderWidth: 1
          },
          {
            label: 'NC Short',
            data: [],
            backgroundColor: 'rgba(239,68,68,0.8)',
            borderColor: '#ef4444',
            borderWidth: 1
          },
          {
            label: 'Commercial Long',
            data: [],
            backgroundColor: 'rgba(59,130,246,0.8)',
            borderColor: '#3b82f6',
            borderWidth: 1
          },
          {
            label: 'Commercial Short',
            data: [],
            backgroundColor: 'rgba(245,158,11,0.8)',
            borderColor: '#f59e0b',
            borderWidth: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: {
              font: { size: 12, weight: 'bold' }
            }
          },
          tooltip: {
            mode: 'index',
            intersect: false,
            callbacks: {
              label: function(context) {
                let label = context.dataset.label || '';
                if (label) {
                  label += ': ';
                }
                label += numberFmt.format(context.parsed.y);
                return label;
              }
            }
          }
        },
        scales: {
          x: {
            stacked: false,
            grid: {
              display: false
            }
          },
          y: {
            stacked: false,
            beginAtZero: false,
            ticks: {
              callback: (v) => numberFmt.format(v),
              font: { size: 11 }
            },
            grid: {
              color: 'rgba(0,0,0,0.05)'
            }
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
      loadCotHistory(currentSymbol, 90), // Default 90 giorni per coerenza con UI
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

async function reloadAll(forceRefresh = false) {
  // Se forceRefresh è true, pulisci la cache prima di ricaricare
  if (forceRefresh) {
    cache.clear();
    console.log('🗑️ Cache pulita prima del reload');
  }

  // OTTIMIZZATO: Carica solo dati essenziali per non sovraccaricare il server
  // Le altre sezioni si caricano on-demand quando apri la tab
  await Promise.allSettled([
    loadOverview(currentSymbol),
    loadCotHistory(currentSymbol, getSelectedDays())
    // Technical, Economic, Predictions vengono caricati solo quando apri la tab specifica
  ]);

  console.log('✅ Reload completato per simbolo:', currentSymbol);
}

function getSelectedDays() {
  const active = document.querySelector('[data-period].active');
  return active ? parseInt(active.dataset.period, 10) : 90; // Default 90 giorni
}

// =====================================================
// CARICAMENTO OVERVIEW
// =====================================================
async function loadOverview(symbol) {
  console.log('📊 loadOverview per simbolo:', symbol);

  try {
    // Carica analisi completa
    const url = `/api/analysis/complete/${encodeURIComponent(symbol)}`;
    console.log('  Fetching:', url);
    const completeRes = await fetchWithCache(url);

    console.log('  Risposta completeRes:', completeRes);
    console.log('  Simbolo nella risposta:', completeRes?.symbol);

    if (completeRes?.symbol !== symbol) {
      console.error(`❌ SIMBOLO SBAGLIATO! Richiesto: ${symbol}, Ricevuto: ${completeRes?.symbol}`);
    } else {
      console.log(`✅ Simbolo corretto: ${symbol}`);
    }

    if (completeRes && !completeRes.error) {
      updateDashboard(completeRes);
    }

    // Carica dati COT separatamente se necessario
    const cotUrl = `/api/data/${encodeURIComponent(symbol)}?days=90`;
    console.log('  Fetching COT:', cotUrl);
    const cotRes = await fetchWithCache(cotUrl);

    console.log('  Risposta cotRes:', cotRes);

    if (cotRes && cotRes.length > 0) {
      const latest = cotRes[0];
      const prev = cotRes[1] || null;

      console.log('  Latest COT symbol:', latest?.symbol);

      if (latest?.symbol !== symbol) {
        console.error(`❌ COT SIMBOLO SBAGLIATO! Richiesto: ${symbol}, Ricevuto: ${latest?.symbol}`);
      }

      // Aggiorna elementi overview
      updateOverviewElements(latest, prev);

      // Aggiorna quick analysis
      updateQuickAnalysis(latest);
    }

  } catch (e) {
    console.error('❌ Errore loadOverview:', e);
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
    console.log('✅ GPT analysis found in updateDashboard:', data.gpt_analysis);
    renderGptAnalysis(document.getElementById('gptAnalysis'), data.gpt_analysis);
  } else {
    console.warn('⚠️ No gpt_analysis in updateDashboard data');
  }
}

function setSentimentBar(score) {
  const bar = document.querySelector('#sentimentBar > div');
  if (!bar) return;

  const w = Math.min(100, Math.max(0, ((score + 100) / 2)));
  bar.style.width = `${w}%`;

  if (score >= 10) {
    bar.style.background = 'linear-gradient(90deg,#10b981,#34d399)';
  } else if (score <= -10) {
    bar.style.background = 'linear-gradient(90deg,#ef4444,#f87171)';
  } else {
    bar.style.background = 'linear-gradient(90deg,#6b7280,#9ca3af)';
  }
}

function setAIPrediction(mlPred) {
  const box = document.getElementById('aiPrediction');
  const confEl = document.getElementById('confidence');

  if (!mlPred) {
    if (box) box.innerHTML = `<span class="signal-box signal-neutral">IN ATTESA</span>`;
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

    // Aggiorna solo i grafici (tabella rimossa)
    updateCOTCharts(res);

  } catch (e) {
    console.error('Errore loadCotHistory:', e);
  }
}

function updateCOTCharts(data) {
  if (!data || !data.length) return;

  const labels = [], ncLong = [], ncShort = [], cLong = [], cShort = [];

  // Ordina per data crescente per il grafico
  const sorted = [...data].sort((a, b) => new Date(a.date) - new Date(b.date));

  sorted.forEach(r => {
    const d = new Date(r.date);
    labels.push(dateFmt.format(d));
    ncLong.push(r.non_commercial_long);
    ncShort.push(r.non_commercial_short);
    cLong.push(r.commercial_long);
    cShort.push(r.commercial_short);
  });

  if (cotChart) {
    cotChart.data.labels = labels;
    cotChart.data.datasets[0].data = ncLong;
    cotChart.data.datasets[1].data = ncShort;
    cotChart.data.datasets[2].data = cLong;
    cotChart.data.datasets[3].data = cShort;
    cotChart.update('none'); // Update senza animazione per performance migliori
  }

  if (pieChart && sorted.length > 0) {
    const last = sorted[sorted.length - 1];
    pieChart.data.datasets[0].data = [
      last.non_commercial_long,
      last.non_commercial_short,
      last.commercial_long,
      last.commercial_short
    ];
    pieChart.update('none');
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
  const gptBox = document.getElementById('gptAnalysis');

  try {
    // Carica solo analisi completa (no tabella previsioni)
    const completeRes = await fetchWithCache(`/api/analysis/complete/${encodeURIComponent(symbol)}`);

    if (completeRes) {
      console.log('📥 Complete analysis response:', completeRes);
      console.log('🔍 gpt_analysis:', completeRes.gpt_analysis);
      console.log('🔍 ml_prediction.gpt_analysis:', completeRes.ml_prediction?.gpt_analysis);

      const gpt = completeRes.gpt_analysis ||
                  completeRes.ml_prediction?.gpt_analysis;

      if (gpt) {
        console.log('✅ Rendering GPT analysis:', gpt);
        renderGptAnalysis(gptBox, gpt);
      } else {
        console.warn('⚠️ No GPT analysis found in response');
        if (gptBox) {
          gptBox.innerHTML = '<div class="loading"><p class="mb-0">Nessuna analisi disponibile. Premi "Analisi AI" per generarne una.</p></div>';
        }
      }
    }

  } catch (e) {
    console.error('Errore loadPredictions:', e);
  }
}

function renderGptAnalysis(container, gpt) {
  console.log('🎨 renderGptAnalysis called');
  console.log('  container:', container);
  console.log('  gpt:', gpt);

  if (!container) {
    console.error('❌ Container non trovato!');
    return;
  }

  if (!gpt) {
    console.warn('⚠️ GPT non disponibile');
    container.innerHTML = '<div class="text-center py-5"><div class="text-muted"><i class="fas fa-robot fa-3x mb-3 opacity-25"></i><p class="mb-0">Nessuna analisi disponibile.<br>Premi "Analisi AI" per generarne una.</p></div></div>';
    return;
  }

  let obj = typeof gpt === 'string' ? { text: gpt } : gpt;
  console.log('  obj:', obj);

  const dir = (obj.direction || obj.trading_bias || 'NEUTRAL').toUpperCase();
  const conf = obj.confidence ? Math.round(obj.confidence) : null;
  const reason = obj.reasoning || obj.summary || obj.text || obj.market_outlook || null;

  // Estrai dettagli aggiuntivi se presenti
  const marketOutlook = obj.market_outlook || null;
  const keyFactors = obj.key_factors || obj.factors || null;
  const risks = obj.risks || obj.risk_factors || null;
  const actionableInsights = obj.actionable_insights || obj.action_items || null;
  const scenarios = obj.scenarios || null;
  const positioning = obj.positioning_analysis || null;
  const quantMetrics = obj.quantitative_metrics || null;

  console.log('  dir:', dir);
  console.log('  conf:', conf);
  console.log('  reason:', reason);

  try {
    // Segnale visivo migliorato
    let signalColor, signalIcon, signalBg;
    if (dir.includes('BULLISH') || dir.includes('BUY')) {
      signalColor = 'success';
      signalIcon = 'fa-arrow-trend-up';
      signalBg = 'rgba(16,185,129,0.1)';
    } else if (dir.includes('BEARISH') || dir.includes('SELL')) {
      signalColor = 'danger';
      signalIcon = 'fa-arrow-trend-down';
      signalBg = 'rgba(239,68,68,0.1)';
    } else {
      signalColor = 'secondary';
      signalIcon = 'fa-arrows-left-right';
      signalBg = 'rgba(107,114,128,0.1)';
    }

    // Barra di confidenza
    const confBar = conf ? `
      <div class="progress mt-2" style="height: 8px;">
        <div class="progress-bar bg-${signalColor}" role="progressbar" style="width: ${conf}%" aria-valuenow="${conf}" aria-valuemin="0" aria-valuemax="100"></div>
      </div>` : '';

    // Layout migliorato
    const html = `
    <div class="card border-0 shadow-sm" style="background: ${signalBg};">
      <div class="card-body p-4">
        <div class="row g-4">
          <!-- Segnale Principale -->
          <div class="col-12 col-md-4">
            <div class="text-center p-3 bg-white rounded-3 shadow-sm h-100">
              <i class="fas ${signalIcon} fa-3x text-${signalColor} mb-3"></i>
              <h5 class="text-uppercase fw-bold text-${signalColor} mb-2">${dir}</h5>
              <small class="text-muted d-block mb-2">Segnale AI</small>
              ${conf ? `<div class="h3 fw-bold mb-0">${conf}%</div><small class="text-muted">Confidenza</small>${confBar}` : '<div class="text-muted">—</div>'}
            </div>
          </div>

          <!-- Analisi Dettagliata -->
          <div class="col-12 col-md-8">
            <div class="bg-white rounded-3 shadow-sm p-4 h-100">
              <h6 class="fw-bold mb-3 d-flex align-items-center">
                <i class="fas fa-chart-line me-2 text-primary"></i>
                Analisi di Mercato
              </h6>

              ${reason ? `
                <div class="mb-3">
                  <div class="small text-muted mb-1 fw-bold"><i class="fas fa-file-lines me-1"></i>Sintesi</div>
                  <p class="mb-0 lh-lg">${escapeHtml(reason)}</p>
                </div>
              ` : ''}

              ${marketOutlook && marketOutlook !== reason ? `
                <div class="mb-3">
                  <div class="small text-muted mb-1 fw-bold"><i class="fas fa-chart-line me-1"></i>Market Outlook</div>
                  <p class="mb-0 lh-base">${escapeHtml(marketOutlook)}</p>
                </div>
              ` : ''}

              ${keyFactors ? `
                <div class="mb-3">
                  <div class="small text-muted mb-1 fw-bold"><i class="fas fa-lightbulb me-1"></i>Fattori Chiave</div>
                  <p class="mb-0 lh-base">${escapeHtml(typeof keyFactors === 'string' ? keyFactors : JSON.stringify(keyFactors))}</p>
                </div>
              ` : ''}

              ${positioning ? `
                <div class="mb-3 p-2 bg-light rounded">
                  <div class="small text-muted mb-2 fw-bold"><i class="fas fa-users me-1"></i>Analisi Posizionamento</div>
                  ${positioning.non_commercial ? `<div class="small mb-1"><strong>Non-Commercial:</strong> ${escapeHtml(positioning.non_commercial)}</div>` : ''}
                  ${positioning.commercial ? `<div class="small mb-1"><strong>Commercial:</strong> ${escapeHtml(positioning.commercial)}</div>` : ''}
                  ${positioning.divergence ? `<div class="small"><strong>Divergenza:</strong> ${escapeHtml(positioning.divergence)}</div>` : ''}
                </div>
              ` : ''}

              ${quantMetrics ? `
                <div class="mb-3">
                  <div class="small text-muted mb-2 fw-bold"><i class="fas fa-chart-bar me-1"></i>Metriche Quantitative</div>
                  <div class="row g-2">
                    ${quantMetrics.net_position_percentile ? `<div class="col-6 col-md-4"><div class="small p-2 border rounded"><strong>Percentile:</strong><br>${escapeHtml(quantMetrics.net_position_percentile)}</div></div>` : ''}
                    ${quantMetrics.sentiment_strength ? `<div class="col-6 col-md-4"><div class="small p-2 border rounded"><strong>Sentiment:</strong><br>${escapeHtml(quantMetrics.sentiment_strength)}</div></div>` : ''}
                    ${quantMetrics.positioning_extreme ? `<div class="col-12 col-md-4"><div class="small p-2 border rounded"><strong>Posizionamento:</strong><br>${escapeHtml(quantMetrics.positioning_extreme)}</div></div>` : ''}
                  </div>
                </div>
              ` : ''}

              ${scenarios ? `
                <div class="mb-3 p-2 border border-primary rounded">
                  <div class="small text-primary mb-2 fw-bold"><i class="fas fa-road me-1"></i>Scenari</div>
                  ${scenarios.bullish_case ? `<div class="small mb-2"><span class="badge bg-success me-1">BULLISH</span> ${escapeHtml(scenarios.bullish_case)}</div>` : ''}
                  ${scenarios.bearish_case ? `<div class="small mb-2"><span class="badge bg-danger me-1">BEARISH</span> ${escapeHtml(scenarios.bearish_case)}</div>` : ''}
                  ${scenarios.most_likely ? `<div class="small fw-bold text-primary"><i class="fas fa-star me-1"></i>Più probabile: ${escapeHtml(scenarios.most_likely)}</div>` : ''}
                </div>
              ` : ''}

              ${actionableInsights && Array.isArray(actionableInsights) ? `
                <div class="mb-3">
                  <div class="small text-muted mb-2 fw-bold"><i class="fas fa-bolt me-1 text-warning"></i>Azioni Consigliate</div>
                  <ul class="small mb-0 ps-3">
                    ${actionableInsights.map(insight => `<li class="mb-1">${escapeHtml(insight)}</li>`).join('')}
                  </ul>
                </div>
              ` : ''}

              ${risks ? `
                <div class="mb-0">
                  <div class="small text-muted mb-1 fw-bold"><i class="fas fa-exclamation-triangle me-1 text-warning"></i>Rischi</div>
                  <p class="mb-0 small text-warning lh-base">${escapeHtml(typeof risks === 'string' ? risks : JSON.stringify(risks))}</p>
                </div>
              ` : ''}

              ${!reason && !marketOutlook && !keyFactors ? `
                <div class="text-center text-muted py-3">
                  <i class="fas fa-info-circle fa-2x mb-2 opacity-25"></i>
                  <p class="mb-0">Analisi in fase di elaborazione...<br>I dettagli appariranno qui quando disponibili.</p>
                </div>
              ` : ''}
            </div>
          </div>
        </div>

        <!-- Footer con timestamp -->
        <div class="text-center mt-3">
          <small class="text-muted">
            <i class="fas fa-clock me-1"></i>
            Analisi generata il ${dateFmt.format(new Date())}
          </small>
        </div>
      </div>
    </div>`;

    console.log('  HTML generato, lunghezza:', html.length);
    container.innerHTML = html;
    console.log('✅ GPT renderizzata con successo!');
  } catch (e) {
    console.error('❌ Errore durante rendering GPT:', e);
    container.innerHTML = '<div class="alert alert-danger">Errore nel rendering dell\'analisi</div>';
  }
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

    // Market sentiment può essere un oggetto o un numero
    let sentimentValue = '—';
    if (res.market_sentiment) {
      if (typeof res.market_sentiment === 'object') {
        // È un oggetto, prendi overall_sentiment
        sentimentValue = res.market_sentiment.overall_sentiment || '—';
      } else {
        sentimentValue = `${res.market_sentiment}%`;
      }
    }

    const riskFlag = res.risk_on ? 'Risk-ON' :
                     res.risk_off ? 'Risk-OFF' :
                     res.market_sentiment?.overall_sentiment || '—';

    box.innerHTML = `
      <div class="row g-3">
        <div class="col-md-4">
          <div class="metric-card">
            <div class="metric-value">${sentimentValue}</div>
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
  showAlert('Analisi AI in corso...', 'info', 10000);

  try {
    const res = await fetch(`/api/scrape/${encodeURIComponent(symbol)}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      }
    });

    if (!res.ok) throw new Error('scrape failed');

    const data = await res.json();

    console.log('✅ Scraping completato, risposta:', data);
    console.log('🔍 data.gpt_analysis:', data.gpt_analysis);
    console.log('🔍 data.data?.gpt_analysis:', data.data?.gpt_analysis);

    // Pulisci TUTTA la cache per forzare refresh
    cache.clear();
    console.log('🗑️ Cache JavaScript completamente pulita');

    // Aspetta 2 secondi per assicurarsi che il backend abbia salvato tutto E invalidato la cache
    console.log('⏳ Aspetto 2 secondi per backend cache invalidation...');
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Ricarica tutto FORZANDO il bypass della cache
    console.log('🔄 Ricaricamento forzato di tutti i dati...');
    await reloadAll(true); // Force refresh = true

    // Dopo reloadAll, loadPredictions dovrebbe aver già caricato GPT
    // Ma logghiamo per essere sicuri
    console.log('✅ reloadAll completato, GPT dovrebbe essere visibile ora');

    showAlert('✅ Analisi AI completata e dati aggiornati!', 'success', 5000);
  } catch (e) {
    console.error('❌ Errore runFullAnalysis:', e);
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

  console.log('⏰ Auto-refresh attivo ogni 5 minuti');
}

// =====================================================
// UTILITIES
// =====================================================
async function fetchWithCache(url, bypassCache = false) {
  const cacheKey = url;
  const cached = cache.get(cacheKey);

  // Se bypassCache è true, salta completamente la cache
  if (!bypassCache && cached && (Date.now() - cached.timestamp < cacheTimeout)) {
    console.log(`✅ Cache hit: ${url}`);
    return cached.data;
  }

  // Aggiungi timestamp per forzare bypass cache HTTP del browser
  const separator = url.includes('?') ? '&' : '?';
  const fetchUrl = bypassCache ? `${url}${separator}_t=${Date.now()}` : url;

  if (bypassCache) {
    console.log(`🔄 Bypass cache per: ${url}`);
  }

  const controller = new AbortController();
  // Aumentato timeout a 30s per TUTTE le API (Render free tier è lento)
  const timeoutMs = 30000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(fetchUrl, {
      signal: controller.signal,
      headers: {
        'Cache-Control': bypassCache ? 'no-cache, no-store, must-revalidate' : 'default',
        'Pragma': bypassCache ? 'no-cache' : 'default'
      }
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

    // Ritorna dati cached anche se vecchi (solo se non stiamo forzando bypass)
    if (!bypassCache && cached) {
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
  if (autoRefreshInterval) clearInterval(autoRefreshInterval);
  if (updateInterval) clearInterval(updateInterval);
});
