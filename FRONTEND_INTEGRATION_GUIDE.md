# Apartment Search - Frontend Integration Guide

## Overview

The Apartment Search backend provides a **semantic search engine** for apartment listings that understands natural language queries. Unlike keyword search, it understands meaning, relationships, and context.

### Key Capabilities

- **Semantic Understanding** - "spacious" matches "large rooms", "open concept", etc.
- **Multi-Domain Search** - Searches rooms, apartments, and neighborhoods simultaneously
- **Location Verification** - Validates claims like "near subway" using Google Maps
- **Multi-Modal Indexing** - Process text descriptions and images together
- **Claim Attribution** - Track which claims came from text vs images

### Technology Stack

- **Vector Search**: Elasticsearch with kNN
- **Embeddings**: Google Gemini (768 dimensions)
- **Vision**: Gemini Vision for image analysis
- **Maps**: Google Maps Grounding for location verification

---

## Core Concepts

### 1. Claim-Based Indexing

The system breaks down listings into **atomic claims** instead of storing raw text.

**Example Input:**
```
"Modern 2BR in Williamsburg. Hardwood floors, renovated kitchen. 
Pet-friendly building. Close to L train."
```

**Indexed as Claims:**
```json
[
  {"claim": "modern apartment", "domain": "apartment", "type": "condition"},
  {"claim": "2 bedroom", "domain": "apartment", "type": "size"},
  {"claim": "located in Williamsburg", "domain": "neighborhood", "type": "location"},
  {"claim": "hardwood floors", "domain": "apartment", "type": "features"},
  {"claim": "renovated kitchen", "domain": "room", "type": "condition"},
  {"claim": "pet-friendly", "domain": "apartment", "type": "policies"},
  {"claim": "close to L train", "domain": "neighborhood", "type": "transport"}
]
```

**Why?** Enables precise matching, better ranking, and faceted filtering.

### 2. Three-Domain Model

| Domain | Description | Examples |
|--------|-------------|----------|
| **Neighborhood** | Area characteristics, location, transport | "trendy area", "near subway", "in Brooklyn" |
| **Apartment** | Building/unit features, policies | "doorman", "renovated", "pets allowed", "2BR" |
| **Room** | Specific room features | "spacious kitchen", "walk-in closet" |

Different domains have different importance weights and are searched separately.

### 3. Claim Kinds

| Kind | Description | Weight Multiplier | Origin |
|------|-------------|-------------------|--------|
| `base` | Directly from listing | 1.0 | LLM extraction |
| `derived` | Semantic expansion | 0.75 | "spacious" → "large", "roomy" |
| `anti` | Negation claims | 0.75 | "pet-friendly" → "no pets allowed" |
| `verified` | Google Maps confirmed | 1.1 | Maps API verification |

### 4. Google Maps Grounding

Location-based claims can be verified with real Google Maps data.

**Unverified Claim:** "close to L train"  
**After Grounding:**
- ✅ Verified: "529m to Bedford Ave L station"
- 📍 Coordinates: `{lat: 40.7149, lng: -73.9566}`
- 🗺️ Widget token for interactive map
- ⭐ Place details (name, rating, photos)

**Benefits:**
- **Trust**: Real data, not just text
- **Precision**: Exact distances vs vague descriptions
- **UX**: Interactive maps users can explore

### 5. Multi-Modal Indexing

Apartments can be indexed with text descriptions AND images.

**Flow:**
1. Submit description + image URLs
2. Gemini Vision describes each image
3. Extract claims from all sources
4. Deduplicate similar claims
5. Index with source attribution

**Source Tracking:**
```json
{
  "claim": "white marble countertops",
  "domain": "room",
  "source": {
    "type": "image",
    "image_url": "https://...",
    "image_index": 0
  }
}
```

---

## API Reference

**Base URL:** `http://localhost:8000`

### Health Check

```http
GET /health
```

Returns server health status.

**Response:**
```json
{
  "status": "healthy"
}
```

---

### Setup Indices

```http
POST /api/setup
```

Initialize Elasticsearch indices. Run once on deployment.

**Response:**
```json
{
  "status": "success",
  "message": "Elasticsearch indices created successfully",
  "indices": {
    "rooms": "rooms",
    "apartments": "apartments",
    "neighborhoods": "neighborhoods"
  }
}
```

---

### Index Apartment

```http
POST /api/index
Content-Type: application/json
```

