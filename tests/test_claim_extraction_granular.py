import pytest
import asyncio
from app.services.llm import llm_service
from app.models import ClaimType, Domain


CLAIM_TYPE_TEST_CASES = {
    ClaimType.LOCATION: [
        {
            "text": "Beautiful apartment in Williamsburg, Brooklyn",
            "expected_claims": ["located in Williamsburg", "located in Brooklyn"],
            "expected_domains": [Domain.NEIGHBORHOOD, Domain.NEIGHBORHOOD]
        },
        {
            "text": "Corner of Bedford Ave and North 7th Street",
            "expected_claims": ["corner of Bedford Ave and North 7th"],
            "expected_domains": [Domain.APARTMENT]
        },
        {
            "text": "Prime location near Central Park",
            "expected_claims": ["near Central Park"],
            "expected_domains": [Domain.NEIGHBORHOOD]
        }
    ],
    
    ClaimType.FEATURES: [
        {
            "text": "Stunning exposed brick walls and 12-foot high ceilings throughout",
            "expected_claims": ["exposed brick walls", "12-foot high ceilings"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT]
        },
        {
            "text": "Living room has beautiful bay windows with city views",
            "expected_claims": ["bay windows", "city views"],
            "expected_domains": [Domain.ROOM, Domain.ROOM]
        },
        {
            "text": "Hardwood floors and crown molding",
            "expected_claims": ["hardwood floors", "crown molding"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT]
        }
    ],
    
    ClaimType.AMENITIES: [
        {
            "text": "Full-service doorman building with roof deck and gym",
            "expected_claims": ["doorman building", "roof deck", "gym"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT, Domain.APARTMENT]
        },
        {
            "text": "In-unit washer and dryer",
            "expected_claims": ["washer and dryer in unit"],
            "expected_domains": [Domain.APARTMENT]
        },
        {
            "text": "Master bedroom with ensuite bathroom and walk-in closet",
            "expected_claims": ["ensuite bathroom", "walk-in closet"],
            "expected_domains": [Domain.ROOM, Domain.ROOM]
        }
    ],
    
    ClaimType.SIZE: [
        {
            "text": "Spacious 2 bedroom 2 bathroom apartment, approximately 1,100 square feet",
            "expected_claims": ["2 bedroom", "2 bathroom", "1,100 square feet"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT, Domain.APARTMENT]
        },
        {
            "text": "Large kitchen with 15m² of space",
            "expected_claims": ["large kitchen", "kitchen area 15m²"],
            "expected_domains": [Domain.ROOM, Domain.ROOM]
        },
        {
            "text": "Oversized living room",
            "expected_claims": ["oversized living room"],
            "expected_domains": [Domain.ROOM]
        }
    ],
    
    ClaimType.CONDITION: [
        {
            "text": "Recently renovated with modern fixtures",
            "expected_claims": ["recently renovated", "modern fixtures"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT]
        },
        {
            "text": "Gut-renovated kitchen with brand new appliances",
            "expected_claims": ["gut-renovated kitchen", "brand new appliances"],
            "expected_domains": [Domain.ROOM, Domain.ROOM]
        },
        {
            "text": "Move-in ready condition",
            "expected_claims": ["move-in ready"],
            "expected_domains": [Domain.APARTMENT]
        }
    ],
    
    ClaimType.PRICING: [
        {
            "text": "Monthly rent $4,200 with no broker fee",
            "expected_claims": ["monthly rent $4,200", "no broker fee"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT]
        },
        {
            "text": "Under $4,000 per month",
            "expected_claims": ["rent under $4,000"],
            "expected_domains": [Domain.APARTMENT]
        },
        {
            "text": "Affordable pricing at $3,500/month",
            "expected_claims": ["rent $3,500"],
            "expected_domains": [Domain.APARTMENT]
        }
    ],
    
    ClaimType.ACCESSIBILITY: [
        {
            "text": "Elevator building with ground floor accessibility",
            "expected_claims": ["elevator building", "ground floor"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT]
        },
        {
            "text": "Wheelchair accessible entrance",
            "expected_claims": ["wheelchair accessible"],
            "expected_domains": [Domain.APARTMENT]
        },
        {
            "text": "No walk-up, elevator access to all floors",
            "expected_claims": ["elevator access"],
            "expected_domains": [Domain.APARTMENT]
        }
    ],
    
    ClaimType.POLICIES: [
        {
            "text": "Pet-friendly building, cats and dogs welcome",
            "expected_claims": ["pets allowed", "cats allowed", "dogs allowed"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT, Domain.APARTMENT]
        },
        {
            "text": "No smoking building",
            "expected_claims": ["no smoking"],
            "expected_domains": [Domain.APARTMENT]
        }
    ],
    
    ClaimType.UTILITIES: [
        {
            "text": "Heat and hot water included in rent, central AC throughout",
            "expected_claims": ["heat included", "hot water included", "central AC"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT, Domain.APARTMENT]
        },
        {
            "text": "All utilities included except electricity",
            "expected_claims": ["utilities included"],
            "expected_domains": [Domain.APARTMENT]
        }
    ],
    
    ClaimType.TRANSPORT: [
        {
            "text": "5 minute walk to Bedford Ave L train station",
            "expected_claims": ["5 minute walk to L train"],
            "expected_domains": [Domain.NEIGHBORHOOD]
        },
        {
            "text": "Near subway, multiple train lines accessible",
            "expected_claims": ["near subway", "multiple train lines"],
            "expected_domains": [Domain.NEIGHBORHOOD, Domain.NEIGHBORHOOD]
        },
        {
            "text": "Parking spot included in rent",
            "expected_claims": ["parking spot included"],
            "expected_domains": [Domain.APARTMENT]
        }
    ],
    
    ClaimType.NEIGHBORHOOD: [
        {
            "text": "Quiet, tree-lined residential street in family-friendly area",
            "expected_claims": ["quiet neighborhood", "tree-lined street", "family-friendly area"],
            "expected_domains": [Domain.NEIGHBORHOOD, Domain.NEIGHBORHOOD, Domain.NEIGHBORHOOD]
        },
        {
            "text": "Trendy neighborhood with vibrant nightlife",
            "expected_claims": ["trendy neighborhood", "vibrant nightlife"],
            "expected_domains": [Domain.NEIGHBORHOOD, Domain.NEIGHBORHOOD]
        },
        {
            "text": "Safe area with excellent restaurants and coffee shops nearby",
            "expected_claims": ["safe neighborhood", "excellent restaurants nearby", "coffee shops nearby"],
            "expected_domains": [Domain.NEIGHBORHOOD, Domain.NEIGHBORHOOD, Domain.NEIGHBORHOOD]
        }
    ],
    
    ClaimType.RESTRICTIONS: [
        {
            "text": "12 month minimum lease required",
            "expected_claims": ["12 month minimum lease"],
            "expected_domains": [Domain.APARTMENT]
        },
        {
            "text": "Guarantor required, income must be 40x monthly rent",
            "expected_claims": ["guarantor required", "income 40x rent"],
            "expected_domains": [Domain.APARTMENT, Domain.APARTMENT]
        }
    ]
}


