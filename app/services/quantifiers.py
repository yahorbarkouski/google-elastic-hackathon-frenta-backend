import asyncio
import json
import logging

import google.generativeai as genai

from app.config import settings
from app.models import Claim, Quantifier, QuantifierOp, QuantifierType

logger = logging.getLogger(__name__)


class QuantifierService:
    def __init__(self, max_concurrent_requests: int = 30):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        logger.info(f"QuantifierService initialized with pool size: {max_concurrent_requests}")

    async def extract_quantifiers(self, claims: list[Claim]) -> list[Claim]:
        claims_with_quantifiers = [c for c in claims if c.has_quantifiers]
        claims_without_quantifiers = [c for c in claims if not c.has_quantifiers]

        if not claims_with_quantifiers:
            return claims

        logger.info(f"Extracting quantifiers in parallel for {len(claims_with_quantifiers)} claims")

        extraction_tasks = [self._extract_claim_quantifiers(claim) for claim in claims_with_quantifiers]

        logger.info(f"Launching {len(extraction_tasks)} parallel LLM calls for quantifiers...")
        import time

        start_time = time.time()

        extraction_results = await asyncio.gather(*extraction_tasks, return_exceptions=True)

        elapsed = time.time() - start_time
        logger.info(
            f"Parallel quantifier extraction completed in {elapsed:.2f}s ({len(claims_with_quantifiers) / elapsed:.1f} claims/sec)"
        )

        extracted_claims = []
        errors = 0

        for claim, result in zip(claims_with_quantifiers, extraction_results):
            if isinstance(result, Exception):
                logger.error(f"Error extracting quantifiers for '{claim.claim}': {result}")
                extracted_claims.append(claim)
                errors += 1
                continue

            quantified_text, quantifiers = result

            if quantifiers:
                claim.quantifiers = quantifiers
                claim.claim = quantified_text

            extracted_claims.append(claim)

        logger.info(f"Quantifier extraction complete: {len(extracted_claims)} processed, {errors} errors")

        return extracted_claims + claims_without_quantifiers

    async def _extract_claim_quantifiers(self, claim: Claim) -> tuple[str, list[Quantifier]]:
        import time

        async with self.semaphore:
            start_time = time.time()
            logger.info(f"🔢 START quantifier extraction for '{claim.claim}'")

            prompt = f"""Extract numeric quantifiers from this claim: "{claim.claim}"

Return JSON with this structure:
{{
  "quantified_claim": "kitchen area VAR_1",
  "quantifiers": [
    {{
      "qtype": "area|money|count|distance|duration",
      "noun": "kitchen|rent|bedroom|subway|lease",
      "vmin": 12.0,
      "vmax": 12.0,
      "op": "EQUALS|GT|GTE|LT|LTE|APPROX|RANGE",
      "unit": "sqm|meters|usd|years"
    }}
  ]
}}

Examples:
- "kitchen area 12m²" → {{"quantified_claim": "kitchen area VAR_1", "quantifiers": [{{"qtype": "area", "noun": "kitchen", "vmin": 12.0, "vmax": 12.0, "op": "APPROX", "unit": "sqm"}}]}}
- "rent under $3500" → {{"quantified_claim": "rent under VAR_1", "quantifiers": [{{"qtype": "money", "noun": "rent", "vmin": 0, "vmax": 3500, "op": "LTE", "unit": "usd"}}]}}
- "5 min walk to subway" → {{"quantified_claim": "VAR_1 walk to subway", "quantifiers": [{{"qtype": "distance", "noun": "subway", "vmin": 400, "vmax": 600, "op": "APPROX", "unit": "meters"}}]}}
- "2 bedroom apartment" → {{"quantified_claim": "2 bedroom apartment", "quantifiers": [{{"qtype": "count", "noun": "bedroom", "vmin": 2, "vmax": 2, "op": "EQUALS"}}]}}
- "1+ bedroom" → {{"quantified_claim": "1+ bedroom", "quantifiers": [{{"qtype": "count", "noun": "bedroom", "vmin": 1, "vmax": null, "op": "GTE"}}]}}
- "at least 2 bedrooms" → {{"quantified_claim": "at least 2 bedrooms", "quantifiers": [{{"qtype": "count", "noun": "bedroom", "vmin": 2, "vmax": null, "op": "GTE"}}]}}
- "studio apartment" → {{"quantified_claim": "studio apartment", "quantifiers": [{{"qtype": "count", "noun": "bedroom", "vmin": 1, "vmax": 1, "op": "EQUALS"}}]}}
- "3 bathroom" → {{"quantified_claim": "3 bathroom", "quantifiers": [{{"qtype": "count", "noun": "bathroom", "vmin": 3, "vmax": 3, "op": "EQUALS"}}]}}

IMPORTANT RULES:
- For COUNT types (bedroom, bathroom), DO NOT replace numbers with VAR_N - keep the exact number in quantified_claim
- STUDIO APARTMENTS count as 1 bedroom (studio = 1 bedroom)
- For AREA, MONEY, DISTANCE types, replace numbers with VAR_1, VAR_2, etc.
- Convert all units to standard: m² for area, meters for distance, USD for money
- Walking time: 1 min ≈ 80 meters
- For "under X", use LTE. For "over X" or "at least X" or "X+", use GTE with vmax=null
- When vmax should be infinity, use null in JSON

Return ONLY the JSON, no explanation."""

            try:
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                
                elapsed = time.time() - start_time

                parsed = json.loads(response.text.strip())
                quantified_claim = parsed.get("quantified_claim", claim.claim)
                quantifiers_data = parsed.get("quantifiers", [])

                quantifiers = []
                for q_dict in quantifiers_data:
                    try:
                        vmin_val = q_dict.get("vmin")
                        vmax_val = q_dict.get("vmax")

                        if vmin_val is None:
                            logger.warning(f"vmin is None for quantifier, skipping: {q_dict}")
                            continue

                        vmin = float(vmin_val)

                        if vmax_val is None or vmax_val == "infinity":
                            vmax = float("inf")
                        else:
                            vmax = float(vmax_val)

                        quantifier = Quantifier(
                            qtype=QuantifierType(q_dict["qtype"]),
                            noun=q_dict["noun"],
                            vmin=vmin,
                            vmax=vmax,
                            op=QuantifierOp(q_dict["op"]),
                            unit=q_dict.get("unit"),
                        )
                        quantifiers.append(quantifier)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Failed to parse quantifier {q_dict}: {e}")

                logger.info(
                    f"✅ DONE quantifier extraction for '{claim.claim}' in {elapsed:.2f}s → {len(quantifiers)} quantifiers"
                )
                return quantified_claim, quantifiers

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"❌ ERROR in quantifier extraction for '{claim.claim}' after {elapsed:.2f}s: {e}")
                return claim.claim, []


quantifier_service = QuantifierService()
