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
        OPENAI_MAX_TOKENS = 3000  # Aggiornato per analisi dettagliate
        OPENAI_TEMPERATURE = 0.3  # Aggiornato per analisi più creative
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
            
            # Chiama GPT con nuova API - MAX_TOKENS AUMENTATO per analisi dettagliate
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Sei un esperto analista finanziario senior specializzato nell'analisi COT (Commitment of Traders) e posizionamento istituzionale.
                        Fornisci analisi professionali, precise, dettagliate e actionable per clienti professionali.
                        Usa numeri specifici, percentuali, e confronti quantitativi. Evita genericità.
                        Rispondi sempre in formato JSON valido."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Leggermente più creativo per analisi dettagliate
                max_tokens=3000,  # AUMENTATO da 1500 a 3000 per supportare analisi complete
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
        """Crea il prompt per l'analisi di un singolo simbolo - VERSIONE DETTAGLIATA"""

        symbol = cot_data.get('symbol', 'ASSET')
        name = cot_data.get('name', symbol)

        # Calcola metriche addizionali
        nc_long = cot_data.get('non_commercial_long', 0)
        nc_short = cot_data.get('non_commercial_short', 0)
        c_long = cot_data.get('commercial_long', 0)
        c_short = cot_data.get('commercial_short', 0)
        net_position = cot_data.get('net_position', 0)
        sentiment_score = cot_data.get('sentiment_score', 0)

        # Calcola % di variazione se disponibile
        prev_net = cot_data.get('prev_net_position', net_position)
        net_change = ((net_position - prev_net) / abs(prev_net) * 100) if prev_net != 0 else 0

        # Total open interest
        total_oi = nc_long + nc_short + c_long + c_short
        nc_percentage = ((nc_long + nc_short) / total_oi * 100) if total_oi > 0 else 0

        prompt = f"""
Sei un analista finanziario esperto specializzato in COT (Commitment of Traders) e analisi dei flussi istituzionali.

Analizza in dettaglio i dati COT per **{name} ({symbol})** e fornisci un'analisi OPERATIVA e PROFESSIONALE.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 DATI COT ATTUALI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Non-Commercial (Speculatori/Hedge Funds):**
• Long Positions: {nc_long:,} contratti
• Short Positions: {nc_short:,} contratti
• Net Position: {net_position:,} contratti ({net_change:+.1f}% vs periodo precedente)
• Long/Short Ratio: {(nc_long/nc_short if nc_short > 0 else 0):.2f}

**Commercial (Hedger/Produttori):**
• Long Positions: {c_long:,} contratti
• Short Positions: {c_short:,} contratti
• Net Position: {(c_long - c_short):,} contratti
• Long/Short Ratio: {(c_long/c_short if c_short > 0 else 0):.2f}

**Metriche Aggregate:**
• Sentiment Score: {sentiment_score:.2f}% (range: -100 a +100)
• Total Open Interest: {total_oi:,} contratti
• Non-Commercial % del mercato: {nc_percentage:.1f}%
• Divergenza NC vs Commercial: {abs((nc_long - nc_short) + (c_short - c_long)):,} contratti

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 RICHIESTA ANALISI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fornisci un'analisi DETTAGLIATA e OPERATIVA seguendo questa struttura JSON:

{{
    "direction": "BULLISH/BEARISH/NEUTRAL",
    "confidence": <numero 0-100>,
    "reasoning": "Sintesi dell'analisi in 2-3 frasi chiare che spiegano perché il sentiment è bullish/bearish/neutral. Menziona i dati chiave: posizioni nette, divergenze NC vs Commercial, variazioni recenti.",

    "market_outlook": "Outlook di mercato dettagliato: cosa stanno facendo i grandi player (NC), come si stanno posizionando i commerciali, quali sono le implicazioni per il prezzo nel breve-medio termine.",

    "key_factors": "Lista dei 3-4 fattori più importanti che guidano questa analisi. Es: 'NC long in aumento del 15%', 'Commercial hedge in riduzione', 'Sentiment score sopra +30 indica forte bias rialzista'",

    "positioning_analysis": {{
        "non_commercial": "Analisi dettagliata: cosa stanno facendo gli speculatori? Sono netti long o short? Di quanto? Questo è bullish o bearish? Stanno accumulando o distribuendo?",
        "commercial": "Analisi hedger: i produttori si stanno coprendo long o short? Questo conferma o contrasta il sentiment NC? Quale gruppo ha storicamente più ragione?",
        "divergence": "C'è divergenza tra NC e Commercial? Se sì, chi tende ad avere ragione storicamente? Questa divergenza è un segnale importante?"
    }},

    "quantitative_metrics": {{
        "net_position_percentile": "Stima il percentile della net position attuale (es: 'Top 20%' = molto bullish, 'Bottom 20%' = molto bearish)",
        "sentiment_strength": "Forte/Moderato/Debole in base al sentiment score",
        "positioning_extreme": "Le posizioni sono estreme? Es: 'NC long ai massimi storici' o 'Posizionamento equilibrato'"
    }},

    "scenarios": {{
        "bullish_case": "Scenario rialzista: cosa deve accadere per un movimento al rialzo? Quali livelli? Target realistici?",
        "bearish_case": "Scenario ribassista: cosa invaliderebbe la view attuale? Quali rischi al ribasso?",
        "most_likely": "BULLISH/BEARISH/NEUTRAL - quale scenario è più probabile dato il COT?"
    }},

    "risks": "Lista 2-3 rischi principali: posizionamento troppo affollato? Divergenze? Eventi macro? Inversioni storiche?",

    "actionable_insights": [
        "Insight 1: cosa fare operativamente",
        "Insight 2: livelli da monitorare",
        "Insight 3: segnali di conferma o invalidazione"
    ],

    "timeframe": "SHORT_TERM/MEDIUM_TERM/LONG_TERM - orizzonte temporale dell'analisi",

    "technical_bias": "STRONGLY_BULLISH/BULLISH/NEUTRAL/BEARISH/STRONGLY_BEARISH"
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ IMPORTANTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Sii SPECIFICO: usa i numeri effettivi, non genericità
2. Sii OPERATIVO: fornisci insight utilizzabili, non ovvietà
3. Sii CHIARO: evita gergo eccessivo, spiega in termini semplici
4. Considera il CONTESTO: sentiment score, net position, divergenze
5. Fornisci VALORE: l'analisi deve essere vendibile a un cliente professionale

RISPONDI SOLO CON IL JSON, NIENT'ALTRO.
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