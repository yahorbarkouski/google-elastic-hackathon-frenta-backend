import asyncio
import logging
import time
from collections import deque

import google.generativeai as genai
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class VisionService:
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self.requests_window = deque()
        self.max_rpm = 150
        self.window_seconds = 60
        self._lock = asyncio.Lock()
    
    async def describe_images(self, image_urls: list[str]) -> list[tuple[str, str]]:
        descriptions = []
        
        for idx, image_url in enumerate(image_urls):
            try:
                description = await self.describe_single_image(image_url, idx)
                descriptions.append((image_url, description))
                logger.info(f"Generated description for image {idx}: {len(description)} chars")
            except Exception as e:
                logger.error(f"Failed to describe image {idx} ({image_url}): {e}")
                descriptions.append((image_url, ""))
        
        return descriptions
    
    async def describe_single_image(self, image_source: str, image_index: int) -> str:
        await self._rate_limit()
        
        try:
            image_data = await self._fetch_image_data(image_source)
            
            prompt = self._build_description_prompt()
            
            response = await asyncio.to_thread(
                self.model.generate_content,
                [prompt, {"mime_type": self._infer_mime_type(image_source), "data": image_data}],
                generation_config=genai.types.GenerationConfig(temperature=0.2)
            )
            
            description = response.text.strip()
            return description
            
        except Exception as e:
            logger.error(f"Error describing image {image_index}: {e}")
            raise
    
    async def _rate_limit(self):
        async with self._lock:
            current_time = time.time()
            
            while self.requests_window and current_time - self.requests_window[0] >= self.window_seconds:
                self.requests_window.popleft()
            
            if len(self.requests_window) >= self.max_rpm:
                oldest_request = self.requests_window[0]
                sleep_time = self.window_seconds - (current_time - oldest_request)
                
                if sleep_time > 0:
                    logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                    
                    current_time = time.time()
                    while self.requests_window and current_time - self.requests_window[0] >= self.window_seconds:
                        self.requests_window.popleft()
            
            self.requests_window.append(current_time)
    
    async def _fetch_image_data(self, source: str) -> bytes:
        if source.startswith(('http://', 'https://')):
            return await self._fetch_from_url(source)
        else:
            return await self._fetch_from_local(source)
    
    async def _fetch_from_url(self, image_url: str) -> bytes:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            return response.content
    
    async def _fetch_from_local(self, file_path: str) -> bytes:
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")
        return await asyncio.to_thread(path.read_bytes)
    
    def _infer_mime_type(self, image_url: str) -> str:
        url_lower = image_url.lower()
        
        if url_lower.endswith('.png'):
            return 'image/png'
        elif url_lower.endswith('.jpg') or url_lower.endswith('.jpeg'):
            return 'image/jpeg'
        elif url_lower.endswith('.webp'):
            return 'image/webp'
        elif url_lower.endswith('.gif'):
            return 'image/gif'
        else:
            return 'image/jpeg'
    
    def _build_description_prompt(self) -> str:
        return """Describe this apartment/room image in detail for property search indexing.

Extract and describe:
1. Room type and layout (kitchen, bedroom, bathroom, living room, etc.)
2. Physical features (hardwood floors, exposed brick, high ceilings, crown molding, etc.)
3. Appliances and fixtures (stainless steel appliances, marble countertops, walk-in shower, etc.)
4. Style and condition (modern, renovated, vintage, pristine, worn, etc.)
5. Amenities (washer/dryer, dishwasher, closet space, balcony, etc.)
6. Architectural details (windows, lighting, built-ins, etc.)
7. Size perception (spacious, compact, open-concept, etc.)

Write as a natural apartment listing description. Focus on searchable features. Omit subjective marketing language."""


vision_service = VisionService()

