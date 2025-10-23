import asyncio
import logging
import sys

from app.services.crud import crud_service
from app.services.elasticsearch_client import es_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


async def test_list_apartments():
    """Test listing all apartments with pagination."""
    
    logger.info("=" * 80)
    logger.info("TESTING APARTMENT LISTING")
    logger.info("=" * 80)
    
    try:
        result = await crud_service.list_apartments(page=1, page_size=10)
        
        logger.info(f"✅ Total apartments: {result['pagination']['total']}")
        logger.info(f"📄 Page: {result['pagination']['page']}/{result['pagination']['total_pages']}")
        logger.info(f"📊 Page size: {result['pagination']['page_size']}")
        logger.info("")
        
        logger.info("📋 Apartments on this page:")
        for i, apt in enumerate(result['apartments'], 1):
            logger.info(f"\n{i}. {apt['apartment_id']}")
            logger.info(f"   Address: {apt['address']}")
            logger.info(f"   Location: {apt['location']}")
            logger.info(f"   Neighborhood: {apt['neighborhood_id']}")
            logger.info(f"   Images: {len(apt['image_urls'])} images")
            if apt['image_urls']:
                for idx, url in enumerate(apt['image_urls'][:2]):
                    logger.info(f"      - Image {idx}: {url[:80]}...")
            logger.info(f"   Claims: {apt['claim_count']}")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("TESTING IMAGE FILTER")
        logger.info("=" * 80)
        
        result_with_images = await crud_service.list_apartments(
            page=1, 
            page_size=10,
            has_images=True
        )
        
        logger.info(f"✅ Apartments with images: {result_with_images['pagination']['total']}")
        logger.info("")
        
        for i, apt in enumerate(result_with_images['apartments'], 1):
            logger.info(f"{i}. {apt['apartment_id']} - {len(apt['image_urls'])} images")
        
        logger.info("")
        logger.info("✨ All tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await es_client.close()


if __name__ == "__main__":
    success = asyncio.run(test_list_apartments())
    sys.exit(0 if success else 1)

