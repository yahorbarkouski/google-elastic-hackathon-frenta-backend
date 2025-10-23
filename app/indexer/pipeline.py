import asyncio
import logging
from typing import Optional

from app.models import ApartmentDocument, AvailabilityRange, Claim, ClaimSource, Domain, EmbeddedClaim, ImageMetadata
from app.services.deduplication import deduplication_service
from app.services.document_chunker import document_chunker
from app.services.elasticsearch_client import es_client
from app.services.embeddings import embedding_service
from app.services.expansion import expansion_service
from app.services.geocoding import geocoding_service
from app.services.grounding import grounding_service
from app.services.llm import llm_service
from app.services.quantifiers import quantifier_service
from app.services.vision import vision_service

logger = logging.getLogger(__name__)


class IndexerPipeline:
    async def process(
        self, 
        document: str, 
        apartment_id: str,
        title: Optional[str] = None,
        address: Optional[str] = None,
        neighborhood_id: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
        image_metadata: Optional[list[dict]] = None,
        rent_price: Optional[float] = None,
        availability_dates: Optional[list[dict]] = None,
        precomputed_image_descriptions: Optional[list[str]] = None
    ) -> dict:
        logger.info(f"Starting indexing pipeline for apartment {apartment_id}")
        
        all_claims, image_descriptions = await self._extract_claims_from_all_sources(
            document, address, image_urls, precomputed_image_descriptions
        )
        
        if not all_claims:
            return self._empty_result(apartment_id)
        
        unique_claims = await deduplication_service.deduplicate_claims(all_claims)
        logger.info(f"Phase 1.5: After deduplication: {len(unique_claims)} unique claims")
        
        structured_properties, location = await asyncio.gather(
            self._extract_structured_properties(document, rent_price, availability_dates),
            self._geocode_address(address)
        )
        
        claims_with_verified = await self._ground_claims(unique_claims, location)
        
        expanded_claims = await expansion_service.expand_claims(claims_with_verified)
        logger.info(f"Phase 3: Expanded to {len(expanded_claims)} total claims")
        
        claims_with_quantifiers = await quantifier_service.extract_quantifiers(expanded_claims)
        logger.info("Phase 4: Processed quantifiers")
        
        embedded_claims = await self._embed_claims(claims_with_quantifiers)
        
        parsed_image_metadata = []
        if image_metadata:
            parsed_image_metadata = [ImageMetadata(**m) for m in image_metadata]
        
        apartment_doc = ApartmentDocument(
            apartment_id=apartment_id,
            title=title,
            neighborhood_id=neighborhood_id,
            address=address,
            location=location,
            raw_description=document,
            image_urls=image_urls or [],
            image_metadata=parsed_image_metadata,
            claims=embedded_claims,
            rent_price=structured_properties.rent_price,
            availability_dates=structured_properties.availability_dates
        )
        
        await self._index_to_elasticsearch(apartment_doc)
        logger.info("Phase 6: Indexed to Elasticsearch")
        
        await self._enrich_apartment(apartment_doc, document, image_descriptions, address, location)
        logger.info("Phase 7: Generated enrichment summaries")
        
        return self._build_result(apartment_id, embedded_claims)
    
    async def _extract_claims_from_all_sources(
        self, 
        document: str, 
        address: Optional[str],
        image_urls: Optional[list[str]],
        precomputed_descriptions: Optional[list[str]] = None
    ) -> tuple[list[Claim], list[str]]:
        tasks = []
        image_task_indices = []
        
        if document:
            tasks.append(self._extract_text_claims(document, address))
        
        if image_urls and precomputed_descriptions:
            logger.info(f"Phase 1b: Using {len(precomputed_descriptions)} precomputed image descriptions")
            for idx, (image_url, description) in enumerate(zip(image_urls, precomputed_descriptions)):
                image_task_indices.append(len(tasks))
                tasks.append(self._extract_claims_from_description(description, idx, address))
        elif image_urls:
            logger.info(f"Phase 1b: Processing {len(image_urls)} images with vision AI in parallel")
            for idx, image_url in enumerate(image_urls):
                image_task_indices.append(len(tasks))
                tasks.append(self._extract_image_claims(image_url, idx, address))
        
        if not tasks:
            logger.warning("No sources provided for claim extraction")
            return [], []
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_claims = []
        image_descriptions = []
        
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error extracting claims: {result}")
                continue
            
            if idx in image_task_indices:
                claims, description = result
                all_claims.extend(claims)
                if description:
                    image_descriptions.append(description)
            else:
                all_claims.extend(result)
        
        logger.info(f"Phase 1: Total {len(all_claims)} base claims from all sources")
        logger.info(f"Phase 1: Preserved {len(image_descriptions)} image descriptions")
        return all_claims, image_descriptions
    
    async def _extract_text_claims(self, document: str, address: Optional[str]) -> list[Claim]:
        if len(document) > 1000:
            logger.info(f"Phase 1a: Document is {len(document)} chars, chunking for parallel processing")
            chunks = document_chunker.chunk(document)
            logger.info(f"Phase 1a: Split into {len(chunks)} chunks")
            
            tasks = []
            for idx, chunk in enumerate(chunks):
                tasks.append(llm_service.aggregate_claims(chunk, address))
            
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            claims = []
            for idx, result in enumerate(chunk_results):
                if isinstance(result, Exception):
                    logger.error(f"Error extracting claims from chunk {idx}: {result}")
                    continue
                claims.extend(result)
            
            for claim in claims:
                claim.source = ClaimSource(type="text")
            
            logger.info(f"Phase 1a: Extracted {len(claims)} claims from {len(chunks)} chunks")
            return claims
        else:
            claims = await llm_service.aggregate_claims(document, address)
            for claim in claims:
                claim.source = ClaimSource(type="text")
            logger.info(f"Phase 1a: Extracted {len(claims)} claims from text (no chunking needed)")
            return claims
    
    async def _extract_image_claims(
        self, 
        image_url: str, 
        image_index: int, 
        address: Optional[str]
    ) -> tuple[list[Claim], str]:
        try:
            description = await vision_service.describe_single_image(image_url, image_index)
            
            if not description:
                logger.warning(f"Empty description for image {image_index}")
                return [], ""
            
            claims = await llm_service.aggregate_claims(description, address)
            for claim in claims:
                claim.source = ClaimSource(type="image", image_url=image_url, image_index=image_index)
            
            logger.info(f"Phase 1b: Extracted {len(claims)} claims from image {image_index}")
            return claims, description
        except Exception as e:
            logger.error(f"Failed to extract claims from image {image_index}: {e}")
            return [], ""
    
    async def _extract_claims_from_description(
        self, 
        description: str, 
        image_index: int, 
        address: Optional[str]
    ) -> tuple[list[Claim], str]:
        try:
            if not description:
                logger.warning(f"Empty precomputed description for image {image_index}")
                return [], ""
            
            claims = await llm_service.aggregate_claims(description, address)
            for claim in claims:
                claim.source = ClaimSource(type="image", image_url=None, image_index=image_index)
            
            logger.info(f"Phase 1b: Extracted {len(claims)} claims from precomputed description {image_index}")
            return claims, description
        except Exception as e:
            logger.error(f"Failed to extract claims from precomputed description {image_index}: {e}")
            return [], ""
    
    async def _geocode_address(self, address: Optional[str]) -> Optional[dict[str, float]]:
        if not address:
            return None
        
        location = await geocoding_service.geocode_address(address)
        logger.info(f"Geocoded address '{address}' to {location}")
        return location
    
    async def _ground_claims(
        self, 
        claims: list[Claim], 
        location: Optional[dict[str, float]]
    ) -> list[Claim]:
        if not location:
            return claims
        
        groundable_claims = [c for c in claims if grounding_service.should_ground_claim(c)]
        
        if not groundable_claims:
            return claims
        
        logger.info(f"Phase 2: Grounding {len(groundable_claims)} claims")
        grounding_result = await grounding_service.ground_claims_batch(
            claims=groundable_claims,
            location=location
        )
        
        verified_claims = grounding_result.verified_claims
        claims.extend(verified_claims)
        logger.info(f"Phase 2: Added {len(verified_claims)} verified claims from grounding")
        
        return claims
    
    async def _embed_claims(self, claims: list[Claim]) -> list[EmbeddedClaim]:
        claim_texts = [c.claim for c in claims]
        embeddings = await embedding_service.embed_texts(claim_texts)
        logger.info(f"Phase 5: Generated {len(embeddings)} embeddings")
        
        embedded_claims = []
        for claim, embedding in zip(claims, embeddings):
            embedded_claim = EmbeddedClaim(**claim.model_dump(), embedding=embedding)
            embedded_claims.append(embedded_claim)
        
        return embedded_claims
    
    async def _extract_structured_properties(
        self, 
        document: str, 
        rent_price: Optional[float], 
        availability_dates: Optional[list[dict]]
    ):
        from app.models import StructuredProperty
        
        if rent_price is not None and availability_dates is not None:
            logger.info("Phase 1.6: Using provided structured properties")
            return StructuredProperty(
                rent_price=rent_price,
                availability_dates=[AvailabilityRange(**d) for d in availability_dates]
            )
        
        logger.info("Phase 1.6: Extracting structured properties from document")
        extracted = await llm_service.extract_structured_properties(document)
        
        final_rent_price = rent_price if rent_price is not None else extracted.rent_price
        final_availability = availability_dates if availability_dates is not None else extracted.availability_dates
        
        if availability_dates:
            final_availability = [AvailabilityRange(**d) for d in availability_dates]
        
        logger.info(
            f"Phase 1.6: Structured properties - rent_price: {final_rent_price}, "
            f"availability_dates: {len(final_availability)} ranges"
        )
        
        return StructuredProperty(
            rent_price=final_rent_price,
            availability_dates=final_availability
        )
    
    def _empty_result(self, apartment_id: str) -> dict:
        logger.warning("No claims extracted from any source")
        return {
            "status": "success",
            "apartment_id": apartment_id,
            "total_features": 0,
            "features": [],
            "domain_breakdown": {"neighborhood": 0, "apartment": 0, "room": 0}
        }
    
    def _build_result(self, apartment_id: str, embedded_claims: list[EmbeddedClaim]) -> dict:
        return {
            "status": "success",
            "apartment_id": apartment_id,
            "total_features": len(embedded_claims),
            "features": embedded_claims,
            "domain_breakdown": {
                "neighborhood": len([c for c in embedded_claims if c.domain == Domain.NEIGHBORHOOD]),
                "apartment": len([c for c in embedded_claims if c.domain == Domain.APARTMENT]),
                "room": len([c for c in embedded_claims if c.domain == Domain.ROOM]),
            }
        }
    
    async def _index_to_elasticsearch(self, apartment_doc: ApartmentDocument):
        room_claims = [c for c in apartment_doc.claims if c.domain == Domain.ROOM]
        apartment_claims = [c for c in apartment_doc.claims if c.domain == Domain.APARTMENT]
        neighborhood_claims = [c for c in apartment_doc.claims if c.domain == Domain.NEIGHBORHOOD]
        
        await self._index_room_claims(apartment_doc, room_claims)
        await self._index_apartment_claims(apartment_doc, apartment_claims)
        await self._index_neighborhood_claims(apartment_doc, neighborhood_claims)
        
        await es_client.client.indices.refresh(index=es_client.rooms_index)
        await es_client.client.indices.refresh(index=es_client.apartments_index)
        await es_client.client.indices.refresh(index=es_client.neighborhoods_index)
    
    async def _index_room_claims(self, apartment_doc: ApartmentDocument, room_claims: list[EmbeddedClaim]):
        for idx, claim in enumerate(room_claims):
            doc = {
                "room_id": f"{apartment_doc.apartment_id}_room_{idx}",
                "apartment_id": apartment_doc.apartment_id,
                "room_type": claim.room_type,
                "claim": claim.claim,
                "claim_type": claim.claim_type.value,
                "kind": claim.kind.value,
                "from_claim": claim.from_claim,
                "is_specific": claim.is_specific,
                "negation": claim.negation,
                "claim_vector": claim.embedding,
                "quantifiers": self._serialize_quantifiers(claim.quantifiers)
            }
            
            if claim.source:
                doc["source"] = claim.source.model_dump()
            
            await es_client.client.index(
                index=es_client.rooms_index,
                id=doc["room_id"],
                document=doc
            )
    
    async def _index_apartment_claims(self, apartment_doc: ApartmentDocument, apartment_claims: list[EmbeddedClaim]):
        for idx, claim in enumerate(apartment_claims):
            doc = {
                "apartment_id": apartment_doc.apartment_id,
                "title": apartment_doc.title,
                "neighborhood_id": apartment_doc.neighborhood_id,
                "address": apartment_doc.address,
                "claim": claim.claim,
                "claim_type": claim.claim_type.value,
                "kind": claim.kind.value,
                "from_claim": claim.from_claim,
                "is_specific": claim.is_specific,
                "negation": claim.negation,
                "claim_vector": claim.embedding,
                "quantifiers": self._serialize_quantifiers(claim.quantifiers),
                "image_urls": apartment_doc.image_urls,
                "image_metadata": [m.model_dump() for m in apartment_doc.image_metadata]
            }
            
            if claim.source:
                doc["source"] = claim.source.model_dump()
            
            if apartment_doc.location:
                doc["apartment_location"] = {
                    "lat": apartment_doc.location["lat"],
                    "lon": apartment_doc.location["lng"]
                }
            
            if claim.grounding_metadata:
                doc["grounding_metadata"] = self._serialize_grounding_metadata(claim.grounding_metadata)
            
            if apartment_doc.rent_price is not None:
                doc["rent_price"] = apartment_doc.rent_price
            
            if apartment_doc.availability_dates:
                doc["availability_dates"] = [
                    {"start": av.start, "end": av.end} for av in apartment_doc.availability_dates
                ]
            
            await es_client.client.index(
                index=es_client.apartments_index,
                id=f"{apartment_doc.apartment_id}_claim_{idx}",
                document=doc
            )
    
    async def _index_neighborhood_claims(self, apartment_doc: ApartmentDocument, neighborhood_claims: list[EmbeddedClaim]):
        for idx, claim in enumerate(neighborhood_claims):
            doc = {
                "neighborhood_id": apartment_doc.neighborhood_id or "unknown",
                "claim": claim.claim,
                "claim_type": claim.claim_type.value,
                "kind": claim.kind.value,
                "from_claim": claim.from_claim,
                "negation": claim.negation,
                "claim_vector": claim.embedding,
            }
            
            if claim.source:
                doc["source"] = claim.source.model_dump()
            
            await es_client.client.index(
                index=es_client.neighborhoods_index,
                id=f"{apartment_doc.neighborhood_id or 'unknown'}_claim_{idx}",
                document=doc
            )
    
    def _serialize_quantifiers(self, quantifiers: list) -> list[dict]:
        quantifiers_json = []
        for q in quantifiers:
            q_dict = q.model_dump()
            if q_dict['vmax'] == float('inf'):
                q_dict['vmax'] = 999999999
            if q_dict['vmin'] == float('inf'):
                q_dict['vmin'] = 999999999
            quantifiers_json.append(q_dict)
        return quantifiers_json
    
    def _serialize_grounding_metadata(self, metadata) -> dict:
        result = {
            "verified": metadata.verified,
            "source": metadata.source,
            "confidence": metadata.confidence
        }
        
        if metadata.coordinates:
            result["coordinates"] = {
                "lat": metadata.coordinates["lat"],
                "lon": metadata.coordinates["lng"]
            }
        
        if metadata.place_id:
            result["place_id"] = metadata.place_id
        
        if metadata.exact_distance_meters:
            result["exact_distance_meters"] = metadata.exact_distance_meters
        
        return result
    
    async def _enrich_apartment(
        self,
        apartment_doc: ApartmentDocument,
        description: str,
        image_descriptions: list[str],
        address: Optional[str],
        location: Optional[dict[str, float]]
    ):
        from app.services.enrichment import enrichment_service
        
        tasks = []
        
        if not apartment_doc.title:
            tasks.append(enrichment_service.generate_title(description, address))
        else:
            tasks.append(asyncio.sleep(0))
        
        tasks.append(enrichment_service.generate_property_summary(description, image_descriptions))
        
        if location and address:
            tasks.append(enrichment_service.generate_location_summary(location, address))
        else:
            tasks.append(asyncio.sleep(0))
        
        results = await asyncio.gather(*tasks)
        title = results[0]
        property_summary = results[1]
        location_result = results[2]
        
        if not apartment_doc.title and isinstance(title, str):
            apartment_doc.title = title
        
        apartment_doc.property_summary = property_summary if property_summary else None
        
        if isinstance(location_result, tuple):
            location_summary, widget_token = location_result
            apartment_doc.location_summary = location_summary if location_summary else None
            apartment_doc.location_widget_token = widget_token
        else:
            apartment_doc.location_summary = None
            apartment_doc.location_widget_token = None
        
        await self._update_elasticsearch_summaries(apartment_doc)
    
    async def _update_elasticsearch_summaries(self, apartment_doc: ApartmentDocument):
        apartment_claims = [c for c in apartment_doc.claims if c.domain == Domain.APARTMENT]
        
        if not apartment_claims:
            logger.warning(f"No apartment claims found for {apartment_doc.apartment_id}, skipping summary update")
            return
        
        doc_id = f"{apartment_doc.apartment_id}_claim_0"
        
        update_body = {}
        if apartment_doc.title:
            update_body["title"] = apartment_doc.title
        if apartment_doc.property_summary:
            update_body["property_summary"] = apartment_doc.property_summary
        if apartment_doc.location_summary:
            update_body["location_summary"] = apartment_doc.location_summary
        if apartment_doc.location_widget_token:
            update_body["location_widget_token"] = apartment_doc.location_widget_token
        
        if update_body:
            try:
                await es_client.client.update(
                    index=es_client.apartments_index,
                    id=doc_id,
                    doc=update_body
                )
                logger.info(f"Updated summaries for {apartment_doc.apartment_id}")
            except Exception as e:
                logger.error(f"Failed to update summaries in ES: {e}")


indexer_pipeline = IndexerPipeline()
