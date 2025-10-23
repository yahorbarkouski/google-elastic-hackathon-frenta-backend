import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)


class SyntheticApartmentGenerator:
    def __init__(self):
        self.client = genai.Client(api_key=settings.google_api_key)
    
    async def generate_full_apartment(
        self,
        description_hint: Optional[str] = None,
        price_range: Optional[dict] = None,
        num_images: int = 6,
        neighborhood_hint: Optional[str] = None,
        city_hint: Optional[str] = None,
        aspect_ratio: str = "16:9"
    ) -> dict:
        logger.info("Starting full synthetic apartment generation")
        
        if not description_hint:
            description_hint = await self._generate_random_apartment_concept(neighborhood_hint, city_hint)
            logger.info(f"Generated random concept: {description_hint[:100]}...")
        
        style_plan = await self._generate_style_plan(description_hint)
        logger.info(f"Generated style plan: {style_plan.get('aesthetic', 'N/A')}")
        
        image_prompts = await self._generate_image_prompts(description_hint, style_plan, num_images)
        logger.info(f"Generated {len(image_prompts)} image prompts")
        
        images_task = self._generate_images_parallel(image_prompts, aspect_ratio)
        metadata_task = self._generate_metadata(
            style_plan=style_plan,
            image_prompts=image_prompts,
            description_hint=description_hint,
            price_range=price_range,
            neighborhood_hint=neighborhood_hint,
            city_hint=city_hint
        )
        
        images_with_bytes, metadata = await asyncio.gather(images_task, metadata_task)
        logger.info(f"Generated {len(images_with_bytes)} images and metadata in parallel")
        logger.info(f"Apartment title: {metadata['title']}")
        
        apartment_id = f"generated_{metadata['neighborhood_id']}_{uuid.uuid4().hex[:8]}"
        
        return {
            "apartment_id": apartment_id,
            "title": metadata["title"],
            "description": metadata["description"],
            "address": metadata["address"],
            "neighborhood_id": metadata["neighborhood_id"],
            "rent_price": metadata["rent_price"],
            "availability_dates": metadata["availability_dates"],
            "style_plan": style_plan,
            "aspect_ratio": aspect_ratio,
            "images": images_with_bytes,
            "image_descriptions": [img["prompt"] for img in image_prompts]
        }
    
    async def _generate_random_apartment_concept(self, neighborhood_hint: Optional[str] = None, city_hint: Optional[str] = None) -> str:
        city = city_hint or "New York City"
        
        prompt = f"""Generate a creative apartment concept description for a {city} apartment.

{"Focus on the " + neighborhood_hint + " neighborhood." if neighborhood_hint else f"Choose any {city} neighborhood."}

Include:
- Neighborhood and approximate location
- Number of bedrooms
- Key architectural features
- Special amenities or features
- Overall style/vibe

Keep it to 2-3 sentences. Make it unique and interesting.

Return ONLY the description, no JSON, no formatting."""
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["Text"],
                temperature=0.9
            )
        )
        
        return response.text.strip()
    
    async def _generate_style_plan(self, description: str) -> dict:
        prompt = f"""Create a comprehensive style guide for generating consistent, high-quality real estate photography of this property:

{description}

Generate a detailed style plan including:
1. Overall aesthetic (modern, industrial, minimalist, traditional, eclectic, etc.)
2. Color palette (walls, floors, furniture, accents)
3. Lighting style (natural, warm, cool, dramatic, soft)
4. Furniture style and materials
5. Architectural details and features
6. Time of day for interior shots
7. Weather/lighting for exterior shots
8. Photography style (wide-angle, intimate, architectural, lifestyle)

Be extremely specific about colors, textures, materials, and mood so all images feel like they're from the same cohesive property.

Return JSON:
{{
  "aesthetic": "Modern industrial with warm accents",
  "color_palette": {{
    "walls": "White with exposed brick accent walls",
    "floors": "Light oak hardwood",
    "furniture": "Mid-century modern in walnut and brass",
    "accents": "Warm copper, muted green plants"
  }},
  "lighting": {{
    "type": "Soft natural light from large windows",
    "time_of_day": "Late afternoon golden hour",
    "artificial": "Warm LED recessed lighting, brass fixtures"
  }},
  "materials": {{
    "kitchen": "White quartz countertops, stainless steel appliances, subway tile",
    "bathroom": "White marble, chrome fixtures, frameless glass",
    "living": "Leather, linen, brass, wood"
  }},
  "architectural_details": ["Exposed brick walls", "12-foot ceilings", "Large industrial windows"],
  "photography_style": "Professional architectural photography, 16mm wide-angle lens, f/5.6, natural light prioritized",
  "exterior_conditions": "Clear day, late afternoon, warm sunlight"
}}"""
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["Text"],
                temperature=0.5,
                response_mime_type="application/json"
            )
        )
        
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif response_text.startswith("```"):
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        return json.loads(response_text)
    
    async def _generate_image_prompts(self, description: str, style_plan: dict, num_images: int) -> list[dict]:
        style_context = json.dumps(style_plan, indent=2)
        
        prompt = f"""Generate {num_images} photorealistic image prompts for real estate photography following this EXACT style guide:

STYLE GUIDE:
{style_context}

PROPERTY DESCRIPTION:
{description}

Generate prompts for different views:
- Living room/main space (2-3 angles)
- Kitchen (2 angles)
- Bedroom(s) (1-2 angles)
- Bathroom (1 angle)
- Building exterior (1 angle)
- Special features

CRITICAL REQUIREMENTS:
1. Every prompt MUST reference the exact colors, materials, and lighting from the style guide
2. Use consistent furniture style and materials across all rooms
3. Maintain the same time of day and lighting quality
4. Reference architectural details consistently
5. Use professional real estate photography language
6. Specify camera settings and composition
7. High resolution, sharp focus, professional quality

Return JSON:
{{
  "prompts": [
    {{"prompt": "A professional architectural photograph...", "type": "living_room", "camera": "16mm wide-angle"}},
    ...
  ]
}}"""
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["Text"],
                temperature=0.6,
                response_mime_type="application/json"
            )
        )
        
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif response_text.startswith("```"):
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(response_text)
        prompts = data.get("prompts", [])
        return prompts[:num_images]
    
    async def _generate_images_parallel(self, prompts: list[dict], aspect_ratio: str) -> list[dict]:
        tasks = [
            self._generate_single_image(prompt["prompt"], idx, aspect_ratio)
            for idx, prompt in enumerate(prompts)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        images = []
        for idx, (result, prompt_data) in enumerate(zip(results, prompts)):
            if isinstance(result, Exception):
                logger.error(f"Failed to generate image {idx}: {result}")
                continue
            
            images.append({
                "index": idx,
                "prompt": prompt_data["prompt"],
                "type": prompt_data.get("type", "unknown"),
                "camera": prompt_data.get("camera", "unknown"),
                "image_bytes": result
            })
        
        return images
    
    async def _generate_single_image(self, prompt: str, index: int, aspect_ratio: str) -> bytes:
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-2.5-flash-image",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["Image"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio)
            )
        )
        
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                return part.inline_data.data
        
        raise ValueError(f"No image generated for prompt {index}")
    
    async def _generate_metadata(
        self,
        style_plan: dict,
        image_prompts: list[dict],
        description_hint: str,
        price_range: Optional[dict] = None,
        neighborhood_hint: Optional[str] = None,
        city_hint: Optional[str] = None
    ) -> dict:
        prompt_summary = "\n".join([f"- {p['type']}: {p['prompt'][:100]}..." for p in image_prompts[:5]])
        
        price_constraint = ""
        if price_range:
            if "min" in price_range and "max" in price_range:
                price_constraint = f"Rent price must be between ${price_range['min']} and ${price_range['max']}/month."
            elif "min" in price_range:
                price_constraint = f"Rent price must be at least ${price_range['min']}/month."
            elif "max" in price_range:
                price_constraint = f"Rent price must be under ${price_range['max']}/month."
        
        neighborhood_constraint = f"Must be in {neighborhood_hint} neighborhood." if neighborhood_hint else ""
        city = city_hint or "NYC"
        city_full = "New York City" if city == "NYC" else city
        
        prompt = f"""Generate realistic apartment listing metadata based on this property:

DESCRIPTION: {description_hint}

STYLE AESTHETIC: {style_plan.get('aesthetic', 'N/A')}

KEY FEATURES FROM IMAGES:
{prompt_summary}

ARCHITECTURAL DETAILS: {', '.join(style_plan.get('architectural_details', []))}

CONSTRAINTS:
{price_constraint}
{neighborhood_constraint}

Generate realistic {city_full} apartment listing metadata:
1. Full detailed description (150-250 words) - write as a professional listing, include all features, materials, architectural details
2. Catchy listing title (4-5 words maximum, max 40 chars, format: "NEIGHBORHOOD VIBE/TYPE". Examples: "Hudson Yards Urban Chic", "Williamsburg Industrial Loft", "SoHo Modern Minimalist". NO amenities, NO features list, just location + aesthetic)
3. Full street address (make it realistic for the neighborhood and city)
4. Neighborhood ID (lowercase, underscore separated, e.g., "williamsburg_brooklyn" or "srodmiescie_warsaw")
5. Monthly rent price (realistic for the city and neighborhood)
6. Availability dates (start from 1-3 months from now, 12-month lease)

Return JSON:
{{
  "description": "Beautiful sun-drenched 2-bedroom apartment...",
  "title": "Williamsburg Industrial Loft",
  "address": "123 Bedford Avenue, Brooklyn, NY 11211",
  "neighborhood_id": "williamsburg_brooklyn",
  "rent_price": 3800,
  "availability_dates": [
    {{"start": "2025-12-01", "end": "2026-11-30"}}
  ]
}}"""
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["Text"],
                temperature=0.7,
                response_mime_type="application/json"
            )
        )
        
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif response_text.startswith("```"):
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        return json.loads(response_text)


synthetic_generator = SyntheticApartmentGenerator()

