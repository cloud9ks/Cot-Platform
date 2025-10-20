"""
COT Analysis Platform - Sistema Completo FINALE
Piattaforma professionale per analisi e previsioni COT
"""

from flask import Flask, redirect, render_template, jsonify, request, send_from_directory, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_caching import Cache
from flask_login import LoginManager, login_required, current_user  # ✅ AGGIUNGI QUI
from functools import wraps
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from cache_manager import GLOBAL_CACHE, cached
import time
import os
import re
import json
import joblib
import logging
import warnings

warnings.filterwarnings('ignore')

from ml_system_fixed import COTPredictorFixed, create_production_predictor
from dotenv import load_dotenv
from models import db, User, init_db, SUBSCRIPTION_PLANS
from auth_routes import auth_bp
from decorators import subscription_context_processor
from analysis.gpt_analyzer import GPTAnalyzer
# Setup logging
logger = logging.getLogger(__name__)

# Istanza singleton globale GPT Analyzer
gpt_analyzer = GPTAnalyzer()
logger.info("✅ GPT Analyzer inizializzato")

load_dotenv()

# =================== CONFIGURAZIONE OTTIMIZZATA ===================
app = Flask(__name__)
CORS(app)

# Fix encoding Unicode per JSON responses
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'

# Session configuration
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# ⚡ DATABASE CONFIGURATION OTTIMIZZATA
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///cot_data.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False  # Disabilita log query

# 🚀 CONNECTION POOLING - CRITICO PER PERFORMANCE!
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,              # Connessioni base nel pool
    'max_overflow': 20,           # Connessioni extra se necessario
    'pool_timeout': 30,           # Timeout acquisizione connessione
    'pool_recycle': 3600,         # Ricicla connessioni dopo 1h
    'pool_pre_ping': True,        # Verifica connessione prima dell'uso
    'connect_args': {
        'connect_timeout': 10,
        'options': '-c statement_timeout=30000'  # Query timeout 30s
    }
}

# 💾 CACHE CONFIGURATION
app.config['CACHE_TYPE'] = 'simple'  # In-memory per ora
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minuti
app.config['CACHE_KEY_PREFIX'] = 'cot_'

# Inizializza cache
cache = Cache(app)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("cot_platform")

# Registra blueprint e context processor
app.register_blueprint(auth_bp)
app.context_processor(subscription_context_processor)

# Inizializza database
db.init_app(app)
scheduler = APScheduler()
# ==========================================
# OTTIMIZZAZIONI PERFORMANCE
# ==========================================

from threading import Lock
from collections import defaultdict
import time

class RequestCoalescer:
    """Unisce richieste duplicate simultanee"""
    def __init__(self):
        self._locks = defaultdict(Lock)
        self._results = {}
        self._timestamps = {}
        self._result_ttl = 2
    
    def get_or_execute(self, key, func, *args, **kwargs):
        lock = self._locks[key]
        
        if key in self._results:
            result, timestamp = self._results[key], self._timestamps[key]
            age = (time.time() - timestamp)
            if age < self._result_ttl:
                logger.info(f"🔄 Coalesced: {key}")
                return result
        
        with lock:
            if key in self._results:
                result, timestamp = self._results[key], self._timestamps[key]
                age = (time.time() - timestamp)
                if age < self._result_ttl:
                    return result
            
            logger.info(f"▶️ Executing: {key}")
            start = time.time()
            result = func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            
            self._results[key] = result
            self._timestamps[key] = time.time()
            
            logger.info(f"✅ Done: {key} ({duration:.0f}ms)")
            return result

def get_smart_cache_timeout():
    """Cache più lunga quando COT non si aggiorna"""
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    
    if weekday == 1 and hour >= 20:  # Martedì sera
        return 3600  # 1 ora
    if weekday == 2 and hour < 12:  # Mercoledì mattina
        return 7200  # 2 ore
    return 86400  # 24 ore altri giorni

def smart_cache_response(key_prefix):
    """Decorator con cache intelligente + coalescing"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{f.__name__}:{':'.join(map(str, args))}"
            
            # Check cache
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"✅ Cache HIT: {cache_key}")
                return jsonify(cached)
            
            # Execute with coalescing
            def execute():
                result = f(*args, **kwargs)
                # Estrai dati da jsonify se necessario
                if hasattr(result, 'get_json'):
                    data = result.get_json()
                elif isinstance(result, tuple):
                    data = result[0].get_json() if hasattr(result[0], 'get_json') else result[0]
                else:
                    data = result
                
                timeout = get_smart_cache_timeout()
                cache.set(cache_key, data, timeout=timeout)
                logger.info(f"💾 Cached {cache_key} (TTL: {timeout}s)")
                return result
            
            return coalescer.get_or_execute(cache_key, execute)
        return wrapper
    return decorator

# Istanza globale
coalescer = RequestCoalescer()
logger.info("✅ Request Coalescer inizializzato")

# =================== MIDDLEWARE PER PERFORMANCE MONITORING ===================
@app.before_request
def before_request():
    """Traccia tempo di esecuzione richieste"""
    g.request_start_time = time.time()

@app.after_request
def after_request(response):
    """Log richieste lente e aggiungi headers"""
    if hasattr(g, 'request_start_time'):
        elapsed = (time.time() - g.request_start_time) * 1000
        
        # Log richieste lente (> 1 secondo)
        if elapsed > 1000:
            logger.warning(
                f"⚠️ SLOW REQUEST: {request.method} {request.path} "
                f"took {elapsed:.2f}ms"
            )
        
        # Aggiungi header X-Response-Time per debugging
        response.headers['X-Response-Time'] = f"{elapsed:.2f}ms"
    
    return response

# =================== DECORATORE CACHE ===================
def cache_response(timeout=300, key_prefix=None):
    """
    Decorator per cachare risposte API
    
    Usage:
        @cache_response(timeout=600, key_prefix='cot_history')
        def get_cot_history(symbol):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Crea cache key unica basata su funzione e argomenti
            cache_key = f"{key_prefix or f.__name__}:{':'.join(map(str, args))}"
            
            # Prova a prendere dalla cache
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"✅ Cache HIT: {cache_key}")
                return cached
            
            # Esegui funzione e cachea risultato
            logger.debug(f"❌ Cache MISS: {cache_key}")
            result = f(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            return result
        
        return decorated_function
    return decorator


# Setup Flask-Login
from flask_login import LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login_page'
login_manager.session_protection = 'strong'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    if request.is_json:
        return jsonify({'error': 'Login richiesto'}), 401
    return redirect('/login')

class COTData(db.Model):
    __tablename__ = 'cot_data'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    date = db.Column(db.DateTime, nullable=False, index=True)
    non_commercial_long = db.Column(db.Integer)
    non_commercial_short = db.Column(db.Integer)
    non_commercial_spreads = db.Column(db.Integer)
    commercial_long = db.Column(db.Integer)
    commercial_short = db.Column(db.Integer)
    net_position = db.Column(db.Integer)
    sentiment_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Prediction(db.Model):
    __tablename__ = 'predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    prediction_date = db.Column(db.DateTime, nullable=False)
    predicted_direction = db.Column(db.String(20))
    confidence = db.Column(db.Float)
    ml_score = db.Column(db.Float)
    gpt_analysis = db.Column(db.Text)
    actual_result = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =================== FUNZIONI DATABASE OTTIMIZZATE ===================
def get_cot_history_optimized(symbol, limit=100):
    """
    Query COT ottimizzata con limit esplicito
    """
    try:
        return (
            COTData.query
            .filter_by(symbol=symbol)
            .order_by(COTData.date.desc())
            .limit(limit)
            .all()
        )
    except Exception as e:
        logger.error(f"Errore query COT: {e}")
        return []

def get_latest_data_batch(symbols):
    """
    Recupera dati più recenti per più simboli in UNA query
    """
    from sqlalchemy import func
    
    try:
        # Subquery per trovare date più recenti
        subq = (
            db.session.query(
                COTData.symbol,
                func.max(COTData.date).label('max_date')
            )
            .filter(COTData.symbol.in_(symbols))
            .group_by(COTData.symbol)
            .subquery()
        )
        
        # Join per record completi
        results = (
            db.session.query(COTData)
            .join(
                subq,
                db.and_(
                    COTData.symbol == subq.c.symbol,
                    COTData.date == subq.c.max_date
                )
            )
            .all()
        )
        
        return {r.symbol: r for r in results}
    
    except Exception as e:
        logger.error(f"Errore batch query: {e}")
        return {}
    
    
# =================== CONFIGURAZIONE SIMBOLI COT ===================
COT_SYMBOLS = {
    'GOLD': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/088691',
        'name': 'Gold',
        'code': '088691'
    },
    'USD': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/098662',
        'name': 'US Dollar Index',
        'code': '098662'
    },
    'EUR': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/099741',
        'name': 'Euro FX',
        'code': '099741'
    },
    'GBP': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/096742',
        'name': 'British Pound',
        'code': '096742'
    },
    'JPY': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/097741',
        'name': 'Japanese Yen',
        'code': '097741'
    },
    'CHF': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/092741',
        'name': 'Swiss Franc',
        'code': '092741'
    },
    'CAD': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/090741',
        'name': 'Canadian Dollar',
        'code': '090741'
    },
    'AUD': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/232741',
        'name': 'Australian Dollar',
        'code': '232741'
    },
    'SILVER': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/084691',
        'name': 'Silver',
        'code': '084691'
    },
    'OIL': {
        'url': 'https://www.tradingster.com/cot/legacy-futures/067651',
        'name': 'Crude Oil',
        'code': '067651'
    }
}

