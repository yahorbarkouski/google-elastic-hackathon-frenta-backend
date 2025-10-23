import asyncio
import logging
import sys

from app.indexer.pipeline import indexer_pipeline
from app.services.crud import crud_service
from app.services.elasticsearch_client import es_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


async def drop_and_recreate_indices():
    """Drop all existing indices and recreate them with new schema."""
    logger.info("=" * 80)
    logger.info("DROPPING AND RECREATING INDICES")
    logger.info("=" * 80)
    
    try:
        for index_name in [es_client.rooms_index, es_client.apartments_index, es_client.neighborhoods_index]:
            try:
                await es_client.client.indices.delete(index=index_name)
                logger.info(f"✅ Dropped index: {index_name}")
            except Exception as e:
                logger.info(f"ℹ️  Index {index_name} did not exist or couldn't be deleted: {e}")
        
        result = await crud_service.setup_indices()
        
        if result["status"] == "success":
            logger.info(f"✅ Created indices: {', '.join(result['indices'].values())}")
        else:
            logger.error(f"❌ Failed to create indices: {result['message']}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in index management: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multimodal_indexing():
    """Test indexing with text description + multiple images."""
    
    test_description = """
    Modern 2 bedroom apartment in Brooklyn. Spacious living room with large windows and natural light.
    Fully renovated kitchen with stainless steel appliances. Hardwood floors throughout.
    Pet-friendly building with laundry in unit. Close to L train.
    """
    
    image_urls = [
        "https://images.unsplash.com/photo-1556912173-46c336c7fd55?w=800",
        "https://images.unsplash.com/photo-1556911220-bff31c812dba?w=800"
    ]
    
    logger.info("=" * 80)
    logger.info("TESTING MULTI-MODAL INDEXING")
    logger.info("=" * 80)
    logger.info(f"📝 Text description: {test_description[:100]}...")
    logger.info(f"🖼️  Images: {len(image_urls)}")
    for idx, url in enumerate(image_urls):
        logger.info(f"   Image {idx}: {url}")
    logger.info("")
    
    try:
        result = await indexer_pipeline.process(
            document=test_description,
            apartment_id="multimodal_test_001",
            address="123 Bedford Ave, Brooklyn, NY 11211",
            neighborhood_id="williamsburg",
            image_urls=image_urls
        )
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("INDEXING RESULTS")
        logger.info("=" * 80)
        logger.info(f"✅ Status: {result['status']}")
        logger.info(f"📊 Total Features: {result['total_features']}")
        logger.info(f"🏘️  Domain Breakdown:")
        logger.info(f"   - Neighborhood: {result['domain_breakdown']['neighborhood']}")
        logger.info(f"   - Apartment: {result['domain_breakdown']['apartment']}")
        logger.info(f"   - Room: {result['domain_breakdown']['room']}")
        
        logger.info("")
        logger.info("📋 Sample Features (first 15):")
        for i, feature in enumerate(result['features'][:15], 1):
            source_type = feature.source.type if feature.source else "unknown"
            source_info = ""
            if feature.source and feature.source.type == "image":
                source_info = f" (Image {feature.source.image_index})"
            
            logger.info(f"\n{i}. {feature.claim}")
            logger.info(f"   Type: {feature.claim_type} | Domain: {feature.domain} | Kind: {feature.kind}")
            logger.info(f"   Source: {source_type}{source_info}")
        
        if len(result['features']) > 15:
            logger.info(f"\n... and {len(result['features']) - 15} more features")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error during indexing: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_retrieve_apartment():
    """Test retrieving the indexed apartment with images."""
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("TESTING APARTMENT RETRIEVAL")
    logger.info("=" * 80)
    
    try:
        result = await crud_service.get_apartment("multimodal_test_001")
        
        if not result:
            logger.error("❌ Apartment not found")
            return False
        
        logger.info(f"✅ Retrieved apartment: {result['apartment_id']}")
        logger.info(f"📍 Address: {result.get('address', 'N/A')}")
        logger.info(f"🗺️  Location: {result.get('location', 'N/A')}")
        logger.info(f"🖼️  Images: {len(result.get('image_urls', []))}")
        
        for idx, url in enumerate(result.get('image_urls', [])):
            logger.info(f"   Image {idx}: {url}")
        
        logger.info(f"📊 Total Claims: {result['total_claims']}")
        
        text_claims = [c for c in result['claims'] if c.get('source') and c['source'].get('type') == 'text']
        image_claims = [c for c in result['claims'] if c.get('source') and c['source'].get('type') == 'image']
        
        logger.info(f"   - From text: {len(text_claims)}")
        logger.info(f"   - From images: {len(image_claims)}")
        
        logger.info("")
        logger.info("📋 Sample Claims:")
        for i, claim in enumerate(result['claims'][:10], 1):
            source = claim.get('source')
            if source:
                source_str = source.get('type', 'unknown')
                if source.get('type') == 'image':
                    source_str += f" (idx: {source.get('image_index')})"
            else:
                source_str = 'unknown'
            
            logger.info(f"{i}. [{source_str}] {claim['claim']} ({claim['claim_type']})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error retrieving apartment: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    logger.info("🏠 Multi-Modal Apartment Indexing Test")
    logger.info("")
    
    try:
        if not await drop_and_recreate_indices():
            logger.error("❌ Failed to setup indices")
            return False
        
        logger.info("")
        await asyncio.sleep(1)
        
        index_result = await test_multimodal_indexing()
        if not index_result:
            logger.error("❌ Indexing test failed")
            return False
        
        await asyncio.sleep(1)
        
        if not await test_retrieve_apartment():
            logger.error("❌ Retrieval test failed")
            return False
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✨ ALL TESTS PASSED")
        logger.info("=" * 80)
        
        return True
        
    finally:
        await es_client.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

