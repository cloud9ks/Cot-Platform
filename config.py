
import os
from datetime import timedelta
from dotenv import load_dotenv

# Carica variabili d'ambiente dal file .env
load_dotenv()

class Config:
    """Configurazione Base"""
    
    # === FLASK CONFIGURATION ===
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-123456789')
    
    # === DATABASE ===
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///cot_data.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Set True per debug queries
    
    # === OPENAI API ===
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = "gpt-4o-mini"  # o "gpt-4" per risultati migliori
    OPENAI_MAX_TOKENS = 1500
    OPENAI_TEMPERATURE = 0.2
    
    # === SCHEDULER CONFIGURATION ===
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "Europe/Rome"
    
    # Orari di aggiornamento COT (Marted alle 21:00)
    COT_UPDATE_DAY = 1  # 0=Luned, 1=Marted, etc.
    COT_UPDATE_HOUR = 21
    COT_UPDATE_MINUTE = 0
    
    # === SELENIUM CONFIGURATION ===
    SELENIUM_HEADLESS = True  # False per vedere il browser durante lo scraping
    SELENIUM_TIMEOUT = 30  # Timeout in secondi
    SELENIUM_WAIT_TIME = 10  # Tempo di attesa caricamento pagina
    
    # === COT SYMBOLS CONFIGURATION ===
    COT_SYMBOLS = {
        'GOLD': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/088691',
            'name': 'Gold',
            'code': '088691',
            'category': 'commodities'
        },
        'USD': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/098662',
            'name': 'US Dollar Index',
            'code': '098662',
            'category': 'currencies'
        },
        'EUR': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/099741',
            'name': 'Euro FX',
            'code': '099741',
            'category': 'currencies'
        },
        'GBP': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/096742',
            'name': 'British Pound',
            'code': '096742',
            'category': 'currencies'
        },
        'JPY': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/097741',
            'name': 'Japanese Yen',
            'code': '097741',
            'category': 'currencies'
        },
        'CHF': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/092741',
            'name': 'Swiss Franc',
            'code': '092741',
            'category': 'currencies'
        },
        'CAD': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/090741',
            'name': 'Canadian Dollar',
            'code': '090741',
            'category': 'currencies'
        },
        'AUD': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/232741',
            'name': 'Australian Dollar',
            'code': '232741',
            'category': 'currencies'
        },
        'NZD': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/112741',
            'name': 'New Zealand Dollar',
            'code': '112741',
            'category': 'currencies'
        },
        'SILVER': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/084691',
            'name': 'Silver',
            'code': '084691',
            'category': 'commodities'
        },
        'OIL': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/067651',
            'name': 'Crude Oil WTI',
            'code': '067651',
            'category': 'energy'
        },
        'COPPER': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/085692',
            'name': 'Copper',
            'code': '085692',
            'category': 'commodities'
        },
        'NATGAS': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/023651',
            'name': 'Natural Gas',
            'code': '023651',
            'category': 'energy'
        },
        'SP500': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/138741',
            'name': 'S&P 500',
            'code': '138741',
            'category': 'indices'
        },
        'NASDAQ': {
            'url': 'https://www.tradingster.com/cot/legacy-futures/209742',
            'name': 'Nasdaq 100',
            'code': '209742',
            'category': 'indices'
        }
    }
    
    # === ANALYSIS PARAMETERS ===
    SENTIMENT_THRESHOLD_BULLISH = 20  # Score sopra questo = Bullish
    SENTIMENT_THRESHOLD_BEARISH = -20  # Score sotto questo = Bearish
    
    # Net position thresholds
    NET_POSITION_EXTREME_HIGH = 100000
    NET_POSITION_EXTREME_LOW = -100000
    
    # === ML PARAMETERS ===
    ML_MIN_DATA_POINTS = 10  # Minimo di dati storici per training
    ML_TRAIN_TEST_SPLIT = 0.8
    ML_RANDOM_STATE = 42
    
    # === API RATE LIMITS ===
    API_RATE_LIMIT_PER_MINUTE = 60
    API_RATE_LIMIT_PER_HOUR = 1000
    
    # === CACHE CONFIGURATION ===
    CACHE_TYPE = "simple"
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minuti
    
    # === LOGGING ===
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = 'logs/cot_platform.log'
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    
    # === DATA PATHS ===
    DATA_FOLDER = 'data'
    CSV_OUTPUT_FOLDER = os.path.join(DATA_FOLDER, 'csv_output')
    ANALYSIS_OUTPUT_FOLDER = os.path.join(DATA_FOLDER, 'analysis_output')
    MODELS_FOLDER = os.path.join(DATA_FOLDER, 'models')
    
    # === ALERTS CONFIGURATION ===
    ENABLE_EMAIL_ALERTS = False
    EMAIL_SMTP_SERVER = os.environ.get('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
    EMAIL_SMTP_PORT = 587
    EMAIL_USERNAME = os.environ.get('EMAIL_USERNAME')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
    EMAIL_RECIPIENTS = os.environ.get('EMAIL_RECIPIENTS', '').split(',')
    
    # === SECURITY ===
    SESSION_COOKIE_SECURE = False  # Set True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # === CORS ===
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:5000"]

class DevelopmentConfig(Config):
    """Configurazione per Sviluppo"""
    DEBUG = True
    TESTING = False
    SELENIUM_HEADLESS = False  # Mostra browser in sviluppo

class ProductionConfig(Config):
    """Configurazione per Produzione"""
    DEBUG = False
    TESTING = False
    
    # Usa PostgreSQL in produzione
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://user:pass@localhost/cot_db'
    )
    
    # Sicurezza extra in produzione
    SESSION_COOKIE_SECURE = True
    
    # Disabilita echo SQL in produzione
    SQLALCHEMY_ECHO = False

class TestingConfig(Config):
    """Configurazione per Testing"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Dizionario configurazioni
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# Funzione helper per ottenere la configurazione
def get_config():
    """Ottiene la configurazione basata sull'ambiente"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config_dict.get(env, DevelopmentConfig)

# Configurazione attiva
current_config = get_config()