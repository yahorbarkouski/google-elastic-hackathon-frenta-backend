import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

from app.models import Claim, ClaimType, Domain, EmbeddedClaim, SearchResult
from app.search.domain_searchers import apartment_searcher, neighborhood_searcher, room_searcher
from app.search.filters import search_filters
from app.search.scorers import result_scorer
from app.search.validators import claim_validator
from app.services.embeddings import embedding_service
from app.services.llm import llm_service
from app.services.quantifiers import quantifier_service

logger = logging.getLogger(__name__)


class SearchPipeline:
    async def search(self, query: str, top_k: int = 10, user_location: Optional[dict] = None, verify_claims: bool = True, double_check_matches: bool = False) -> list[SearchResult]:
        search_start = time.time()
        logger.info(f"Starting search for query: {query} (verify_claims: {verify_claims}, double_check_matches: {double_check_matches})")

        search_claims, structured_filters = await asyncio.gather(
            self._extract_search_claims(query),
            self._extract_structured_filters(query)
        )
        search_claims = self._filter_redundant_claims(search_claims, structured_filters)
        search_claims = await self._process_quantifiers(search_claims)
        search_claims = await self._embed_claims(search_claims)

        geo_filters = []

        results = await self._execute_domain_searches(search_claims, geo_filters, structured_filters)
        ranked_results = await self._rank_and_filter_results(results, search_claims, verify_claims, double_check_matches)

        total_duration = time.time() - search_start
        logger.info(f"🎯 Total search time: {total_duration:.3f}s")

        return ranked_results[:top_k]

    async def _extract_search_claims(self, query: str) -> list[Claim]:
        phase_start = time.time()
        search_claims = await llm_service.aggregate_claims(query, use_fast_model=True)
        phase_duration = time.time() - phase_start
        logger.info(f"Phase 1: Extracted {len(search_claims)} search claims (Flash) [{phase_duration:.3f}s]")
        return search_claims
    
    async def _extract_structured_filters(self, query: str) -> dict:
        phase_start = time.time()
        structured_filters = await llm_service.extract_structured_filters(query)
        phase_duration = time.time() - phase_start
        if structured_filters:
            logger.info(f"Phase 1.5: Extracted structured filters: {structured_filters} [{phase_duration:.3f}s]")
        return structured_filters
    
    def _filter_redundant_claims(self, search_claims: list[Claim], structured_filters: dict) -> list[Claim]:
        filtered_claims = []
        for claim in search_claims:
            if claim.claim_type == ClaimType.PRICING and "rent_price" in structured_filters:
                logger.info(f"Skipping redundant pricing claim '{claim.claim}' (already handled by structured filter)")
                continue
            
            if claim.claim_type == ClaimType.RESTRICTIONS and "availability_dates" in structured_filters:
                availability_keywords = ["available", "availability", "lease start", "move-in date", "move in"]
                if any(keyword in claim.claim.lower() for keyword in availability_keywords):
                    logger.info(f"Skipping redundant availability claim '{claim.claim}' (already handled by structured filter)")
                    continue
            
            filtered_claims.append(claim)
        return filtered_claims

    async def _process_quantifiers(self, search_claims: list[Claim]) -> list[Claim]:
        phase_start = time.time()
        search_claims = await quantifier_service.extract_quantifiers(search_claims)
        phase_duration = time.time() - phase_start
        logger.info(f"Phase 2: Processed quantifiers [{phase_duration:.3f}s]")
        return search_claims

    async def _embed_claims(self, search_claims: list[Claim]) -> list[EmbeddedClaim]:
        phase_start = time.time()
        claim_texts = [c.claim for c in search_claims]
        query_embeddings = await embedding_service.embed_texts(claim_texts, task_type="retrieval_query")
        phase_duration = time.time() - phase_start
        logger.info(f"Phase 3: Generated {len(query_embeddings)} query embeddings [{phase_duration:.3f}s]")

        embedded_search_claims = []
        for claim, embedding in zip(search_claims, query_embeddings):
            embedded_claim = EmbeddedClaim(**claim.model_dump(), embedding=embedding)
            embedded_search_claims.append(embedded_claim)

        return embedded_search_claims

    async def _execute_domain_searches(self, search_claims: list[Claim], geo_filters: Optional[list[dict]], structured_filters: dict) -> dict:
        phase_start = time.time()

        claims_by_domain = defaultdict(list)
        for claim in search_claims:
            claims_by_domain[claim.domain].append(claim)

        room_matches = {}
        apartment_matches = {}
        neighborhood_matches = {}

        if claims_by_domain[Domain.ROOM]:
            substep_start = time.time()
            room_matches = await room_searcher.search(claims_by_domain[Domain.ROOM])
            substep_duration = time.time() - substep_start
            logger.info(f"  Room search: {len(room_matches)} apartments matched [{substep_duration:.3f}s]")

        if claims_by_domain[Domain.APARTMENT]:
            substep_start = time.time()
            apartment_matches = await apartment_searcher.search(claims_by_domain[Domain.APARTMENT], geo_filters, structured_filters)
            substep_duration = time.time() - substep_start
            logger.info(f"  Apartment search: {len(apartment_matches)} apartments matched [{substep_duration:.3f}s]")

        if claims_by_domain[Domain.NEIGHBORHOOD]:
            substep_start = time.time()
            neighborhood_matches = await neighborhood_searcher.search(claims_by_domain[Domain.NEIGHBORHOOD])
            substep_duration = time.time() - substep_start
            logger.info(
                f"  Neighborhood search: {len(neighborhood_matches)} neighborhoods matched [{substep_duration:.3f}s]"
            )

        substep_start = time.time()
        valid_apartments = await search_filters.filter_by_hierarchy(
            room_matches, apartment_matches, neighborhood_matches, search_claims, structured_filters
        )
        substep_duration = time.time() - substep_start
        logger.info(f"  Hierarchy filtering: {len(valid_apartments)} apartments valid [{substep_duration:.3f}s]")

        phase_duration = time.time() - phase_start
        logger.info(f"Phase 4: Retrieved {len(valid_apartments)} apartments [{phase_duration:.3f}s]")

        return {
            "apartments": valid_apartments,
            "room_matches": room_matches,
            "apartment_matches": apartment_matches,
            "neighborhood_matches": neighborhood_matches,
        }

    async def _rank_and_filter_results(self, results: dict, search_claims: list[Claim], verify_claims: bool = True, double_check_matches: bool = False) -> list[SearchResult]:
        phase_start = time.time()

        apartments = results["apartments"]
        room_matches = results["room_matches"]
        apartment_matches = results["apartment_matches"]
        neighborhood_matches = results["neighborhood_matches"]

        substep_start = time.time()
        filtered_apartments = search_filters.filter_by_anti_claims(
            apartments, room_matches, apartment_matches, neighborhood_matches
        )
        substep_duration = time.time() - substep_start
        logger.info(
            f"Anti-claim filtering: {len(apartments)} apartments → {len(filtered_apartments)} apartments "
            f"({len(apartments) - len(filtered_apartments)} excluded due to strong anti-claim matches) [{substep_duration:.3f}s]"
        )

        if verify_claims:
            substep_start = time.time()
            best_matches = result_scorer.get_best_matches_globally(
                filtered_apartments, room_matches, apartment_matches, neighborhood_matches
            )
            compatibility_cache = await claim_validator.validate_all_claim_pairs(best_matches)
            substep_duration = time.time() - substep_start
            logger.info(f"LLM validation: {len(compatibility_cache)} unique claim pairs [{substep_duration:.3f}s]")
        else:
            compatibility_cache = {}
            logger.info("LLM validation: SKIPPED (verify_claims=False)")

        ranked_results = await result_scorer.rank_results(
            filtered_apartments, room_matches, apartment_matches, neighborhood_matches, search_claims, compatibility_cache, double_check_matches
        )

        phase_duration = time.time() - phase_start
        logger.info(
            f"Phase 5: Ranked results, top score: {ranked_results[0].final_score if ranked_results else 0} [{phase_duration:.3f}s]"
        )

        return ranked_results


search_pipeline = SearchPipeline()
