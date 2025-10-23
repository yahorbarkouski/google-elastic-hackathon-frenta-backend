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

from app.indexer.pipeline import indexer_pipeline
from app.search.pipeline import search_pipeline
from app.services.elasticsearch_client import es_client


async def main():
    print("\n🧪 QUICK GROUNDING TEST")
    print("="*80)
    
    await es_client.create_indices()
    
    apartment_desc = """
2BR apartment near Bedford Ave L train station in Williamsburg.
Close to great coffee shops. Rent $3,500/month.
    """
    
    print("\n1. Indexing apartment...")
    result = await indexer_pipeline.process(
        document=apartment_desc,
        apartment_id="test_quick_001",
        address="Bedford Ave, Brooklyn, NY",
        neighborhood_id="williamsburg"
    )
    print(f"   ✓ Indexed {result['total_features']} claims")
    print(f"   ✓ Breakdown: {result['domain_breakdown']}")
    
    print("\n2. Searching with location-based query...")
    search_results = await search_pipeline.search(
        query="apartment near subway in Williamsburg",
        top_k=3
    )
    
    print(f"   ✓ Found {len(search_results)} results")
    for r in search_results:
        print(f"     - {r.apartment_id}: score={r.final_score:.3f}, coverage={r.coverage_count}")
    
    assert len(search_results) > 0, "Should find results"
    assert any("test_quick_001" in r.apartment_id for r in search_results), "Should find our apartment"
    
    print("\n✅ Quick test PASSED!")
    
    await es_client.close()


if __name__ == "__main__":
    asyncio.run(main())