Add or update an apartment listing with optional images.

**Request Body:**
```json
{
  "apartment_id": "apt_12345",
  "document": "Modern 2BR with hardwood floors...",
  "address": "123 Bedford Ave, Brooklyn, NY 11211",
  "neighborhood_id": "williamsburg",
  "image_urls": [
    "https://example.com/kitchen.jpg",
    "https://example.com/living-room.jpg"
  ]
}
```

**Parameters:**
- `apartment_id` (required) - Unique identifier
- `document` (optional) - Text description
- `address` (optional) - Full address for geocoding/grounding
- `neighborhood_id` (optional) - Neighborhood identifier
- `image_urls` (optional) - Array of publicly accessible image URLs

**Constraints:**
- At least one of `document` or `image_urls` required
- Supported image formats: JPG, PNG, WebP, GIF
- Recommended image size: 800px+ width, <5MB

**Response:**
```json
{
  "status": "success",
  "apartment_id": "apt_12345",
  "total_features": 143,
  "domain_breakdown": {
    "neighborhood": 15,
    "apartment": 36,
    "room": 92
  }
}
```

**Performance Notes:**
- Indexing takes 30-60 seconds
- LLM processing is the bottleneck
- Images processed in parallel
- Re-indexing same ID replaces all data

---

### Batch Index

```http
POST /api/index/batch
Content-Type: application/json
```

Index multiple apartments in parallel.

**Request Body:**
```json
{
  "apartments": [
    {
      "apartment_id": "apt_001",
      "document": "...",
      "address": "..."
    },
    {
      "apartment_id": "apt_002",
      "document": "...",
      "image_urls": ["..."]
    }
  ]
}
```

**Response:**
```json
{
  "status": "complete",
  "total": 2,
  "successful": 2,
  "failed": 0,
  "results": [...],
  "errors": []
}
```

---

### Search Apartments

```http
POST /api/search
Content-Type: application/json
```

Semantic search with natural language queries.

**Request Body:**
```json
{
  "query": "2BR with hardwood floors near subway in Brooklyn",
  "top_k": 10,
  "user_location": {
    "lat": 40.7128,
    "lng": -73.9559
  }
}
```

**Parameters:**
- `query` (required) - Natural language search query
- `top_k` (optional, default: 10) - Number of results
- `user_location` (optional) - User coordinates for location-aware grounding

**Response:**
```json
{
  "results": [
    {
      "apartment_id": "apt_12345",
      "final_score": 0.89,
      "coverage_count": 8,
      "coverage_ratio": 0.8,
      "weight_coverage": 0.85,
      "matched_claims": [
        {
          "query_claim": "2 bedroom",
          "matched_claim": "2 bedroom apartment",
          "similarity": 0.95,
          "domain": "apartment",
          "kind": "base"
        }
      ],
      "domain_scores": {
        "apartment": 0.92,
        "neighborhood": 0.85,
        "room": 0.88
      },
      "geo_proximity": {
        "distance": "450m",
        "location": "Bedford Ave L Station"
      },
      "grounded_sources": [
        {
          "title": "Bedford Ave Station",
          "uri": "https://maps.google.com/?cid=...",
          "rating": null,
          "category": "Subway Station"
        }
      ],
      "map_widget_tokens": ["ChIJwxyz..."]
    }
  ]
}
```

**Score Interpretation:**
- `final_score` - Overall match quality (0-1)
  - 0.8+ = Excellent match
  - 0.6-0.8 = Good match
  - 0.4-0.6 = Partial match
  - <0.4 = Weak match
- `coverage_count` - Number of query claims matched
- `coverage_ratio` - Percentage of query claims matched
- `weight_coverage` - Weighted coverage (accounts for claim importance)
- `domain_scores` - Match quality per domain

**Map Widget Tokens:**
- Tokens for rendering interactive Google Maps
- Show verified places (restaurants, stations, etc.)
- User can explore neighborhood visually
- Require Google Maps JavaScript API to render

---

### List Apartments

```http
GET /api/apartments?page=1&page_size=20&has_images=false
```

Get all indexed apartments with pagination (for database views).

**Query Parameters:**
- `page` (optional, default: 1) - Page number
- `page_size` (optional, default: 20, max: 100) - Items per page
- `has_images` (optional, default: false) - Filter apartments with images

