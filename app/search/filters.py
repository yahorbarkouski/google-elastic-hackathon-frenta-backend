import logging

from app.models import Claim, QuantifierType
from app.search.validators import claim_validator
from app.services.elasticsearch_client import es_client

logger = logging.getLogger(__name__)


class SearchFilters:
    async def filter_by_hierarchy(
        self,
        room_matches: dict,
        apartment_matches: dict,
        neighborhood_matches: dict,
        search_claims: list[Claim] = None,
        structured_filters: dict = None,
    ) -> set:
        valid_apartments = None

        if apartment_matches:
            valid_apartments = set(apartment_matches.keys())

        if room_matches:
            room_apartment_ids = set(room_matches.keys())
            if valid_apartments is None:
                valid_apartments = room_apartment_ids
            else:
                valid_apartments &= room_apartment_ids

        if neighborhood_matches:
            query_body = {
                "query": {"terms": {"neighborhood_id": list(neighborhood_matches.keys())}},
                "_source": ["apartment_id"],
                "size": 1000,
            }
            
            if structured_filters:
                query_body["query"] = self._build_query_with_structured_filters(
                    query_body["query"], structured_filters
                )
            
            response = await es_client.client.search(
                index=es_client.apartments_index,
                body=query_body,
            )

            neighborhood_apartment_ids = set(hit["_source"]["apartment_id"] for hit in response["hits"]["hits"])

            if valid_apartments is None:
                valid_apartments = neighborhood_apartment_ids
            else:
                valid_apartments &= neighborhood_apartment_ids
        
        if structured_filters and valid_apartments is None:
            valid_apartments = await self._apply_structured_filters_globally(structured_filters)

        if valid_apartments and search_claims:
            valid_apartments = self._filter_by_quantifiers(
                valid_apartments, apartment_matches, room_matches, search_claims
            )

        return valid_apartments if valid_apartments else set()

    def _filter_by_quantifiers(
        self, apartments: set[str], apartment_matches: dict, room_matches: dict, search_claims: list[Claim]
    ) -> set[str]:
        search_quantified_claims = [
            c for c in search_claims if c.quantifiers
        ]

        if not search_quantified_claims:
            return apartments

        filtered_apartments = set()

        for apt_id in apartments:
            exclude_apartment = False

            for search_claim in search_quantified_claims:
                apt_claim_matches = apartment_matches.get(apt_id, []) + room_matches.get(apt_id, [])

                for match in apt_claim_matches:
                    if match.get("search_claim") == search_claim.claim:
                        matched_quantifiers = match.get("quantifiers", [])

                        if not claim_validator.validate_quantifiers(search_claim, matched_quantifiers):
                            logger.info(
                                f"Excluding apartment {apt_id}: "
                                f"quantifier mismatch for '{search_claim.claim}' vs '{match.get('matched_claim')}'"
                            )
                            exclude_apartment = True
                            break

                if exclude_apartment:
                    break

            if not exclude_apartment:
                filtered_apartments.add(apt_id)

        logger.info(
            f"Quantifier filtering: {len(apartments)} apartments → {len(filtered_apartments)} apartments "
            f"({len(apartments) - len(filtered_apartments)} excluded due to quantifier mismatches)"
        )

        return filtered_apartments

    def filter_by_anti_claims(
        self,
        apartments: set[str],
        room_matches: dict,
        apartment_matches: dict,
        neighborhood_matches: dict,
        anti_claim_threshold: float = 0.90,
    ) -> set[str]:
        excluded_apartments = set()

        for apartment_id in apartments:
            all_matches = []
            all_matches.extend(room_matches.get(apartment_id, []))
            all_matches.extend(apartment_matches.get(apartment_id, []))

            for neighborhood_id, matches in neighborhood_matches.items():
                all_matches.extend(matches)

            matches_by_search_claim = {}
            for match in all_matches:
                search_claim = match.get("search_claim")
                if search_claim not in matches_by_search_claim:
                    matches_by_search_claim[search_claim] = {"anti": [], "positive": []}
                
                if match.get("kind") == "anti":
                    matches_by_search_claim[search_claim]["anti"].append(match)
                else:
                    matches_by_search_claim[search_claim]["positive"].append(match)

            for search_claim, grouped_matches in matches_by_search_claim.items():
                anti_matches = grouped_matches["anti"]
                positive_matches = grouped_matches["positive"]
                
                if not anti_matches:
                    continue
                
                best_anti_score = max(m.get("score", 0) for m in anti_matches)
                
                if best_anti_score < anti_claim_threshold:
                    continue
                
                best_positive_score = max((m.get("score", 0) for m in positive_matches), default=0)
                
                if best_anti_score > best_positive_score:
                    best_anti_match = max(anti_matches, key=lambda m: m.get("score", 0))
                    logger.info(
                        f"Excluding apartment {apartment_id}: anti-claim dominates for '{search_claim}' "
                        f"→ '{best_anti_match.get('matched_claim')}' "
                        f"(anti: {best_anti_score:.4f} vs positive: {best_positive_score:.4f})"
                    )
                    excluded_apartments.add(apartment_id)
                    break

        return apartments - excluded_apartments
    
    def _build_query_with_structured_filters(self, base_query: dict, structured_filters: dict) -> dict:
        must_clauses = [base_query]
        
        if "rent_price" in structured_filters:
            rent_filter = structured_filters["rent_price"]
            range_clause = {}
            
            if "min" in rent_filter:
                range_clause["gte"] = rent_filter["min"]
            if "max" in rent_filter:
                range_clause["lte"] = rent_filter["max"]
            
            if range_clause:
                must_clauses.append({"range": {"rent_price": range_clause}})
        
        if "availability_dates" in structured_filters:
            date_filter = structured_filters["availability_dates"]
            start = date_filter.get("start")
            end = date_filter.get("end")
            
            if start and end:
                must_clauses.append({
                    "nested": {
                        "path": "availability_dates",
                        "query": {
                            "bool": {
                                "must": [
                                    {"range": {"availability_dates.start": {"lte": end}}},
                                    {"range": {"availability_dates.end": {"gte": start}}}
                                ]
                            }
                        }
                    }
                })
            elif start:
                must_clauses.append({
                    "nested": {
                        "path": "availability_dates",
                        "query": {
                            "range": {"availability_dates.end": {"gte": start}}
                        }
                    }
                })
        
        return {"bool": {"must": must_clauses}}
    
    async def _apply_structured_filters_globally(self, structured_filters: dict) -> set:
        must_clauses = []
        
        if "rent_price" in structured_filters:
            rent_filter = structured_filters["rent_price"]
            range_clause = {}
            
            if "min" in rent_filter:
                range_clause["gte"] = rent_filter["min"]
            if "max" in rent_filter:
                range_clause["lte"] = rent_filter["max"]
            
            if range_clause:
                must_clauses.append({"range": {"rent_price": range_clause}})
        
        if "availability_dates" in structured_filters:
            date_filter = structured_filters["availability_dates"]
            start = date_filter.get("start")
            end = date_filter.get("end")
            
            if start and end:
                must_clauses.append({
                    "nested": {
                        "path": "availability_dates",
                        "query": {
                            "bool": {
                                "must": [
                                    {"range": {"availability_dates.start": {"lte": end}}},
                                    {"range": {"availability_dates.end": {"gte": start}}}
                                ]
                            }
                        }
                    }
                })
            elif start:
                must_clauses.append({
                    "nested": {
                        "path": "availability_dates",
                        "query": {
                            "range": {"availability_dates.end": {"gte": start}}
                        }
                    }
                })
        
        if not must_clauses:
            return set()
        
        query_body = {
            "query": {"bool": {"must": must_clauses}},
            "_source": ["apartment_id"],
            "size": 10000,
        }
        
        response = await es_client.client.search(
            index=es_client.apartments_index,
            body=query_body,
        )
        
        return set(hit["_source"]["apartment_id"] for hit in response["hits"]["hits"])


search_filters = SearchFilters()