# =================== FUNZIONI SCRAPING COT ===================
def calculate_cot_sentiment(nc_long, nc_short, c_long, c_short):
    """
    Calcola sentiment COT migliorato
    I non-commercial sono i 'smart money' - peso maggiore
    I commercial sono gli hedger - comportamento opposto
    """
    
    # Net position dei non-commercial (gli speculatori intelligenti)
    nc_net = nc_long - nc_short
    
    # Net position dei commercial (opposite sentiment)
    c_net = c_long - c_short
    
    # Total Open Interest
    total_oi = nc_long + nc_short + c_long + c_short
    
    if total_oi == 0:
        return 0
    
    # I non-commercial guidano il sentiment (peso 70%)
    # I commercial sono contrarian (peso 30%, invertito)
    nc_weight = 0.7
    c_weight = 0.3
    
    # Normalizza rispetto al total OI
    nc_sentiment = (nc_net / total_oi) * 100 * nc_weight
    c_sentiment = -(c_net / total_oi) * 100 * c_weight  # Nota il segno meno
    
    # Sentiment finale
    final_sentiment = nc_sentiment + c_sentiment
    
    # Amplifica per rendere pi sensibile (moltiplica per 3)
    final_sentiment *= 3
    
    # Limita tra -100 e +100
    final_sentiment = max(-100, min(100, final_sentiment))
    
    return round(final_sentiment, 2)

try:
    from technical_analyzer import (
        TechnicalAnalyzer, 
        analyze_symbol_complete,
        get_symbol_technical_data, 
        get_economic_events, 
        get_market_sentiment,
        get_technical_signals
    )
    TECHNICAL_ANALYZER_AVAILABLE = True
    logger.info("✅ Technical Analyzer importato correttamente")
except ImportError as e:
    TECHNICAL_ANALYZER_AVAILABLE = False
    logger.warning(f"⚠️ Technical Analyzer non disponibile: {e}")



def scrape_cot_data(symbol):
    """Scraping dati COT per un simbolo specifico - VERSIONE CORRETTA CON LOCK"""
    
    # Importa threading per gestire concorrenza
    import threading
    
    # Lock globale per evitare scraping concorrenti
    if not hasattr(scrape_cot_data, 'lock'):
        scrape_cot_data.lock = threading.Lock()
    
    # Acquisisci lock - una sola istanza di scraping alla volta
    with scrape_cot_data.lock:
        try:
            # Importa il nuovo scraper
            from collectors.cot_scraper import COTScraper
            
            logger.info(f"🔄 Avvio scraping per {symbol}...")
            
            # Usa il nuovo scraper con context manager (chiude automaticamente)
            with COTScraper(headless=True) as scraper:
                data = scraper.scrape_cot_data(symbol)
                
                # Se il scraper ha successo, ricalcola il sentiment
                if data:
                    data['sentiment_score'] = calculate_cot_sentiment(
                        data['non_commercial_long'],
                        data['non_commercial_short'], 
                        data['commercial_long'],
                        data['commercial_short']
                    )
                    logger.info(f"✅ Sentiment ricalcolato per {symbol}: {data['sentiment_score']:.2f}%")
                else:
                    logger.warning(f"⚠️ Scraper ha ritornato None per {symbol}")
                
                return data
                
        except ImportError as e:
            logger.error(f"❌ Modulo COTScraper non trovato: {e}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Errore generale scraping {symbol}: {str(e)}")
            return None

