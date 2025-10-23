# Google Maps Grounding Integration

## Overview

Google Maps Grounding connects Gemini's generative capabilities with Google Maps' 250+ million places database. For apartment search, this enables:

1. **Verified Location Claims**: Ground vague descriptions ("near subway") into precise coordinates and distances
2. **Amenity Discovery**: Identify actual businesses/services around listings (coffee shops, parks, restaurants)
3. **Neighborhood Intelligence**: Extract safety, vibe, and quality signals from aggregated review data
4. **Coordinate-Based Filtering**: Search apartments within specific geographic boundaries
5. **Interactive Exploration**: Return map widgets for users to visually explore neighborhoods

**Source**: [Grounding with Google Maps - Google Blog](https://blog.google/technology/developers/grounding-google-maps-gemini-api/)

**Pricing**: $25/1K grounded prompts (only charged when Maps data is returned)

---

## Integration Architecture

### Dual Integration Strategy

**Indexing Enrichment** (Selective):
- Ground location-based claims during indexing to verify and enrich
- Only invoke when listing contains amenity/location references that benefit from verification
- Creates verified claims with precise coordinates and metadata

**Search Enhancement** (Selective):
- Ground user location queries to resolve ambiguity
- Find specific amenities user mentions, get coordinates
- Enable coordinate-radius filtering in Elasticsearch

**Key Principle**: Use selectively, not universally. Let the system decide when grounding adds value.

---

## Indexing Pipeline Integration

### Phase 1.5: Selective Google Maps Grounding (After Claim Aggregation)

**Trigger Conditions** - Invoke Google Maps Grounding when:

```python
def should_ground_claim(claim):
    """
    Decide if a claim should be grounded with Google Maps
    """
    # Trigger 1: Transport claims with vague proximity
    if claim.claim_type == "transport" and any(word in claim.claim.lower() 
        for word in ["near", "close", "walking distance", "min walk"]):
        return True
    
    # Trigger 2: Amenity claims mentioning specific types
    if claim.claim_type == "amenities" and claim.domain == "neighborhood":
        amenity_keywords = ["restaurant", "cafe", "coffee", "park", "gym", "grocery", "school"]
        if any(keyword in claim.claim.lower() for keyword in amenity_keywords):
            return True
    
    # Trigger 3: Location claims with specific area names
    if claim.claim_type == "location" and claim.is_specific:
        return True
    
    # Trigger 4: Neighborhood vibe claims that can be validated
    if claim.claim_type == "neighborhood":
        validatable = ["safe", "trendy", "quiet", "family-friendly"]
        if any(word in claim.claim.lower() for word in validatable):
            return True
    
    return False
```

### Grounding Execution

**Input Claim**:
```json
{
  "claim": "5 min walk to subway",
  "claim_type": "transport",
  "domain": "neighborhood",
  "apartment_address": "123 Bedford Ave, Brooklyn, NY 11249"
}
```

**Grounding Query**:
```python
from google import genai
from google.genai import types

client = genai.Client()

# Extract coordinates from apartment address
apartment_coords = geocode("123 Bedford Ave, Brooklyn, NY 11249")

prompt = f"""
Find subway stations within 5 minute walk from this location.
Return station names, exact distances, and walking times.
"""

response = client.models.generate_content(
    model='gemini-2.5-flash-lite',
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_maps=types.GoogleMaps())],
        tool_config=types.ToolConfig(
            retrieval_config=types.RetrievalConfig(
                lat_lng=types.LatLng(
                    latitude=apartment_coords.lat,
                    longitude=apartment_coords.lng
                )
            )
        ),
    ),
)
```

**Grounding Response**:
```json
{
  "text": "Bedford Ave L station is 350m away (4 min walk). Marcy Ave J/M/Z station is 650m away (8 min walk).",
  "groundingChunks": [
    {
      "maps": {
        "uri": "https://maps.google.com/?cid=...",
        "title": "Bedford Ave Station",
        "placeId": "ChIJ..."
      }
    }
  ]
}
```

**Enriched Claims Generated**:
```json
{
  "base_claim": {
    "claim": "5 min walk to subway",
    "claim_type": "transport",
    "domain": "neighborhood",
    "kind": "base",
    "grounding_metadata": null
  },
  "verified_claims": [
    {
      "claim": "350m to Bedford Ave L station",
      "claim_type": "transport",
      "domain": "neighborhood",
      "kind": "verified",
      "from_claim": "5 min walk to subway",
      "grounding_metadata": {
        "verified": true,
        "source": "google_maps",
        "coordinates": {"lat": 40.7149, "lng": -73.9566},
        "place_id": "ChIJ...",
        "exact_distance_meters": 350,
        "walking_time_minutes": 4
      },
      "has_quantifiers": true,
      "quantifiers": [{
        "qtype": "distance",
        "noun": "subway",
        "vmin": 350,
        "vmax": 350,
        "op": "EQUALS",
        "unit": "meters"
      }]
    },
    {
      "claim": "4 min walk to subway",
      "claim_type": "transport",
      "domain": "neighborhood",
      "kind": "derived",
      "from_claim": "5 min walk to subway",
      "grounding_metadata": {
        "verified": true,
        "source": "google_maps"
      }
    }
  ]
}
```

**Key Benefits**:
- Original claim preserved (for semantic matching)
- Verified claim with exact metrics (for precise filtering)
- Coordinates stored (for geo-radius queries)
- Higher trust score for grounded claims

---

## Search Pipeline Integration

### Phase 1.5: Selective Query Grounding (After Claim Aggregation)

**Trigger Conditions** - Ground search queries when:

```python
def should_ground_search_claim(claim, user_location=None):
    """
    Decide if a search claim should be grounded with Google Maps
    """
    # Trigger 1: User wants specific amenities nearby
    amenity_patterns = [
        "good coffee shops", "best restaurants", "italian restaurants",
        "playgrounds", "parks", "grocery stores", "gyms"
    ]
    if any(pattern in claim.claim.lower() for pattern in amenity_patterns):
        return True
    
    # Trigger 2: Vague location that needs resolution
    vague_location_patterns = ["near", "close to", "around", "in the area"]
    if claim.claim_type == "location" and any(p in claim.claim.lower() for p in vague_location_patterns):
        return True
    
    # Trigger 3: User provides specific landmark or address
    if claim.is_specific and claim.claim_type == "location":
        return True
    
    # Trigger 4: User location provided but query says "near here"
    if user_location and "near here" in claim.claim.lower():
        return True
    
    return False
```

### Search Query Grounding Example

**User Query**: "2BR near good Italian restaurants in Williamsburg under $4000"

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "2 bedroom apartment",
      "domain": "apartment",
      "weight": 0.95
    },
    {
      "claim": "near good Italian restaurants",
      "domain": "neighborhood",
      "claim_type": "amenities",
      "weight": 0.80
    },
    {
      "claim": "located in Williamsburg",
      "domain": "neighborhood",
      "claim_type": "location",
      "weight": 0.85
    },
    {
      "claim": "monthly rent under $4,000",
      "domain": "apartment",
      "weight": 0.90
    }
  ]
}
```

**Ground the Amenity Claim**:
```python
# Claim: "near good Italian restaurants"
grounding_prompt = "Find the best rated Italian restaurants in Williamsburg, Brooklyn"

