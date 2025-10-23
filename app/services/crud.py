import logging
from typing import Optional

from app.services.elasticsearch_client import es_client

logger = logging.getLogger(__name__)


class CrudService:
    async def list_apartments(
        self, 
        page: int = 1, 
        page_size: int = 20,
        has_images: bool = False
    ) -> dict:
        """
        List all apartments with basic info and pagination.
        Returns apartment_id, address, location, image_urls, and claim counts.
        """
        try:
            offset = (page - 1) * page_size
            
            query = {"match_all": {}}
            if has_images:
                query = {
                    "bool": {
                        "must": [
                            {"exists": {"field": "image_urls"}},
                            {"script": {
                                "script": "doc['image_urls'].size() > 0"
                            }}
                        ]
                    }
                }
            
            response = await es_client.client.search(
                index=es_client.apartments_index,
                body={
                    "query": query,
                    "size": 0,
                    "aggs": {
                        "unique_apartments": {
                            "terms": {
                                "field": "apartment_id",
                                "size": 10000,
                                "order": {"_key": "asc"}
                            },
                            "aggs": {
                                "latest_doc": {
                                    "top_hits": {
                                        "size": 1,
                                        "_source": ["apartment_id", "title", "address", "neighborhood_id", "apartment_location", "image_urls", "image_metadata", "property_summary", "location_summary", "location_widget_token", "rent_price", "availability_dates"]
                                    }
                                },
                                "claim_count": {
                                    "value_count": {
                                        "field": "apartment_id"
                                    }
                                }
                            }
                        }
                    }
                }
            )
            
            apartments = []
            for bucket in response["aggregations"]["unique_apartments"]["buckets"]:
                doc = bucket["latest_doc"]["hits"]["hits"][0]["_source"]
                apartments.append({
                    "apartment_id": doc["apartment_id"],
                    "title": doc.get("title"),
                    "address": doc.get("address"),
                    "neighborhood_id": doc.get("neighborhood_id"),
                    "location": doc.get("apartment_location"),
                    "image_urls": doc.get("image_urls", []),
                    "image_metadata": doc.get("image_metadata", []),
                    "claim_count": bucket["claim_count"]["value"],
                    "rent_price": doc.get("rent_price"),
                    "availability_dates": doc.get("availability_dates", []),
                    "property_summary": doc.get("property_summary"),
                    "location_summary": doc.get("location_summary"),
                    "location_widget_token": doc.get("location_widget_token")
                })
            
            total = len(apartments)
            paginated_apartments = apartments[offset:offset + page_size]
            
            return {
                "apartments": paginated_apartments,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing apartments: {e}")
            return {
                "apartments": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": 0,
                    "total_pages": 0
                },
                "error": str(e)
            }
    
    async def setup_indices(self) -> dict:
        """Initialize all Elasticsearch indices."""
        try:
            await es_client.create_indices()
            return {
                "status": "success",
                "message": "Elasticsearch indices created successfully",
                "indices": {
                    "rooms": es_client.rooms_index,
                    "apartments": es_client.apartments_index,
                    "neighborhoods": es_client.neighborhoods_index
                }
            }
        except Exception as e:
            logger.error(f"Error creating indices: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def get_apartment(self, apartment_id: str) -> Optional[dict]:
        """Fetch apartment by ID with all claims."""
        try:
            query = {
                "query": {"term": {"apartment_id": apartment_id}},
                "size": 100
            }
            
            response = await es_client.client.search(
                index=es_client.apartments_index,
                body=query
            )
            
            if not response["hits"]["hits"]:
                return None
            
            try:
                summary_doc = await es_client.client.get(
                    index=es_client.apartments_index,
                    id=f"{apartment_id}_claim_0"
                )
                title = summary_doc["_source"].get("title")
                property_summary = summary_doc["_source"].get("property_summary")
                location_summary = summary_doc["_source"].get("location_summary")
                location_widget_token = summary_doc["_source"].get("location_widget_token")
            except Exception:
                title = None
                property_summary = None
                location_summary = None
                location_widget_token = None
            
            claims = []
            location = None
            image_urls = []
            image_metadata = []
            address = None
            neighborhood_id = None
            rent_price = None
            availability_dates = []
            
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                claims.append({
                    "claim": source["claim"],
                    "claim_type": source["claim_type"],
                    "kind": source["kind"],
                    "domain": "apartment",
                    "room_type": source.get("room_type"),
                    "is_specific": source.get("is_specific", False),
                    "has_quantifiers": bool(source.get("quantifiers")),
                    "from_claim": source.get("from_claim"),
                    "weight": 1.0,
                    "negation": source.get("negation", False),
                    "source": source.get("source", {"type": "text"}),
                    "grounding_metadata": source.get("grounding_metadata"),
                    "quantifiers": source.get("quantifiers", [])
                })
                
                if "apartment_location" in source and not location:
                    location = source["apartment_location"]
                
                if "image_urls" in source and not image_urls:
                    image_urls = source["image_urls"]
                
                if "image_metadata" in source and not image_metadata:
                    image_metadata = source["image_metadata"]
                
                if "address" in source and not address:
                    address = source["address"]
                
                if "neighborhood_id" in source and not neighborhood_id:
                    neighborhood_id = source["neighborhood_id"]
                
                if "rent_price" in source and rent_price is None:
                    rent_price = source["rent_price"]
                
                if "availability_dates" in source and not availability_dates:
                    availability_dates = source.get("availability_dates", [])
            
            neighborhood_response = await es_client.client.search(
                index=es_client.neighborhoods_index,
                body={
                    "query": {"term": {"apartment_id": apartment_id}},
                    "size": 100
                }
            )
            
            for hit in neighborhood_response["hits"]["hits"]:
                source = hit["_source"]
                claims.append({
                    "claim": source["claim"],
                    "claim_type": source["claim_type"],
                    "kind": source.get("kind", "base"),
                    "domain": "neighborhood",
                    "room_type": None,
                    "is_specific": source.get("is_specific", False),
                    "has_quantifiers": False,
                    "from_claim": source.get("from_claim"),
                    "weight": 1.0,
                    "negation": source.get("negation", False),
                    "source": source.get("source", {"type": "text"}),
                    "grounding_metadata": source.get("grounding_metadata"),
                    "quantifiers": []
                })
            
            room_response = await es_client.client.search(
                index=es_client.rooms_index,
                body={
                    "query": {"term": {"apartment_id": apartment_id}},
                    "size": 200
                }
            )
            
            for hit in room_response["hits"]["hits"]:
                source = hit["_source"]
                claims.append({
                    "claim": source["claim"],
                    "claim_type": source["claim_type"],
                    "kind": source.get("kind", "base"),
                    "domain": "room",
                    "room_type": source.get("room_type"),
                    "is_specific": source.get("is_specific", False),
                    "has_quantifiers": bool(source.get("quantifiers")),
                    "from_claim": source.get("from_claim"),
                    "weight": 1.0,
                    "negation": source.get("negation", False),
                    "source": source.get("source", {"type": "text"}),
                    "grounding_metadata": source.get("grounding_metadata"),
                    "quantifiers": source.get("quantifiers", [])
                })
            
            base_claims = sum(1 for c in claims if c["kind"] == "base")
            verified_claims = sum(1 for c in claims if c["kind"] == "verified")
            derived_claims = sum(1 for c in claims if c["kind"] in ["derived", "anti"])
            
            return {
                "apartment_id": apartment_id,
                "title": title,
                "address": address,
                "neighborhood_id": neighborhood_id,
                "location": location,
                "image_urls": image_urls,
                "image_metadata": image_metadata,
                "rent_price": rent_price,
                "availability_dates": availability_dates,
                "property_summary": property_summary,
                "location_summary": location_summary,
                "location_widget_token": location_widget_token,
                "claims": claims,
                "total_claims": len(claims),
                "summary": {
                    "base_claims": base_claims,
                    "verified_claims": verified_claims,
                    "derived_claims": derived_claims
                }
            }
            
        except Exception as e:
            logger.error(f"Error fetching apartment {apartment_id}: {e}")
            return None
    
    async def delete_apartment(self, apartment_id: str) -> dict:
        """Delete apartment and all associated claims from indices."""
        try:
            deleted_counts = {
                "apartments": 0,
                "neighborhoods": 0,
                "rooms": 0
            }
            
            apartment_query = {"query": {"term": {"apartment_id": apartment_id}}}
            
            apartment_response = await es_client.client.delete_by_query(
                index=es_client.apartments_index,
                body=apartment_query
            )
            deleted_counts["apartments"] = apartment_response.get("deleted", 0)
            
            if apartment_id:
                neighborhood_response = await es_client.client.delete_by_query(
                    index=es_client.neighborhoods_index,
                    body=apartment_query
                )
                deleted_counts["neighborhoods"] = neighborhood_response.get("deleted", 0)
            
            room_response = await es_client.client.delete_by_query(
                index=es_client.rooms_index,
                body=apartment_query
            )
            deleted_counts["rooms"] = room_response.get("deleted", 0)
            
            await es_client.client.indices.refresh(index=es_client.apartments_index)
            await es_client.client.indices.refresh(index=es_client.neighborhoods_index)
            await es_client.client.indices.refresh(index=es_client.rooms_index)
            
            total_deleted = sum(deleted_counts.values())
            
            return {
                "status": "success",
                "apartment_id": apartment_id,
                "deleted_counts": deleted_counts,
                "total_deleted": total_deleted
            }
            
        except Exception as e:
            logger.error(f"Error deleting apartment {apartment_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }


crud_service = CrudService()