# =================== MACHINE LEARNING PREDICTIONS ===================
class COTPredictorFixed:
    """Sistema ML corretto per predizioni COT"""
    
    def __init__(self):
        """Inizializza il predictor con gestione errori robusta"""
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.ml_available = False
        self.features_columns = None
        self.last_training_data_size = 0
        self.accuracy_history = []
        
        # Tenta inizializzazione ML
        self._init_ml_components()
    
    def _init_ml_components(self):
        """Inizializza componenti ML con gestione errori"""
        try:
            # Test import numpy
            import numpy as np
            numpy_version = np.__version__
            logger.info(f"NumPy version: {numpy_version}")
            
            # Test import scikit-learn
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_squared_error, r2_score
            import sklearn
            
            sklearn_version = sklearn.__version__
            logger.info(f"Scikit-learn version: {sklearn_version}")
            
            # Inizializza modelli
            self.model = RandomForestRegressor(
                n_estimators=50,  # Ridotto per performance
                max_depth=10,     # Evita overfitting
                random_state=42,
                n_jobs=1          # Single thread per stabilit 
            )
            self.scaler = StandardScaler()
            self.ml_available = True
            
            logger.info(" ML components inizializzati correttamente")
            
        except ImportError as e:
            logger.warning(f"  ML libraries non disponibili: {e}")
            logger.info(" Per attivare ML: pip install scikit-learn==1.3.0 numpy==1.24.3")
            self.ml_available = False
            
        except Exception as e:
            logger.error(f" Errore inizializzazione ML: {e}")
            self.ml_available = False
    
    def prepare_features(self, data_point):
        """Prepara features per ML con validazione robusta"""
        if not self.ml_available:
            return None
        
        try:
            # Estrai features base
            features = []
            
            # Features principali COT
            nc_long = float(data_point.get('non_commercial_long', 0))
            nc_short = float(data_point.get('non_commercial_short', 0))
            c_long = float(data_point.get('commercial_long', 0))
            c_short = float(data_point.get('commercial_short', 0))
            net_pos = float(data_point.get('net_position', 0))
            sentiment = float(data_point.get('sentiment_score', 0))
            
            # Features derivate
            nc_ratio = nc_long / (nc_short + 1)  # Evita divisione per zero
            c_ratio = c_long / (c_short + 1)
            total_long = nc_long + c_long
            total_short = nc_short + c_short
            total_oi = total_long + total_short
            
            # Features normalizzate
            if total_oi > 0:
                nc_long_pct = nc_long / total_oi
                nc_short_pct = nc_short / total_oi
                c_long_pct = c_long / total_oi
                c_short_pct = c_short / total_oi
            else:
                nc_long_pct = nc_short_pct = c_long_pct = c_short_pct = 0.25
            
            # Assembla feature vector
            features = [
                nc_long, nc_short, c_long, c_short,  # Raw values
                net_pos, sentiment,                    # Derived values
                nc_ratio, c_ratio,                     # Ratios
                total_oi,                              # Total OI
                nc_long_pct, nc_short_pct, c_long_pct, c_short_pct,  # Percentages
                abs(net_pos), abs(sentiment)           # Absolute values
            ]
            
            # Validazione features
            features = [float(f) if not np.isnan(f) and not np.isinf(f) else 0.0 for f in features]
            
            return np.array(features).reshape(1, -1)
            
        except Exception as e:
            logger.error(f"Errore preparazione features: {e}")
            return None
    
    def train(self, historical_data):
        """Training del modello con validazione robusta"""
        if not self.ml_available:
            logger.info("ML non disponibile - training saltato")
            return False
        
        if not historical_data or len(historical_data) < 3:
            logger.info(f"Dati insufficienti per training: {len(historical_data) if historical_data else 0} < 3")
            return False
        
        try:
            X = []
            y = []
            
            logger.info(f"Inizio training con {len(historical_data)} data points...")
            
            # Prepara dataset
            for i in range(len(historical_data) - 1):
                current_data = historical_data[i]
                next_data = historical_data[i + 1]
                
                # Prepara features
                features = self.prepare_features(current_data)
                if features is None:
                    continue
                
                # Target: cambiamento nel sentiment score
                current_sentiment = float(current_data.get('sentiment_score', 0))
                next_sentiment = float(next_data.get('sentiment_score', 0))
                target = next_sentiment - current_sentiment
                
                # Validazione target
                if np.isnan(target) or np.isinf(target):
                    continue
                
                X.append(features[0])
                y.append(target)
            
            if len(X) < 2:
                logger.warning(f"Features valide insufficienti: {len(X)} < 2")
                return False
            
            X = np.array(X)
            y = np.array(y)
            
            logger.info(f"Dataset preparato: X shape={X.shape}, y shape={y.shape}")
            
            # Training
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            self.is_trained = True
            self.last_training_data_size = len(X)
            
            # Calcola accuracy sul training set
            y_pred = self.model.predict(X_scaled)
            mse = np.mean((y - y_pred) ** 2)
            mae = np.mean(np.abs(y - y_pred))
            
            # Score di accuratezza personalizzato
            accuracy_score = max(0, min(100, 100 - (mae * 10)))  # Converte MAE in percentuale
            self.accuracy_history.append(accuracy_score)
            
            logger.info(f" Training completato!")
            logger.info(f"   Samples: {len(X)}")
            logger.info(f"   MSE: {mse:.3f}")
            logger.info(f"   MAE: {mae:.3f}")
            logger.info(f"   Accuracy: {accuracy_score:.1f}%")
            
            return True
            
        except Exception as e:
            logger.error(f" Errore durante training: {e}")
            logger.error(f"   Tipo errore: {type(e).__name__}")
            self.is_trained = False
            return False
    
    def predict(self, current_data):
        """Predizione con fallback intelligente"""
        if not self.ml_available or not self.is_trained:
            logger.info("ML non disponibile - usando predizione fallback")
            return self._fallback_prediction(current_data)
        
        try:
            # Prepara features
            features = self.prepare_features(current_data)
            if features is None:
                return self._fallback_prediction(current_data)
            
            # Predizione
            features_scaled = self.scaler.transform(features)
            prediction = self.model.predict(features_scaled)[0]
            
            # Converti in direzione e confidenza
            direction, confidence = self._interpret_prediction(prediction, current_data)
            
            result = {
                'direction': direction,
                'confidence': confidence,
                'score': float(prediction),
                'method': 'machine_learning',
                'model_accuracy': self._get_current_accuracy(),
                'training_size': self.last_training_data_size
            }
            
            logger.info(f" ML Prediction: {direction} (confidence: {confidence:.0f}%, score: {prediction:.3f})")
            return result
            
        except Exception as e:
            logger.error(f" Errore predizione ML: {e}")
            return self._fallback_prediction(current_data)
    
    def _interpret_prediction(self, prediction_score, current_data):
        """Interpreta il score di predizione in direzione e confidenza"""
        
        # Ottieni context dal dato corrente
        current_sentiment = current_data.get('sentiment_score', 0)
        net_position = current_data.get('net_position', 0)
        
        # Soglie dinamiche basate sul contesto
        base_threshold = 2.0
        
        # Aggiusta soglie in base al sentiment corrente
        if abs(current_sentiment) > 30:  # Sentiment estremo
            threshold_multiplier = 0.7  # Soglie pi basse
        elif abs(current_sentiment) < 10:  # Sentiment neutro
            threshold_multiplier = 1.3  # Soglie pi alte
        else:
            threshold_multiplier = 1.0
        
        adjusted_threshold = base_threshold * threshold_multiplier
        
        # Determina direzione
        if prediction_score > adjusted_threshold:
            direction = "BULLISH"
            confidence = min(abs(prediction_score) * 20, 90)
        elif prediction_score < -adjusted_threshold:
            direction = "BEARISH"
            confidence = min(abs(prediction_score) * 20, 90)
        else:
            direction = "NEUTRAL"
            confidence = 50 + min(abs(prediction_score) * 10, 20)
        
        # Boost confidenza se allineato con sentiment
        if (direction == "BULLISH" and current_sentiment > 0) or \
           (direction == "BEARISH" and current_sentiment < 0):
            confidence = min(confidence * 1.1, 95)
        
        return direction, confidence
    
    def _fallback_prediction(self, current_data):
        """Predizione di fallback quando ML non  disponibile"""
        
        try:
            # Usa logica basata su regole
            sentiment_score = current_data.get('sentiment_score', 0)
            net_position = current_data.get('net_position', 0)
            nc_long = current_data.get('non_commercial_long', 0)
            nc_short = current_data.get('non_commercial_short', 0)
            
            # Calcola indicatori semplici
            nc_ratio = nc_long / (nc_short + 1)
            
            # Logica di predizione
            if sentiment_score > 25 or (net_position > 100000 and nc_ratio > 1.5):
                direction = "BULLISH"
                confidence = min(70 + abs(sentiment_score) * 0.5, 85)
            elif sentiment_score < -25 or (net_position < -100000 and nc_ratio < 0.7):
                direction = "BEARISH"
                confidence = min(70 + abs(sentiment_score) * 0.5, 85)
            elif sentiment_score > 10:
                direction = "BULLISH"
                confidence = min(60 + abs(sentiment_score), 75)
            elif sentiment_score < -10:
                direction = "BEARISH"
                confidence = min(60 + abs(sentiment_score), 75)
            else:
                direction = "NEUTRAL"
                confidence = 50
            
            return {
                'direction': direction,
                'confidence': confidence,
                'score': sentiment_score / 10,  # Normalizza
                'method': 'rule_based_fallback',
                'note': 'Predizione basata su regole - ML non disponibile'
            }
            
        except Exception as e:
            logger.error(f"Errore fallback prediction: {e}")
            return {
                'direction': 'NEUTRAL',
                'confidence': 50,
                'score': 0,
                'method': 'emergency_fallback',
                'error': str(e)
            }
    
    def _get_current_accuracy(self):
        """Ottieni accuratezza corrente"""
        if not self.accuracy_history:
            return 0.0
        return self.accuracy_history[-1]
    
    def get_model_info(self):
        """Informazioni dettagliate sul modello"""
        return {
            'ml_available': self.ml_available,
            'is_trained': self.is_trained,
            'training_data_size': self.last_training_data_size,
            'current_accuracy': self._get_current_accuracy(),
            'accuracy_history': self.accuracy_history[-5:],  # Ultimi 5
            'model_type': 'RandomForestRegressor' if self.ml_available else 'None',
            'features_count': 14,  # Numero di features
            'sklearn_available': self.ml_available
        }
    
    def retrain_if_needed(self, new_data_size):
        """Re-training automatico se necessario"""
        if not self.is_trained:
            return False
        
        # Re-train se i dati sono aumentati significativamente
        if new_data_size > self.last_training_data_size * 1.5:
            logger.info(f"Auto re-training: {new_data_size} > {self.last_training_data_size * 1.5}")
            return True
        
        return False


# =================== FUNZIONI HELPER ===================