response = client.models.generate_content(
    model='gemini-2.5-flash-lite',
    contents=grounding_prompt,
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_maps=types.GoogleMaps(enable_widget=True))],
        tool_config=types.ToolConfig(
            retrieval_config=types.RetrievalConfig(
                # Center on Williamsburg
                lat_lng=types.LatLng(latitude=40.7081, longitude=-73.9571)
            )
        ),
    ),
)
```

**Grounded Response**:
```json
{
  "text": "Lilia (4.6★, 567 Wythe Ave), Antica Pesa (4.5★, 115 Berry St), and Aurora (4.4★, 70 Grand St) are highly-rated Italian restaurants in Williamsburg.",
  "groundingChunks": [
    {
      "maps": {
        "title": "Lilia",
        "placeId": "ChIJ...",
        "uri": "https://maps.google.com/?cid=..."
      }
    }
  ],
  "googleMapsWidgetContextToken": "widget_token_xyz123"
}
```

**Enriched Search Claims**:
```json
{
  "base_claim": {
    "claim": "near good Italian restaurants",
    "claim_type": "amenities",
    "domain": "neighborhood",
    "weight": 0.80
  },
  "verified_claims": [
    {
      "claim": "near Lilia restaurant",
      "claim_type": "amenities",
      "domain": "neighborhood",
      "weight": 0.85,
      "kind": "verified",
      "grounding_metadata": {
        "coordinates": {"lat": 40.7124, "lng": -73.9579},
        "place_id": "ChIJ...",
        "rating": 4.6,
        "verified": true
      }
    },
    {
      "claim": "near Antica Pesa restaurant",
      "weight": 0.85,
      "grounding_metadata": {
        "coordinates": {"lat": 40.7108, "lng": -73.9601}
      }
    }
  ]
}
```

**Geo-Radius Filtering**:
Now we can search apartments within radius of these verified restaurants:

```json
POST /apartments/_search
{
  "query": {
    "bool": {
      "filter": {
        "geo_distance": {
          "distance": "500m",
          "location": {
            "lat": 40.7124,
            "lon": -73.9579
          }
        }
      }
    }
  }
}
```

---

## Use Case Patterns

### 1. **Amenity Proximity Verification**

**Indexing Pattern**:
```
Listing: "Near great coffee shops"
↓ Google Maps Grounding
↓ Finds: Devoción (4.7★), Blue Bottle (4.5★), Variety Coffee (4.6★)
↓ Generates:
  - "near Devoción coffee" (verified, coords)
  - "near Blue Bottle coffee" (verified, coords)  
  - "15+ coffee shops within 500m" (aggregated claim)
```

**Search Pattern**:
```
Query: "apartment near good coffee shops"
↓ Google Maps Grounding
↓ Finds top-rated coffee shops in search area
↓ Search apartments within 500m radius of those shops
```

**Elasticsearch Query**:
```json
{
  "query": {
    "bool": {
      "should": [
        {
          "geo_distance": {
            "distance": "500m",
            "apartment_location": {"lat": 40.7124, "lon": -73.9579}
          }
        },
        {
          "geo_distance": {
            "distance": "500m",
            "apartment_location": {"lat": 40.7108, "lon": -73.9601}
          }
        }
      ],
      "minimum_should_match": 1
    }
  }
}
```

**Widget Return**:
```python
return {
  "apartments": [...],
  "google_maps_widget_token": widget_token,  # Frontend renders coffee shop locations
  "grounded_sources": [
    {"title": "Devoción", "uri": "https://maps.google.com/?cid=...", "rating": 4.7}
  ]
}
```

---

### 2. **Neighborhood Safety & Vibe Inference**

**Indexing Pattern**:
```
Listing location: "40.7081, -73.9571" (Williamsburg)
↓ Google Maps Grounding
↓ Prompt: "Analyze neighborhood safety and vibe based on recent reviews and ratings within 500m radius"
↓ Response: "Area has 4.4 avg rating, reviews mention 'safe at night', 'family-friendly', 'vibrant nightlife'"
↓ Generates:
  - "safe neighborhood" (inferred, source: maps_reviews)
  - "vibrant nightlife nearby" (inferred, source: maps_reviews)
  - "family-friendly area" (inferred, source: maps_reviews)
```

**Enriched Claim**:
```json
{
  "claim": "safe neighborhood",
  "claim_type": "neighborhood",
  "domain": "neighborhood",
  "kind": "verified",
  "grounding_metadata": {
    "verified": true,
    "source": "google_maps_review_analysis",
    "confidence": 0.85,
    "supporting_evidence": "Analyzed 450+ reviews within 500m, 78% mention safety positively"
  }
}
```

**Trust Signal**: Claims with `grounding_metadata.verified=true` get weight boost (+0.1) during search.

---

### 3. **Transport Precision**

**Indexing Pattern**:
```
Listing: "Close to L train"
Location: "123 Bedford Ave, Brooklyn"
↓ Google Maps Grounding
↓ Finds: Bedford Ave L station (350m, 4 min walk)
↓ Generates:
  - Base: "close to L train"
  - Verified: "350m to Bedford Ave L station" (coordinates: 40.7149, -73.9566)
  - Derived: "4 min walk to subway"
```

**Search Pattern**:
```
Query: "apartment within 10 min walk of L train"
↓ Google Maps Grounding
↓ Finds all L train stations in search area
↓ Creates coordinate set for each station
↓ Search apartments within 800m (10 min walk) of ANY L station
```

**Elasticsearch Query with Geo-Distance**:
```json
POST /apartments/_search
{
  "query": {
    "bool": {
      "should": [
        {"geo_distance": {"distance": "800m", "apartment_location": {"lat": 40.7149, "lon": -73.9566}}},
        {"geo_distance": {"distance": "800m", "apartment_location": {"lat": 40.7094, "lon": -73.9440}}},
        {"geo_distance": {"distance": "800m", "apartment_location": {"lat": 40.7208, "lon": -73.9501}}}
      ],
      "minimum_should_match": 1
    }
  }
}
```

**Benefit**: User gets apartments actually within 10 min walk, not just semantically matching "near subway".

---

### 4. **Multi-Amenity Clustering**

**Search Pattern**:
```
Query: "family-friendly neighborhood with playgrounds, good schools, and grocery stores nearby"
↓ Google Maps Grounding (3 parallel queries)
  1. "playgrounds in [area]" → 5 playgrounds found
  2. "highly-rated schools in [area]" → 8 schools found  
  3. "grocery stores in [area]" → 12 stores found
↓ Get coordinate clusters where ALL THREE are within 500m
↓ Search apartments in those clusters only
```

**Cluster Identification**:
```python
# Find geographic areas with ALL required amenities
playground_coords = [(40.71, -73.95), (40.72, -73.96), ...]
school_coords = [(40.71, -73.95), (40.73, -73.97), ...]
grocery_coords = [(40.71, -73.95), (40.72, -73.96), ...]

# Find coordinate clusters where amenities overlap
amenity_clusters = find_clusters_with_all_amenities(
    playgrounds=playground_coords,
    schools=school_coords, 
    groceries=grocery_coords,
    radius=500  # meters
)
# Returns: [(40.71, -73.95), ...] <- coordinates with all 3 amenities nearby

