
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
import os
import sys
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Setup path per imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import current_config as config
from collectors.cot_scraper import COTScraper
from collectors.data_processor import COTDataProcessor
from analysis.gpt_analyzer import GPTAnalyzer
from analysis.predictions import COTPredictionSystem

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class COTScheduler:
    """Sistema di scheduling per aggiornamenti automatici"""
    
    def __init__(self, db=None):
        """
        Inizializza lo scheduler
        
        Args:
            db: Istanza del database SQLAlchemy (opzionale)
        """
        self.scheduler = BackgroundScheduler(timezone=config.SCHEDULER_TIMEZONE)
        self.db = db
        self.scraper = None
        self.processor = COTDataProcessor()
        self.analyzer = GPTAnalyzer() if config.OPENAI_API_KEY else None
        self.predictor = COTPredictionSystem()
        self.last_update = None
        self.update_history = []
        
    def start(self):
        """Avvia lo scheduler"""
        try:
            # Aggiungi job per scraping COT
            self.scheduler.add_job(
                func=self.scheduled_cot_update,
                trigger=CronTrigger(
                    day_of_week=config.COT_UPDATE_DAY,
                    hour=config.COT_UPDATE_HOUR,
                    minute=config.COT_UPDATE_MINUTE
                ),
                id='cot_weekly_update',
                name='Aggiornamento settimanale COT',
                replace_existing=True
            )
            
            # Aggiungi job per analisi giornaliera
            self.scheduler.add_job(
                func=self.daily_analysis,
                trigger=CronTrigger(hour=9, minute=0),  # Ogni giorno alle 9:00
                id='daily_analysis',
                name='Analisi giornaliera',
                replace_existing=True
            )
            
            # Aggiungi job per backup database
            self.scheduler.add_job(
                func=self.backup_database,
                trigger=CronTrigger(hour=2, minute=0),  # Ogni notte alle 2:00
                id='nightly_backup',
                name='Backup notturno database',
                replace_existing=True
            )
            
            # Aggiungi job per pulizia logs
            self.scheduler.add_job(
                func=self.cleanup_old_files,
                trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),  # Domenica alle 3:00
                id='weekly_cleanup',
                name='Pulizia settimanale file',
                replace_existing=True
            )
            
            # Avvia scheduler
            self.scheduler.start()
            logger.info("✓ Scheduler avviato con successo")
            
            # Log dei job schedulati
            jobs = self.scheduler.get_jobs()
            logger.info(f"Job schedulati: {len(jobs)}")
            for job in jobs:
                logger.info(f"  - {job.name}: {job.next_run_time}")
            
            return True
            
        except Exception as e:
            logger.error(f"Errore avvio scheduler: {str(e)}")
            return False
    
    def stop(self):
        """Ferma lo scheduler"""
        try:
            self.scheduler.shutdown(wait=True)
            logger.info("✓ Scheduler fermato")
        except Exception as e:
            logger.error(f"Errore stop scheduler: {str(e)}")
    
    def scheduled_cot_update(self):
        """Aggiornamento schedulato dei dati COT"""
        logger.info("="*50)
        logger.info(f"🔄 Avvio aggiornamento COT schedulato: {datetime.now()}")
        logger.info("="*50)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'success': [],
            'failed': [],
            'predictions': []
        }
        
        try:
            # Inizializza scraper
            self.scraper = COTScraper()
            
            # Scraping per tutti i simboli
            for symbol in config.COT_SYMBOLS.keys():
                try:
                    logger.info(f"\n📊 Processing {symbol}...")
                    
                    # 1. Scraping dati
                    cot_data = self.scraper.scrape_cot_data(symbol)
                    
                    if cot_data:
                        # 2. Salva nel database se disponibile
                        if self.db:
                            self._save_to_database(cot_data)
                        
                        # 3. Processa i dati
                        self.processor.load_data(cot_data)
                        self.processor.calculate_technical_indicators()
                        
                        # 4. Genera previsione
                        prediction = self.predictor.generate_prediction(cot_data)
                        results['predictions'].append(prediction)
                        
                        # 5. Analisi GPT se disponibile
                        if self.analyzer:
                            gpt_analysis = self.analyzer.analyze_single_symbol(cot_data)
                            if gpt_analysis:
                                cot_data['gpt_analysis'] = gpt_analysis
                        
                        results['success'].append(symbol)
                        logger.info(f"✓ {symbol} completato")
                    else:
                        results['failed'].append(symbol)
                        logger.warning(f"✗ {symbol} fallito")
                    
                except Exception as e:
                    logger.error(f"Errore processing {symbol}: {str(e)}")
                    results['failed'].append(symbol)
                
                # Pausa tra richieste
                import time
                time.sleep(5)
            
            # Chiudi scraper
            if self.scraper:
                self.scraper.close()
            
            # Genera report
            self._generate_update_report(results)
            
            # Invia notifiche se configurate
            if config.ENABLE_EMAIL_ALERTS:
                self._send_email_notification(results)
            
            # Salva risultati
            self.last_update = results
            self.update_history.append(results)
            
            logger.info(f"\n✓ Aggiornamento completato: {len(results['success'])}/{len(config.COT_SYMBOLS)} simboli")
            
        except Exception as e:
            logger.error(f"Errore durante aggiornamento schedulato: {str(e)}")
        finally:
            if self.scraper:
                self.scraper.close()
    
    def daily_analysis(self):
        """Analisi giornaliera dei dati esistenti"""
        logger.info(f"📈 Avvio analisi giornaliera: {datetime.now()}")
        
        try:
            # Carica ultimi dati dal database
            if self.db:
                recent_data = self._load_recent_data()
                
                if recent_data:
                    # Genera analisi per ogni simbolo
                    for symbol, data in recent_data.items():
                        # Processa indicatori tecnici
                        self.processor.load_data(data)
                        self.processor.calculate_technical_indicators()
                        
                        # Rileva pattern
                        patterns = self.processor.detect_patterns()
                        
                        # Genera segnali
                        signals = self.processor.generate_signals()
                        
                        logger.info(f"{symbol}: {signals.get('signal', 'N/A')} ({signals.get('confidence', 0):.0f}%)")
                
                # Genera report giornaliero
                if self.analyzer:
                    report = self.analyzer.generate_market_report(recent_data)
                    logger.info("✓ Report giornaliero generato")
            
        except Exception as e:
            logger.error(f"Errore analisi giornaliera: {str(e)}")
    
    def backup_database(self):
        """Backup del database"""
        try:
            if not self.db:
                return
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join('backups', 'database')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Per SQLite
            if 'sqlite' in config.SQLALCHEMY_DATABASE_URI:
                import shutil
                db_path = config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
                backup_path = os.path.join(backup_dir, f'cot_data_backup_{timestamp}.db')
                shutil.copy2(db_path, backup_path)
                logger.info(f"✓ Database backup salvato: {backup_path}")
            
            # Per PostgreSQL (richiede pg_dump)
            elif 'postgresql' in config.SQLALCHEMY_DATABASE_URI:
                import subprocess
                backup_path = os.path.join(backup_dir, f'cot_data_backup_{timestamp}.sql')
                cmd = f"pg_dump {config.SQLALCHEMY_DATABASE_URI} > {backup_path}"
                subprocess.run(cmd, shell=True)
                logger.info(f"✓ Database backup salvato: {backup_path}")
                
        except Exception as e:
            logger.error(f"Errore backup database: {str(e)}")
    
    def cleanup_old_files(self):
        """Pulizia file vecchi"""
        try:
            folders_to_clean = [
                config.CSV_OUTPUT_FOLDER,
                config.ANALYSIS_OUTPUT_FOLDER,
                'logs'
            ]
            
            days_to_keep = 30
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            for folder in folders_to_clean:
                if os.path.exists(folder):
                    for filename in os.listdir(folder):
                        filepath = os.path.join(folder, filename)
                        if os.path.isfile(filepath):
                            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                            if file_time < cutoff_date:
                                os.remove(filepath)
                                logger.info(f"Rimosso file vecchio: {filename}")
            
            logger.info("✓ Pulizia file completata")
            
        except Exception as e:
            logger.error(f"Errore pulizia file: {str(e)}")
    
    def _save_to_database(self, cot_data):
        """Salva dati nel database"""
        if not self.db:
            return
        
        try:
            from app_complete import COTData
            
            # Controlla se esiste già
            existing = self.db.session.query(COTData).filter_by(
                symbol=cot_data['symbol'],
                date=cot_data['date']
            ).first()
            
            if not existing:
                entry = COTData(**cot_data)
                self.db.session.add(entry)
                self.db.session.commit()
                logger.info(f"✓ Salvato nel database: {cot_data['symbol']}")
            else:
                logger.info(f"- {cot_data['symbol']} già presente nel database")
                
        except Exception as e:
            logger.error(f"Errore salvataggio database: {str(e)}")
            self.db.session.rollback()
    
    def _load_recent_data(self):
        """Carica dati recenti dal database"""
        if not self.db:
            return {}
        
        try:
            from app_complete import COTData
            
            recent_data = {}
            
            for symbol in config.COT_SYMBOLS.keys():
                data = self.db.session.query(COTData).filter_by(
                    symbol=symbol
                ).order_by(COTData.date.desc()).limit(20).all()
                
                if data:
                    recent_data[symbol] = [
                        {
                            'date': d.date,
                            'net_position': d.net_position,
                            'sentiment_score': d.sentiment_score,
                            'non_commercial_long': d.non_commercial_long,
                            'non_commercial_short': d.non_commercial_short,
                            'commercial_long': d.commercial_long,
                            'commercial_short': d.commercial_short
                        }
                        for d in data
                    ]
            
            return recent_data
            
        except Exception as e:
            logger.error(f"Errore caricamento dati: {str(e)}")
            return {}
    
    def _generate_update_report(self, results):
        """Genera report dell'aggiornamento"""
        try:
            os.makedirs('reports', exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = os.path.join('reports', f'update_report_{timestamp}.json')
            
            with open(report_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"✓ Report salvato: {report_path}")
            
        except Exception as e:
            logger.error(f"Errore generazione report: {str(e)}")
    
    def _send_email_notification(self, results):
        """Invia notifica email"""
        if not config.EMAIL_USERNAME or not config.EMAIL_PASSWORD:
            return
        
        try:
            # Prepara messaggio
            msg = MIMEMultipart()
            msg['From'] = config.EMAIL_USERNAME
            msg['To'] = ', '.join(config.EMAIL_RECIPIENTS)
            msg['Subject'] = f"COT Update Report - {datetime.now().strftime('%Y-%m-%d')}"
            
            # Corpo email
            body = f"""
            COT Update Report
            =================
            
            Timestamp: {results['timestamp']}
            
            Successi: {len(results['success'])}
            Falliti: {len(results['failed'])}
            
            Simboli aggiornati:
            {', '.join(results['success'])}
            
            Previsioni principali:
            """
            
            for pred in results.get('predictions', [])[:5]:
                body += f"\n- {pred.get('symbol')}: {pred.get('direction')} ({pred.get('confidence', 0):.0f}%)"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Invia email
            with smtplib.SMTP(config.EMAIL_SMTP_SERVER, config.EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(config.EMAIL_USERNAME, config.EMAIL_PASSWORD)
                server.send_message(msg)
            
            logger.info("✓ Notifica email inviata")
            
        except Exception as e:
            logger.error(f"Errore invio email: {str(e)}")
    
    def add_custom_job(self, func, trigger, job_id, name=None):
        """
        Aggiunge un job personalizzato
        
        Args:
            func: Funzione da eseguire
            trigger: Trigger APScheduler
            job_id: ID univoco del job
            name: Nome descrittivo
        """
        try:
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name=name or job_id,
                replace_existing=True
            )
            logger.info(f"✓ Job personalizzato aggiunto: {name or job_id}")
            return True
        except Exception as e:
            logger.error(f"Errore aggiunta job: {str(e)}")
            return False
    
    def remove_job(self, job_id):
        """Rimuove un job"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"✓ Job rimosso: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Errore rimozione job: {str(e)}")
            return False
    
    def get_jobs_info(self):
        """Ottiene informazioni sui job attivi"""
        jobs = self.scheduler.get_jobs()
        return [
            {
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            }
            for job in jobs
        ]
    
    def run_job_now(self, job_id):
        """Esegue immediatamente un job"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now())
                logger.info(f"✓ Job {job_id} schedulato per esecuzione immediata")
                return True
            else:
                logger.error(f"Job {job_id} non trovato")
                return False
        except Exception as e:
            logger.error(f"Errore esecuzione job: {str(e)}")
            return False


# Istanza globale dello scheduler
scheduler_instance = None

def init_scheduler(db=None):
    """Inizializza lo scheduler globale"""
    global scheduler_instance
    scheduler_instance = COTScheduler(db)
    return scheduler_instance

def get_scheduler():
    """Ottiene l'istanza dello scheduler"""
    return scheduler_instance


# Test del modulo
if __name__ == "__main__":
    print("⏰ Test Scheduler System")
    print("="*50)
    
    # Inizializza scheduler
    scheduler = COTScheduler()
    
    # Avvia
    scheduler.start()
    
    # Mostra job
    jobs = scheduler.get_jobs_info()
    print(f"\n📋 Job configurati: {len(jobs)}")
    for job in jobs:
        print(f"  - {job['name']}: Prossima esecuzione {job['next_run']}")
    
    print("\nScheduler in esecuzione. Premi Ctrl+C per fermare.")
    
    try:
        # Mantieni in esecuzione
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n\nArresto scheduler...")
        scheduler.stop()
        print("✓ Scheduler fermato")
    
    print("\n" + "="*50)