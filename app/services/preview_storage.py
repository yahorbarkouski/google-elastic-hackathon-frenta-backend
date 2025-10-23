import asyncio
import json
import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PreviewStorageManager:
    def __init__(self):
        self.preview_dir = Path("./output/previews")
        self.permanent_dir = Path("./output/generated_apartments")
        self.ttl_hours = 1
    
    async def store_preview(self, preview_id: str, preview_data: dict) -> None:
        preview_path = self.preview_dir / preview_id
        preview_path.mkdir(parents=True, exist_ok=True)
        
        serializable_data = {**preview_data}
        serializable_data["images"] = []
        
        for idx, image_data in enumerate(preview_data.get("images", [])):
            if "image_bytes" in image_data:
                image_path = preview_path / f"{idx}.png"
                await asyncio.to_thread(image_path.write_bytes, image_data["image_bytes"])
            
            serializable_image = {k: v for k, v in image_data.items() if k != "image_bytes"}
            serializable_data["images"].append(serializable_image)
        
        metadata_path = preview_path / "metadata.json"
        metadata_json = json.dumps({
            **serializable_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=self.ttl_hours)).isoformat()
        }, indent=2)
        await asyncio.to_thread(metadata_path.write_text, metadata_json)
        
        logger.info(f"Stored preview {preview_id} with {len(preview_data.get('images', []))} images")
    
    async def get_preview(self, preview_id: str) -> Optional[dict]:
        preview_path = self.preview_dir / preview_id / "metadata.json"
        
        if not preview_path.exists():
            logger.warning(f"Preview {preview_id} not found")
            return None
        
        metadata = json.loads(await asyncio.to_thread(preview_path.read_text))
        
        expires_at = datetime.fromisoformat(metadata["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            logger.warning(f"Preview {preview_id} expired")
            await self.cleanup_preview(preview_id)
            return None
        
        return metadata
    
    async def get_preview_image(self, preview_id: str, image_index: int) -> Optional[bytes]:
        image_path = self.preview_dir / preview_id / f"{image_index}.png"
        
        if not image_path.exists():
            logger.warning(f"Preview image {preview_id}/{image_index} not found")
            return None
        
        return await asyncio.to_thread(image_path.read_bytes)
    
    async def promote_to_permanent(self, preview_id: str, apartment_id: str) -> dict:
        preview_path = self.preview_dir / preview_id
        permanent_path = self.permanent_dir
        permanent_path.mkdir(parents=True, exist_ok=True)
        
        metadata = await self.get_preview(preview_id)
        if not metadata:
            raise ValueError(f"Preview {preview_id} not found or expired")
        
        image_paths = []
        for idx in range(len(metadata.get("images", []))):
            source = preview_path / f"{idx}.png"
            dest = permanent_path / f"{apartment_id}_{idx}.png"
            await asyncio.to_thread(shutil.copy2, source, dest)
            image_paths.append(str(dest))
        
        manifest_path = permanent_path / f"{apartment_id}_manifest.json"
        manifest_data = {
            "apartment_id": apartment_id,
            "description": metadata["description"],
            "style_plan": metadata["style_plan"],
            "num_images": len(metadata["images"]),
            "aspect_ratio": metadata.get("aspect_ratio", "16:9"),
            "generated_at": metadata["created_at"],
            "images": [
                {
                    "index": idx,
                    "prompt": img["prompt"],
                    "file_path": image_paths[idx],
                    "type": img["type"],
                    "camera": img.get("camera", "unknown")
                }
                for idx, img in enumerate(metadata["images"])
            ]
        }
        await asyncio.to_thread(manifest_path.write_text, json.dumps(manifest_data, indent=2))
        
        await self.update_permanent_index(apartment_id, metadata, image_paths)
        
        await self.cleanup_preview(preview_id)
        
        logger.info(f"Promoted preview {preview_id} to permanent {apartment_id}")
        return {"apartment_id": apartment_id, "image_paths": image_paths, "manifest_path": str(manifest_path)}
    
    async def update_permanent_index(self, apartment_id: str, metadata: dict, image_paths: list[str]) -> None:
        index_path = self.permanent_dir / "apartments_index.json"
        
        if index_path.exists():
            index = json.loads(await asyncio.to_thread(index_path.read_text))
        else:
            index = {
                "version": "1.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "apartments": []
            }
        
        index["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        index_entry = {
            "apartment_id": apartment_id,
            "description": metadata["description"],
            "style_aesthetic": metadata["style_plan"].get("aesthetic", "N/A"),
            "num_images": len(image_paths),
            "generated_at": metadata["created_at"],
            "indexed": True,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "manifest_path": f"{apartment_id}_manifest.json",
            "image_paths": image_paths,
            "synthetic_metadata": {
                "title": metadata.get("title"),
                "address": metadata.get("address"),
                "rent_price": metadata.get("rent_price"),
                "availability_dates": metadata.get("availability_dates", [])
            }
        }
        
        existing_idx = next(
            (i for i, apt in enumerate(index["apartments"]) if apt["apartment_id"] == apartment_id),
            None
        )
        
        if existing_idx is not None:
            index["apartments"][existing_idx] = index_entry
        else:
            index["apartments"].append(index_entry)
        
        await asyncio.to_thread(index_path.write_text, json.dumps(index, indent=2))
    
    async def cleanup_preview(self, preview_id: str) -> None:
        preview_path = self.preview_dir / preview_id
        
        if preview_path.exists():
            await asyncio.to_thread(shutil.rmtree, preview_path)
            logger.info(f"Cleaned up preview {preview_id}")
    
    async def cleanup_expired_previews(self) -> int:
        if not self.preview_dir.exists():
            return 0
        
        cleaned = 0
        for preview_path in self.preview_dir.iterdir():
            if not preview_path.is_dir():
                continue
            
            metadata_path = preview_path / "metadata.json"
            if not metadata_path.exists():
                await asyncio.to_thread(shutil.rmtree, preview_path)
                cleaned += 1
                continue
            
            try:
                metadata = json.loads(await asyncio.to_thread(metadata_path.read_text))
                expires_at = datetime.fromisoformat(metadata["expires_at"])
                
                if datetime.now(timezone.utc) > expires_at:
                    await asyncio.to_thread(shutil.rmtree, preview_path)
                    cleaned += 1
                    logger.info(f"Cleaned up expired preview {preview_path.name}")
            except Exception as e:
                logger.error(f"Error checking preview {preview_path.name}: {e}")
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired previews")
        
        return cleaned


preview_storage = PreviewStorageManager()