# Search apartments near these clusters
```

**Elasticsearch Query**:
```json
{
  "query": {
    "bool": {
      "should": [
        {"geo_distance": {"distance": "300m", "apartment_location": {"lat": 40.71, "lon": -73.95}}},
        {"geo_distance": {"distance": "300m", "apartment_location": {"lat": 40.72, "lon": -73.96}}}
      ]
    }
  }
}
```

---

### 5. **Specific Landmark Proximity**

**Search Pattern**:
```
Query: "apartment near Central Park with park views"
↓ Google Maps Grounding
↓ Resolves "Central Park" to coordinates: (40.7829, -73.9654)
↓ Gets park boundary polygon
↓ Search apartments within 200m of park boundary
```

**Grounding Query**:
```python
prompt = "What are the coordinates and boundary of Central Park in NYC?"
response = client.models.generate_content(
    model='gemini-2.5-flash-lite',
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_maps=types.GoogleMaps())],
    ),
)
```

**Response Processing**:
```python
{
  "park_center": {"lat": 40.7829, "lon": -73.9654},
  "park_bounds": {
    "north": 40.8006,
    "south": 40.7644,
    "east": -73.9497,
    "west": -73.9816
  }
}
```

**Elasticsearch Geo-Shape Query**:
```json
{
  "query": {
    "bool": {
      "filter": {
        "geo_distance": {
          "distance": "200m",
          "apartment_location": {"lat": 40.7829, "lon": -73.9654}
        }
      }
    }
  }
}
```

**Combined with Semantic**:
- Geo-filter: Apartments within 200m of Central Park
- Semantic-filter: Match "park views" claim
- Result: Apartments actually overlooking Central Park

---

### 6. **Commute-Time Based Search**

**Search Pattern**:
```
Query: "apartment with <30 min commute to Google NYC office"
↓ Google Maps Grounding
↓ Resolves "Google NYC office" to address: 111 8th Ave, NYC
↓ Gets coordinates: (40.7414, -74.0040)
↓ Queries isochrone: "areas within 30 min commute"
↓ Returns neighborhood polygons within 30 min transit time
↓ Search apartments in those polygons
```

**Grounding Query**:
```python
prompt = """
What neighborhoods in NYC are within 30 minutes of commute time 
to 111 8th Ave (Google NYC office) via public transit during morning rush hour?
"""

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_maps=types.GoogleMaps())],
        tool_config=types.ToolConfig(
            retrieval_config=types.RetrievalConfig(
                lat_lng=types.LatLng(latitude=40.7414, longitude=-74.0040)
            )
        ),
    ),
)
```

**Response**:
```
Chelsea (10-15 min), West Village (15-20 min), Williamsburg (20-25 min), 
Park Slope (25-30 min) are within 30 min commute.
```

**Converted to Geo-Search**:
```python
# Get bounding boxes for these neighborhoods
neighborhoods = ["Chelsea", "West Village", "Williamsburg", "Park Slope"]
neighborhood_bounds = []

for neighborhood in neighborhoods:
    bounds = get_neighborhood_bounds(neighborhood)  # From Maps or geocoding
    neighborhood_bounds.append(bounds)

# Search apartments within these neighborhoods
```

**Widget**: Return interactive map showing commute times from different neighborhoods to office.

---

## Elasticsearch Geo-Spatial Schema

### Apartment Index with Geo-Point

```json
{
  "mappings": {
    "properties": {
      "apartment_id": {"type": "keyword"},
      "apartment_location": {
        "type": "geo_point"
      },
      "address": {"type": "text"},
      "neighborhood_id": {"type": "keyword"},
      "claim": {"type": "text"},
      "claim_type": {"type": "keyword"},
      "claim_vector": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine"
      },
      "grounding_metadata": {
        "type": "object",
        "properties": {
          "verified": {"type": "boolean"},
          "source": {"type": "keyword"},
          "coordinates": {"type": "geo_point"},
          "place_id": {"type": "keyword"},
          "exact_distance_meters": {"type": "integer"},
          "confidence": {"type": "float"}
        }
      }
    }
  }
}
```

### Neighborhood Index with Geo-Shape

```json
{
  "mappings": {
    "properties": {
      "neighborhood_id": {"type": "keyword"},
      "neighborhood_name": {"type": "text"},
      "neighborhood_boundary": {
        "type": "geo_shape"
      },
      "center_point": {"type": "geo_point"},
      "claim": {"type": "text"},
      "claim_vector": {"type": "dense_vector", "dims": 768},
      "verified_amenities": {
        "type": "nested",
        "properties": {
          "amenity_type": {"type": "keyword"},
          "name": {"type": "text"},
          "location": {"type": "geo_point"},
          "rating": {"type": "float"},
          "place_id": {"type": "keyword"}
        }
      }
    }
  }
}
```

---

## Hybrid Search: Semantic + Geographic

Combine semantic claim matching with geographic filtering:

### Example: "Modern 2BR near good coffee shops in Brooklyn under $4000"

**Step 1: Ground Coffee Shop Requirement**
```python
# Google Maps finds top coffee shops in Brooklyn
coffee_shops = [
    {"name": "Devoción", "coords": (40.7124, -73.9579), "rating": 4.7},
    {"name": "Blue Bottle", "coords": (40.7108, -73.9601), "rating": 4.5},
    # ... more
]
```

**Step 2: Parallel Search with Geo-Filter**

```json
POST /_msearch
{}
{"index": "apartments"}
{
  "query": {
    "bool": {
      "must": [
        {
          "knn": {
            "field": "claim_vector",
            "query_vector": [...],
            "k": 100,
            "filter": {
              "term": {"claim_type": "size"}
            }
          }
        }
      ],
      "filter": [
        {
          "bool": {
            "should": [
              {"geo_distance": {"distance": "500m", "apartment_location": {"lat": 40.7124, "lon": -73.9579}}},
              {"geo_distance": {"distance": "500m", "apartment_location": {"lat": 40.7108, "lon": -73.9601}}}
            ],
            "minimum_should_match": 1
          }
        },
        {
          "nested": {
            "path": "quantifiers",
            "query": {
              "bool": {
                "must": [
                  {"term": {"quantifiers.qtype": "money"}},
                  {"range": {"quantifiers.vmax": {"lte": 4000}}}
                ]
              }
            }
          }
        }
      ]
    }
  }
}
```

**Query Combines**:
- Semantic kNN: Match "2 bedroom", "modern"
- Geo-filter: Within 500m of verified coffee shops
- Quantifier-filter: Rent ≤ $4000

**Result**: Apartments that semantically match AND are actually near good coffee shops (verified by Maps data).

---

## Smart Grounding Decision Logic

### When NOT to Ground (Cost Optimization)

```python
def skip_grounding(claim, context):
    """
    Skip grounding to save costs when it doesn't add value
    """
    # Skip 1: No location context
    if not context.has_location and claim.claim_type not in ["location", "transport"]:
        return True
    
    # Skip 2: Already verified in cache
    if claim.claim in grounding_cache:
        return True
    
    # Skip 3: Generic claims that don't need verification
    generic_patterns = [
        "spacious", "modern", "clean", "bright",
        "well-designed", "cozy", "comfortable"
    ]
    if any(pattern in claim.claim.lower() for pattern in generic_patterns):
        return True
    
    # Skip 4: Apartment-level features (Maps can't verify)
    if claim.domain == "apartment" and claim.claim_type == "features":
        return True
    
    # Skip 5: Room-level claims (Maps has no room data)
    if claim.domain == "room":
        return True
    
    return False
```

### When TO Ground (High Value)

```python
def should_ground(claim, context):
    """
    Ground when it adds significant value
    """
    # Ground 1: Specific amenity mentions
    if claim.claim_type == "amenities" and claim.domain == "neighborhood":
        amenity_keywords = [
            "restaurant", "cafe", "coffee", "park", "gym", "school",
            "grocery", "pharmacy", "hospital", "library"
        ]
        return any(kw in claim.claim.lower() for kw in amenity_keywords)
    
    # Ground 2: Transport with distance/time
    if claim.claim_type == "transport" and claim.has_quantifiers:
        return True
    
    # Ground 3: Specific location names (landmarks, neighborhoods)
    if claim.claim_type == "location" and claim.is_specific:
        return True
    
    # Ground 4: Neighborhood vibe that can be validated
    if claim.claim_type == "neighborhood":
        validatable = ["safe", "quiet", "trendy", "family-friendly", "walkable"]
        return any(v in claim.claim.lower() for v in validatable)
    
    # Ground 5: User explicitly provides address or landmark
    if "near" in claim.claim.lower() and claim.is_specific:
        return True
    
    return False
