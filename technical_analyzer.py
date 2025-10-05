#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Technical Analyzer - Supporti, Resistenze e Notizie
Fonte live: Twelve Data (quote + time_series) con fallback simulato.
"""

from __future__ import annotations

import os
import logging
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from time import monotonic, sleep
from threading import Lock, RLock

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# ENV & LOG
# -----------------------------------------------------------------------------
load_dotenv()
TD_API_KEY = os.getenv("TWELVE_DATA_API_KEY") or os.getenv("TD_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("technical_analyzer")

# Sessione HTTP riutilizzabile
_TD_SESSION = requests.Session()
_TD_SESSION.headers.update({"User-Agent": "cot-platform/1.0"})


# =============================================================================
# ANALYZER
# =============================================================================
class TechnicalAnalyzer:
    """Analisi tecnica (S/R + indicatori) usando Twelve Data con fallback robusto."""

    def __init__(self):
        # (sono mantenute per retro-compatibilità con altri moduli)
        self.price_cache: Dict[str, float] = {}
        self.last_update: Dict[str, datetime] = {}

        # --- TTL caches in-process ---
        # symbol -> (price, ts_monotonic)
        self._price_cache_store: Dict[str, Tuple[float, float]] = {}
        # (symbol, interval) -> (df, ts_monotonic)
        self._ohlc_cache_store: Dict[Tuple[str, str], Tuple[pd.DataFrame, float]] = {}
        self._ttl_seconds_price = int(os.getenv("TD_CACHE_TTL_PRICE_SEC", "60"))
        self._ttl_seconds_ohlc = int(os.getenv("TD_CACHE_TTL_OHLC_SEC", "60"))

        # --- Locks per coalescing delle chiamate duplicate ---
        self._locks: Dict[Tuple[str, str], Lock] = {}
        self._global_lock = RLock()

        # --- Rate limiter (token bucket) per non sforare gli 8/min di TwelveData ---
        self._tokens_per_min = int(os.getenv("TD_RATE_LIMIT_PER_MIN", "8"))
        self._tokens = self._tokens_per_min
        self._window_start = monotonic()
        self._rate_lock = Lock()

        # Prezzi base per fallback
        self.base_prices = {
            "GOLD": 2539.71, "SILVER": 24.32, "USD": 103.45,
            "EUR": 1.0875, "GBP": 1.2634, "JPY": 150.25,
            "CHF": 0.9145, "CAD": 1.3542, "AUD": 0.6745,
            "OIL": 78.45, "COPPER": 3.85, "NATGAS": 2.65,
            "SP500": 4485.50, "NASDAQ": 15234.80
        }

        # Mappa "logica" -> candidati Twelve Data
        self.td_symbol_map: Dict[str, List[str]] = {
            "GOLD":   ["XAU/USD", "XAUUSD"],
            "SILVER": ["XAG/USD", "XAGUSD"],
            "USD":    ["DXY"],                  # se non disponibile -> fallback
            "EUR":    ["EUR/USD", "EURUSD"],
            "GBP":    ["GBP/USD", "GBPUSD"],
            "AUD":    ["AUD/USD", "AUDUSD"],
            "JPY":    ["USD/JPY", "USDJPY"],   # non invertire
            "CHF":    ["USD/CHF", "USDCHF"],
            "CAD":    ["USD/CAD", "USDCAD"],
            "SP500":  ["SPY", "SPX"],
            "NASDAQ": ["QQQ", "NDX"],
            "OIL":    ["WTI/USD", "BRENT/USD"],
        }

        self.TD_BASE = "https://api.twelvedata.com"
        self._catalog_cache: Dict[str, set] = {"forex": set(), "commodities": set()}

    # -------------------------------------------------------------------------
    # RATE LIMITER & CACHE HELPERS
    # -------------------------------------------------------------------------
    def _throttle(self) -> None:
        """Limita a N richieste/minuto per processo (token bucket)."""
        with self._rate_lock:
            now = monotonic()
            elapsed = now - self._window_start
            if elapsed >= 60:
                self._tokens = self._tokens_per_min
                self._window_start = now
            if self._tokens <= 1:
                wait = 60 - elapsed + 1
                if wait > 0:
                    logger.warning(f"TD rate-limit locale: sleep {wait:.1f}s per non sforare i crediti")
                    sleep(wait)
                self._tokens = self._tokens_per_min
                self._window_start = monotonic()
            self._tokens -= 1

    def _get_lock(self, symbol: str, interval: str = "") -> Lock:
        """Ritorna (creandolo se serve) il lock per (symbol, interval)."""
        key = (symbol, interval)
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = Lock()
            return self._locks[key]

    def _cache_get_price(self, symbol: str) -> Optional[float]:
        rec = self._price_cache_store.get(symbol)
        if not rec:
            return None
        price, ts = rec
        if monotonic() - ts <= self._ttl_seconds_price:
            return float(price)
        return None

    def _cache_set_price(self, symbol: str, price: float) -> None:
        self._price_cache_store[symbol] = (float(price), monotonic())

    def _cache_get_ohlc(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        rec = self._ohlc_cache_store.get((symbol, interval))
        if not rec:
            return None
        df, ts = rec
        if monotonic() - ts <= self._ttl_seconds_ohlc:
            return df.copy()
        return None

    def _cache_set_ohlc(self, symbol: str, interval: str, df: pd.DataFrame) -> None:
        self._ohlc_cache_store[(symbol, interval)] = (df.copy(), monotonic())

    def _is_price_sane(self, symbol: str, price: float) -> bool:
        """Filtra valori anomali (es. 3706 su XAUUSD). Range conservativi per simbolo."""
        try:
            p = float(price)
        except Exception:
            return False
        bounds = {
            "GOLD": (1000.0, 4000.0),
            "SILVER": (5.0, 100.0),
            "EUR": (0.5, 2.0),
            "GBP": (0.8, 2.0),
            "AUD": (0.4, 1.2),
            "JPY": (50.0, 250.0),     # USD/JPY
            "CHF": (0.5, 2.0),
            "CAD": (0.5, 2.0),
            "OIL": (20.0, 200.0),
            "SP500": (500.0, 10000.0),
            "NASDAQ": (1000.0, 25000.0),
        }
        lo, hi = bounds.get(symbol, (0.00001, 1e9))
        return lo <= p <= hi

    # -------------------------------------------------------------------------
    # TWELVE DATA HELPERS (tutti **dentro** la classe)
    # -------------------------------------------------------------------------
    def _td_request(self, path: str, params: Dict, timeout: int = 8) -> Optional[dict]:
        """Wrapper HTTP con gestione errori Twelve Data + rate-limit locale."""
        if not TD_API_KEY:
            logger.warning("TD_API_KEY non configurata")
            return None

        q = params.copy()
        q["apikey"] = TD_API_KEY
        url = f"{self.TD_BASE}/{path}"

        try:
            self._throttle()  # rispetta rate-limit locale
            logger.debug(f"TD API call: {url} with params: {q}")
            r = _TD_SESSION.get(url, params=q, timeout=timeout)

            if r.status_code != 200:
                logger.warning(f"TD API HTTP error {r.status_code}: {r.text}")
                return None

            data = r.json()

            # Verifica errori Twelve Data
            if isinstance(data, dict) and data.get("status") == "error":
                msg = data.get("message", "Unknown error")
                logger.warning(f"TD API error: {msg}")
                return None

            logger.debug(f"TD API success: {path}")
            return data

        except Exception as e:
            logger.warning(f"TD API exception for {path}: {e}")
            return None

    def _load_catalog(self) -> None:
        """Carica e cachea i cataloghi di simboli (forex e commodities)."""
        if not TD_API_KEY:
            return
        if not self._catalog_cache["forex"]:
            fx = self._td_request("forex_pairs", {})
            if isinstance(fx, dict) and isinstance(fx.get("data"), list):
                self._catalog_cache["forex"] = {
                    row["symbol"] for row in fx["data"] if "symbol" in row
                }
        if not self._catalog_cache["commodities"]:
            com = self._td_request("commodities", {})
            if isinstance(com, dict) and isinstance(com.get("data"), list):
                self._catalog_cache["commodities"] = {
                    row["symbol"] for row in com["data"] if "symbol" in row
                }

    def _resolve_td_symbol(self, logical_symbol: str) -> Optional[str]:
        """
        Restituisce il simbolo Twelve Data da usare per 'logical_symbol'.
        Es.: GOLD->XAU/USD, EUR->EUR/USD, JPY->USD/JPY (non invertiamo).
        """
        # Mappa diretta senza bisogno di cataloghi
        direct_mapping = {
            "GOLD": "XAU/USD",
            "SILVER": "XAG/USD",
            "EUR": "EUR/USD",
            "GBP": "GBP/USD",
            "AUD": "AUD/USD",
            "JPY": "USD/JPY",
            "CHF": "USD/CHF",
            "CAD": "USD/CAD",
            "USD": "USDX",  
            "OIL": "WTI/USD",
        }

        td_symbol = direct_mapping.get(logical_symbol)
        if td_symbol:
            logger.debug(f"Resolved {logical_symbol} -> {td_symbol}")
            return td_symbol

        # Fallback: usa la logica originale se necessario
        self._load_catalog()
        candidates = self.td_symbol_map.get(logical_symbol, [])

        # Prova con i candidati nei cataloghi
        for s in candidates:
            if s in self._catalog_cache["forex"] or s in self._catalog_cache["commodities"]:
                logger.debug(f"Resolved {logical_symbol} -> {s} (from catalog)")
                return s

        # Ultima risorsa: primo candidato o None
        result = candidates[0] if candidates else None
        logger.debug(f"Resolved {logical_symbol} -> {result} (fallback)")
        return result

    def _td_get_price(self, symbol: str) -> Tuple[Optional[float], Optional[str]]:
        """Ultimo prezzo: usa cache+lock; poi /quote, poi /price; fallback cache 'stale' o base."""
        td_sym = self._resolve_td_symbol(symbol)
        if not td_sym or not TD_API_KEY:
            return None, None

        with self._get_lock(symbol, "price"):
            # 1) cache fresca
            cached = self._cache_get_price(symbol)
            if cached is not None:
                return float(cached), td_sym

            # 2) /quote
            try:
                data = self._td_request("quote", {"symbol": td_sym})
                if isinstance(data, dict) and not data.get("status") == "error":
                    if data.get("close"):
                        price = float(data["close"])
                        if self._is_price_sane(symbol, price):
                            self._cache_set_price(symbol, price)
                            return price, td_sym
            except Exception as e:
                logger.warning(f"Quote API error for {td_sym}: {e}")

            # 3) /price
            try:
                data = self._td_request("price", {"symbol": td_sym})
                if isinstance(data, dict) and not data.get("status") == "error":
                    if data.get("price"):
                        price = float(data["price"])
                        if self._is_price_sane(symbol, price):
                            self._cache_set_price(symbol, price)
                            return price, td_sym
            except Exception as e:
                logger.warning(f"Price API error for {td_sym}: {e}")

            # 4) cache "stale" (meglio di niente)
            stale = self._price_cache_store.get(symbol)
            if stale:
                price, _ = stale
                logger.info(f"Using cached price (stale) for {symbol}: {price}")
                return float(price), td_sym

            # 5) base price (ultimissima risorsa)
            base_price = self.base_prices.get(symbol, 100.0)
            logger.info(f"Using fallback price for {symbol}: {base_price}")
            return base_price, td_sym

    def _td_get_ohlc(
        self,
        symbol: str,
        interval: str = "1day",
        outputsize: int = 500
    ) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        Serie OHLC via /time_series. Ritorna (df, td_symbol) con colonne Open/High/Low/Close.
        Usa cache+lock; prova interval, poi 1day e 1h; fallback su cache stale.
        """
        td_sym = self._resolve_td_symbol(symbol)
        if not td_sym or not TD_API_KEY:
            return None, None

        lock = self._get_lock(symbol, interval)
        with lock:
            # 1) cache fresca
            cached_df = self._cache_get_ohlc(symbol, interval)
            if cached_df is not None and len(cached_df) >= 30:
                logger.info(f"TD OHLC served from cache: {symbol} -> {td_sym} ({interval})")
                return cached_df, td_sym

            # 2) prova 'interval' richiesto, poi 1day, poi 1h
            for itv in (interval, "1day", "1h"):
                data = self._td_request(
                    "time_series",
                    {
                        "symbol": td_sym,
                        "interval": itv,
                        "outputsize": str(outputsize),
                        "timezone": "UTC",
                        "order": "ASC",
                    },
                    timeout=12,
                )
                vals = (data or {}).get("values")
                if not vals:
                    continue

                try:
                    df = pd.DataFrame(vals)
                    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
                    df = df.sort_values("datetime")
                    for col in ["open", "high", "low", "close"]:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                    df = df.dropna(subset=["open", "high", "low", "close"])
                    if df.empty:
                        continue

                    df = df.rename(
                        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}
                    )[["Open", "High", "Low", "Close"]]

                    logger.info(f"TD OHLC resolved: {symbol} -> {td_sym} ({itv})")
                    # metti in cache per richieste ravvicinate (sul 'interval' richiesto originariamente)
                    self._cache_set_ohlc(symbol, interval, df)
                    return df, td_sym
                except Exception:
                    continue

            # 3) fallback su cache "stale" se esiste
            stale = self._ohlc_cache_store.get((symbol, interval))
            if stale:
                df, _ = stale
                logger.warning(f"TD OHLC fallback to stale cache for {symbol} ({interval})")
                return df.copy(), td_sym

            return None, None

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------
    def get_current_price(self, symbol: str) -> float:
        """
        Prezzo corrente con priorità:
        1) TwelveData (/quote -> /price), con sanity-check e cache 60s
        2) cache "stale" locale se disponibile
        3) base price con piccola variazione deterministica oraria (simulato)
        """
        price, _ = self._td_get_price(symbol)
        if price is not None:
            # se TwelveData risponde ma il valore è anomalo, prova cache poi base
            if self._is_price_sane(symbol, price):
                return float(price)
            cached = self._cache_get_price(symbol)
            if cached is not None and self._is_price_sane(symbol, cached):
                return float(cached)

        # Fallback simulato (±2% deterministico sull’ora, per evitare jitter)
        base_price = float(self.base_prices.get(symbol, 100.0))
        random.seed(hash(symbol + str(datetime.now().hour)))
        variation = random.uniform(-0.02, 0.02)  # ±2%
        return base_price * (1 + variation)

    def calculate_support_resistance(self, symbol: str) -> Dict:
        """
        Calcola supporti/resistenze + indicatori.
        Usa dati TwelveData (con cache/lock/throttle) e ripiega su cache/base price
        se necessario. Marca data_quality/source in modo trasparente per la UI.
        """
        from math import isnan

        def _nan_to_none(x):
            return None if x is None or (isinstance(x, float) and (np.isnan(x) or isnan(x))) else float(x)

        try:
            # ===================== DATI LIVE / CACHE TD =====================
            df, used_symbol = self._td_get_ohlc(symbol, interval="1day", outputsize=500)

            if df is not None and not df.empty and len(df) >= 30:
                # Prezzo “live” dall’ultima candela (potrebbe provenire da cache recente)
                current_price = float(df["Close"].iloc[-1])
                data_quality = "live"
                source = "twelvedata"

                # Sanity check sul prezzo
                if not self._is_price_sane(symbol, current_price):
                    cached_p = self._cache_get_price(symbol)
                    if cached_p is not None and self._is_price_sane(symbol, cached_p):
                        logger.warning(f"Anomalia prezzo live {symbol}: {current_price} -> uso cached price {cached_p}")
                        current_price = float(cached_p)
                        data_quality = "stale"
                        source = "twelvedata-cache"
                    else:
                        base_p = self.base_prices.get(symbol, current_price)
                        logger.warning(f"Anomalia prezzo live {symbol}: {current_price} -> uso base {base_p}")
                        current_price = float(base_p)
                        data_quality = "stale"
                        source = "fallback-base"

                # ===================== INDICATORI =====================
                # SMA
                sma50 = float(pd.Series(df["Close"]).rolling(50).mean().iloc[-1])
                sma200 = float(pd.Series(df["Close"]).rolling(200).mean().iloc[-1]) if len(df) >= 200 else np.nan

                # RSI(14)
                delta = pd.Series(df["Close"]).diff()
                up = delta.clip(lower=0.0)
                down = -delta.clip(upper=0.0)
                roll_up = up.ewm(alpha=1/14, adjust=False).mean()
                roll_down = down.ewm(alpha=1/14, adjust=False).mean()
                rs = roll_up / (roll_down.replace(0, np.nan))
                rsi14 = 100 - (100 / (1 + rs))
                rsi14 = float(rsi14.iloc[-1])

                # MACD (12-26)
                ema12 = pd.Series(df["Close"]).ewm(span=12, adjust=False).mean()
                ema26 = pd.Series(df["Close"]).ewm(span=26, adjust=False).mean()
                macd = float((ema12 - ema26).iloc[-1])

                # ATR(14)
                hl = pd.Series(df["High"]) - pd.Series(df["Low"])
                hc = (pd.Series(df["High"]) - pd.Series(df["Close"]).shift(1)).abs()
                lc = (pd.Series(df["Low"]) - pd.Series(df["Close"]).shift(1)).abs()
                tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
                atr14 = float(tr.rolling(14).mean().iloc[-1])

                # Volatilità 20D (std %)
                ret = pd.Series(df["Close"]).pct_change()
                vol20 = float(ret.rolling(20).std().iloc[-1] * 100)

                indicators = {
                    "rsi14": _nan_to_none(rsi14),
                    "sma50": _nan_to_none(sma50),
                    "sma200": _nan_to_none(sma200),
                    "macd": _nan_to_none(macd),
                    "atr14": _nan_to_none(atr14),
                    "volatility20": _nan_to_none(vol20),
                }

                # ===================== LIVELLI S/R =====================
                # Quantili su 60 barre recenti (robusto e veloce)
                last_n = df.tail(60)
                s_candidates = [last_n["Low"].quantile(q) for q in [0.05, 0.10, 0.20]] + [last_n["Low"].min()]
                r_candidates = [last_n["High"].quantile(q) for q in [0.95, 0.90, 0.80]] + [last_n["High"].max()]

                strong_support = max([s for s in s_candidates if s <= current_price],
                                     default=float(last_n["Low"].min()))
                strong_resistance = min([r for r in r_candidates if r >= current_price],
                                        default=float(last_n["High"].max()))

                # Pivot standard (ultimo giorno)
                last_h = float(df["High"].iloc[-1])
                last_l = float(df["Low"].iloc[-1])
                last_c = float(df["Close"].iloc[-1])
                pivot = (last_h + last_l + last_c) / 3.0
                r1 = 2 * pivot - last_l
                s1 = 2 * pivot - last_h
                r2 = pivot + (last_h - last_l)
                s2 = pivot - (last_h - last_l)

                pivot_points = {
                    "pivot": float(pivot),
                    "r1": float(r1), "s1": float(s1),
                    "r2": float(r2), "s2": float(s2),
                }

                # Distanze in %
                try:
                    distance_to_support = round((current_price - strong_support) / current_price * 100, 2)
                except Exception:
                    distance_to_support = None
                try:
                    distance_to_resistance = round((strong_resistance - current_price) / current_price * 100, 2)
                except Exception:
                    distance_to_resistance = None

                # Bias di trend semplice
                if not np.isnan(sma200) and current_price > sma200 and sma50 > sma200:
                    trend_bias = "BULLISH"
                elif not np.isnan(sma200) and current_price < sma200 and sma50 < sma200:
                    trend_bias = "BEARISH"
                else:
                    trend_bias = "NEUTRAL"

                levels = {
                    "supports": sorted([float(x) for x in s_candidates if not np.isnan(x)]),
                    "resistances": sorted([float(x) for x in r_candidates if not np.isnan(x)]),
                }

                result = {
                    "symbol": symbol,
                    "timestamp": datetime.now().isoformat(),

                    "current_price": float(current_price),
                    "strong_support": _nan_to_none(strong_support),
                    "strong_resistance": _nan_to_none(strong_resistance),
                    "distance_to_support": distance_to_support,
                    "distance_to_resistance": distance_to_resistance,

                    "pivot_points": pivot_points,
                    "levels": levels,
                    "trend_bias": trend_bias,

                    "data_quality": data_quality,
                    "source": source,
                    "source_symbol": used_symbol,

                    "signals": {},
                    "indicators": indicators,

                    "note": f"Analisi per {symbol} su dati {data_quality} ({source})",
                }

                logger.info(
                    f"[OK] S/R calcolati ({data_quality}) {symbol}: {current_price:.4f} "
                    f"(S: {result['strong_support']:.4f}, R: {result['strong_resistance']:.4f})"
                )
                return result

           # ===================== FALLBACK SIMULATO =====================
            logger.info(f"[WARN] Live non disponibili per {symbol} – uso fallback simulato")
            current_price = float(self.get_current_price(symbol))

            # Se disponibili utility di calcolo livelli, usale
            try:
                levels = self._calculate_key_levels(current_price, symbol)
                strong_resistance = self._find_strongest_level(levels["resistances"], current_price)
                strong_support = self._find_strongest_level(levels["supports"], current_price)
                pivot_points = self._calculate_pivot_points(current_price)
                all_resistances = [float(x) for x in levels["resistances"][:3]]
                all_supports = [float(x) for x in levels["supports"][:3]]
            except Exception:
                # fallback minimale
                offsets = np.array([0.005, 0.01, 0.02])
                supps = list((current_price * (1 - offsets)).tolist()) + [current_price * 0.985]
                ress = list((current_price * (1 + offsets)).tolist()) + [current_price * 1.015]
                strong_support = max([s for s in supps if s <= current_price], default=current_price * 0.99)
                strong_resistance = min([r for r in ress if r >= current_price], default=current_price * 1.01)
                pivot_points = {
                    "pivot": float(current_price),
                    "r1": float(current_price * 1.005),
                    "s1": float(current_price * 0.995),
                    "r2": float(current_price * 1.01),
                    "s2": float(current_price * 0.99),
                }
                all_resistances, all_supports = ress[:3], supps[:3]

            result = {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),

                "current_price": float(current_price),
                "strong_resistance": float(strong_resistance),
                "medium_resistance": float(all_resistances[1] if len(all_resistances) > 1 else strong_resistance),
                "strong_support": float(strong_support),
                "critical_support": float(all_supports[-1] if len(all_supports) > 0 else strong_support),

                "all_resistances": [float(x) for x in all_resistances],
                "all_supports": [float(x) for x in all_supports],

                "pivot_points": pivot_points,

                "distance_to_resistance": round((strong_resistance - current_price) / current_price * 100, 2),
                "distance_to_support": round((current_price - strong_support) / current_price * 100, 2),

                "price_position": self._determine_price_position(current_price, strong_support, strong_resistance),
                "trend_bias": self._determine_trend_bias(
                    current_price, {"supports": all_supports, "resistances": all_resistances}
                ),

                "data_quality": "simulated",
                "source": "fallback",
                "source_symbol": None,

                "indicators": {},
                "signals": {},

                "note": f"Analisi per {symbol} basata su algoritmo simulato",
            }

            logger.info(
                f"[OK] S/R calcolati (fallback) {symbol}: {current_price:.4f} "
                f"(S: {result['strong_support']:.4f}, R: {result['strong_resistance']:.4f})"
            )
            return result

        except Exception as e:
            logger.error(f"[ERROR] Errore calcolo S/R per {symbol}: {e}")
            # fallback minimale d'emergenza - VERSIONE CORRETTA CON price_position
            try:
                current_price = float(self.get_current_price(symbol))
            except Exception:
                current_price = float(self.base_prices.get(symbol, 100.0))
            
            strong_support = current_price * 0.99
            strong_resistance = current_price * 1.01
            
            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "current_price": float(current_price),
                "strong_support": float(strong_support),
                "strong_resistance": float(strong_resistance),
                "distance_to_support": round((current_price - strong_support) / current_price * 100, 2),
                "distance_to_resistance": round((strong_resistance - current_price) / current_price * 100, 2),
                "pivot_points": {"pivot": float(current_price)},
                "levels": {},
                "trend_bias": "NEUTRAL",
                # 🔑 FIX PRINCIPALE: Aggiungi price_position mancante
                "price_position": self._determine_price_position(current_price, strong_support, strong_resistance),
                "data_quality": "simulated",
                "source": "fallback",
                "source_symbol": None,
                "indicators": {},
                "signals": {},
                "note": f"Analisi per {symbol} (fallback d'emergenza)",
            }

    # -------------------------------------------------------------------------
    # INDICATORI
    # -------------------------------------------------------------------------
    def _compute_indicators(self, df: pd.DataFrame) -> Dict[str, Optional[float]]:
        """SMA50/200, RSI14, ATR14, MACD, Volatility20 - robusto con dati scarsi."""
        out: Dict[str, Optional[float]] = {
            "sma50": None, "sma200": None, "rsi14": None,
            "atr14": None, "macd": None, "macd_signal": None, "volatility20": None
        }

        close = df["Close"].copy()
        n = len(close)

        # SMA
        if n >= 50:
            out["sma50"] = float(close.rolling(50).mean().iloc[-1])
        if n >= 200:
            out["sma200"] = float(close.rolling(200).mean().iloc[-1])

        # RSI 14
        if n >= 15:
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            val = rsi.iloc[-1]
            out["rsi14"] = float(val) if pd.notna(val) else None

        # ATR 14
        if n >= 15:
            tr = pd.concat([
                df["High"] - df["Low"],
                (df["High"] - df["Close"].shift()).abs(),
                (df["Low"] - df["Close"].shift()).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            out["atr14"] = float(atr) if pd.notna(atr) else None

        # MACD (12, 26, 9)
        if n >= 26:
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            macd_signal = macd.ewm(span=9, adjust=False).mean()
            out["macd"] = float(macd.iloc[-1]) if pd.notna(macd.iloc[-1]) else None
            out["macd_signal"] = float(macd_signal.iloc[-1]) if pd.notna(macd_signal.iloc[-1]) else None

        # Volatility 20 (std %)
        if n >= 21:
            vol20 = close.pct_change().rolling(20).std().iloc[-1] * 100
            out["volatility20"] = float(vol20) if pd.notna(vol20) else None

        return out

    # -------------------------------------------------------------------------
    # LOGICHE FALLBACK
    # -------------------------------------------------------------------------
    def _calculate_key_levels(self, price: float, symbol: str) -> Dict:
        psychological_levels = self._get_psychological_levels(price)
        percentage_levels = self._get_percentage_levels(price)
        asset_specific = self._get_asset_specific_levels(price, symbol)

        all_resistances, all_supports = [], []
        for level_set in [psychological_levels, percentage_levels, asset_specific]:
            all_resistances.extend([l for l in level_set["resistances"] if l > price])
            all_supports.extend([l for l in level_set["supports"] if l < price])

        resistances = sorted(list(set(all_resistances)))[:5]
        supports = sorted(list(set(all_supports)), reverse=True)[:5]
        return {"resistances": resistances, "supports": supports}

    def _get_psychological_levels(self, price: float) -> Dict:
        magnitude = 10 ** (len(str(int(price))) - 1) if price >= 1 else 0.1
        base = int(price / magnitude) * magnitude if magnitude >= 1 else round(price, 1)
        resistances, supports = [], []
        for i in range(1, 4):
            level = base + (magnitude * i)
            if level > price:
                resistances.append(level)
        for i in range(0, 3):
            level = base - (magnitude * i)
            if level < price and level > 0:
                supports.append(level)
        return {"resistances": resistances, "supports": supports}

    def _get_percentage_levels(self, price: float) -> Dict:
        percentages = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]
        resistances = [price * (1 + pct) for pct in percentages]
        supports = [price * (1 - pct) for pct in percentages]
        return {"resistances": resistances, "supports": supports}

    def _get_asset_specific_levels(self, price: float, symbol: str) -> Dict:
        if symbol in ["GOLD", "SILVER"]:
            increments = [5, 10, 20, 25, 50, 100]
            base = int(price / 10) * 10
        elif symbol == "USD":
            increments = [0.5, 1.0, 1.5, 2.0]
            base = int(price)
        elif symbol in ["EUR", "GBP", "AUD"]:
            increments = [0.005, 0.01, 0.02, 0.05]
            base = round(price, 3)
        elif symbol in ["SP500", "NASDAQ"]:
            increments = [25, 50, 100, 200]
            base = int(price / 50) * 50
        else:
            increments = [1, 2, 5, 10]
            base = int(price)

        resistances = [base + inc for inc in increments if base + inc > price]
        supports = [base - inc for inc in increments if base - inc < price and base - inc > 0]
        return {"resistances": resistances, "supports": supports}

    def _find_strongest_level(self, levels: List[float], current_price: float) -> float:
        if not levels:
            return current_price * 1.02
        return min(levels, key=lambda x: abs(x - current_price))

    def _calculate_pivot_points(self, current_price: float) -> Dict:
        high = current_price * 1.015
        low = current_price * 0.985
        close = current_price
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        return {
            "pivot": float(pivot),
            "R1": float(r1), "R2": float(r2), "R3": float(r3),
            "S1": float(s1), "S2": float(s2), "S3": float(s3),
            "calculation_base": "simulated_ohlc",
        }

    def _determine_price_position(self, price: float, support: float, resistance: float) -> str:
        range_size = max(resistance - support, 1e-9)
        price_in_range = (price - support) / range_size
        if price_in_range > 0.8:
            return "NEAR_RESISTANCE"
        elif price_in_range < 0.2:
            return "NEAR_SUPPORT"
        elif 0.4 <= price_in_range <= 0.6:
            return "MIDDLE_RANGE"
        elif price_in_range > 0.6:
            return "UPPER_RANGE"
        else:
            return "LOWER_RANGE"

    def _determine_trend_bias(self, price: float, levels: Dict) -> str:
        resistances = levels["resistances"]
        supports = levels["supports"]
        if not resistances or not supports:
            return "NEUTRAL"
        avg_resistance_distance = float(np.mean([abs(r - price) for r in resistances[:2]]))
        avg_support_distance = float(np.mean([abs(s - price) for s in supports[:2]]))
        if avg_support_distance < avg_resistance_distance:
            return "BULLISH"
        elif avg_resistance_distance < avg_support_distance:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def _create_fallback_sr(self, symbol: str) -> Dict:
        current = float(self.base_prices.get(symbol, 100.0))
        return {
            "symbol": symbol,
            "current_price": current,
            "strong_resistance": current * 1.02,
            "medium_resistance": current * 1.015,
            "strong_support": current * 0.98,
            "critical_support": current * 0.975,
            "all_resistances": [current * 1.02, current * 1.035, current * 1.05],
            "all_supports": [current * 0.98, current * 0.965, current * 0.95],
            "pivot_points": {
                "pivot": current,
                "R1": current * 1.01, "R2": current * 1.02,
                "S1": current * 0.99, "S2": current * 0.98,
            },
            "distance_to_resistance": 2.0,
            "distance_to_support": 2.0,
            "price_position": "MIDDLE_RANGE",
            "trend_bias": "NEUTRAL",
            "timestamp": datetime.now().isoformat(),
            "data_quality": "fallback",
            "source": "fallback",
            "source_symbol": None,
            "indicators": {},
            "note": "Livelli di emergenza - Twelve Data non disponibile",
        }

    # -------------------------------------------------------------------------
    # SEGNALI
    # -------------------------------------------------------------------------
    def get_technical_signals(self, symbol: str) -> Dict:
        """Genera segnali tecnici completi per un simbolo."""
        try:
            sr_data = self.calculate_support_resistance(symbol)
            current_price = sr_data["current_price"]

            signals = {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "current_price": current_price,
                "signals": {},
            }

            sr_signal = self._calculate_sr_signal(sr_data)
            signals["signals"]["support_resistance"] = sr_signal

            trend_signal = self._calculate_trend_signal(sr_data)
            signals["signals"]["trend"] = trend_signal

            position_signal = self._calculate_position_signal(sr_data)
            signals["signals"]["position"] = position_signal

            overall_signal = self._combine_signals(signals["signals"])
            signals["overall"] = overall_signal

            return signals

        except Exception as e:
            logger.error(f"[ERROR] Errore segnali tecnici {symbol}: {e}")
            return {"symbol": symbol, "error": str(e), "timestamp": datetime.now().isoformat()}

    def _calculate_sr_signal(self, sr_data: Dict) -> Dict:
        dR = float(sr_data["distance_to_resistance"])
        dS = float(sr_data["distance_to_support"])
        if dR <= 1.0:
            return {"signal": "SELL", "strength": 80, "reason": f"Vicino a resistenza ({dR:.1f}%)",
                    "distance_resistance": dR, "distance_support": dS}
        if dS <= 1.0:
            return {"signal": "BUY", "strength": 80, "reason": f"Vicino a supporto ({dS:.1f}%)",
                    "distance_resistance": dR, "distance_support": dS}
        if dR <= 2.0:
            return {"signal": "SELL", "strength": 60, "reason": f"Prossimo a resistenza ({dR:.1f}%)",
                    "distance_resistance": dR, "distance_support": dS}
        if dS <= 2.0:
            return {"signal": "BUY", "strength": 60, "reason": f"Prossimo a supporto ({dS:.1f}%)",
                    "distance_resistance": dR, "distance_support": dS}
        return {"signal": "NEUTRAL", "strength": 50, "reason": "Lontano da livelli chiave",
                "distance_resistance": dR, "distance_support": dS}

    def _calculate_trend_signal(self, sr_data: Dict) -> Dict:
        bias = sr_data["trend_bias"]
        if bias == "BULLISH":
            return {"signal": "BUY", "strength": 70, "bias": bias, "reason": f"Trend bias: {bias}"}
        if bias == "BEARISH":
            return {"signal": "SELL", "strength": 70, "bias": bias, "reason": f"Trend bias: {bias}"}
        return {"signal": "NEUTRAL", "strength": 50, "bias": bias, "reason": f"Trend bias: {bias}"}

    def _calculate_position_signal(self, sr_data: Dict) -> Dict:
        
        pos = sr_data.get("price_position")
        
        if not pos:
            # Se mancante, calcolalo al volo
            current_price = sr_data.get("current_price", 100.0)
            strong_support = sr_data.get("strong_support", current_price * 0.95)
            strong_resistance = sr_data.get("strong_resistance", current_price * 1.05)
            
            pos = self._determine_price_position(current_price, strong_support, strong_resistance)
            logger.warning(f"price_position mancante, calcolato: {pos}")
        
        # Mapping robusto con fallback
        mapping = {
            "NEAR_RESISTANCE": {"signal": "SELL", "strength": 75, "reason": "Prezzo vicino a resistenza"},
            "NEAR_SUPPORT": {"signal": "BUY", "strength": 75, "reason": "Prezzo vicino a supporto"},
            "UPPER_RANGE": {"signal": "SELL", "strength": 55, "reason": "Prezzo nella parte alta del range"},
            "LOWER_RANGE": {"signal": "BUY", "strength": 55, "reason": "Prezzo nella parte bassa del range"},
            "MIDDLE_RANGE": {"signal": "NEUTRAL", "strength": 50, "reason": "Prezzo nel mezzo del range"},
            "BETWEEN_LEVELS": {"signal": "NEUTRAL", "strength": 50, "reason": "Prezzo tra i livelli"},
        }
        
        # Usa il mapping o fallback
        result = mapping.get(pos, {
            "signal": "NEUTRAL", 
            "strength": 50, 
            "reason": f"Posizione prezzo non determinata: {pos}"
        })
        
        # Aggiungi posizione per debug
        result["position"] = pos
        
        return result

    def _combine_signals(self, signals: Dict) -> Dict:
        weights = {"support_resistance": 0.4, "trend": 0.3, "position": 0.3}
        signal_values = {"STRONG_BUY": 2, "BUY": 1, "NEUTRAL": 0, "SELL": -1, "STRONG_SELL": -2}

        weighted_score = 0.0
        total_strength = 0.0
        dist = {"BUY": 0, "SELL": 0, "NEUTRAL": 0}

        for k, w in weights.items():
            if k not in signals:
                continue
            sdata = signals[k]
            signal = sdata.get("signal", "NEUTRAL")
            strength = float(sdata.get("strength", 50))

            if "BUY" in signal:
                dist["BUY"] += 1
            elif "SELL" in signal:
                dist["SELL"] += 1
            else:
                dist["NEUTRAL"] += 1

            val = float(signal_values.get(signal, 0))
            weighted_score += val * w * (strength / 100.0)
            total_strength += strength * w

        if weighted_score > 0.6:
            final_signal = "STRONG_BUY"
        elif weighted_score > 0.2:
            final_signal = "BUY"
        elif weighted_score < -0.6:
            final_signal = "STRONG_SELL"
        elif weighted_score < -0.2:
            final_signal = "SELL"
        else:
            final_signal = "NEUTRAL"

        confidence = min(abs(weighted_score) * 100.0, 95.0) if weighted_score != 0 else 50.0

        return {
            "signal": final_signal,
            "confidence": confidence,
            "weighted_score": weighted_score,
            "signal_distribution": dist,
            "consensus": max(dist, key=dist.get),
            "total_strength": total_strength,
        }

    # -------------------------------------------------------------------------
    # ECONOMICS & SENTIMENT (mock)
    # -------------------------------------------------------------------------
    def get_economic_calendar(self, days_ahead: int = 7) -> List[Dict]:
        events = []
        base_date = datetime.now()
        typical_events = [
            {"name": "FOMC Meeting Decision", "time": "20:00", "impact": "HIGH", "currency": "USD",
             "description": "Probabile taglio 25bps - evento rilevante per l'oro",
             "category": "monetary_policy", "importance": 10, "expected_impact_gold": "HIGH_POSITIVE"},
            {"name": "US Core CPI m/m", "time": "14:30", "impact": "HIGH", "currency": "USD",
             "description": "Inflazione core",
             "category": "inflation", "importance": 9, "expected_impact_gold": "POSITIVE"},
            {"name": "Non-Farm Payrolls", "time": "14:30", "impact": "HIGH", "currency": "USD",
             "description": "Dinamica del mercato del lavoro",
             "category": "employment", "importance": 8, "expected_impact_gold": "POSITIVE"},
            {"name": "ECB Interest Rate Decision", "time": "13:45", "impact": "HIGH", "currency": "EUR",
             "description": "Decisione tassi BCE",
             "category": "monetary_policy", "importance": 8, "expected_impact_gold": "NEUTRAL"},
            {"name": "US GDP Preliminary", "time": "14:30", "impact": "MEDIUM", "currency": "USD",
             "description": "Crescita economica",
             "category": "growth", "importance": 7, "expected_impact_gold": "POSITIVE"},
            {"name": "China Manufacturing PMI", "time": "03:00", "impact": "MEDIUM", "currency": "CNY",
             "description": "PMI manifatturiero",
             "category": "business", "importance": 6, "expected_impact_gold": "NEUTRAL"},
            {"name": "UK Inflation Rate y/y", "time": "08:00", "impact": "MEDIUM", "currency": "GBP",
             "description": "Inflazione UK",
             "category": "inflation", "importance": 6, "expected_impact_gold": "POSITIVE"},
        ]
        for i, tpl in enumerate(typical_events[:days_ahead]):
            event_date = base_date + timedelta(days=i + 1)
            if event_date.weekday() >= 5 and tpl["importance"] >= 8:
                event_date += timedelta(days=2)
            e = tpl.copy()
            e.update({
                "date": event_date.strftime("%Y-%m-%d"),
                "day_name": event_date.strftime("%A"),
                "days_until": (event_date - base_date).days,
                "is_today": event_date.date() == base_date.date(),
                "is_tomorrow": event_date.date() == (base_date + timedelta(days=1)).date(),
                "formatted_date": event_date.strftime("%d %b").upper(),
            })
            events.append(e)
        events.sort(key=lambda x: (x["date"], -x["importance"]))
        logger.info(f"[OK] Calendario economico generato: {len(events)} eventi")
        return events

    def get_market_sentiment_data(self) -> Dict:
        sentiment_data = {
            "timestamp": datetime.now().isoformat(),
            "overall_sentiment": "RISK_ON_MODERATE",
            "indicators": {
                "vix": {"value": 18.5, "change": -1.2, "level": "MODERATE",
                        "description": "VIX moderato", "impact_on_gold": "NEUTRAL"},
                "dollar_index": {"value": 103.45, "change": -0.12, "trend": "WEAKENING",
                                 "description": "Dollar Index in indebolimento", "impact_on_gold": "POSITIVE"},
                "yield_10y": {"value": 3.85, "change": -0.05, "trend": "DECLINING",
                              "description": "Rendimenti decennali in calo", "impact_on_gold": "POSITIVE"},
                "fed_funds_futures": {"september_cut_25bps": 87, "september_cut_50bps": 13,
                                      "description": "Mercato prezza taglio Fed", "impact_on_gold": "VERY_POSITIVE"},
            },
            "themes": [
                {"theme": "Allentamento Monetario Globale", "relevance": "HIGH",
                 "impact_on_gold": "VERY_POSITIVE", "description": "Fed e BCE verso tagli tassi"},
                {"theme": "Disinflazione in Corso", "relevance": "HIGH",
                 "impact_on_gold": "POSITIVE", "description": "Trend inflazione favorevole ai metalli preziosi"},
                {"theme": "Tensioni Geopolitiche", "relevance": "MEDIUM",
                 "impact_on_gold": "POSITIVE", "description": "Incertezza che sostiene beni rifugio"},
                {"theme": "Indebolimento Dollaro", "relevance": "MEDIUM",
                 "impact_on_gold": "POSITIVE", "description": "DXY sotto pressione"},
            ],
            "summary": {
                "gold_supportive_factors": 6,
                "gold_negative_factors": 1,
                "net_sentiment": "BULLISH",
                "confidence": 78,
            },
        }
        logger.info("[OK] Sentiment di mercato generato")
        return sentiment_data


# =============================================================================
# FUNZIONI HELPER PER LE API (come nel tuo backend)
# =============================================================================

# PATCH C: Istanza globale del TechnicalAnalyzer per performance
GLOBAL_TA = TechnicalAnalyzer()

def analyze_symbol_complete(symbol: str) -> Dict:
    # CORRETTO: usa GLOBAL_TA invece di creare nuova istanza
    analyzer = GLOBAL_TA
    try:
        sr_analysis = analyzer.calculate_support_resistance(symbol)
        technical_signals = analyzer.get_technical_signals(symbol)
        economic_calendar = analyzer.get_economic_calendar(7)
        market_sentiment = analyzer.get_market_sentiment_data()
        combined = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "support_resistance": sr_analysis,
            "technical_signals": technical_signals,
            "economic_calendar": economic_calendar,
            "market_sentiment": market_sentiment,
            "status": "SUCCESS",
        }
        return combined
    except Exception as e:
        logger.error(f"[ERROR] Errore analisi completa {symbol}: {e}")
        return {"symbol": symbol, "error": str(e), "status": "ERROR", "timestamp": datetime.now().isoformat()}

