import asyncio
import json
import logging
from pathlib import Path

from app.services.crud import crud_service
from app.services.elasticsearch_client import es_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_manifest(manifest_path: Path) -> dict:
    with open(manifest_path) as f:
        return json.load(f)


async def update_apartment_metadata(apartment_id: str, manifest: dict):
    image_metadata = []
    for img in manifest.get("images", []):
        image_url = f"/api/images/generated/{Path(img['file_path']).name}"
        image_metadata.append({
            "url": image_url,
            "type": img.get("type", "unknown"),
            "index": img.get("index", 0),
            "prompt": img.get("prompt"),
            "camera": img.get("camera")
        })
    
    logger.info(f"Updating {apartment_id} with {len(image_metadata)} image metadata entries")
    
    query = {
        "query": {"term": {"apartment_id": apartment_id}}
    }
    
    response = await es_client.client.search(
        index=es_client.apartments_index,
        body=query,
        size=1000
    )
    
    if not response["hits"]["hits"]:
        logger.warning(f"No documents found for {apartment_id}")
        return
    
    update_script = {
        "script": {
            "source": "ctx._source.image_metadata = params.image_metadata",
            "params": {
                "image_metadata": image_metadata
            }
        }
    }
    
    updated_count = 0
    for hit in response["hits"]["hits"]:
        doc_id = hit["_id"]
        await es_client.client.update(
            index=es_client.apartments_index,
            id=doc_id,
            body=update_script
        )
        updated_count += 1
    
    await es_client.client.indices.refresh(index=es_client.apartments_index)
    
    logger.info(f"✅ Updated {updated_count} documents for {apartment_id}")


async def main():
    _ = es_client.client
    
    manifests_dir = Path("output/generated_apartments")
    manifest_files = list(manifests_dir.glob("*_manifest.json"))
    
    if not manifest_files:
        logger.warning("No manifest files found in output/generated_apartments")
        return
    
    logger.info(f"Found {len(manifest_files)} manifest files")
    
    for manifest_path in manifest_files:
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing: {manifest_path.name}")
            logger.info(f"{'='*60}")
            
            manifest = await load_manifest(manifest_path)
            apartment_id = manifest.get("apartment_id")
            
            if not apartment_id:
                logger.error(f"No apartment_id found in {manifest_path.name}")
                continue
            
            await update_apartment_metadata(apartment_id, manifest)
            
        except Exception as e:
            logger.error(f"Error processing {manifest_path.name}: {e}", exc_info=True)
            continue
    
    await es_client.close()
    logger.info(f"\n{'='*60}")
    logger.info("✅ Reindexing complete!")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())

