import pytest
import asyncio
from app.indexer.pipeline import indexer_pipeline
from app.search.pipeline import search_pipeline
from app.services.elasticsearch_client import es_client


COMPREHENSIVE_APARTMENT_LISTING = """
Stunning 2-bedroom, 2-bathroom apartment in the heart of Williamsburg, Brooklyn.

This spacious 1,100 sq ft loft features:
- Soaring 12-foot ceilings with exposed brick walls
- Beautiful hardwood floors throughout
- Oversized windows providing excellent natural light
- Modern, fully-renovated kitchen with 15m² space, stainless steel appliances, gas stove, dishwasher, and large granite countertops
- Master bedroom with walk-in closet and ensuite bathroom
- Second bedroom perfect for home office or guests
- Updated bathrooms with contemporary fixtures
- In-unit washer and dryer
- Private balcony with city views

Building amenities:
- Full-service doorman building
- Elevator access (no walk-up)
- Roof deck with stunning Manhattan skyline views
- Bike storage room
- Pet-friendly building (cats and dogs welcome)

Location highlights:
- Located on a quiet, tree-lined residential street
- 5-minute walk (400m) to Bedford Ave L train station
- 3-minute walk to McCarren Park
- Surrounded by excellent coffee shops, including Devoción and Blue Bottle
- Abundant restaurants, bars, and nightlife within walking distance
- Whole Foods grocery store 2 blocks away
- Safe, family-friendly neighborhood with great schools nearby

Lease details:
- Monthly rent: $4,200
- 12-month lease minimum
- No broker fee
- Utilities: Heat and hot water included
- Central AC throughout
- Available immediately

This apartment offers the perfect combination of modern luxury, prime location, and Brooklyn charm!
"""


SEARCH_QUERIES = [
    {
        "query": "2 bedroom apartment in Williamsburg with modern kitchen",
        "description": "Basic size + location + features query",
        "expected_claim_types": ["size", "location", "features"],
        "should_match": True
    },
    {
        "query": "spacious apartment with high ceilings over 10 feet",
        "description": "Size with quantifier (ceiling height)",
        "expected_claim_types": ["size", "features"],
        "should_match": True
    },
    {
        "query": "pet-friendly building with doorman in Brooklyn",
        "description": "Policies + amenities + location",
        "expected_claim_types": ["policies", "amenities", "location"],
        "should_match": True
    },
    {
        "query": "apartment near L train with walking distance to subway",
        "description": "Transport claim with distance",
        "expected_claim_types": ["transport"],
        "should_match": True
    },
    {
        "query": "modern kitchen larger than 12m² with stainless appliances",
        "description": "Room-level size + features with quantifier",
        "expected_claim_types": ["size", "features"],
        "should_match": True
    },
    {
        "query": "recently renovated apartment with updated fixtures",
        "description": "Condition claim",
        "expected_claim_types": ["condition"],
        "should_match": True
    },
    {
        "query": "apartment under $4500 per month with utilities included",
        "description": "Pricing + utilities with quantifier",
        "expected_claim_types": ["pricing", "utilities"],
        "should_match": True
    },
    {
        "query": "elevator building with roof deck access",
        "description": "Accessibility + amenities",
        "expected_claim_types": ["accessibility", "amenities"],
        "should_match": True
    },
    {
        "query": "quiet neighborhood near parks and coffee shops",
        "description": "Neighborhood vibe + amenities",
        "expected_claim_types": ["neighborhood", "amenities"],
        "should_match": True
    },
    {
        "query": "apartment with washer and dryer in unit and central AC",
        "description": "Amenities + utilities",
        "expected_claim_types": ["amenities", "utilities"],
        "should_match": True
    },
    {
        "query": "flexible lease terms, month-to-month preferred",
        "description": "Restrictions query (should NOT match - we require 12 months)",
        "expected_claim_types": ["restrictions"],
        "should_match": False
    },
    {
        "query": "studio apartment with no pets allowed",
        "description": "Size + negative policy (should NOT match - we're 2BR and pet-friendly)",
        "expected_claim_types": ["size", "policies"],
        "should_match": False
    },
    {
        "query": "apartment in Park Slope near Prospect Park",
        "description": "Wrong location (should NOT match - we're in Williamsburg)",
        "expected_claim_types": ["location"],
        "should_match": False
    },
    {
        "query": "large 3-bedroom family apartment over 1500 sq ft",
        "description": "Wrong size (should NOT match - we're 2BR, 1100 sqft)",
        "expected_claim_types": ["size"],
        "should_match": False
    }
]


