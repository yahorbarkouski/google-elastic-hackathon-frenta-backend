import asyncio
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, "/Users/yahorbarkouski/thenetwork/apartment-search")

from app.models import Claim, ClaimType, Domain
from app.services.geocoding import geocoding_service
from app.services.grounding import grounding_service

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


async def test_geocoding():
    """Test geocoding service."""
    print("\n" + "="*80)
    print("TEST 1: Geocoding Service")
    print("="*80)
    
    address = "123 Bedford Ave, Brooklyn, NY 11249"
    coords = await geocoding_service.geocode_address(address)
    
    print(f"\nAddress: {address}")
    print(f"Coordinates: {coords}")
    
    assert coords is not None, "Geocoding failed"
    assert "lat" in coords and "lng" in coords, "Missing lat/lng"
    assert 40.5 < coords["lat"] < 41.0, f"Latitude out of range: {coords['lat']}"
    assert -74.5 < coords["lng"] < -73.5, f"Longitude out of range: {coords['lng']}"
    
    print("✅ Geocoding test PASSED")
    return coords


async def test_grounding():
    """Test grounding service with real Google Maps API."""
    print("\n" + "="*80)
    print("TEST 2: Grounding Service")
    print("="*80)
    
    williamsburg_coords = await geocoding_service.geocode_address("Bedford Ave, Brooklyn, NY")
    
    test_claims = [
        Claim(
            claim="near Bedford Ave L train station",
            claim_type=ClaimType.TRANSPORT,
            domain=Domain.NEIGHBORHOOD,
            is_specific=True,
            has_quantifiers=False
        ),
        Claim(
            claim="close to coffee shops",
            claim_type=ClaimType.AMENITIES,
            domain=Domain.NEIGHBORHOOD,
            is_specific=False,
            has_quantifiers=False
        )
    ]
    
    print(f"\nClaims to ground:")
    for i, claim in enumerate(test_claims, 1):
        print(f"  {i}. {claim.claim} (type: {claim.claim_type.value})")
    
    print(f"\nLocation: {williamsburg_coords}")
    print("\nCalling Google Maps Grounding API...")
    
    result = await grounding_service.ground_claims_batch(
        claims=test_claims,
        location=williamsburg_coords,
        enable_widget=True
    )
    
    print(f"\n📊 Results:")
    print(f"  Verified claims: {len(result.verified_claims)}")
    print(f"  Grounded sources: {len(result.grounded_sources)}")
    print(f"  Widget tokens: {len(result.widget_tokens)}")
    
    for i, vclaim in enumerate(result.verified_claims, 1):
        print(f"\n✅ Verified Claim {i}:")
        print(f"     Text: {vclaim.claim}")
        print(f"     From: {vclaim.from_claim}")
        print(f"     Kind: {vclaim.kind.value}")
        if vclaim.grounding_metadata:
            meta = vclaim.grounding_metadata
            print(f"     Verified: {meta.verified}")
            print(f"     Confidence: {meta.confidence}")
            if meta.place_name:
                print(f"     Place: {meta.place_name}")
            if meta.exact_distance_meters:
                print(f"     Distance: {meta.exact_distance_meters}m")
            if meta.coordinates:
                print(f"     Coords: {meta.coordinates}")
    
    for i, source in enumerate(result.grounded_sources, 1):
        print(f"\n🗺️  Source {i}:")
        print(f"     Title: {source['title']}")
        print(f"     URI: {source['uri'][:80]}...")
    
    assert len(result.verified_claims) > 0, "No verified claims returned"
    print("\n✅ Grounding test PASSED")


async def test_decision_logic():
    """Test grounding decision logic."""
    print("\n" + "="*80)
    print("TEST 3: Grounding Decision Logic")
    print("="*80)
    
    should_ground = [
        Claim(claim="near subway", claim_type=ClaimType.TRANSPORT, domain=Domain.NEIGHBORHOOD),
        Claim(claim="close to parks", claim_type=ClaimType.AMENITIES, domain=Domain.NEIGHBORHOOD),
        Claim(claim="in Williamsburg", claim_type=ClaimType.LOCATION, domain=Domain.NEIGHBORHOOD, is_specific=True),
        Claim(claim="safe neighborhood", claim_type=ClaimType.NEIGHBORHOOD, domain=Domain.NEIGHBORHOOD),
    ]
    
    should_not_ground = [
        Claim(claim="high ceilings", claim_type=ClaimType.FEATURES, domain=Domain.APARTMENT),
        Claim(claim="large kitchen", claim_type=ClaimType.SIZE, domain=Domain.ROOM, room_type="kitchen"),
        Claim(claim="pets allowed", claim_type=ClaimType.POLICIES, domain=Domain.APARTMENT),
    ]
    
    print("\nShould ground:")
    for claim in should_ground:
        result = grounding_service.should_ground_claim(claim)
        print(f"  ✓ {claim.claim}: {result}")
        assert result, f"Should ground '{claim.claim}' but returned False"
    
    print("\nShould NOT ground:")
    for claim in should_not_ground:
        result = grounding_service.should_ground_claim(claim)
        print(f"  ✗ {claim.claim}: {result}")
        assert not result, f"Should not ground '{claim.claim}' but returned True"
    
    print("\n✅ Decision logic test PASSED")


async def main():
    """Run all grounding tests."""
    print("\n🧪 GOOGLE MAPS GROUNDING TESTS")
    print("="*80)
    
    try:
        await test_geocoding()
        await test_decision_logic()
        await test_grounding()
        
        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED!")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

