/**
 * COT Analysis Platform - Dashboard Enhanced JavaScript CORRETTO
 * Sistema completo per gestione dashboard avanzata
 */

/* ========= STATO ========= */
let currentSymbol = 'GOLD';
let symbols = {};
let cotChart = null;
let pieChart = null;
let priceChart = null;
let isAnalyzing = false;
let autoRefreshInterval = null;
let priceChartInstance = null;

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

/* ========= FORMATTERS ========= */
const numberFmt = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 4 });
const currencyFmt = new Intl.NumberFormat('it-IT', {
  style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2
});
const dateFmt = new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' });
const fmt = (v, dec = 2) => (v == null ? '—' : (+v).toFixed(dec));

/* ========= FUNZIONE MANCANTE signalClass ========= */
function signalClass(signal) {
  const s = (signal || 'NEUTRAL').toUpperCase();
  if (s.includes('STRONG_BUY')) return 'signal-strong-buy';
  if (s.includes('BUY') || s === 'BULLISH') return 'signal-bullish';
  if (s.includes('STRONG_SELL')) return 'signal-strong-sell';
  if (s.includes('SELL') || s === 'BEARISH') return 'signal-bearish';
  return 'signal-neutral';
}

/* ========= FUNZIONE MANCANTE renderTechnicalIndicators ========= */
function renderTechnicalIndicators(data) {
  // Questa funzione è chiamata da loadOverview ma non serve più
  // La lasciamo vuota per evitare errori
  return;
}

/* ========= BOOT ========= */
document.addEventListener('DOMContentLoaded', async () => {
  try {
    await loadUserPlanConfig();
    setupEventListeners();
    await loadSymbols();
    initCharts();
    await loadInitialData();
    setupAutoRefresh();
    console.log('✅ Dashboard pronta');
  } catch (err) {
    console.error('❌ Errore inizializzazione:', err);
    showAlert("Errore durante l'inizializzazione della dashboard", 'danger');
  }
});
/* ========= CONFIGURAZIONE PIANO ========= */
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
  
  if (!userPlan.features.aiPredictions) {
    const tab = document.getElementById('predictions-tab');
    if (tab) {
      tab.style.opacity = '0.5';
      tab.style.pointerEvents = 'none';
      tab.title = 'Disponibile solo con piano Professional';
    }
  }
  
  if (!userPlan.features.technicalAnalysis) {
    const tab = document.getElementById('technical-tab');
    if (tab) {
      tab.style.opacity = '0.5';
      tab.style.pointerEvents = 'none';
      tab.title = 'Disponibile solo con piano Professional';
    }
  }
}

function checkFeatureAccess(feature) {
  if (userPlan.isAdmin) return true;
  return userPlan.features[feature] || false;
}