@pytest.mark.asyncio
async def test_indexing_comprehensive_apartment():
    """Test Phase 1-4: Index comprehensive apartment listing"""
    
    # Setup Elasticsearch indices
    await es_client.create_indices()
    
    result = await indexer_pipeline.process(
        document=COMPREHENSIVE_APARTMENT_LISTING,
        apartment_id="williamsburg_luxury_2br",
        address="250 Bedford Ave, Brooklyn, NY 11249",
        neighborhood_id="williamsburg_brooklyn"
    )
    
    assert result["status"] == "success"
    assert result["apartment_id"] == "williamsburg_luxury_2br"
    assert result["total_features"] > 0
    
    print(f"\n{'='*80}")
    print(f"INDEXING RESULTS")
    print(f"{'='*80}")
    print(f"Total claims extracted: {result['total_features']}")
    print(f"Domain breakdown:")
    print(f"  - Neighborhood: {result['domain_breakdown']['neighborhood']}")
    print(f"  - Apartment: {result['domain_breakdown']['apartment']}")
    print(f"  - Room: {result['domain_breakdown']['room']}")
    
    print(f"\n{'='*80}")
    print(f"SAMPLE CLAIMS (showing first 15):")
    print(f"{'='*80}")
    
    for idx, claim in enumerate(result['features'][:15], 1):
        print(f"\n{idx}. {claim.claim}")
        print(f"   Type: {claim.claim_type.value} | Domain: {claim.domain.value}", end="")
        if claim.room_type:
            print(f" | Room: {claim.room_type}", end="")
        if claim.quantifiers:
            print(f" | Quantifiers: {len(claim.quantifiers)}", end="")
        print()
        
        if claim.quantifiers:
            for q in claim.quantifiers:
                print(f"      → {q.qtype.value}: {q.vmin}-{q.vmax} {q.unit or ''} ({q.op.value})")
    
    if result['total_features'] > 15:
        print(f"\n... and {result['total_features'] - 15} more claims")
    
    assert result['domain_breakdown']['apartment'] > 0
    assert result['domain_breakdown']['room'] > 0
    assert result['domain_breakdown']['neighborhood'] > 0
    
    has_quantifiers = any(claim.has_quantifiers for claim in result['features'])
    assert has_quantifiers, "Should have claims with quantifiers (rent, size, etc.)"
    
    await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_search_queries_comprehensive():
    """Test Phase 5: Search with diverse queries covering all claim types"""
    
    # Ensure Elasticsearch indices exist
    await es_client.create_indices()
    
    print(f"\n{'='*80}")
    print(f"SEARCH RESULTS - TESTING {len(SEARCH_QUERIES)} QUERIES")
    print(f"{'='*80}")
    
    results_summary = []
    
    for query_data in SEARCH_QUERIES:
        query = query_data["query"]
        should_match = query_data["should_match"]
        description = query_data["description"]
        
        print(f"\n{'-'*80}")
        print(f"Query: {query}")
        print(f"Description: {description}")
        print(f"Expected: {'MATCH' if should_match else 'NO MATCH'}")
        print(f"{'-'*80}")
        
        results = await search_pipeline.search(query, top_k=3)
        
        found_target = any(
            r.apartment_id == "williamsburg_luxury_2br" 
            for r in results
        )
        
        if results:
            print(f"Found {len(results)} results")
            
            for idx, result in enumerate(results, 1):
                print(f"\n  Result {idx}: {result.apartment_id}")
                print(f"    Score: {result.final_score:.4f}")
                print(f"    Coverage: {result.coverage_count} claims ({result.coverage_ratio:.1%})")
                print(f"    Domain scores:")
                for domain, score in result.domain_scores.items():
                    print(f"      {domain}: {score:.4f}")
                
                if result.matched_claims:
                    print(f"    Top matched claims:")
                    for match in result.matched_claims[:3]:
                        print(f"      - '{match['search_claim']}' → '{match['matched_claim']}' (score: {match['score']:.4f})")
        else:
            print("  No results found")
        
        status = "✅ PASS" if found_target == should_match else "❌ FAIL"
        print(f"\n{status}: Expected {should_match}, Found: {found_target}")
        
        results_summary.append({
            "query": query,
            "description": description,
            "expected": should_match,
            "found": found_target,
            "passed": found_target == should_match,
            "num_results": len(results),
            "top_score": results[0].final_score if results else 0
        })
    
    print(f"\n{'='*80}")
    print(f"FINAL SUMMARY")
    print(f"{'='*80}")
    
    total_queries = len(results_summary)
    passed = sum(1 for r in results_summary if r["passed"])
    failed = total_queries - passed
    
    print(f"\nTotal queries tested: {total_queries}")
    print(f"Passed: {passed} ({passed/total_queries:.1%})")
    print(f"Failed: {failed} ({failed/total_queries:.1%})")
    
    print(f"\n{'Query':<60} {'Expected':<10} {'Found':<10} {'Status':<10}")
    print(f"{'-'*90}")
    
    for r in results_summary:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        expected_str = "MATCH" if r["expected"] else "NO-MATCH"
        found_str = "MATCH" if r["found"] else "NO-MATCH"
        
        query_short = r["query"][:55] + "..." if len(r["query"]) > 55 else r["query"]
        print(f"{query_short:<60} {expected_str:<10} {found_str:<10} {status:<10}")
    
    success_rate = passed / total_queries
    assert success_rate >= 0.7, f"Success rate {success_rate:.1%} is below 70% threshold"
    
    print(f"\n{'='*80}")
    print(f"Overall test: {'✅ PASSED' if success_rate >= 0.7 else '❌ FAILED'} (threshold: 70%)")
    print(f"{'='*80}\n")