**Response:**
```json
{
  "apartments": [
    {
      "apartment_id": "apt_12345",
      "address": "123 Bedford Ave, Brooklyn, NY 11211",
      "neighborhood_id": "williamsburg",
      "location": {
        "lat": 40.7195322,
        "lon": -73.9556267
      },
      "image_urls": [
        "https://example.com/image1.jpg",
        "https://example.com/image2.jpg"
      ],
      "claim_count": 143
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 47,
    "total_pages": 3
  }
}
```

**Use Cases:**
- Build admin/database view
- Show apartment inventory
- Display image galleries
- Export/analytics

---

### Get Apartment Details

```http
GET /api/apartments/{apartment_id}
```

Retrieve complete details for a specific apartment including all claims.

**Response:**
```json
{
  "apartment_id": "apt_12345",
  "address": "123 Bedford Ave, Brooklyn, NY 11211",
  "neighborhood_id": "williamsburg",
  "location": {
    "lat": 40.7195322,
    "lon": -73.9556267
  },
  "image_urls": [
    "https://example.com/kitchen.jpg",
    "https://example.com/living.jpg"
  ],
  "total_claims": 143,
  "claims": [
    {
      "claim": "modern apartment",
      "claim_type": "condition",
      "kind": "base",
      "domain": "apartment",
      "source": {"type": "text"},
      "is_specific": false,
      "grounding_metadata": null
    },
    {
      "claim": "white marble countertops",
      "claim_type": "features",
      "kind": "base",
      "domain": "room",
      "source": {
        "type": "image",
        "image_url": "https://example.com/kitchen.jpg",
        "image_index": 0
      }
    },
    {
      "claim": "529m to Bedford Ave L station",
      "claim_type": "transport",
      "kind": "verified",
      "domain": "neighborhood",
      "grounding_metadata": {
        "verified": true,
        "source": "google_maps",
        "place_id": "ChIJ...",
        "coordinates": {"lat": 40.7149, "lon": -73.9566},
        "exact_distance_meters": 529,
        "walking_time_minutes": 2.8,
        "confidence": 1.0
      }
    }
  ],
  "summary": {
    "base_claims": 12,
    "verified_claims": 1,
    "derived_claims": 130
  }
}
```

**Use Cases:**
- Show detailed apartment view
- Display "verified with Google Maps" badges
- Debug indexing results
- Explain search rankings

---

### Delete Apartment

```http
DELETE /api/apartments/{apartment_id}
```

Remove apartment and all associated claims from all indices.

**Response:**
```json
{
  "apartment_id": "apt_12345",
  "status": "deleted",
  "deleted_counts": {
    "apartments": 143,
    "neighborhoods": 15,
    "rooms": 92
  },
  "total_deleted": 250
}
```

---

## Data Models

### Claim Object

```json
{
  "claim": "hardwood floors",
  "claim_type": "features",
  "domain": "apartment",
  "room_type": null,
  "kind": "base",
  "is_specific": false,
  "has_quantifiers": false,
  "from_claim": null,
  "weight": 0.75,
  "negation": false,
  "source": {
    "type": "text"
  },
  "grounding_metadata": null,
  "quantifiers": []
}
```

**Fields:**
- `claim` - The claim text
- `claim_type` - Category (see below)
- `domain` - "neighborhood" | "apartment" | "room"
- `room_type` - Only for room domain (e.g., "kitchen", "bedroom")
- `kind` - "base" | "derived" | "anti" | "verified"
- `is_specific` - Contains named entities (locations, brands)
- `has_quantifiers` - Contains numbers/measurements
- `from_claim` - Parent claim for derived/anti claims
- `weight` - Importance multiplier (0-1)
- `negation` - Is this a negative claim?
- `source` - Where claim originated
- `grounding_metadata` - Google Maps verification data
- `quantifiers` - Extracted numbers/measurements

**Claim Types:**
- `location` - Geographic locations, addresses
- `features` - Physical characteristics
- `amenities` - Services, facilities
- `size` - Dimensions, room counts
- `condition` - Maintenance state, age
- `pricing` - Rent, fees
- `accessibility` - Physical access features
- `policies` - Rules, restrictions
- `utilities` - Included services
- `transport` - Commute, transit access
- `neighborhood` - Area vibe, character
- `restrictions` - Lease terms

### Claim Source

```json
{
  "type": "image",
  "image_url": "https://example.com/kitchen.jpg",
  "image_index": 0
}
```

