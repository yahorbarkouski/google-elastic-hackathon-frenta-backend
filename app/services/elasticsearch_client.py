import asyncio
import logging

from elasticsearch import AsyncElasticsearch

from app.config import settings

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    def __init__(self):
        self._client = None
        self._loop_id = None
        self.rooms_index = "rooms"
        self.apartments_index = "apartments"
        self.neighborhoods_index = "neighborhoods"
    
    @property
    def client(self):
        try:
            current_loop = asyncio.get_running_loop()
            current_loop_id = id(current_loop)
        except RuntimeError:
            current_loop_id = None
        
        if self._client is None or self._loop_id != current_loop_id:
            if self._client is not None:
                logger.debug("Creating new ES client for new event loop")
            self._client = AsyncElasticsearch(settings.elasticsearch_url)
            self._loop_id = current_loop_id
        
        return self._client
    
    async def create_indices(self):
        await self._create_rooms_index()
        await self._create_apartments_index()
        await self._create_neighborhoods_index()
    
    async def _create_rooms_index(self):
        mapping = {
            "mappings": {
                "properties": {
                    "room_id": {"type": "keyword"},
                    "apartment_id": {"type": "keyword"},
                    "room_type": {"type": "keyword"},
                    "claim": {"type": "text"},
                    "claim_type": {"type": "keyword"},
                    "kind": {"type": "keyword"},
                    "from_claim": {"type": "text"},
                    "is_specific": {"type": "boolean"},
                    "negation": {"type": "boolean"},
                    "claim_vector": {
                        "type": "dense_vector",
                        "dims": 3072,
                        "index": True,
                        "similarity": "cosine",
                        "index_options": {"type": "hnsw", "m": 16, "ef_construction": 200}
                    },
                    "quantifiers": {
                        "type": "nested",
                        "properties": {
                            "qtype": {"type": "keyword"},
                            "noun": {"type": "keyword"},
                            "vmin": {"type": "float"},
                            "vmax": {"type": "float"},
                            "op": {"type": "keyword"},
                            "unit": {"type": "keyword"}
                        }
                    },
                    "source": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "keyword"},
                            "image_url": {"type": "keyword"},
                            "image_index": {"type": "integer"}
                        }
                    }
                }
            }
        }
        
        response = await self.client.options(ignore_status=[400]).indices.create(
            index=self.rooms_index, 
            body=mapping
        )
        if response.meta.status == 200:
            logger.info(f"Created index '{self.rooms_index}'")
        else:
            logger.info(f"Index '{self.rooms_index}' already exists")
    
    async def _create_apartments_index(self):
        mapping = {
            "mappings": {
                "properties": {
                    "apartment_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "neighborhood_id": {"type": "keyword"},
                    "address": {"type": "text"},
                    "apartment_location": {"type": "geo_point"},
                    "claim": {"type": "text"},
                    "claim_type": {"type": "keyword"},
                    "kind": {"type": "keyword"},
                    "from_claim": {"type": "text"},
                    "is_specific": {"type": "boolean"},
                    "negation": {"type": "boolean"},
                    "claim_vector": {
                        "type": "dense_vector",
                        "dims": 3072,
                        "index": True,
                        "similarity": "cosine",
                        "index_options": {"type": "hnsw", "m": 16, "ef_construction": 200}
                    },
                    "quantifiers": {
                        "type": "nested",
                        "properties": {
                            "qtype": {"type": "keyword"},
                            "noun": {"type": "keyword"},
                            "vmin": {"type": "float"},
                            "vmax": {"type": "float"},
                            "op": {"type": "keyword"},
                            "unit": {"type": "keyword"}
                        }
                    },
                    "grounding_metadata": {
                        "type": "object",
                        "properties": {
                            "verified": {"type": "boolean"},
                            "source": {"type": "keyword"},
                            "coordinates": {"type": "geo_point"},
                            "place_id": {"type": "keyword"},
                            "exact_distance_meters": {"type": "integer"},
                            "confidence": {"type": "float"}
                        }
                    },
                    "source": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "keyword"},
                            "image_url": {"type": "keyword"},
                            "image_index": {"type": "integer"}
                        }
                    },
                    "image_urls": {"type": "keyword"},
                    "image_metadata": {
                        "type": "nested",
                        "properties": {
                            "url": {"type": "keyword"},
                            "type": {"type": "keyword"},
                            "index": {"type": "integer"},
                            "prompt": {"type": "text"},
                            "camera": {"type": "keyword"}
                        }
                    },
                    "rent_price": {"type": "float"},
                    "availability_dates": {
                        "type": "nested",
                        "properties": {
                            "start": {"type": "date", "format": "yyyy-MM-dd"},
                            "end": {"type": "date", "format": "yyyy-MM-dd"}
                        }
                    },
                    "property_summary": {"type": "text"},
                    "location_summary": {"type": "text"}
                }
            }
        }
        
        response = await self.client.options(ignore_status=[400]).indices.create(
            index=self.apartments_index, 
            body=mapping
        )
        if response.meta.status == 200:
            logger.info(f"Created index '{self.apartments_index}'")
        else:
            logger.info(f"Index '{self.apartments_index}' already exists")
    
    async def _create_neighborhoods_index(self):
        mapping = {
            "mappings": {
                "properties": {
                    "neighborhood_id": {"type": "keyword"},
                    "neighborhood_name": {"type": "text"},
                    "neighborhood_boundary": {"type": "geo_shape"},
                    "center_point": {"type": "geo_point"},
                    "claim": {"type": "text"},
                    "claim_type": {"type": "keyword"},
                    "kind": {"type": "keyword"},
                    "from_claim": {"type": "text"},
                    "negation": {"type": "boolean"},
                    "claim_vector": {
                        "type": "dense_vector",
                        "dims": 3072,
                        "index": True,
                        "similarity": "cosine",
                        "index_options": {"type": "hnsw"}
                    },
                    "source": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "keyword"},
                            "image_url": {"type": "keyword"},
                            "image_index": {"type": "integer"}
                        }
                    }
                }
            }
        }
        
        response = await self.client.options(ignore_status=[400]).indices.create(
            index=self.neighborhoods_index, 
            body=mapping
        )
        if response.meta.status == 200:
            logger.info(f"Created index '{self.neighborhoods_index}'")
        else:
            logger.info(f"Index '{self.neighborhoods_index}' already exists")
    
    async def close(self):
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._loop_id = None


es_client = ElasticsearchClient()

