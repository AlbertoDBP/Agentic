"""Redis Cache Manager"""
import redis.asyncio as redis
import json
import logging
from typing import Optional, Any
from datetime import timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    """Async Redis cache manager with JSON serialization"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            await self.client.ping()
            logger.info("✅ Connected to Redis cache")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.client = None
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        if not self.client:
            logger.warning("Cache not available")
            return None
        
        try:
            value = await self.client.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set cached value with TTL (seconds)"""
        if not self.client:
            logger.warning("Cache not available")
            return
        
        try:
            await self.client.setex(
                key,
                timedelta(seconds=ttl),
                json.dumps(value, default=str)
            )
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
    
    async def delete(self, key: str):
        """Delete cached value"""
        if not self.client:
            return
        
        try:
            await self.client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
    
    async def is_connected(self) -> bool:
        """Check if cache is connected"""
        if not self.client:
            return False
        
        try:
            await self.client.ping()
            return True
        except:
            return False
    
    async def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.client:
            return {"connected": False}
        
        try:
            info = await self.client.info("stats")
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses
            
            return {
                "connected": True,
                "hits": hits,
                "misses": misses,
                "hit_rate": round((hits / total * 100), 2) if total > 0 else 0.0
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"connected": False, "error": str(e)}