```

---

## Implementation Workflow

### Indexing Flow with Selective Grounding

```python
async def index_apartment_listing(listing_text, address):
    # Phase 1: Claim Aggregation
    claims = await llm_aggregate_claims(listing_text)
    
    # Phase 1.5: Selective Google Maps Grounding
    grounding_candidates = [c for c in claims if should_ground(c, context={"address": address})]
    
    if grounding_candidates:
        # Batch ground multiple claims in one call
        grounding_prompt = f"""
        Verify and enrich the following claims about an apartment at {address}:
        {json.dumps([c.claim for c in grounding_candidates])}
        
        For each claim, provide:
        - Verification status
        - Exact distances/coordinates if applicable
        - Specific place names and ratings
        """
        
        grounded_response = await gemini_ground_with_maps(
            prompt=grounding_prompt,
            location=geocode(address)
        )
        
        # Parse grounded response and create verified claims
        verified_claims = parse_grounding_response(grounded_response)
        claims.extend(verified_claims)
    
    # Phase 2: Deduplication (including verified claims)
    claims = deduplicate_claims(claims)
    
    # Phase 3: Expansion (only for base claims, not verified)
    base_claims = [c for c in claims if c.kind != "verified"]
    expanded = await expand_claims(base_claims)
    claims.extend(expanded)
    
    # Phases 4-6: Quantifier extraction, embedding, Elasticsearch indexing
    # ...
```

### Search Flow with Selective Grounding

```python
async def search_apartments(query, user_location=None):
    # Phase 1: Claim Aggregation
    search_claims = await llm_aggregate_search_claims(query)
    
    # Phase 1.5: Selective Google Maps Grounding
    grounding_candidates = [c for c in search_claims if should_ground_search_claim(c, user_location)]
    
    geo_filters = []
    widget_tokens = []
    
    if grounding_candidates:
        for claim in grounding_candidates:
            grounding_prompt = build_search_grounding_prompt(claim, user_location)
            
            grounded = await gemini_ground_with_maps(
                prompt=grounding_prompt,
                location=user_location,
                enable_widget=True
            )
            
            # Extract coordinates for geo-filtering
            if grounded.coordinates:
                geo_filters.append({
                    "claim": claim.claim,
                    "coordinates": grounded.coordinates,
                    "radius": infer_radius(claim)  # "near" = 500m, "walking distance" = 800m
                })
            
            # Store widget token for frontend
            if grounded.widget_token:
                widget_tokens.append({
                    "claim": claim.claim,
                    "widget_token": grounded.widget_token,
                    "sources": grounded.grounding_chunks
                })
    
    # Phase 2: Quantifier Extraction
    search_claims = await extract_quantifiers(search_claims)
    
    # Phase 3: Embedding
    embedded_claims = await embed_claims(search_claims)
    
    # Phase 4: Parallel Recursive Search WITH geo-filters
    results = await recursive_search_with_geo(
        embedded_claims=embedded_claims,
        geo_filters=geo_filters
    )
    
    # Return results + widget tokens for frontend rendering
    return {
        "apartments": results,
        "map_widgets": widget_tokens,
        "grounded_sources": extract_sources(widget_tokens)
    }
```

---

## Grounding Prompt Templates

### Template 1: Amenity Discovery & Verification

```python
def build_amenity_grounding_prompt(claim, location):
    """
    For claims like: "near good coffee shops", "close to parks"
    """
    amenity_type = extract_amenity_type(claim.claim)  # "coffee shops", "parks"
    
    return f"""
    Find the top-rated {amenity_type} near this location.
    Return:
    - Business names
    - Ratings (if available)
    - Exact distances in meters
    - Walking times
    
    Prioritize places with 4.0+ ratings and focus on those within 500m.
    """
```

### Template 2: Transport Verification

```python
def build_transport_grounding_prompt(claim, address):
    """
    For claims like: "5 min walk to subway", "near L train"
    """
    return f"""
    Find subway/train stations near {address}.
    For each station:
    - Station name and line(s)
    - Exact walking distance in meters
    - Estimated walking time
    - Coordinates
    
    Focus on stations within 1km.
    """
```

### Template 3: Neighborhood Vibe Analysis

```python
def build_vibe_grounding_prompt(claim, neighborhood):
    """
    For claims like: "safe neighborhood", "trendy area", "family-friendly"
    """
    vibe_descriptor = extract_vibe(claim.claim)  # "safe", "trendy", "family-friendly"
    
    return f"""
    Analyze {neighborhood} to determine if it can be characterized as "{vibe_descriptor}".
    
    Use:
    - Recent user reviews (last 12 months)
    - Business types and ratings
    - Amenity distribution
    
    Provide:
    - Confirmation (yes/no/partial)
    - Confidence score (0-1)
    - Supporting evidence from reviews
    """
```

### Template 4: Multi-Amenity Clustering

```python
def build_cluster_grounding_prompt(claims, area):
    """
    For queries with multiple amenity requirements
    """
    amenity_list = [extract_amenity_type(c.claim) for c in claims]
    
    return f"""
    Find areas in {area} that have ALL of the following nearby:
    {", ".join(amenity_list)}
    
    For each amenity type:
    - List top 3-5 options with ratings
    - Provide coordinates
    
    Identify 3-5 "sweet spot" locations where all amenities are within 500m.
    """
```

---

## Frontend Integration

### Widget Rendering

```typescript
// Frontend receives widget token
const searchResults = await fetch('/api/search', {
  method: 'POST',
  body: JSON.stringify({ query: "2BR near good coffee shops in Brooklyn" })
});

const data = await searchResults.json();

// Render apartment results
data.apartments.forEach(apt => renderApartment(apt));

// Render Google Maps contextual widgets
data.map_widgets.forEach(widget => {
  const container = document.createElement('div');
  container.innerHTML = `
    <gmp-place-contextual 
      context-token="${widget.widget_token}">
    </gmp-place-contextual>
  `;
  document.getElementById('maps-container').appendChild(container);
});
```

### Display Grounded Sources

```typescript
// Show which Google Maps sources were used
function renderGroundedSources(sources) {
  return sources.map(source => `
    <div class="grounded-source">
      <img src="maps-favicon.png" />
      <a href="${source.uri}" target="_blank" translate="no">
        Google Maps
      </a>
      <span class="source-title">${source.title}</span>
      ${source.rating ? `<span class="rating">${source.rating}★</span>` : ''}
    </div>
  `).join('');
}
```

**Attribution Requirements** (per Google's guidelines):
- Use "Google Maps" text (no modification, no translation)
- Font: Roboto or sans-serif fallback
- Size: 12-16sp
- Color: Black (#1F1F1F) or gray (#5E5E5E)
- Attribute `translate="no"` to prevent browser translation

---

## Cost Management Strategies

### 1. **Claim-Level Grounding (Not Query-Level)**

Ground individual claims selectively, not entire queries:

```python
# ❌ EXPENSIVE: Ground entire query
ground_entire_query("2BR near coffee shops in Brooklyn under $4000")  
# Cost: 1 grounding call

# ✅ COST-EFFECTIVE: Ground only amenity claim
claims = aggregate_claims(query)
for claim in claims:
    if should_ground(claim):  # Only "near coffee shops"
        ground_claim(claim)
# Cost: 1 grounding call (same), but more targeted
```

### 2. **Batch Grounding**

Combine multiple groundable claims into one API call:

```python
# Multiple claims from same listing
claims_to_ground = [
    "near subway",
    "close to parks", 
    "good restaurants nearby"
]

