import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GeocodingService:
    def __init__(self):
        self.api_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.cache = {}
        self.cache_timestamps = {}
        logger.info("GeocodingService initialized with Google Maps Geocoding API")
    
    async def geocode_address(self, address: str) -> Optional[dict]:
        """
        Convert address to coordinates using Google Maps Geocoding API.
        Returns: {"lat": 40.7149, "lng": -73.9566} or None
        """
        if not address or not address.strip():
            logger.warning("Empty address provided for geocoding")
            return None
        
        cache_key = address.lower().strip()
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        logger.info(f"Geocoding address: {address}")
        
        try:
            coords = await self._geocode_with_maps_api(address)
            if coords:
                self._set_cache(cache_key, coords)
                logger.info(f"✓ Geocoded '{address}' to {coords}")
            else:
                logger.warning(f"Failed to geocode address: {address}")
            return coords
        except Exception as e:
            logger.error(f"Error geocoding address '{address}': {e}")
            return None
    
    async def _geocode_with_maps_api(self, address: str) -> Optional[dict]:
        """Use Google Maps Geocoding API to get coordinates."""
        params = {
            "address": address,
            "key": settings.google_maps_api_key
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.api_url, params=params, timeout=10.0)
                response.raise_for_status()
                
                data = response.json()
                
                if data["status"] == "OK" and data["results"]:
                    result = data["results"][0]
                    location = result["geometry"]["location"]
                    
                    coords = {
                        "lat": location["lat"],
                        "lng": location["lng"]
                    }
                    
                    formatted_address = result.get("formatted_address", address)
                    logger.info(f"Geocoded to: {formatted_address}")
                    
                    return coords
                else:
                    logger.warning(f"Geocoding API returned status: {data['status']}")
                    return None
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during geocoding: {e}")
            return None
        except Exception as e:
            logger.error(f"Geocoding API error: {e}")
            return None
    
    def _get_from_cache(self, cache_key: str) -> Optional[dict]:
        """Get cached geocoding result if not stale (90 day TTL)."""
        if cache_key not in self.cache:
            return None
        
        timestamp = self.cache_timestamps.get(cache_key)
        if timestamp:
            age = datetime.now() - timestamp
            if age > timedelta(days=90):
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
                return None
        
        logger.debug("Geocoding cache HIT")
        return self.cache[cache_key]
    
    def _set_cache(self, cache_key: str, coords: dict):
        """Store geocoding result in cache."""
        self.cache[cache_key] = coords
        self.cache_timestamps[cache_key] = datetime.now()
        logger.debug("Geocoding cache SET")


geocoding_service = GeocodingService()
