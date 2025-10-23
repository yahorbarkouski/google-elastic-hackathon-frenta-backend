import asyncio
import httpx


async def test_synthetic_generation():
    base_url = "http://localhost:8000"
    
    print("Testing synthetic apartment generation...\n")
    
    print("Step 1: Generate preview...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{base_url}/api/apartments/generate/preview",
            json={
                "description": "Cozy studio in Brooklyn Heights with modern amenities",
                "num_images": 2,
                "price_range": {"min": 2000, "max": 3000}
            }
        )
        
        if response.status_code != 200:
            print(f"❌ Preview generation failed: {response.text}")
            return
        
        preview = response.json()
        print(f"✓ Preview generated: {preview['preview_id']}")
        print(f"  Title: {preview['title']}")
        print(f"  Price: ${preview['rent_price']}/month")
        print(f"  Address: {preview['address']}")
        print(f"  Images: {preview['num_images']}")
        print()
        
        print("Step 2: Fetch preview image...")
        image_response = await client.get(f"{base_url}{preview['images'][0]['url']}")
        if image_response.status_code == 200:
            print(f"✓ Image {preview['images'][0]['index']} fetched ({len(image_response.content)} bytes)")
        else:
            print(f"❌ Image fetch failed: {image_response.status_code}")
        print()
        
        print("Step 3: Confirm and index...")
        confirm_response = await client.post(
            f"{base_url}/api/apartments/generate/confirm",
            json={"preview_id": preview["preview_id"]}
        )
        
        if confirm_response.status_code != 200:
            print(f"❌ Confirmation failed: {confirm_response.text}")
            return
        
        result = confirm_response.json()
        print(f"✓ Apartment indexed: {result['apartment_id']}")
        print(f"  Elasticsearch ID: {result['elasticsearch_id']}")
        print()
        
        print("✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_synthetic_generation())