**Types:**
- `text` - From text description
- `image` - From image analysis

### Grounding Metadata

```json
{
  "verified": true,
  "source": "google_maps",
  "place_id": "ChIJ...",
  "place_name": "Bedford Ave Station",
  "place_uri": "https://maps.google.com/?cid=...",
  "coordinates": {
    "lat": 40.7149,
    "lon": -73.9566
  },
  "exact_distance_meters": 529,
  "walking_time_minutes": 2.8,
  "confidence": 1.0,
  "verified_at": "2025-10-21T10:30:00Z",
  "supporting_evidence": "L train station on Bedford Avenue"
}
```

Present when claim is verified via Google Maps.

### Search Result

```json
{
  "apartment_id": "apt_12345",
  "final_score": 0.89,
  "coverage_count": 8,
  "coverage_ratio": 0.8,
  "weight_coverage": 0.85,
  "matched_claims": [...],
  "domain_scores": {
    "apartment": 0.92,
    "neighborhood": 0.85,
    "room": 0.88
  },
  "geo_proximity": {
    "distance": "450m",
    "location": "Bedford Ave L Station"
  },
  "grounded_sources": [...],
  "map_widget_tokens": [...]
}
```

### Matched Claim

```json
{
  "query_claim": "2 bedroom",
  "matched_claim": "2 bedroom apartment",
  "similarity": 0.95,
  "domain": "apartment",
  "kind": "base"
}
```

Shows how query requirements matched against indexed claims.

### Grounded Source

```json
{
  "title": "Bedford Ave Station",
  "uri": "https://maps.google.com/?cid=4182415126097975725",
  "rating": 4.3,
  "category": "Subway Station"
}
```

Places from Google Maps used to verify claims.

---

## Google Maps Widgets

### What Are They?

Map widget tokens enable rendering **interactive Google Maps** showing verified locations. Instead of just text ("near coffee shops"), users see an actual map with markers they can explore.

### How to Get Them

Widget tokens are automatically included in search results when:
1. Query contains location-based claims
2. User location is provided
3. Google Maps verification succeeds

### Token Format

```json
{
  "map_widget_tokens": ["ChIJwxyz123..."]
}
```

Each token is a string that encodes:
- Map view (center, zoom)
- Place markers
- Place details (names, ratings, photos)

### Rendering Requirements

To display widgets, you need:
1. Google Maps JavaScript API loaded
2. Valid Google Maps API key
3. The `<gmp-place-contextual>` web component
4. Proper attribution to Google Maps

### Example Rendering

```html
<!-- Include Google Maps library -->
<script src="https://maps.googleapis.com/maps/api/js?key=YOUR_KEY&libraries=places"></script>

<!-- Render widget -->
<gmp-place-contextual context-token="ChIJwxyz123...">
</gmp-place-contextual>

<!-- Required attribution -->
<a href="https://maps.google.com" translate="no">Google Maps</a>
```

### Attribution Requirements

Per Google's terms, you must:
- Display "Google Maps" text (no modification)
- Use Roboto font or sans-serif fallback
- Font size: 12-16px
- Color: #1F1F1F (black) or #5E5E5E (gray)
- Add `translate="no"` attribute
- Link to maps.google.com

### Token Lifecycle

- **Valid for:** ~30 days
- **Caching:** Not recommended (ephemeral)
- **Cost:** Included in grounding call (no extra charge)

---

## Best Practices

### Query Construction

**Good Queries:**
- Natural language: "2BR with hardwood floors near subway in Brooklyn"
- Include details: "Modern studio with in-unit laundry, pet-friendly"
- Be specific: "Apartment near good coffee shops and parks under $3000"

**Avoid:**
- Too vague: "apt"
- Abbreviations: "2br hwf subway bk"
- All caps: "MODERN LUXURY PENTHOUSE"

### Handling Long Operations

**Indexing:**
- Takes 30-60 seconds
- Show progress indicator
- Don't block UI
- Provide cancel option

**Searching:**
- Usually <2 seconds
- Consider debouncing (wait 300ms after typing)
- Show loading state immediately
- Cache repeated queries

### Image URLs

**Requirements:**
- Must be publicly accessible (not localhost)
- Supported: JPG, PNG, WebP, GIF
- Recommended: 800px+ width
- File size: <5MB per image

