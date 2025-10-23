# Apartment Semantic Search

Recursive claim-based semantic search for apartments with hierarchical domain filtering.

## Architecture

- **3-domain hierarchy**: Neighborhood → Apartment → Room
- **12 claim types**: location, features, amenities, size, condition, pricing, accessibility, policies, utilities, transport, neighborhood, restrictions
- **Recursive parallel search**: Query all domains via Elasticsearch `_msearch`, filter by hierarchy, merge scores
- **Quantifier separation**: Numeric constraints extracted and filtered separately from semantic matching
- **Coverage-first ranking**: Prioritize apartments satisfying more query aspects

## Stack

- Gemini 2.5 Pro (claim aggregation, quantifier extraction)
- Gemini embedding-001 (768-dim embeddings)
- Elasticsearch 8.11 (kNN with HNSW)
- **Real API calls in tests** - no mocks, actual LLM/embedding evaluation

## Setup

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY

make docker-up
make install
```

## Run Tests

### Comprehensive End-to-End Test
```bash
make test-comprehensive
```

This will:
1. Index a comprehensive apartment listing with 40+ claims
2. Run 14 diverse search queries covering all claim types
3. Validate matching precision and recall

### Granular Claim Extraction Tests (REAL LLM CALLS)
```bash
make test-granular
```

Tests claim extraction for each of the 12 claim types with real Gemini API calls:
- Tests 30+ different apartment descriptions
- Validates claim type accuracy
- Tests domain assignment (neighborhood/apartment/room)
- Tests quantifier detection accuracy
- **No mocks** - helps tune prompts and thresholds based on actual LLM behavior

### Embedding Quality Tests (REAL API CALLS)
```bash
make test-embeddings
```

Tests semantic similarity quality with real embeddings:
- Validates that synonyms have high similarity ("doorman" vs "full-service building")
- Tests quantified claims (VAR_1 replacement) maintain semantic meaning
- Tests claim type discrimination (features vs amenities vs location)
- Tests embedding consistency

### Run All Tests
```bash
make test-all
```

## Run Server

```bash
make run
```

## Implementation Progress

- [x] Phase 1: Claim aggregation (12 types, 3 domains)
- [x] Phase 2: Quantifier extraction
- [x] Phase 3: Embedding generation
- [x] Phase 4: Elasticsearch indexing (3 indices)
- [x] Phase 5: Recursive domain search
- [x] Phase 6: Score merging & ranking
- [ ] Phase 7: Claim expansion (base → derived)
- [ ] Phase 8: Google Maps grounding (selective)

## Test Coverage

The comprehensive test indexes one apartment with:
- 2 bedrooms, 2 bathrooms
- Modern kitchen with quantified size
- Located in Williamsburg, Brooklyn
- Multiple amenities, features, policies
- Transport and neighborhood claims

Then runs 14 queries testing:
- ✅ Positive matches (should find apartment)
- ❌ Negative matches (should NOT find - wrong location, size, policies)
- All 12 claim types
- Quantifier filtering
- Domain hierarchy filtering

