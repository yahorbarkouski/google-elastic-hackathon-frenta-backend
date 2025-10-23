import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.indexer.pipeline import indexer_pipeline
from app.search.pipeline import search_pipeline
from app.services.crud import crud_service
from app.services.grounding import grounding_service
from app.services.preview_storage import preview_storage
from app.services.synthetic_generator import synthetic_generator

logger = logging.getLogger(__name__)

router = APIRouter()


class IndexRequest(BaseModel):
    document: Optional[str] = None
    apartment_id: str
    title: Optional[str] = None
    address: Optional[str] = None
    neighborhood_id: Optional[str] = None
    image_urls: Optional[list[str]] = None
    rent_price: Optional[float] = None
    availability_dates: Optional[list[dict]] = None


class BatchIndexRequest(BaseModel):
    apartments: list[IndexRequest]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    user_location: Optional[dict] = None
    verify_claims: bool = True
    double_check_matches: bool = False


class MapsGroundingRequest(BaseModel):
    prompt: str
    latitude: float
    longitude: float
    enable_widget: bool = True


@router.post("/api/setup")
async def setup_indices():
    """Initialize Elasticsearch indices for rooms, apartments, and neighborhoods."""
    result = await crud_service.setup_indices()
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result


@router.post("/api/index")
async def index_apartment(request: IndexRequest):
    """
    Index a single apartment with multi-modal support (text + images).
    Supports text descriptions, image URLs, or both.
    If address is provided, geocoding and grounding will be applied.
    """
    if not request.document and not request.image_urls:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'document' or 'image_urls' must be provided"
        )
    
    try:
        result = await indexer_pipeline.process(
            document=request.document or "",
            apartment_id=request.apartment_id,
            title=request.title,
            address=request.address,
            neighborhood_id=request.neighborhood_id,
            image_urls=request.image_urls,
            rent_price=request.rent_price,
            availability_dates=request.availability_dates
        )
        return result
    except Exception as e:
        logger.error(f"Error indexing apartment {request.apartment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/index/batch")
async def index_apartments_batch(request: BatchIndexRequest):
    """
    Bulk index multiple apartments with multi-modal support.
    Processes apartments in parallel for efficiency.
    """
    import asyncio
    
    logger.info(f"Batch indexing {len(request.apartments)} apartments")
    
    tasks = []
    for apt_req in request.apartments:
        task = indexer_pipeline.process(
            document=apt_req.document or "",
            apartment_id=apt_req.apartment_id,
            title=apt_req.title,
            address=apt_req.address,
            neighborhood_id=apt_req.neighborhood_id,
            image_urls=apt_req.image_urls,
            rent_price=apt_req.rent_price,
            availability_dates=apt_req.availability_dates
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successes = []
    errors = []
    
    for apt_req, result in zip(request.apartments, results):
        if isinstance(result, Exception):
            errors.append({
                "apartment_id": apt_req.apartment_id,
                "error": str(result)
            })
        else:
            successes.append(result)
    
    return {
        "status": "complete",
        "total": len(request.apartments),
        "successful": len(successes),
        "failed": len(errors),
        "results": successes,
        "errors": errors
    }


@router.post("/api/search")
async def search_apartments(request: SearchRequest):
    """
    Search for apartments with optional grounding.
    If user_location is provided, grounding and geo-filtering will be applied.
    """
    try:
        results = await search_pipeline.search(
            query=request.query,
            top_k=request.top_k,
            user_location=request.user_location,
            verify_claims=request.verify_claims,
            double_check_matches=request.double_check_matches
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"Error searching: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/apartments")
async def list_apartments(
    page: int = 1,
    page_size: int = 20,
    has_images: bool = False
):
    """
    List all apartments with basic info (id, address, location, images, claim count).
    Supports pagination and filtering by image presence.
    
    Query params:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - has_images: Filter apartments that have images (default: false)
    """
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be >= 1")
    
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="Page size must be between 1 and 100")
    
    try:
        result = await crud_service.list_apartments(
            page=page,
            page_size=page_size,
            has_images=has_images
        )
        return result
    except Exception as e:
        logger.error(f"Error listing apartments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/apartments/{apartment_id}")
async def get_apartment(apartment_id: str):
    """Fetch a specific apartment by ID with all claims."""
    result = await crud_service.get_apartment(apartment_id)
    
    if result is None:
        raise HTTPException(status_code=404, detail=f"Apartment {apartment_id} not found")
    
    return result


@router.delete("/api/apartments/{apartment_id}")
async def delete_apartment(apartment_id: str):
    """Delete an apartment and all associated claims."""
    result = await crud_service.delete_apartment(apartment_id)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result


class GeneratePreviewRequest(BaseModel):
    description: Optional[str] = None
    price_range: Optional[dict] = None
    num_images: int = 6
    neighborhood_hint: Optional[str] = None
    city_hint: Optional[str] = None
    aspect_ratio: str = "16:9"


class ConfirmGenerationRequest(BaseModel):
    preview_id: str
    overrides: Optional[dict] = None


