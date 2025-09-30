"""
COT Analysis Platform - Sistema Completo FINALE
Piattaforma professionale per analisi e previsioni COT
"""

from flask import Flask, redirect, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
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
load_dotenv()

# =================== CONFIGURAZIONE ===================
app = Flask(__name__)
CORS(app)
    
# AGGIUNGI QUESTE LINEE:
# Fix encoding Unicode per JSON responses
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False

# Le tue configurazioni esistenti continuano qui...
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
# Usa PostgreSQL in produzione, SQLite in sviluppo locale
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///cot_data.db')
# Fix per Render che usa postgres:// invece di postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

# Database
db = SQLAlchemy(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("cot_platform")

# Scheduler per aggiornamenti automatici
scheduler = APScheduler()

# =================== MODELLI DATABASE ===================

# =================== USER MODEL & ADMIN DECORATOR ===================
from flask_login import LoginManager, UserMixin, login_required, current_user
from functools import wraps

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    """Modello User con supporto admin"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)  # 🆕 Campo admin
    subscription_plan = db.Column(db.String(20), default='starter')
    subscription_status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    """Decoratore per route che richiedono privilegi admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login richiesto'}), 401
        if not current_user.is_admin:
            return jsonify({'error': 'Privilegi admin richiesti'}), 403
        return f(*args, **kwargs)
    return decorated_function


class COTData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    non_commercial_long = db.Column(db.Integer)
    non_commercial_short = db.Column(db.Integer)
    non_commercial_spreads = db.Column(db.Integer)
    commercial_long = db.Column(db.Integer)
    commercial_short = db.Column(db.Integer)
    net_position = db.Column(db.Integer)
    sentiment_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)
    prediction_date = db.Column(db.DateTime, nullable=False)
    predicted_direction = db.Column(db.String(20))
    confidence = db.Column(db.Float)
    ml_score = db.Column(db.Float)
    gpt_analysis = db.Column(db.Text)
    actual_result = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    """Scraping dati COT per un simbolo specifico - VERSIONE CORRETTA"""
    try:
        # Importa il nuovo scraper
        from collectors.cot_scraper import COTScraper
        
        # Usa il nuovo scraper
        with COTScraper(headless=False) as scraper:
            data = scraper.scrape_cot_data(symbol)
            
            # Se il scraper ha successo, ricalcola il sentiment
            if data:
                data['sentiment_score'] = calculate_cot_sentiment(
                    data['non_commercial_long'],
                    data['non_commercial_short'], 
                    data['commercial_long'],
                    data['commercial_short']
                )
                print(f" Sentiment ricalcolato per {symbol}: {data['sentiment_score']:.2f}%")
            
            return data
            
    except ImportError:
        # Fallback al vecchio metodo se non trova il modulo
        print("Usando metodo scraping vecchio...")
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            import time
            import re
            
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            
            # Prova con chromedriver.exe locale
            if os.path.exists("chromedriver.exe"):
                service = Service("chromedriver.exe")
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                driver = webdriver.Chrome(options=chrome_options)
            
            url = COT_SYMBOLS[symbol]['url']
            driver.get(url)
            time.sleep(5)
            
            # Estrai dati
            table = driver.find_element(By.CLASS_NAME, 'table-striped')
            rows = table.find_elements(By.TAG_NAME, 'tr')
            
            if len(rows) > 3:
                cells = rows[3].find_elements(By.TAG_NAME, 'td')
                
                non_commercial_long = int(cells[0].text.replace(',', ''))
                non_commercial_short = int(cells[1].text.replace(',', ''))
                commercial_long = int(cells[3].text.replace(',', ''))
                commercial_short = int(cells[4].text.replace(',', ''))
                
                driver.quit()
                
                net_position = non_commercial_long - non_commercial_short
                
                # USA IL NUOVO CALCOLO SENTIMENT
                sentiment_score = calculate_cot_sentiment(
                    non_commercial_long,
                    non_commercial_short,
                    commercial_long, 
                    commercial_short
                )
                
                print(f" Scraping completato per {symbol}")
                print(f"   Net Position: {net_position:,}")
                print(f"   Sentiment Score (nuovo): {sentiment_score:.2f}%")
                
                return {
                    'symbol': symbol,
                    'date': datetime.now(),
                    'non_commercial_long': non_commercial_long,
                    'non_commercial_short': non_commercial_short,
                    'commercial_long': commercial_long,
                    'commercial_short': commercial_short,
                    'net_position': net_position,
                    'sentiment_score': sentiment_score
                }
            
            driver.quit()
            return None
            
        except Exception as e:
            print(f" Errore scraping {symbol}: {str(e)}")
            if 'driver' in locals():
                try:
                    driver.quit()
                except:
                    pass
            return None
    
    except Exception as e:
        print(f" Errore generale scraping: {str(e)}")
        return None

