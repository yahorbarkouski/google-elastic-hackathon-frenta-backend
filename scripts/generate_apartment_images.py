import asyncio
import json
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

from app.config import settings


async def generate_style_plan(description: str) -> dict:
    client = genai.Client(api_key=settings.google_api_key)
    
    prompt = f"""Create a comprehensive style guide for generating consistent, high-quality real estate photography of this property:

{description}

Generate a detailed style plan including:
1. Overall aesthetic (modern, industrial, minimalist, traditional, eclectic, etc.)
2. Color palette (walls, floors, furniture, accents)
3. Lighting style (natural, warm, cool, dramatic, soft)
4. Furniture style and materials
5. Architectural details and features
6. Time of day for interior shots
7. Weather/lighting for exterior shots
8. Photography style (wide-angle, intimate, architectural, lifestyle)

Be extremely specific about colors, textures, materials, and mood so all images feel like they're from the same cohesive property.

Return JSON:
{{
  "aesthetic": "Modern industrial with warm accents",
  "color_palette": {{
    "walls": "White with exposed brick accent walls",
    "floors": "Light oak hardwood",
    "furniture": "Mid-century modern in walnut and brass",
    "accents": "Warm copper, muted green plants"
  }},
  "lighting": {{
    "type": "Soft natural light from large windows",
    "time_of_day": "Late afternoon golden hour",
    "artificial": "Warm LED recessed lighting, brass fixtures"
  }},
  "materials": {{
    "kitchen": "White quartz countertops, stainless steel appliances, subway tile",
    "bathroom": "White marble, chrome fixtures, frameless glass",
    "living": "Leather, linen, brass, wood"
  }},
  "architectural_details": ["Exposed brick walls", "12-foot ceilings", "Large industrial windows"],
  "photography_style": "Professional architectural photography, 16mm wide-angle lens, f/5.6, natural light prioritized",
  "exterior_conditions": "Clear day, late afternoon, warm sunlight"
}}"""
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["Text"],
            temperature=0.5,
            response_mime_type="application/json"
        )
    )
    
    response_text = response.text.strip()
    if response_text.startswith("```json"):
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif response_text.startswith("```"):
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    return json.loads(response_text)


async def generate_image_prompts(description: str, style_plan: dict, num_images: int) -> list[dict]:
    client = genai.Client(api_key=settings.google_api_key)
    
    style_context = json.dumps(style_plan, indent=2)
    
    prompt = f"""Generate {num_images} photorealistic image prompts for real estate photography following this EXACT style guide:

STYLE GUIDE:
{style_context}

PROPERTY DESCRIPTION:
{description}

Generate prompts for different views:
- Living room/main space (2-3 angles)
- Kitchen (2 angles)
- Bedroom(s) (1-2 angles)
- Bathroom (1 angle)
- Building exterior (1 angle)
- Special features

CRITICAL REQUIREMENTS:
1. Every prompt MUST reference the exact colors, materials, and lighting from the style guide
2. Use consistent furniture style and materials across all rooms
3. Maintain the same time of day and lighting quality
4. Reference architectural details consistently
5. Use professional real estate photography language
6. Specify camera settings and composition
7. High resolution, sharp focus, professional quality

Return JSON:
{{
  "prompts": [
    {{"prompt": "A professional architectural photograph...", "type": "living_room", "camera": "16mm wide-angle"}},
    ...
  ]
}}"""
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["Text"],
            temperature=0.6,
            response_mime_type="application/json"
        )
    )
    
    response_text = response.text.strip()
    if response_text.startswith("```json"):
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif response_text.startswith("```"):
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    data = json.loads(response_text)
    prompts = data.get("prompts", [])
    return prompts[:num_images]


async def generate_single_image(client: genai.Client, prompt: str, index: int, aspect_ratio: str = "16:9") -> dict:
    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.5-flash-image",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["Image"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio)
        )
    )
    
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return {
                "index": index,
                "prompt": prompt,
                "image_data": part.inline_data.data
            }
    
    raise ValueError(f"No image generated for prompt {index}")


async def generate_property_images(
    description: str,
    num_images: int = 6,
    output_dir: str = "./output/generated_apartments",
    apartment_id: str = "property",
    aspect_ratio: str = "16:9"
) -> dict:
    client = genai.Client(api_key=settings.google_api_key)
    
    print("Phase 1: Generating style plan...")
    style_plan = await generate_style_plan(description)
    print(f"✓ Style plan created: {style_plan.get('aesthetic', 'N/A')}")
    
    print(f"\nPhase 2: Generating {num_images} coordinated image prompts...")
    prompts_data = await generate_image_prompts(description, style_plan, num_images)
    
    print(f"\nPhase 3: Generating {len(prompts_data)} images in parallel...")
    tasks = [
        generate_single_image(client, p["prompt"], idx, aspect_ratio)
        for idx, p in enumerate(prompts_data)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    saved_images = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"✗ Image {idx} failed: {result}")
            continue
        
        image = Image.open(BytesIO(result["image_data"]))
        file_path = output_path / f"{apartment_id}_{idx}.png"
        image.save(file_path, optimize=True, quality=95)
        
        saved_images.append({
            "index": idx,
            "prompt": result["prompt"],
            "file_path": str(file_path),
            "type": prompts_data[idx].get("type", "unknown"),
            "camera": prompts_data[idx].get("camera", "unknown")
        })
        
        print(f"✓ Image {idx} saved: {file_path.name}")
    
    apartment_data = {
        "apartment_id": apartment_id,
        "description": description,
        "style_plan": style_plan,
        "num_images": len(saved_images),
        "aspect_ratio": aspect_ratio,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "images": saved_images
    }
    
    manifest_path = output_path / f"{apartment_id}_manifest.json"
    manifest_path.write_text(json.dumps(apartment_data, indent=2))
    
    await update_index(apartment_data, output_dir)
    
    print(f"\n✓ Generated {len(saved_images)}/{num_images} images")
    print(f"✓ Manifest: {manifest_path}")
    
    return apartment_data


