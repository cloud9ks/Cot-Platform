
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
import os
import sys
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Setup path per imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import current_config as config

# Import moduli interni
try:
    from analysis.gpt_analyzer import GPTAnalyzer
except:
    GPTAnalyzer = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class COTPredictionSystem:
    """Sistema completo di previsioni basato su dati COT"""
    
    def __init__(self):
        """Inizializza il sistema di previsioni"""
        self.predictions_history = []
        self.accuracy_metrics = {}
        self.gpt_analyzer = GPTAnalyzer() if GPTAnalyzer else None
        
    def generate_prediction(self, 
                          current_data: Dict,
                          historical_data: List[Dict] = None,
                          use_ai: bool = True) -> Dict:
        """
        Genera una previsione completa
        
        Args:
            current_data: Dati COT attuali
            historical_data: Dati storici opzionali
            use_ai: Se True, usa anche GPT per l'analisi
            
        Returns:
            Dict con previsione completa
        """
        try:
            prediction = {
                'symbol': current_data.get('symbol', 'UNKNOWN'),
                'timestamp': datetime.now().isoformat(),
                'data_date': current_data.get('date', datetime.now()).isoformat() if isinstance(current_data.get('date'), datetime) else str(current_data.get('date', '')),
                'components': {}
            }
            
            # 1. Analisi Tecnica Base
            technical_prediction = self._technical_analysis(current_data, historical_data)
            prediction['components']['technical'] = technical_prediction
            
            # 2. Analisi Sentiment
            sentiment_prediction = self._sentiment_analysis(current_data)
            prediction['components']['sentiment'] = sentiment_prediction
            
            # 3. Analisi Pattern
            pattern_prediction = self._pattern_analysis(current_data, historical_data)
            prediction['components']['patterns'] = pattern_prediction
            
            # 4. Analisi Momentum
            momentum_prediction = self._momentum_analysis(current_data, historical_data)
            prediction['components']['momentum'] = momentum_prediction
            
            # 5. Analisi AI (se disponibile)
            if use_ai and self.gpt_analyzer and config.OPENAI_API_KEY:
                ai_prediction = self.gpt_analyzer.predict_direction(current_data, historical_data)
                prediction['components']['ai'] = ai_prediction
            else:
                prediction['components']['ai'] = {'status': 'Not available'}
            
            # 6. Combina tutte le previsioni
            final_prediction = self._combine_predictions(prediction['components'])
            prediction.update(final_prediction)
            
            # 7. Calcola livelli di trading
            trading_levels = self._calculate_trading_levels(current_data, prediction)
            prediction['trading_levels'] = trading_levels
            
            # 8. Risk assessment
            risk_assessment = self._assess_risk(current_data, prediction)
            prediction['risk'] = risk_assessment
            
            # Salva nella storia
            self.predictions_history.append(prediction)
            
            logger.info(f"✓ Previsione generata per {prediction['symbol']}: {prediction['direction']} ({prediction['confidence']:.1f}%)")
            
            return prediction
            
        except Exception as e:
            logger.error(f"Errore generazione previsione: {str(e)}")
            return {
                'error': str(e),
                'symbol': current_data.get('symbol', 'UNKNOWN'),
                'direction': 'UNDEFINED',
                'confidence': 0
            }
    
    def _technical_analysis(self, current_data: Dict, historical_data: List[Dict] = None) -> Dict:
        """Analisi tecnica basata su COT"""
        try:
            analysis = {
                'direction': 'NEUTRAL',
                'strength': 0,
                'signals': []
            }
            
            # Net position analysis
            net_position = current_data.get('net_position', 0)
            
            if historical_data and len(historical_data) > 0:
                # Calcola medie
                net_positions = [d.get('net_position', 0) for d in historical_data]
                avg_net = np.mean(net_positions)
                std_net = np.std(net_positions)
                
                # Z-score
                if std_net > 0:
                    z_score = (net_position - avg_net) / std_net
                    
                    if z_score > 1.5:
                        analysis['direction'] = 'BULLISH'
                        analysis['strength'] = min(abs(z_score) * 33, 100)
                        analysis['signals'].append(f"Net position {z_score:.1f} deviazioni sopra la media")
                    elif z_score < -1.5:
                        analysis['direction'] = 'BEARISH'
                        analysis['strength'] = min(abs(z_score) * 33, 100)
                        analysis['signals'].append(f"Net position {z_score:.1f} deviazioni sotto la media")
                    
                    analysis['z_score'] = z_score
                
                # Trend analysis
                recent_avg = np.mean(net_positions[-5:]) if len(net_positions) >= 5 else avg_net
                if recent_avg > avg_net * 1.1:
                    analysis['trend'] = 'ASCENDING'
                    analysis['signals'].append("Trend ascendente confermato")
                elif recent_avg < avg_net * 0.9:
                    analysis['trend'] = 'DESCENDING'
                    analysis['signals'].append("Trend discendente confermato")
                else:
                    analysis['trend'] = 'LATERAL'
            else:
                # Analisi solo su dati correnti
                if net_position > config.NET_POSITION_EXTREME_HIGH:
                    analysis['direction'] = 'BULLISH'
                    analysis['strength'] = 75
                    analysis['signals'].append("Net position estremamente long")
                elif net_position < config.NET_POSITION_EXTREME_LOW:
                    analysis['direction'] = 'BEARISH'
                    analysis['strength'] = 75
                    analysis['signals'].append("Net position estremamente short")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Errore analisi tecnica: {str(e)}")
            return {'direction': 'NEUTRAL', 'strength': 0}
    
    def _sentiment_analysis(self, current_data: Dict) -> Dict:
        """Analisi del sentiment basata su COT"""
        try:
            sentiment_score = current_data.get('sentiment_score', 0)
            sentiment_direction = current_data.get('sentiment_direction', 'NEUTRAL')
            
            analysis = {
                'direction': sentiment_direction,
                'score': sentiment_score,
                'interpretation': '',
                'strength': 0
            }
            
            # Interpreta il sentiment
            if sentiment_score > config.SENTIMENT_THRESHOLD_BULLISH:
                analysis['interpretation'] = 'Sentiment fortemente rialzista'
                analysis['strength'] = min(sentiment_score, 100)
            elif sentiment_score < config.SENTIMENT_THRESHOLD_BEARISH:
                analysis['interpretation'] = 'Sentiment fortemente ribassista'
                analysis['strength'] = min(abs(sentiment_score), 100)
            else:
                analysis['interpretation'] = 'Sentiment neutrale/incerto'
                analysis['strength'] = 50
            
            # Analizza divergenze
            nc_ratio = current_data.get('nc_long_ratio', 1)
            c_ratio = current_data.get('c_long_ratio', 1)
            
            if nc_ratio > 1.5 and c_ratio < 0.7:
                analysis['divergence'] = 'BEARISH_DIVERGENCE'
                analysis['divergence_note'] = 'Non-commercial long mentre commercial short (possibile top)'
            elif nc_ratio < 0.7 and c_ratio > 1.5:
                analysis['divergence'] = 'BULLISH_DIVERGENCE'
                analysis['divergence_note'] = 'Non-commercial short mentre commercial long (possibile bottom)'
            else:
                analysis['divergence'] = 'NO_DIVERGENCE'
            
            return analysis
            
        except Exception as e:
            logger.error(f"Errore analisi sentiment: {str(e)}")
            return {'direction': 'NEUTRAL', 'score': 0, 'strength': 0}
    
    def _pattern_analysis(self, current_data: Dict, historical_data: List[Dict] = None) -> Dict:
        """Riconoscimento pattern nei dati COT"""
        try:
            patterns = {
                'identified': [],
                'strength': 0,
                'direction_hint': 'NEUTRAL'
            }
            
            if not historical_data or len(historical_data) < 10:
                return patterns
            
            # Prepara dati per analisi
            net_positions = [d.get('net_position', 0) for d in historical_data]
            net_positions.append(current_data.get('net_position', 0))
            
            # Pattern 1: Double Top/Bottom
            if len(net_positions) >= 20:
                recent = net_positions[-20:]
                max_val = max(recent)
                min_val = min(recent)
                
                # Double Top
                peaks = [i for i, v in enumerate(recent) if v > max_val * 0.95]
                if len(peaks) >= 2 and peaks[-1] - peaks[0] > 5:
                    patterns['identified'].append('DOUBLE_TOP')
                    patterns['direction_hint'] = 'BEARISH'
                    patterns['strength'] = 70
                
                # Double Bottom
                troughs = [i for i, v in enumerate(recent) if v < min_val * 1.05]
                if len(troughs) >= 2 and troughs[-1] - troughs[0] > 5:
                    patterns['identified'].append('DOUBLE_BOTTOM')
                    patterns['direction_hint'] = 'BULLISH'
                    patterns['strength'] = 70
            
            # Pattern 2: Breakout
            if len(net_positions) >= 10:
                recent_range = max(net_positions[-10:-1]) - min(net_positions[-10:-1])
                current = net_positions[-1]
                
                if current > max(net_positions[-10:-1]) + recent_range * 0.2:
                    patterns['identified'].append('BULLISH_BREAKOUT')
                    patterns['direction_hint'] = 'BULLISH'
                    patterns['strength'] = 80
                elif current < min(net_positions[-10:-1]) - recent_range * 0.2:
                    patterns['identified'].append('BEARISH_BREAKOUT')
                    patterns['direction_hint'] = 'BEARISH'
                    patterns['strength'] = 80
            
            # Pattern 3: Accumulation/Distribution
            if len(net_positions) >= 15:
                recent = net_positions[-15:]
                volatility = np.std(recent)
                avg_vol = np.std(net_positions[:-15]) if len(net_positions) > 30 else volatility
                
                if volatility < avg_vol * 0.5 and abs(recent[-1] - recent[0]) < volatility:
                    if current_data.get('sentiment_score', 0) > 0:
                        patterns['identified'].append('ACCUMULATION')
                        patterns['direction_hint'] = 'BULLISH'
                    else:
                        patterns['identified'].append('DISTRIBUTION')
                        patterns['direction_hint'] = 'BEARISH'
                    patterns['strength'] = 60
            
            return patterns
            
        except Exception as e:
            logger.error(f"Errore analisi pattern: {str(e)}")
            return {'identified': [], 'strength': 0, 'direction_hint': 'NEUTRAL'}
    
    def _momentum_analysis(self, current_data: Dict, historical_data: List[Dict] = None) -> Dict:
        """Analisi del momentum"""
        try:
            momentum = {
                'direction': 'NEUTRAL',
                'strength': 0,
                'roc': 0,  # Rate of change
                'acceleration': 'STABLE'
            }
            
            if not historical_data or len(historical_data) < 2:
                return momentum
            
            # Calcola ROC
            current_net = current_data.get('net_position', 0)
            
            # ROC a 1 periodo
            if len(historical_data) >= 1:
                prev_net = historical_data[-1].get('net_position', 0)
                if prev_net != 0:
                    momentum['roc'] = ((current_net - prev_net) / abs(prev_net)) * 100
            
            # ROC a 5 periodi
            if len(historical_data) >= 5:
                old_net = historical_data[-5].get('net_position', 0)
                if old_net != 0:
                    momentum['roc5'] = ((current_net - old_net) / abs(old_net)) * 100
            
            # Determina direzione momentum
            if momentum['roc'] > 5:
                momentum['direction'] = 'BULLISH'
                momentum['strength'] = min(abs(momentum['roc']) * 2, 100)
            elif momentum['roc'] < -5:
                momentum['direction'] = 'BEARISH'
                momentum['strength'] = min(abs(momentum['roc']) * 2, 100)
            
            # Calcola accelerazione
            if len(historical_data) >= 3:
                recent_changes = []
                for i in range(1, min(4, len(historical_data))):
                    if i < len(historical_data):
                        change = historical_data[-i].get('net_position', 0) - historical_data[-i-1].get('net_position', 0)
                        recent_changes.append(change)
                
                if recent_changes:
                    current_change = current_net - historical_data[-1].get('net_position', 0)
                    avg_change = np.mean(recent_changes)
                    
                    if current_change > avg_change * 1.5:
                        momentum['acceleration'] = 'ACCELERATING'
                    elif current_change < avg_change * 0.5:
                        momentum['acceleration'] = 'DECELERATING'
            
            return momentum
            
        except Exception as e:
            logger.error(f"Errore analisi momentum: {str(e)}")
            return {'direction': 'NEUTRAL', 'strength': 0, 'roc': 0}
    
    def _combine_predictions(self, components: Dict) -> Dict:
        """Combina tutte le componenti in una previsione finale"""
        try:
            # Pesi per ogni componente
            weights = {
                'technical': 0.25,
                'sentiment': 0.25,
                'patterns': 0.20,
                'momentum': 0.15,
                'ai': 0.15
            }
            
            # Mappa direzioni a valori numerici
            direction_map = {
                'BULLISH': 1,
                'BEARISH': -1,
                'NEUTRAL': 0,
                'UP': 1,
                'DOWN': -1,
                'SIDEWAYS': 0
            }
            
            weighted_sum = 0
            total_confidence = 0
            valid_components = 0
            
            for component, weight in weights.items():
                if component in components and components[component]:
                    comp_data = components[component]
                    
                    # Estrai direzione
                    direction = comp_data.get('direction', comp_data.get('prediction', 'NEUTRAL'))
                    direction_value = direction_map.get(direction, 0)
                    
                    # Estrai confidenza/strength
                    confidence = comp_data.get('confidence', comp_data.get('strength', 50))
                    
                    # Aggiungi al calcolo pesato
                    if direction_value != 0 or confidence > 0:
                        weighted_sum += direction_value * weight * (confidence / 100)
                        total_confidence += confidence * weight
                        valid_components += weight
            
            # Calcola risultato finale
            if valid_components > 0:
                # Direzione finale
                if weighted_sum > 0.2:
                    final_direction = 'BULLISH'
                elif weighted_sum < -0.2:
                    final_direction = 'BEARISH'
                else:
                    final_direction = 'NEUTRAL'
                
                # Confidenza finale
                final_confidence = (total_confidence / valid_components) if valid_components > 0 else 50
                
                # Timeframe (basato principalmente su AI se disponibile)
                if 'ai' in components and 'timeframe' in components['ai']:
                    timeframe = components['ai']['timeframe']
                else:
                    timeframe = '1W'  # Default 1 settimana
                
                return {
                    'direction': final_direction,
                    'confidence': min(final_confidence, 100),
                    'strength': abs(weighted_sum) * 100,
                    'timeframe': timeframe,
                    'weighted_score': weighted_sum
                }
            else:
                return {
                    'direction': 'NEUTRAL',
                    'confidence': 50,
                    'strength': 0,
                    'timeframe': '1W',
                    'weighted_score': 0
                }
                
        except Exception as e:
            logger.error(f"Errore combinazione previsioni: {str(e)}")
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'strength': 0,
                'timeframe': 'UNKNOWN'
            }
    
    def _calculate_trading_levels(self, current_data: Dict, prediction: Dict) -> Dict:
        """Calcola livelli di trading suggeriti"""
        try:
            # Questo è semplificato - in produzione useresti dati di prezzo reali
            base_value = 100  # Valore base simbolico
            
            levels = {
                'entry': base_value,
                'stop_loss': 0,
                'take_profit_1': 0,
                'take_profit_2': 0,
                'take_profit_3': 0,
                'risk_reward_ratio': 0
            }
            
            # Calcola in base alla direzione
            if prediction['direction'] == 'BULLISH':
                risk_percent = 2  # 2% di risk
                reward_percent = risk_percent * 2  # Risk/reward 1:2
                
                levels['stop_loss'] = base_value * (1 - risk_percent/100)
                levels['take_profit_1'] = base_value * (1 + reward_percent/100)
                levels['take_profit_2'] = base_value * (1 + reward_percent*1.5/100)
                levels['take_profit_3'] = base_value * (1 + reward_percent*2/100)
                
            elif prediction['direction'] == 'BEARISH':
                risk_percent = 2
                reward_percent = risk_percent * 2
                
                levels['stop_loss'] = base_value * (1 + risk_percent/100)
                levels['take_profit_1'] = base_value * (1 - reward_percent/100)
                levels['take_profit_2'] = base_value * (1 - reward_percent*1.5/100)
                levels['take_profit_3'] = base_value * (1 - reward_percent*2/100)
            
            # Calcola risk/reward
            if levels['stop_loss'] != 0 and levels['stop_loss'] != base_value:
                risk = abs(base_value - levels['stop_loss'])
                reward = abs(levels['take_profit_1'] - base_value)
                levels['risk_reward_ratio'] = reward / risk if risk > 0 else 0
            
            return levels
            
        except Exception as e:
            logger.error(f"Errore calcolo livelli: {str(e)}")
            return {}
    
    def _assess_risk(self, current_data: Dict, prediction: Dict) -> Dict:
        """Valuta il rischio della previsione"""
        try:
            risk = {
                'level': 'MEDIUM',
                'score': 50,
                'factors': []
            }
            
            risk_score = 0
            
            # Factor 1: Confidenza della previsione
            confidence = prediction.get('confidence', 50)
            if confidence < 60:
                risk_score += 30
                risk['factors'].append('Bassa confidenza nella previsione')
            
            # Factor 2: Posizioni estreme
            net_position = current_data.get('net_position', 0)
            if abs(net_position) > config.NET_POSITION_EXTREME_HIGH:
                risk_score += 20
                risk['factors'].append('Posizioni a livelli estremi')
            
            # Factor 3: Divergenze
            if 'sentiment' in prediction.get('components', {}):
                if prediction['components']['sentiment'].get('divergence') != 'NO_DIVERGENCE':
                    risk_score += 15
                    risk['factors'].append('Presenza di divergenze')
            
            # Factor 4: Volatilità
            if 'components' in prediction:
                tech = prediction['components'].get('technical', {})
                if 'z_score' in tech and abs(tech['z_score']) > 2:
                    risk_score += 15
                    risk['factors'].append('Alta volatilità statistica')
            
            # Determina livello di rischio
            risk['score'] = risk_score
            if risk_score < 30:
                risk['level'] = 'LOW'
            elif risk_score < 60:
                risk['level'] = 'MEDIUM'
            else:
                risk['level'] = 'HIGH'
            
            return risk
            
        except Exception as e:
            logger.error(f"Errore valutazione rischio: {str(e)}")
            return {'level': 'UNKNOWN', 'score': 0, 'factors': []}
    
    def evaluate_accuracy(self, predictions: List[Dict], actual_results: List[Dict]) -> Dict:
        """
        Valuta l'accuratezza delle previsioni
        
        Args:
            predictions: Lista di previsioni fatte
            actual_results: Risultati effettivi
            
        Returns:
            Metriche di accuratezza
        """
        try:
            if not predictions or not actual_results:
                return {'accuracy': 0, 'total': 0}
            
            correct = 0
            total = 0
            
            for pred in predictions:
                # Trova risultato corrispondente
                symbol = pred.get('symbol')
                pred_date = pred.get('timestamp')
                
                for result in actual_results:
                    if result.get('symbol') == symbol:
                        # Confronta direzioni
                        if pred.get('direction') == result.get('actual_direction'):
                            correct += 1
                        total += 1
                        break
            
            accuracy = (correct / total * 100) if total > 0 else 0
            
            metrics = {
                'accuracy': accuracy,
                'correct': correct,
                'total': total,
                'performance_rating': 'EXCELLENT' if accuracy > 70 else 'GOOD' if accuracy > 60 else 'FAIR' if accuracy > 50 else 'POOR'
            }
            
            # Salva metriche
            self.accuracy_metrics = metrics
            
            return metrics
            
        except Exception as e:
            logger.error(f"Errore valutazione accuratezza: {str(e)}")
            return {'accuracy': 0, 'total': 0}
    
    def export_predictions(self, format='json') -> str:
        """
        Esporta lo storico delle previsioni
        
        Args:
            format: Formato export ('json' o 'csv')
            
        Returns:
            Path del file salvato
        """
        try:
            os.makedirs(config.ANALYSIS_OUTPUT_FOLDER, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if format == 'json':
                filename = f"predictions_{timestamp}.json"
                filepath = os.path.join(config.ANALYSIS_OUTPUT_FOLDER, filename)
                
                with open(filepath, 'w') as f:
                    json.dump({
                        'predictions': self.predictions_history,
                        'accuracy_metrics': self.accuracy_metrics,
                        'export_date': datetime.now().isoformat()
                    }, f, indent=2, default=str)
                    
            elif format == 'csv':
                filename = f"predictions_{timestamp}.csv"
                filepath = os.path.join(config.ANALYSIS_OUTPUT_FOLDER, filename)
                
                if self.predictions_history:
                    df = pd.DataFrame(self.predictions_history)
                    df.to_csv(filepath, index=False)
            else:
                raise ValueError(f"Formato {format} non supportato")
            
            logger.info(f"✓ Previsioni esportate in: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Errore export previsioni: {str(e)}")
            return None


# Funzioni helper
def generate_prediction(symbol: str, cot_data: Dict, historical_data: List[Dict] = None) -> Dict:
    """
    Genera previsione per un simbolo
    
    Args:
        symbol: Simbolo da analizzare
        cot_data: Dati COT attuali
        historical_data: Dati storici opzionali
        
    Returns:
        Previsione completa
    """
    system = COTPredictionSystem()
    cot_data['symbol'] = symbol
    return system.generate_prediction(cot_data, historical_data)


# Test del modulo
if __name__ == "__main__":
    print("🔮 Test Prediction System")
    print("="*50)
    
    # Dati di test
    current = {
        'symbol': 'GOLD',
        'date': datetime.now(),
        'non_commercial_long': 250000,
        'non_commercial_short': 150000,
        'net_position': 100000,
        'sentiment_score': 25.5,
        'sentiment_direction': 'BULLISH',
        'nc_long_ratio': 1.67,
        'c_long_ratio': 0.64
    }
    
    # Dati storici simulati
    historical = [
        {'net_position': 95000, 'sentiment_score': 22.0},
        {'net_position': 92000, 'sentiment_score': 20.5},
        {'net_position': 88000, 'sentiment_score': 18.0},
        {'net_position': 85000, 'sentiment_score': 15.5},
        {'net_position': 87000, 'sentiment_score': 17.0},
        {'net_position': 90000, 'sentiment_score': 19.0},
        {'net_position': 93000, 'sentiment_score': 21.0},
        {'net_position': 96000, 'sentiment_score': 23.0},
        {'net_position': 98000, 'sentiment_score': 24.5},
    ]
    
    print("\n📊 Generando previsione per GOLD...")
    prediction = generate_prediction('GOLD', current, historical)
    
    print(f"\n✓ Previsione completata!")
    print(f"Direzione: {prediction.get('direction', 'N/A')}")
    print(f"Confidenza: {prediction.get('confidence', 0):.1f}%")
    print(f"Timeframe: {prediction.get('timeframe', 'N/A')}")
    print(f"Risk Level: {prediction.get('risk', {}).get('level', 'N/A')}")
    
    print("\n" + "="*50)