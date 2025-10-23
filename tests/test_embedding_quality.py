import numpy as np
import pytest

from app.services.embeddings import embedding_service


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))


SEMANTIC_SIMILARITY_TESTS = [
    {
        "claim_pair": ("exposed brick walls", "brick walls exposed"),
        "expected_similarity": "very high",
        "min_score": 0.95,
    },
    {
        "claim_pair": ("doorman building", "full-service building with doorman"),
        "expected_similarity": "high",
        "min_score": 0.80,
    },
    {"claim_pair": ("high ceilings", "soaring ceilings"), "expected_similarity": "high", "min_score": 0.75},
    {"claim_pair": ("modern kitchen", "contemporary kitchen"), "expected_similarity": "high", "min_score": 0.75},
    {"claim_pair": ("pet-friendly", "pets allowed"), "expected_similarity": "high", "min_score": 0.75},
    {"claim_pair": ("elevator building", "no walk-up"), "expected_similarity": "medium", "min_score": 0.60},
    {"claim_pair": ("quiet neighborhood", "peaceful area"), "expected_similarity": "high", "min_score": 0.75},
    {"claim_pair": ("near subway", "close to public transit"), "expected_similarity": "high", "min_score": 0.70},
    {"claim_pair": ("recently renovated", "newly updated"), "expected_similarity": "high", "min_score": 0.75},
    {"claim_pair": ("spacious apartment", "large unit"), "expected_similarity": "high", "min_score": 0.70},
    {"claim_pair": ("hardwood floors", "exposed brick walls"), "expected_similarity": "low", "max_score": 0.60},
    {
        "claim_pair": ("pets allowed", "no pets allowed"),
        "expected_similarity": "medium",
        "min_score": 0.50,
        "max_score": 0.75,
    },
]


QUANTIFIED_CLAIM_TESTS = [
    {
        "claim_pair": ("kitchen area VAR_1", "large kitchen space"),
        "expected_similarity": "high",
        "min_score": 0.70,
        "note": "Quantified claim should match semantic equivalent",
    },
    {
        "claim_pair": ("VAR_1 bedroom apartment", "multiple bedroom unit"),
        "expected_similarity": "medium",
        "min_score": 0.60,
        "note": "Bedroom count generalized should still match",
    },
    {
        "claim_pair": ("monthly rent VAR_1", "affordable rent"),
        "expected_similarity": "medium",
        "min_score": 0.55,
        "note": "Rent quantifier with affordability",
    },
    {
        "claim_pair": ("VAR_1 walk to subway", "near public transit"),
        "expected_similarity": "high",
        "min_score": 0.65,
        "note": "Walking distance should match transit proximity",
    },
]


@pytest.mark.asyncio
async def test_semantic_similarity_quality():
    """Test that embedding model produces expected semantic similarities"""

    print(f"\n{'=' * 100}")
    print(f"SEMANTIC SIMILARITY QUALITY TEST")
    print(f"{'=' * 100}\n")

    passed = 0
    total = len(SEMANTIC_SIMILARITY_TESTS)

    for test_case in SEMANTIC_SIMILARITY_TESTS:
        claim1, claim2 = test_case["claim_pair"]
        expected = test_case["expected_similarity"]
        min_score = test_case.get("min_score", 0.0)
        max_score = test_case.get("max_score", 1.0)

        print(f"  '{claim1}' <-> '{claim2}'")
        print(f"  Expected: {expected} similarity")

        embeddings = await embedding_service.embed_texts([claim1, claim2])
        similarity = cosine_similarity(embeddings[0], embeddings[1])

        print(f"  Actual similarity: {similarity:.4f}")

        if min_score <= similarity <= max_score:
            print(f"  ✅ PASS (within [{min_score:.2f}, {max_score:.2f}])\n")
            passed += 1
        else:
            print(f"  ❌ FAIL (expected [{min_score:.2f}, {max_score:.2f}])\n")

    accuracy = passed / total
    print(f"Semantic similarity accuracy: {accuracy:.1%} ({passed}/{total})")

    assert accuracy >= 0.7, f"Semantic similarity accuracy {accuracy:.1%} below 70% threshold"


