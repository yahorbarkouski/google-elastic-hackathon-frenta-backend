# Apartment Semantic Search (for google & elastic hackathon)

Semantic search for apartments using hierarchical domain search across neighborhoods, apartments, and rooms.

## How it works

1. **Claim extraction**: Gemini breaks listings into atomic facts with domain labels (neighborhood/apartment/room)
2. **Multi-modal indexing**: Extract claims from text AND images, deduplicate semantically
3. **Embedding**: Generate 768-dim vectors for semantic matching (Gemini embedding-001)
4. **Hierarchical search**: Query 3 Elasticsearch indices in parallel via `_msearch`, filter by domain hierarchy
5. **Location grounding**: Verify location claims with Google Maps (distances, coordinates)
6. **Coverage ranking**: Apartments matching more requirements rank higher

**Architecture**: 3-domain hierarchy (Neighborhood → Apartment → Room), 12 claim types, quantifier separation for numeric filtering.

## Stack

- Gemini 2.5 Pro + Flash (claim extraction, quantifier parsing)
- Gemini embedding-001 (768-dim embeddings)
- Gemini Vision (image descriptions)
- Elasticsearch 8.11 (kNN with HNSW)
- Google Maps Grounding API
- FastAPI + uvicorn

## Setup

Install dependencies:
```bash
uv pip install -e .
```

Configure environment:
```bash
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY
```

Start Elasticsearch:
```bash
make docker-up
```

## Run

```bash
make run
```

Server runs on http://localhost:8000

## API

- `POST /api/index` - Index apartment (text + images)
- `POST /api/search` - Semantic search
- `GET /api/apartments` - List all apartments
- `GET /api/apartments/{id}` - Get apartment details
- `DELETE /api/apartments/{id}` - Delete apartment

See `FRONTEND_INTEGRATION_GUIDE.md` for complete API docs.

## Tests

All tests use **real API calls** (no mocks) to validate LLM behavior:

```bash
make test-comprehensive    # End-to-end indexing + 14 search queries
make test-granular         # Claim extraction across 12 types
make test-embeddings       # Semantic similarity quality
make test-all              # Everything
```

## Architecture docs

- `CLAIM_BASED_SEARCH_ANALYSIS.md` - Complete architecture breakdown
- `FRONTEND_INTEGRATION_GUIDE.md` - API reference for frontend
- `GOOGLE_MAPS_GROUNDING.md` - Location verification details

