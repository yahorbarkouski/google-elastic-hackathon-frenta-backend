import asyncio
import logging
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, "/Users/yahorbarkouski/thenetwork/apartment-search")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.elasticsearch_client import es_client


async def test_setup_endpoint():
    """Test POST /api/setup endpoint."""
    print("\n" + "="*100)
    print("TEST 1: POST /api/setup - Initialize indices")
    print("="*100)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/setup")
        
        print(f"\nStatus: {response.status_code}")
        print(f"Response: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "rooms" in data["indices"]
        assert "apartments" in data["indices"]
        assert "neighborhoods" in data["indices"]
        
        print("✅ Setup endpoint PASSED")


async def test_index_endpoint():
    """Test POST /api/index endpoint with grounding."""
    print("\n" + "="*100)
    print("TEST 2: POST /api/index - Index apartment with grounding")
    print("="*100)
    
    request_data = {
        "document": "Modern 2BR apartment near Bedford Ave L train. Great coffee shops nearby. Rent $3,200/month.",
        "apartment_id": "api_test_001",
        "address": "Bedford Ave, Brooklyn, NY",
        "neighborhood_id": "williamsburg"
    }
    
    print(f"\nRequest:")
    print(f"  Apartment ID: {request_data['apartment_id']}")
    print(f"  Address: {request_data['address']}")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120.0) as client:
        response = await client.post("/api/index", json=request_data)
        
        print(f"\nStatus: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"\nResponse:")
        print(f"  Status: {data['status']}")
        print(f"  Total features: {data['total_features']}")
        print(f"  Domain breakdown: {data['domain_breakdown']}")
        
        assert data["status"] == "success"
        assert data["total_features"] > 0
        
        print("✅ Index endpoint PASSED")
        return data


async def test_batch_index_endpoint():
    """Test POST /api/index/batch endpoint."""
    print("\n" + "="*100)
    print("TEST 3: POST /api/index/batch - Batch index apartments")
    print("="*100)
    
    request_data = {
        "apartments": [
            {
                "document": "Spacious 1BR in Park Slope. Near Prospect Park. Rent $2,800/month.",
                "apartment_id": "batch_test_001",
                "address": "7th Ave, Brooklyn, NY",
                "neighborhood_id": "parkslope"
            },
            {
                "document": "Cozy studio in Williamsburg. Close to coffee shops. Rent $2,200/month.",
                "apartment_id": "batch_test_002",
                "address": "Bedford Ave, Brooklyn, NY",
                "neighborhood_id": "williamsburg"
            }
        ]
    }
    
    print(f"\nBatch indexing {len(request_data['apartments'])} apartments")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=180.0) as client:
        response = await client.post("/api/index/batch", json=request_data)
        
        print(f"\nStatus: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"\nResponse:")
        print(f"  Status: {data['status']}")
        print(f"  Total: {data['total']}")
        print(f"  Successful: {data['successful']}")
        print(f"  Failed: {data['failed']}")
        
        assert data["total"] == 2
        assert data["successful"] == 2
        assert data["failed"] == 0
        
        print("✅ Batch index endpoint PASSED")


async def test_search_endpoint():
    """Test POST /api/search endpoint."""
    print("\n" + "="*100)
    print("TEST 4: POST /api/search - Search with grounding")
    print("="*100)
    
    request_data = {
        "query": "2 bedroom apartment near subway",
        "top_k": 5
    }
    
    print(f"\nQuery: '{request_data['query']}'")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120.0) as client:
        response = await client.post("/api/search", json=request_data)
        
        print(f"\nStatus: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"\nResponse:")
        print(f"  Results found: {len(data['results'])}")
        
        for i, result in enumerate(data['results'][:3], 1):
            print(f"\n  {i}. {result['apartment_id']}")
            print(f"     Score: {result['final_score']:.4f}")
            print(f"     Coverage: {result['coverage_count']} claims")
        
        print("✅ Search endpoint PASSED")


async def test_get_apartment_endpoint():
    """Test GET /api/apartments/{id} endpoint."""
    print("\n" + "="*100)
    print("TEST 5: GET /api/apartments/{id} - Fetch apartment")
    print("="*100)
    
    apartment_id = "api_test_001"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/apartments/{apartment_id}")
        
        print(f"\nStatus: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"\nResponse:")
        print(f"  Apartment ID: {data['apartment_id']}")
        print(f"  Total claims: {data['total_claims']}")
        print(f"  Location: {data['location']}")
        
        print(f"\n  Sample claims:")
        for claim in data['claims'][:5]:
            print(f"    - {claim['claim']} ({claim['claim_type']})")
        
        assert data["apartment_id"] == apartment_id
        assert data["total_claims"] > 0
        
        print("✅ Get apartment endpoint PASSED")


async def test_delete_apartment_endpoint():
    """Test DELETE /api/apartments/{id} endpoint."""
    print("\n" + "="*100)
    print("TEST 6: DELETE /api/apartments/{id} - Delete apartment")
    print("="*100)
    
    apartment_id = "batch_test_002"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/apartments/{apartment_id}")
        
        print(f"\nStatus: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"\nResponse:")
        print(f"  Status: {data['status']}")
        print(f"  Deleted counts: {data['deleted_counts']}")
        print(f"  Total deleted: {data['total_deleted']}")
        
        assert data["status"] == "success"
        assert data["total_deleted"] > 0
        
        print("✅ Delete apartment endpoint PASSED")


async def test_search_with_user_location():
    """Test search with user_location for grounding."""
    print("\n" + "="*100)
    print("TEST 7: POST /api/search - Search with user location (grounding enabled)")
    print("="*100)
    
    request_data = {
        "query": "apartment near coffee shops",
        "top_k": 3,
        "user_location": {"lat": 40.7173, "lng": -73.9569}
    }
    
    print(f"\nQuery: '{request_data['query']}'")
    print(f"User location: {request_data['user_location']}")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120.0) as client:
        response = await client.post("/api/search", json=request_data)
        
        print(f"\nStatus: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"\nResults: {len(data['results'])}")
        
        for result in data['results']:
            print(f"  - {result['apartment_id']}: score={result['final_score']:.3f}")
        
        print("✅ Search with location PASSED")


async def run_all_endpoint_tests():
    """Run comprehensive endpoint tests."""
    print("\n" + "="*100)
    print("🧪 API ENDPOINTS TEST SUITE")
    print("="*100)
    
    try:
        await test_setup_endpoint()
        await test_index_endpoint()
        await test_batch_index_endpoint()
        await test_search_endpoint()
        await test_get_apartment_endpoint()
        await test_delete_apartment_endpoint()
        await test_search_with_user_location()
        
        print("\n" + "="*100)
        print("🎉 ALL ENDPOINT TESTS PASSED!")
        print("="*100)
        
        print("\n📋 ENDPOINTS SUMMARY:")
        print("  ✅ POST   /api/setup            - Initialize indices")
        print("  ✅ POST   /api/index            - Index single apartment with grounding")
        print("  ✅ POST   /api/index/batch      - Bulk index apartments")
        print("  ✅ POST   /api/search           - Search with optional grounding")
        print("  ✅ GET    /api/apartments/{id}  - Fetch apartment by ID")
        print("  ✅ DELETE /api/apartments/{id}  - Delete apartment")
        print()
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await es_client.close()


if __name__ == "__main__":
    asyncio.run(run_all_endpoint_tests())

