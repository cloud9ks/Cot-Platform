"""
ml_system_fixed.py
Sistema ML robusto per previsioni COT con fallback automatico

- Usa RandomForestRegressor + StandardScaler se scikit-learn  disponibile.
- Se le librerie ML non sono disponibili (o SciPy  rotto), passa in fallback
  basato su regole senza interrompere l'applicazione.

Esporta:
- COTPredictorFixed
- create_production_predictor
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

# Logger locale del modulo
logger = logging.getLogger("cot_ml")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

# Import opzionale di NumPy: lo usiamo solo se presente
try:
    import numpy as np  # type: ignore
    logger.info(f"NumPy version: {np.__version__}")
except Exception as e:  # pragma: no cover
    np = None  # type: ignore
    logger.warning(f"NumPy non disponibile o danneggiato: {e}")


class COTPredictorFixed:
    """Sistema ML corretto per predizioni COT

    - Tenta l'inizializzazione ML (RandomForest + StandardScaler)
    - Se fallisce, resta operativo in modalit fallback (regole)
    """

    def __init__(self) -> None:
        self.model = None
        self.scaler = None
        self.is_trained: bool = False
        self.ml_available: bool = False
        self.features_columns: Optional[List[str]] = None
        self.last_training_data_size: int = 0
        self.accuracy_history: List[float] = []
        self._init_ml_components()

    # ---------------- ML INIT ---------------- #
    def _init_ml_components(self) -> None:
        """Inizializza i componenti ML in modo resiliente."""
        try:
            # Import lazy per scikit-learn (pu fallire se SciPy  rotto)
            from sklearn.ensemble import RandomForestRegressor  # type: ignore
            from sklearn.preprocessing import StandardScaler  # type: ignore
            import sklearn  # type: ignore
            logger.info(f"Scikit-learn version: {sklearn.__version__}")

            # Se manca numpy, non abilitiamo ML
            if np is None:
                raise ImportError("NumPy mancante")

            # Istanzia i componenti ML
            self.model = RandomForestRegressor(
                n_estimators=50,
                max_depth=10,
                random_state=42,
                n_jobs=1,
            )
            self.scaler = StandardScaler()
            self.ml_available = True
            logger.info("[OK] ML components inizializzati correttamente")
        except Exception as e:  # noqa: BLE001
            # Qualsiasi errore (SciPy rotto, assente, ecc.) -> fallback
            self.model = None
            self.scaler = None
            self.ml_available = False
            logger.warning(
                f"[WARN] ML libraries non disponibili: {e}\n"
                "[TIP] Per attivare ML: pip install scikit-learn==1.3.0 numpy==1.24.3 scipy==1.10.1"
            )

    # ---------------- FEATURE ENGINEERING ---------------- #
    def prepare_features(self, data_point: Dict[str, Any]):
        """Prepara il vettore di feature per il modello.

        Ritorna un array 2D (1, n_features) se ML  disponibile, altrimenti None.
        """
        if not self.ml_available or np is None:
            return None
        try:
            # Estrai features base
            nc_long = float(data_point.get("non_commercial_long", 0))
            nc_short = float(data_point.get("non_commercial_short", 0))
            c_long = float(data_point.get("commercial_long", 0))
            c_short = float(data_point.get("commercial_short", 0))
            net_pos = float(data_point.get("net_position", 0))
            sentiment = float(data_point.get("sentiment_score", 0))

            # Derivate
            nc_ratio = nc_long / (nc_short + 1.0)
            c_ratio = c_long / (c_short + 1.0)
            total_long = nc_long + c_long
            total_short = nc_short + c_short
            total_oi = total_long + total_short

            if total_oi > 0:
                nc_long_pct = nc_long / total_oi
                nc_short_pct = nc_short / total_oi
                c_long_pct = c_long / total_oi
                c_short_pct = c_short / total_oi
            else:
                nc_long_pct = nc_short_pct = c_long_pct = c_short_pct = 0.25

            features = [
                nc_long, nc_short, c_long, c_short,  # raw
                net_pos, sentiment,                  # derived
                nc_ratio, c_ratio,                   # ratios
                total_oi,                            # size
                nc_long_pct, nc_short_pct, c_long_pct, c_short_pct,
                abs(net_pos), abs(sentiment)         # stabilizers
            ]

            # Sanity check
            features = [float(f) if (f is not None) else 0.0 for f in features]
            arr = np.array(features, dtype=float).reshape(1, -1)
            # Protezione contro NaN/Inf
            if np.any(~np.isfinite(arr)):
                arr[~np.isfinite(arr)] = 0.0
            return arr
        except Exception as e:  # noqa: BLE001
            logger.error(f"Errore preparazione features: {e}")
            return None

    # ---------------- TRAIN ---------------- #
    def train(self, historical_data: List[Dict[str, Any]]) -> bool:
        """Allena il modello sul cambiamento del sentiment tra t e t+1."""
        if not self.ml_available or self.model is None or self.scaler is None or np is None:
            logger.info("ML non disponibile - training saltato")
            return False
        if not historical_data or len(historical_data) < 3:
            logger.info(f"Dati insufficienti per training: {len(historical_data) if historical_data else 0} < 3")
            return False
        try:
            X_list: List[List[float]] = []
            y_list: List[float] = []

            for i in range(len(historical_data) - 1):
                cur = historical_data[i]
                nxt = historical_data[i + 1]
                feats = self.prepare_features(cur)
                if feats is None:
                    continue
                cur_s = float(cur.get("sentiment_score", 0))
                nxt_s = float(nxt.get("sentiment_score", 0))
                target = nxt_s - cur_s
                if not np.isfinite(target):  # type: ignore[attr-defined]
                    continue
                X_list.append(feats[0].tolist())
                y_list.append(target)

            if len(X_list) < 2:
                logger.warning(f"Features valide insufficienti: {len(X_list)} < 2")
                return False

            X = np.array(X_list, dtype=float)
            y = np.array(y_list, dtype=float)

            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            self.is_trained = True
            self.last_training_data_size = len(X)

            # Stima semplice di accuratezza sul training set
            y_pred = self.model.predict(X_scaled)
            mae = float(np.mean(np.abs(y - y_pred)))
            accuracy_score = max(0.0, min(100.0, 100.0 - (mae * 10.0)))
            self.accuracy_history.append(accuracy_score)

            logger.info(
                "[OK] Training completato! Samples=%s MAE=%.3f Acc=%.1f%%",
                len(X), mae, accuracy_score,
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"[ERROR] Errore durante training: {e}")
            self.is_trained = False
            return False

    # ---------------- PREDICT ---------------- #
    def predict(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restituisce un dizionario con direzione, confidenza e dettagli."""
        if not self.ml_available or not self.is_trained or self.model is None or self.scaler is None:
            logger.info("ML non disponibile - usando predizione fallback")
            return self._fallback_prediction(current_data)
        try:
            feats = self.prepare_features(current_data)
            if feats is None:
                return self._fallback_prediction(current_data)
            feats_scaled = self.scaler.transform(feats)
            score = float(self.model.predict(feats_scaled)[0])
            direction, confidence = self._interpret_prediction(score, current_data)
            out = {
                "direction": direction,
                "confidence": confidence,
                "score": score,
                "method": "machine_learning",
                "model_accuracy": self._get_current_accuracy(),
                "training_size": self.last_training_data_size,
            }
            logger.info("[OK] ML Prediction: %s (conf: %.0f%%, score: %.3f)", direction, confidence, score)
            return out
        except Exception as e:  # noqa: BLE001
            logger.error(f"[ERROR] Errore predizione ML: {e}")
            return self._fallback_prediction(current_data)

    # ---------------- INTERPRETAZIONE ---------------- #
    def _interpret_prediction(self, prediction_score: float, current_data: Dict[str, Any]):
        current_sentiment = float(current_data.get("sentiment_score", 0))
        base_threshold = 2.0
        if abs(current_sentiment) > 30:
            threshold_multiplier = 0.7
        elif abs(current_sentiment) < 10:
            threshold_multiplier = 1.3
        else:
            threshold_multiplier = 1.0
        thr = base_threshold * threshold_multiplier

        if prediction_score > thr:
            direction = "BULLISH"
            confidence = min(abs(prediction_score) * 20.0, 90.0)
        elif prediction_score < -thr:
            direction = "BEARISH"
            confidence = min(abs(prediction_score) * 20.0, 90.0)
        else:
            direction = "NEUTRAL"
            confidence = 50.0 + min(abs(prediction_score) * 10.0, 20.0)

        if (direction == "BULLISH" and current_sentiment > 0) or (
            direction == "BEARISH" and current_sentiment < 0
        ):
            confidence = min(confidence * 1.1, 95.0)
        return direction, confidence

    # ---------------- FALLBACK ---------------- #
    def _fallback_prediction(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            sentiment_score = float(current_data.get("sentiment_score", 0))
            net_position = float(current_data.get("net_position", 0))
            nc_long = float(current_data.get("non_commercial_long", 0))
            nc_short = float(current_data.get("non_commercial_short", 0))
            nc_ratio = nc_long / (nc_short + 1.0)

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
                "direction": direction,
                "confidence": float(confidence),
                "score": float(sentiment_score) / 10.0,
                "method": "rule_based_fallback",
                "note": "Predizione basata su regole - ML non disponibile",
            }
        except Exception as e:  # noqa: BLE001
            logger.error(f"Errore fallback prediction: {e}")
            return {
                "direction": "NEUTRAL",
                "confidence": 50.0,
                "score": 0.0,
                "method": "emergency_fallback",
                "error": str(e),
            }

    # ---------------- INFO / UTILS ---------------- #
    def _get_current_accuracy(self) -> float:
        return self.accuracy_history[-1] if self.accuracy_history else 0.0

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "ml_available": self.ml_available,
            "is_trained": self.is_trained,
            "training_data_size": self.last_training_data_size,
            "current_accuracy": self._get_current_accuracy(),
            "accuracy_history": self.accuracy_history[-5:],
            "model_type": "RandomForestRegressor" if self.ml_available else "None",
            "features_count": 14,
            "sklearn_available": self.ml_available,
        }

    def retrain_if_needed(self, new_data_size: int) -> bool:
        if not self.is_trained:
            return False
        return new_data_size > self.last_training_data_size * 1.5


# Factory consigliata per produzione

def create_production_predictor() -> COTPredictorFixed:
    return COTPredictorFixed()


__all__ = ["COTPredictorFixed", "create_production_predictor"]


if __name__ == "__main__":  # Esegui un mini test solo se lanci questo file direttamente
    p = COTPredictorFixed()
    demo_hist = [
        {"non_commercial_long": 200000, "non_commercial_short": 120000, "commercial_long": 150000, "commercial_short": 160000, "net_position": 80000, "sentiment_score": 12.0},
        {"non_commercial_long": 220000, "non_commercial_short": 110000, "commercial_long": 145000, "commercial_short": 170000, "net_position": 100000, "sentiment_score": 16.0},
        {"non_commercial_long": 250000, "non_commercial_short": 100000, "commercial_long": 140000, "commercial_short": 180000, "net_position": 150000, "sentiment_score": 22.0},
    ]
    p.train(demo_hist)
    print(p.get_model_info())
    print(p.predict(demo_hist[-1]))
