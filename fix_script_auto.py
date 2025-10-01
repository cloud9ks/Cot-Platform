"""
Script per pulire automaticamente app_complete.py
Rimuove il vecchio codice di scraping e inserisce quello nuovo
"""

def fix_app_complete():
    # Leggi il file
    with open('app_complete.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verifica se c'è ancora il vecchio codice
    if "Usando metodo scraping vecchio" in content:
        print("❌ TROVATO vecchio codice da rimuovere!")
        
        # Trova l'inizio della funzione scrape_cot_data
        start_marker = "def scrape_cot_data(symbol):"
        
        if start_marker not in content:
            print("❌ Non trovo la funzione scrape_cot_data!")
            return False
        
        # Trova dove inizia
        start_idx = content.find(start_marker)
        
        # Trova la fine (prossima def o fine file)
        # Cerca la prossima funzione che inizia con def e non è indentata
        remaining = content[start_idx + len(start_marker):]
        lines = remaining.split('\n')
        
        end_line_idx = 0
        for i, line in enumerate(lines):
            # Salta righe vuote e commenti
            if not line.strip() or line.strip().startswith('#'):
                continue
            # Se troviamo una nuova def non indentata, ci fermiamo
            if line.startswith('def ') and i > 0:
                end_line_idx = i
                break
        
        if end_line_idx > 0:
            # Calcola l'indice esatto nel contenuto
            end_idx = start_idx + len(start_marker) + len('\n'.join(lines[:end_line_idx]))
            
            # Prepara il nuovo codice
            new_function = '''def scrape_cot_data(symbol):
    """
    Scraping dati COT per un simbolo specifico - VERSIONE CORRETTA CON LOCK
    FIX: Usa SOLO il nuovo COTScraper, rimosso completamente il fallback vecchio
    """
    
    # Lock globale per evitare scraping simultanei
    import threading
    if not hasattr(scrape_cot_data, 'lock'):
        scrape_cot_data.lock = threading.Lock()
    
    # Prova ad acquisire il lock (non blocca)
    acquired = scrape_cot_data.lock.acquire(blocking=False)
    
    if not acquired:
        logger.warning(f"⚠️ Scraping già in corso, richiesta saltata per {symbol}")
        return None
    
    try:
        logger.info(f"🔄 Avvio scraping per {symbol}...")
        
        # Importa il nuovo scraper
        try:
            from collectors.cot_scraper import COTScraper
        except ImportError as e:
            logger.error(f"❌ Modulo COTScraper non trovato: {e}")
            return None
        
        # Usa il nuovo scraper con context manager (chiude automaticamente)
        with COTScraper(headless=True) as scraper:
            data = scraper.scrape_cot_data(symbol)
            
            if data:
                # Ricalcola sentiment con la funzione corretta
                data['sentiment_score'] = calculate_cot_sentiment(
                    data['non_commercial_long'],
                    data['non_commercial_short'], 
                    data['commercial_long'],
                    data['commercial_short']
                )
                logger.info(f"✅ Scraping completato per {symbol}: sentiment {data['sentiment_score']:.2f}%")
                return data
            else:
                logger.warning(f"⚠️ Scraper ha ritornato None per {symbol}")
                return None
    
    except Exception as e:
        logger.error(f"❌ Errore scraping {symbol}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None
    
    finally:
        # IMPORTANTE: Rilascia sempre il lock
        try:
            scrape_cot_data.lock.release()
            logger.info(f"🔓 Lock rilasciato per {symbol}")
        except:
            pass

'''
            
            # Ricostruisci il file
            new_content = content[:start_idx] + new_function + content[end_idx:]
            
            # Salva backup
            with open('app_complete.py.backup', 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ Backup salvato in app_complete.py.backup")
            
            # Salva il nuovo file
            with open('app_complete.py', 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("✅ File aggiornato!")
            print("\nOra esegui:")
            print("git add app_complete.py")
            print('git commit -m "Fix: Rimosso vecchio fallback scraping"')
            print("git push origin main")
            
            return True
        else:
            print("❌ Non riesco a trovare la fine della funzione")
            return False
    else:
        print("✅ Nessun vecchio codice trovato - sembra già aggiornato!")
        
        # Verifica che ci sia il nuovo
        if "from collectors.cot_scraper import COTScraper" in content:
            print("✅ Nuovo codice presente!")
            return True
        else:
            print("⚠️ Non trovo né vecchio né nuovo codice - controlla manualmente")
            return False

if __name__ == "__main__":
    print("🔧 Fix automatico app_complete.py")
    print("="*50)
    success = fix_app_complete()
    print("="*50)
    if success:
        print("✅ Fix completato!")
    else:
        print("❌ Fix fallito - controlla manualmente")