@router.post("/api/apartments/generate/preview")
async def generate_apartment_preview(request: GeneratePreviewRequest):
    """Generate a preview of a synthetic apartment with images and metadata."""
    try:
        logger.info(f"Generating apartment preview with {request.num_images} images")
        
        preview_data = await synthetic_generator.generate_full_apartment(
            description_hint=request.description,
            price_range=request.price_range,
            num_images=request.num_images,
            neighborhood_hint=request.neighborhood_hint,
            city_hint=request.city_hint,
            aspect_ratio=request.aspect_ratio
        )
        
        preview_id = str(uuid.uuid4())
        await preview_storage.store_preview(preview_id, preview_data)
        
        image_list = [
            {
                "index": img["index"],
                "url": f"/api/preview/{preview_id}/{img['index']}.png",
                "type": img["type"],
                "prompt": img["prompt"][:150]
            }
            for img in preview_data["images"]
        ]
        
        return {
            "preview_id": preview_id,
            "apartment_id": preview_data["apartment_id"],
            "title": preview_data["title"],
            "description": preview_data["description"],
            "address": preview_data["address"],
            "neighborhood_id": preview_data["neighborhood_id"],
            "rent_price": preview_data["rent_price"],
            "availability_dates": preview_data["availability_dates"],
            "style_aesthetic": preview_data["style_plan"].get("aesthetic", "N/A"),
            "images": image_list,
            "num_images": len(image_list),
            "expires_in_hours": 1
        }
        
    except Exception as e:
        logger.error(f"Error generating apartment preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/preview/{preview_id}/{image_index}.png")
async def get_preview_image(preview_id: str, image_index: int):
    """Get a specific image from a preview."""
    try:
        image_bytes = await preview_storage.get_preview_image(preview_id, image_index)
        
        if not image_bytes:
            raise HTTPException(status_code=404, detail="Preview image not found or expired")
        
        return Response(content=image_bytes, media_type="image/png")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving preview image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/images/generated/{filename}")
async def get_generated_image(filename: str):
    """Serve generated apartment images."""
    try:
        import asyncio
        from pathlib import Path
        
        image_path = Path("./output/generated_apartments") / filename
        
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        
        if image_path.suffix.lower() not in ['.png', '.jpg', '.jpeg']:
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        image_bytes = await asyncio.to_thread(image_path.read_bytes)
        
        media_type = "image/png" if image_path.suffix.lower() == '.png' else "image/jpeg"
        return Response(content=image_bytes, media_type=media_type)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving generated image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/apartments/generate/confirm")
async def confirm_apartment_generation(request: ConfirmGenerationRequest):
    """Confirm apartment generation and index to Elasticsearch."""
    try:
        preview = await preview_storage.get_preview(request.preview_id)
        
        if not preview:
            raise HTTPException(status_code=404, detail="Preview not found or expired")
        
        metadata = {
            "title": preview.get("title"),
            "description": preview.get("description"),
            "address": preview.get("address"),
            "neighborhood_id": preview.get("neighborhood_id"),
            "rent_price": preview.get("rent_price"),
            "availability_dates": preview.get("availability_dates", [])
        }
        
        if request.overrides:
            metadata.update(request.overrides)
        
        apartment_id = preview["apartment_id"]
        
        permanent = await preview_storage.promote_to_permanent(request.preview_id, apartment_id)
        logger.info(f"Promoted preview to permanent: {apartment_id}")
        
        from pathlib import Path
        image_urls = [
            f"/api/images/generated/{Path(path).name}"
            for path in permanent["image_paths"]
        ]
        
        image_descriptions = preview.get("image_descriptions", [])
        
        logger.info(f"Starting indexing for {apartment_id} with {len(image_descriptions)} precomputed descriptions")
        await indexer_pipeline.process(
            document=metadata["description"],
            apartment_id=apartment_id,
            title=metadata["title"],
            address=metadata["address"],
            neighborhood_id=metadata["neighborhood_id"],
            image_urls=image_urls,
            rent_price=metadata["rent_price"],
            availability_dates=metadata["availability_dates"],
            precomputed_image_descriptions=image_descriptions
        )
        
        logger.info(f"Successfully indexed synthetic apartment: {apartment_id}")
        
        return {
            "apartment_id": apartment_id,
            "indexed": True,
            "elasticsearch_id": apartment_id,
            "message": "Apartment generated and indexed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming apartment generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/preview/{preview_id}")
async def cancel_preview(preview_id: str):
    """Cancel and cleanup a preview."""
    try:
        await preview_storage.cleanup_preview(preview_id)
        return {"message": "Preview cancelled successfully"}
        
    except Exception as e:
        logger.error(f"Error cancelling preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/maps-grounding")
async def generate_maps_grounded_content(request: MapsGroundingRequest):
    """Generate Maps-grounded content using Gemini API."""
    try:
        result = await grounding_service.generate_grounded_content(
            prompt=request.prompt,
            latitude=request.latitude,
            longitude=request.longitude,
            enable_widget=request.enable_widget
        )
        return result
        
    except Exception as e:
        logger.error(f"Error generating Maps-grounded content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