def get_symbol_technical_data(symbol: str) -> Dict:
    # CORRETTO: usa direttamente GLOBAL_TA
    return GLOBAL_TA.calculate_support_resistance(symbol)

def get_economic_events() -> List[Dict]:
    # CORRETTO: usa direttamente GLOBAL_TA
    return GLOBAL_TA.get_economic_calendar()

def get_market_sentiment() -> Dict:
    # CORRETTO: usa direttamente GLOBAL_TA
    return GLOBAL_TA.get_market_sentiment_data()

def get_technical_signals(symbol: str) -> Dict:
    # CORRETTO: usa direttamente GLOBAL_TA
    return GLOBAL_TA.get_technical_signals(symbol)


# =============================================================================
# TEST MANUALE
# =============================================================================
def test_technical_analyzer():
    print("[CONFIG] Test Technical Analyzer (Twelve Data)")
    print("=" * 50)
    test_symbols = ["GOLD", "EUR", "GBP", "AUD", "JPY", "CHF", "CAD", "USD"]
    for symbol in test_symbols:
        print(f"\n[DATA] Test {symbol}...")
        try:
            analysis = analyze_symbol_complete(symbol)
            if analysis.get("status") == "SUCCESS":
                sr = analysis["support_resistance"]
                overall = analysis["technical_signals"].get("overall", {})
                print(f"  Source: {sr.get('source')} {sr.get('source_symbol')}")
                print(f"  Prezzo: {sr['current_price']:.5f}  "
                      f"S: {sr['strong_support']:.5f}  R: {sr['strong_resistance']:.5f}  "
                      f"({sr['data_quality']})")
                print(f"  Segnale: {overall.get('signal','NEUTRAL')} "
                      f"({round(overall.get('confidence',50))}%)")
                print("  [OK] OK")
            else:
                print(f"  [ERROR] Fail: {analysis.get('error')}")
        except Exception as e:
            print(f"  [ERROR] Errore: {e}")
    print("\n[OK] Test completato")

if __name__ == "__main__":
    test_technical_analyzer()