# Single grounding call
prompt = f"""
For an apartment at {address}, verify:
1. {claims_to_ground[0]}
2. {claims_to_ground[1]}
3. {claims_to_ground[2]}
"""
# Cost: 1 call instead of 3
```

### 3. **Smart Caching**

Cache grounding results by **location + claim pattern**:

```python
cache_key = f"{neighborhood_id}:transport:subway"
if cache_key in grounding_cache and cache_age < 30_days:
    return cached_grounding
else:
    grounded = await ground_with_maps(...)
    cache.set(cache_key, grounded, ttl=30_days)
```

**Cache Scope**:
- Neighborhood-level amenities: 30 days TTL
- Transport verification: 90 days TTL (stations don't move)
- Vibe analysis: 14 days TTL (reviews change)

### 4. **Trigger Thresholds**

Only ground when claim is ambiguous or verification adds high value:

```python
GROUNDING_VALUE_SCORES = {
    ("transport", "has_quantifiers"): 0.9,  # "5 min to subway" - high value
    ("amenities", "neighborhood"): 0.8,     # "good restaurants" - high value
    ("location", "is_specific"): 0.7,       # "in Williamsburg" - medium value
    ("neighborhood", "safe"): 0.8,          # "safe area" - high value
    ("features", "apartment"): 0.2,         # "exposed brick" - low value (can't verify)
}

# Only ground if value score > 0.6
```

### 5. **Progressive Enhancement**

Start with semantic-only results, ground asynchronously:

```python
# Return initial semantic results immediately
initial_results = await semantic_search(query)

# Ground in background, update results
asyncio.create_task(
    ground_and_refine(query, initial_results)
)

return initial_results  # Fast response
```

---

## Advanced Use Cases

### Use Case 1: "Best of Category" Neighborhoods

**Query**: "Best neighborhood for coffee lovers in Brooklyn"

**Grounding Approach**:
```python
prompt = """
Analyze all neighborhoods in Brooklyn to find the best for coffee enthusiasts.
Consider:
- Density of highly-rated coffee shops (4.5+ stars)
- Variety of coffee shop types (specialty, third-wave, cafes)
- Walkability score between shops

Return top 3 neighborhoods with supporting data.
"""

grounded = await ground_with_maps(prompt, location=brooklyn_center)
```

**Response**:
```
Williamsburg (45 coffee shops, 4.6 avg rating, 15 within 500m walk)
Park Slope (38 coffee shops, 4.5 avg rating, 12 within 500m walk)
DUMBO (22 coffee shops, 4.7 avg rating, 8 within 500m walk)
```

**Enriched Search**:
- Search apartments in Williamsburg, Park Slope, DUMBO
- Boost apartments within 300m of multiple coffee shops
- Return widget showing coffee shop density map

---

### Use Case 2: Reverse Geocoding User Queries

**Query**: "apartment near where I work" (user at 40.7414, -74.0040)

**Grounding Approach**:
```python
prompt = "What is this location? Provide neighborhood name and notable landmarks."

grounded = await ground_with_maps(
    prompt, 
    location=(40.7414, -74.0040)
)
```

**Response**:
```
This is Chelsea, Manhattan. Near Google NYC office, Madison Square Garden, 
and Penn Station. Well-connected by A/C/E and 1/2/3 trains.
```

**Search Conversion**:
- User query → "apartment in Chelsea near Penn Station"
- Ground to coordinates
- Search within 1km radius
- Filter by commute time (<30 min to work)

---

### Use Case 3: Competitive Neighborhood Analysis

**Indexing Enhancement**:
```
Listing: "Quiet neighborhood, great for families"
Address: "456 Park Pl, Brooklyn"
↓ Google Maps Grounding
↓ Prompt: "Analyze family-friendliness of area around 456 Park Pl, Brooklyn. 
           Count playgrounds, schools, family restaurants within 800m."
↓ Response: "2 playgrounds (4.3★ avg), 3 elementary schools (4.5★ avg), 
           8 family restaurants (4.4★ avg) within 800m. Low bar/club density."
↓ Generates verified claims:
  - "2 playgrounds within 800m" (verified, coordinates)
  - "3 schools nearby" (verified, coordinates)
  - "family-friendly area" (verified from analysis)
```

**Search Benefit**:
Query: "family-friendly neighborhood"
- Matches both base claim AND verified claim
- Verified claims have higher weight
- User gets apartments in ACTUALLY family-friendly areas (backed by Maps data)

---

### Use Case 4: Commute Optimization

**Search Pattern**:
```
Query: "apartment with <25 min commute to Times Square"
↓ Resolve "Times Square" to coords: (40.7580, -73.9855)
↓ Google Maps Grounding: "What areas are within 25 min transit of Times Square?"
↓ Response: Astoria (15-20 min), LIC (10-15 min), Williamsburg (20-25 min)
↓ Get neighborhood boundaries for these areas
↓ Search apartments within those boundaries
```

**Grounding Query**:
```python
prompt = """
What neighborhoods in NYC have <25 minute public transit commute to Times Square 
(40.7580, -73.9855) during morning rush hour (8-9 AM)?

For each neighborhood:
- Name
- Typical commute time range
- Primary transit lines used
"""

grounded = await ground_with_maps(
    prompt,
    location=(40.7580, -73.9855)
)
```

**Geo-Filter Generation**:
```python
# From grounded response, get neighborhood boundaries
neighborhoods = ["Astoria", "LIC", "Williamsburg"]
geo_filters = []

for nbh in neighborhoods:
    bounds = get_neighborhood_polygon(nbh)  # From Maps API or geocoding
    geo_filters.append({
        "geo_shape": {
            "apartment_location": {
                "shape": bounds,
                "relation": "within"
            }
        }
    })
```

---

### Use Case 5: Specific Business Proximity

**Query**: "apartment near Whole Foods in Brooklyn"

**Grounding**:
```python
prompt = "Find all Whole Foods locations in Brooklyn with coordinates"

grounded = await ground_with_maps(prompt)
```

**Response**:
```json
{
  "locations": [
    {"name": "Whole Foods Gowanus", "coords": (40.6740, -73.9870)},
    {"name": "Whole Foods Williamsburg", "coords": (40.7081, -73.9571)},
    {"name": "Whole Foods DUMBO", "coords": (40.7033, -73.9898)}
  ],
  "widget_token": "xyz123"
}
```

**Search Strategy**:
```python
# Create geo-filter for each Whole Foods location
geo_queries = []
for location in grounded.locations:
    geo_queries.append({
        "geo_distance": {
            "distance": "800m",  # Walking distance
            "apartment_location": location.coords
        }
    })

# Search apartments near ANY Whole Foods
# Also show widget so user can see which Whole Foods and choose
```

---

## Elasticsearch Geo-Query Patterns

### Pattern 1: Geo-Distance Filter with Semantic kNN

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "knn": {
            "field": "claim_vector",
            "query_vector": [...],
            "k": 100,
            "filter": {"term": {"claim_type": "features"}}
          }
        }
      ],
      "filter": {
        "geo_distance": {
          "distance": "500m",
          "apartment_location": {
            "lat": 40.7124,
            "lon": -73.9579
          }
        }
      }
    }
  }
}
```

### Pattern 2: Multiple Geo-Points (OR Logic)

```json
{
  "query": {
    "bool": {
      "must": [
        {"knn": {...}}
      ],
      "filter": {
        "bool": {
          "should": [
            {"geo_distance": {"distance": "500m", "apartment_location": {"lat": 40.71, "lon": -73.96}}},
            {"geo_distance": {"distance": "500m", "apartment_location": {"lat": 40.72, "lon": -73.97}}},
            {"geo_distance": {"distance": "500m", "apartment_location": {"lat": 40.73, "lon": -73.98}}}
          ],
          "minimum_should_match": 1
        }
      }
    }
  }
}
```

