import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.models import Claim, ClaimKind, ClaimType, Domain, GroundingMetadata, Quantifier, QuantifierOp, QuantifierType

logger = logging.getLogger(__name__)


class GroundingResult:
    def __init__(
        self,
        verified_claims: list[Claim],
        widget_tokens: list[str],
        grounded_sources: list[dict]
    ):
        self.verified_claims = verified_claims
        self.widget_tokens = widget_tokens
        self.grounded_sources = grounded_sources


class GroundingService:
    def __init__(self):
        self.model_name = settings.grounding_model
        self.cache = {}
        self.cache_timestamps = {}
        logger.info(f"GroundingService initialized with model: {self.model_name}")
    
    def should_ground_claim(self, claim: Claim, context: Optional[dict] = None) -> bool:
        """
        Decide if a claim should be grounded with Google Maps.
        Only ground specific named places, not generic categories.
        """
        if not settings.enable_grounding:
            return False
        
        if claim.domain == Domain.ROOM:
            return False
        
        if not claim.is_specific:
            return False
        
        if claim.claim_type in [ClaimType.LOCATION, ClaimType.TRANSPORT, ClaimType.AMENITIES]:
            return True
        
        return False
    
    def should_ground_search_claim(self, claim: Claim, user_location: Optional[dict] = None) -> bool:
        """Decide if a search claim should be grounded. Same logic as should_ground_claim."""
        return self.should_ground_claim(claim)
    
    def _get_cache_key(self, claim: Claim, location: Optional[dict]) -> str:
        """Generate cache key for claim grounding."""
        location_key = "no_location"
        if location:
            lat = location.get("lat", 0)
            lng = location.get("lng", 0)
            location_key = f"{round(lat, 2)}_{round(lng, 2)}"
        
        claim_pattern = claim.claim.lower()[:50].replace(" ", "_")
        return f"{location_key}:{claim.claim_type.value}:{claim_pattern}"
    
    def _get_cache_ttl_days(self, claim: Claim) -> int:
        """Get TTL for cache based on claim type."""
        if claim.claim_type == ClaimType.TRANSPORT:
            return 90
        elif claim.claim_type == ClaimType.LOCATION:
            return 90
        elif claim.claim_type == ClaimType.NEIGHBORHOOD:
            return 14
        else:
            return settings.grounding_cache_ttl_days
    
    def _get_from_cache(self, cache_key: str, ttl_days: int) -> Optional[list[Claim]]:
        """Get cached grounding result if not stale."""
        if cache_key not in self.cache:
            return None
        
        timestamp = self.cache_timestamps.get(cache_key)
        if timestamp:
            age = datetime.now() - timestamp
            if age > timedelta(days=ttl_days):
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
                return None
        
        logger.info(f"Cache HIT for key: {cache_key}")
        return self.cache[cache_key]
    
    def _set_cache(self, cache_key: str, verified_claims: list[Claim]):
        """Store grounding result in cache."""
        self.cache[cache_key] = verified_claims
        self.cache_timestamps[cache_key] = datetime.now()
        logger.info(f"Cache SET for key: {cache_key}")
    
    async def ground_claims_batch(
        self,
        claims: list[Claim],
        location: Optional[dict] = None,
        enable_widget: bool = False
    ) -> GroundingResult:
        """
        Ground multiple claims using Gemini API's Maps tool.
        Returns verified claims + grounding metadata + widget tokens.
        """
        if not claims:
            return GroundingResult([], [], [])
        
        logger.info(f"Grounding {len(claims)} claims with location: {location}")
        
        verified_claims_all = []
        widget_tokens = []
        grounded_sources = []
        
        claims_to_ground = []
        for claim in claims[:settings.max_groundings_per_listing]:
            cache_key = self._get_cache_key(claim, location)
            ttl_days = self._get_cache_ttl_days(claim)
            cached = self._get_from_cache(cache_key, ttl_days)
            
            if cached:
                verified_claims_all.extend(cached)
            else:
                claims_to_ground.append((claim, cache_key))
        
        if not claims_to_ground:
            logger.info("All claims served from cache")
            return GroundingResult(verified_claims_all, widget_tokens, grounded_sources)
        
        tasks = []
        for claim, cache_key in claims_to_ground:
            task = self._ground_single_claim(claim, location, enable_widget)
            tasks.append((task, claim, cache_key))
        
        logger.info(f"Launching {len(tasks)} parallel grounding calls...")
        results = await asyncio.gather(*[t[0] for t in tasks], return_exceptions=True)
        
        for (_, claim, cache_key), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"Error grounding claim '{claim.claim}': {result}")
                continue
            
            if result is None:
                logger.warning(f"None result for claim '{claim.claim}'")
                continue
            
            verified_claims, sources, widget = result
            
            if verified_claims and isinstance(verified_claims, list):
                self._set_cache(cache_key, verified_claims)
                verified_claims_all.extend(verified_claims)
            
            if sources and isinstance(sources, list):
                grounded_sources.extend(sources)
            
            if widget:
                widget_tokens.append(widget)
        
        logger.info(f"Grounding complete: {len(verified_claims_all)} verified claims, {len(grounded_sources)} sources")
        return GroundingResult(verified_claims_all, widget_tokens, grounded_sources)
    
    async def _ground_single_claim(
        self,
        claim: Claim,
        location: Optional[dict],
        enable_widget: bool
    ) -> tuple[list[Claim], list[dict], Optional[str]]:
        """Ground a single claim and return verified claims."""
        prompt = self._build_grounding_prompt(claim, location)
        
        try:
            response = await self._call_gemini_with_maps(prompt, location, enable_widget)
            result = await self._parse_grounding_response(response, claim, location)
            
            if result is None or not isinstance(result, tuple) or len(result) != 3:
                logger.error(f"Invalid result format from _parse_grounding_response: {result}")
                return [], [], None
            
            return result
        except Exception as e:
            logger.error(f"Error grounding claim '{claim.claim}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], [], None
    
    async def _call_gemini_with_maps(
        self,
        prompt: str,
        location: Optional[dict],
        enable_widget: bool
    ) -> dict:
        """Call Gemini API with Google Maps tool enabled."""
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=settings.google_api_key)
        
        config_dict = {
            "tools": [types.Tool(google_maps=types.GoogleMaps(enable_widget=enable_widget))],
            "temperature": 0.1
        }
        
        if location:
            config_dict["tool_config"] = types.ToolConfig(
                retrieval_config=types.RetrievalConfig(
                    lat_lng=types.LatLng(
                        latitude=location["lat"],
                        longitude=location["lng"]
                    )
                )
            )
        
        config = types.GenerateContentConfig(**config_dict)
        
        logger.info("Calling Gemini Maps API...")
        
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=self.model_name,
            contents=prompt,
            config=config
        )
        
        return response
    
    def _build_grounding_prompt(self, claim: Claim, location: Optional[dict]) -> str:
        """Build natural language prompt for Gemini Maps grounding."""
        location_str = ""
        if location:
            location_str = f" near {location['lat']}, {location.get('lon', location.get('lng'))}"
        
        base_instruction = "DO NOT write any explanatory text. DO NOT ask questions. Immediately use the Google Maps tool without any preamble. For ambiguous locations: (1) cities over states, (2) more populous areas, (3) well-known landmarks."
        
        if claim.claim_type == ClaimType.TRANSPORT:
            return f"""{base_instruction}

Use Maps tool for: "{claim.claim}"{location_str}"""
        
        elif claim.claim_type == ClaimType.AMENITIES:
            return f"""{base_instruction}

Use Maps tool for: "{claim.claim}"{location_str}"""
        
        elif claim.claim_type == ClaimType.LOCATION:
            return f"""{base_instruction}

If ambiguous (e.g., "Washington"), choose most likely city/neighborhood for apartments.
Use Maps tool for: "{claim.claim}"{location_str}"""
        
        elif claim.claim_type == ClaimType.NEIGHBORHOOD:
            return f"""{base_instruction}

Use Maps tool to analyze: "{claim.claim}"{location_str}"""
        
        else:
            return f"""{base_instruction}

Use Maps tool for: "{claim.claim}"{location_str}"""
    
    async def _parse_grounding_response(
        self,
        response,
        original_claim: Claim,
        location: Optional[dict]
    ) -> tuple[list[Claim], list[dict], Optional[str]]:
        """
        Parse Gemini response with Google Maps grounding data.
        Uses LLM to extract structured data - NO manual parsing/heuristics.
        """
        verified_claims = []
        grounded_sources = []
        widget_token = None
        
        response_text = response.text if hasattr(response, 'text') else str(response)
        logger.info(f"Grounding response: {response_text[:300]}...")
        
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                metadata = candidate.grounding_metadata
                
                if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks is not None:
                    for chunk in metadata.grounding_chunks:
                        if hasattr(chunk, 'maps') and chunk.maps is not None:
                            maps_chunk = chunk.maps
                            source = {
                                "title": getattr(maps_chunk, 'title', ''),
                                "uri": getattr(maps_chunk, 'uri', ''),
                                "place_id": getattr(maps_chunk, 'place_id', None)
                            }
                            grounded_sources.append(source)
                            logger.info(f"Found Maps source: {source['title']}")
                
                if hasattr(metadata, 'google_maps_widget_context_token') and metadata.google_maps_widget_context_token:
                    widget_token = metadata.google_maps_widget_context_token
                    logger.info("Got widget token")
        
        if not grounded_sources:
            logger.warning(f"No grounded sources found for claim: {original_claim.claim}")
            return [], [], widget_token
        
        logger.info(f"Extracting structured data for claim: {original_claim.claim}")
        structured_data = await self._extract_structured_data_with_llm(response_text, original_claim, grounded_sources)
        logger.info(f"Structured data returned: type={type(structured_data)}, is_list={isinstance(structured_data, list)}, value={structured_data}")
        
        if structured_data and isinstance(structured_data, list):
            logger.info(f"Processing {len(structured_data)} structured data items")
            for data in structured_data:
                grounding_meta = GroundingMetadata(
                    verified=True,
                    source="google_maps",
                    confidence=0.95,
                    place_name=data.get("place_name"),
                    place_id=data.get("place_id"),
                    place_uri=data.get("place_uri")
                )
                
                if "coordinates" in data:
                    grounding_meta.coordinates = data["coordinates"]
                
                if "distance_meters" in data:
                    grounding_meta.exact_distance_meters = data["distance_meters"]
                
                if "walking_minutes" in data:
                    grounding_meta.walking_time_minutes = data["walking_minutes"]
                
                if "recommended_radius_meters" in data:
                    grounding_meta.recommended_radius_meters = data["recommended_radius_meters"]
                
                verified_claim = Claim(
                    claim=data.get("verified_claim_text", f"{original_claim.claim} (verified)"),
                    claim_type=original_claim.claim_type,
                    domain=original_claim.domain,
                    room_type=original_claim.room_type,
                    is_specific=True,
                    has_quantifiers=original_claim.has_quantifiers or bool(grounding_meta.exact_distance_meters),
                    kind=ClaimKind.VERIFIED,
                    from_claim=original_claim.claim,
                    weight=original_claim.weight * 1.15,
                    grounding_metadata=grounding_meta
                )
                
                if grounding_meta.exact_distance_meters and not original_claim.quantifiers:
                    verified_claim.quantifiers = [
                        Quantifier(
                            qtype=QuantifierType.DISTANCE,
                            noun=data.get("noun", "location"),
                            vmin=float(grounding_meta.exact_distance_meters),
                            vmax=float(grounding_meta.exact_distance_meters),
                            op=QuantifierOp.APPROX,
                            unit="meters"
                        )
                    ]
                
                verified_claims.append(verified_claim)
                logger.info(
                    f"✓ Created verified claim: '{verified_claim.claim[:60]}' "
                    f"(place: {grounding_meta.place_name}, dist: {grounding_meta.exact_distance_meters}m)"
                )
        else:
            logger.warning(f"No structured data extracted for claim: {original_claim.claim}")
        
        logger.info(f"Returning: {len(verified_claims)} verified claims, {len(grounded_sources)} sources")
        return verified_claims, grounded_sources, widget_token
    
    async def _extract_structured_data_with_llm(
        self,
        response_text: str,
        original_claim: Claim,
        grounded_sources: list[dict]
    ) -> list[dict]:
        """
        Use LLM to extract structured data from the grounding response.
        NO heuristics - let the LLM do all parsing.
        """
        import google.generativeai as genai
        
        place_names = [s["title"] for s in grounded_sources if s["title"]]
        
        extraction_prompt = f"""Extract precise structured data from this Google Maps grounding response.

Original claim: "{original_claim.claim}"
Places found: {', '.join(place_names) if place_names else 'None'}

Grounding response:
{response_text}

Extract and return ONLY a JSON array with verified information:
{{
  "verifications": [
    {{
      "verified_claim_text": "exact distance to specific place",
      "place_name": "exact place name from response",
      "distance_meters": numeric_value_or_null,
      "walking_minutes": numeric_value_or_null,
      "coordinates": {{"lat": number, "lng": number}} or null,
      "noun": "what the distance is to (subway, park, etc)",
      "recommended_radius_meters": number
    }}
  ]
}}

Rules:
- Only include data explicitly mentioned in the response
- Convert all distances to meters
- Extract coordinates if mentioned
- For recommended_radius_meters, consider the place type:
  * Specific station/stop: 500-800m (walkable)
  * Small landmark/plaza: 800-1200m
  * Large park/area: 1500-3000m
  * Neighborhood: 3000-8000m
  * Borough/district: 10000-20000m
- If multiple places, create one entry for the closest/best one
- Return empty array if nothing can be extracted"""
        
        try:
            extraction_response = await asyncio.to_thread(
                genai.GenerativeModel(settings.gemini_model).generate_content,
                extraction_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )
            
            extracted_text = extraction_response.text.strip()
            logger.debug(f"Extraction response: {extracted_text[:300]}")
            
            parsed = json.loads(extracted_text)
            
            if isinstance(parsed, list) and parsed:
                if isinstance(parsed[0], dict) and "verifications" in parsed[0]:
                    verifications = parsed[0]["verifications"]
                else:
                    verifications = parsed
            elif isinstance(parsed, dict):
                verifications = parsed.get("verifications", [])
            else:
                verifications = []
            
            logger.info(f"Parsed verifications: {verifications}")
            
            if verifications and isinstance(verifications, list):
                for v in verifications:
                    if isinstance(v, dict) and grounded_sources:
                        v["place_id"] = grounded_sources[0].get("place_id")
                        v["place_uri"] = grounded_sources[0].get("uri")
            
            logger.info(f"Returning {len(verifications) if verifications else 0} verifications")
            return verifications if verifications else []
            
        except Exception as e:
            logger.error(f"Error extracting structured data: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def infer_radius(self, claim: Claim) -> int:
        """
        Get search radius from grounding metadata.
        Priority: recommended_radius > distance + buffer > default 500m
        """
        if claim.grounding_metadata:
            if claim.grounding_metadata.recommended_radius_meters:
                radius = claim.grounding_metadata.recommended_radius_meters
                logger.info(f"Using recommended radius: {radius}m for claim: {claim.claim}")
                return radius
            
            if claim.grounding_metadata.exact_distance_meters:
                distance = claim.grounding_metadata.exact_distance_meters
                buffer = max(100, int(distance * 0.3))
                radius = distance + buffer
                logger.info(f"Calculated radius: {radius}m (distance: {distance}m + buffer: {buffer}m)")
                return radius
        
        logger.warning(f"No distance in grounding metadata for claim: {claim.claim}. Using default 500m")
        return 500
    
    async def generate_location_description(
        self,
        location: dict[str, float],
        address: str
    ) -> tuple[str, Optional[str]]:
        """
        Generate a comprehensive, descriptive location summary using Gemini grounding.
        Uses Google Maps to discover nearby attractions, restaurants, transit, etc.
        Returns (description, widget_token).
        """
        prompt = self._build_location_description_prompt(address, location)
        
        try:
            response = await self._call_gemini_with_maps(
                prompt=prompt,
                location=location,
                enable_widget=True
            )
            
            description = response.text.strip() if hasattr(response, 'text') else ""
            logger.info(f"Generated location description: {len(description)} chars")
            
            widget_token = None
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    metadata = candidate.grounding_metadata
                    if hasattr(metadata, 'google_maps_widget_context_token'):
                        widget_token = metadata.google_maps_widget_context_token
                        logger.info("Captured widget token for location description")
            
            return description, widget_token
            
        except Exception as e:
            logger.error(f"Error generating location description: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "", None
    
    def _build_location_description_prompt(
        self, 
        address: str, 
        location: dict[str, float]
    ) -> str:
        return f"""Use Google Maps to write a location description. Return ONLY the description text, no preamble.

Address: {address}
Coordinates: {location['lat']}, {location.get('lon', location.get('lng'))}

Requirements:
- Use Google Maps to find nearby attractions, dining, transit, parks
- Luxury hospitality tone (sophisticated, inviting)
- 3-4 sentences, 100-150 words
- Include specific place names with walking times
- Emphasize convenience and lifestyle

Example format (DO NOT include "Here is" or similar phrases):
"Perfectly situated just minutes from Joshua Tree National Park, this home provides easy access to world-class hiking, rock climbing, and stargazing. Guests can explore the thriving local art scene, shop eclectic boutiques in Joshua Tree Village, or savor craft food and cocktails at nearby restaurants."

CRITICAL: Use the Google Maps tool first, then write the description using real places found. Return ONLY the location description:"""


grounding_service = GroundingService()
