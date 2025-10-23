import logging
from typing import Optional

import numpy as np

from app.models import Claim, ClaimSource
from app.services.embeddings import embedding_service

logger = logging.getLogger(__name__)


class DeduplicationService:
    def __init__(self, similarity_threshold: float = 0.98):
        self.similarity_threshold = similarity_threshold
    
    async def deduplicate_claims(self, claims: list[Claim]) -> list[Claim]:
        if len(claims) <= 1:
            return claims
        
        logger.info(f"Deduplicating {len(claims)} claims (threshold={self.similarity_threshold})")
        
        claim_texts = [c.claim for c in claims]
        embeddings = await embedding_service.embed_texts(claim_texts)
        
        claim_embeddings = list(zip(claims, embeddings))
        
        unique_claims = []
        seen_indices = set()
        
        for i, (claim_i, emb_i) in enumerate(claim_embeddings):
            if i in seen_indices:
                continue
            
            merged_sources = [claim_i.source] if claim_i.source else []
            duplicates_found = False
            
            for j in range(i + 1, len(claim_embeddings)):
                if j in seen_indices:
                    continue
                
                claim_j, emb_j = claim_embeddings[j]
                
                similarity = self._cosine_similarity(emb_i, emb_j)
                
                if similarity >= self.similarity_threshold:
                    logger.info(f"Duplicate detected (similarity={similarity:.3f}): '{claim_i.claim}' ≈ '{claim_j.claim}'")
                    
                    if claim_j.source and claim_j.source not in merged_sources:
                        merged_sources.append(claim_j.source)
                    
                    seen_indices.add(j)
                    duplicates_found = True
            
            final_claim = claim_i.model_copy()
            
            if duplicates_found and len(merged_sources) > 1:
                final_claim = final_claim.model_copy(update={
                    "source": self._merge_sources(merged_sources)
                })
            
            unique_claims.append(final_claim)
        
        removed_count = len(claims) - len(unique_claims)
        logger.info(f"Deduplication complete: {len(unique_claims)} unique claims ({removed_count} duplicates removed)")
        
        return unique_claims
    
    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(v1, v2) / (norm1 * norm2))
    
    def _merge_sources(self, sources: list[Optional[ClaimSource]]) -> ClaimSource:
        text_source = next((s for s in sources if s and s.type == "text"), None)
        image_sources = [s for s in sources if s and s.type == "image"]
        
        if text_source:
            return text_source
        
        if image_sources:
            return image_sources[0]
        
        return ClaimSource(type="text")


deduplication_service = DeduplicationService()

