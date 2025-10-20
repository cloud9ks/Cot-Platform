# cache_manager.py
"""
Sistema di cache ottimizzato per COT Platform
Risolve i problemi di performance e richieste duplicate
"""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Callable
from functools import wraps
import asyncio
import pickle

logger = logging.getLogger("cache_manager")

class CacheManager:
    """
    Gestore cache in-memory semplice ma efficace.
    Non richiede Redis per funzionare.
    """
    
    def __init__(self):
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.hits = 0
        self.misses = 0
        self.lock = asyncio.Lock()
        
        # TTL configurazione (in secondi)
        self.ttl_config = {
            'price': 60,           # 1 minuto per prezzi live
            'technical': 300,      # 5 minuti per analisi tecniche  
            'cot_data': 3600,      # 1 ora per dati COT
            'prediction': 1800,    # 30 minuti per predizioni
            'scrape': 86400,       # 24 ore per scraping
            'complete': 600,       # 10 minuti per analisi complete
            'economic': 1800,      # 30 minuti per dati economici
            'default': 300         # 5 minuti default
        }
        
        logger.info("Cache Manager inizializzato")
    
    def _get_cache_key(self, category: str, key: str) -> str:
        """Genera chiave univoca per la cache"""
        return f"{category}:{key}"
    
    def get(self, category: str, key: str) -> Optional[Any]:
        """Recupera valore dalla cache se non scaduto"""
        cache_key = self._get_cache_key(category, key)
        
        if cache_key in self.cache:
            value, expiry = self.cache[cache_key]
            if datetime.now() < expiry:
                self.hits += 1
                logger.debug(f"Cache HIT: {cache_key}")
                return value
            else:
                # Rimuovi entry scaduta
                del self.cache[cache_key]
                logger.debug(f"Cache EXPIRED: {cache_key}")
        
        self.misses += 1
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    
    async def get_async(self, category: str, key: str) -> Optional[Any]:
        """Versione asincrona di get"""
        async with self.lock:
            return self.get(category, key)
    
    def set(self, category: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Salva valore in cache con TTL"""
        cache_key = self._get_cache_key(category, key)
        
        if ttl is None:
            ttl = self.ttl_config.get(category, self.ttl_config['default'])
        
        expiry = datetime.now() + timedelta(seconds=ttl)
        self.cache[cache_key] = (value, expiry)
        
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
        
        # Cleanup se troppi elementi
        if len(self.cache) > 1000:
            self._cleanup()
    
    async def set_async(self, category: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Versione asincrona di set"""
        async with self.lock:
            self.set(category, key, value, ttl)
    
    def invalidate(self, category: str, key: Optional[str] = None) -> None:
        """Invalida cache per categoria o chiave specifica"""
        if key:
            cache_key = self._get_cache_key(category, key)
            if cache_key in self.cache:
                del self.cache[cache_key]
                logger.info(f"Cache invalidata: {cache_key}")
        else:
            # Invalida tutta la categoria
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{category}:")]
            for k in keys_to_remove:
                del self.cache[k]
            logger.info(f"Cache invalidata per categoria: {category} ({len(keys_to_remove)} entries)")
    
    def _cleanup(self) -> None:
        """Rimuove entries scadute"""
        now = datetime.now()
        expired = [k for k, (_, exp) in self.cache.items() if exp < now]
        
        for k in expired:
            del self.cache[k]
        
        if expired:
            logger.info(f"Cleanup cache: rimosse {len(expired)} entries scadute")
    
    def clear_all(self) -> None:
        """Pulisce tutta la cache"""
        size = len(self.cache)
        self.cache.clear()
        logger.info(f"Cache completamente pulita: {size} entries rimosse")
    
    def get_stats(self) -> Dict[str, Any]:
        """Ritorna statistiche cache"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'entries': len(self.cache),
            'categories': len(set(k.split(':')[0] for k in self.cache.keys()))
        }


def cached(category: str, ttl: Optional[int] = None):
    """
    Decoratore per cache automatica di funzioni.
    Funziona sia con funzioni sincrone che asincrone.
    """
    def decorator(func: Callable) -> Callable:
        # Determina se la funzione è async
        is_async = asyncio.iscoroutinefunction(func)
        
        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Genera chiave cache basata su funzione e argomenti
                cache_key = f"{func.__name__}:{_generate_cache_key(args, kwargs)}"
                
                # Ottieni cache manager dall'istanza o globale
                cache_manager = getattr(args[0], 'cache_manager', None) if args else None
                if not cache_manager:
                    cache_manager = GLOBAL_CACHE
                
                # Prova a recuperare dalla cache
                cached_value = await cache_manager.get_async(category, cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Esegui funzione
                result = await func(*args, **kwargs)
                
                # Salva in cache
                await cache_manager.set_async(category, cache_key, result, ttl)
                
                return result
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Genera chiave cache basata su funzione e argomenti
                cache_key = f"{func.__name__}:{_generate_cache_key(args, kwargs)}"
                
                # Ottieni cache manager dall'istanza o globale
                cache_manager = getattr(args[0], 'cache_manager', None) if args else None
                if not cache_manager:
                    cache_manager = GLOBAL_CACHE
                
                # Prova a recuperare dalla cache
                cached_value = cache_manager.get(category, cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Esegui funzione
                result = func(*args, **kwargs)
                
                # Salva in cache
                cache_manager.set(category, cache_key, result, ttl)
                
                return result
            return sync_wrapper
    
    return decorator


def _generate_cache_key(args: tuple, kwargs: dict) -> str:
    """Genera una chiave univoca per gli argomenti"""
    # Crea una stringa rappresentativa degli argomenti
    key_parts = []
    
    # Aggiungi args (salta self/cls se presente)
    start_idx = 1 if args and hasattr(args[0], '__class__') else 0
    for arg in args[start_idx:]:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            key_parts.append(str(type(arg).__name__))
    
    # Aggiungi kwargs ordinati
    for k in sorted(kwargs.keys()):
        v = kwargs[k]
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}={v}")
        else:
            key_parts.append(f"{k}={type(v).__name__}")
    
    # Crea hash MD5 per chiavi lunghe
    key_str = ":".join(key_parts)
    if len(key_str) > 100:
        return hashlib.md5(key_str.encode()).hexdigest()[:16]
    
    return key_str


# Cache globale singleton
GLOBAL_CACHE = CacheManager()


# ============================================================================
# INTEGRAZIONE CON IL TUO BACKEND
# ============================================================================

class CachedEndpoints:
    """
    Esempio di come usare il cache manager nei tuoi endpoint.
    Aggiungi questi decoratori alle tue funzioni API.
    """
    
    def __init__(self):
        self.cache_manager = GLOBAL_CACHE
    
    @cached(category='technical', ttl=300)  # Cache 5 minuti
    async def get_technical_analysis(self, symbol: str):
        """Endpoint per analisi tecnica con cache automatica"""
        # Il tuo codice esistente qui
        pass
    
    @cached(category='cot_data', ttl=3600)  # Cache 1 ora
    def get_cot_data(self, symbol: str, days: int = 90):
        """Endpoint per dati COT con cache automatica"""
        # Il tuo codice esistente qui
        pass
    
    @cached(category='complete', ttl=600)  # Cache 10 minuti
    async def get_complete_analysis(self, symbol: str):
        """Analisi completa con cache automatica"""
        # Il tuo codice esistente qui
        pass
    
    async def force_refresh(self, symbol: str):
        """Forza refresh dei dati invalidando la cache"""
        self.cache_manager.invalidate('technical', symbol)
        self.cache_manager.invalidate('cot_data', symbol)
        self.cache_manager.invalidate('complete', symbol)
        self.cache_manager.invalidate('prediction', symbol)
        
        logger.info(f"Cache invalidata per {symbol}")
        
        # Ricarica i dati
        return await self.get_complete_analysis(symbol)


# ============================================================================
# MODIFICHE DA FARE NEL TUO main.py o app.py
# ============================================================================

"""
# AGGIUNGI ALL'INIZIO DEL TUO FILE PRINCIPALE:

from cache_manager import GLOBAL_CACHE, cached

# NEI TUOI ENDPOINT, AGGIUNGI IL DECORATORE @cached:

@app.route('/api/analysis/complete/<symbol>')
@cached(category='complete', ttl=600)  # <-- AGGIUNGI QUESTA RIGA
async def get_complete_analysis(symbol: str):
    # ... il tuo codice esistente
    
@app.route('/api/technical/<symbol>')
@cached(category='technical', ttl=300)  # <-- AGGIUNGI QUESTA RIGA
async def get_technical_analysis(symbol: str):
    # ... il tuo codice esistente

@app.route('/api/data/<symbol>')
@cached(category='cot_data', ttl=3600)  # <-- AGGIUNGI QUESTA RIGA
async def get_cot_data(symbol: str):
    # ... il tuo codice esistente

# AGGIUNGI UN ENDPOINT PER LE STATISTICHE CACHE:

@app.route('/api/cache/stats')
async def cache_stats():
    return jsonify(GLOBAL_CACHE.get_stats())

# AGGIUNGI UN ENDPOINT PER PULIRE LA CACHE:

@app.route('/api/cache/clear', methods=['POST'])
async def cache_clear():
    GLOBAL_CACHE.clear_all()
    return jsonify({"status": "Cache cleared"})

# MODIFICA L'ENDPOINT DI SCRAPING PER INVALIDARE LA CACHE:

@app.route('/api/scrape/<symbol>')
async def scrape_symbol(symbol: str):
    # ... il tuo codice di scraping esistente
    
    # Dopo scraping riuscito, invalida cache vecchia:
    GLOBAL_CACHE.invalidate('technical', symbol)
    GLOBAL_CACHE.invalidate('cot_data', symbol)
    GLOBAL_CACHE.invalidate('complete', symbol)
    
    return result
"""