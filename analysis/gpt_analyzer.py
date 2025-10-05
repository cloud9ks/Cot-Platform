import json
import logging
from datetime import datetime
import os
import sys
from typing import Dict, List, Optional, Any

# Setup path per imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import current_config as config
except ImportError:
    # Config di fallback
    class config:
        OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
        OPENAI_MODEL = "gpt-4o-mini"
        OPENAI_MAX_TOKENS = 1500
        OPENAI_TEMPERATURE = 0.2
        SENTIMENT_THRESHOLD_BULLISH = 20
        SENTIMENT_THRESHOLD_BEARISH = -20
        ANALYSIS_OUTPUT_FOLDER = 'data/analysis_output'

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GPTAnalyzer:
    """Classe per analisi COT con GPT-4"""
    
    def __init__(self, model=None):
        """
        Inizializza l'analizzatore GPT
        
        Args:
            model: Modello GPT da usare (default: da config)
        """
        self.model = model or config.OPENAI_MODEL
        self.max_tokens = config.OPENAI_MAX_TOKENS
        self.temperature = config.OPENAI_TEMPERATURE
        self.client = None
        
        # Inizializza client OpenAI
        self._init_openai_client()
    
    def _init_openai_client(self):
        """Inizializza il client OpenAI con la nuova API - VERSIONE CORRETTA"""
        try:
            if not config.OPENAI_API_KEY:
                logger.error("OpenAI API key non configurata!")
                logger.info("Imposta OPENAI_API_KEY nel file .env")
                return
            
            try:
                from openai import OpenAI
                
                # FIX: Inizializza client SENZA parametro 'proxies'
                # La versione 1.0+ di OpenAI non supporta più questo parametro
                self.client = OpenAI(
                    api_key=config.OPENAI_API_KEY
                )
                
                logger.info("Client OpenAI inizializzato correttamente")
                
            except ImportError:
                logger.error("Libreria OpenAI non trovata. Installa con: pip install openai>=1.0.0")
            except Exception as e:
                logger.error(f"Errore inizializzazione OpenAI: {str(e)}")
                
        except Exception as e:
            logger.error(f"Errore generale inizializzazione: {str(e)}")
    
    def analyze_single_symbol(self, cot_data: Dict) -> Optional[Dict]:
        """
        Analizza i dati COT di un singolo simbolo
        
        Args:
            cot_data: Dizionario con i dati COT
            
        Returns:
            Dict con l'analisi o None in caso di errore
        """
        if not self.client:
            logger.error("Client OpenAI non disponibile")
            return self._create_fallback_analysis(cot_data)
        
        try:
            # Prepara il prompt
            prompt = self._create_single_analysis_prompt(cot_data)
            
            # Chiama GPT con nuova API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Sei un esperto analista finanziario specializzato nell'analisi COT (Commitment of Traders). 
                        Fornisci analisi professionali, precise e actionable. Rispondi sempre in formato JSON valido."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Estrai e parsa la risposta
            analysis_text = response.choices[0].message.content.strip()
            
            try:
                analysis = json.loads(analysis_text)
            except json.JSONDecodeError:
                # Se il JSON non è valido, crea struttura base
                analysis = {
                    "analysis": analysis_text,
                    "direction": "NEUTRAL",
                    "confidence": 50,
                    "market_outlook": "Analisi disponibile ma formato non standard"
                }
            
            # Aggiungi metadata
            analysis['timestamp'] = datetime.now().isoformat()
            analysis['model'] = self.model
            analysis['symbol'] = cot_data.get('symbol', 'UNKNOWN')
            
            logger.info(f"Analisi GPT completata per {cot_data.get('symbol', 'N/A')}")
            return analysis
            
        except Exception as e:
            logger.error(f"Errore analisi GPT: {str(e)}")
            return self._create_fallback_analysis(cot_data)
    
    def _create_fallback_analysis(self, cot_data: Dict) -> Dict:
        """Crea un'analisi di fallback quando GPT non è disponibile"""
        try:
            # Analisi tecnica base senza GPT
            net_position = cot_data.get('net_position', 0)
            sentiment_score = cot_data.get('sentiment_score', 0)
            
            # Determina direzione basata su sentiment
            if sentiment_score > config.SENTIMENT_THRESHOLD_BULLISH:
                direction = "BULLISH"
                confidence = min(70 + abs(sentiment_score), 95)
            elif sentiment_score < config.SENTIMENT_THRESHOLD_BEARISH:
                direction = "BEARISH"
                confidence = min(70 + abs(sentiment_score), 95)
            else:
                direction = "NEUTRAL"
                confidence = 50
            
            return {
                "direction": direction,
                "confidence": confidence,
                "market_outlook": f"Analisi tecnica automatica: Sentiment score di {sentiment_score:.2f}% indica un bias {direction.lower()}",
                "key_observations": [
                    f"Net position: {net_position:,}",
                    f"Sentiment score: {sentiment_score:.2f}%",
                    "Analisi GPT non disponibile - utilizzata analisi tecnica di base"
                ],
                "sentiment_analysis": {
                    "non_commercial": "Analisi semplificata in corso",
                    "commercial": "Dati commerciali elaborati automaticamente",
                    "divergence": "Controllo divergenze in corso"
                },
                "technical_levels": {
                    "support": "Da determinare con analisi approfondita",
                    "resistance": "Da determinare con analisi approfondita",
                    "target": "Target basato su sentiment score"
                },
                "risk_factors": [
                    "Analisi semplificata - consultare analista per dettagli",
                    "Dati basati solo su indicatori tecnici"
                ],
                "trading_bias": direction,
                "action_items": [
                    f"Monitorare posizione net: {net_position:,}",
                    f"Seguire sentiment: {direction}"
                ],
                "model": "fallback_analysis",
                "timestamp": datetime.now().isoformat(),
                "symbol": cot_data.get('symbol', 'UNKNOWN'),
                "note": "Analisi generata automaticamente - GPT non disponibile"
            }
            
        except Exception as e:
            logger.error(f"Errore creazione analisi fallback: {str(e)}")
            return {
                "direction": "NEUTRAL",
                "confidence": 0,
                "error": str(e),
                "symbol": cot_data.get('symbol', 'UNKNOWN'),
                "timestamp": datetime.now().isoformat()
            }
    
    def _create_single_analysis_prompt(self, cot_data: Dict) -> str:
        """Crea il prompt per l'analisi di un singolo simbolo"""
        
        symbol = cot_data.get('symbol', 'ASSET')
        name = cot_data.get('name', symbol)
        
        prompt = f"""
        Analizza i seguenti dati COT per {name} ({symbol}):
        
        POSIZIONI ATTUALI:
        - Non-Commercial Long: {cot_data.get('non_commercial_long', 0):,}
        - Non-Commercial Short: {cot_data.get('non_commercial_short', 0):,}
        - Commercial Long: {cot_data.get('commercial_long', 0):,}
        - Commercial Short: {cot_data.get('commercial_short', 0):,}
        
        METRICHE CALCOLATE:
        - Net Position (NC): {cot_data.get('net_position', 0):,}
        - Sentiment Score: {cot_data.get('sentiment_score', 0):.2f}%
        - Sentiment Direction: {cot_data.get('sentiment_direction', 'NEUTRAL')}
        
        RATIOS:
        - NC Long/Short Ratio: {cot_data.get('nc_long_ratio', 0):.2f}
        - Commercial Long/Short Ratio: {cot_data.get('c_long_ratio', 0):.2f}
        
        Fornisci un'analisi dettagliata in formato JSON con questa struttura:
        {{
            "market_outlook": "Descrizione della prospettiva di mercato",
            "direction": "BULLISH/BEARISH/NEUTRAL",
            "confidence": numero da 0 a 100,
            "timeframe": "SHORT/MEDIUM/LONG",
            "key_observations": [
                "Osservazione 1",
                "Osservazione 2",
                "Osservazione 3"
            ],
            "sentiment_analysis": {{
                "non_commercial": "Analisi del sentiment dei trader non commerciali",
                "commercial": "Analisi del sentiment dei trader commerciali",
                "divergence": "Eventuali divergenze tra i due gruppi"
            }},
            "technical_levels": {{
                "support": "Livello di supporto chiave",
                "resistance": "Livello di resistenza chiave",
                "target": "Target di prezzo potenziale"
            }},
            "risk_factors": [
                "Rischio 1",
                "Rischio 2"
            ],
            "trading_bias": "LONG/SHORT/NEUTRAL",
            "action_items": [
                "Azione consigliata 1",
                "Azione consigliata 2"
            ]
        }}
        """
        
        return prompt
    
    def predict_direction(self, cot_data: Dict, historical_data: List[Dict] = None) -> Dict:
        """
        Predice la direzione futura basandosi su COT e dati storici
        
        Args:
            cot_data: Dati COT attuali
            historical_data: Dati storici opzionali
            
        Returns:
            Predizione con probabilità
        """
        if not self.client:
            return self._create_fallback_prediction(cot_data)
        
        try:
            prompt = f"""
            Basandoti sui dati COT, predici la direzione più probabile per {cot_data.get('symbol', 'questo asset')}:
            
            Dati attuali:
            - Net Position: {cot_data.get('net_position', 0):,}
            - Sentiment Score: {cot_data.get('sentiment_score', 0):.2f}%
            - NC Long/Short Ratio: {cot_data.get('nc_long_ratio', 0):.2f}
            
            """
            
            if historical_data:
                prompt += f"""
                Trend storico (ultimi {len(historical_data)} periodi):
                - Net Position medio: {sum(d.get('net_position', 0) for d in historical_data) / len(historical_data):.0f}
                - Sentiment medio: {sum(d.get('sentiment_score', 0) for d in historical_data) / len(historical_data):.1f}%
                """
            
            prompt += """
            
            Rispondi in formato JSON:
            {{
                "prediction": "UP/DOWN/SIDEWAYS",
                "probability": 0-100,
                "timeframe": "1W/1M/3M",
                "reasoning": "Spiegazione breve",
                "key_levels": {{
                    "entry": "livello entry",
                    "stop_loss": "livello stop",
                    "take_profit": "livello target"
                }}
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Sei un trader esperto che usa l'analisi COT per previsioni di mercato."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            prediction = json.loads(response.choices[0].message.content.strip())
            prediction['symbol'] = cot_data.get('symbol', 'UNKNOWN')
            prediction['analysis_date'] = datetime.now().isoformat()
            
            return prediction
            
        except Exception as e:
            logger.error(f"Errore predizione: {str(e)}")
            return self._create_fallback_prediction(cot_data)
    
    def _create_fallback_prediction(self, cot_data: Dict) -> Dict:
        """Crea predizione di fallback"""
        sentiment = cot_data.get('sentiment_score', 0)
        
        if sentiment > 15:
            prediction = "UP"
            probability = min(60 + abs(sentiment), 85)
        elif sentiment < -15:
            prediction = "DOWN"
            probability = min(60 + abs(sentiment), 85)
        else:
            prediction = "SIDEWAYS"
            probability = 50
        
        return {
            "prediction": prediction,
            "probability": probability,
            "timeframe": "1W",
            "reasoning": f"Basato su sentiment score di {sentiment:.2f}%",
            "key_levels": {
                "entry": "Da determinare",
                "stop_loss": "2% dal entry",
                "take_profit": "4% dal entry"
            },
            "symbol": cot_data.get('symbol', 'UNKNOWN'),
            "analysis_date": datetime.now().isoformat(),
            "note": "Predizione automatica - GPT non disponibile"
        }


# Funzioni helper per uso standalone
def quick_analysis(symbol: str, cot_data: Dict) -> Dict:
    """
    Analisi rapida di un simbolo
    
    Args:
        symbol: Simbolo da analizzare
        cot_data: Dati COT
        
    Returns:
        Risultato analisi
    """
    analyzer = GPTAnalyzer()
    cot_data['symbol'] = symbol
    return analyzer.analyze_single_symbol(cot_data)

def generate_daily_report(all_symbols_data: Dict) -> str:
    """
    Genera report giornaliero
    
    Args:
        all_symbols_data: Dati di tutti i simboli
        
    Returns:
        Report testuale
    """
    analyzer = GPTAnalyzer()
    
    if not analyzer.client:
        # Report semplificato senza GPT
        report = f"""
        REPORT GIORNALIERO COT - {datetime.now().strftime('%Y-%m-%d')}
        ===============================================
        
        Analisi automatica di {len(all_symbols_data)} asset:
        
        """
        
        for symbol, data in all_symbols_data.items():
            sentiment = data.get('sentiment_score', 0)
            direction = "BULLISH" if sentiment > 15 else "BEARISH" if sentiment < -15 else "NEUTRAL"
            
            report += f"""
        {symbol}: {direction} (Sentiment: {sentiment:.1f}%)
        - Net Position: {data.get('net_position', 0):,}
        """
        
        report += f"""
        
        Nota: Report generato automaticamente
        OpenAI GPT non disponibile per analisi approfondita
        
        Timestamp: {datetime.now().isoformat()}
        """
        
        return report
    
    # Se GPT è disponibile, genera report completo
    try:
        prompt = f"""
        Genera un report di mercato giornaliero analizzando i seguenti dati COT:
        
        {json.dumps(all_symbols_data, indent=2)}
        
        Il report deve includere:
        1. Overview generale del mercato
        2. Asset con sentiment più forte (bullish/bearish)
        3. Divergenze interessanti
        4. Raccomandazioni operative
        """
        
        response = analyzer.client.chat.completions.create(
            model=analyzer.model,
            messages=[
                {
                    "role": "system",
                    "content": "Sei un analista di mercato che genera report giornalieri basati su dati COT."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Errore generazione report: {str(e)}")
        return "Errore generazione report"


# Test del modulo
if __name__ == "__main__":
    print("Test GPT Analyzer (Versione Corretta)")
    print("="*50)
    
    # Dati di test
    test_data = {
        'symbol': 'GOLD',
        'name': 'Gold',
        'non_commercial_long': 250000,
        'non_commercial_short': 150000,
        'commercial_long': 180000,
        'commercial_short': 280000,
        'net_position': 100000,
        'sentiment_score': 15.5,
        'sentiment_direction': 'BULLISH',
        'nc_long_ratio': 1.67,
        'c_long_ratio': 0.64
    }
    
    # Test analisi
    print("\nAnalizzando GOLD...")
    result = quick_analysis('GOLD', test_data)
    
    if result:
        print("\nAnalisi completata!")
        print(f"Direzione: {result.get('direction', 'N/A')}")
        print(f"Confidenza: {result.get('confidence', 0)}%")
        print(f"Note: {result.get('note', 'N/A')}")
    else:
        print("\nAnalisi fallita")
    
    print("\n" + "="*50)