async def update_index(apartment_data: dict, output_dir: str):
    index_path = Path(output_dir) / "apartments_index.json"
    
    if index_path.exists():
        index = json.loads(index_path.read_text())
    else:
        index = {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "apartments": []
        }
    
    index["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    existing_idx = next(
        (i for i, apt in enumerate(index["apartments"]) if apt["apartment_id"] == apartment_data["apartment_id"]),
        None
    )
    
    index_entry = {
        "apartment_id": apartment_data["apartment_id"],
        "description": apartment_data["description"],
        "style_aesthetic": apartment_data["style_plan"].get("aesthetic", "N/A"),
        "num_images": apartment_data["num_images"],
        "generated_at": apartment_data["generated_at"],
        "manifest_path": f"{apartment_data['apartment_id']}_manifest.json",
        "image_paths": [img["file_path"] for img in apartment_data["images"]]
    }
    
    if existing_idx is not None:
        index["apartments"][existing_idx] = index_entry
        print("✓ Updated existing entry in index")
    else:
        index["apartments"].append(index_entry)
        print("✓ Added new entry to index")
    
    index_path.write_text(json.dumps(index, indent=2))
    print(f"✓ Index updated: {index_path}")


async def batch_generate(config_path: str):
    with open(config_path) as f:
        config = json.load(f)
    
    apartments = config.get("apartments", [])
    print(f"Batch generating {len(apartments)} apartments\n")
    
    for idx, apt in enumerate(apartments):
        print(f"\n{'='*60}")
        print(f"Apartment {idx + 1}/{len(apartments)}: {apt.get('id', f'apt_{idx}')}")
        print(f"{'='*60}\n")
        
        await generate_property_images(
            description=apt["description"],
            num_images=apt.get("num_images", 6),
            output_dir=apt.get("output_dir", "./output/generated_apartments"),
            apartment_id=apt.get("id", f"apt_{idx}"),
            aspect_ratio=apt.get("aspect_ratio", "16:9")
        )
    
    print(f"\n✓ All {len(apartments)} apartments completed")


def view_index(output_dir: str = "./output/generated_apartments"):
    index_path = Path(output_dir) / "apartments_index.json"
    
    if not index_path.exists():
        print(f"No index found at {index_path}")
        return
    
    index = json.loads(index_path.read_text())
    
    print(f"\n{'=' * 80}")
    print("APARTMENTS INDEX")
    print(f"{'=' * 80}")
    print(f"Version: {index.get('version', 'N/A')}")
    print(f"Created: {index.get('created_at', 'N/A')}")
    print(f"Updated: {index.get('updated_at', 'N/A')}")
    print(f"Total apartments: {len(index.get('apartments', []))}\n")
    
    for idx, apt in enumerate(index.get("apartments", []), 1):
        print(f"{idx}. {apt['apartment_id']}")
        print(f"   Style: {apt.get('style_aesthetic', 'N/A')}")
        print(f"   Images: {apt['num_images']}")
        print(f"   Generated: {apt['generated_at']}")
        print(f"   Description: {apt['description'][:80]}...")
        print()


def print_usage():
    print("""
Usage:
  python generate_apartment_images.py [OPTIONS]

Options:
  --description TEXT       Property description
  --num-images INT        Number of images (default: 6)
  --output-dir PATH       Output directory (default: ./output/generated_apartments)
  --apartment-id TEXT     ID for file naming (default: property)
  --aspect-ratio RATIO    Aspect ratio: 1:1, 16:9, 4:3, etc. (default: 16:9)
  --config PATH           Batch generation config file
  --view-index            View the apartments index
  --help                  Show this message

Examples:
  # Single apartment with style coordination
  python generate_apartment_images.py \\
    --description "Modern 2BR in Williamsburg with exposed brick, hardwood floors, chef's kitchen" \\
    --num-images 8 \\
    --apartment-id "williamsburg_2br_001"

  # Batch generation
  python generate_apartment_images.py --config apartments.json

  # View generated apartments index
  python generate_apartment_images.py --view-index

Features:
  - Phase 1: Generates comprehensive style plan (colors, materials, lighting)
  - Phase 2: Creates coordinated prompts following style guide
  - Phase 3: Generates all images in parallel
  - Maintains local index database (apartments_index.json)
  - Higher quality: optimize=True, quality=95

Config format:
{
  "apartments": [
    {
      "id": "apt_001",
      "description": "Luxurious penthouse...",
      "num_images": 8,
      "output_dir": "./output/apartments",
      "aspect_ratio": "16:9"
    }
  ]
}
""")


async def main():
    if len(sys.argv) == 1 or "--help" in sys.argv:
        print_usage()
        return
    
    args = {}
    i = 1
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            key = sys.argv[i][2:].replace("-", "_")
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
                args[key] = sys.argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1
    
    if "view_index" in args:
        view_index(args.get("output_dir", "./output/generated_apartments"))
    elif "config" in args:
        await batch_generate(args["config"])
    elif "description" in args:
        await generate_property_images(
            description=args["description"],
            num_images=int(args.get("num_images", 6)),
            output_dir=args.get("output_dir", "./output/generated_apartments"),
            apartment_id=args.get("apartment_id", "property"),
            aspect_ratio=args.get("aspect_ratio", "16:9")
        )
    else:
        print("Error: --description, --config, or --view-index required\n")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

