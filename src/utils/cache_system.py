"""
Comprehensive Caching System for Model Card Generation

This module provides a robust caching system to track and store all scraped
and extracted information during model card generation. This enables debugging
of incomplete model cards by allowing inspection of what data was actually
retrieved and processed at each stage.

Features:
- Multi-level caching (web scraping, AI extraction, pipeline stages)
- Detailed logging of cache hits/misses
- Data inspection tools for debugging
- Automatic cache cleanup and management
- Support for different cache backends (file, memory, database)
"""

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
import pickle
import gzip

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata"""
    key: str
    data: Any
    timestamp: datetime
    source: str  # 'web_scraping', 'ai_extraction', 'gemini_agent', etc.
    url: Optional[str] = None
    model_name: Optional[str] = None
    stage: Optional[str] = None  # 'discovery', 'extraction', 'generation', etc.
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class CacheStats:
    """Cache statistics for monitoring"""
    total_entries: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    last_cleanup: Optional[datetime] = None

class CacheSystem:
    """
    Comprehensive caching system for model card generation pipeline.
    
    Provides multi-level caching with detailed logging and inspection capabilities.
    """
    
    def __init__(self, cache_dir: Union[str, Path] = "cache", max_size_mb: int = 500):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_mb = max_size_mb
        
        # Initialize cache storage
        self.db_path = self.cache_dir / "cache.db"
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.stats = CacheStats()
        
        # Initialize database
        self._init_database()
        
        # Load existing cache stats
        self._load_stats()
        
        logger.info(f"Cache system initialized at {self.cache_dir}")
    
    def _init_database(self):
        """Initialize SQLite database for persistent cache storage"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    data BLOB,
                    timestamp TEXT,
                    source TEXT,
                    url TEXT,
                    model_name TEXT,
                    stage TEXT,
                    metadata TEXT,
                    size_bytes INTEGER
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_stats (
                    stat_name TEXT PRIMARY KEY,
                    stat_value TEXT,
                    updated_at TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source ON cache_entries(source)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_name ON cache_entries(model_name)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stage ON cache_entries(stage)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON cache_entries(timestamp)
            """)
    
    def _load_stats(self):
        """Load cache statistics from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT stat_name, stat_value FROM cache_stats")
                for stat_name, stat_value in cursor.fetchall():
                    if stat_name == "total_entries":
                        self.stats.total_entries = int(stat_value)
                    elif stat_name == "hits":
                        self.stats.hits = int(stat_value)
                    elif stat_name == "misses":
                        self.stats.misses = int(stat_value)
                    elif stat_name == "evictions":
                        self.stats.evictions = int(stat_value)
                    elif stat_name == "last_cleanup":
                        if stat_value:
                            self.stats.last_cleanup = datetime.fromisoformat(stat_value)
        except Exception as e:
            logger.warning(f"Failed to load cache stats: {e}")
    
    def _save_stats(self):
        """Save cache statistics to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                stats_data = [
                    ("total_entries", str(self.stats.total_entries)),
                    ("hits", str(self.stats.hits)),
                    ("misses", str(self.stats.misses)),
                    ("evictions", str(self.stats.evictions)),
                    ("last_cleanup", self.stats.last_cleanup.isoformat() if self.stats.last_cleanup else None),
                ]
                
                conn.executemany(
                    "INSERT OR REPLACE INTO cache_stats (stat_name, stat_value, updated_at) VALUES (?, ?, ?)",
                    [(name, value, datetime.now().isoformat()) for name, value in stats_data]
                )
        except Exception as e:
            logger.warning(f"Failed to save cache stats: {e}")
    
    def _generate_key(self, source: str, identifier: str, **kwargs) -> str:
        """Generate a unique cache key"""
        # Create a deterministic key from the source, identifier, and any additional parameters
        key_data = {
            "source": source,
            "identifier": identifier,
            **kwargs
        }
        
        # Sort keys for consistent hashing
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for storage"""
        try:
            # Try JSON first for readability
            if isinstance(data, (dict, list, str, int, float, bool)) or data is None:
                return json.dumps(data, ensure_ascii=False).encode('utf-8')
            else:
                # Fall back to pickle for complex objects
                return pickle.dumps(data)
        except Exception:
            # Final fallback to pickle
            return pickle.dumps(data)
    
    def _deserialize_data(self, data_bytes: bytes) -> Any:
        """Deserialize data from storage"""
        try:
            # Try JSON first
            return json.loads(data_bytes.decode('utf-8'))
        except Exception:
            try:
                # Fall back to pickle
                return pickle.loads(data_bytes)
            except Exception as e:
                logger.error(f"Failed to deserialize data: {e}")
                return None
    
    def _compress_data(self, data_bytes: bytes) -> bytes:
        """Compress data for storage"""
        return gzip.compress(data_bytes)
    
    def _decompress_data(self, compressed_bytes: bytes) -> bytes:
        """Decompress data from storage"""
        return gzip.decompress(compressed_bytes)
    
    async def get(self, source: str, identifier: str, **kwargs) -> Optional[Any]:
        """Get data from cache"""
        key = self._generate_key(source, identifier, **kwargs)
        
        # Check memory cache first
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            self.stats.hits += 1
            logger.debug(f"Cache HIT (memory): {source}:{identifier}")
            return entry.data
        
        # Check database cache
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT data, timestamp FROM cache_entries WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                
                if row:
                    data_bytes, timestamp_str = row
                    
                    # Decompress and deserialize
                    try:
                        decompressed = self._decompress_data(data_bytes)
                        data = self._deserialize_data(decompressed)
                        
                        # Add to memory cache for faster access
                        # Filter kwargs to only include valid CacheEntry parameters
                        valid_kwargs = {k: v for k, v in kwargs.items() if k in ['url', 'model_name', 'stage', 'metadata']}
                        entry = CacheEntry(
                            key=key,
                            data=data,
                            timestamp=datetime.fromisoformat(timestamp_str),
                            source=source,
                            **valid_kwargs
                        )
                        self.memory_cache[key] = entry
                        
                        self.stats.hits += 1
                        logger.debug(f"Cache HIT (database): {source}:{identifier}")
                        return data
                    except Exception as e:
                        logger.warning(f"Failed to deserialize cached data: {e}")
                        # Remove corrupted entry
                        conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
        
        except Exception as e:
            logger.warning(f"Database cache lookup failed: {e}")
        
        self.stats.misses += 1
        logger.debug(f"Cache MISS: {source}:{identifier}")
        return None
    
    async def set(self, source: str, identifier: str, data: Any, 
                  url: Optional[str] = None, model_name: Optional[str] = None,
                  stage: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None,
                  **kwargs) -> bool:
        """Store data in cache"""
        key = self._generate_key(source, identifier, **kwargs)
        
        try:
            # Serialize and compress data
            serialized = self._serialize_data(data)
            compressed = self._compress_data(serialized)
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                data=data,
                timestamp=datetime.now(),
                source=source,
                url=url,
                model_name=model_name,
                stage=stage,
                metadata=metadata or {}
            )
            
            # Store in memory cache
            self.memory_cache[key] = entry
            
            # Store in database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache_entries 
                    (key, data, timestamp, source, url, model_name, stage, metadata, size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    compressed,
                    entry.timestamp.isoformat(),
                    source,
                    url,
                    model_name,
                    stage,
                    json.dumps(metadata or {}),
                    len(compressed)
                ))
            
            self.stats.total_entries += 1
            logger.debug(f"Cache SET: {source}:{identifier} ({len(compressed)} bytes)")
            
            # Check if cleanup is needed
            await self._check_cleanup_needed()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache data: {e}")
            return False
    
    async def _check_cleanup_needed(self):
        """Check if cache cleanup is needed based on size limits"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT SUM(size_bytes) FROM cache_entries")
                total_size_bytes = cursor.fetchone()[0] or 0
                
                total_size_mb = total_size_bytes / (1024 * 1024)
                
                if total_size_mb > self.max_size_mb:
                    logger.info(f"Cache size ({total_size_mb:.1f}MB) exceeds limit ({self.max_size_mb}MB), cleaning up...")
                    await self.cleanup()
                    
        except Exception as e:
            logger.warning(f"Failed to check cache size: {e}")
    
    async def cleanup(self, max_age_hours: int = 24):
        """Clean up old cache entries"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Count entries to be deleted
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM cache_entries WHERE timestamp < ?",
                    (cutoff_time.isoformat(),)
                )
                count_to_delete = cursor.fetchone()[0]
                
                if count_to_delete > 0:
                    # Delete old entries
                    conn.execute(
                        "DELETE FROM cache_entries WHERE timestamp < ?",
                        (cutoff_time.isoformat(),)
                    )
                    
                    self.stats.evictions += count_to_delete
                    self.stats.last_cleanup = datetime.now()
                    
                    logger.info(f"Cleaned up {count_to_delete} old cache entries")
                    
                    # Update total entries count
                    cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
                    self.stats.total_entries = cursor.fetchone()[0]
                    
                    # Clear memory cache of deleted entries
                    keys_to_remove = []
                    for key, entry in self.memory_cache.items():
                        if entry.timestamp < cutoff_time:
                            keys_to_remove.append(key)
                    
                    for key in keys_to_remove:
                        del self.memory_cache[key]
                    
                    self._save_stats()
                    
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        hit_rate = 0.0
        if self.stats.hits + self.stats.misses > 0:
            hit_rate = self.stats.hits / (self.stats.hits + self.stats.misses)
        
        return {
            "total_entries": self.stats.total_entries,
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "evictions": self.stats.evictions,
            "hit_rate": hit_rate,
            "last_cleanup": self.stats.last_cleanup.isoformat() if self.stats.last_cleanup else None,
            "memory_cache_size": len(self.memory_cache)
        }
    
    async def inspect_by_model(self, model_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """Inspect all cached data for a specific model"""
        results = {}
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT key, source, url, stage, timestamp, metadata FROM cache_entries WHERE model_name = ? ORDER BY timestamp DESC",
                    (model_name,)
                )
                
                for row in cursor.fetchall():
                    key, source, url, stage, timestamp, metadata_json = row
                    
                    if source not in results:
                        results[source] = []
                    
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    
                    results[source].append({
                        "key": key,
                        "url": url,
                        "stage": stage,
                        "timestamp": timestamp,
                        "metadata": metadata
                    })
                    
        except Exception as e:
            logger.error(f"Failed to inspect cache for model {model_name}: {e}")
        
        return results
    
    async def inspect_by_source(self, source: str) -> List[Dict[str, Any]]:
        """Inspect all cached data from a specific source"""
        results = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT key, url, model_name, stage, timestamp, metadata FROM cache_entries WHERE source = ? ORDER BY timestamp DESC",
                    (source,)
                )
                
                for row in cursor.fetchall():
                    key, url, model_name, stage, timestamp, metadata_json = row
                    
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    
                    results.append({
                        "key": key,
                        "url": url,
                        "model_name": model_name,
                        "stage": stage,
                        "timestamp": timestamp,
                        "metadata": metadata
                    })
                    
        except Exception as e:
            logger.error(f"Failed to inspect cache for source {source}: {e}")
        
        return results
    
    async def get_cached_data(self, key: str) -> Optional[Any]:
        """Get specific cached data by key"""
        # Check memory cache first
        if key in self.memory_cache:
            return self.memory_cache[key].data
        
        # Check database
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT data FROM cache_entries WHERE key = ?", (key,))
                row = cursor.fetchone()
                
                if row:
                    data_bytes = row[0]
                    decompressed = self._decompress_data(data_bytes)
                    return self._deserialize_data(decompressed)
                    
        except Exception as e:
            logger.error(f"Failed to get cached data for key {key}: {e}")
        
        return None
    
    async def clear_model_cache(self, model_name: str):
        """Clear all cached data for a specific model"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Count entries to be deleted
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM cache_entries WHERE model_name = ?",
                    (model_name,)
                )
                count_to_delete = cursor.fetchone()[0]
                
                if count_to_delete > 0:
                    # Get keys to remove from memory cache
                    cursor = conn.execute(
                        "SELECT key FROM cache_entries WHERE model_name = ?",
                        (model_name,)
                    )
                    keys_to_remove = [row[0] for row in cursor.fetchall()]
                    
                    # Delete from database
                    conn.execute("DELETE FROM cache_entries WHERE model_name = ?", (model_name,))
                    
                    # Remove from memory cache
                    for key in keys_to_remove:
                        self.memory_cache.pop(key, None)
                    
                    self.stats.total_entries -= count_to_delete
                    self._save_stats()
                    
                    logger.info(f"Cleared {count_to_delete} cache entries for model {model_name}")
                    
        except Exception as e:
            logger.error(f"Failed to clear cache for model {model_name}: {e}")
    
    async def export_cache_data(self, model_name: str, output_path: Optional[Path] = None) -> Path:
        """Export all cached data for a model to a JSON file"""
        if output_path is None:
            output_path = self.cache_dir / f"cache_export_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        export_data = {
            "model_name": model_name,
            "export_timestamp": datetime.now().isoformat(),
            "cache_stats": await self.get_stats(),
            "cached_data": {}
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT key, source, url, stage, timestamp, metadata, data FROM cache_entries WHERE model_name = ?",
                    (model_name,)
                )
                
                for row in cursor.fetchall():
                    key, source, url, stage, timestamp, metadata_json, data_bytes = row
                    
                    # Decompress and deserialize data
                    try:
                        decompressed = self._decompress_data(data_bytes)
                        data = self._deserialize_data(decompressed)
                        
                        if source not in export_data["cached_data"]:
                            export_data["cached_data"][source] = []
                        
                        export_data["cached_data"][source].append({
                            "key": key,
                            "url": url,
                            "stage": stage,
                            "timestamp": timestamp,
                            "metadata": json.loads(metadata_json) if metadata_json else {},
                            "data": data
                        })
                        
                    except Exception as e:
                        logger.warning(f"Failed to deserialize data for key {key}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to export cache data: {e}")
            return output_path
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Exported cache data for {model_name} to {output_path}")
        return output_path

# Global cache instance
_cache_instance: Optional[CacheSystem] = None

def get_cache() -> CacheSystem:
    """Get the global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheSystem()
    return _cache_instance

@asynccontextmanager
async def cache_context(cache_dir: Union[str, Path] = "cache"):
    """Context manager for cache operations"""
    global _cache_instance
    old_instance = _cache_instance
    _cache_instance = CacheSystem(cache_dir)
    
    try:
        yield _cache_instance
    finally:
        _cache_instance = old_instance