### Pattern 3: Geo-Shape Polygon Filter

```json
{
  "query": {
    "bool": {
      "filter": {
        "geo_shape": {
          "apartment_location": {
            "shape": {
              "type": "polygon",
              "coordinates": [[
                [-73.99, 40.70],
                [-73.95, 40.70],
                [-73.95, 40.73],
                [-73.99, 40.73],
                [-73.99, 40.70]
              ]]
            },
            "relation": "within"
          }
        }
      }
    }
  }
}
```

### Pattern 4: Geo-Distance Aggregation

Find apartments clustered near amenities:

```json
{
  "query": {...},
  "aggs": {
    "amenity_clusters": {
      "geo_distance": {
        "field": "apartment_location",
        "origin": {"lat": 40.7124, "lon": -73.9579},
        "ranges": [
          {"to": 300},
          {"from": 300, "to": 500},
          {"from": 500, "to": 800}
        ]
      }
    }
  }
}
```

Returns apartment count by distance band (0-300m, 300-500m, 500-800m).

---

## Grounding Metadata Schema

### Enriched Claim Structure

```python
{
  "claim": "350m to Bedford Ave L station",
  "claim_type": "transport",
  "domain": "neighborhood",
  "kind": "verified",
  "from_claim": "close to subway",
  "weight": 0.90,  # Boosted for verification
  "has_quantifiers": true,
  "quantifiers": [{
    "qtype": "distance",
    "noun": "subway",
    "vmin": 350,
    "vmax": 350,
    "op": "EQUALS"
  }],
  "grounding_metadata": {
    "verified": true,
    "source": "google_maps",
    "place_id": "ChIJ...",
    "place_name": "Bedford Ave Station",
    "place_uri": "https://maps.google.com/?cid=...",
    "coordinates": {
      "lat": 40.7149,
      "lon": -73.9566
    },
    "exact_distance_meters": 350,
    "walking_time_minutes": 4,
    "confidence": 1.0,
    "verified_at": "2025-10-21T10:30:00Z"
  }
}
```

---

## Decision Matrix: When to Use Grounding

| Claim Pattern | Ground? | Why / Why Not |
|---------------|---------|---------------|
| "near subway" | ✅ Yes | High value - verify station, distance |
| "5 min walk to L train" | ✅ Yes | High value - verify accuracy |
| "good coffee shops nearby" | ✅ Yes | High value - find actual shops, ratings |
| "safe neighborhood" | ✅ Yes | High value - validate from reviews |
| "trendy area" | ✅ Yes | High value - validate from business types |
| "in Williamsburg" | ⚠️ Maybe | Medium value - if need exact boundaries |
| "high ceilings" | ❌ No | No value - Maps can't verify apartment features |
| "modern kitchen" | ❌ No | No value - Maps has no room data |
| "spacious apartment" | ❌ No | No value - subjective, not in Maps |
| "pets allowed" | ❌ No | No value - policy not in Maps |
| "exposed brick" | ❌ No | No value - architectural detail not in Maps |
| "2 bedroom" | ❌ No | No value - Maps doesn't have unit details |

**Rule of Thumb**: Ground claims about **location, proximity, and neighborhood characteristics**. Skip claims about **apartment internals** and **subjective qualities** Maps can't verify.

---

## Example: Full Grounding-Enhanced Flow

**Query**: "Modern 2BR near top-rated Italian restaurants in Williamsburg, <10 min to L train, safe area"

### Phase 1: Claim Aggregation
```json
{
  "claims": [
    {"claim": "2 bedroom apartment", "domain": "apartment"},
    {"claim": "modern apartment", "domain": "apartment"},
    {"claim": "near top-rated Italian restaurants", "domain": "neighborhood", "groundable": true},
    {"claim": "located in Williamsburg", "domain": "neighborhood", "groundable": true},
    {"claim": "<10 min walk to L train", "domain": "neighborhood", "groundable": true},
    {"claim": "safe area", "domain": "neighborhood", "groundable": true}
  ]
}
```

### Phase 1.5: Selective Grounding (4 groundable claims)

**Grounding Call 1** - Italian Restaurants:
```python
prompt = "Find top-rated (4.5+ stars) Italian restaurants in Williamsburg, Brooklyn"
→ Finds: Lilia (4.6★, coords), Antica Pesa (4.5★, coords), Aurora (4.4★, coords)
→ Widget token: "widget_xyz"
```

**Grounding Call 2** - L Train Stations:
```python
prompt = "Find L train stations in Williamsburg with walking distances from neighborhood center"
→ Finds: Bedford Ave (center), Lorimer St (east), Graham Ave (east)
→ Returns coordinates for each
```

**Grounding Call 3** - Safety Validation:
```python
prompt = "Analyze safety of Williamsburg based on recent reviews and place ratings"
→ Response: "Generally safe, 82% of reviews mention positive safety, well-lit streets, active nightlife. Some areas very quiet after midnight."
→ Confidence: 0.85
```

**Cost**: 3 grounding calls = $0.075

### Phase 2: Generate Verified Claims

```json
{
  "verified_claims": [
    {
      "claim": "near Lilia Italian restaurant",
      "kind": "verified",
      "grounding_metadata": {
        "coordinates": {"lat": 40.7124, "lon": -73.9579},
        "rating": 4.6,
        "place_id": "ChIJ..."
      }
    },
    {
      "claim": "400m to Bedford Ave L station",
      "kind": "verified",
      "quantifiers": [{"qtype": "distance", "vmin": 400, "vmax": 400}],
      "grounding_metadata": {
        "coordinates": {"lat": 40.7149, "lon": -73.9566},
        "walking_time_minutes": 5
      }
    },
    {
      "claim": "safe neighborhood",
      "kind": "verified",
      "grounding_metadata": {
        "verified": true,
        "confidence": 0.85,
        "supporting_evidence": "82% of 450+ reviews mention safety positively"
      }
    }
  ]
}
```

### Phase 3: Geo-Filtered Recursive Search

**Elasticsearch Query**:
```json
POST /_msearch
{}
{"index": "neighborhoods"}
{
  "query": {
    "bool": {
      "must": [
        {"knn": {"field": "claim_vector", "query_vector": [...], "k": 20}}
      ],
      "filter": {
        "geo_shape": {
          "neighborhood_boundary": {
            "shape": {
              "type": "point",
              "coordinates": [-73.9571, 40.7081]
            },
            "relation": "contains"
          }
        }
      }
    }
  }
}
{}
{"index": "apartments"}
{
  "query": {
    "bool": {
      "must": [
        {"knn": {"field": "claim_vector", "query_vector": [...], "k": 100}}
      ],
      "filter": {
        "bool": {
          "should": [
            {"geo_distance": {"distance": "500m", "apartment_location": {"lat": 40.7124, "lon": -73.9579}}},
            {"geo_distance": {"distance": "800m", "apartment_location": {"lat": 40.7149, "lon": -73.9566}}}
          ],
          "minimum_should_match": 1
        }
      }
    }
  }
}
```

**Combined Filters**:
- Semantic: Match "2BR", "modern"
- Geographic: Within 500m of Lilia OR 800m of Bedford L station
- Neighborhood: In Williamsburg boundary, safe area verified

### Phase 4: Return Results + Widget

