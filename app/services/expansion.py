import asyncio
import json
import logging
from typing import Optional

import google.generativeai as genai

from app.config import settings
from app.models import Claim, ClaimKind, ClaimType

logger = logging.getLogger(__name__)


class ExpansionService:
    def __init__(self, max_concurrent_requests: int = 50):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        logger.info(f"ExpansionService initialized with pool size: {max_concurrent_requests}")

    async def expand_claims(self, claims: list[Claim]) -> list[Claim]:
        """
        Expand base claims with derived claims (synonyms, generalizations)
        and anti-claims (semantic opposites).
        Uses parallel execution for performance.
        """
        base_claims = [c for c in claims if c.kind == ClaimKind.BASE]
        
        logger.info(f"Starting parallel claim expansion for {len(base_claims)} base claims")
        
        if not base_claims:
            return claims

        expansion_tasks = [self._expand_single_claim(claim) for claim in base_claims]
        
        logger.info(f"Launching {len(expansion_tasks)} parallel LLM calls for expansion...")
        import time
        start_time = time.time()
        
        expansion_results = await asyncio.gather(*expansion_tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        logger.info(f"Parallel expansion completed in {elapsed:.2f}s ({len(base_claims)/elapsed:.1f} claims/sec)")
        
        all_claims = list(claims)
        total_derived = 0
        total_anti = 0
        errors = 0
        
        for claim, result in zip(base_claims, expansion_results):
            if isinstance(result, Exception):
                logger.error(f"Error expanding claim '{claim.claim}': {result}")
                errors += 1
                continue
            
            expanded_claims = result
            all_claims.extend(expanded_claims)
            
            derived_count = len([c for c in expanded_claims if c.kind == ClaimKind.DERIVED])
            anti_count = len([c for c in expanded_claims if c.kind == ClaimKind.ANTI])
            
            total_derived += derived_count
            total_anti += anti_count
            
            logger.debug(
                f"Expanded '{claim.claim}': +{derived_count} derived, +{anti_count} anti"
            )

        logger.info(
            f"Expansion complete: {len(base_claims)} base → {len(all_claims)} total "
            f"(+{total_derived} derived, +{total_anti} anti, {errors} errors)"
        )

        return all_claims

    async def _expand_single_claim(self, claim: Claim) -> list[Claim]:
        """Generate derived and anti-claims for a single base claim"""
        
        import time
        
        expansion_strategy = self._get_expansion_strategy(claim.claim_type)

        if not expansion_strategy:
            logger.debug(f"No expansion strategy for {claim.claim_type}, skipping: '{claim.claim}'")
            return []

        prompt = self._build_expansion_prompt(claim, expansion_strategy)

        async with self.semaphore:
            start_time = time.time()
            logger.info(f"🚀 START expanding '{claim.claim}' (type={claim.claim_type.value})")
            
            try:
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
                
                elapsed = time.time() - start_time
                logger.info(f"✅ DONE expanding '{claim.claim}' in {elapsed:.2f}s")

                parsed = json.loads(response.text.strip())

                expanded_claims = []

                for derived_text in parsed.get("derived_claims", []):
                    derived_claim = Claim(
                        claim=derived_text,
                        claim_type=claim.claim_type,
                        domain=claim.domain,
                        room_type=claim.room_type,
                        is_specific=False,
                        has_quantifiers=False,
                        kind=ClaimKind.DERIVED,
                        from_claim=claim.claim,
                        weight=claim.weight * 0.9,
                        negation=claim.negation,
                    )
                    expanded_claims.append(derived_claim)

                for anti_text in parsed.get("anti_claims", []):
                    anti_claim = Claim(
                        claim=anti_text,
                        claim_type=claim.claim_type,
                        domain=claim.domain,
                        room_type=claim.room_type,
                        is_specific=False,
                        has_quantifiers=False,
                        kind=ClaimKind.ANTI,
                        from_claim=claim.claim,
                        weight=claim.weight * 0.5,
                        negation=not claim.negation,
                    )
                    expanded_claims.append(anti_claim)

                derived_claims = [c for c in expanded_claims if c.kind == ClaimKind.DERIVED]
                anti_claims = [c for c in expanded_claims if c.kind == ClaimKind.ANTI]
                
                logger.info(
                    f"   → Generated {len(derived_claims)} derived, {len(anti_claims)} anti"
                )
                
                if derived_claims:
                    derived_texts = [c.claim for c in derived_claims]
                    logger.info(f"   → Derived: {derived_texts}")
                
                if anti_claims:
                    anti_texts = [c.claim for c in anti_claims]
                    logger.info(f"   → Anti: {anti_texts}")
                
                return expanded_claims

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"❌ ERROR expanding '{claim.claim}' after {elapsed:.2f}s: {e}")
                return []

    def _get_expansion_strategy(self, claim_type: ClaimType) -> Optional[dict]:
        """
        Get expansion strategy for each claim type.
        Returns dict with 'derive' and 'anti' strategies.
        Anti-claims should ONLY be used for clear semantic oppositions users search for.
        """

        strategies = {
            ClaimType.RESTRICTIONS: {
                "derive": "similar lease terms, formality variations, time period synonyms",
                "anti": "opposite lease flexibility, conflicting lease duration",
                "generate_anti": True,
                "examples": {
                    "base": "12-month minimum lease",
                    "derived": ["annual lease required", "one-year commitment", "12-month term minimum", "year-long lease"],
                    "anti": [
                        "month-to-month available",
                        "flexible lease terms",
                        "short-term lease allowed",
                    ],
                },
            },
            ClaimType.POLICIES: {
                "derive": "similar policy phrasings, equivalent allowances, permission synonyms",
                "anti": "opposite policies ONLY (allowed vs not allowed)",
                "generate_anti": True,
                "examples": {
                    "base": "pets allowed",
                    "derived": ["pet-friendly", "dogs and cats welcome", "animals permitted", "cats and dogs okay"],
                    "anti": ["no pets allowed", "pet-free building", "animals prohibited"],
                },
            },
            ClaimType.SIZE: {
                "derive": "size synonyms, room count variations, measurement equivalents",
                "anti": None,
                "generate_anti": False,
                "examples": {
                    "base": "2 bedroom",
                    "derived": ["two bedroom", "2BR", "2 bed", "two bed apartment"],
                    "anti": [],
                },
            },
            ClaimType.LOCATION: {
                "derive": "geographic hierarchy (neighborhood → borough → city), area synonyms",
                "anti": None,
                "generate_anti": False,
                "examples": {
                    "base": "located in Williamsburg",
                    "derived": ["Williamsburg Brooklyn", "North Brooklyn", "Williamsburg neighborhood", "in Williamsburg area"],
                    "anti": [],
                },
            },
            ClaimType.FEATURES: {
                "derive": "feature synonyms, similar characteristics, related attributes",
                "anti": None,
                "generate_anti": False,
                "examples": {
                    "base": "high ceilings",
                    "derived": ["tall ceilings", "soaring ceilings", "lofty spaces", "elevated ceilings", "12+ foot ceilings"],
                    "anti": [],
                },
            },
            ClaimType.AMENITIES: {
                "derive": "amenity synonyms, service equivalents, facility variations",
                "anti": None,
                "generate_anti": False,
                "examples": {
                    "base": "doorman building",
                    "derived": ["concierge service", "full-service building", "attended lobby", "24/7 staff", "front desk"],
                    "anti": [],
                },
            },
            ClaimType.CONDITION: {
                "derive": "condition synonyms, renovation equivalents, age indicators",
                "anti": None,
                "generate_anti": False,
                "examples": {
                    "base": "newly renovated",
                    "derived": ["recently updated", "modern finishes", "contemporary renovation", "freshly remodeled", "gut renovated"],
                    "anti": [],
                },
            },
            ClaimType.NEIGHBORHOOD: {
                "derive": "vibe synonyms, character equivalents, atmosphere descriptions",
                "anti": "ONLY clear opposite vibes (quiet vs noisy, safe vs unsafe)",
                "generate_anti": True,
                "examples": {
                    "base": "quiet neighborhood",
                    "derived": ["peaceful area", "tranquil location", "low noise level", "serene environment", "residential feel"],
                    "anti": ["noisy area", "busy neighborhood", "nightlife district"],
                },
            },
            ClaimType.TRANSPORT: {
                "derive": "transit synonyms, access equivalents, commute variations",
                "anti": None,
                "generate_anti": False,
                "examples": {
                    "base": "near subway",
                    "derived": ["close to metro", "walking distance to train", "convenient transit access", "steps from subway"],
                    "anti": [],
                },
            },
            ClaimType.UTILITIES: {
                "derive": "utility inclusion synonyms, service coverage variations",
                "anti": None,
                "generate_anti": False,
                "examples": {
                    "base": "utilities included",
                    "derived": ["all utilities covered", "heat and water included", "no utility bills", "utilities paid"],
                    "anti": [],
                },
            },
            ClaimType.ACCESSIBILITY: {
                "derive": "accessibility synonyms, mobility equivalents, access descriptions",
                "anti": None,
                "generate_anti": False,
                "examples": {
                    "base": "elevator building",
                    "derived": ["lift access", "no stairs required", "elevator to all floors", "accessible building"],
                    "anti": [],
                },
            },
            ClaimType.PRICING: {
                "derive": "price range variations, cost descriptors",
                "anti": None,
                "generate_anti": False,
                "examples": {
                    "base": "affordable rent",
                    "derived": ["reasonably priced", "budget-friendly", "good value", "competitive pricing"],
                    "anti": [],
                },
            },
        }

        return strategies.get(claim_type)

    def _build_expansion_prompt(self, claim: Claim, strategy: dict) -> str:
        """Build LLM prompt for claim expansion"""

        examples = strategy.get("examples", {})
        generate_anti = strategy.get("generate_anti", False)
        
        if generate_anti:
            task_desc = "1. DERIVED CLAIMS: Synonyms, paraphrases, and generalizations\n2. ANTI CLAIMS: Semantic opposites ONLY when there's a clear, meaningful opposition"
            anti_rules = """2. Anti claims should ONLY be generated when:
   - There's a clear semantic opposition (e.g., "pets allowed" vs "no pets")
   - Users would search for the opposite (e.g., "month-to-month" vs "12-month")
   - Different specific locations (e.g., "Williamsburg" vs "Park Slope")
   - Generate 2-3 anti claims ONLY if truly meaningful"""
        else:
            task_desc = "1. DERIVED CLAIMS: Synonyms, paraphrases, and generalizations\n2. NO ANTI CLAIMS for this claim type (return empty array)"
            anti_rules = "2. DO NOT generate anti claims - return empty array []"

        return f"""You are an expert at generating semantic variations for apartment search claims.

Given a base claim, generate:
{task_desc}

<task>
Base Claim: "{claim.claim}"
Claim Type: {claim.claim_type.value}
Domain: {claim.domain.value}

Expansion Strategy:
- Derive: {strategy["derive"]}

Example for this claim type:
Base: "{examples.get("base", "N/A")}"
Derived: {examples.get("derived", [])}
Anti: {examples.get("anti", [])}
</task>

<rules>
1. Derived claims should:
   - Preserve the core meaning
   - Use different phrasing or synonyms
   - Include generalizations when appropriate
   - Generate 4-6 high-quality derived claims

{anti_rules}

3. Keep claims concise and lowercase (except proper nouns)
4. Focus on actual semantic meaning users would search for
5. Quality over quantity
</rules>

<output_format>
Return ONLY valid JSON:
{{
  "derived_claims": ["synonym 1", "synonym 2", "generalization", "variation 4"],
  "anti_claims": []
}}
</output_format>

Generate expansions for the base claim above."""


expansion_service = ExpansionService()