def test_ml_system():
    """Test completo del sistema ML"""
    print(" TEST SISTEMA ML CORRETTO")
    print("=" * 60)
    
    # Inizializza predictor
    predictor = COTPredictorFixed()
    
    # Test 1: Verifica disponibilit 
    print("\n1 Verifica Componenti...")
    model_info = predictor.get_model_info()
    print(f"   ML disponibile: {model_info['ml_available']}")
    print(f"   Modello: {model_info['model_type']}")
    
    # Test 2: Genera dati di training
    print("\n2 Generazione Dati Training...")
    training_data = generate_test_data(20)  # 20 settimane di dati
    print(f"   Dati generati: {len(training_data)} record")
    
    # Test 3: Training
    print("\n3 Training Modello...")
    training_success = predictor.train(training_data)
    print(f"   Training: {' Riuscito' if training_success else ' Fallito'}")
    
    if training_success:
        model_info = predictor.get_model_info()
        print(f"   Accuratezza: {model_info['current_accuracy']:.1f}%")
        print(f"   Dati training: {model_info['training_data_size']}")
    
    # Test 4: Predizioni
    print("\n4 Test Predizioni...")
    test_scenarios = [
        {
            'name': 'Bullish Scenario',
            'data': {
                'non_commercial_long': 300000,
                'non_commercial_short': 100000,
                'commercial_long': 120000,
                'commercial_short': 220000,
                'net_position': 200000,
                'sentiment_score': 35.0
            }
        },
        {
            'name': 'Bearish Scenario',
            'data': {
                'non_commercial_long': 80000,
                'non_commercial_short': 280000,
                'commercial_long': 250000,
                'commercial_short': 150000,
                'net_position': -200000,
                'sentiment_score': -30.0
            }
        },
        {
            'name': 'Neutral Scenario',
            'data': {
                'non_commercial_long': 180000,
                'non_commercial_short': 170000,
                'commercial_long': 160000,
                'commercial_short': 170000,
                'net_position': 10000,
                'sentiment_score': 2.0
            }
        }
    ]
    
    for scenario in test_scenarios:
        prediction = predictor.predict(scenario['data'])
        print(f"   {scenario['name']}: {prediction['direction']} ({prediction['confidence']:.0f}%) - {prediction['method']}")
    
    # Test 5: Model Info
    print("\n5 Informazioni Modello...")
    info = predictor.get_model_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
    
    print(f"\n" + "=" * 60)
    print(f" Test completato! ML Status: {' FUNZIONANTE' if predictor.is_trained else '  FALLBACK MODE'}")
    
    return predictor

def generate_test_data(num_weeks):
    """Genera dati di test realistici"""
    data = []
    base_date = datetime.now() - timedelta(weeks=num_weeks)
    
    for i in range(num_weeks):
        # Simula trend con rumore
        trend = i * 500  # Trend crescente
        noise = np.random.normal(0, 5000)
        
        net_pos = 50000 + trend + noise
        nc_long = 200000 + trend//2 + np.random.normal(0, 10000)
        nc_short = nc_long - net_pos + np.random.normal(0, 5000)
        c_long = 150000 - trend//3 + np.random.normal(0, 8000)
        c_short = c_long + net_pos//2 + np.random.normal(0, 5000)
        
        # Assicura valori positivi
        nc_long = max(10000, nc_long)
        nc_short = max(10000, nc_short)
        c_long = max(10000, c_long)
        c_short = max(10000, c_short)
        
        # Calcola sentiment
        total_long = nc_long + c_long
        total_short = nc_short + c_short
        sentiment = ((total_long - total_short) / (total_long + total_short)) * 100
        
        data_point = {
            'date': base_date + timedelta(weeks=i),
            'non_commercial_long': int(nc_long),
            'non_commercial_short': int(nc_short),
            'commercial_long': int(c_long),
            'commercial_short': int(c_short),
            'net_position': int(net_pos),
            'sentiment_score': sentiment
        }
        
        data.append(data_point)
    
    return data

def create_production_predictor():
    """Crea predictor per produzione - USA QUESTA FUNZIONE"""
    return COTPredictorFixed()


if __name__ == "__main__":
    # Test del sistema
    predictor = test_ml_system()
    
    print(f"\n Per integrare nel tuo app:")
    print(f"1. Sostituisci la classe COTPredictor con COTPredictorFixed")
    print(f"2. Il sistema funziona con o senza scikit-learn")
    print(f"3. Fallback automatico se ML non disponibile")
    print(f"4. Gestione errori robusta")

# Inizializza predictor
predictor = create_production_predictor()
@app.route('/api/technical/<symbol>')
@smart_cache_response('technical')
@cached(category='technical', ttl=300)  # Cache 5 minuti
def get_technical_analysis(symbol):
    """Analisi tecnica completa per un simbolo"""
    try:
        if symbol not in COT_SYMBOLS:
            return jsonify({'error': 'Simbolo non valido'}), 400
        
        if not TECHNICAL_ANALYZER_AVAILABLE:
            return jsonify({
                'error': 'Technical Analyzer non disponibile',
                'fallback': create_fallback_technical_analysis(symbol)
            }), 503
        
        # Ottieni analisi tecnica completa
        analysis = get_symbol_technical_data(symbol)
        
        # Arricchisci con segnali
        signals = get_technical_signals(symbol)
        analysis['signals'] = signals
        
        # Aggiungi timestamp
        analysis['api_timestamp'] = datetime.now().isoformat()
        
        return jsonify(analysis)
        
    except Exception as e:
        logger.error(f"Errore analisi tecnica {symbol}: {str(e)}")
        return jsonify({
            'error': str(e),
            'fallback': create_fallback_technical_analysis(symbol)
        }), 500