```python
return {
  "apartments": [
    {
      "apartment_id": "apt_123",
      "address": "250 Bedford Ave",
      "score": 0.92,
      "coverage": "6/6 claims matched",
      "geo_proximity": {
        "to_lilia": "320m",
        "to_bedford_L": "180m"
      }
    }
  ],
  "grounded_sources": [
    {
      "title": "Lilia",
      "uri": "https://maps.google.com/?cid=...",
      "rating": 4.6,
      "category": "Italian Restaurant"
    },
    {
      "title": "Bedford Ave Station",
      "uri": "https://maps.google.com/?cid=...",
      "category": "Subway Station"
    }
  ],
  "map_widget_token": "widget_xyz",  // Frontend renders interactive map
  "grounding_metadata": {
    "grounded_claims": 4,
    "cost": "$0.075"
  }
}
```

**Frontend Rendering**:
- Show apartment results with verified proximity badges
- Render Google Maps widget showing restaurants + stations
- Display grounded sources with Google Maps attribution
- User can explore neighborhood visually

---

## Grounding Prompt Patterns

### Pattern 1: Amenity Discovery

```python
AMENITY_GROUNDING_TEMPLATE = """
Find {amenity_type} near {location} that match these criteria:
- Rating: {min_rating}+ stars
- Distance: within {max_distance}m
- {additional_filters}

Return for each:
- Name
- Rating
- Exact distance in meters
- Coordinates
- Brief description if relevant

Focus on top {limit} results.
"""

# Usage
prompt = AMENITY_GROUNDING_TEMPLATE.format(
    amenity_type="Italian restaurants",
    location="Williamsburg, Brooklyn",
    min_rating=4.5,
    max_distance=800,
    additional_filters="open for dinner",
    limit=5
)
```

### Pattern 2: Transport Verification

```python
TRANSPORT_GROUNDING_TEMPLATE = """
Find {transport_type} near {address}.

Return:
- Station/stop name
- Line(s) or route numbers
- Walking distance in meters
- Walking time in minutes
- Coordinates

Include all options within {max_distance}m.
"""

# Usage
prompt = TRANSPORT_GROUNDING_TEMPLATE.format(
    transport_type="subway stations",
    address="123 Bedford Ave, Brooklyn NY",
    max_distance=1000
)
```

### Pattern 3: Neighborhood Analysis

```python
NEIGHBORHOOD_VIBE_TEMPLATE = """
Analyze the {neighborhood} neighborhood to determine if it is "{vibe_descriptor}".

Consider:
- Recent user reviews (last 12 months) for businesses in the area
- Types of businesses and their ratings
- Foot traffic patterns and activity level
- Demographic indicators if available

Provide:
- Confirmation: yes/no/partial
- Confidence score: 0.0-1.0
- Supporting evidence: key phrases from reviews or observations
- Notable businesses that support or contradict this characterization

Be objective and data-driven.
"""

# Usage
prompt = NEIGHBORHOOD_VIBE_TEMPLATE.format(
    neighborhood="Williamsburg, Brooklyn",
    vibe_descriptor="trendy with good nightlife"
)
```

### Pattern 4: Multi-Criteria Clustering

```python
CLUSTER_GROUNDING_TEMPLATE = """
Find locations in {area} where ALL of the following are nearby:
{amenity_list}

For each amenity type:
- List top 3 options with names, ratings, coordinates

Then identify 3-5 "sweet spot" coordinates where all amenities are within {radius}m.

Return as JSON:
{{
  "amenities": {{amenity_type: [{{name, rating, coords}}]}},
  "sweet_spots": [{{coords, coverage_score}}]
}}
"""

# Usage
prompt = CLUSTER_GROUNDING_TEMPLATE.format(
    area="Brooklyn",
    amenity_list="\n".join([
        "- Highly-rated coffee shops (4.5+ stars)",
        "- Parks or green spaces", 
        "- Grocery stores",
        "- Gyms or fitness centers"
    ]),
    radius=500
)
```

---

## Widget Integration Guide

### Backend: Return Widget Tokens

```python
@app.post("/api/search")
async def search_apartments(query: str, user_location: Optional[dict] = None):
    results = await search_with_grounding(query, user_location)
    
    return {
        "apartments": results.apartments,
        "widgets": [
            {
                "context_token": results.widget_tokens[0],
                "title": "Italian Restaurants in Area",
                "type": "amenities"
            },
            {
                "context_token": results.widget_tokens[1],
                "title": "Nearby Subway Stations",
                "type": "transport"
            }
        ],
        "grounded_sources": results.grounded_sources
    }
```

### Frontend: Render Widgets

```typescript
// Load Google Maps JavaScript API
<script src="https://maps.googleapis.com/maps/api/js?key=YOUR_API_KEY&libraries=places"></script>

// Component
function MapWidgets({ widgets }: { widgets: Widget[] }) {
  return (
    <div className="maps-widgets">
      {widgets.map(widget => (
        <div key={widget.context_token} className="widget-container">
          <h3>{widget.title}</h3>
          <gmp-place-contextual 
            context-token={widget.context_token}>
          </gmp-place-contextual>
        </div>
      ))}
    </div>
  );
}
```

### Grounded Source Attribution

```typescript
function GroundedSources({ sources }: { sources: Source[] }) {
  return (
    <div className="grounded-sources">
      <p className="attribution-header">Verified with:</p>
      {sources.map(source => (
        <div key={source.place_id} className="source-item">
          <img src="/maps-favicon.png" alt="" />
          <a 
            href={source.uri} 
            target="_blank" 
            className="GMP-attribution"
            translate="no">
            Google Maps
          </a>
          <span className="source-title">{source.title}</span>
          {source.rating && (
            <span className="rating">{source.rating}★</span>
          )}
        </div>
      ))}
    </div>
  );
}
```