@pytest.mark.asyncio
async def test_claim_extraction_by_type():
    """Test claim extraction for each claim type with REAL LLM calls"""
    
    print(f"\n{'='*100}")
    print(f"GRANULAR CLAIM EXTRACTION TEST - REAL LLM CALLS")
    print(f"{'='*100}\n")
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for claim_type, test_cases in CLAIM_TYPE_TEST_CASES.items():
        print(f"\n{'-'*100}")
        print(f"Testing {claim_type.value.upper()} claims")
        print(f"{'-'*100}")
        
        for idx, test_case in enumerate(test_cases, 1):
            total_tests += 1
            text = test_case["text"]
            expected_claims = test_case["expected_claims"]
            expected_domains = test_case["expected_domains"]
            
            print(f"\n  Test {idx}: {text[:80]}...")
            
            try:
                claims = await llm_service.aggregate_claims(text)
                
                filtered_claims = [c for c in claims if c.claim_type == claim_type]
                
                print(f"    Expected claims: {len(expected_claims)}")
                print(f"    Extracted claims: {len(filtered_claims)}")
                
                if filtered_claims:
                    print(f"    Actual claims:")
                    for claim in filtered_claims:
                        print(f"      - '{claim.claim}' (domain: {claim.domain.value}, specific: {claim.is_specific}, quantifiers: {claim.has_quantifiers})")
                
                claim_texts = [c.claim for c in filtered_claims]
                domains = [c.domain for c in filtered_claims]
                
                found_count = 0
                for expected in expected_claims:
                    found = any(expected.lower() in claim.lower() or claim.lower() in expected.lower() for claim in claim_texts)
                    if found:
                        found_count += 1
                
                coverage = found_count / len(expected_claims) if expected_claims else 0
                
                if coverage >= 0.8:
                    print(f"    ✅ PASS - Coverage: {coverage:.0%} ({found_count}/{len(expected_claims)})")
                    passed_tests += 1
                elif coverage >= 0.5:
                    print(f"    ⚠️  PARTIAL - Coverage: {coverage:.0%} ({found_count}/{len(expected_claims)})")
                    passed_tests += 1
                else:
                    print(f"    ❌ FAIL - Coverage: {coverage:.0%} ({found_count}/{len(expected_claims)})")
                    failed_tests.append({
                        "claim_type": claim_type.value,
                        "text": text,
                        "expected": expected_claims,
                        "got": claim_texts,
                        "coverage": coverage
                    })
                
                domain_match = len(set(domains) & set(expected_domains)) > 0
                if not domain_match and filtered_claims:
                    print(f"    ⚠️  Domain mismatch: expected {[d.value for d in expected_domains]}, got {[d.value for d in domains]}")
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"    ❌ ERROR: {e}")
                failed_tests.append({
                    "claim_type": claim_type.value,
                    "text": text,
                    "error": str(e)
                })
    
    print(f"\n{'='*100}")
    print(f"FINAL RESULTS")
    print(f"{'='*100}")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests} ({passed_tests/total_tests:.1%})")
    print(f"Failed: {len(failed_tests)} ({len(failed_tests)/total_tests:.1%})")
    
    if failed_tests:
        print(f"\n{'='*100}")
        print(f"FAILED TESTS DETAIL")
        print(f"{'='*100}")
        for fail in failed_tests[:10]:
            print(f"\n  Claim type: {fail['claim_type']}")
            print(f"  Text: {fail['text']}")
            if 'error' in fail:
                print(f"  Error: {fail['error']}")
            else:
                print(f"  Expected: {fail['expected']}")
                print(f"  Got: {fail['got']}")
                print(f"  Coverage: {fail['coverage']:.1%}")
    
    success_rate = passed_tests / total_tests
    assert success_rate >= 0.7, f"Success rate {success_rate:.1%} below 70% threshold"