@app.route('/api/economic/current')
@cached(category='economic', ttl=1800)  # Cache 30 minuti
def get_current_economic_data():
    """Dati economici attuali con sentiment"""
    try:
        if not TECHNICAL_ANALYZER_AVAILABLE:
            return jsonify(create_fallback_economic_data()), 503
        
        # Ottieni sentiment di mercato
        market_data = get_market_sentiment()
        
        # Combina con dati economici simulati
        economic_data = {
            'timestamp': datetime.now().isoformat(),
            'market_sentiment': market_data,
            'key_indicators': {
                'inflation_usa': {
                    'value': 2.7,
                    'change': -0.3,
                    'trend': 'DECLINING',
                    'impact_gold': 'POSITIVE'
                },
                'fed_funds_rate': {
                    'value': 4.50,
                    'probability_cut_25bps': 87,
                    'next_meeting': '2024-09-18',
                    'impact_gold': 'POSITIVE'
                },
                'dollar_index': {
                    'value': 103.45,
                    'change': -0.12,
                    'trend': 'WEAKENING',
                    'impact_gold': 'POSITIVE'
                }
            },
            'fed_watch': {
                'september_cut_25bps': 87,
                'september_cut_50bps': 13,
                'market_pricing': 'Taglio tassi quasi certo'
            }
        }
        
        return jsonify(economic_data)
        
    except Exception as e:
        logger.error(f"Errore dati economici: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/economic/calendar')
@cached(category='economic', ttl=1800)  # Cache 30 minuti
def get_economic_calendar_api():
    """Calendario economico eventi importanti"""
    try:
        if not TECHNICAL_ANALYZER_AVAILABLE:
            return jsonify({
                'events': create_fallback_calendar(),
                'source': 'fallback'
            })
        
        events = get_economic_events()
        
        return jsonify({
            'events': events,
            'timestamp': datetime.now().isoformat(),
            'source': 'technical_analyzer',
            'count': len(events)
        })
        
    except Exception as e:
        logger.error(f"Errore calendario economico: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/synthesis/<symbol>')
@smart_cache_response('synthesis')
@cached(category='synthesis', ttl=600)  # <-- AGGIUNGI QUESTA RIGA
def get_cot_synthesis(symbol):
    """Sintesi COT + Tecnica per un simbolo"""
    try:
        if symbol not in COT_SYMBOLS:
            return jsonify({'error': 'Simbolo non valido'}), 400
        
        # Ottieni dati COT pi recenti
        latest_cot = COTData.query.filter_by(symbol=symbol)\
            .order_by(COTData.date.desc()).first()
        
        if not latest_cot:
            return jsonify({'error': 'Nessun dato COT disponibile'}), 404
        
        # Calcola metriche COT
        nc_net = latest_cot.non_commercial_long - latest_cot.non_commercial_short
        c_net = latest_cot.commercial_long - latest_cot.commercial_short
        
        # Ottieni analisi tecnica se disponibile
        technical_data = {}
        if TECHNICAL_ANALYZER_AVAILABLE:
            try:
                technical_data = get_symbol_technical_data(symbol)
                signals_data = get_technical_signals(symbol)
                technical_data['signals'] = signals_data
            except Exception as e:
                logger.warning(f"Errore technical data: {e}")
                technical_data = create_fallback_technical_analysis(symbol)
        else:
            technical_data = create_fallback_technical_analysis(symbol)
        
        # Sintesi combinata
        synthesis = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'cot_summary': {
                'large_spec_net': nc_net,
                'commercial_net': c_net,
                'open_interest_delta': calculate_oi_delta(symbol),
                'sentiment_score': latest_cot.sentiment_score,
                'net_position': latest_cot.net_position,
                'last_update': latest_cot.date.isoformat()
            },
            'technical_summary': {
                'current_price': technical_data.get('current_price', 0),
                'strong_resistance': technical_data.get('strong_resistance', 0),
                'strong_support': technical_data.get('strong_support', 0),
                'trend_bias': technical_data.get('trend_bias', 'NEUTRAL'),
                'price_position': technical_data.get('price_position', 'UNKNOWN')
            },
            'combined_signals': {
                'cot_signal': determine_cot_signal(latest_cot),
                'technical_signal': technical_data.get('signals', {}).get('overall', {}).get('signal', 'NEUTRAL'),
                'combined_bias': combine_signals(latest_cot, technical_data)
            },
            'market_regime': determine_market_regime_synthesis(latest_cot, technical_data)
        }
        
        return jsonify(synthesis)
        
    except Exception as e:
        logger.error(f"Errore sintesi {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis/complete/<symbol>')
@smart_cache_response('complete_analysis')
@cached(category='complete', ttl=600)  # Cache 10 minuti
def get_complete_analysis(symbol):
    """Analisi completa: COT + Tecnica + AI + ML"""
    try:
        if symbol not in COT_SYMBOLS:
            return jsonify({'error': 'Simbolo non valido'}), 400
        
        # Risultato finale
        complete_analysis = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'status': 'SUCCESS'
        }
        
        # 1. Dati COT
        latest_cot = COTData.query.filter_by(symbol=symbol)\
            .order_by(COTData.date.desc()).first()
        
        if latest_cot:
            try:
                gpt_input = {
                    'symbol': symbol,
                    'date': latest_cot.date.isoformat(),
                    'non_commercial_long': latest_cot.non_commercial_long,
                    'non_commercial_short': latest_cot.non_commercial_short,
                    'commercial_long': latest_cot.commercial_long,
                    'commercial_short': latest_cot.commercial_short,
                    'net_position': latest_cot.net_position,
                    'sentiment_score': latest_cot.sentiment_score
                }
                
                # ✅ USA GPTAnalyzer invece di analyze_with_gpt()
                if gpt_analyzer.client:
                    gpt_raw = gpt_analyzer.analyze_single_symbol(gpt_input)
                else:
                    logger.warning("GPT Analyzer non disponibile - usando fallback")
                    gpt_raw = gpt_analyzer._create_fallback_analysis(gpt_input)
                
                # Gestisci il risultato
                try:
                    if isinstance(gpt_raw, dict):
                        complete_analysis['gpt_analysis'] = gpt_raw
                    else:
                        complete_analysis['gpt_analysis'] = json.loads(gpt_raw)
                except Exception:
                    complete_analysis['gpt_analysis'] = {'raw': gpt_raw, 'note': 'Non-JSON'}
            except Exception as e:
                complete_analysis['gpt_analysis'] = {'error': str(e)}
        
        # 2. Analisi Tecnica
        if TECHNICAL_ANALYZER_AVAILABLE:
            try:
                tech_analysis = analyze_symbol_complete(symbol)
                complete_analysis['technical_analysis'] = tech_analysis
            except Exception as e:
                logger.warning(f"Errore technical analysis: {e}")
                complete_analysis['technical_analysis'] = {'error': str(e)}
        
        # 3. Predizione ML
        if latest_cot:
            # Assicurati che predictor sia inizializzato
            global predictor
            if predictor is None:
                predictor = create_production_predictor()
            
            # Carica dati storici per training automatico
            hist_rows = (COTData.query
                        .filter_by(symbol=symbol)
                        .order_by(COTData.date.asc())
                        .all())
            
            historical = []
            for r in hist_rows:
                historical.append({
                    "non_commercial_long": r.non_commercial_long,
                    "non_commercial_short": r.non_commercial_short,
                    "commercial_long": r.commercial_long,
                    "commercial_short": r.commercial_short,
                    "net_position": r.net_position,
                    "sentiment_score": r.sentiment_score
                })
            
            # Auto-train se necessario (serve almeno 3 record)
            if not predictor.is_trained and len(historical) >= 3:
                try:
                    trained = predictor.train(historical)
                    logger.info(f"🎯 Auto-train per {symbol}: {'OK' if trained else 'FAILED'} (n={len(historical)})")
                except Exception as e:
                    logger.warning(f"⚠️ Auto-train fallito per {symbol}: {e}")
            
            # Prepara dati per predizione
            cot_data_dict = {
                'non_commercial_long': latest_cot.non_commercial_long,
                'non_commercial_short': latest_cot.non_commercial_short,
                'commercial_long': latest_cot.commercial_long,
                'commercial_short': latest_cot.commercial_short,
                'net_position': latest_cot.net_position,
                'sentiment_score': latest_cot.sentiment_score
            }
            
            # Genera predizione
            ml_prediction = predictor.predict(cot_data_dict)
            complete_analysis['ml_prediction'] = ml_prediction
        
        # 4. Predizioni storiche
        recent_predictions = Prediction.query.filter_by(symbol=symbol)\
            .order_by(Prediction.prediction_date.desc()).limit(5).all()
        
        complete_analysis['recent_predictions'] = [
            {
                'date': p.prediction_date.isoformat(),
                'direction': p.predicted_direction,
                'confidence': p.confidence,
                'ml_score': p.ml_score
            } for p in recent_predictions
        ]
        
        # FIX: Aggiungi GPT Analysis dall'ultima predizione salvata
        last_pred = Prediction.query.filter_by(symbol=symbol)\
            .order_by(Prediction.prediction_date.desc()).first()
        
        if last_pred and last_pred.gpt_analysis:
            try:
                gpt_json = json.loads(last_pred.gpt_analysis) \
                           if isinstance(last_pred.gpt_analysis, str) else last_pred.gpt_analysis
                complete_analysis['gpt_analysis'] = gpt_json
            except Exception:
                complete_analysis['gpt_analysis'] = last_pred.gpt_analysis
        
        return jsonify(complete_analysis)
        
    except Exception as e:
        logger.error(f"Errore analisi completa {symbol}: {str(e)}")
        return jsonify({
            'symbol': symbol,
            'error': str(e),
            'status': 'ERROR',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/system/status')
def get_system_status():
    """Status completo del sistema"""
    try:
        # Test database
        db_status = 'ONLINE'
        db_count = 0
        try:
            db_count = COTData.query.count()
        except:
            db_status = 'ERROR'
        
        # Test ML
        ml_info = predictor.get_model_info()
        
        # Test Technical Analyzer
        ta_status = 'ACTIVE' if TECHNICAL_ANALYZER_AVAILABLE else 'DISABLED'
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'components': {
                'database': {
                    'status': db_status,
                    'record_count': db_count,
                    'last_update': get_last_db_update()
                },
                'machine_learning': {
                    'status': 'TRAINED' if ml_info['is_trained'] else 'NOT_TRAINED',
                    'available': ml_info['ml_available'],
                    'accuracy': ml_info['current_accuracy'],
                    'training_size': ml_info['training_data_size']
                },
                'technical_analysis': {
                    'status': ta_status,
                    'features': ['support_resistance', 'signals', 'economic_calendar'] if TECHNICAL_ANALYZER_AVAILABLE else []
                },
                'openai_api': {
                    'status': 'CONFIGURED' if os.environ.get('OPENAI_API_KEY') else 'NOT_CONFIGURED'
                }
            },
            'data_coverage': {
                'symbols_count': len(COT_SYMBOLS),
                'predictions_count': get_predictions_count(),
                'newest_data': get_newest_data_date()
            }
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Errore system status: {e}")
        return jsonify({'error': str(e)}), 500

# ==========================================
# API ADMIN: CACHE MANAGEMENT
# ==========================================

@app.route('/api/admin/cache/stats')
@login_required
def cache_stats_api():
    """Statistiche cache - solo admin"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        stats = {
            'timestamp': datetime.now().isoformat(),
            'coalescer': {
                'active_results': len(coalescer._results),
                'active_locks': len(coalescer._locks),
            },
            'cache': {
                'smart_timeout_current_seconds': get_smart_cache_timeout(),
                'smart_timeout_current_hours': get_smart_cache_timeout() / 3600
            },
            'next_cot_update': get_next_cot_update_time()
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/cache/clear', methods=['POST'])
@login_required
def clear_cache_api():
    """Svuota cache - solo admin"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        cache.clear()
        coalescer._results.clear()
        coalescer._timestamps.clear()
        coalescer._locks.clear()
        
        logger.info("🗑️ Cache cleared by admin")
        
        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully'
        })
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/cache/warm', methods=['POST'])
@login_required
def warm_cache_api():
    """Forza cache warming manuale - solo admin"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Avvia warming in thread separato
        def do_warming():
            with app.app_context():
                logger.info("🔥 Manual cache warming...")
                priority_symbols = ['GOLD', 'USD', 'EUR']
                
                for symbol in priority_symbols:
                    try:
                        latest_cot = COTData.query.filter_by(symbol=symbol)\
                            .order_by(COTData.date.desc()).first()
                        
                        if latest_cot:
                            analysis_data = {
                                'symbol': symbol,
                                'timestamp': datetime.now().isoformat(),
                                'cot_data': {
                                    'net_position': latest_cot.net_position,
                                    'sentiment_score': latest_cot.sentiment_score
                                }
                            }
                            
                            cache_key = f"complete_analysis:get_complete_analysis:{symbol}"
                            timeout = get_smart_cache_timeout()
                            cache.set(cache_key, analysis_data, timeout=timeout)
                            logger.info(f"✅ Warmed {symbol}")
                    except Exception as e:
                        logger.error(f"Failed {symbol}: {e}")
                
                logger.info("🔥 Manual warming done")
        
        import threading
        thread = threading.Thread(target=do_warming, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Cache warming started in background'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_next_cot_update_time():
    """Calcola prossimo update COT (martedì 21:00)"""
    now = datetime.now()
    days_until_tuesday = (1 - now.weekday()) % 7
    
    if days_until_tuesday == 0 and now.hour >= 21:
        days_until_tuesday = 7
    
    next_update = now + timedelta(days=days_until_tuesday)
    next_update = next_update.replace(hour=21, minute=0, second=0, microsecond=0)
    
    return next_update.isoformat()
# =================== FUNZIONI HELPER ===================
# Aggiungi queste funzioni helper

def create_fallback_technical_analysis(symbol):
    """Analisi tecnica di fallback quando TA non disponibile"""
    base_prices = {
        'GOLD': 2539.71, 'SILVER': 24.32, 'USD': 103.45, 'EUR': 1.0875,
        'GBP': 1.2634, 'JPY': 150.25, 'OIL': 78.45, 'SP500': 4485.50
    }
    
    current_price = base_prices.get(symbol, 100.0)
    
    return {
        'symbol': symbol,
        'current_price': current_price,
        'strong_resistance': current_price * 1.025,
        'medium_resistance': current_price * 1.015,
        'strong_support': current_price * 0.985,
        'critical_support': current_price * 0.975,
        'trend_bias': 'NEUTRAL',
        'price_position': 'MIDDLE_RANGE',
        'signals': {
            'overall': {'signal': 'NEUTRAL', 'confidence': 50}
        },
        'note': 'Dati simulati - Technical Analyzer non disponibile'
    }

def create_fallback_economic_data():
    """Dati economici di fallback"""
    return {
        'timestamp': datetime.now().isoformat(),
        'key_indicators': {
            'inflation_usa': {'value': 2.7, 'trend': 'DECLINING'},
            'fed_funds_rate': {'value': 4.50, 'probability_cut_25bps': 87},
            'dollar_index': {'value': 103.45, 'trend': 'WEAKENING'}
        },
        'note': 'Dati simulati - Technical Analyzer non disponibile'
    }

def create_fallback_calendar():
    """Calendario eventi di fallback"""
    base_date = datetime.now()
    return [
        {
            'name': 'FOMC Meeting',
            'date': (base_date + timedelta(days=5)).strftime('%Y-%m-%d'),
            'impact': 'HIGH',
            'description': 'Decisione tassi Fed'
        },
        {
            'name': 'CPI Data',
            'date': (base_date + timedelta(days=3)).strftime('%Y-%m-%d'),
            'impact': 'HIGH',
            'description': 'Dato inflazione USA'
        }
    ]

def calculate_oi_delta(symbol):
    """Calcola variazione Open Interest (simulata)"""
    import random
    random.seed(hash(symbol + str(datetime.now().date())))
    return random.randint(-8000, 12000)

def determine_cot_signal(cot_data):
    """Determina segnale da dati COT"""
    sentiment = cot_data.sentiment_score or 0
    
    if sentiment > 20:
        return 'STRONG_BUY'
    elif sentiment > 10:
        return 'BUY'
    elif sentiment < -20:
        return 'STRONG_SELL'
    elif sentiment < -10:
        return 'SELL'
    else:
        return 'NEUTRAL'

def combine_signals(cot_data, technical_data):
    """Combina segnali COT e tecnici"""
    cot_signal = determine_cot_signal(cot_data)
    tech_signal = technical_data.get('signals', {}).get('overall', {}).get('signal', 'NEUTRAL')
    
    # Logica semplice di combinazione
    if 'BUY' in cot_signal and 'BUY' in tech_signal:
        return 'STRONG_BULLISH'
    elif 'SELL' in cot_signal and 'SELL' in tech_signal:
        return 'STRONG_BEARISH'
    elif 'BUY' in cot_signal or 'BUY' in tech_signal:
        return 'BULLISH'
    elif 'SELL' in cot_signal or 'SELL' in tech_signal:
        return 'BEARISH'
    else:
        return 'NEUTRAL'

def determine_market_regime_synthesis(cot_data, technical_data):
    """Determina regime di mercato"""
    net_pos = abs(cot_data.net_position or 0)
    sentiment = abs(cot_data.sentiment_score or 0)
    
    if net_pos > 200000 and sentiment > 30:
        return 'EXTREME_POSITIONING'
    elif sentiment > 20:
        return 'STRONG_TREND'
    elif sentiment < 10:
        return 'CONSOLIDATION'
    else:
        return 'TRANSITIONAL'

def get_last_db_update():
    """Ultimo aggiornamento database"""
    try:
        latest = COTData.query.order_by(COTData.created_at.desc()).first()
        return latest.created_at.isoformat() if latest else None
    except:
        return None

def get_predictions_count():
    """Conta predizioni totali"""
    try:
        return Prediction.query.count()
    except:
        return 

def get_newest_data_date():
    """Data del dato pi recente"""
    try:
        latest = COTData.query.order_by(COTData.date.desc()).first()
        return latest.date.isoformat() if latest else None
    except:
        return None
# =================== API ROUTES ===================
# ==========================================
# IMPORT MANCANTI (aggiungi in alto con gli altri import)
# ==========================================
from flask_login import login_required, current_user

# ==========================================
# ROUTES PUBBLICHE
# ==========================================

@app.route('/')
def index():
    """Homepage"""
    if current_user.is_authenticated:
        return redirect('/dashboard')
    return render_template('index.html')

@app.route('/features')
def features():
    """Pagina features"""
    return render_template('features.html')

@app.route('/pricing')
def pricing():
    """Pagina pricing"""
    return render_template('pricing.html', plans=SUBSCRIPTION_PLANS)

@app.route('/about')
def about():
    """Pagina about"""
    return render_template('about.html')

@app.route('/contact')
def contact():
    """Pagina contact"""
    return render_template('contact.html')

# ==========================================
# ROUTES AUTENTICAZIONE (gestite da auth_bp)
# Le routes /login, /register, /logout, /checkout
# sono già nel auth_routes.py - NON duplicarle qui
# ==========================================

# ==========================================
# DASHBOARD E PROFILO
# ==========================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principale"""
    stats = {
        'days_active': (datetime.utcnow() - current_user.created_at).days if current_user.created_at else 0,
        'analyses_count': 0,  # TODO: implementa conteggio reale
        'assets_tracked': 0,
        'accuracy': 0
    }
    return render_template('dashboard.html', current_user=current_user, stats=stats)

@app.route('/profile')
@login_required
def profile():
    """Profilo utente"""
    stats = {
        'days_active': (datetime.utcnow() - current_user.created_at).days if current_user.created_at else 0,
        'analyses_count': 0,
        'assets_tracked': 0,
        'accuracy': 0
    }
    return render_template('profile.html', current_user=current_user, stats=stats)

@app.route('/auth/update-profile', methods=['POST'])
@login_required
def update_profile():
    """Aggiorna dati profilo"""
    data = request.json
    try:
        current_user.first_name = data['firstName']
        current_user.last_name = data['lastName']
        current_user.email = data['email']
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """Cambia password"""
    data = request.json
    
    if not current_user.check_password(data['currentPassword']):
        return jsonify({'error': 'Password attuale errata'}), 400
    
    try:
        current_user.set_password(data['newPassword'])
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/auth/update-preferences', methods=['POST'])
@login_required
def update_preferences():
    """Aggiorna preferenze"""
    data = request.json
    try:
        current_user.email_notifications = data.get('emailNotifications', True)
        current_user.newsletter = data.get('newsletter', False)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ==========================================
# API COT - CON PROTEZIONI ABBONAMENTO
# ==========================================

@app.route('/api/symbols')
@login_required
@cached(category='default', ttl=86400)  # Cache 24 ore
def get_symbols():
    """Lista simboli disponibili"""
    # Admin o Professional: tutti i simboli
    if current_user.is_admin or current_user.subscription_plan == 'professional':
        symbols_list = [
            {'code': 'GOLD', 'name': 'Gold'},
            {'code': 'USD', 'name': 'US Dollar Index'},
            {'code': 'EUR', 'name': 'Euro FX'},
            {'code': 'GBP', 'name': 'British Pound'},
            {'code': 'JPY', 'name': 'Japanese Yen'},
            {'code': 'CHF', 'name': 'Swiss Franc'},
            {'code': 'CAD', 'name': 'Canadian Dollar'},
            {'code': 'AUD', 'name': 'Australian Dollar'},
            {'code': 'SILVER', 'name': 'Silver'},
            {'code': 'OIL', 'name': 'Crude Oil'}
        ]
        return jsonify({
            'symbols': symbols_list,
            'limit': None,
            'message': None
        })
    
    # Starter: primi 5
    symbols_list = [
        {'code': 'GOLD', 'name': 'Gold'},
        {'code': 'USD', 'name': 'US Dollar Index'},
        {'code': 'EUR', 'name': 'Euro FX'},
        {'code': 'GBP', 'name': 'British Pound'},
        {'code': 'JPY', 'name': 'Japanese Yen'}
    ]
    
    return jsonify({
        'symbols': symbols_list,
        'limit': 5,
        'message': 'Piano Starter: max 5 asset monitorabili. Passa a Professional per tutti gli asset.'
    })

@app.route('/api/scrape/<symbol>')
@login_required
def scrape_symbol(symbol):
    """Scraping manuale - solo admin - VERSIONE OTTIMIZZATA"""
    if not current_user.is_admin:
        return jsonify({'error': 'Accesso negato - solo admin'}), 403
    
    if symbol not in COT_SYMBOLS:
        return jsonify({'error': 'Simbolo non valido'}), 400
    
    try:
        # Lock per scraping
        import threading
        if not hasattr(scrape_symbol, 'lock'):
            scrape_symbol.lock = threading.Lock()
        
        with scrape_symbol.lock:
            from collectors.cot_scraper import COTScraper
            
            logger.info(f"🔄 Scraping {symbol}...")
            
            # 1. Scraping COT
            with COTScraper(headless=True) as scraper:
                data = scraper.scrape_cot_data(symbol)
                
                if not data:
                    return jsonify({'error': 'Scraping failed'}), 500
                
                # Ricalcola sentiment
                data['sentiment_score'] = calculate_cot_sentiment(
                    data['non_commercial_long'],
                    data['non_commercial_short'], 
                    data['commercial_long'],
                    data['commercial_short']
                )
                logger.info(f"✅ Sentiment: {data['sentiment_score']:.2f}%")
            
            # 2. Salva COT nel DB
            existing = COTData.query.filter_by(
                symbol=symbol, date=data['date']
            ).first()
            
            if not existing:
                cot_entry = COTData(**data)
                db.session.add(cot_entry)
                db.session.commit()
                logger.info(f"✅ COT data saved for {symbol}")
            else:
                logger.info(f"ℹ️ COT data already exists for {symbol}")
            
            # 3. ⚡ GPT Pre-calcolo (CHIAVE PER PERFORMANCE!)
            gpt_analysis = None
            try:
                if gpt_analyzer.client:
                    logger.info(f"🤖 Running GPT analysis for {symbol}...")
                    start_gpt = time.time()
                    gpt_analysis = gpt_analyzer.analyze_single_symbol(data)
                    gpt_duration = (time.time() - start_gpt) * 1000
                    logger.info(f"✅ GPT completed in {gpt_duration:.0f}ms")
                else:
                    logger.warning("GPT Analyzer not available - using fallback")
                    gpt_analysis = gpt_analyzer._create_fallback_analysis(data)
            except Exception as e:
                logger.error(f"❌ GPT error: {e}")
                gpt_analysis = gpt_analyzer._create_fallback_analysis(data)
            
            # 4. Salva predizione con GPT
            if gpt_analysis:
                prediction = Prediction(
                    symbol=symbol,
                    prediction_date=datetime.now(),
                    predicted_direction=gpt_analysis.get('direction', 'NEUTRAL'),
                    confidence=gpt_analysis.get('confidence', 50),
                    ml_score=None,
                    gpt_analysis=json.dumps(gpt_analysis) if isinstance(gpt_analysis, dict) else gpt_analysis
                )
                db.session.add(prediction)
                db.session.commit()
                logger.info(f"✅ Prediction saved for {symbol}")
            
            # 5. ⚡ INVALIDA CACHE (CRITICO!)
            cache_keys = [
                f"complete_analysis:get_complete_analysis:{symbol}",
                f"technical:get_technical_analysis:{symbol}",
                f"cot_data:get_data:{symbol}",
                f"synthesis:get_cot_synthesis:{symbol}"
            ]
            
            for key in cache_keys:
                try:
                    cache.delete(key)
                    logger.info(f"🗑️ Cache invalidated: {key}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate {key}: {e}")
            
            return jsonify({
                'status': 'success',
                'message': f'Analysis completed for {symbol}',
                'data': {
                    'symbol': symbol,
                    'date': data['date'].isoformat() if isinstance(data['date'], datetime) else data['date'],
                    'sentiment_score': data['sentiment_score'],
                    'net_position': data['net_position']
                },
                'gpt_analysis': gpt_analysis
            })
            
    except Exception as e:
        logger.error(f"❌ Error scraping {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/data/<symbol>')
@login_required
@smart_cache_response('cot_data')
@cached(category='cot_data', ttl=3600)  # Cache 1 ora
def get_data(symbol):
    """Dati storici simbolo"""
    days = request.args.get('days', 30, type=int)
    
    data = COTData.query.filter_by(symbol=symbol)\
        .filter(COTData.date >= datetime.now() - timedelta(days=days))\
        .order_by(COTData.date.desc()).all()
    
    return jsonify([{
        'date': d.date.isoformat(),
        'non_commercial_long': d.non_commercial_long,
        'non_commercial_short': d.non_commercial_short,
        'commercial_long': d.commercial_long,
        'commercial_short': d.commercial_short,
        'net_position': d.net_position,
        'sentiment_score': d.sentiment_score
    } for d in data])

@app.route('/api/predictions/<symbol>')
@login_required
@cached(category='prediction', ttl=1800)  # Cache 30 minuti
def get_predictions(symbol):
    """Predizioni simbolo - solo Professional o Admin"""
    # ✅ ADMIN bypassa tutto
    if not current_user.is_admin and not current_user.has_feature('ai_predictions'):
        return jsonify({
            'error': 'Feature AI disponibile solo per Professional',
            'upgrade_url': '/pricing'
        }), 403
    
    predictions = Prediction.query.filter_by(symbol=symbol)\
        .order_by(Prediction.prediction_date.desc())\
        .limit(10).all()
    
    return jsonify([{
        'date': p.prediction_date.isoformat(),
        'direction': p.predicted_direction,
        'confidence': p.confidence,
        'ml_score': p.ml_score,
        'gpt_analysis': p.gpt_analysis
    } for p in predictions])
# ==========================================
# HEALTH CHECK (per Render)
# ==========================================

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected'
    })