/* ========= LISTENERS ========= */
function setupEventListeners() {
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

  const btnSystemStatus = document.getElementById('btnSystemStatus');
  if (btnSystemStatus) {
    btnSystemStatus.addEventListener('click', async () => {
      try { 
        await loadSystemStatus(); 
        showAlert('Stato sistema aggiornato', 'info'); 
      } catch { 
        showAlert('Impossibile recuperare lo stato del sistema', 'warning'); 
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

  // Tab listener per analisi tecnica
  const techTab = document.getElementById('technical-tab');
  if (techTab) {
    techTab.addEventListener('shown.bs.tab', () => {
      loadTechnical(currentSymbol);
    });
  }
}

/* ========= SIMBOLI ========= */
async function loadSymbols() {
  setLoading('#symbolSelector', true, 'Caricamento simboli...');
  try {
    const res = await fetch('/api/symbols');
    if (!res.ok) throw new Error('symbols fetch failed');
    const data = await res.json();

    let symbolsList = [];
    let planLimit = null;
    
    if (data.symbols && Array.isArray(data.symbols)) {
      symbolsList = data.symbols;
      planLimit = data.limit;
      
      if (planLimit && planLimit > 0 && data.message) {
        const container = document.getElementById('symbolSelector');
        const alert = document.createElement('div');
        alert.className = 'alert alert-warning mb-3';
        alert.innerHTML = `<i class="fas fa-info-circle"></i> ${data.message}`;
        container.parentElement.insertBefore(alert, container);
      }
    } else {
      symbolsList = Object.keys(data).map(code => ({
        code: code,
        name: data[code].name || code
      }));
    }

    const container = document.getElementById('symbolSelector');
    container.innerHTML = '';
    
    symbolsList.forEach((symbol) => {
      const code = symbol.code || symbol;
      const name = symbol.name || symbol;
      
      const btn = document.createElement('button');
      btn.className = 'symbol-btn' + (code === currentSymbol ? ' active' : '');
      btn.textContent = `${code} — ${name}`;
      btn.dataset.symbol = code;
      
      btn.addEventListener('click', async () => {
        if (currentSymbol === code) return;
        document.querySelectorAll('.symbol-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentSymbol = code;
        await reloadAll();
      });
      
      container.appendChild(btn);
    });

    symbols = {};
    symbolsList.forEach(s => {
      const code = s.code || s;
      symbols[code] = { name: s.name || code };
    });

    if (symbolsList.length > 0) {
      const firstSymbol = symbolsList[0].code || symbolsList[0];
      if (!currentSymbol || !symbols[currentSymbol]) {
        currentSymbol = firstSymbol;
        await reloadAll();
      }
    }
    
  } catch (e) {
    console.error('Errore caricamento simboli:', e);
    document.getElementById('symbolSelector').innerHTML = 
      '<div class="alert alert-danger">Errore nel caricamento dei simboli</div>';
  }
}
/* ========= CHARTS ========= */
function initCharts() {
  const cotCtx = document.getElementById('cotChart');
  const pieCtx = document.getElementById('pieChart');
  const priceCtx = document.getElementById('priceChart');

  if (cotCtx) {
    cotChart = new Chart(cotCtx, {
      type: 'line',
      data: { 
        labels: [], 
        datasets: [
          { label: 'NC Long', data: [], borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.1)', tension: 0.25 },
          { label: 'NC Short', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', tension: 0.25 },
          { label: 'Commercial Long', data: [], borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', tension: 0.25 },
          { label: 'Commercial Short', data: [], borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)', tension: 0.25 },
          { label: 'Net Position', data: [], borderColor: '#8b5cf6', borderWidth: 3, tension: 0.25 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { 
          legend: { position: 'top' }, 
          tooltip: { mode: 'index', intersect: false } 
        },
        interaction: { mode: 'nearest', intersect: false },
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
            label: 'Strong Support', 
            data: [], 
            borderColor: '#10b981',
            borderDash: [6, 6], 
            pointRadius: 0 
          },
          { 
            label: 'Strong Resistance', 
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
          y: { ticks: { callback: (v) => numberFmt.format(v) } },
          x: { display: false }
        }
      }
    });
  }
}
// ========== HELPERS PANORAMICA MERCATO ROBUSTI ==========

// Normalizza un percentuale da numero o stringa ("98,3%", "0.983", 98.3)
function normalizePercent(v) {
  if (v == null || v === '') return null;
  if (typeof v === 'number') return v <= 1 ? Math.round(v * 100) : Math.round(v);
  if (typeof v === 'string') {
    const m = v.match(/-?\d+(?:[.,]\d+)?/);
    if (!m) return null;
    const n = parseFloat(m[0].replace(',', '.'));
    if (!isFinite(n)) return null;
    return n <= 1 ? Math.round(n * 100) : Math.round(n);
  }
  return null;
}

// Estrae un valore annidato con "path" tipo "a.b.c"
function pick(obj, path) {
  return path.split('.').reduce((acc, k) => (acc && acc[k] != null ? acc[k] : undefined), obj);
}

// Cerca in profondità il PRIMO valore il cui nome chiave contiene "keyPart"
// e prova a normalizzarlo a percentuale (se chiediamo "sentiment") o a risk flag.
function deepFindByKey(obj, keyPart) {
  const part = keyPart.toLowerCase();
  const stack = [obj];
  while (stack.length) {
    const cur = stack.pop();
    if (cur && typeof cur === 'object') {
      for (const [k, v] of Object.entries(cur)) {
        if (k.toLowerCase().includes(part)) return v;
        if (v && typeof v === 'object') stack.push(v);
      }
    }
  }
  return undefined;
}

// Converte varie forme in boolean Risk-ON/Risk-OFF
function normalizeRiskFlag(v) {
  if (v == null) return null;
  if (typeof v === 'boolean') return v;
  if (typeof v === 'number') {
    // es. 1 ON, 0 OFF
    if (v === 1) return true;
    if (v === 0) return false;
  }
  const s = String(v).toLowerCase();
  if (['on', 'risk-on', 'riskon', 'bull', 'bullish'].some(t => s.includes(t))) return true;
  if (['off', 'risk-off', 'riskoff', 'bear', 'bearish'].some(t => s.includes(t))) return false;
  return null;
}

/* ========= LOAD CICLO ========= */
async function loadInitialData() {
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
}

function setupAutoRefresh() {
  if (autoRefreshInterval) clearInterval(autoRefreshInterval);
  autoRefreshInterval = setInterval(async () => {
    try {
      await loadOverview(currentSymbol);
      await loadPredictions(currentSymbol);
    } catch (e) {
      console.warn('Auto refresh error:', e);
    }
  }, 60_000);
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
/* ========= ALERT & NOTIFICHE ========= */
function withinHours(ts, hours=48) {
  const t = new Date(ts);
  if (isNaN(+t)) return false;
  const diffH = (t - new Date()) / 36e5;
  return diffH >= 0 && diffH <= hours;
}

async function loadAlerts(symbol) {
  const box = document.getElementById('alertsBox') || document.getElementById('alertsPanel');
  if (!box) return;

  // Se non ha accesso agli alert personalizzati, mostra upgrade
  if (!checkFeatureAccess('alerts')) {
    box.innerHTML = `
      <div class="alert alert-info">
        <i class="fas fa-bell-slash"></i>
        <strong>Alert Personalizzati</strong>
        <p class="mb-2 small">Ricevi notifiche automatiche quando il mercato si muove.</p>
        <a href="/pricing" class="btn btn-sm btn-success">Upgrade a Professional</a>
      </div>`;
    return;
  }

  try {
    const [tRes, calRes] = await Promise.allSettled([
      fetch(`/api/technical/${encodeURIComponent(symbol)}`),
      fetch('/api/economic/calendar')
    ]);

    const alerts = [];

    // --- Technical based alerts ---
    if (tRes.status === 'fulfilled' && tRes.value.ok) {
      const t = await tRes.value.json();
      const sdist = +t.distance_to_support;
      const rdist = +t.distance_to_resistance;
      const bias  = (t.trend_bias || '').toString().toUpperCase();
      const pos   = (t.price_position || '').toString().toUpperCase();

      if (isFinite(rdist) && rdist <= 0.5) alerts.push({ sev:'danger', text:`Prezzo vicino alla RESISTENZA (${rdist.toFixed(2)}%)` });
      if (isFinite(sdist) && sdist <= 0.5) alerts.push({ sev:'success', text:`Prezzo vicino al SUPPORTO (${sdist.toFixed(2)}%)` });
      if (bias === 'BULLISH') alerts.push({ sev:'success', text:'Trend bias: BULLISH' });
      if (bias === 'BEARISH') alerts.push({ sev:'danger',  text:'Trend bias: BEARISH' });
      if (pos === 'BREAKOUT') alerts.push({ sev:'warning', text:'Possibile breakout in corso' });
    }

    // --- Calendar based alerts ---
    if (calRes.status === 'fulfilled' && calRes.value.ok) {
      const c = await calRes.value.json();
      const events = Array.isArray(c?.events) ? c.events : [];
      const hi = events.filter(ev =>
        (ev.impact || '').toString().toLowerCase().startsWith('high') &&
        withinHours(ev.datetime || ev.time || ev.date, 48)
      );

      if (hi.length) {
        const list = hi.slice(0, 3)
          .map(ev => `${ev.event || 'Evento'} (${ev.country || ev.region || ev.currency || ''} - ${ev.time || ev.datetime || ''})`)
          .join('<br>');
        alerts.push({ sev:'warning', text:`Eventi ad alto impatto in arrivo (48h):<br>${list}` });
      }
    }

    // --- Render ---
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
    box.innerHTML = '<div class="text-muted">Impossibile caricare gli alert</div>';
  }
}
/* ========= OVERVIEW ========= */
async function loadOverview(symbol) {
  try {
    const res = await fetch(`/api/data/${encodeURIComponent(symbol)}?days=90`);
    if (!res.ok) throw new Error('overview fetch failed');
    
    const rows = await res.json();
    if (!rows.length) {
      updateOverviewElements('—', '—', '—', 0, null);
      return;
    }
    
    const latest = rows[0];
    const prev = rows[1] || null;

    // Net Position
    document.getElementById('netPosition').textContent = numberFmt.format(latest.net_position);
    const netChange = prev ? latest.net_position - prev.net_position : 0;
    const elChange = document.getElementById('netChange');
    elChange.textContent = `${netChange >= 0 ? '+' : ''}${numberFmt.format(netChange)}`;
    elChange.className = netChange >= 0 ? 'text-success fw-bold' : 'text-danger fw-bold';

    // Sentiment
    document.getElementById('sentimentScore').textContent = `${(latest.sentiment_score ?? 0).toFixed(2)}%`;
    setSentimentBar(latest.sentiment_score || 0);

    // Last Update
    const d = new Date(latest.date);
    document.getElementById('lastUpdate').textContent = dateFmt.format(d);

    // Quick Analysis
    updateQuickAnalysis(latest);

    // Carica predizione AI
    try {
      const completeRes = await fetch(`/api/analysis/complete/${encodeURIComponent(symbol)}`);
      if (completeRes.ok) {
        const data = await completeRes.json();
        setAIPrediction(data.ml_prediction || null);
      }
    } catch (e) {
      console.warn('complete analysis unavailable:', e);
      setAIPrediction(null);
    }

  } catch (e) {
    console.error('Errore loadOverview:', e);
    updateOverviewElements('Errore', 'Errore', 'Errore', 0, null);
  }
}

function updateOverviewElements(netPos, sentiment, lastUpd, sentScore, prediction) {
  document.getElementById('netPosition').textContent = netPos;
  document.getElementById('sentimentScore').textContent = sentiment;
  document.getElementById('lastUpdate').textContent = lastUpd;
  setSentimentBar(sentScore);
  setAIPrediction(prediction);
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
  if (!box || !confEl) return;
  
  if (!mlPred) {
    box.innerHTML = `<span class="signal-box signal-neutral">IN ATTESA…</span>`;
    confEl.textContent = '—';
    return;
  }
  
  const dir = (mlPred.direction || 'NEUTRAL').toUpperCase();
  const conf = Math.round(mlPred.confidence || 50);
  const cls = dir === 'BULLISH' ? 'signal-bullish' : dir === 'BEARISH' ? 'signal-bearish' : 'signal-neutral';
  box.innerHTML = `<span class="signal-box ${cls}">${dir}</span>`;
  confEl.textContent = `${conf}`;
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

/* ========= COT ========= */
async function loadCotHistory(symbol, days = 30) {
  try {
    const res = await fetch(`/api/data/${encodeURIComponent(symbol)}?days=${days}`);
    if (!res.ok) throw new Error('cot history fetch failed');
    
    const rows = await res.json();

    // Aggiorna tabella
    const tbody = document.getElementById('cotDataTable');
    if (tbody) {
      tbody.innerHTML = '';
      rows.forEach(r => {
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
    const labels = [], ncLong = [], ncShort = [], cLong = [], cShort = [], net = [];
    rows.forEach(r => {
      const d = new Date(r.date);
      labels.push(dateFmt.format(d));
      ncLong.push(r.non_commercial_long);
      ncShort.push(r.non_commercial_short);
      cLong.push(r.commercial_long);
      cShort.push(r.commercial_short);
      net.push(r.net_position);
    });

    if (cotChart) {
      cotChart.data.labels = labels.reverse();
      cotChart.data.datasets[0].data = ncLong.reverse();
      cotChart.data.datasets[1].data = ncShort.reverse();
      cotChart.data.datasets[2].data = cLong.reverse();
      cotChart.data.datasets[3].data = cShort.reverse();
      cotChart.data.datasets[4].data = net.reverse();
      cotChart.update();
    }

    if (pieChart && rows[0]) {
      const last = rows[0];
      pieChart.data.datasets[0].data = [
        last.non_commercial_long, 
        last.non_commercial_short,
        last.commercial_long, 
        last.commercial_short
      ];
      pieChart.update();
    }

  } catch (e) {
    console.error('Errore loadCotHistory:', e);
    const tbody = document.getElementById('cotDataTable');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Errore caricamento dati COT</td></tr>';
    }
  }
}

/* ========= TECNICA ========= */
async function loadTechnical(symbol) {
  try {
    console.log(`🔧 Loading technical data for ${symbol}`);
    
    // Endpoint tecnico principale
    const res = await fetch(`/api/technical/${encodeURIComponent(symbol)}`);
    
    if (!res.ok) {
      console.warn(`Technical API failed for ${symbol}:`, res.status);
      renderTechnicalFallback(symbol);
      return;
    }

    const data = await res.json();
    console.log('📊 Technical data received:', data);

    // Se c'è un errore nei dati ma la risposta è OK
    if (data.error) {
      console.warn('Technical data error:', data.error);
      if (data.fallback) {
        renderTechnicalData(data.fallback);
      } else {
        renderTechnicalFallback(symbol);
      }
      return;
    }

    // Dati validi
    renderTechnicalData(data);

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
  
  // Grafico prezzi con livelli - FIX distruggi prima il vecchio
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
    </div>
    <div class="mt-3">
      <small class="text-muted">
        <i class="fas fa-info-circle"></i> 
        Fonte: ${data.source || 'unknown'} | 
        Qualità: ${data.data_quality || 'unknown'} |
        Aggiornato: ${new Date().toLocaleTimeString()}
      </small>
    </div>
  `;
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
    </div>
    <div class="mt-3">
      <small class="text-muted">
        Prezzo: ${(currentPrice || 0).toLocaleString('it-IT', {maximumFractionDigits: 2})}
      </small>
    </div>
  `;
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
          <small class="text-muted">Momentum</small>
        </div>
      </div>
      <div class="col-md-4">
        <div class="p-3 border rounded">
          <div class="text-muted small">SMA 50</div>
          <div class="h5 mb-0">${fmt(indicators.sma50)}</div>
          <small class="text-muted">Trend MT</small>
        </div>
      </div>
      <div class="col-md-4">
        <div class="p-3 border rounded">
          <div class="text-muted small">SMA 200</div>
          <div class="h5 mb-0">${fmt(indicators.sma200)}</div>
          <small class="text-muted">Trend LT</small>
        </div>
      </div>
      <div class="col-md-4">
        <div class="p-3 border rounded">
          <div class="text-muted small">MACD</div>
          <div class="h5 mb-0">${fmt(indicators.macd)}</div>
          <small class="text-muted">Divergenza</small>
        </div>
      </div>
      <div class="col-md-4">
        <div class="p-3 border rounded">
          <div class="text-muted small">ATR (14)</div>
          <div class="h5 mb-0">${fmt(indicators.atr14)}</div>
          <small class="text-muted">Volatilità</small>
        </div>
      </div>
      <div class="col-md-4">
        <div class="p-3 border rounded">
          <div class="text-muted small">Vol 20D</div>
          <div class="h5 mb-0">${fmt(indicators.volatility20, '%')}</div>
          <small class="text-muted">Range %</small>
        </div>
      </div>
    </div>
  `;
}

function updatePriceChart(data) {
  // IMPORTANTE: Distruggi il chart esistente prima di crearne uno nuovo
  if (priceChartInstance) {
    priceChartInstance.destroy();
    priceChartInstance = null;
  }
  
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
  
  document.getElementById('supportResistance').innerHTML = `
    <div class="text-center text-muted py-4">
      <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
      <div>Analisi tecnica non disponibile per ${symbol}</div>
      <small>Verifica la configurazione del Technical Analyzer</small>
    </div>`;
    
  document.getElementById('technicalSignals').innerHTML = `
    <div class="text-center">
      <span class="signal-box signal-neutral">NON DISPONIBILE</span>
      <div class="mt-2"><small class="text-muted">Segnali non disponibili</small></div>
    </div>`;
    
  document.getElementById('technicalIndicators').innerHTML = `
    <div class="text-center text-muted py-4">
      <div>Indicatori tecnici non disponibili</div>
    </div>`;
}

/* ========= ECONOMIA ========= */
async function loadEconomic() {
  const indEl = document.getElementById('economicIndicators');
  const fedEl = document.getElementById('fedWatch');
  const calEl = document.getElementById('economicCalendar');

  try {
    const [cur, cal] = await Promise.allSettled([
      fetch('/api/economic/current'),
      fetch('/api/economic/calendar')
    ]);

    // Current Economic Data
    if (cur.status === 'fulfilled' && cur.value.ok) {
      const data = await cur.value.json();
      if (indEl) indEl.innerHTML = renderEconomicIndicatorsHTML(data);
      if (fedEl) fedEl.innerHTML = renderFedWatchHTML(data);
    } else {
      if (indEl) indEl.innerHTML = '<div class="text-muted">Indicatori non disponibili</div>';
      if (fedEl) fedEl.innerHTML = '<div class="text-muted">Fed Watch non disponibile</div>';
    }

    // Economic Calendar
    if (cal.status === 'fulfilled' && cal.value.ok) {
      const c = await cal.value.json();
      if (calEl) {
        calEl.innerHTML =
          (c && Array.isArray(c.events) && c.events.length)
            ? renderEconomicCalendarHTML(c.events)
            : '<div class="text-muted">Nessun evento imminente</div>';
      }
    } else {
      if (calEl) calEl.innerHTML = '<div class="text-muted">Calendario non disponibile</div>';
    }
  } catch (e) {
    console.error('Errore loadEconomic:', e);
    if (indEl) indEl.innerHTML = '<div class="text-muted">Indicatori non disponibili</div>';
    if (fedEl) fedEl.innerHTML = '<div class="text-muted">Fed Watch non disponibile</div>';
    if (calEl) calEl.innerHTML = '<div class="text-muted">Calendario non disponibile</div>';
  }
}

/* ========= RENDER ECONOMIA (compat vecchio/nuovo schema) ========= */
function renderEconomicIndicatorsHTML(data) {
  const card = (lbl, val, suf='') => `
    <div class="col-md-4">
      <div class="p-3 border rounded">
        <div class="text-muted small">${lbl}</div>
        <div class="h5 mb-0">${val != null && val !== '' ? (+val).toFixed(2) + suf : '—'}</div>
        <small class="text-muted">Ultimo aggiornamento</small>
      </div>
    </div>`;

  // Nuovo schema (annidato in key_indicators)
  const k = data && data.key_indicators ? data.key_indicators : null;
  if (k) {
    const out = [];
    out.push(card('CPI YoY', k?.inflation_usa?.value, '%'));
    out.push(card('Disoccupazione', k?.unemployment_rate?.value, '%'));
    out.push(card('GDP QoQ', k?.gdp_qoq?.value, '%'));
    out.push(card('PMI', k?.pmi?.value, ''));
    out.push(card('Core PCE', k?.core_pce?.value, '%'));
    out.push(card('Fed Funds', k?.fed_funds_rate?.value, '%'));
    return `<div class="row g-3">${out.join('')}</div>`;
  }

  // Vecchio schema (campi piatti)
  const items = [
    { label: 'CPI YoY', key: 'cpi_yoy', suffix:'%' },
    { label: 'Disoccupazione', key: 'unemployment_rate', suffix:'%' },
    { label: 'GDP QoQ', key: 'gdp_qoq', suffix:'%' },
    { label: 'PMI', key: 'pmi', suffix:'' },
    { label: 'Core PCE', key: 'core_pce', suffix:'%' },
    { label: 'Retail Sales', key: 'retail_sales', suffix:'%' },
  ];
  return `<div class="row g-3">${
    items.map(it => card(it.label, data?.[it.key] ?? data?.[it.label] ?? null, it.suffix)).join('')
  }</div>`;
}

function renderFedWatchHTML(data) {
  const fw = data && (data.fed_watch || data.fedWatch);
  if (!fw) return '<div class="text-muted">Nessun dato disponibile</div>';

  // Vecchio formato: array di {rate, prob}
  if (Array.isArray(fw)) {
    const rows = fw.map(x => `
      <div class="d-flex justify-content-between align-items-center py-1 border-bottom">
        <div>${x.rate ?? '—'}</div>
        <strong>${x.prob != null ? (+x.prob).toFixed(1) + '%' : '—'}</strong>
      </div>`).join('');
    return `<div class="p-2">${rows}</div>`;
  }

  // Nuovo formato: oggetto (es. {september_cut_25bps: 62.0, ...})
  const mapping = [
    { label: 'Taglio 25 bps', value: fw.september_cut_25bps },
    { label: 'Taglio 50 bps', value: fw.september_cut_50bps },
  ];
  const rows = mapping.map(m => `
    <div class="d-flex justify-content-between align-items-center py-1 border-bottom">
      <div>${m.label}</div>
      <strong>${m.value != null ? (+m.value).toFixed(1) + '%' : '—'}</strong>
    </div>`).join('');
  return `<div class="p-2">${rows}</div>`;
}

function renderEconomicCalendarHTML(events) {
  const impClass = (imp) => {
    const v = (imp || '').toString().toLowerCase();
    if (v.startsWith('high')) return 'economic-event high-impact';
    if (v.startsWith('med'))  return 'economic-event medium-impact';
    return 'economic-event';
  };

  return (events || []).map(ev => {
    const title = ev.event || ev.name || 'Evento';
    const region = ev.country || ev.currency || ev.region || '—';
    const when   = ev.time || ev.datetime || ev.date || '';

    const rightCol = (ev.forecast != null || ev.previous != null || ev.actual != null)
      ? `
        <div class="text-end">
          <div class="small"><span class="text-muted">Atteso:</span> ${ev.forecast ?? '—'}</div>
          <div class="small"><span class="text-muted">Precedente:</span> ${ev.previous ?? '—'}</div>
          <div class="small"><span class="text-muted">Attuale:</span> <strong>${ev.actual ?? '—'}</strong></div>
        </div>`
      : `<div class="text-end small text-muted">${ev.description || ''}</div>`;

    return `
      <div class="${impClass(ev.impact)}">
        <div class="d-flex justify-content-between">
          <div>
            <strong>${title}</strong>
            <div class="small text-muted">${region} · ${when}</div>
          </div>
          ${rightCol}
        </div>
      </div>`;
  }).join('');
}


/* ========= PREVISIONI & ANALISI GPT ========= */
async function loadPredictions(symbol) {
  const table  = document.getElementById('predictionsTable');
  const gptBox = document.getElementById('gptAnalysis');
  // Verifica accesso
  if (!checkFeatureAccess('aiPredictions')) {
    if (gptBox) {
      gptBox.innerHTML = `
        <div class="alert alert-warning">
          <h5><i class="fas fa-lock"></i> Funzionalità Premium</h5>
          <p>Le previsioni AI sono disponibili solo con il piano <strong>Professional</strong>.</p>
          <a href="/pricing" class="btn btn-success mt-2">
            <i class="fas fa-rocket"></i> Upgrade a Professional
          </a>
        </div>`;
    }
    if (table) {
      table.innerHTML = `<tr><td colspan="7" class="text-center">Disponibile con piano Professional</td></tr>`;
    }
    return;
  }
  try {
    const [predRes, completeRes] = await Promise.allSettled([
      fetch(`/api/predictions/${encodeURIComponent(symbol)}`),
      fetch(`/api/analysis/complete/${encodeURIComponent(symbol)}`)
    ]);

    // --- Tabella previsioni ---
    let preds = [];
    if (predRes.status === 'fulfilled' && predRes.value.ok) {
      preds = await predRes.value.json();
      renderPredictionsTable(preds);
    } else if (table) {
      table.innerHTML =
        `<tr><td colspan="7" class="text-center text-muted py-4">Nessuna previsione disponibile</td></tr>`;
    }

    // --- Analisi GPT (box in alto) ---
    let gpt = null;

    if (completeRes.status === 'fulfilled' && completeRes.value.ok) {
      const comp = await completeRes.value.json();

      // 1) preferisci gpt_analysis diretto
      gpt = comp?.gpt_analysis
        // 2) oppure annidato dentro ml_prediction
        ?? comp?.ml_prediction?.gpt_analysis
        ?? null;

      // 3) se ancora nulla, prova a costruire un oggetto "gpt-like"
      if (!gpt && comp?.ml_prediction) {
        const mp = comp.ml_prediction;
        const direction  = (mp.direction || mp.predicted_direction || mp.signal || 'NEUTRAL');
        const confidence = mp.confidence ?? mp.confidence_pct ?? mp.probability ?? null;
        const reasoning  = mp.reasoning || mp.summary || mp.explanation || null;

        // Se c'è almeno una info utile, crea un fallback
        if (direction || confidence || reasoning) {
          gpt = {
            direction,
            confidence,
            reasoning,
            levels: mp.levels || mp.trade || undefined,
            risk_management: mp.risk_management || mp.risk || undefined
          };
        }
      }
    }

    // 4) fallback finale: prendi la prima riga delle predictions (se contiene gpt_analysis)
    if (!gpt && Array.isArray(preds) && preds.length) {
      gpt = preds[0]?.gpt_analysis ?? null;
    }

    // renderizza la box (anche se gpt è null -> messaggio "Nessuna analisi…")
    renderGptAnalysis(gptBox, gpt);

  } catch (e) {
    console.error('Errore loadPredictions:', e);
    if (table) {
      table.innerHTML =
        `<tr><td colspan="7" class="text-center text-danger py-4">Errore caricamento previsioni</td></tr>`;
    }
    renderGptAnalysis(gptBox, null);
  }
}

function renderPredictionsTable(preds) {
  const tbody = document.getElementById('predictionsTable');
  if (!tbody) return;

  if (!Array.isArray(preds) || !preds.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">Nessuna previsione disponibile</td></tr>`;
    return;
  }

  const toPct = (v) => {
    if (v == null || v === '') return null;
    const n = +v;
    if (!isFinite(n)) return null;
    // se è 0..1 lo tratto come frazione -> %
    return n <= 1 ? Math.round(n * 100) : Math.round(n);
  };

  const rows = preds.map(p => {
    const dateStr = p.prediction_date || p.created_at || p.timestamp || p.date || null;
    const d = dateStr ? new Date(dateStr) : null;

    const direction = (p.predicted_direction || p.direction || p.signal || 'NEUTRAL').toUpperCase();
    const confPct   = toPct(p.confidence ?? p.confidence_pct ?? p.probability ?? p.prob ?? null);
    const score     = (p.ml_score ?? p.model_score ?? p.score ?? p.ai_score);
    const accuracy  = toPct(p.accuracy ?? p.acc ?? p.current_accuracy ?? null);
    const status    = p.status || p.state || '—';
    const sym       = p.symbol || p.asset || '—';

    const sigCls = signalClass(direction);

    return `<tr>
      <td>${d ? dateFmt.format(d) : '—'}</td>
      <td>${sym}</td>
      <td><span class="signal-box ${sigCls}">${direction}</span></td>
      <td>${confPct != null ? confPct + '%' : '—'}</td>
      <td>${score != null ? (+score).toFixed(2) : '—'}</td>
      <td>${status}</td>
      <td>${accuracy != null ? accuracy + '%' : '—'}</td>
    </tr>`;
  }).join('');

  tbody.innerHTML = rows;
}

function renderGptAnalysis(container, gpt) {
  if (!container) return;

  if (!gpt) {
    container.innerHTML = `
      <div class="loading"><p class="mb-0">
        Nessuna analisi disponibile. Premi "Analisi AI" per generarne una.
      </p></div>`;
    return;
  }

  // accetta stringa JSON, stringa semplice o oggetto
  let obj;
  if (typeof gpt === 'string') {
    try { obj = JSON.parse(gpt); } catch { obj = { raw: gpt, text: gpt }; }
  } else { obj = gpt; }

  const toPct = (v) => {
    if (v == null || v === '') return null;
    const n = +v; if (!isFinite(n)) return null;
    return n <= 1 ? Math.round(n * 100) : Math.round(n);
  };

  const dir  = (obj.direction || obj.prediction || obj.signal || obj.bias || 'NEUTRAL').toUpperCase();
  const conf = toPct(obj.confidence ?? obj.confidence_pct ?? obj.confidence_percent ?? obj.prob ?? obj.probability);
  const reason =
    obj.market_outlook ||
    obj.reasoning || obj.summary || obj.explanation || obj.analysis ||
    obj.text || obj.comment || obj.note || null;

  const bullets = Array.isArray(obj.key_observations) && obj.key_observations.length
    ? '<ul class="gpt-list mb-0">' +
      obj.key_observations.map(x => `<li>${escapeHtml(String(x))}</li>`).join('') +
      '</ul>'
    : '';

  const risk   = obj.risk_management || obj.risk || obj.riskPlan || {};
  const levels = obj.levels || obj.trade || obj.setup || {};

  const chip =
    `<span class="signal-box gpt ${signalClass(dir)}">${dir}</span>`;

    container.innerHTML = `
    <div class="gpt-card">
      <div class="row g-3 align-items-stretch">
  
        <!-- Direzione -->
        <div class="col-12 col-lg-3">
          <div class="gpt-panel h-100 d-flex flex-column justify-content-center text-center">
            <div class="gpt-label mb-1">Direzione</div>
            <div class="mb-2">${chip}</div>
          </div>
        </div>
  
        <!-- Confidenza (gauge) -->
        <div class="col-6 col-lg-3">
          <div class="gpt-panel h-100 d-flex flex-column justify-content-center text-center">
            <div class="gpt-label mb-1">Confidenza</div>
            <div class="gpt-gauge mx-auto" style="--p:${conf != null ? conf : 0}">
              <div class="gpt-gauge-inner">${conf != null ? conf + '%' : '—'}</div>
            </div>
          </div>
        </div>
  
        <!-- Meta / chip -->
        <div class="col-6 col-lg-6">
          <div class="gpt-panel h-70">
            <div class="gpt-label mb-2">Meta</div>
            <div class="d-flex flex-wrap gap-2">
              ${obj.trading_bias ? `<span class="gpt-chip">Bias: ${escapeHtml(String(obj.trading_bias))}</span>` : ''}
              ${obj.risk_level   ? `<span class="gpt-chip">Rischio: ${escapeHtml(String(obj.risk_level))}</span>` : ''}
              ${obj.timeframe    ? `<span class="gpt-chip">TF: ${escapeHtml(String(obj.timeframe))}</span>` : ''}
              ${obj.model        ? `<span class="gpt-chip">Model: ${escapeHtml(String(obj.model))}</span>` : ''}
            </div>
          </div>
        </div>
  
        <!-- Sintesi a tutta larghezza -->
        <div class="col-12">
          <div class="gpt-panel">
            <div class="gpt-label">Sintesi</div>
            ${reason ? `<p class="mb-2">${escapeHtml(reason)}</p>` : '<div class="text-muted">—</div>'}
            ${bullets}
          </div>
        </div>
  
      </div>
    </div>`;
}


/* ========= STATO SISTEMA ========= */
async function loadSystemStatus() {
  try {
    const res = await fetch('/api/system/status');
    if (!res.ok) throw new Error('status fetch failed');
    const s = await res.json();

    // ci sono 4 card nell'HTML, aggiorno in ordine
    const cards = document.querySelectorAll('#systemStatusDetail .metric-card .metric-value');
    if (cards[0]) cards[0].textContent = (s.database && s.database.status) || (s.db_status || 'OK');
    if (cards[1]) cards[1].textContent = (s.openai && s.openai.status) || (s.openai_status || 'OK');
    if (cards[2]) cards[2].textContent = (s.ml && s.ml.status) || (s.ml_status || 'OK');
    if (cards[3]) cards[3].textContent = (s.selenium && s.selenium.status) || (s.selenium_status || 'OK');

    // badge header
    const badge = document.getElementById('systemStatus');
    if (badge) {
      const ok = !s.error;
      badge.className = 'badge ' + (ok ? 'bg-success' : 'bg-danger');
      badge.textContent = ok ? 'Sistema Online' : 'Sistema con errori';
    }
  } catch (e) {
    console.warn('Errore loadSystemStatus:', e);
  }
}

/* ========= MARKET OVERVIEW (robusto) ========= */
function parsePercent(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'number') {
    // se è una frazione 0..1 la trasformo in %
    return value <= 1 ? Math.round(value * 100) : Math.round(value);
  }
  if (typeof value === 'string') {
    // prendo la prima cifra, gestisco virgola europea e %
    const m = value.match(/-?\d+(?:[.,]\d+)?/);
    if (!m) return null;
    const n = parseFloat(m[0].replace(',', '.'));
    if (!isFinite(n)) return null;
    return n <= 1 ? Math.round(n * 100) : Math.round(n);
  }
  return null;
}

function parseRiskFlag(d) {
  // prova varie chiavi/valori comuni
  if (typeof d?.risk_on === 'boolean') return d.risk_on;
  const reg = (d?.risk_regime || d?.risk || '').toString().toLowerCase();
  if (reg.includes('on')) return true;
  if (reg.includes('off')) return false;
  return null;
}

async function loadMarketOverview() {
  const box = document.getElementById('marketOverview');
  if (!box) return;

  try {
    const res = await fetch('/api/economic/current');
    if (!res.ok) throw new Error('market overview failed');
    const data = await res.json();
    console.debug('[economic/current]', data); // utile per capire il payload reale

    // 1) Prova chiavi "note" e dentro key_indicators
    let sentimentPct =
      normalizePercent(data.market_sentiment) ??
      normalizePercent(data.sentiment) ??
      normalizePercent(pick(data, 'key_indicators.market_sentiment.value')) ??
      normalizePercent(pick(data, 'key_indicators.sentiment.value')) ??
      normalizePercent(deepFindByKey(data, 'sentiment'));

    let riskFlag =
      normalizeRiskFlag(data.risk_on) ??
      normalizeRiskFlag(data.risk) ??
      normalizeRiskFlag(data.risk_regime) ??
      normalizeRiskFlag(data.regime) ??
      normalizeRiskFlag(pick(data, 'key_indicators.risk_regime.value')) ??
      normalizeRiskFlag(deepFindByKey(data, 'risk'));

    // 2) Fallback: usa il sentiment dell'asset corrente se il backend non dà nulla
    if (sentimentPct == null) {
      try {
        const r2 = await fetch(`/api/data/${encodeURIComponent(currentSymbol)}?days=1`);
        if (r2.ok) {
          const rows = await r2.json();
          const s = rows?.[0]?.sentiment_score; // 98.38 ecc.
          const n = normalizePercent(s);
          if (n != null) sentimentPct = n;
        }
      } catch {}
    }

    // 3) Se manca il risk, deducilo dal sentiment
    if (riskFlag == null && sentimentPct != null) {
      if (sentimentPct >= 55) riskFlag = true;
      else if (sentimentPct <= 45) riskFlag = false;
      // 45–55 resta null → "—"
    }

    const sentimentHTML = sentimentPct != null ? sentimentPct + '%' : '—';
    const riskHTML = riskFlag === true ? 'Risk-ON' : riskFlag === false ? 'Risk-OFF' : '—';

    box.innerHTML = `
      <div class="row g-3">
        <div class="col-md-4">
          <div class="metric-card">
            <div class="metric-value">${sentimentHTML}</div>
            <div class="metric-label">Market Sentiment</div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="metric-card" style="background:linear-gradient(135deg,#34d399 0%, #10b981 100%)">
            <div class="metric-value">${riskHTML}</div>
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
    box.innerHTML = '<div class="text-muted">Panoramica non disponibile</div>';
  }
}

/* ========= ANALISI COMPLETA (SCRAPE + REFRESH) ========= */
async function runFullAnalysis(symbol) {
  // Solo admin può eseguire analisi manuale
  if (!userPlan.isAdmin) {
    showAlert('Funzionalità riservata agli amministratori', 'warning');
    return;
  }
  
  setLoading('#gptAnalysis', true, 'Esecuzione analisi AI in corso...');
  try {
    const res = await fetch(`/api/scrape/${encodeURIComponent(symbol)}`);
    if (!res.ok) throw new Error('scrape failed');

    const data = await res.json();

    // aggiorna subito la box GPT dalla risposta diretta
    if (data && data.gpt_analysis) {
      renderGptAnalysis(document.getElementById('gptAnalysis'), data.gpt_analysis);
    }

    // ricarica overview, predictions e tecnica
    await Promise.allSettled([
      loadOverview(symbol),
      loadPredictions(symbol),
      loadTechnical(symbol)
    ]);

    showAlert('Analisi AI completata', 'success');
  } catch (e) {
    console.error('Errore runFullAnalysis:', e);
    showAlert('Errore durante l\'analisi AI', 'danger');
    // fallback: ricarico comunque le predizioni (magari erano già presenti)
    await loadPredictions(symbol);
  } finally {
    setLoading('#gptAnalysis', false);
  }
}

/* ========= UTILITY ========= */
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

function setLoading(selector, on, text='Caricamento...') {
  const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
  if (!el) return;
  if (on) {
    el.setAttribute('data-prev', el.innerHTML);
    el.innerHTML = `
      <div class="loading">
        <div class="spinner-border text-primary"></div>
        <p class="mt-2">${text}</p>
      </div>`;
  } else {
    const prev = el.getAttribute('data-prev');
    if (prev != null) el.innerHTML = prev;
    el.removeAttribute('data-prev');
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
// Inizializza le tab quando il DOM è pronto
document.addEventListener('DOMContentLoaded', () => {
  // Attiva manualmente le tab di Bootstrap
  const triggerTabList = document.querySelectorAll('#mainTabs button[data-bs-toggle="tab"]');
  triggerTabList.forEach(triggerEl => {
    triggerEl.addEventListener('click', event => {
      event.preventDefault();
      // Usa l'API di Bootstrap 5 per attivare la tab
      const tab = new bootstrap.Tab(triggerEl);
      tab.show();
    });
  });
  
  console.log('✅ Tab Bootstrap inizializzate');
});