import asyncio
import logging
import sys

from app.indexer.pipeline import indexer_pipeline
from app.services.elasticsearch_client import es_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


async def test_indexing():
    test_description = """
    Spacious 3 bedroom 2 bathroom apartment with high ceilings (approximately 12 feet).
    Beautiful hardwood floors throughout. Updated kitchen with gas stove and double door refrigerator.
    Built in 2015. Located on a quiet residential street with no bars nearby.
    Pet-friendly building. Private balcony with city views. In-unit washer and dryer.
    Walking distance to grocery stores and public transit. Modern fixtures and neutral paint colors.
    """
    
    print("🏠 Testing Apartment Indexing Pipeline")
    print(f"📝 Description: {test_description[:100]}...")
    print("\n🔄 Starting indexing process...\n")
    
    logger.info("="*80)
    logger.info("STARTING INDEXING TEST")
    logger.info("="*80)
    
    try:
        logger.info("Calling indexer_pipeline.process()...")
        result = await indexer_pipeline.process(
            document=test_description,
            apartment_id="test_apt_001"
        )
        
        print(f"✅ Status: {result['status']}")
        print(f"📊 Total Features Extracted: {result['total_features']}")
        print(f"\n📋 Sample Features:")
        
        for i, feature in enumerate(result['features'][:10], 1):
            print(f"\n{i}. {feature.claim}")
            print(f"   Type: {feature.claim_type}")
            print(f"   Kind: {feature.kind}")
            print(f"   Embedding Dimensions: {len(feature.embedding)}")
        
        if len(result['features']) > 10:
            print(f"\n... and {len(result['features']) - 10} more features")
        
        print("\n✨ Indexing test completed successfully!")
        return True
    
    except Exception as e:
        print(f"\n❌ Error during indexing: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        logger.info("Closing ES client...")
        await es_client.close()
        logger.info("ES client closed")


if __name__ == "__main__":
    success = asyncio.run(test_indexing())
    sys.exit(0 if success else 1)