# ⚡ HEALTH CHECK AVANZATO
@app.route('/api/health')
def health_check():
    """Health check con metriche database"""
    try:
        db.session.execute('SELECT 1')
        active_connections = 'N/A'
        if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']:
            try:
                result = db.session.execute('SELECT count(*) FROM pg_stat_activity')
                active_connections = result.scalar()
            except:
                pass
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'active_connections': active_connections,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500
# ==========================================
# ERROR HANDLERS
# ==========================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# =================== SCHEDULED TASKS ===================
def scheduled_scraping():
    """Scraping automatico schedulato"""
    print(f"Avvio scraping automatico: {datetime.now()}")
    
    for symbol in COT_SYMBOLS.keys():
        try:
            data = scrape_cot_data(symbol)
            if data:
                # Controlla se esiste gi  
                existing = COTData.query.filter_by(
                    symbol=symbol,
                    date=data['date']
                ).first()
                
                if not existing:
                    cot_entry = COTData(**data)
                    db.session.add(cot_entry)
                    db.session.commit()
                    print(f" Salvato {symbol}")
                else:
                    print(f"- {symbol} gi  presente")
        except Exception as e:
            print(f" Errore {symbol}: {str(e)}")
        
        time.sleep(10)  # Pausa tra richieste

# =================== INIZIALIZZAZIONE ===================
# Inizializza database all'avvio
with app.app_context():
    try:
        db.create_all()
        print("✅ Database creato/verificato")
        
        # ⚡ CACHE WARMING - Pre-carica dati più richiesti
        def warm_cache_background():
            """Cache warming in background per non bloccare l'avvio"""
            import time
            time.sleep(3)  # Aspetta che l'app sia completamente pronta
            
            with app.app_context():
                logger.info("🔥 Cache warming started...")
                priority_symbols = ['GOLD', 'USD', 'EUR']
                
                for symbol in priority_symbols:
                    try:
                        logger.info(f"🔥 Warming cache for {symbol}...")
                        
                        # Recupera ultimo dato COT
                        latest_cot = COTData.query.filter_by(symbol=symbol)\
                            .order_by(COTData.date.desc()).first()
                        
                        if not latest_cot:
                            logger.warning(f"⚠️ No COT data for {symbol}, skipping")
                            continue
                        
                        # Costruisci analisi base
                        analysis_data = {
                            'symbol': symbol,
                            'timestamp': datetime.now().isoformat(),
                            'status': 'SUCCESS',
                            'cot_data': {
                                'date': latest_cot.date.isoformat(),
                                'net_position': latest_cot.net_position,
                                'sentiment_score': latest_cot.sentiment_score,
                                'non_commercial_long': latest_cot.non_commercial_long,
                                'non_commercial_short': latest_cot.non_commercial_short,
                                'commercial_long': latest_cot.commercial_long,
                                'commercial_short': latest_cot.commercial_short
                            }
                        }
                        
                        # Aggiungi Technical Analysis se disponibile
                        if TECHNICAL_ANALYZER_AVAILABLE:
                            try:
                                tech_analysis = analyze_symbol_complete(symbol)
                                analysis_data['technical_analysis'] = tech_analysis
                            except Exception as e:
                                logger.warning(f"Technical analysis failed for {symbol}: {e}")
                        
                        # Aggiungi ultima predizione GPT se disponibile
                        last_pred = Prediction.query.filter_by(symbol=symbol)\
                            .order_by(Prediction.prediction_date.desc()).first()
                        
                        if last_pred and last_pred.gpt_analysis:
                            try:
                                gpt_json = json.loads(last_pred.gpt_analysis) \
                                           if isinstance(last_pred.gpt_analysis, str) else last_pred.gpt_analysis
                                analysis_data['gpt_analysis'] = gpt_json
                            except Exception as e:
                                logger.warning(f"Failed to parse GPT analysis: {e}")
                        
                        # Aggiungi ML prediction
                        if predictor and predictor.is_trained:
                            try:
                                cot_dict = {
                                    'non_commercial_long': latest_cot.non_commercial_long,
                                    'non_commercial_short': latest_cot.non_commercial_short,
                                    'commercial_long': latest_cot.commercial_long,
                                    'commercial_short': latest_cot.commercial_short,
                                    'net_position': latest_cot.net_position,
                                    'sentiment_score': latest_cot.sentiment_score
                                }
                                ml_pred = predictor.predict(cot_dict)
                                analysis_data['ml_prediction'] = ml_pred
                            except Exception as e:
                                logger.warning(f"ML prediction failed: {e}")
                        
                        # Salva in cache
                        cache_key = f"complete_analysis:get_complete_analysis:{symbol}"
                        timeout = get_smart_cache_timeout()
                        cache.set(cache_key, analysis_data, timeout=timeout)
                        
                        logger.info(f"✅ Cache warmed for {symbol} (TTL: {timeout}s)")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to warm cache for {symbol}: {e}")
                
                logger.info("🔥 Cache warming completed!")
        
        # Avvia cache warming in thread separato per non bloccare l'avvio
        import threading
        warming_thread = threading.Thread(target=warm_cache_background, daemon=True)
        warming_thread.start()
        logger.info("🚀 Cache warming thread started")
        
    except Exception as e:
        logger.error(f"⚠️ Initialization error: {e}")