**CSS** (per Google's attribution guidelines):
```css
@import url('https://fonts.googleapis.com/css2?family=Roboto&display=swap');

.GMP-attribution {
  font-family: Roboto, Sans-Serif;
  font-style: normal;
  font-weight: 400;
  font-size: 1rem;
  letter-spacing: normal;
  white-space: nowrap;
  color: #5e5e5e;
  text-decoration: none;
}

.GMP-attribution:hover {
  color: #1F1F1F;
}
```

---

## Cost Optimization Strategies

### Strategy 1: Claim-Level Caching

```python
class GroundingCache:
    def __init__(self):
        self.cache = {}
    
    def get_cache_key(self, claim, location):
        """
        Create cache key from claim pattern + general location
        """
        # Normalize location to neighborhood level (not exact coords)
        neighborhood = resolve_to_neighborhood(location)
        claim_pattern = normalize_claim(claim.claim)  # Remove specifics
        
        return f"{neighborhood}:{claim.claim_type}:{claim_pattern}"
    
    async def get_or_ground(self, claim, location):
        cache_key = self.get_cache_key(claim, location)
        
        # Check cache
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if not is_stale(cached, max_age_days=30):
                return cached
        
        # Ground and cache
        grounded = await ground_with_maps(claim, location)
        self.cache[cache_key] = grounded
        return grounded
```

**Example**:
- "near subway" in "Williamsburg" → Cache key: `williamsburg:transport:near_subway`
- Cached for 90 days (stations don't change)
- All Williamsburg listings reuse this grounding

### Strategy 2: Progressive Grounding

```python
async def index_with_progressive_grounding(listing):
    """
    Ground high-value claims first, skip rest if quota reached
    """
    claims = await aggregate_claims(listing)
    
    # Sort by grounding value
    groundable = sorted(
        [c for c in claims if should_ground(c)],
        key=lambda c: calculate_grounding_value(c),
        reverse=True
    )
    
    # Ground top 3 highest-value claims only
    grounded_count = 0
    max_groundings_per_listing = 3
    
    for claim in groundable:
        if grounded_count >= max_groundings_per_listing:
            break
        
        verified = await ground_claim(claim)
        if verified:
            claims.extend(verified)
            grounded_count += 1
    
    return claims
```

**Cost per Listing**: Max 3 grounding calls = $0.075

### Strategy 3: Conditional Search Grounding

Only ground search queries when user explicitly needs it:

```python
async def search_with_conditional_grounding(query, user_location=None):
    """
    Ground search only for high-value scenarios
    """
    claims = await aggregate_search_claims(query)
    
    # Count how many claims would benefit from grounding
    groundable = [c for c in claims if should_ground_search_claim(c)]
    
    # Only ground if:
    # 1. User has ≥2 location/amenity requirements, OR
    # 2. User provided their location, OR  
    # 3. Query mentions specific businesses/landmarks
    should_ground_this_query = (
        len(groundable) >= 2 or
        user_location is not None or
        any(c.is_specific for c in groundable)
    )
    
    if should_ground_this_query:
        # Ground and enhance search
        geo_filters = await ground_location_claims(groundable, user_location)
        results = await search_with_geo_filters(claims, geo_filters)
    else:
        # Pure semantic search (no geo-filtering)
        results = await semantic_search(claims)
    
    return results
```

**Estimated Grounding Rate**: ~30-40% of search queries (only location-heavy queries)

### Strategy 4: Batch Neighborhood Pre-Analysis

For popular neighborhoods, pre-compute grounded claims:

```python
# One-time batch job for top 50 neighborhoods
POPULAR_NEIGHBORHOODS = ["Williamsburg", "Park Slope", "Astoria", ...]

async def precompute_neighborhood_grounding():
    """
    Run once, cache for 30 days
    """
    for neighborhood in POPULAR_NEIGHBORHOODS:
        # Ground standard amenity claims
        grounded = await ground_with_maps(f"""
        Analyze {neighborhood}:
        - Safety rating and evidence
        - Top amenities (coffee, restaurants, parks)
        - Transport access (subway stations with distances)
        - Neighborhood vibe keywords
        """, location=get_neighborhood_center(neighborhood))
        
        # Store in cache
        cache.set(f"neighborhood:{neighborhood}:grounded", grounded, ttl=30*86400)

# Cost: 50 neighborhoods × 1 call = $1.25 (one-time per month)
```

**Usage**: When indexing/searching in pre-computed neighborhood, reuse cached grounding.

---

## Integration with Recursive Search

### Enhanced Phase 4: Recursive Search with Geo-Constraints

```python
async def recursive_search_with_grounding(embedded_claims, grounded_geo_filters):
    """
    Combine recursive domain search with geo-filtering from grounding
    """
    # Build msearch query
    queries = []
    
    # Room queries (no geo-filtering at room level)
    room_claims = [c for c in embedded_claims if c.domain == "room"]
    for claim in room_claims:
        queries.append(build_room_knn_query(claim))
    
    # Apartment queries WITH geo-filtering
    apartment_claims = [c for c in embedded_claims if c.domain == "apartment"]
    for claim in apartment_claims:
        query = build_apartment_knn_query(claim)
        
        # Add geo-filters from grounding
        if grounded_geo_filters:
            query["query"]["bool"]["filter"] = {
                "bool": {
                    "should": [
                        {"geo_distance": {"distance": f["radius"], "apartment_location": f["coords"]}}
                        for f in grounded_geo_filters
                    ],
                    "minimum_should_match": 1
                }
            }
        
        queries.append(query)
    
    # Neighborhood queries (semantic only, boundaries checked in apartment geo-filter)
    neighborhood_claims = [c for c in embedded_claims if c.domain == "neighborhood"]
    for claim in neighborhood_claims:
        queries.append(build_neighborhood_knn_query(claim))
    
    # Execute parallel
    results = await elasticsearch.msearch(queries)
    
    # Recursive filtering + geo-aware scoring
    return merge_results_with_geo_boost(results, grounded_geo_filters)
```

**Geo-Boost Scoring**:
```python
def calculate_geo_boost(apartment, grounded_filters):
    """
    Boost apartments closer to grounded amenities
    """
    if not grounded_filters:
        return 1.0
    
    min_distance = float('inf')
    for filter in grounded_filters:
        distance = haversine(apartment.location, filter.coords)
        min_distance = min(min_distance, distance)
    
    # Boost apartments closer to verified amenities
    # 0m = 1.2x, 500m = 1.0x, 1000m+ = 0.9x
    if min_distance < 200:
        return 1.2
    elif min_distance < 500:
        return 1.1
    elif min_distance < 1000:
        return 1.0
    else:
        return 0.9
```

---

## Best Practices

### 1. **Selective Grounding**
- Not every claim needs grounding
- Focus on location, transport, amenities, neighborhood vibe
- Skip apartment internals and room features (Maps has no data)

### 2. **Batch Where Possible**
- Combine multiple claims into one grounding call
- "Near subway + parks + coffee" → Single Maps query
- Saves cost and latency

### 3. **Cache Aggressively for Neighborhoods**
- Neighborhood-level grounding is reusable
- Cache by neighborhood + claim pattern
- TTL: 30-90 days depending on claim type

### 4. **Use Widget Tokens**
- Always enable widgets for grounded searches
- Enhances UX significantly
- No additional cost (included in grounding call)

### 5. **Geo-Filtering Strategy**
- Store `apartment_location` as geo_point in Elasticsearch
- Use geo_distance for radius searches
- Use geo_shape for neighborhood boundaries
- Combine with semantic kNN in bool query

### 6. **Trust Signals**
- Verified claims get weight boost (+0.1)
- Display "Verified with Google Maps" badge
- Show grounded sources with proper attribution

### 7. **Error Handling**
- Grounding may fail or return no results
- Fall back to semantic-only search
- Log grounding failures for analysis

### 8. **Monitor Costs**
- Track grounding invocation rate
- Set budget alerts
- Optimize trigger conditions based on ROI

---

## Attribution Requirements

Per [Google Maps Platform Terms](https://cloud.google.com/maps-platform/terms):

### Text Attribution
When displaying grounded sources:

```html
<div class="grounded-source">
  <img src="maps-favicon.png" alt="" width="16" height="16" />
  <a 
    href="{source.uri}" 
    target="_blank"
    class="GMP-attribution"
    translate="no">
    Google Maps
  </a>
  <span>{source.title}</span>
</div>
```

**Requirements**:
- Text "Google Maps" must not be modified, translated, or wrapped
- Font: Roboto or sans-serif, 12-16sp, normal weight
- Color: White, black (#1F1F1F), or gray (#5E5E5E)
- Attribute `translate="no"` to prevent translation
- Must be viewable within one user interaction

### Widget Attribution
Widgets handle attribution automatically - no additional requirements.

---

## Conclusion

Google Maps Grounding transforms the apartment search from purely semantic to **geo-semantic hybrid search**:

**Indexing Benefits**:
- Verify vague location claims with precise coordinates
- Discover amenities landlords mention but don't detail
- Validate neighborhood vibe from aggregated review data
- Create high-confidence verified claims

**Search Benefits**:
- Resolve user location queries to exact coordinates
- Find specific businesses user mentions
- Enable radius-based filtering for "near X" queries
- Return interactive widgets for neighborhood exploration

**Key Innovation**: Selective grounding based on claim value - not every claim needs Maps data, but when used correctly, it dramatically improves precision and user experience.

**Cost Management**: Through smart triggering, caching, and batching, grounding cost stays manageable (<$0.10 per listing, <$0.05 per search on average).

**User Experience**: Verified proximity, interactive exploration, and geo-filtered results create trust and reduce apartment search friction.

