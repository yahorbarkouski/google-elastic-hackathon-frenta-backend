import logging
import time

from app.models import Claim, ClaimType, Domain, SearchResult
from app.search.constants import CLAIM_TYPE_THRESHOLDS, DOMAIN_WEIGHTS
from app.search.validators import claim_validator
from app.services.elasticsearch_client import es_client

logger = logging.getLogger(__name__)


class ResultScorer:
    async def fetch_apartment_metadata(self, apartment_ids: set[str]) -> dict[str, dict]:
        metadata = {}
        
        if not apartment_ids:
            return metadata
        
        query = {
            "query": {
                "terms": {"apartment_id": list(apartment_ids)}
            },
            "size": len(apartment_ids),
            "_source": ["apartment_id", "neighborhood_id", "title", "address", "image_urls", "image_metadata", "rent_price", "availability_dates"],
            "collapse": {
                "field": "apartment_id"
            }
        }
        
        try:
            response = await es_client.client.search(
                index=es_client.apartments_index,
                body=query
            )
            
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                apartment_id = source["apartment_id"]
                metadata[apartment_id] = {
                    "neighborhood_id": source.get("neighborhood_id"),
                    "title": source.get("title"),
                    "address": source.get("address"),
                    "image_urls": source.get("image_urls", []),
                    "image_metadata": source.get("image_metadata", []),
                    "rent_price": source.get("rent_price"),
                    "availability_dates": source.get("availability_dates", [])
                }
        except Exception as e:
            logger.error(f"Error fetching apartment metadata: {e}")
        
        return metadata

    def get_best_matches_globally(
        self, apartments: set[str], room_matches: dict, apartment_matches: dict, neighborhood_matches: dict
    ) -> dict[str, dict]:
        best_matches_global = {}

        for apartment_id in apartments:
            apartment_room_matches = room_matches.get(apartment_id, [])
            apartment_apt_matches = apartment_matches.get(apartment_id, [])
            all_apt_matches = apartment_room_matches + apartment_apt_matches

            for match in all_apt_matches:
                search_claim = match["search_claim"]
                if search_claim not in best_matches_global or match["score"] > best_matches_global[search_claim]["score"]:
                    best_matches_global[search_claim] = match

        for matches in neighborhood_matches.values():
            for match in matches:
                search_claim = match["search_claim"]
                if search_claim not in best_matches_global or match["score"] > best_matches_global[search_claim]["score"]:
                    best_matches_global[search_claim] = match

        return best_matches_global

    def apply_match_validation(
        self, match: dict, compatibility_cache: dict, double_check_matches: bool = False
    ) -> tuple[float, bool]:
        threshold = CLAIM_TYPE_THRESHOLDS.get(match["claim_type"], 0.75)
        search_claim_obj = match.get("search_claim_obj")

        if search_claim_obj and search_claim_obj.is_specific and search_claim_obj.claim_type == ClaimType.LOCATION:
            threshold = 0.9

        if not double_check_matches and match["score"] < threshold:
            return 0.0, False

        base_score = match["score"]
        matched_quantifiers = match.get("quantifiers", [])
        matched_kind = match.get("kind", "base")
        search_claim_text = match["search_claim"]

        if search_claim_obj:
            is_valid = claim_validator.validate_quantifiers(search_claim_obj, matched_quantifiers)
            search_negation = search_claim_obj.negation
            matched_negation = match.get("matched_negation", False)

            if not is_valid:
                base_score *= 0.1
            elif matched_kind == "anti" and base_score >= 0.85:
                base_score *= 0.01
            elif matched_kind == "anti":
                base_score *= 0.05
            elif search_negation != matched_negation:
                base_score *= 0.1

        pair = (search_claim_text, match["matched_claim"])
        compatibility = compatibility_cache.get(pair, "compatible")

        if compatibility == "incompatible":
            logger.info(
                f"Skipping incompatible match: '{search_claim_text}' vs '{match['matched_claim']}'"
            )
            return 0.0, False
        elif compatibility == "partial":
            base_score *= 0.5

        return base_score, True

    def get_validated_best_matches(
        self, all_matches: list[dict], compatibility_cache: dict, double_check_matches: bool = False
    ) -> dict[str, dict]:
        validated_best = {}

        for match in all_matches:
            validated_score, is_valid = self.apply_match_validation(match, compatibility_cache, double_check_matches)
            
            if not is_valid or validated_score <= 0:
                continue

            search_claim = match["search_claim"]
            
            if search_claim not in validated_best or validated_score > validated_best[search_claim]["validated_score"]:
                validated_best[search_claim] = {
                    **match,
                    "validated_score": validated_score
                }

        return validated_best

    def calculate_score_from_validated_matches(
        self, validated_matches: dict[str, dict], search_claims: list[Claim]
    ) -> float:
        if not search_claims or not validated_matches:
            return 0.0

        total_score = sum(match["validated_score"] for match in validated_matches.values())
        return total_score / len(search_claims)

    def normalize_domain_weights(self, room_claims: list[Claim], apt_claims: list[Claim], neighborhood_claims: list[Claim]) -> dict:
        active_weights = {}
        if room_claims:
            active_weights[Domain.ROOM] = DOMAIN_WEIGHTS[Domain.ROOM]
        if apt_claims:
            active_weights[Domain.APARTMENT] = DOMAIN_WEIGHTS[Domain.APARTMENT]
        if neighborhood_claims:
            active_weights[Domain.NEIGHBORHOOD] = DOMAIN_WEIGHTS[Domain.NEIGHBORHOOD]

        weight_sum = sum(active_weights.values())
        normalized_weights = {k: v / weight_sum for k, v in active_weights.items()} if weight_sum > 0 else {}

        logger.info(
            f"Domain weight normalization: "
            f"room={normalized_weights.get(Domain.ROOM, 0):.2f}, "
            f"apartment={normalized_weights.get(Domain.APARTMENT, 0):.2f}, "
            f"neighborhood={normalized_weights.get(Domain.NEIGHBORHOOD, 0):.2f}"
        )

        return normalized_weights

    async def rank_results(
        self,
        filtered_apartments: set[str],
        room_matches: dict,
        apartment_matches: dict,
        neighborhood_matches: dict,
        search_claims: list[Claim],
        compatibility_cache: dict,
        double_check_matches: bool = False,
    ) -> list[SearchResult]:
        room_claims = [c for c in search_claims if c.domain == Domain.ROOM]
        apt_claims = [c for c in search_claims if c.domain == Domain.APARTMENT]
        neighborhood_claims = [c for c in search_claims if c.domain == Domain.NEIGHBORHOOD]

        normalized_weights = self.normalize_domain_weights(room_claims, apt_claims, neighborhood_claims)

        substep_start = time.time()
        apartment_metadata = await self.fetch_apartment_metadata(filtered_apartments)
        ranked = []

        for apartment_id in filtered_apartments:
            all_room_matches = room_matches.get(apartment_id, [])
            all_apt_matches = apartment_matches.get(apartment_id, [])
            
            apartment_neighborhood_id = apartment_metadata.get(apartment_id, {}).get("neighborhood_id")
            all_neighborhood_matches_for_apt = []
            if apartment_neighborhood_id and apartment_neighborhood_id in neighborhood_matches:
                all_neighborhood_matches_for_apt = neighborhood_matches[apartment_neighborhood_id]

            validated_room_matches = self.get_validated_best_matches(all_room_matches, compatibility_cache, double_check_matches)
            validated_apt_matches = self.get_validated_best_matches(all_apt_matches, compatibility_cache, double_check_matches)
            validated_neighborhood_matches = self.get_validated_best_matches(
                all_neighborhood_matches_for_apt, compatibility_cache, double_check_matches
            )

            room_score = self.calculate_score_from_validated_matches(validated_room_matches, room_claims)
            apt_score = self.calculate_score_from_validated_matches(validated_apt_matches, apt_claims)
            neighborhood_score = self.calculate_score_from_validated_matches(
                validated_neighborhood_matches, neighborhood_claims
            )

            domain_scores = {
                Domain.ROOM.value: room_score,
                Domain.APARTMENT.value: apt_score,
                Domain.NEIGHBORHOOD.value: neighborhood_score,
            }

            final_score = (
                normalized_weights.get(Domain.ROOM, 0) * room_score
                + normalized_weights.get(Domain.APARTMENT, 0) * apt_score
                + normalized_weights.get(Domain.NEIGHBORHOOD, 0) * neighborhood_score
            )

            all_validated_matches = {**validated_room_matches, **validated_apt_matches, **validated_neighborhood_matches}

            matched_claims_detail = []
            for match in all_validated_matches.values():
                search_claim_obj = match.get("search_claim_obj")
                domain_value = "apartment"
                if search_claim_obj and hasattr(search_claim_obj, "domain"):
                    domain_value = search_claim_obj.domain.value
                
                room_type_value = None
                if search_claim_obj and hasattr(search_claim_obj, "room_type"):
                    room_type_value = search_claim_obj.room_type

                search_quantifiers = []
                if search_claim_obj and hasattr(search_claim_obj, "quantifiers"):
                    search_quantifiers = [q.model_dump() for q in search_claim_obj.quantifiers]
                
                matched_quantifiers = match.get("quantifiers", [])
                
                matched_claims_detail.append(
                    {
                        "query_claim": match["search_claim"],
                        "matched_claim": match["matched_claim"],
                        "similarity": match["validated_score"],
                        "domain": domain_value,
                        "kind": match.get("kind", "base"),
                        "room_type": room_type_value,
                        "query_quantifiers": search_quantifiers,
                        "matched_quantifiers": matched_quantifiers,
                    }
                )

            coverage_count = len(matched_claims_detail)
            coverage_ratio = coverage_count / len(search_claims) if search_claims else 0

            metadata = apartment_metadata.get(apartment_id, {})
            result = SearchResult(
                apartment_id=apartment_id,
                title=metadata.get("title"),
                address=metadata.get("address"),
                final_score=final_score,
                coverage_count=coverage_count,
                coverage_ratio=coverage_ratio,
                weight_coverage=coverage_ratio,
                matched_claims=matched_claims_detail,
                domain_scores=domain_scores,
                image_urls=metadata.get("image_urls", []),
                image_metadata=metadata.get("image_metadata", []),
                rent_price=metadata.get("rent_price"),
                availability_dates=metadata.get("availability_dates", []),
            )
            ranked.append(result)

        substep_duration = time.time() - substep_start
        logger.info(f"Scoring {len(ranked)} apartments [{substep_duration:.3f}s]")

        if double_check_matches:
            filtered_results = [r for r in ranked if r.coverage_count > 0]
            if len(filtered_results) < len(ranked):
                logger.info(
                    f"Double-check mode: Filtered out {len(ranked) - len(filtered_results)} results with coverage = 0 (score threshold DISABLED)"
                )
        else:
            filtered_results = [r for r in ranked if r.final_score > 0.05 and r.coverage_count > 0]
            if len(filtered_results) < len(ranked):
                logger.info(
                    f"Filtered out {len(ranked) - len(filtered_results)} results with score <= 0.05 or coverage = 0"
                )

        filtered_results.sort(key=lambda x: (x.coverage_count, x.final_score), reverse=True)

        return filtered_results


result_scorer = ResultScorer()