# =================== CLI COMMANDS ===================
@app.cli.command('create-admin')
def create_admin():
    """Crea utente admin - uso: flask create-admin"""
    from werkzeug.security import generate_password_hash
    
    email = input("Email admin: ")
    password = input("Password: ")
    
    if User.query.filter_by(email=email).first():
        print("❌ Email già esistente")
        return
    
    admin_user = User(
        email=email,
        password_hash=generate_password_hash(password),
        first_name='Admin',
        last_name='User',
        is_admin=True,
        subscription_plan='enterprise'
    )
    
    db.session.add(admin_user)
    db.session.commit()
    
    print(f"✅ Admin creato: {email}")

# =================== CREAZIONE INDICI DATABASE ===================
def create_database_indexes():
    """
    Crea indici per ottimizzare query comuni
    Esegui DOPO aver creato le tabelle
    """
    try:
        with app.app_context():
            # Indice composto per query COT più comuni
            db.session.execute(
                'CREATE INDEX IF NOT EXISTS idx_cot_symbol_date '
                'ON cot_data(symbol, date DESC)'
            )
            
            # Indice per predictions
            db.session.execute(
                'CREATE INDEX IF NOT EXISTS idx_pred_symbol_date '
                'ON predictions(symbol, prediction_date DESC)'
            )
            
            db.session.commit()
            logger.info("✅ Indici database creati con successo")
    
    except Exception as e:
        logger.error(f"Errore creazione indici: {e}")
        db.session.rollback()
  