# =================== ANALISI GPT-4 CORRETTA ===================
def analyze_with_gpt(data):
    """Analisi con GPT-4 dei dati COT - VERSIONE MIGLIORATA"""
    try:
        # Controlla se la chiave API  disponibile
        openai_api_key = os.environ.get('OPENAI_API_KEY')
        if not openai_api_key:
            print("  OpenAI API key non configurata")
            return create_fallback_analysis(data)
        
        # Inizializza client OpenAI con nuova API
        from openai import OpenAI
        
        client = OpenAI(api_key=openai_api_key)
        
        # Calcola metriche avanzate
        nc_net = data['non_commercial_long'] - data['non_commercial_short']
        c_net = data['commercial_long'] - data['commercial_short']
        nc_ratio = data['non_commercial_long'] / max(data['non_commercial_short'], 1)
        c_ratio = data['commercial_long'] / max(data['commercial_short'], 1)
        
        prompt = f"""
        Sei un analista COT esperto. Analizza questi dati per {data['symbol']}:

         POSIZIONI:
        - Non-Commercial Long: {data['non_commercial_long']:,}
        - Non-Commercial Short: {data['non_commercial_short']:,}
        - Commercial Long: {data['commercial_long']:,}
        - Commercial Short: {data['commercial_short']:,}
        
         METRICHE:
        - Net Position NC: {nc_net:,}
        - Net Position Commercial: {c_net:,}
        - NC Long/Short Ratio: {nc_ratio:.2f}
        - Commercial Long/Short Ratio: {c_ratio:.2f}
        - Sentiment Score: {data['sentiment_score']:.2f}%

        REGOLE ANALISI:
        1. NC Long dominanti + C Short = BULLISH STRONG
        2. NC Short dominanti + C Long = BEARISH STRONG  
        3. Sentiment > 15% = BULLISH
        4. Sentiment < -15% = BEARISH
        5. -15% < Sentiment < 15% = NEUTRAL

        Rispondi SOLO in questo formato JSON (senza markdown):
        {{
            "direction": "BULLISH/BEARISH/NEUTRAL",
            "confidence": numero_0_a_100,
            "market_outlook": "Spiegazione breve e chiara",
            "key_observations": [
                "Osservazione 1",
                "Osservazione 2", 
                "Osservazione 3"
            ],
            "trading_bias": "LONG/SHORT/NEUTRAL",
            "risk_level": "LOW/MEDIUM/HIGH"
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sei un esperto analista COT. Rispondi SEMPRE e SOLO in formato JSON pulito, senza ```json o markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Pi deterministico
            max_tokens=800
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Pulisci la risposta da eventuali markdown
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        # Prova a parsare JSON
        try:
            analysis = json.loads(response_text)
            
            # Validazione e correzione
            if analysis.get('direction') not in ['BULLISH', 'BEARISH', 'NEUTRAL']:
                analysis['direction'] = 'NEUTRAL'
            
            confidence = analysis.get('confidence', 50)
            if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 100:
                analysis['confidence'] = 50
                
            return json.dumps(analysis)
            
        except json.JSONDecodeError:
            print(f"  GPT response non  JSON valido: {response_text[:200]}")
            return create_fallback_analysis(data)
            
    except Exception as e:
        print(f"  Errore GPT analysis: {str(e)}")
        return create_fallback_analysis(data)

def create_fallback_analysis(data):
    """Analisi di fallback migliorata"""
    sentiment_score = data.get('sentiment_score', 0)
    nc_net = data['non_commercial_long'] - data['non_commercial_short']
    
    # Logica migliorata
    if sentiment_score > 5 or nc_net > 50000:
        direction = "BULLISH"
        confidence = min(75 + abs(sentiment_score), 95)
    elif sentiment_score < -5 or nc_net < -50000:
        direction = "BEARISH" 
        confidence = min(75 + abs(sentiment_score), 95)
    else:
        direction = "NEUTRAL"
        confidence = 50
    
    return json.dumps({
        "direction": direction,
        "confidence": confidence,
        "market_outlook": f"Analisi automatica: Net position NC {nc_net:,}, Sentiment {sentiment_score:.2f}%",
        "key_observations": [
            f"Non-Commercial net: {nc_net:,}",
            f"Sentiment score: {sentiment_score:.2f}%",
            f"Bias: {direction}"
        ],
        "trading_bias": direction,
        "risk_level": "MEDIUM"
    })

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
                gpt_raw = analyze_with_gpt(gpt_input)
                try:
                    complete_analysis['gpt_analysis'] = json.loads(gpt_raw) if isinstance(gpt_raw, str) else gpt_raw
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
@app.route('/')
def home():
    """Homepage"""
    return render_template('index.html')

@app.route('/features')
@app.route('/features.html')
def features():
    """Pagina features"""
    return render_template('features.html')

@app.route('/pricing')
@app.route('/pricing.html')
def pricing():
    """Pagina pricing"""
    return render_template('pricing.html')

@app.route('/about')
@app.route('/about.html')
def about():
    """Pagina about"""
    return render_template('about.html')

@app.route('/contact')
@app.route('/contact.html')
def contact():
    """Pagina contact"""
    return render_template('contact.html')

@app.route('/register')
@app.route('/register.html')
def register():
    """Pagina registrazione"""
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principale"""
    return render_template('dashboard.html')

