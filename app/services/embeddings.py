import asyncio
import logging

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
    
    async def embed_texts(self, texts: list[str], task_type: str = "retrieval_document") -> list[list[float]]:
        if not texts:
            return []
        
        try:
            result = await asyncio.to_thread(
                genai.embed_content,
                model=self.model,
                content=texts,
                task_type=task_type,
                output_dimensionality=self.dimensions,
            )
            
            embeddings = self._extract_batch_embeddings(result)
            
            if len(embeddings) != len(texts):
                raise ValueError(f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}")
            
            for i, embedding in enumerate(embeddings):
                if len(embedding) != self.dimensions:
                    raise ValueError(f"Embedding dimension mismatch at index {i}: expected {self.dimensions}, got {len(embedding)}")
            
            logger.info(f"Generated {len(embeddings)} embeddings (task_type={task_type}), dim={self.dimensions}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    async def embed_query(self, query: str) -> list[float]:
        try:
            result = await asyncio.to_thread(
                genai.embed_content,
                model=self.model,
                content=query,
                task_type="retrieval_query",
                output_dimensionality=self.dimensions,
            )
            
            embedding = self._extract_single_embedding(result)
            
            if len(embedding) != self.dimensions:
                raise ValueError(f"Embedding dimension mismatch: expected {self.dimensions}, got {len(embedding)}")
            
            logger.info(f"Generated query embedding (task_type=retrieval_query), dim={len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            raise
    
    def _extract_single_embedding(self, result: dict) -> list[float]:
        if isinstance(result, dict):
            if "embedding" in result and isinstance(result["embedding"], list):
                return result["embedding"]
            if (
                "embedding" in result
                and isinstance(result["embedding"], dict)
                and "values" in result["embedding"]
            ):
                return result["embedding"]["values"]
        raise ValueError("Unexpected single embedding response format")
    
    def _extract_batch_embeddings(self, result: dict) -> list[list[float]]:
        if isinstance(result, dict):
            if "embeddings" in result and isinstance(result["embeddings"], list):
                out: list[list[float]] = []
                for item in result["embeddings"]:
                    if isinstance(item, dict) and "values" in item:
                        out.append(item["values"])
                    elif isinstance(item, list):
                        out.append(item)
                if out:
                    return out
            if (
                "embedding" in result
                and isinstance(result["embedding"], list)
                and all(isinstance(x, list) for x in result["embedding"])
            ):
                return result["embedding"]
        raise ValueError("Unexpected batch embedding response format")


embedding_service = EmbeddingService()