@app.route('/api/cache/stats')
def cache_stats():
    """Mostra statistiche cache"""
    return jsonify(GLOBAL_CACHE.get_stats())

@app.route('/api/cache/clear', methods=['POST'])
@login_required
def cache_clear():
    """Pulisce cache - solo utenti loggati"""
    if not current_user.is_admin:
        return jsonify({'error': 'Solo admin'}), 403
    
    GLOBAL_CACHE.clear_all()
    cache.clear()  # Pulisci anche la cache Flask
    
    return jsonify({
        'status': 'success',
        'message': 'Cache cleared'
    })      
        
if __name__ == '__main__':
    import os
    
    # Porta da environment (per Render/Heroku)
    port = int(os.environ.get('PORT', 5000))
    
    # Modalità development locale
    if os.environ.get('FLASK_ENV') == 'development':
        print("Avvio COT Analysis Platform - DEVELOPMENT")
        app.run(
            debug=True,
            host='0.0.0.0',
            port=port,
            use_reloader=False
        )
    else:
        # In produzione usa gunicorn
        print("Modalità PRODUZIONE - usa: gunicorn app_complete:app")
    
    # use_reloader=False evita riavvii automatici quando modifichi file
    app.run(
        debug=True,           # Mantiene debug per messaggi dettagliati
        host='0.0.0.0',      # Accessibile da qualsiasi IP
        port=5000,           # Porta standard
        use_reloader=False   # 🔑 CHIAVE: Evita riavvii automatici
    )