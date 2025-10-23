import asyncio
import json
import logging
from typing import Literal, Optional

import google.generativeai as genai

from app.config import settings
from app.models import AvailabilityRange, Claim, ClaimType, Domain, StructuredProperty

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self.search_model = genai.GenerativeModel("gemini-2.5-flash")
        self.flash_model = genai.GenerativeModel("gemini-2.5-flash-lite")
    
    async def aggregate_claims(self, text: str, address: Optional[str] = None, use_fast_model: bool = False) -> list[Claim]:
        text_with_address = f"Address: {address}\n\n{text}" if address else text
        prompt = self._build_claim_extraction_prompt(text_with_address)
        model = self.search_model if use_fast_model else self.model
        
        try:
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                )
            )
            
            response_text = response.text.strip()
            logger.info(f"LLM Response: {response_text[:500]}...")
            
            parsed = json.loads(response_text)
            claims_data = parsed.get("claims", [])
            
            claims = []
            for claim_dict in claims_data:
                claim = Claim(
                    claim=claim_dict["claim"],
                    claim_type=ClaimType(claim_dict["claim_type"].lower()),
                    domain=Domain(claim_dict["domain"].lower()),
                    room_type=claim_dict.get("room_type"),
                    is_specific=claim_dict.get("is_specific", False),
                    has_quantifiers=claim_dict.get("has_quantifiers", False),
                    negation=claim_dict.get("negation", False),
                )
                claims.append(claim)
            
            logger.info(f"Extracted {len(claims)} claims")
            return claims
            
        except Exception as e:
            logger.error(f"Error aggregating claims: {e}")
            raise
    
    def _build_claim_extraction_prompt(self, text: str) -> str:
        return f"""You are an expert at extracting structured claims from apartment listings and search queries.

Extract atomic facts and automatically identify:
1. The CLAIM TYPE (from the taxonomy below)
2. The DOMAIN (neighborhood, apartment, or room)
3. For room domain: the ROOM_TYPE (kitchen, bedroom, bathroom, living_room, etc.)

<claim_types>
LOCATION (0.85): Geographic locations, addresses, area names
- Examples: "located in Williamsburg", "near Central Park", "Brooklyn area"
- Domain: neighborhood (primary), apartment (secondary)

FEATURES (0.75): Physical characteristics, architectural details
- Examples: "exposed brick", "high ceilings", "walk-in closet", "hardwood floors"
- Domain: all (context-dependent)

AMENITIES (0.70): Services, facilities, convenience features  
- Examples: "doorman", "washer/dryer in unit", "ensuite bathroom", "roof deck"
- Domain: all (context-dependent)

SIZE (0.80): Dimensions, space descriptions, room counts
- Examples: "2 bedroom", "studio apartment", "12m² kitchen", "spacious", "1000 sq ft"
- Domain: apartment, room
- Has quantifiers: almost always (includes "studio" which equals 1 bedroom)

CONDITION (0.75): Maintenance state, renovation status, age
- Examples: "newly renovated", "pre-war building", "move-in ready"
- Domain: apartment (primary), room (secondary)

PRICING (0.85): Rent, fees, deposits, pricing descriptors
- Examples: "rent $3,200/month", "no broker fee", "under $4,000"
- Domain: apartment only
- Has quantifiers: always

ACCESSIBILITY (0.75): Physical access, mobility features
- Examples: "elevator building", "ground floor", "wheelchair accessible"
- Domain: apartment (primary), room (secondary)

POLICIES (0.80): Rules, restrictions, allowances
- Examples: "pets allowed", "no smoking", "subletting permitted"
- Domain: apartment only

UTILITIES (0.75): Included services, heating/cooling
- Examples: "utilities included", "central AC", "heat included"
- Domain: apartment (primary), room (secondary)

TRANSPORT (0.75): Commute access, public transit, parking
- Examples: "5 min walk to L train", "parking included", "near subway"
- Domain: neighborhood (primary), apartment (secondary)
- Has quantifiers: often

NEIGHBORHOOD (0.73): Vibe, character, lifestyle
- Examples: "quiet area", "trendy neighborhood", "nightlife", "family-friendly"
- Domain: neighborhood only

RESTRICTIONS (0.80): Lease terms, requirements, limitations
- Examples: "12 month minimum lease", "guarantor required", "income 40x rent"  
- Domain: apartment only
- Has quantifiers: often
</claim_types>

<domain_rules>
DOMAIN IDENTIFICATION:
- If claim is about area character, location, or commute → "neighborhood"
- If claim is about building, unit features, policies, pricing → "apartment"
- If claim explicitly mentions a room type AND describes that specific room → "room"

CRITICAL: Kitchen appliances and fixtures are ROOM-level claims:
- "gas stove", "electric stove", "dishwasher", "sink", "oven" → ROOM domain, room_type: kitchen
- "bathtub", "shower", "toilet" → ROOM domain, room_type: bathroom
- "closet", "wardrobe" → ROOM domain, room_type: bedroom or closet

ROOM TYPE EXTRACTION (only for room domain):
- kitchen, bedroom, bathroom, living_room, dining_room, office, closet, balcony, outdoor_space

AMBIGUOUS CASES:
- "5 min to subway" → neighborhood (transport)
- "parking spot" → apartment (amenities)
- "gas stove" → room (amenities) with room_type: kitchen
- "electric stove" → room (amenities) with room_type: kitchen
- "dishwasher" → room (amenities) with room_type: kitchen
- "spacious kitchen 12m²" → room (size) with room_type: kitchen
- "2 bedroom" → apartment (size)
- "exposed brick" without context → apartment (features)
- "exposed brick in living room" → room (features) with room_type: living_room
- "washer/dryer in unit" → apartment (amenities)
</domain_rules>

<output_format>
Return ONLY valid JSON with this structure:
{{
  "claims": [
    {{
      "claim": "exposed brick walls",
      "claim_type": "features",
      "domain": "apartment",
      "is_specific": false,
      "has_quantifiers": false,
      "negation": false
    }},
    {{
      "claim": "kitchen area 12m²",
      "claim_type": "size",
      "domain": "room",
      "room_type": "kitchen",
      "is_specific": false,
      "has_quantifiers": true,
      "negation": false
    }},
    {{
      "claim": "located in Williamsburg",
      "claim_type": "location",
      "domain": "neighborhood",
      "is_specific": true,
      "has_quantifiers": false,
      "negation": false
    }},
    {{
      "claim": "no pets allowed",
      "claim_type": "policies",
      "domain": "apartment",
      "is_specific": false,
      "has_quantifiers": false,
      "negation": true
    }},
    {{
      "claim": "no smoking",
      "claim_type": "policies",
      "domain": "apartment",
      "is_specific": false,
      "has_quantifiers": false,
      "negation": true
    }}
  ]
}}

RULES:
- Write claims concisely, one fact per claim
- Use lowercase except for proper nouns (Williamsburg, Brooklyn)
- Set has_quantifiers=true if claim contains numbers, measurements, time periods
- Set is_specific=true if claim contains named entities (specific neighborhoods, streets)
- Set negation=true if claim expresses prohibition or absence (no pets, no smoking, pets not allowed, non-smoking, etc.)
- Always assign domain field (neighborhood/apartment/room)
- For room domain, always include room_type field
</output_format>

Extract claims from: {text}"""
    
    async def validate_claim_compatibility_batch(
        self, 
        pairs: list[tuple[str, str]]
    ) -> dict[tuple[str, str], Literal["compatible", "incompatible", "partial"]]:
        if not pairs:
            return {}
        
        batch_size = 50
        results = {}
        tasks = []
        
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]
            tasks.append(self._validate_batch(batch))
        
        batch_results = await asyncio.gather(*tasks)
        
        for batch_result in batch_results:
            results.update(batch_result)
        
        logger.info(f"Validated {len(pairs)} claim pairs in {len(tasks)} batches: \n{results}")
        return results
    
    async def _validate_batch(
        self, 
        pairs: list[tuple[str, str]]
    ) -> dict[tuple[str, str], Literal["compatible", "incompatible", "partial"]]:
        prompt = self._build_compatibility_prompt(pairs)
        
        try:
            response = await asyncio.to_thread(
                self.flash_model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                )
            )
            
            parsed = json.loads(response.text.strip())
            results = {}
            
            for idx, status in enumerate(parsed.get("results", [])):
                if idx < len(pairs):
                    results[pairs[idx]] = status
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating compatibility batch: {e}")
            return {pair: "compatible" for pair in pairs}
    
    def _build_compatibility_prompt(self, pairs: list[tuple[str, str]]) -> str:
        pairs_text = "\n".join([
            f'{i+1}. Query: "{query}" | Match: "{match}"'
            for i, (query, match) in enumerate(pairs)
        ])
        
        return f"""You are validating if query claims are compatible with matched apartment claims.

Return "compatible" if the claims match or are semantically equivalent.
Return "incompatible" if they are mutually exclusive or contradictory.
Return "partial" if they are related but not fully compatible.

Examples:
- Query: "electric stove" | Match: "gas stove" → incompatible (mutually exclusive)
- Query: "near subway" | Match: "close to L train" → compatible (same meaning)
- Query: "2 bedroom" | Match: "1 bedroom" → incompatible (different quantities)
- Query: "pets allowed" | Match: "no pets allowed" → incompatible (contradictory)
- Query: "modern kitchen" | Match: "renovated kitchen" → compatible (similar)
- Query: "furnished" | Match: "partially furnished" → partial (not exact match)
- Query: "parking included" | Match: "street parking available" → partial (different types)
- Query: "3 bedroom" | Match: "3 bedroom apartment" → compatible (same)

Validate these {len(pairs)} pairs:

{pairs_text}

Return JSON array with "compatible", "incompatible", or "partial" for each pair in order:
{{"results": ["compatible", "incompatible", ...]}}"""
    
    async def extract_structured_properties(self, text: str) -> StructuredProperty:
        prompt = self._build_property_extraction_prompt(text)
        
        try:
            response = await asyncio.to_thread(
                self.search_model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                )
            )
            
            parsed = json.loads(response.text.strip())
            
            availability_dates = []
            for date_range in parsed.get("availability_dates", []):
                availability_dates.append(
                    AvailabilityRange(
                        start=date_range["start"],
                        end=date_range.get("end")
                    )
                )
            
            return StructuredProperty(
                rent_price=parsed.get("rent_price"),
                availability_dates=availability_dates
            )
            
        except Exception as e:
            logger.error(f"Error extracting structured properties: {e}")
            return StructuredProperty()
    
    def _build_property_extraction_prompt(self, text: str) -> str:
        return f"""Extract structured property information from apartment listing text.

Extract the following if present:
1. rent_price: Monthly rent amount in USD (extract number only, no currency symbol)
2. availability_dates: All mentioned availability periods as date ranges

Return JSON:
{{
  "rent_price": 2500.0,
  "availability_dates": [
    {{"start": "2024-01-01", "end": "2024-01-31"}},
    {{"start": "2024-03-15", "end": "2024-04-30"}}
  ]
}}

Rules:
- rent_price: Extract monthly rent only. Parse "$2,500/month" → 2500.0
- availability_dates: Extract ALL mentioned periods (can be multiple)
- Date format: YYYY-MM-DD
- If end date not specified, set to null
- Parse "available now" as current date
- Parse "starting June 2024" as {{"start": "2024-06-01", "end": null}}
- Parse "Jan 1-31" as {{"start": "YYYY-01-01", "end": "YYYY-01-31"}} (use current year)
- If nothing found, return {{"rent_price": null, "availability_dates": []}}

Examples:
Input: "Beautiful 2BR apartment. Rent $2,500/month. Available Jan-Feb 2024."
Output: {{"rent_price": 2500.0, "availability_dates": [{{"start": "2024-01-01", "end": "2024-02-28"}}]}}

Input: "Studio for $1,800. Available now through June. Also available Aug 15 - Sep 30."
Output: {{"rent_price": 1800.0, "availability_dates": [{{"start": "2024-01-01", "end": "2024-06-30"}}, {{"start": "2024-08-15", "end": "2024-09-30"}}]}}

Extract from: {text}"""
    
    async def extract_structured_filters(self, query: str) -> dict:
        prompt = self._build_filter_extraction_prompt(query)
        
        try:
            response = await asyncio.to_thread(
                self.search_model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                )
            )
            
            parsed = json.loads(response.text.strip())
            return parsed
            
        except Exception as e:
            logger.error(f"Error extracting structured filters: {e}")
            return {}
    
    def _build_filter_extraction_prompt(self, query: str) -> str:
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        return f"""Extract structured search filters from user query.

Current date: {current_date}

Extract the following if present:
1. rent_price: Price constraints (min, max, or exact)
2. availability_dates: Date range user is looking for

Return JSON:
{{
  "rent_price": {{"min": 1500, "max": 2000}},
  "availability_dates": {{"start": "2024-03-01", "end": "2024-03-31"}}
}}

Rules for rent_price:
- "under $2000" → {{"max": 2000}}
- "at least $1500" → {{"min": 1500}}
- "between $1500 and $2000" → {{"min": 1500, "max": 2000}}
- "around $1800" → {{"min": 1600, "max": 2000}} (±10% range)
- "$2000" → {{"min": 2000, "max": 2000}}

Rules for availability_dates:
- "available in November" → {{"start": "2025-11-01", "end": "2025-11-30"}}
- "available March 15" → {{"start": "2026-03-15", "end": "2026-03-15"}}
- "available starting June" → {{"start": "2026-06-01", "end": null}}
- "available now" → {{"start": "{current_date}", "end": null}} (use current date)

If nothing found, return {{}}.

Examples:
Input: "2 bedroom apartment under $2000"
Output: {{"rent_price": {{"max": 2000}}}}

Input: "apartment available in November for around $1800"
Output: {{"rent_price": {{"min": 1600, "max": 2000}}, "availability_dates": {{"start": "2025-11-01", "end": "2025-11-30"}}}}

Input: "modern kitchen with gas stove"
Output: {{}}

Extract from: {query}"""


llm_service = LLMService()