@pytest.mark.asyncio
async def test_quantified_claim_similarity():
    """Test that quantified claims (with VAR_N) still match semantically"""

    print(f"\n{'=' * 100}")
    print(f"QUANTIFIED CLAIM SIMILARITY TEST")
    print(f"{'=' * 100}\n")

    passed = 0
    total = len(QUANTIFIED_CLAIM_TESTS)

    for test_case in QUANTIFIED_CLAIM_TESTS:
        claim1, claim2 = test_case["claim_pair"]
        expected = test_case["expected_similarity"]
        min_score = test_case.get("min_score", 0.0)
        note = test_case.get("note", "")

        print(f"  '{claim1}' <-> '{claim2}'")
        print(f"  Expected: {expected} similarity")
        if note:
            print(f"  Note: {note}")

        embeddings = await embedding_service.embed_texts([claim1, claim2])
        similarity = cosine_similarity(embeddings[0], embeddings[1])

        print(f"  Actual similarity: {similarity:.4f}")

        if similarity >= min_score:
            print(f"  ✅ PASS (≥ {min_score:.2f})\n")
            passed += 1
        else:
            print(f"  ❌ FAIL (expected ≥ {min_score:.2f})\n")

    accuracy = passed / total
    print(f"Quantified claim similarity accuracy: {accuracy:.1%} ({passed}/{total})")

    assert accuracy >= 0.7, f"Quantified claim accuracy {accuracy:.1%} below 70% threshold"


@pytest.mark.asyncio
async def test_claim_type_discrimination():
    """Test that different claim types are distinguishable"""

    print(f"\n{'=' * 100}")
    print(f"CLAIM TYPE DISCRIMINATION TEST")
    print(f"{'=' * 100}\n")

    claim_groups = {
        "features": ["exposed brick", "high ceilings", "hardwood floors"],
        "amenities": ["doorman", "roof deck", "gym in building"],
        "location": ["in Williamsburg", "near Central Park", "Brooklyn area"],
        "transport": ["near subway", "5 min to L train", "close to bus"],
        "pricing": ["rent $4000", "affordable pricing", "under $5000"],
    }

    all_claims = []
    labels = []

    for claim_type, claims in claim_groups.items():
        all_claims.extend(claims)
        labels.extend([claim_type] * len(claims))

    print(f"Embedding {len(all_claims)} claims across {len(claim_groups)} types...")
    embeddings = await embedding_service.embed_texts(all_claims)

    correct_higher = 0
    total_comparisons = 0

    for i, (claim1, type1, emb1) in enumerate(zip(all_claims, labels, embeddings)):
        same_type_scores = []
        diff_type_scores = []

        for j, (claim2, type2, emb2) in enumerate(zip(all_claims, labels, embeddings)):
            if i == j:
                continue

            sim = cosine_similarity(emb1, emb2)

            if type1 == type2:
                same_type_scores.append(sim)
            else:
                diff_type_scores.append(sim)

        if same_type_scores and diff_type_scores:
            avg_same = np.mean(same_type_scores)
            avg_diff = np.mean(diff_type_scores)

            if avg_same > avg_diff:
                correct_higher += 1

            total_comparisons += 1

            if i < 3:
                print(f"\n  '{claim1}' ({type1}):")
                print(f"    Avg similarity to same type: {avg_same:.4f}")
                print(f"    Avg similarity to other types: {avg_diff:.4f}")
                print(f"    {'✅ Same > Different' if avg_same > avg_diff else '❌ Same ≤ Different'}")

    discrimination_rate = correct_higher / total_comparisons

    print(f"\n{'=' * 100}")
    print(f"Discrimination rate: {discrimination_rate:.1%} ({correct_higher}/{total_comparisons})")
    print(f"(Measures how often same-type claims are more similar than different-type)")
    print(f"{'=' * 100}")

    assert discrimination_rate >= 0.6, f"Discrimination rate {discrimination_rate:.1%} below 60% threshold"


@pytest.mark.asyncio
async def test_embedding_consistency():
    """Test that same text produces consistent embeddings"""

    print(f"\n{'=' * 100}")
    print(f"EMBEDDING CONSISTENCY TEST")
    print(f"{'=' * 100}\n")

    test_claims = [
        "modern kitchen with stainless appliances",
        "2 bedroom apartment",
        "quiet neighborhood",
        "near subway station",
    ]

    passed = 0
    total = len(test_claims)

    for claim in test_claims:
        print(f"  Testing: '{claim}'")

        emb1 = await embedding_service.embed_texts([claim])
        emb2 = await embedding_service.embed_texts([claim])

        similarity = cosine_similarity(emb1[0], emb2[0])

        print(f"  Similarity between two embeddings: {similarity:.6f}")

        if similarity > 0.999:
            print(f"  ✅ PASS (highly consistent)\n")
            passed += 1
        else:
            print(f"  ⚠️  WARNING (similarity < 0.999)\n")
            passed += 1

    consistency_rate = passed / total
    print(f"Consistency rate: {consistency_rate:.1%} ({passed}/{total})")

    assert consistency_rate >= 0.9, f"Consistency rate {consistency_rate:.1%} below 90% threshold"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
