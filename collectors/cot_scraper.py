"""
COT Scraper Module - VERSIONE DOCKER OTTIMIZZATA
Compatibile sia con ambiente locale che con Docker/Render
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import time
import re
from datetime import datetime
import logging
import os
import sys
import platform

# Aggiungi path per import del config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importa config se disponibile, altrimenti usa defaults
try:
    from config import current_config as config
except:
    class config:
        SELENIUM_HEADLESS = True
        SELENIUM_WAIT_TIME = 10
        SELENIUM_TIMEOUT = 30
        SENTIMENT_THRESHOLD_BULLISH = 20
        SENTIMENT_THRESHOLD_BEARISH = -20
        CSV_OUTPUT_FOLDER = 'data/csv_output'
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
            }
        }

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rileva se siamo in ambiente Docker
IS_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_ENV') == 'true'

class COTScraper:
    """Classe principale per lo scraping dei dati COT - ottimizzata per Docker e locale"""
    
    def __init__(self, headless=None):
        """
        Inizializza il scraper
        
        Args:
            headless: Se True, esegue Chrome in modalità headless
        """
        self.headless = headless if headless is not None else config.SELENIUM_HEADLESS
        self.driver = None
        self.wait_time = config.SELENIUM_WAIT_TIME
        self.timeout = config.SELENIUM_TIMEOUT
        
    def setup_driver(self):
        """Configura il driver Chrome con le opzioni ottimali"""
        try:
            chrome_options = Options()
            
            # OPZIONI CRITICHE PER DOCKER
            chrome_options.add_argument("--no-sandbox")  # ESSENZIALE per Docker
            chrome_options.add_argument("--disable-dev-shm-usage")  # ESSENZIALE per Docker
            chrome_options.add_argument("--disable-gpu")
            
            # Modalità headless
            if self.headless:
                chrome_options.add_argument("--headless=new")
            
            # Ottimizzazioni performance
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-extensions")
            
            # User agent realistico
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Disabilita notifiche
            prefs = {"profile.default_content_setting_values.notifications": 2}
            chrome_options.add_experimental_option("prefs", prefs)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # STRATEGIA DI FALLBACK MULTIPLA
            driver_initialized = False
            
            # Tentativo 1: Chrome di sistema (funziona in Docker se Chrome è installato)
            if IS_DOCKER or platform.system() == 'Linux':
                try:
                    logger.info("Tentativo con Chrome di sistema (Docker/Linux)...")
                    self.driver = webdriver.Chrome(options=chrome_options)
                    driver_initialized = True
                    logger.info("✓ Chrome driver configurato (sistema)")
                except Exception as e:
                    logger.warning(f"Chrome di sistema fallito: {str(e)}")
            
            # Tentativo 2: WebDriver Manager (per ambiente locale)
            if not driver_initialized:
                try:
                    logger.info("Tentativo con WebDriver Manager...")
                    driver_path = ChromeDriverManager().install()
                    
                    if not os.path.exists(driver_path):
                        raise Exception("Driver non trovato nel path specificato")
                    
                    service = Service(driver_path)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    driver_initialized = True
                    logger.info("✓ Chrome driver configurato (WebDriver Manager)")
                except Exception as e:
                    logger.warning(f"WebDriver Manager fallito: {str(e)}")
            
            # Tentativo 3: Driver locale (chromedriver.exe nella cartella)
            if not driver_initialized:
                try:
                    logger.info("Tentativo con driver locale...")
                    if os.path.exists("chromedriver.exe"):
                        service = Service("chromedriver.exe")
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                        driver_initialized = True
                        logger.info("✓ Chrome driver configurato (locale)")
                except Exception as e:
                    logger.warning(f"Driver locale fallito: {str(e)}")
            
            if not driver_initialized:
                raise Exception(
                    "ChromeDriver non disponibile. "
                    "In Docker: assicurati che Chrome sia installato. "
                    "In locale: scarica ChromeDriver da https://chromedriver.chromium.org/"
                )
            
            # Configura timeout implicito
            self.driver.implicitly_wait(10)
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Errore configurazione driver: {str(e)}")
            if IS_DOCKER:
                logger.error("SOLUZIONE DOCKER: Assicurati che il Dockerfile installi Chrome correttamente")
            else:
                logger.error("SOLUZIONE LOCALE: Scarica ChromeDriver da https://chromedriver.chromium.org/")
            return False
    
    def scrape_cot_data(self, symbol):
        """
        Scrape dei dati COT per un simbolo specifico
        
        Args:
            symbol: Simbolo da analizzare (es. 'GOLD', 'USD')
            
        Returns:
            dict: Dati COT estratti o None in caso di errore
        """
        if symbol not in config.COT_SYMBOLS:
            logger.error(f"Simbolo {symbol} non trovato nella configurazione")
            return None
        
        try:
            # Setup driver se necessario
            if not self.driver:
                if not self.setup_driver():
                    return None
            
            # Ottieni URL per il simbolo
            url = config.COT_SYMBOLS[symbol]['url']
            logger.info(f"📊 Scraping {symbol} da: {url}")
            
            # Naviga alla pagina
            self.driver.get(url)
            
            # Attendi caricamento tabella
            try:
                WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'table-striped'))
                )
            except:
                logger.warning("Timeout attesa tabella, procedo comunque...")
            
            time.sleep(self.wait_time)
            
            # Estrai data del report
            report_date = self._extract_report_date()
            
            # Estrai dati dalla tabella
            positions_data = self._extract_positions_data()
            
            if not positions_data:
                logger.error(f"Impossibile estrarre dati per {symbol}")
                return None
            
            # Aggiungi metadati
            positions_data['symbol'] = symbol
            positions_data['date'] = report_date
            positions_data['name'] = config.COT_SYMBOLS[symbol]['name']
            positions_data['category'] = config.COT_SYMBOLS[symbol].get('category', 'unknown')
            
            # Calcola net position
            positions_data['net_position'] = (
                positions_data['non_commercial_long'] - 
                positions_data['non_commercial_short']
            )
            
            # Calcola sentiment score
            total_long = positions_data['non_commercial_long'] + positions_data['commercial_long']
            total_short = positions_data['non_commercial_short'] + positions_data['commercial_short']
            
            if (total_long + total_short) > 0:
                positions_data['sentiment_score'] = (
                    (total_long - total_short) / (total_long + total_short) * 100
                )
            else:
                positions_data['sentiment_score'] = 0
            
            # Calcola ratios (con protezione divisione per zero)
            positions_data['nc_long_ratio'] = (
                positions_data['non_commercial_long'] / 
                max(positions_data['non_commercial_short'], 1)
            )
            
            positions_data['c_long_ratio'] = (
                positions_data['commercial_long'] / 
                max(positions_data['commercial_short'], 1)
            )
            
            # Determina direzione sentiment
            if positions_data['sentiment_score'] > config.SENTIMENT_THRESHOLD_BULLISH:
                positions_data['sentiment_direction'] = 'BULLISH'
            elif positions_data['sentiment_score'] < config.SENTIMENT_THRESHOLD_BEARISH:
                positions_data['sentiment_direction'] = 'BEARISH'
            else:
                positions_data['sentiment_direction'] = 'NEUTRAL'
            
            logger.info(f"✓ Dati estratti per {symbol}")
            logger.info(f"  Net Position: {positions_data['net_position']:,}")
            logger.info(f"  Sentiment: {positions_data['sentiment_direction']} ({positions_data['sentiment_score']:.2f}%)")
            
            return positions_data
            
        except Exception as e:
            logger.error(f"✗ Errore durante scraping {symbol}: {str(e)}")
            return None
    
    def _extract_report_date(self):
        """Estrae la data del report dalla pagina"""
        try:
            # Prova diversi selettori
            selectors = [
                'body > div.container > h3',
                'h3',
                '.date',
                '.report-date'
            ]
            
            date_text = None
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    date_text = element.text.strip()
                    if date_text:
                        break
                except:
                    continue
            
            if date_text:
                # Cerca data in formato YYYY-MM-DD
                match = re.search(r'\d{4}-\d{2}-\d{2}', date_text)
                if match:
                    date_str = match.group(0)
                    return datetime.strptime(date_str, '%Y-%m-%d')
            
            logger.warning("Data report non trovata, uso data corrente")
            return datetime.now()
                
        except Exception as e:
            logger.warning(f"Errore estrazione data: {str(e)}")
            return datetime.now()
    
    def _extract_positions_data(self):
        """Estrae i dati delle posizioni dalla tabella"""
        try:
            # Trova la tabella
            table = self.driver.find_element(By.CLASS_NAME, 'table-striped')
            rows = table.find_elements(By.TAG_NAME, 'tr')
            
            if len(rows) < 4:
                logger.error("Tabella non ha abbastanza righe")
                return None
            
            # Prova diverse righe (alcuni report hanno strutture diverse)
            for row_index in [3, 2, 4, 1]:
                if row_index < len(rows):
                    cells = rows[row_index].find_elements(By.TAG_NAME, 'td')
                    if len(cells) >= 5:
                        break
            
            if len(cells) < 5:
                logger.error("Non trovo abbastanza celle nella tabella")
                return None
            
            # Estrai valori
            positions = {
                'non_commercial_long': self._clean_number(cells[0].text),
                'non_commercial_short': self._clean_number(cells[1].text),
                'non_commercial_spreads': self._clean_number(cells[2].text) if len(cells) > 2 else 0,
                'commercial_long': self._clean_number(cells[3].text) if len(cells) > 3 else 0,
                'commercial_short': self._clean_number(cells[4].text) if len(cells) > 4 else 0,
            }
            
            return positions
            
        except Exception as e:
            logger.error(f"Errore estrazione dati: {str(e)}")
            return None
    
    def _clean_number(self, text):
        """Pulisce e converte stringhe numeriche in interi"""
        try:
            # Rimuovi tutto tranne numeri e segno meno
            cleaned = re.sub(r'[^\d\-]', '', str(text))
            return int(cleaned) if cleaned and cleaned != '-' else 0
        except:
            return 0
    
    def close(self):
        """Chiude il driver browser"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✓ Browser chiuso")
            except:
                pass
            self.driver = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Funzione helper per compatibilità
def test_scraper():
    """Test rapido del scraper"""
    print("🧪 Test Scraper COT")
    print("="*50)
    
    scraper = COTScraper(headless=False)  # Mostra browser per debug
    
    try:
        data = scraper.scrape_cot_data('GOLD')
        
        if data:
            print("\n✅ Scraping riuscito!")
            print(f"Symbol: {data['symbol']}")
            print(f"Net Position: {data['net_position']:,}")
            print(f"Sentiment: {data['sentiment_direction']} ({data['sentiment_score']:.2f}%)")
        else:
            print("\n❌ Scraping fallito")
            
    finally:
        scraper.close()
    
    print("\n" + "="*50)


if __name__ == "__main__":
    test_scraper()