import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embeddings import embedding_service
from app.services.elasticsearch_client import es_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReembeddingService:
    def __init__(self):
        self.batch_size = 100
        self.total_updated = 0
        self.total_failed = 0
    
    async def reembed_all_indices(self, skip_completed: bool = False):
        logger.info("Starting re-embedding process for all indices")
        logger.info("=" * 80)
        
        await es_client.create_indices()
        
        if not skip_completed:
            await self._reembed_index(
                index_name=es_client.rooms_index,
                id_field="room_id",
                index_type="rooms"
            )
            
            await self._reembed_index(
                index_name=es_client.apartments_index,
                id_field="apartment_id",
                index_type="apartments"
            )
        else:
            logger.info("Skipping rooms and apartments (already completed)")
        
        await self._reembed_index(
            index_name=es_client.neighborhoods_index,
            id_field="neighborhood_id",
            index_type="neighborhoods"
        )
        
        logger.info("=" * 80)
        logger.info(f"Re-embedding complete!")
        logger.info(f"Total documents updated: {self.total_updated}")
        logger.info(f"Total documents failed: {self.total_failed}")
    
    async def _reembed_index(self, index_name: str, id_field: str, index_type: str):
        logger.info(f"\n{'='*80}")
        logger.info(f"Processing index: {index_name}")
        logger.info(f"{'='*80}")
        
        try:
            count_response = await es_client.client.count(index=index_name)
            total_docs = count_response['count']
            logger.info(f"Total documents in {index_name}: {total_docs}")
        except Exception as e:
            logger.error(f"Failed to count documents in {index_name}: {e}")
            return
        
        if total_docs == 0:
            logger.info(f"No documents to process in {index_name}")
            return
        
        processed = 0
        failed = 0
        
        query = {"query": {"match_all": {}}}
        
        try:
            batch = []
            
            async for doc in self._scroll_documents(index_name, query):
                batch.append(doc)
                
                if len(batch) >= self.batch_size:
                    batch_processed, batch_failed = await self._process_batch(index_name, batch, processed, total_docs)
                    processed += batch_processed
                    failed += batch_failed
                    batch = []
            
            if batch:
                batch_processed, batch_failed = await self._process_batch(index_name, batch, processed, total_docs)
                processed += batch_processed
                failed += batch_failed
            
            await es_client.client.indices.refresh(index=index_name)
            
            logger.info(f"\n{'='*80}")
            logger.info(f"Completed {index_name}:")
            logger.info(f"  ✓ Successfully updated: {processed}")
            logger.info(f"  ✗ Failed: {failed}")
            logger.info(f"{'='*80}\n")
            
            self.total_updated += processed
            self.total_failed += failed
            
        except Exception as e:
            logger.error(f"Fatal error processing {index_name}: {e}")
            raise
    
    async def _process_batch(self, index_name: str, batch: list, current_processed: int, total_docs: int):
        claim_texts = []
        valid_docs = []
        
        for doc in batch:
            doc_id = doc['_id']
            source = doc['_source']
            claim_text = source.get('claim')
            
            if not claim_text:
                logger.warning(f"Document {doc_id} has no claim text, skipping")
                continue
            
            claim_texts.append(claim_text)
            valid_docs.append((doc_id, claim_text))
        
        if not claim_texts:
            return 0, len(batch)
        
        try:
            new_embeddings = await embedding_service.embed_texts(claim_texts, task_type="retrieval_document")
            
            for (doc_id, _), embedding in zip(valid_docs, new_embeddings):
                await self._update_document_embedding(index_name, doc_id, embedding)
            
            processed = len(valid_docs)
            failed = len(batch) - processed
            
            total_processed = current_processed + processed
            logger.info(f"[{index_name}] Progress: {total_processed}/{total_docs} ({(total_processed/total_docs)*100:.1f}%) - Batch: {processed} docs")
            
            return processed, failed
            
        except Exception as e:
            logger.error(f"Failed to process batch: {e}")
            return 0, len(batch)
    
    async def _scroll_documents(self, index_name: str, query: dict):
        scroll_timeout = "5m"
        
        response = await es_client.client.search(
            index=index_name,
            body=query,
            scroll=scroll_timeout,
            size=100
        )
        
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']
        
        while hits:
            for hit in hits:
                yield hit
            
            response = await es_client.client.scroll(
                scroll_id=scroll_id,
                scroll=scroll_timeout
            )
            
            scroll_id = response['_scroll_id']
            hits = response['hits']['hits']
        
        await es_client.client.clear_scroll(scroll_id=scroll_id)
    
    async def _update_document_embedding(self, index_name: str, doc_id: str, new_embedding: list[float]):
        await es_client.client.update(
            index=index_name,
            id=doc_id,
            doc={"claim_vector": new_embedding}
        )


async def main():
    service = ReembeddingService()
    skip_completed = "--skip-completed" in sys.argv or "--neighborhoods-only" in sys.argv
    
    try:
        await service.reembed_all_indices(skip_completed=skip_completed)
    except KeyboardInterrupt:
        logger.warning("\nProcess interrupted by user")
        logger.info(f"Partial progress: {service.total_updated} documents updated")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await es_client.close()


if __name__ == "__main__":
    asyncio.run(main())