**Tips:**
- Use CDN for better performance
- Consider image optimization
- Provide fallback for failed loads

### Error Handling

**Common Errors:**

| Status | Meaning | Action |
|--------|---------|--------|
| 400 | Invalid request | Check parameters |
| 404 | Apartment not found | Verify ID exists |
| 500 | Server error | Retry or contact support |

**Indexing Failures:**
- Image fetch errors (check URLs)
- Vision API limits (wait and retry)
- Invalid address (geocoding fails)

**Search Failures:**
- No results (query too specific)
- Timeout (reduce top_k)
- Invalid location (check coordinates)

### Performance

**Search Optimization:**
- Cache results for identical queries
- Debounce search input
- Limit top_k to reasonable values (10-20)
- Consider pagination for large result sets

**Display Optimization:**
- Lazy load images
- Virtualize long lists
- Show results progressively
- Defer widget rendering until visible

### Security

**API Access:**
- Use HTTPS in production
- Implement rate limiting
- Validate all inputs
- Sanitize displayed content

**Google Maps:**
- Restrict API key to your domain
- Monitor usage/costs
- Follow Google's terms of service

---

## Common Scenarios

### Scenario 1: Basic Search

1. User enters query: "2BR near subway"
2. Call `POST /api/search` with query
3. Display results with scores
4. Show matched claims to explain ranking
5. Highlight verified claims with badges

### Scenario 2: Location-Aware Search

1. Get user's location via browser geolocation
2. Include in search request as `user_location`
3. Backend grounds claims relative to user
4. Results include geo-filtered apartments
5. Display distances from user location

### Scenario 3: Indexing with Images

1. User provides description + image URLs
2. Call `POST /api/index` with both
3. Show progress (30-60s wait)
4. Backend analyzes images in parallel
5. Display indexed features grouped by source
6. Show which claims came from which image

### Scenario 4: Admin/Database View

1. Call `GET /api/apartments` with pagination
2. Display grid/list of all apartments
3. Show thumbnail gallery for image_urls
4. Filter by `has_images=true` if needed
5. Implement pagination controls
6. Link to detail view for each apartment

### Scenario 5: Apartment Detail Page

1. Get apartment_id from URL/route
2. Call `GET /api/apartments/{id}`
3. Display full details
4. Group claims by domain
5. Highlight verified claims
6. Show image gallery
7. Display location on map

---

## Troubleshooting

### No Search Results

**Possible Causes:**
- No apartments indexed
- Query too specific
- Elasticsearch connection issue

**Solutions:**
1. Check if apartments exist: `GET /api/apartments`
2. Try broader query
3. Check backend logs

### Slow Indexing

**Expected:** 30-60s for text + 2 images

**If Slower:**
- Check backend logs for errors
- Verify image URLs are accessible
- Check Gemini API rate limits
- Network latency fetching images

### Widgets Not Showing

**Checklist:**
- ✅ Google Maps JS library loaded?
- ✅ Valid API key?
- ✅ Token exists in response?
- ✅ Correct web component used?
- ✅ Attribution displayed?

### Images Not Analyzed

**Check:**
- URLs publicly accessible?
- Valid image format?
- Not timing out (large files)?
- Backend logs for vision API errors

---

## Quick Reference

### Endpoints

```
POST   /api/setup           - Initialize indices
POST   /api/index           - Index single apartment
POST   /api/index/batch     - Batch index apartments
POST   /api/search          - Search apartments
GET    /api/apartments      - List all apartments
GET    /api/apartments/:id  - Get apartment details
DELETE /api/apartments/:id  - Delete apartment
GET    /health              - Health check
```

### Key Concepts

- **Claims** - Atomic facts extracted from listings
- **Domains** - Neighborhood, Apartment, Room
- **Kinds** - Base, Derived, Anti, Verified
- **Grounding** - Google Maps verification of location claims
- **Multi-modal** - Text + Image analysis
- **Semantic** - Understanding meaning, not just keywords

### Score Ranges

- **0.8+** - Excellent match (show prominently)
- **0.6-0.8** - Good match (show normally)
- **0.4-0.6** - Partial match (show with caveats)
- **<0.4** - Weak match (consider hiding)

### Timing Expectations

- **Search:** 1-3 seconds
- **Indexing (text only):** 20-30 seconds
- **Indexing (text + images):** 30-60 seconds
- **Widget rendering:** Instant (after search)