@app.route('/<path:filename>')
def serve_html_files(filename):
    """Serve file HTML statici"""
    if filename.endswith('.html'):
        try:
            # Prima prova in templates/
            return render_template(filename)
        except:
            # Se non trova, prova nella root
            try:
                return send_from_directory('.', filename)
            except FileNotFoundError:
                return f"File {filename} non trovato", 404
    # Fallback per altri file (CSS, JS, immagini)
    return send_from_directory('.', filename)

# Assicurati che questa route esista gi , se non c' aggiungila:
@app.route('/api/symbols')
def get_symbols():
    """Lista simboli disponibili"""
    return jsonify(COT_SYMBOLS)

@app.route('/api/scrape/<symbol>')
@login_required
@admin_required  # 🆕 Solo admin
def scrape_symbol(symbol):
    """Scraping manuale per un simbolo"""
    if symbol not in COT_SYMBOLS:
        return jsonify({'error': 'Simbolo non valido'}), 400
    
    # Scraping
    data = scrape_cot_data(symbol)
    if not data:
        return jsonify({'error': 'Errore scraping'}), 500
    
   # Salva nel database
    try:
        # Filtra solo i campi supportati dal modello COTData
        db_data = {
            'symbol': data['symbol'],
            'date': data['date'],
            'non_commercial_long': data['non_commercial_long'],
            'non_commercial_short': data['non_commercial_short'],
            'non_commercial_spreads': data.get('non_commercial_spreads', 0),
            'commercial_long': data['commercial_long'],
            'commercial_short': data['commercial_short'],
            'net_position': data['net_position'],
            'sentiment_score': data['sentiment_score']
        }
        
        cot_entry = COTData(**db_data)
        db.session.add(cot_entry)
        db.session.commit()
        print(f" Dati salvati per {symbol}")
    except Exception as e:
        print(f"  Errore salvataggio dati: {str(e)}")
        db.session.rollback()
    
    # Analisi GPT
    gpt_analysis = analyze_with_gpt(data)
    try:
        gpt_analysis_parsed = json.loads(gpt_analysis) if isinstance(gpt_analysis, str) else gpt_analysis
    except Exception:
        gpt_analysis_parsed = {'raw': gpt_analysis}
        
    # ML Prediction con debug
    print(f"=== DEBUG ML per {symbol} ===")
    historical = COTData.query.filter_by(symbol=symbol).order_by(COTData.date).all()
    print(f"Record storici trovati: {len(historical)}")
    print(f"Predictor model exists: {predictor.model is not None}")
    print(f"Predictor trained: {predictor.is_trained}")
    
    ml_prediction = None
    if len(historical) > 2:  # Soglia abbassata per test
        print("Tentativo training ML...")
        hist_data = [{
            'non_commercial_long': h.non_commercial_long,
            'non_commercial_short': h.non_commercial_short,
            'commercial_long': h.commercial_long,
            'commercial_short': h.commercial_short,
            'net_position': h.net_position,
            'sentiment_score': h.sentiment_score
        } for h in historical]
       
        train_result = predictor.train(hist_data)
        print(f"Training result: {train_result}")
        
        if train_result:
            ml_prediction = predictor.predict(data)
            print(f"ML prediction result: {ml_prediction}")
    else:
        print(f"Dati insufficienti per ML: {len(historical)} <= 2")
    
    print("=== FINE DEBUG ML ===")
    
    # NUOVA SEZIONE: Analisi Tecnica
    technical_analysis = None
    technical_signals = None
    
    if TECHNICAL_ANALYZER_AVAILABLE:
        try:
            print(f"=== ANALISI TECNICA per {symbol} ===")
            technical_analysis = get_symbol_technical_data(symbol)
            technical_signals = get_technical_signals(symbol)
            
            print(f" Analisi tecnica completata per {symbol}")
            print(f"   Prezzo corrente: ${technical_analysis.get('current_price', 0):.2f}")
            print(f"   Supporto forte: ${technical_analysis.get('strong_support', 0):.2f}")
            print(f"   Resistenza forte: ${technical_analysis.get('strong_resistance', 0):.2f}")
            print(f"   Segnale tecnico: {technical_signals.get('overall', {}).get('signal', 'N/A')}")
            
        except Exception as e:
            print(f"  Errore analisi tecnica: {e}")
            # Crea dati di fallback
            base_price = {'GOLD': 2539.71, 'USD': 103.45, 'EUR': 1.0875}.get(symbol, 100.0)
            technical_analysis = {
                'symbol': symbol,
                'current_price': base_price,
                'strong_resistance': base_price * 1.025,
                'strong_support': base_price * 0.985,
                'error': str(e),
                'note': 'Dati di fallback - Technical Analyzer con errore'
            }
            technical_signals = {
                'overall': {'signal': 'NEUTRAL', 'confidence': 50},
                'error': str(e)
            }
    else:
        print("  Technical Analyzer non disponibile - saltato")
    
    # Salva predizione (sempre, anche senza ML)
    try:
        # Prova a estrarre direzione e confidenza dall'analisi GPT
        gpt_direction = "NEUTRAL"
        gpt_confidence = 50
        ml_score = None
        
        # Se abbiamo ML prediction, usa quei valori
        if ml_prediction:
            gpt_direction = ml_prediction['direction']
            gpt_confidence = ml_prediction['confidence']
            ml_score = ml_prediction.get('score', 0)
        else:
            # Altrimenti prova a estrarre dall'analisi GPT
            try:
                gpt_data = json.loads(gpt_analysis) if isinstance(gpt_analysis, str) else gpt_analysis
                gpt_direction = gpt_data.get('direction', 'NEUTRAL')
                gpt_confidence = gpt_data.get('confidence', 50)
            except:
                pass  # Usa i valori di default

        # NORMALIZZA GPT ANALYSIS PER UNICODE PULITO
        try:
            # Se è già una stringa JSON, parsala e ri-serializzala pulita
            if isinstance(gpt_analysis, str):
                parsed = json.loads(gpt_analysis)
            else:
                parsed = gpt_analysis
            
            # Re-serializza con encoding Unicode corretto
            gpt_analysis_clean = json.dumps(parsed, ensure_ascii=False, indent=2)
            
        except Exception as e:
            # Se non è JSON valido, incapsulalo in un oggetto
            logger.warning(f"GPT analysis non è JSON valido: {e}")
            gpt_analysis_clean = json.dumps({
                "raw": str(gpt_analysis),
                "note": "Analisi non in formato JSON standard"
            }, ensure_ascii=False, indent=2)

        # Crea la prediction con tutti i campi
        prediction = Prediction(
            symbol=symbol,
            prediction_date=datetime.now(),
            predicted_direction=gpt_direction,
            confidence=float(gpt_confidence),
            ml_score=float(ml_score) if ml_score is not None else None,
            gpt_analysis=gpt_analysis_clean
        )
        
        db.session.add(prediction)
        db.session.commit()
        
        logger.info(f"✅ Predizione salvata per {symbol}: {gpt_direction} ({gpt_confidence}%)")
        
    except Exception as e:
        logger.error(f"❌ Errore salvataggio predizione: {str(e)}")
        db.session.rollback()
    
    # RETURN MODIFICATO: Include analisi tecnica
    return jsonify({
        'data': data,
        'gpt_analysis': gpt_analysis_parsed,
        'ml_prediction': ml_prediction,
        'technical_analysis': technical_analysis,
        'technical_signals': technical_signals,
        'status': 'success'
    })

