
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import json
import os
import sys

# Setup path per imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import current_config as config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class COTDataProcessor:
    """Classe per l'elaborazione avanzata dei dati COT"""
    
    def __init__(self):
        """Inizializza il processor"""
        self.data = None
        self.processed_data = None
        self.indicators = {}
        
    def load_data(self, data):
        """
        Carica i dati da elaborare
        
        Args:
            data: Può essere dict, DataFrame, o path a file CSV
        """
        try:
            if isinstance(data, str):
                # Carica da file
                if data.endswith('.csv'):
                    self.data = pd.read_csv(data)
                elif data.endswith('.json'):
                    with open(data, 'r') as f:
                        self.data = pd.DataFrame(json.load(f))
            elif isinstance(data, dict):
                # Converti dict in DataFrame
                if all(isinstance(v, dict) for v in data.values()):
                    self.data = pd.DataFrame.from_dict(data, orient='index')
                else:
                    self.data = pd.DataFrame([data])
            elif isinstance(data, pd.DataFrame):
                self.data = data
            else:
                raise ValueError("Formato dati non supportato")
            
            # Converti date column se presente
            if 'date' in self.data.columns:
                self.data['date'] = pd.to_datetime(self.data['date'])
            
            logger.info(f"✓ Dati caricati: {len(self.data)} righe")
            return True
            
        except Exception as e:
            logger.error(f"Errore caricamento dati: {str(e)}")
            return False
    
    def calculate_technical_indicators(self):
        """Calcola indicatori tecnici sui dati COT"""
        if self.data is None:
            logger.error("Nessun dato caricato")
            return None
        
        try:
            df = self.data.copy()
            
            # Moving Averages
            if 'net_position' in df.columns:
                df['net_position_ma5'] = df['net_position'].rolling(window=5, min_periods=1).mean()
                df['net_position_ma10'] = df['net_position'].rolling(window=10, min_periods=1).mean()
                df['net_position_ma20'] = df['net_position'].rolling(window=20, min_periods=1).mean()
            
            # Sentiment Moving Averages
            if 'sentiment_score' in df.columns:
                df['sentiment_ma5'] = df['sentiment_score'].rolling(window=5, min_periods=1).mean()
                df['sentiment_ma10'] = df['sentiment_score'].rolling(window=10, min_periods=1).mean()
            
            # Rate of Change (ROC)
            if 'net_position' in df.columns:
                df['net_position_roc'] = df['net_position'].pct_change(periods=1) * 100
                df['net_position_roc5'] = df['net_position'].pct_change(periods=5) * 100
            
            # Volatility
            if 'sentiment_score' in df.columns:
                df['sentiment_volatility'] = df['sentiment_score'].rolling(window=10, min_periods=1).std()
            
            # Z-Score (normalized positions)
            if 'net_position' in df.columns:
                rolling_mean = df['net_position'].rolling(window=20, min_periods=1).mean()
                rolling_std = df['net_position'].rolling(window=20, min_periods=1).std()
                df['net_position_zscore'] = (df['net_position'] - rolling_mean) / (rolling_std + 1e-10)
            
            # Extreme positions detection
            if 'net_position' in df.columns:
                df['extreme_long'] = df['net_position'] > df['net_position'].quantile(0.9)
                df['extreme_short'] = df['net_position'] < df['net_position'].quantile(0.1)
            
            # Commercial vs Non-Commercial Divergence
            if all(col in df.columns for col in ['non_commercial_long', 'non_commercial_short', 
                                                   'commercial_long', 'commercial_short']):
                df['nc_net'] = df['non_commercial_long'] - df['non_commercial_short']
                df['c_net'] = df['commercial_long'] - df['commercial_short']
                df['divergence'] = df['nc_net'] + df['c_net']  # Commercials usually opposite to NC
                df['divergence_signal'] = np.where(df['divergence'] > 0, 'ALIGNED', 'DIVERGENT')
            
            # Momentum indicators
            if 'net_position' in df.columns and len(df) > 1:
                df['momentum'] = df['net_position'].diff()
                df['momentum_ma5'] = df['momentum'].rolling(window=5, min_periods=1).mean()
                df['momentum_signal'] = np.where(df['momentum'] > 0, 'INCREASING', 'DECREASING')
            
            # Open Interest changes (if available)
            if 'open_interest' in df.columns:
                df['oi_change'] = df['open_interest'].pct_change() * 100
                df['oi_ma5'] = df['open_interest'].rolling(window=5, min_periods=1).mean()
            
            self.processed_data = df
            
            # Salva indicatori principali
            self._calculate_summary_indicators()
            
            logger.info("✓ Indicatori tecnici calcolati")
            return df
            
        except Exception as e:
            logger.error(f"Errore calcolo indicatori: {str(e)}")
            return None
    
    def _calculate_summary_indicators(self):
        """Calcola indicatori riassuntivi"""
        if self.processed_data is None:
            return
        
        df = self.processed_data
        
        # Ultimo valore disponibile
        latest = df.iloc[-1] if len(df) > 0 else None
        
        if latest is not None:
            self.indicators = {
                'current_net_position': latest.get('net_position', 0),
                'current_sentiment': latest.get('sentiment_score', 0),
                'sentiment_direction': latest.get('sentiment_direction', 'NEUTRAL'),
                'momentum': latest.get('momentum', 0),
                'momentum_signal': latest.get('momentum_signal', 'STABLE'),
                'extreme_position': 'LONG' if latest.get('extreme_long', False) else 
                                  'SHORT' if latest.get('extreme_short', False) else 'NORMAL',
                'divergence_signal': latest.get('divergence_signal', 'UNKNOWN'),
                'volatility': latest.get('sentiment_volatility', 0),
                'z_score': latest.get('net_position_zscore', 0)
            }
            
            # Aggiungi trend
            if len(df) > 5:
                recent_trend = df['net_position'].tail(5).mean() if 'net_position' in df.columns else 0
                older_trend = df['net_position'].tail(10).head(5).mean() if 'net_position' in df.columns else 0
                self.indicators['trend'] = 'UP' if recent_trend > older_trend else 'DOWN'
            else:
                self.indicators['trend'] = 'INSUFFICIENT_DATA'
    
    def analyze_correlations(self, other_symbols_data):
        """
        Analizza correlazioni con altri simboli
        
        Args:
            other_symbols_data: Dict con dati di altri simboli
            
        Returns:
            DataFrame con matrice di correlazione
        """
        try:
            if not other_symbols_data:
                return None
            
            # Prepara DataFrame per correlazioni
            correlation_data = {}
            
            # Aggiungi dati correnti
            if self.data is not None and 'symbol' in self.data.columns:
                symbol = self.data['symbol'].iloc[0] if len(self.data) > 0 else 'CURRENT'
                if 'sentiment_score' in self.data.columns:
                    correlation_data[symbol] = self.data['sentiment_score'].values
            
            # Aggiungi altri simboli
            for symbol, data in other_symbols_data.items():
                if isinstance(data, pd.DataFrame) and 'sentiment_score' in data.columns:
                    correlation_data[symbol] = data['sentiment_score'].values
                elif isinstance(data, dict) and 'sentiment_score' in data:
                    correlation_data[symbol] = [data['sentiment_score']]
            
            # Calcola correlazioni
            if len(correlation_data) > 1:
                # Allinea lunghezze
                min_len = min(len(v) for v in correlation_data.values())
                for key in correlation_data:
                    correlation_data[key] = correlation_data[key][:min_len]
                
                # Crea DataFrame e calcola correlazioni
                corr_df = pd.DataFrame(correlation_data)
                correlation_matrix = corr_df.corr()
                
                logger.info("✓ Correlazioni calcolate")
                return correlation_matrix
            
            return None
            
        except Exception as e:
            logger.error(f"Errore calcolo correlazioni: {str(e)}")
            return None
    
    def detect_patterns(self):
        """Rileva pattern significativi nei dati COT"""
        if self.processed_data is None:
            logger.error("Nessun dato processato disponibile")
            return None
        
        patterns = {
            'reversals': [],
            'extremes': [],
            'divergences': [],
            'trends': []
        }
        
        try:
            df = self.processed_data
            
            # Pattern 1: Reversal Detection
            if 'net_position' in df.columns and len(df) > 10:
                # Cerca inversioni significative
                for i in range(10, len(df)):
                    window = df.iloc[i-10:i]
                    current = df.iloc[i]
                    
                    # Inversione da estremo positivo
                    if window['net_position'].max() == current['net_position'] and \
                       current['net_position'] > df['net_position'].quantile(0.8):
                        patterns['reversals'].append({
                            'type': 'TOP_REVERSAL',
                            'date': current.get('date', i),
                            'value': current['net_position'],
                            'confidence': 'HIGH' if current.get('extreme_long', False) else 'MEDIUM'
                        })
                    
                    # Inversione da estremo negativo
                    if window['net_position'].min() == current['net_position'] and \
                       current['net_position'] < df['net_position'].quantile(0.2):
                        patterns['reversals'].append({
                            'type': 'BOTTOM_REVERSAL',
                            'date': current.get('date', i),
                            'value': current['net_position'],
                            'confidence': 'HIGH' if current.get('extreme_short', False) else 'MEDIUM'
                        })
            
            # Pattern 2: Extreme Positions
            if 'net_position_zscore' in df.columns:
                extremes = df[df['net_position_zscore'].abs() > 2]
                for _, row in extremes.iterrows():
                    patterns['extremes'].append({
                        'type': 'EXTREME_LONG' if row['net_position_zscore'] > 0 else 'EXTREME_SHORT',
                        'date': row.get('date', None),
                        'z_score': row['net_position_zscore'],
                        'value': row.get('net_position', 0)
                    })
            
            # Pattern 3: Commercial/Non-Commercial Divergence
            if 'divergence_signal' in df.columns:
                divergences = df[df['divergence_signal'] == 'DIVERGENT']
                if len(divergences) > 0:
                    recent_divergences = divergences.tail(5)
                    for _, row in recent_divergences.iterrows():
                        patterns['divergences'].append({
                            'date': row.get('date', None),
                            'nc_net': row.get('nc_net', 0),
                            'c_net': row.get('c_net', 0),
                            'strength': abs(row.get('divergence', 0))
                        })
            
            # Pattern 4: Trend Identification
            if 'net_position' in df.columns and len(df) > 20:
                # Trend a breve termine (5 periodi)
                short_trend = df['net_position'].tail(5).mean() - df['net_position'].tail(10).head(5).mean()
                
                # Trend a medio termine (20 periodi)
                if len(df) > 20:
                    medium_trend = df['net_position'].tail(10).mean() - df['net_position'].tail(20).head(10).mean()
                else:
                    medium_trend = 0
                
                patterns['trends'] = {
                    'short_term': 'BULLISH' if short_trend > 0 else 'BEARISH',
                    'short_term_strength': abs(short_trend),
                    'medium_term': 'BULLISH' if medium_trend > 0 else 'BEARISH',
                    'medium_term_strength': abs(medium_trend),
                    'alignment': 'ALIGNED' if (short_trend > 0) == (medium_trend > 0) else 'DIVERGENT'
                }
            
            logger.info(f"✓ Pattern rilevati: {len(patterns['reversals'])} inversioni, "
                       f"{len(patterns['extremes'])} estremi, {len(patterns['divergences'])} divergenze")
            
            return patterns
            
        except Exception as e:
            logger.error(f"Errore rilevamento pattern: {str(e)}")
            return patterns
    
    def generate_signals(self):
        """
        Genera segnali di trading basati sui dati processati
        
        Returns:
            dict: Segnali di trading con confidenza
        """
        if self.processed_data is None or len(self.processed_data) == 0:
            return {'signal': 'NO_DATA', 'confidence': 0}
        
        try:
            latest = self.processed_data.iloc[-1]
            signals = []
            weights = []
            
            # Segnale 1: Sentiment Direction (peso 30%)
            if 'sentiment_direction' in latest:
                if latest['sentiment_direction'] == 'BULLISH':
                    signals.append(1)
                    weights.append(0.3)
                elif latest['sentiment_direction'] == 'BEARISH':
                    signals.append(-1)
                    weights.append(0.3)
                else:
                    signals.append(0)
                    weights.append(0.3)
            
            # Segnale 2: Momentum (peso 25%)
            if 'momentum' in latest and latest['momentum'] != 0:
                if latest['momentum'] > 0:
                    signals.append(1)
                    weights.append(0.25)
                else:
                    signals.append(-1)
                    weights.append(0.25)
            
            # Segnale 3: Z-Score (peso 20%)
            if 'net_position_zscore' in latest:
                z_score = latest['net_position_zscore']
                if z_score > 1.5:
                    signals.append(1)
                    weights.append(0.2)
                elif z_score < -1.5:
                    signals.append(-1)
                    weights.append(0.2)
                else:
                    signals.append(0)
                    weights.append(0.2)
            
            # Segnale 4: Divergence (peso 15%)
            if 'divergence_signal' in latest:
                if latest['divergence_signal'] == 'DIVERGENT':
                    # Divergenza è spesso contrarian
                    if 'nc_net' in latest and latest['nc_net'] > 0:
                        signals.append(-0.5)  # Cautela su long
                    else:
                        signals.append(0.5)   # Cautela su short
                    weights.append(0.15)
                else:
                    signals.append(0)
                    weights.append(0.15)
            
            # Segnale 5: Extreme positions (peso 10%)
            if 'extreme_long' in latest and latest['extreme_long']:
                signals.append(-0.5)  # Possibile inversione da estremo long
                weights.append(0.1)
            elif 'extreme_short' in latest and latest['extreme_short']:
                signals.append(0.5)   # Possibile inversione da estremo short
                weights.append(0.1)
            else:
                signals.append(0)
                weights.append(0.1)
            
            # Calcola segnale complessivo
            if signals and weights:
                weighted_signal = np.average(signals, weights=weights)
                
                # Determina direzione e confidenza
                if weighted_signal > 0.3:
                    direction = 'BUY'
                    confidence = min(abs(weighted_signal) * 100, 100)
                elif weighted_signal < -0.3:
                    direction = 'SELL'
                    confidence = min(abs(weighted_signal) * 100, 100)
                else:
                    direction = 'NEUTRAL'
                    confidence = 50
                
                return {
                    'signal': direction,
                    'strength': weighted_signal,
                    'confidence': confidence,
                    'components': {
                        'sentiment': latest.get('sentiment_direction', 'N/A'),
                        'momentum': latest.get('momentum_signal', 'N/A'),
                        'z_score': latest.get('net_position_zscore', 0),
                        'extreme': 'YES' if latest.get('extreme_long', False) or latest.get('extreme_short', False) else 'NO'
                    }
                }
            
            return {'signal': 'INSUFFICIENT_DATA', 'confidence': 0}
            
        except Exception as e:
            logger.error(f"Errore generazione segnali: {str(e)}")
            return {'signal': 'ERROR', 'confidence': 0}
    
    def export_analysis(self, format='json'):
        """
        Esporta l'analisi completa
        
        Args:
            format: Formato output ('json', 'csv', 'excel')
            
        Returns:
            str: Path del file salvato
        """
        try:
            # Crea cartella output
            os.makedirs(config.ANALYSIS_OUTPUT_FOLDER, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if format == 'json':
                filename = f"analysis_{timestamp}.json"
                filepath = os.path.join(config.ANALYSIS_OUTPUT_FOLDER, filename)
                
                export_data = {
                    'timestamp': timestamp,
                    'indicators': self.indicators,
                    'signals': self.generate_signals(),
                    'patterns': self.detect_patterns()
                }
                
                # Aggiungi dati processati come lista
                if self.processed_data is not None:
                    export_data['data'] = self.processed_data.to_dict('records')
                
                with open(filepath, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                    
            elif format == 'csv':
                filename = f"analysis_{timestamp}.csv"
                filepath = os.path.join(config.ANALYSIS_OUTPUT_FOLDER, filename)
                
                if self.processed_data is not None:
                    self.processed_data.to_csv(filepath, index=False)
                    
            elif format == 'excel':
                filename = f"analysis_{timestamp}.xlsx"
                filepath = os.path.join(config.ANALYSIS_OUTPUT_FOLDER, filename)
                
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    if self.processed_data is not None:
                        self.processed_data.to_excel(writer, sheet_name='Data', index=False)
                    
                    # Aggiungi indicatori
                    if self.indicators:
                        pd.DataFrame([self.indicators]).to_excel(writer, sheet_name='Indicators', index=False)
                    
                    # Aggiungi segnali
                    signals = self.generate_signals()
                    pd.DataFrame([signals]).to_excel(writer, sheet_name='Signals', index=False)
            
            else:
                raise ValueError(f"Formato {format} non supportato")
            
            logger.info(f"✓ Analisi esportata in: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Errore esportazione: {str(e)}")
            return None


# Test del modulo
if __name__ == "__main__":
    print("🔬 Test Data Processor")
    print("="*50)
    
    # Crea dati di test
    test_data = {
        'symbol': 'GOLD',
        'date': datetime.now(),
        'non_commercial_long': 250000,
        'non_commercial_short': 150000,
        'commercial_long': 180000,
        'commercial_short': 280000,
        'net_position': 100000,
        'sentiment_score': 15.5
    }
    
    # Inizializza processor
    processor = COTDataProcessor()
    
    # Carica dati
    processor.load_data(test_data)
    
    # Calcola indicatori
    processor.calculate_technical_indicators()
    
    # Genera segnali
    signals = processor.generate_signals()
    
    print(f"\n📊 Risultati Analisi:")
    print(f"Segnale: {signals['signal']}")
    print(f"Confidenza: {signals['confidence']:.1f}%")
    
    print("\n" + "="*50)