@pytest.mark.asyncio
async def test_domain_assignment_accuracy():
    """Test that LLM correctly assigns domains to claims"""
    
    test_cases = [
        {
            "text": "Quiet neighborhood near parks",
            "expected_domain": Domain.NEIGHBORHOOD,
            "claim_type": ClaimType.NEIGHBORHOOD
        },
        {
            "text": "Exposed brick walls",
            "expected_domain": Domain.APARTMENT,
            "claim_type": ClaimType.FEATURES
        },
        {
            "text": "Modern kitchen with stainless appliances",
            "expected_domain": Domain.ROOM,
            "claim_type": ClaimType.FEATURES
        },
        {
            "text": "5 minute walk to subway",
            "expected_domain": Domain.NEIGHBORHOOD,
            "claim_type": ClaimType.TRANSPORT
        },
        {
            "text": "Parking spot in building",
            "expected_domain": Domain.APARTMENT,
            "claim_type": ClaimType.AMENITIES
        },
        {
            "text": "Walk-in closet in master bedroom",
            "expected_domain": Domain.ROOM,
            "claim_type": ClaimType.FEATURES
        }
    ]
    
    print(f"\n{'='*100}")
    print(f"DOMAIN ASSIGNMENT ACCURACY TEST")
    print(f"{'='*100}\n")
    
    correct = 0
    total = len(test_cases)
    
    for test_case in test_cases:
        text = test_case["text"]
        expected_domain = test_case["expected_domain"]
        expected_type = test_case["claim_type"]
        
        print(f"  Testing: '{text}'")
        print(f"  Expected: {expected_domain.value}")
        
        claims = await llm_service.aggregate_claims(text)
        
        matching_claims = [c for c in claims if c.claim_type == expected_type]
        
        if matching_claims:
            actual_domain = matching_claims[0].domain
            print(f"  Got: {actual_domain.value}")
            
            if actual_domain == expected_domain:
                print(f"  ✅ CORRECT\n")
                correct += 1
            else:
                print(f"  ❌ WRONG\n")
        else:
            print(f"  ❌ NO MATCHING CLAIMS\n")
        
        await asyncio.sleep(0.5)
    
    accuracy = correct / total
    print(f"Domain assignment accuracy: {accuracy:.1%} ({correct}/{total})")
    
    assert accuracy >= 0.8, f"Domain assignment accuracy {accuracy:.1%} below 80% threshold"


@pytest.mark.asyncio
async def test_quantifier_detection_accuracy():
    """Test that LLM correctly identifies claims with quantifiers"""
    
    test_cases = [
        {"text": "2 bedroom apartment", "should_have_quantifiers": True},
        {"text": "Rent $4,200 per month", "should_have_quantifiers": True},
        {"text": "15m² kitchen", "should_have_quantifiers": True},
        {"text": "5 minute walk to subway", "should_have_quantifiers": True},
        {"text": "12 month minimum lease", "should_have_quantifiers": True},
        {"text": "Beautiful exposed brick", "should_have_quantifiers": False},
        {"text": "Pet-friendly building", "should_have_quantifiers": False},
        {"text": "Quiet neighborhood", "should_have_quantifiers": False},
    ]
    
    print(f"\n{'='*100}")
    print(f"QUANTIFIER DETECTION ACCURACY TEST")
    print(f"{'='*100}\n")
    
    correct = 0
    total = len(test_cases)
    
    for test_case in test_cases:
        text = test_case["text"]
        should_have = test_case["should_have_quantifiers"]
        
        print(f"  Testing: '{text}'")
        print(f"  Should have quantifiers: {should_have}")
        
        claims = await llm_service.aggregate_claims(text)
        
        if claims:
            has_quantifiers = claims[0].has_quantifiers
            print(f"  Detected: {has_quantifiers}")
            
            if has_quantifiers == should_have:
                print(f"  ✅ CORRECT\n")
                correct += 1
            else:
                print(f"  ❌ WRONG\n")
        else:
            print(f"  ❌ NO CLAIMS\n")
        
        await asyncio.sleep(0.5)
    
    accuracy = correct / total
    print(f"Quantifier detection accuracy: {accuracy:.1%} ({correct}/{total})")
    
    assert accuracy >= 0.8, f"Quantifier detection accuracy {accuracy:.1%} below 80% threshold"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