@app.route('/api/data/<symbol>')
def get_data(symbol):
    """Ottieni dati storici per un simbolo"""
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
def get_predictions(symbol):
    """Ottieni predizioni per un simbolo"""
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

@app.route('/api/analysis/multi')
def multi_analysis():
    """Analisi multi-asset correlazioni"""
    symbols = request.args.get('symbols', 'GOLD,USD,EUR').split(',')
    
    result = {}
    for symbol in symbols:
        latest = COTData.query.filter_by(symbol=symbol)\
            .order_by(COTData.date.desc()).first()
        
        if latest:
            result[symbol] = {
                'sentiment': latest.sentiment_score,
                'net_position': latest.net_position,
                'date': latest.date.isoformat()
            }
    
    # Calcola correlazioni
    if len(result) > 1:
        sentiments = [v['sentiment'] for v in result.values()]
        avg_sentiment = np.mean(sentiments)
        result['market_sentiment'] = {
            'average': avg_sentiment,
            'trend': 'BULLISH' if avg_sentiment > 10 else 'BEARISH' if avg_sentiment < -10 else 'NEUTRAL'
        }
    
    return jsonify(result)

@app.route('/api/backtest/<symbol>')
def backtest(symbol):
    """Backtest delle predizioni"""
    predictions = Prediction.query.filter_by(symbol=symbol)\
        .filter(Prediction.actual_result.isnot(None))\
        .all()
    
    if not predictions:
        return jsonify({'message': 'Nessun dato di backtest disponibile'})
    
    correct = sum(1 for p in predictions if p.predicted_direction == p.actual_result)
    accuracy = (correct / len(predictions)) * 100
    
    return jsonify({
        'total_predictions': len(predictions),
        'correct': correct,
        'accuracy': accuracy,
        'avg_confidence': np.mean([p.confidence for p in predictions])
    })

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
    db.create_all()
    print(" Database creato")

# Inizializza scheduler
scheduler.init_app(app)
scheduler.start()

# Aggiungi job schedulato (ogni marted alle 21:00)
scheduler.add_job(
    id='cot_scraping',
    func=scheduled_scraping,
    trigger='cron',
    day_of_week='tue',
    hour=21,
    minute=0
)

print(" Sistema inizializzato")

# =================== MAIN ===================

# =================== API USER/ADMIN ===================
@app.route('/api/user/info')
@login_required
def get_user_info():
    """Info utente corrente"""
    return jsonify({
        'id': current_user.id,
        'email': current_user.email,
        'name': f"{current_user.first_name or ''} {current_user.last_name or ''}",
        'is_admin': current_user.is_admin,
        'subscription_plan': current_user.subscription_plan
    })



# =================== AUTENTICAZIONE ROUTES ===================
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Pagina di login"""
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect('/dashboard')
        return render_template('login.html')
    
    data = request.get_json() if request.is_json else request.form
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email e password richiesti'}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Credenziali non valide'}), 401
    
    login_user(user, remember=True)
    
    return jsonify({
        'success': True,
        'redirect': '/dashboard',
        'is_admin': user.is_admin
    })

@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    return redirect('/login')


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