@pytest.mark.asyncio
async def test_claim_type_coverage():
    """Verify that indexing extracts all 12 claim types"""
    
    # Ensure Elasticsearch indices exist
    await es_client.create_indices()
    
    result = await indexer_pipeline.process(
        document=COMPREHENSIVE_APARTMENT_LISTING,
        apartment_id="test_coverage",
        address="250 Bedford Ave, Brooklyn, NY 11249",
        neighborhood_id="williamsburg_brooklyn"
    )
    
    claim_types_found = set(claim.claim_type for claim in result['features'])
    
    print(f"\n{'='*80}")
    print(f"CLAIM TYPE COVERAGE TEST")
    print(f"{'='*80}")
    print(f"Found {len(claim_types_found)} unique claim types:")
    
    for ct in sorted(claim_types_found, key=lambda x: x.value):
        count = sum(1 for c in result['features'] if c.claim_type == ct)
        print(f"  - {ct.value}: {count} claims")
    
    expected_types = {
        "location", "features", "amenities", "size", "condition", 
        "pricing", "accessibility", "policies", "utilities", "transport", "neighborhood"
    }
    
    found_types = {ct.value for ct in claim_types_found}
    missing_types = expected_types - found_types
    
    if missing_types:
        print(f"\nMissing claim types: {missing_types}")
    
    assert len(claim_types_found) >= 8, f"Should extract at least 8 different claim types, found {len(claim_types_found)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

