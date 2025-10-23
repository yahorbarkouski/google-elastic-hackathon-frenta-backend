import logging
from collections import defaultdict
from typing import Optional

from app.models import Claim
from app.services.elasticsearch_client import es_client

logger = logging.getLogger(__name__)


class RoomSearcher:
    async def search(self, claims: list[Claim]) -> dict:
        all_matches = defaultdict(list)

        for claim in claims:
            filter_clause = None
            if claim.room_type:
                filter_clause = {"term": {"room_type": claim.room_type}}
            
            query_body = {
                "knn": {
                    "field": "claim_vector",
                    "query_vector": claim.embedding,
                    "k": 100,
                    "num_candidates": 500,
                },
                "_source": ["room_id", "apartment_id", "claim", "kind", "room_type", "quantifiers", "negation"],
                "size": 100,
            }
            
            if filter_clause:
                query_body["knn"]["filter"] = filter_clause

            response = await es_client.client.search(index=es_client.rooms_index, body=query_body)

            for hit in response["hits"]["hits"]:
                apartment_id = hit["_source"]["apartment_id"]
                all_matches[apartment_id].append(
                    {
                        "search_claim": claim.claim,
                        "search_claim_obj": claim,
                        "matched_claim": hit["_source"]["claim"],
                        "score": hit["_score"],
                        "kind": hit["_source"]["kind"],
                        "claim_type": claim.claim_type,
                        "quantifiers": hit["_source"].get("quantifiers", []),
                        "matched_negation": hit["_source"].get("negation", False),
                    }
                )

        return all_matches


class ApartmentSearcher:
    async def search(self, claims: list[Claim], geo_filters: Optional[list[dict]] = None, structured_filters: Optional[dict] = None) -> dict:
        all_matches = defaultdict(list)

        for claim in claims:
            filter_clause = self._build_filter_clause(claim, geo_filters, structured_filters)

            query_body = {
                "knn": {
                    "field": "claim_vector",
                    "query_vector": claim.embedding,
                    "k": 200,
                    "num_candidates": 500,
                },
                "_source": ["apartment_id", "neighborhood_id", "claim", "kind", "quantifiers", "negation"],
                "size": 200,
            }
            
            if filter_clause:
                query_body["knn"]["filter"] = filter_clause

            response = await es_client.client.search(index=es_client.apartments_index, body=query_body)

            for hit in response["hits"]["hits"]:
                apartment_id = hit["_source"]["apartment_id"]
                all_matches[apartment_id].append(
                    {
                        "search_claim": claim.claim,
                        "search_claim_obj": claim,
                        "matched_claim": hit["_source"]["claim"],
                        "score": hit["_score"],
                        "kind": hit["_source"]["kind"],
                        "claim_type": claim.claim_type,
                        "quantifiers": hit["_source"].get("quantifiers", []),
                        "matched_negation": hit["_source"].get("negation", False),
                    }
                )

        return all_matches
    
    def _build_filter_clause(self, claim: Claim, geo_filters: Optional[list[dict]], structured_filters: Optional[dict]) -> dict:
        must_clauses = []
        should_clauses = []
        
        if geo_filters:
            geo_should_clauses = [
                {
                    "geo_distance": {
                        "distance": f"{f['radius']}m",
                        "apartment_location": {"lat": f["coords"]["lat"], "lon": f["coords"]["lng"]},
                    }
                }
                for f in geo_filters
            ]
            should_clauses.extend(geo_should_clauses)
        
        if structured_filters:
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
        
        if not must_clauses and not should_clauses:
            return None
        
        if should_clauses:
            return {
                "bool": {
                    "must": must_clauses if must_clauses else [],
                    "should": should_clauses,
                    "minimum_should_match": 1 if geo_filters else 0,
                }
            }
        
        if len(must_clauses) == 1:
            return must_clauses[0]
        
        if must_clauses:
            return {"bool": {"must": must_clauses}}
        
        return None


class NeighborhoodSearcher:
    async def search(self, claims: list[Claim]) -> dict:
        all_matches = defaultdict(list)

        for claim in claims:
            query_body = {
                "knn": {
                    "field": "claim_vector",
                    "query_vector": claim.embedding,
                    "k": 50,
                    "num_candidates": 200,
                    "filter": {"term": {"claim_type": claim.claim_type.value}},
                },
                "_source": ["neighborhood_id", "claim", "kind", "negation"],
                "size": 50,
            }

            response = await es_client.client.search(index=es_client.neighborhoods_index, body=query_body)

            for hit in response["hits"]["hits"]:
                neighborhood_id = hit["_source"]["neighborhood_id"]
                all_matches[neighborhood_id].append(
                    {
                        "search_claim": claim.claim,
                        "search_claim_obj": claim,
                        "matched_claim": hit["_source"]["claim"],
                        "score": hit["_score"],
                        "kind": hit["_source"].get("kind", "base"),
                        "claim_type": claim.claim_type,
                        "matched_negation": hit["_source"].get("negation", False),
                    }
                )

        return all_matches


room_searcher = RoomSearcher()
apartment_searcher = ApartmentSearcher()
neighborhood_searcher = NeighborhoodSearcher()

