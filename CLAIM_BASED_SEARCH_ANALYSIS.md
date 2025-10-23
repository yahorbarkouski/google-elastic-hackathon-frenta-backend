# Recursive Claim-Based Semantic Search Architecture

## Overview

This architecture implements a hierarchical claim-based semantic search system for apartment discovery. The core innovation combines two powerful concepts:

1. **Claim Decomposition**: Breaking down complex descriptions into atomic, structured "claims" matched semantically
2. **Recursive Domain Search**: Querying across hierarchical domains (Neighborhood → Apartment → Room) in parallel, then merging results with weighted scoring

### Core Philosophy

1. **Claim Atomicity**: Break down apartment descriptions and queries into atomic, verifiable statements
2. **Domain Hierarchy**: Model real-world entity relationships (neighborhoods contain apartments, apartments contain rooms)
3. **Recursive Search**: Search all relevant domains in parallel, filter up the hierarchy, merge scores
4. **Semantic Over Keyword**: Rely primarily on embedding-based similarity using Elasticsearch kNN
5. **Structured Intelligence**: Use LLMs to identify domains and extract structure from unstructured text
6. **Type-Based Matching**: Route claims by semantic type to improve precision
7. **Quantifier Separation**: Handle numeric/spatial constraints separately from semantic matching

### Architecture Goals

- Operate on embeddings primarily (minimal hardcoding)
- Parallel subdomain queries for performance
- Clean domain separation with explicit linking
- Leverage Elasticsearch best practices (kNN, multi-index, filtering)

---

## Domain Hierarchy

The architecture models three interconnected domains:

```
Neighborhood (e.g., "Williamsburg", "Brooklyn")
    ↓ contains
Apartment (e.g., "2BR loft at 123 Main St")
    ↓ contains
Room (e.g., "kitchen", "bedroom", "bathroom")
```

### Domain Linking Strategy

**Subdomain → Domain references** (upward pointers):
- Each `room` document contains `apartment_id`
- Each `apartment` document contains `neighborhood_id`

**Storage**: Three separate Elasticsearch indices:
- `rooms` index
- `apartments` index  
- `neighborhoods` index

This enables:
- Independent querying of each domain
- Parallel search execution across domains
- Efficient filtering up the hierarchy
- Domain-specific optimization (field mappings, analyzers)

---

## Claim Types & Domain Mapping

### Claim Type Taxonomy

The system uses **12 structured claim types** that apply across all domains. Each claim type has specific threshold tuning and expansion strategies.

#### 1. **location** (Threshold: 0.85)
**Covers**: Geographic locations, addresses, area names, proximity indicators

**Domain mapping**:
- Neighborhood: "located in Williamsburg", "Brooklyn area", "East Village"
- Apartment: "corner of 5th and Main", "123 Main Street"
- Room: ❌ (rooms don't have location claims)

**Query examples**:
- "apartment in Brooklyn"
- "near Central Park"
- "Williamsburg location"
- "downtown Manhattan"

**Expansion strategy**: Location hierarchy (Williamsburg → Brooklyn → NYC → New York State)

---

#### 2. **features** (Threshold: 0.75)
**Covers**: Physical characteristics, architectural details, distinctive attributes

**Domain mapping**:
- Neighborhood: "tree-lined streets", "historic architecture", "waterfront area"
- Apartment: "exposed brick", "high ceilings", "hardwood floors", "large windows", "balcony"
- Room: "walk-in closet", "bay window", "skylight", "built-in shelves"

**Query examples**:
- "high ceiling apartment"
- "exposed brick"
- "hardwood floors"
- "modern kitchen with island"
- "walk-in closet in bedroom"

**Expansion strategy**: Feature implications ("exposed brick" → "industrial style", "loft-style")

---

#### 3. **amenities** (Threshold: 0.70)
**Covers**: Services, facilities, convenience features

**Domain mapping**:
- Neighborhood: "good schools", "restaurants nearby", "parks", "shopping centers"
- Apartment: "doorman", "elevator", "washer/dryer in unit", "central AC", "dishwasher", "parking"
- Room: "ensuite bathroom", "private entrance"

**Query examples**:
- "doorman building"
- "washer/dryer in unit"
- "gym in building"
- "roof deck access"
- "24/7 concierge"

**Expansion strategy**: Service levels ("doorman" → "full-service building", "concierge", "attended lobby")

---

#### 4. **size** (Threshold: 0.80)
**Covers**: Dimensions, space descriptions, room counts, area measurements

**Domain mapping**:
- Neighborhood: ❌ (neighborhoods don't have size claims)
- Apartment: "2 bedroom", "1000 sq ft", "spacious", "studio apartment"
- Room: "12m² kitchen", "large bedroom", "compact bathroom", "oversized living room"

**Query examples**:
- "2 bedroom apartment"
- "spacious kitchen over 10m²"
- "large master bedroom"
- "1000+ sq ft"

**Expansion strategy**: Size qualifiers ("spacious" → "large", "generous", "ample space")

**Has quantifiers**: Almost always (bedroom counts, area measurements)

---

#### 5. **condition** (Threshold: 0.75)
**Covers**: Maintenance state, renovation status, age indicators

**Domain mapping**:
- Neighborhood: "gentrifying area", "well-maintained neighborhood"
- Apartment: "newly renovated", "gut renovated", "move-in ready", "pre-war building", "needs TLC"
- Room: "renovated kitchen", "updated bathroom", "original finishes"

**Query examples**:
- "newly renovated apartment"
- "pre-war building"
- "modern renovation"
- "updated kitchen"

**Expansion strategy**: Condition synonyms ("newly renovated" → "recently updated", "modern", "contemporary finishes")

---

#### 6. **pricing** (Threshold: 0.85)
**Covers**: Rent, fees, deposits, pricing descriptors

**Domain mapping**:
- Neighborhood: "affordable area", "luxury neighborhood"
- Apartment: "rent $3,200/month", "under $4,000", "no broker fee", "1 month deposit"
- Room: ❌ (rooms don't have individual pricing)

**Query examples**:
- "rent under $3,500/month"
- "no broker fee"
- "affordable apartment"
- "luxury pricing"

**Expansion strategy**: Price ranges with margin ("$3,200" → "$3,000-$3,400" for APPROX)

**Has quantifiers**: Always (dollar amounts, percentages)

---

#### 7. **accessibility** (Threshold: 0.75)
**Covers**: Physical access, mobility features, building entry

**Domain mapping**:
- Neighborhood: "pedestrian-friendly", "bike lanes"
- Apartment: "elevator building", "ground floor", "wheelchair accessible", "no stairs"
- Room: "accessible bathroom", "wide doorways"

**Query examples**:
- "elevator building"
- "ground floor apartment"
- "wheelchair accessible"
- "no walk-up"

**Expansion strategy**: Accessibility implications ("elevator building" → "no stairs", "accessible to all floors")

---

#### 8. **policies** (Threshold: 0.80)
**Covers**: Rules, restrictions, allowances

**Domain mapping**:
- Neighborhood: ❌ (neighborhoods don't have policy claims)
- Apartment: "pets allowed", "no smoking", "subletting permitted", "short-term rentals OK"
- Room: ❌ (rooms don't have individual policies)

**Query examples**:
- "pet-friendly apartment"
- "dogs allowed"
- "no smoking building"
- "subletting allowed"

**Expansion strategy**: Policy synonyms ("pets allowed" → "pet-friendly", "dogs OK", "cats welcome")

**Anti-claims common**: "no pets allowed" for exclusion

---

#### 9. **utilities** (Threshold: 0.75)
**Covers**: Included services, heating/cooling, internet, electricity

**Domain mapping**:
- Neighborhood: ❌
- Apartment: "utilities included", "heat included", "central AC", "gas heat", "high-speed internet"
- Room: "radiator heating", "window AC unit"

**Query examples**:
- "utilities included"
- "central air conditioning"
- "gas heating"
- "heat and hot water included"

**Expansion strategy**: Utility details ("central AC" → "air conditioning", "climate control", "cooling system")

---

#### 10. **transport** (Threshold: 0.75)
**Covers**: Commute access, public transit, parking, distances to transit

**Domain mapping**:
- Neighborhood: "near subway", "multiple train lines", "bus routes", "walkable area"
- Apartment: "5 min walk to L train", "parking spot included", "bike storage"
- Room: ❌

**Query examples**:
- "close to subway"
- "5 minute walk to L train"
- "parking included"
- "near express bus"

**Expansion strategy**: Transport modes ("5 min to subway" → "close to public transit", "convenient commute")

**Has quantifiers**: Often (distances, walk times)

---

#### 11. **neighborhood** (Threshold: 0.73)
**Covers**: Vibe, character, lifestyle, community attributes

**Domain mapping**:
- Neighborhood: "quiet area", "trendy neighborhood", "nightlife", "family-friendly", "artistic community"
- Apartment: ❌ (apartment-specific, not neighborhood description)
- Room: ❌

**Query examples**:
- "quiet neighborhood"
- "trendy area with restaurants"
- "family-friendly community"
- "nightlife nearby"

**Expansion strategy**: Vibe synonyms ("trendy" → "hip", "up-and-coming", "popular", "vibrant")

---

#### 12. **restrictions** (Threshold: 0.80)
**Covers**: Lease terms, requirements, limitations

**Domain mapping**:
- Neighborhood: ❌
- Apartment: "12 month minimum lease", "no students", "guarantor required", "income 40x rent"
- Room: ❌

**Query examples**:
- "month-to-month lease"
- "flexible lease terms"
- "no guarantor required"

**Expansion strategy**: Restriction formality ("12 month lease" → "annual commitment", "1-year term")

**Has quantifiers**: Often (lease duration, income requirements)

---

### Domain-Specific Claim Type Distribution

**Neighborhood domain** typically has:
- location (primary)
- neighborhood (primary)
- transport (secondary)
- features (secondary)
- amenities (secondary)

**Apartment domain** typically has:
- size (primary)
- features (primary)
- amenities (primary)
- pricing (primary)
- condition (secondary)
- policies (secondary)
- utilities (secondary)
- accessibility (secondary)
- restrictions (secondary)

**Room domain** typically has:
- size (primary)
- features (primary)
- amenities (secondary)
- condition (secondary)

---

### LLM Prompt for Claim Type Extraction

The following prompt is used during **Phase 1: Domain-Aware Claim Aggregation** for both indexing and search:

```
You are an expert at extracting structured claims from apartment listings and search queries.

Extract atomic facts and automatically identify:
1. The CLAIM TYPE (from the taxonomy below)
2. The DOMAIN (neighborhood, apartment, or room)
3. For room domain: the ROOM_TYPE (kitchen, bedroom, bathroom, living_room, etc.)

<claim_types>
LOCATION (0.85): Geographic locations, addresses, area names
- Examples: "located in Williamsburg", "near Central Park", "Brooklyn area"
- Domain: neighborhood (primary), apartment (secondary)

FEATURES (0.75): Physical characteristics, architectural details
- Examples: "exposed brick", "high ceilings", "walk-in closet", "hardwood floors"
- Domain: all (context-dependent)

AMENITIES (0.70): Services, facilities, convenience features  
- Examples: "doorman", "washer/dryer in unit", "ensuite bathroom", "roof deck"
- Domain: all (context-dependent)

SIZE (0.80): Dimensions, space descriptions, room counts
- Examples: "2 bedroom", "12m² kitchen", "spacious", "1000 sq ft"
- Domain: apartment, room
- Has quantifiers: almost always

CONDITION (0.75): Maintenance state, renovation status, age
- Examples: "newly renovated", "pre-war building", "move-in ready"
- Domain: apartment (primary), room (secondary)

PRICING (0.85): Rent, fees, deposits, pricing descriptors
- Examples: "rent $3,200/month", "no broker fee", "under $4,000"
- Domain: apartment only
- Has quantifiers: always

ACCESSIBILITY (0.75): Physical access, mobility features
- Examples: "elevator building", "ground floor", "wheelchair accessible"
- Domain: apartment (primary), room (secondary)

POLICIES (0.80): Rules, restrictions, allowances
- Examples: "pets allowed", "no smoking", "subletting permitted"
- Domain: apartment only

UTILITIES (0.75): Included services, heating/cooling
- Examples: "utilities included", "central AC", "heat included"
- Domain: apartment (primary), room (secondary)

TRANSPORT (0.75): Commute access, public transit, parking
- Examples: "5 min walk to L train", "parking included", "near subway"
- Domain: neighborhood (primary), apartment (secondary)
- Has quantifiers: often

NEIGHBORHOOD (0.73): Vibe, character, lifestyle
- Examples: "quiet area", "trendy neighborhood", "nightlife", "family-friendly"
- Domain: neighborhood only

RESTRICTIONS (0.80): Lease terms, requirements, limitations
- Examples: "12 month minimum lease", "guarantor required", "income 40x rent"  
- Domain: apartment only
- Has quantifiers: often
</claim_types>

<domain_rules>
DOMAIN IDENTIFICATION:
- If claim is about area character, location, or commute → "neighborhood"
- If claim is about building, unit features, policies, pricing → "apartment"
- If claim explicitly mentions a room type AND describes that specific room → "room"

ROOM TYPE EXTRACTION (only for room domain):
- kitchen, bedroom, bathroom, living_room, dining_room, office, closet, balcony, outdoor_space

AMBIGUOUS CASES:
- "5 min to subway" → neighborhood (transport)
- "parking spot" → apartment (amenities)
- "spacious kitchen 12m²" → room (size) with room_type: kitchen
- "2 bedroom" → apartment (size)
- "exposed brick" without context → apartment (features)
- "exposed brick in living room" → room (features) with room_type: living_room
</domain_rules>

<output_format>
Return ONLY valid JSON array with this structure:
{
  "claims": [
    {
      "claim": "exposed brick walls",
      "claim_type": "features",
      "domain": "apartment",
      "is_specific": false,
      "has_quantifiers": false
    },
    {
      "claim": "kitchen area 12m²",
      "claim_type": "size",
      "domain": "room",
      "room_type": "kitchen",
      "is_specific": false,
      "has_quantifiers": true
    },
    {
      "claim": "located in Williamsburg",
      "claim_type": "location",
      "domain": "neighborhood",
      "is_specific": true,
      "has_quantifiers": false
    }
  ]
}

RULES:
- Write claims concisely, one fact per claim
- Use lowercase except for proper nouns (Williamsburg, Brooklyn)
- Set has_quantifiers=true if claim contains numbers, measurements, time periods
- Set is_specific=true if claim contains named entities (specific neighborhoods, streets)
- Always assign domain field (neighborhood/apartment/room)
- For room domain, always include room_type field
</output_format>

<examples>
Input: "Spacious 2BR in Williamsburg with modern 15m² kitchen, exposed brick, doorman, $3,500/mo"

Output:
{
  "claims": [
    {
      "claim": "2 bedroom apartment",
      "claim_type": "size",
      "domain": "apartment",
      "has_quantifiers": true
    },
    {
      "claim": "spacious apartment",
      "claim_type": "size",
      "domain": "apartment"
    },
    {
      "claim": "located in Williamsburg",
      "claim_type": "location",
      "domain": "neighborhood",
      "is_specific": true
    },
    {
      "claim": "modern kitchen",
      "claim_type": "features",
      "domain": "room",
      "room_type": "kitchen"
    },
    {
      "claim": "kitchen area 15m²",
      "claim_type": "size",
      "domain": "room",
      "room_type": "kitchen",
      "has_quantifiers": true
    },
    {
      "claim": "exposed brick walls",
      "claim_type": "features",
      "domain": "apartment"
    },
    {
      "claim": "doorman building",
      "claim_type": "amenities",
      "domain": "apartment"
    },
    {
      "claim": "monthly rent $3,500",
      "claim_type": "pricing",
      "domain": "apartment",
      "has_quantifiers": true
    }
  ]
}
</examples>

Extract claims from: {user_input}
```

---

## Indexing Pipeline

The indexing pipeline transforms raw apartment listings into searchable claim embeddings stored across Elasticsearch indices.

### Phase 1: Domain-Aware Claim Aggregation

**Input**: Raw apartment listing text
**Output**: Structured claims with domain labels and metadata

Uses an LLM to extract atomic facts and **automatically identify which domain** each claim belongs to:

```json
{
  "claims": [
    {
      "claim": "located in Williamsburg",
      "claim_type": "location",
      "domain": "neighborhood",
      "is_specific": true
    },
    {
      "claim": "2 bedroom apartment",
      "claim_type": "size", 
      "domain": "apartment",
      "has_quantifiers": true
    },
    {
      "claim": "exposed brick walls",
      "claim_type": "features",
      "domain": "apartment"
    },
    {
      "claim": "kitchen area 12m²",
      "claim_type": "size",
      "domain": "room",
      "room_type": "kitchen",
      "has_quantifiers": true
    },
    {
      "claim": "stainless steel appliances",
      "claim_type": "features",
      "domain": "room",
      "room_type": "kitchen"
    }
  ]
}
```

**Key Features**:
- **Domain Identification**: LLM automatically assigns `domain` field (neighborhood/apartment/room)
- **Room Type Extraction**: For room domain, extracts `room_type` (kitchen, bedroom, bathroom, living room)
- **Claim Types**: Structured types (location, features, amenities, size, condition, pricing, accessibility, policies, utilities, transport, neighborhood, restrictions)
- **Quantifier Flagging**: Marks claims with numbers, areas, distances, prices
- **Normalization**: Consistent naming (sq ft vs m², subway vs train, etc.)

### Phase 2: Claim Deduplication

**Input**: Claims from multiple listing sources
**Output**: Deduplicated claim set per entity

Deduplicates claims within each domain:
- Apartment-level: Remove duplicate features, amenities from multiple listing platforms
- Room-level: Deduplicate room-specific claims when rooms are listed multiple times
- Keeps most recent or most detailed version of duplicate claims

### Phase 3: Domain-Specific Claim Expansion

**Input**: Base claims (grouped by domain)
**Output**: Expanded claims with variations

Generates semantic variations **within each domain** for better recall:

**Neighborhood Domain**:
```json
{
  "claims": [
    {
      "claim": "located in Williamsburg",
      "kind": "base",
      "domain": "neighborhood"
    },
    {
      "claim": "located in Brooklyn",
      "kind": "derived",
      "from_claim": "located in Williamsburg",
      "domain": "neighborhood"
    },
    {
      "claim": "trendy neighborhood",
      "kind": "derived",
      "from_claim": "located in Williamsburg",
      "domain": "neighborhood"
    }
  ]
}
```

**Apartment Domain**:
```json
{
  "claim": "doorman building",
  "expansions": ["full-service building", "luxury amenities", "concierge service"]
}
```

**Room Domain**:
```json
{
  "claim": "spacious kitchen",
  "expansions": ["large kitchen", "generous cooking area", "ample kitchen space"]
}
```

**Expansion Strategies**:
- **Synonym Generation**: "doorman" → "concierge", "full-service"
- **Generalization**: "Williamsburg" → "Brooklyn" → "NYC"
- **Category Facts**: "pre-war building" → "historic architecture", "high ceilings"
- **Feature Implications**: "chef's kitchen" → "gas stove", "large kitchen"

**Claim Kinds**:
- `base`: Original claim from aggregation
- `derived`: Semantic variation for recall
- `anti`: Negative evidence (e.g., "no pets allowed" for pet-friendly searches)

### Phase 4: Quantifier Extraction

**Input**: Claims (both base and derived)
**Output**: Claims with structured quantifiers

Extracts numeric/spatial/temporal constraints into structured format:

```python
{
  "claim": "kitchen area 12m²",
  "quantified_claim": "kitchen area VAR_1",
  "quantifiers": [
    {
      "qtype": "area",
      "noun": "kitchen",
      "vmin": 12.0,
      "vmax": 12.0,
      "op": QuantifierOp.APPROX,
      "unit": "sqm"
    }
  ]
}

{
  "claim": "monthly rent under $3500",
  "quantified_claim": "monthly rent VAR_1",
  "quantifiers": [
    {
      "qtype": "money",
      "noun": "rent",
      "vmin": 0,
      "vmax": 3500,
      "op": QuantifierOp.LTE
    }
  ]
}

{
  "claim": "5 min walk to subway",
  "quantified_claim": "VAR_1 walk to subway",
  "quantifiers": [
    {
      "qtype": "distance",
      "noun": "subway",
      "vmin": 300,
      "vmax": 500,
      "op": QuantifierOp.APPROX,
      "unit": "meters"
    }
  ]
}
```

**Quantifier Types**:
- `money`: Prices (rent, fees, deposits) in USD
- `area`: Room/apartment sizes in square meters or feet
- `count`: Bedrooms, bathrooms, rooms
- `distance`: Walking distance, proximity in meters
- `duration`: Lease terms, availability dates

**Operators**: `EQUALS`, `GT`, `GTE`, `LT`, `LTE`, `APPROX`, `RANGE`

**Strategy**: Quantifiers are extracted but the quantified claim text (with variables) is used for embedding to generalize numeric patterns. Original values stored separately for filtering.

### Phase 5: Claim Embedding

**Input**: Claims with quantifiers (grouped by domain)
**Output**: Embedded claims with vectors

Generates embeddings for semantic matching:

```python
{
  "claim": "kitchen area VAR_1",  # Uses quantified version
  "embedding": [0.123, -0.456, ...],  # 768-dim vector
  "quantifiers": [...],
  "domain": "room",
  "room_type": "kitchen",
  "kind": "base"
}
```

**Embedding Model**:
- **Text Embedding Model**: 768 dimensions (e.g., text-embedding-3-large, multilingual-e5-large)
- Same model for all domains for consistent semantic space

**Key Decisions**:
- Uses quantified claim text for embedding (generalizes numbers)
- Preserves quantifiers separately for filtering
- Same embedding model across all domains

### Phase 6: Elasticsearch Indexing

**Input**: Embedded claims grouped by domain
**Output**: Claims indexed across three Elasticsearch indices

Stores claims in separate indices with domain-specific schemas:

**Rooms Index** (`rooms`):
```json
{
  "mappings": {
    "properties": {
      "room_id": {"type": "keyword"},
      "apartment_id": {"type": "keyword"},
      "room_type": {"type": "keyword"},
      "claim": {"type": "text"},
      "claim_type": {"type": "keyword"},
      "kind": {"type": "keyword"},
      "from_claim": {"type": "text"},
      "is_specific": {"type": "boolean"},
      "claim_vector": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine",
        "index_options": {"type": "hnsw", "m": 16, "ef_construction": 200}
      },
      "quantifiers": {"type": "nested"},
      "source_url": {"type": "keyword"}
    }
  }
}
```

**Apartments Index** (`apartments`):
```json
{
  "mappings": {
    "properties": {
      "apartment_id": {"type": "keyword"},
      "neighborhood_id": {"type": "keyword"},
      "claim": {"type": "text"},
      "claim_type": {"type": "keyword"},
      "kind": {"type": "keyword"},
      "claim_vector": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine",
        "index_options": {"type": "hnsw", "m": 16, "ef_construction": 200}
      },
      "quantifiers": {"type": "nested"},
      "is_specific": {"type": "boolean"}
    }
  }
}
```

**Neighborhoods Index** (`neighborhoods`):
```json
{
  "mappings": {
    "properties": {
      "neighborhood_id": {"type": "keyword"},
      "claim": {"type": "text"},
      "claim_type": {"type": "keyword"},
      "claim_vector": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine",
        "index_options": {"type": "hnsw"}
      }
    }
  }
}
```

**HNSW Configuration Best Practices**:
- `m: 16`: Good balance of recall/speed (Elasticsearch default is 16, can go to 32 for higher recall)
- `ef_construction: 200`: Quality of index build (higher = better recall, slower indexing)
- `similarity: cosine`: Cosine similarity for normalized vectors
- `index: true`: Enable HNSW indexing for kNN search

**Quantifiers as Nested Objects**:
```json
{
  "quantifiers": [
    {
      "qtype": "area",
      "noun": "kitchen",
      "vmin": 12.0,
      "vmax": 12.0,
      "op": 5
    }
  ]
}
```

---

## Recursive Semantic Search Pipeline

The search pipeline transforms natural language queries into ranked apartment results using **recursive domain search** - searching across the hierarchy in parallel then merging scores.

### Phase 1: Domain-Aware Search Claim Aggregation

**Input**: Natural language query
**Output**: Structured search claims with **domains** and **weights**

LLM extracts claims and **automatically identifies which domain** each belongs to:

**Example Query**:
```
"High ceiling apartment with >10m² kitchen in trendy Brooklyn neighborhood"
```

**Aggregated Claims**:
```json
{
  "claims": [
    {
      "claim": "high ceiling",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.75
    },
    {
      "claim": "kitchen area >10m²",
      "claim_type": "size",
      "domain": "room",
      "room_type": "kitchen",
      "weight": 0.85,
      "has_quantifiers": true
    },
    {
      "claim": "trendy neighborhood",
      "claim_type": "neighborhood_character",
      "domain": "neighborhood",
      "weight": 0.7
    },
    {
      "claim": "located in Brooklyn",
      "claim_type": "location",
      "domain": "neighborhood",
      "weight": 0.8
    }
  ]
}
```

**Weight Assignment Strategy**:
- Base weight: 0.7
- Hard requirements (size, price, location): 0.85-0.95
- Features (amenities, condition): 0.7-0.8
- Soft preferences (neighborhood vibe): 0.6-0.7
- Quantified claims: +0.1 boost
- Negated claims: +0.1 boost (user is specific about what they don't want)

**Domain Distribution**:
The claims are automatically grouped:
- **Neighborhood**: 2 claims (trendy, Brooklyn)
- **Apartment**: 1 claim (high ceiling)
- **Room**: 1 claim (kitchen >10m²)

### Phase 2: Quantifier Extraction

**Input**: Search claims
**Output**: Search claims with quantifier constraints

Extracts numeric/spatial constraints from search claims:

```python
{
  "claim": "kitchen area >10m²",
  "quantified_claim": "kitchen area VAR_1",
  "domain": "room",
  "room_type": "kitchen",
  "quantifiers": [
    {
      "qtype": "area",
      "noun": "kitchen",
      "vmin": 10.0,
      "vmax": float('inf'),
      "op": QuantifierOp.GT,
      "unit": "sqm"
    }
  ],
  "weight": 0.85
}
```

**Purpose**: Separate semantic matching from numeric filtering. The quantified claim is embedded, quantifiers become Elasticsearch filters.

### Phase 3: Claim Embedding

**Input**: Search claims with quantifiers
**Output**: Embedded search claims (grouped by domain)

Embeds search claims using the same model as indexing:

```python
{
  "claim": "kitchen area VAR_1",
  "embedding": [0.234, -0.567, ...],
  "domain": "room",
  "room_type": "kitchen",
  "weight": 0.85,
  "quantifiers": [...]
}
```

Claims are now ready for domain-specific kNN search.

### Phase 4: Parallel Recursive Domain Search

**Input**: Embedded search claims (grouped by domain)
**Output**: Domain-specific matches with entity IDs

This is the **core innovation**: searches happen in parallel across domain indices, results are filtered up the hierarchy, then merged.

#### Step 1: Parallel kNN Queries

Use Elasticsearch `_msearch` API to query multiple indices in parallel:

```json
POST /_msearch
{}
{"index": "rooms"}
{
  "knn": {
    "field": "claim_vector",
    "query_vector": [0.234, -0.567, ...],
    "k": 100,
    "num_candidates": 500,
    "filter": {
      "bool": {
        "must": [
          {"term": {"room_type": "kitchen"}},
          {"term": {"claim_type": "size"}}
        ],
        "filter": {
          "nested": {
            "path": "quantifiers",
            "query": {
              "bool": {
                "must": [
                  {"term": {"quantifiers.qtype": "area"}},
                  {"range": {"quantifiers.vmin": {"lte": 10.0}}},
                  {"range": {"quantifiers.vmax": {"gte": 10.0}}}
                ]
              }
            }
          }
        }
      }
    }
  },
  "_source": ["room_id", "apartment_id", "claim", "kind"],
  "size": 100
}
{}
{"index": "apartments"}
{
  "knn": {
    "field": "claim_vector",
    "query_vector": [0.123, -0.456, ...],
    "k": 200,
    "num_candidates": 500,
    "filter": {
      "term": {"claim_type": "features"}
    }
  },
  "_source": ["apartment_id", "neighborhood_id", "claim", "kind"],
  "size": 200
}
{}
{"index": "neighborhoods"}
{
  "knn": {
    "field": "claim_vector",
    "query_vector": [0.345, -0.678, ...],
    "k": 50,
    "num_candidates": 200,
    "filter": {
      "term": {"claim_type": "location"}
    }
  },
  "_source": ["neighborhood_id", "claim"],
  "size": 50
}
```

**Query Parameters**:
- `k`: Number of neighbors to return
- `num_candidates`: HNSW search candidates (higher = better recall, slower)
- `filter`: Pre-filter before kNN (more efficient than post-filter)
- `_source`: Only return needed fields

**Parallel Execution**: All three queries execute simultaneously via `_msearch`.

#### Step 2: Extract Entity IDs from Results

From the parallel queries, extract unique entity IDs:

```python
# Room query results
room_matches = [
  {"apartment_id": "apt_123", "room_id": "room_1", "score": 0.92},
  {"apartment_id": "apt_456", "room_id": "room_2", "score": 0.88},
  ...
]
apartment_ids_from_rooms = ["apt_123", "apt_456", ...]  # Filter apartments by these

# Apartment query results  
apartment_matches = [
  {"apartment_id": "apt_123", "neighborhood_id": "nbh_1", "score": 0.85},
  {"apartment_id": "apt_789", "neighborhood_id": "nbh_2", "score": 0.80},
  ...
]
neighborhood_ids_from_apartments = ["nbh_1", "nbh_2", ...]

# Neighborhood query results
neighborhood_matches = [
  {"neighborhood_id": "nbh_1", "score": 0.90},
  {"neighborhood_id": "nbh_3", "score": 0.87},
  ...
]
```

#### Step 3: Recursive Filtering (Up the Hierarchy)

Filter results by intersecting with parent domain results:

```python
# Filter apartments: Keep only apartments that:
# 1. Match apartment-level claims (from apartment query)
# 2. Have rooms that match room-level claims (from room query)
# 3. Are in neighborhoods that match neighborhood claims (from neighborhood query)

valid_apartment_ids = (
    set(apartment_ids_from_rooms) &           # Has matching rooms
    {m["apartment_id"] for m in apartment_matches} &  # Matches apartment claims
    {m["apartment_id"] for m in apartment_matches 
     if m["neighborhood_id"] in {n["neighborhood_id"] for n in neighborhood_matches}}  # In matching neighborhood
)

# Final result: Apartments that satisfy ALL domain requirements
filtered_apartments = [m for m in apartment_matches if m["apartment_id"] in valid_apartment_ids]
```

**Key Insight**: Only apartments that have:
- Matching rooms (kitchen >10m²)
- Matching apartment features (high ceiling)
- Matching neighborhood (Brooklyn, trendy)

...will be included in final results.

#### Step 4: Threshold Filtering & Anti-Claim Handling

Apply dynamic thresholds per claim type:

```python
# Dynamic thresholds
CLAIM_TYPE_THRESHOLDS = {
    "location": 0.85,
    "size": 0.80,
    "features": 0.75,
    "pricing": 0.85,
    "amenities": 0.70,
}

# Filter by threshold
def filter_by_threshold(matches, claim_type):
    threshold = CLAIM_TYPE_THRESHOLDS.get(claim_type, 0.75)
    return [m for m in matches if m["score"] >= threshold]

# Handle anti-claims (negation)
def apply_anti_penalty(match, search_negation):
    if match["kind"] == "anti":
        if search_negation:
            return 1.0  # User wants "not X", evidence is anti-X (match!)
        else:
            return 0.1  # User wants X, evidence is anti-X (penalty)
    else:
        if search_negation:
            return 0.0  # User wants "not X", evidence is X (exclude)
        else:
            return 1.0  # Normal positive match
```

### Phase 5: Weighted Domain Score Merging

**Input**: Claim matches from multiple domains (filtered)
**Output**: Ranked apartment results with merged scores

Aggregates scores across domains using weighted combination:

#### Domain Weight Configuration

Define relative importance of each domain:

```python
DOMAIN_WEIGHTS = {
    "room": 0.35,          # Room-level requirements are important
    "apartment": 0.40,     # Apartment features are most important
    "neighborhood": 0.25   # Neighborhood is secondary
}
```

These weights are **configurable per query** based on claim distribution or can be learned.

#### Per-Domain Score Calculation

For each domain, calculate aggregated score:

```python
def calculate_domain_score(matches, search_claims):
    """
    Calculate score for a single domain (e.g., all room matches for an apartment)
    """
    total_weighted_score = 0.0
    total_possible_weight = 0.0
    
    # Group matches by search claim
    for search_claim in search_claims:
        claim_matches = [m for m in matches if m["search_claim"] == search_claim["claim"]]
        
        if claim_matches:
            # Apply diminishing returns for multiple matches of same claim
            sorted_matches = sorted(claim_matches, key=lambda x: x["score"], reverse=True)
            claim_score = 0.0
            weights_sum = 0.0
            
            for i, match in enumerate(sorted_matches[:4]):  # Top 4 matches
                diminishing_weight = 1.0 / (2 ** i)  # 1.0, 0.5, 0.25, 0.125
                claim_score += match["score"] * diminishing_weight
                weights_sum += diminishing_weight
            
            claim_score = claim_score / weights_sum if weights_sum > 0 else 0.0
            total_weighted_score += claim_score * search_claim["weight"]
        
        total_possible_weight += search_claim["weight"]
    
    return total_weighted_score / total_possible_weight if total_possible_weight > 0 else 0.0
```

#### Cross-Domain Weighted Merging

Combine scores from all domains:

```python
def calculate_final_apartment_score(apartment_id, domain_matches, search_claims_by_domain):
    """
    Merge scores across room, apartment, and neighborhood domains
    """
    domain_scores = {}
    
    # Calculate score for each domain
    for domain in ["room", "apartment", "neighborhood"]:
        matches = domain_matches[domain].get(apartment_id, [])
        search_claims = search_claims_by_domain[domain]
        domain_scores[domain] = calculate_domain_score(matches, search_claims)
    
    # Weighted combination
    final_score = (
        DOMAIN_WEIGHTS["room"] * domain_scores["room"] +
        DOMAIN_WEIGHTS["apartment"] * domain_scores["apartment"] +
        DOMAIN_WEIGHTS["neighborhood"] * domain_scores["neighborhood"]
    )
    
    return final_score
```

#### Coverage & Confidence Calculation

```python
def calculate_coverage_and_confidence(apartment_id, domain_matches, search_claims_by_domain):
    """
    Calculate coverage (how many query aspects satisfied) and confidence
    """
    satisfied_claims = 0
    total_claims = sum(len(claims) for claims in search_claims_by_domain.values())
    total_weight_satisfied = 0.0
    total_weight = 0.0
    
    for domain, search_claims in search_claims_by_domain.items():
        for claim in search_claims:
            total_weight += claim["weight"]
            matches = [m for m in domain_matches[domain].get(apartment_id, []) 
                      if m["search_claim"] == claim["claim"]]
            
            # Check if claim is satisfied (has at least one good match)
            if any(m["score"] >= CLAIM_TYPE_THRESHOLDS.get(m["claim_type"], 0.75) for m in matches):
                satisfied_claims += 1
                total_weight_satisfied += claim["weight"]
    
    coverage_ratio = satisfied_claims / total_claims if total_claims > 0 else 0.0
    weight_coverage = total_weight_satisfied / total_weight if total_weight > 0 else 0.0
    
    return {
        "coverage_count": satisfied_claims,
        "coverage_ratio": coverage_ratio,
        "weight_coverage": weight_coverage
    }
```

#### Final Ranking

```python
# Rank apartments by weighted score and coverage
apartments_with_scores = []
for apartment_id in valid_apartment_ids:
    final_score = calculate_final_apartment_score(apartment_id, domain_matches, search_claims_by_domain)
    coverage = calculate_coverage_and_confidence(apartment_id, domain_matches, search_claims_by_domain)
    
    apartments_with_scores.append({
        "apartment_id": apartment_id,
        "final_score": final_score,
        "coverage_count": coverage["coverage_count"],
        "coverage_ratio": coverage["coverage_ratio"],
        "weight_coverage": coverage["weight_coverage"]
    })

# Sort by coverage first, then score
ranked_apartments = sorted(
    apartments_with_scores,
    key=lambda x: (x["coverage_count"], x["weight_coverage"], x["final_score"]),
    reverse=True
)
```

---

## Key Innovations

### 1. Recursive Domain Search
The architecture's **primary innovation**: Search across hierarchical domains in parallel, filter up the hierarchy, merge scores.

**How it works**:
- Query: "High ceiling apartment with >10m² kitchen in Brooklyn"
- Parallel kNN search: rooms index (kitchen claim), apartments index (high ceiling), neighborhoods index (Brooklyn)
- Filter apartments: Must have matching rooms AND match apartment claims AND be in matching neighborhood
- Score merging: Weighted combination across domains (room: 0.35, apartment: 0.40, neighborhood: 0.25)

**Benefits**:
- Natural modeling of real-world entity relationships
- Precise filtering (apartments without qualifying rooms are excluded)
- Parallel execution for speed
- Domain-specific tuning (different thresholds, expansions per domain)

### 2. Automatic Domain Identification
LLM automatically assigns domain labels during claim aggregation:
- No manual domain mapping required
- "kitchen area 12m²" → `domain: room`, `room_type: kitchen`
- "high ceiling" → `domain: apartment`
- "trendy neighborhood" → `domain: neighborhood`

Enables dynamic query decomposition without hardcoding.

### 3. Claim Atomicity
Breaking down listings and queries into atomic facts enables:
- Precise semantic matching at claim level
- Partial query satisfaction (coverage metrics)
- Explainable results (which specific claims matched)
- Domain-specific claim variations

### 4. Three-Tier Claim System
- **Base claims**: Original facts from listing
- **Derived claims**: Semantic variations for recall ("doorman" → "concierge", "full-service")
- **Anti-claims**: Negative evidence ("no pets allowed" for pet-friendly searches)

Balances precision (base) with recall (derived) while handling negation (anti).

### 5. Quantifier Separation
Separating numeric/spatial constraints from semantic matching:
- Semantic similarity: "kitchen area VAR_1" (generalizes the concept)
- Numeric filtering: Applied as Elasticsearch nested query filters
- Prevents embedding space pollution with specific numbers
- Example: ">10m² kitchen" → embedding for "kitchen area" + filter for area > 10

### 6. Multi-Index Elasticsearch Architecture
Uses separate indices for each domain:
- Independent HNSW tuning per domain
- Parallel `_msearch` queries
- Domain-specific schema optimization
- Clean separation of concerns

Better than nested documents or parent-child joins for this use case.

### 7. Weighted Domain Merging
Configurable domain importance:
```python
final_score = (
    0.35 * room_score +
    0.40 * apartment_score +
    0.25 * neighborhood_score
)
```

Allows queries to emphasize different aspects (room-focused vs neighborhood-focused).

### 8. Coverage-First Ranking
Prioritizes query satisfaction over individual claim scores:
- Apartments matching more query aspects rank higher
- Prevents single-dimension outliers from dominating
- Weighted coverage (important claims count more)
- More intuitive for complex multi-requirement queries

---

## Elasticsearch Implementation Summary

### Key Technical Details

**Three Separate Indices**:
- `rooms` - Room-level claims with `apartment_id` reference
- `apartments` - Apartment-level claims with `neighborhood_id` reference + **geo_point** for location
- `neighborhoods` - Neighborhood-level claims + **geo_shape** for boundaries

**HNSW Configuration**:
- `m: 16` - Links per node (can tune to 32 for higher recall)
- `ef_construction: 200` - Index build quality
- `similarity: cosine` - Normalized vector similarity
- 768-dimensional vectors

**Query Execution**:
- Use `_msearch` API for parallel domain queries
- Combine `knn` with `filter` for efficient constrained search
- Nested queries for quantifier filtering
- **Geo-spatial queries** for coordinate-based filtering (geo_distance, geo_shape)
- Pre-filter before kNN for better performance

**Linking Strategy**:
- Subdomain → Domain upward pointers
- Filter apartments by `apartment_id IN (room results)`
- Filter by `neighborhood_id IN (neighborhood results)`
- **Geo-filter** apartments by proximity to verified amenities/landmarks
- Set intersection for final valid apartments

### Google Maps Grounding Integration

The architecture integrates **Google Maps Grounding** to enhance both indexing and search with verified location data, amenity discovery, and coordinate-based filtering. This enables:

- **Verified Claims**: "near subway" → "350m to Bedford Ave L station" (with coordinates)
- **Amenity Discovery**: "good coffee shops" → Specific shops with ratings and locations
- **Geo-Filtering**: Search apartments within radius of verified amenities
- **Interactive Widgets**: Return map widgets for visual neighborhood exploration

See [**GOOGLE_MAPS_GROUNDING.md**](./GOOGLE_MAPS_GROUNDING.md) for complete integration guide, use cases, and implementation patterns.

---

## Architectural Strengths

**1. Explainability**:
- Every result shows which domain-level claims matched
- Trace back through room → apartment → neighborhood hierarchy
- Understand why apartments were included/excluded

**2. Composability**:
- Query complexity scales naturally
- Add more domains without changing search logic
- Independent domain tuning

**3. Precision**:
- Recursive filtering ensures ALL requirements met
- No apartments without qualifying rooms slip through
- Domain-specific thresholds

**4. Extensibility**:
- Adding new room types: just add room_type values
- New domains (building features?): add index + linking
- No changes to core search logic

**5. Parallel Execution**:
- All domain searches happen simultaneously
- Elasticsearch `_msearch` handles parallelism
- Fast even with complex multi-domain queries

---

## Architectural Tradeoffs

**1. LLM Dependency**:
- Domain identification relies on LLM quality
- Prompt engineering critical
- Consider caching aggregation results

**2. Index Coordination**:
- Must maintain referential integrity (apartment_id, neighborhood_id)
- Re-indexing requires coordination across indices
- Consider using Elasticsearch aliases for zero-downtime updates

**3. Threshold Tuning**:
- Multiple claim types × domains requires extensive evaluation
- Start with conservative thresholds, tune based on user feedback
- Consider per-domain threshold multipliers

**4. Expansion Overhead**:
- 3-5x claim multiplication increases storage
- More claims = slower indexing
- Balance recall needs vs storage/indexing cost

**5. Quantifier Extraction Reliability**:
- LLM may miss or misparse complex constraints
- Unit normalization challenging (m² vs sq ft)
- Consider validation layer for critical quantifiers (price, size)

---

## Implementation Best Practices

**1. Domain Identification**:
- Use few-shot examples in LLM prompts
- Validate domain assignments for key claim types
- Consider fallback heuristics (claim_type → domain mapping)

**2. Claim Expansion**:
- Start without expansion, add when recall issues identified
- Domain-specific expansion strategies
- Limit expansion depth to prevent drift

**3. Quantifier Handling**:
- Normalize units during extraction (always meters, always USD)
- Use APPROX operator generously (5 min → 4-6 min range)
- Test edge cases (">1M", "under $1K", etc.)

**4. Elasticsearch Tuning**:
- Start with `m:16`, increase to 32 if recall poor
- Use `num_candidates: 5-10x k` for good recall/speed balance
- Pre-filter aggressively (claim_type, room_type) before kNN
- Monitor Elasticsearch query latencies per domain

**5. Score Merging**:
- Make domain weights query-dependent:
  - Kitchen-focused query → higher room weight
  - Location-focused query → higher neighborhood weight
- Consider learning weights from user interaction data
- Provide manual weight override for power users

**6. Caching Strategy**:
- Cache claim aggregation results (LLM calls expensive)
- Cache quantifier extraction (LLM calls expensive)
- Cache embeddings for common claims
- Use Elasticsearch query cache for repeated patterns

**7. Iterative Development**:
- Start with 2 domains (apartment + room), add neighborhood later
- Begin with base claims only, add expansion once baseline works
- Add quantifiers incrementally by type (count → money → area → distance)
- Tune thresholds empirically using eval sets

---

## Example End-to-End Flow

**Query**: "Spacious 2BR with modern kitchen >12m² in Williamsburg under $4000"

**1. Claim Aggregation** (LLM):
```json
{
  "claims": [
    {"claim": "2 bedroom apartment", "domain": "apartment", "weight": 0.95},
    {"claim": "spacious apartment", "domain": "apartment", "weight": 0.7},
    {"claim": "modern kitchen", "domain": "room", "room_type": "kitchen", "weight": 0.75},
    {"claim": "kitchen area >12m²", "domain": "room", "room_type": "kitchen", "weight": 0.85},
    {"claim": "located in Williamsburg", "domain": "neighborhood", "weight": 0.8},
    {"claim": "monthly rent <$4000", "domain": "apartment", "weight": 0.9}
  ]
}
```

**2. Quantifier Extraction** (LLM):
- "kitchen area >12m²" → quantified_claim: "kitchen area VAR_1", quantifiers: [{qtype: "area", vmin: 12, vmax: inf, op: GT}]
- "monthly rent <$4000" → quantified_claim: "monthly rent VAR_1", quantifiers: [{qtype: "money", vmin: 0, vmax: 4000, op: LTE}]

**3. Embedding**:
- Generate 768-dim vectors for each claim (using quantified versions)

**4. Parallel kNN Search** (`_msearch`):
- Room index: Match "modern kitchen", "kitchen area >12m²" → [apt_1, apt_5, apt_12, ...]
- Apartment index: Match "2BR", "spacious", "rent <$4000" → [apt_1, apt_3, apt_5, apt_12, apt_20, ...]
- Neighborhood index: Match "Williamsburg" → [nbh_williamsburg]

**5. Recursive Filtering**:
```python
apartments_with_rooms = {apt_1, apt_5, apt_12}  # From room matches
apartments_matching = {apt_1, apt_3, apt_5, apt_12, apt_20}  # From apartment matches
apartments_in_williamsburg = {apt_1, apt_5, apt_12, apt_18, apt_20}  # From neighborhood

valid = {apt_1, apt_5, apt_12}  # Intersection
```

**6. Score Merging**:
```python
# apt_1 scores
room_score = 0.88  # kitchen matches well
apartment_score = 0.92  # 2BR + spacious + price matches
neighborhood_score = 0.95  # Williamsburg perfect match

final_score = 0.35 * 0.88 + 0.40 * 0.92 + 0.25 * 0.95
            = 0.308 + 0.368 + 0.238 = 0.914
```

**7. Ranking**:
- apt_1: score=0.914, coverage=6/6
- apt_5: score=0.875, coverage=5/6
- apt_12: score=0.820, coverage=5/6

**Result**: apt_1 ranked first (highest score + full coverage)

---

## Real-World Query Processing Examples

This section demonstrates how the system handles complex, nuanced real-world queries with multi-domain requirements, implicit preferences, and ambiguous phrasing.

### Query 1: "A quiet apartment facing a courtyard with big windows and morning sun, preferably on a higher floor."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "quiet apartment",
      "claim_type": "neighborhood",
      "domain": "neighborhood",
      "weight": 0.75
    },
    {
      "claim": "facing courtyard",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.70
    },
    {
      "claim": "big windows",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.65
    },
    {
      "claim": "morning sun exposure",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.70
    },
    {
      "claim": "higher floor",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.60
    }
  ]
}
```

**Tricky Cases Handled**:
1. **"quiet"** → Mapped to **neighborhood** domain (not apartment) because it describes the area character
2. **"morning sun"** → Apartment feature (not separated into room-level) because it affects the whole unit
3. **"preferably on higher floor"** → Lower weight (0.60) due to "preferably" soft language

**Recursive Search**:
- Neighborhood query: "quiet neighborhood" → Finds areas with low noise
- Apartment query: "courtyard facing", "big windows", "morning sun", "higher floor" → All apartment-level features
- No room-level queries (nothing room-specific)
- Filter: Apartments in quiet neighborhoods with matching features

---

### Query 2: "Small but well-designed studio with enough kitchen space for cooking daily and a balcony large enough for two chairs."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "studio apartment",
      "claim_type": "size",
      "domain": "apartment",
      "weight": 0.85
    },
    {
      "claim": "small apartment",
      "claim_type": "size",
      "domain": "apartment",
      "weight": 0.70
    },
    {
      "claim": "well-designed apartment",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.60
    },
    {
      "claim": "enough kitchen space for cooking",
      "claim_type": "size",
      "domain": "room",
      "room_type": "kitchen",
      "weight": 0.80
    },
    {
      "claim": "functional kitchen",
      "claim_type": "features",
      "domain": "room",
      "room_type": "kitchen",
      "weight": 0.75
    },
    {
      "claim": "balcony large enough for two chairs",
      "claim_type": "size",
      "domain": "room",
      "room_type": "balcony",
      "has_quantifiers": true,
      "weight": 0.70
    }
  ]
}
```

**Tricky Cases Handled**:
1. **"Small but well-designed"** → Two separate claims: size (negative) + features (positive)
2. **"enough kitchen space for cooking daily"** → Room-level size claim (kitchen domain) with implied functional requirement
3. **"balcony large enough for two chairs"** → Room domain (balcony is a room_type), has_quantifiers=true (implicit size)
4. **"well-designed"** → Subjective, mapped to generic "features" with lower weight (0.60)

**Recursive Search**:
- Room query: Kitchen size/functionality + balcony size → Get apartment_ids with qualifying kitchens AND balconies
- Apartment query: Studio, small, well-designed → Get apartment_ids
- Filter: Studio apartments (small) that have both functional kitchens AND appropriately-sized balconies

**Quantifier Extraction** (Phase 2):
```python
{
  "claim": "balcony large enough for two chairs",
  "quantified_claim": "balcony large enough for VAR_1 chairs",
  "quantifiers": [{
    "qtype": "area",  # Implicit - inferred from "large enough for 2 chairs"
    "noun": "balcony",
    "vmin": 4.0,  # ~4m² estimated minimum
    "vmax": float('inf'),
    "op": QuantifierOp.GTE
  }]
}
```

---

### Query 3: "Pet-friendly building near a park, not too old, with good soundproofing and natural light."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "pets allowed",
      "claim_type": "policies",
      "domain": "apartment",
      "weight": 0.90
    },
    {
      "claim": "near park",
      "claim_type": "amenities",
      "domain": "neighborhood",
      "weight": 0.75
    },
    {
      "claim": "recently built",
      "claim_type": "condition",
      "domain": "apartment",
      "weight": 0.65,
      "negation": true
    },
    {
      "claim": "good soundproofing",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.80
    },
    {
      "claim": "natural light",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.75
    }
  ]
}
```

**Tricky Cases Handled**:
1. **"pet-friendly building"** → Apartment domain (policies), not neighborhood
2. **"near a park"** → Neighborhood amenity, not apartment or room
3. **"not too old"** → Converted to positive claim "recently built" with negation=true and lower weight (0.65) for soft language
4. **"good soundproofing"** → Apartment-level feature (affects whole unit, not specific rooms)
5. **"natural light"** → Apartment-level (general characteristic, not room-specific)

**Anti-Claim Handling**:
During expansion, "recently built" with negation=true generates:
- Base: "recently built" (for semantic matching)
- Anti: "old building", "outdated construction"
- Search will prefer apartments WITHOUT anti-claims about age

**Recursive Search**:
- Neighborhood query: "near park" → Get neighborhoods with parks
- Apartment query: "pets allowed", "soundproofing", "natural light", "not old" → Get apartment_ids
- Filter: Pet-friendly apartments with soundproofing/light in park-adjacent neighborhoods

---

### Query 4: "One-bedroom apartment with a separate corner that can be used as a home office and strong internet connection."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "1 bedroom apartment",
      "claim_type": "size",
      "domain": "apartment",
      "has_quantifiers": true,
      "weight": 0.90
    },
    {
      "claim": "separate corner space",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.75
    },
    {
      "claim": "home office space",
      "claim_type": "features",
      "domain": "room",
      "room_type": "office",
      "weight": 0.80
    },
    {
      "claim": "strong internet connection",
      "claim_type": "utilities",
      "domain": "apartment",
      "weight": 0.70
    }
  ]
}
```

**Tricky Cases Handled**:
1. **"separate corner that can be used as home office"** → Two claims:
   - Apartment feature: "separate corner space" (layout characteristic)
   - Room domain: "home office space" (functional room requirement)
2. **"strong internet"** → Utilities (not amenities) because it's a service characteristic
3. **Implicit flexibility**: "can be used as" suggests the space doesn't need to be a formal office

**Recursive Search**:
- Room query: "home office space" → Get apartment_ids with office/study areas
- Apartment query: "1 bedroom", "separate corner", "internet" → Get apartment_ids
- Filter: 1BR apartments with office space AND good internet

---

### Query 5: "Affordable place that still feels spacious — I don't mind an older building if it's clean and bright."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "affordable rent",
      "claim_type": "pricing",
      "domain": "apartment",
      "weight": 0.85
    },
    {
      "claim": "spacious apartment",
      "claim_type": "size",
      "domain": "apartment",
      "weight": 0.80
    },
    {
      "claim": "clean apartment",
      "claim_type": "condition",
      "domain": "apartment",
      "weight": 0.75
    },
    {
      "claim": "bright apartment",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.75
    }
  ]
}
```

**Tricky Cases Handled**:
1. **"affordable"** → Pricing domain without specific amount (relies on semantic understanding)
2. **"feels spacious"** → Size claim (subjective but mappable)
3. **"I don't mind an older building"** → **EXCLUDED** from claims (negative statement about what user will tolerate, not a requirement)
4. **"if it's clean and bright"** → Two separate condition/feature claims (conditional requirements)
5. No age requirement extracted (user explicitly accepts older buildings)

**What's NOT extracted**:
- "older building" is mentioned but NOT turned into a claim because it's framed as acceptable ("don't mind"), not desired

**Recursive Search**:
- Apartment query only: "affordable", "spacious", "clean", "bright"
- No neighborhood or room-level requirements
- Filter: Affordable apartments matching size/condition criteria (age not filtered)

---

### Query 6: "Top-floor apartment with elevator access, good insulation, and no noisy bars or construction nearby."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "top floor apartment",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.80
    },
    {
      "claim": "elevator building",
      "claim_type": "accessibility",
      "domain": "apartment",
      "weight": 0.85
    },
    {
      "claim": "good insulation",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.75
    },
    {
      "claim": "quiet neighborhood",
      "claim_type": "neighborhood",
      "domain": "neighborhood",
      "weight": 0.80
    },
    {
      "claim": "no noisy bars nearby",
      "claim_type": "neighborhood",
      "domain": "neighborhood",
      "negation": true,
      "weight": 0.75
    },
    {
      "claim": "no construction nearby",
      "claim_type": "neighborhood",
      "domain": "neighborhood",
      "negation": true,
      "weight": 0.70
    }
  ]
}
```

**Tricky Cases Handled**:
1. **"top-floor"** → Apartment feature (not accessibility, because it's about floor position)
2. **"elevator access"** → Accessibility (standardized to "elevator building")
3. **"no noisy bars or construction"** → Neighborhood domain (not apartment) with negation=true
   - Creates TWO separate negated claims (bars, construction)
4. **Multiple negations**: System creates anti-claims during expansion for matching against "quiet neighborhood" evidence

**Anti-Claim Generation** (Expansion):
```json
{
  "claim": "quiet neighborhood",
  "kind": "base",
  "expansions": [
    {"claim": "peaceful area", "kind": "derived"},
    {"claim": "low noise level", "kind": "derived"},
    {"claim": "nightlife area", "kind": "anti"},
    {"claim": "noisy bars nearby", "kind": "anti"}
  ]
}
```

**Recursive Search**:
- Neighborhood query: "quiet", NOT("noisy bars"), NOT("construction") → Get quiet neighborhoods
- Apartment query: "top floor", "elevator", "insulation" → Get apartment_ids
- Filter: Top-floor elevator apartments in quiet areas

---

### Query 7: "Apartment with high ceilings, wooden floors, and an open-plan living room connected to the kitchen."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "high ceilings",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.75
    },
    {
      "claim": "wooden floors",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.70
    },
    {
      "claim": "open-plan living room",
      "claim_type": "features",
      "domain": "room",
      "room_type": "living_room",
      "weight": 0.80
    },
    {
      "claim": "living room connected to kitchen",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.75
    }
  ]
}
```

**Tricky Cases Handled**:
1. **"high ceilings"** → Apartment-level (affects whole unit)
2. **"wooden floors"** → Apartment-level (typically throughout, not room-specific)
3. **"open-plan living room"** → Room domain (living_room) because it describes that specific space
4. **"connected to kitchen"** → Apartment-level layout feature (describes relationship between rooms)

**Domain Ambiguity Resolution**:
- "open-plan living room" could be apartment OR room domain
- Assigned to **room** domain because "open-plan" is a characteristic of the living room itself
- "connected to kitchen" is **apartment** domain because it describes inter-room relationship (layout)

**Recursive Search**:
- Room query: "open-plan living room" → Get apartment_ids with open-plan living rooms
- Apartment query: "high ceilings", "wooden floors", "living-kitchen connection" → Get apartment_ids
- Filter: Apartments with high ceilings AND wood floors AND have open-plan living rooms connected to kitchen

---

### Query 8: "Modern kitchen with built-in appliances — dishwasher, oven, large fridge — and enough countertop space."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "modern kitchen",
      "claim_type": "condition",
      "domain": "room",
      "room_type": "kitchen",
      "weight": 0.75
    },
    {
      "claim": "built-in appliances",
      "claim_type": "amenities",
      "domain": "room",
      "room_type": "kitchen",
      "weight": 0.80
    },
    {
      "claim": "dishwasher in kitchen",
      "claim_type": "amenities",
      "domain": "room",
      "room_type": "kitchen",
      "weight": 0.85
    },
    {
      "claim": "oven in kitchen",
      "claim_type": "amenities",
      "domain": "room",
      "room_type": "kitchen",
      "weight": 0.90
    },
    {
      "claim": "large fridge in kitchen",
      "claim_type": "amenities",
      "domain": "room",
      "room_type": "kitchen",
      "weight": 0.70
    },
    {
      "claim": "enough countertop space",
      "claim_type": "size",
      "domain": "room",
      "room_type": "kitchen",
      "weight": 0.75
    }
  ]
}
```

**Tricky Cases Handled**:
1. **All claims → room domain (kitchen)** because query is entirely kitchen-focused
2. **Appliance details** → Separated into individual amenity claims (dishwasher, oven, fridge)
3. **"modern"** → Condition type (not features) because it describes renovation state
4. **"enough countertop space"** → Size type (not features) because it's about available area
5. **Weight hierarchy**: oven (0.90) > dishwasher (0.85) > fridge (0.70) based on importance

**Recursive Search**:
- Room query: ALL kitchen claims → Get apartment_ids with matching kitchens
- No apartment-level queries (everything is kitchen-specific)
- No neighborhood queries
- Filter: Apartments where kitchen matches ALL/MOST requirements (coverage-based ranking)

**Coverage Analysis**:
With 6 kitchen-specific claims, apartments need to match at least 4-5 to rank well:
- Kitchen with modern + appliances + space: High coverage
- Kitchen with only appliances but no space: Lower coverage

---

### Query 9: "Area that feels safe at night, with grocery stores and coffee shops within walking distance."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "safe neighborhood",
      "claim_type": "neighborhood",
      "domain": "neighborhood",
      "weight": 0.90
    },
    {
      "claim": "safe at night",
      "claim_type": "neighborhood",
      "domain": "neighborhood",
      "weight": 0.85
    },
    {
      "claim": "grocery stores within walking distance",
      "claim_type": "amenities",
      "domain": "neighborhood",
      "weight": 0.80
    },
    {
      "claim": "coffee shops within walking distance",
      "claim_type": "amenities",
      "domain": "neighborhood",
      "weight": 0.70
    }
  ]
}
```

**Tricky Cases Handled**:
1. **"feels safe at night"** → Two claims: general safety + temporal safety (at night)
2. **All claims → neighborhood domain** (no apartment/room requirements)
3. **"within walking distance"** → Implicit quantifier (will be extracted as distance constraint)
4. **"Area that"** → Correctly identified as neighborhood context

**Quantifier Extraction** (Phase 2):
```python
{
  "claim": "grocery stores within walking distance",
  "quantified_claim": "grocery stores within VAR_1",
  "quantifiers": [{
    "qtype": "distance",
    "noun": "grocery_stores",
    "vmin": 0,
    "vmax": 800,  # ~800m = ~10 min walk
    "op": QuantifierOp.LTE,
    "unit": "meters"
  }]
}
```

**Recursive Search**:
- Neighborhood query only: "safe", "safe at night", "grocery stores nearby", "coffee shops nearby"
- Get neighborhood_ids matching safety + amenity criteria
- Apartment query: None (user didn't specify apartment preferences)
- Filter: Any apartments in qualifying neighborhoods

**Query Interpretation**:
This query is **neighborhood-only** - user cares about location/area, not apartment specifics. System will return apartments in good neighborhoods regardless of apartment features.

---

### Query 10: "Bright two-bedroom apartment suitable for a couple with a cat and lots of plants, facing south or west."

**Extracted Claims**:
```json
{
  "claims": [
    {
      "claim": "bright apartment",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.80
    },
    {
      "claim": "2 bedroom apartment",
      "claim_type": "size",
      "domain": "apartment",
      "has_quantifiers": true,
      "weight": 0.95
    },
    {
      "claim": "pets allowed",
      "claim_type": "policies",
      "domain": "apartment",
      "weight": 0.90
    },
    {
      "claim": "cats allowed",
      "claim_type": "policies",
      "domain": "apartment",
      "weight": 0.85
    },
    {
      "claim": "south-facing apartment",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.75,
      "or_group": 1
    },
    {
      "claim": "west-facing apartment",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.75,
      "or_group": 1
    },
    {
      "claim": "space for plants",
      "claim_type": "features",
      "domain": "apartment",
      "weight": 0.60
    }
  ]
}
```

**Tricky Cases Handled**:
1. **"for a couple with a cat"** → Extracted as "cats allowed" (policy), not "suitable for couples"
2. **"lots of plants"** → Interpreted as "space for plants" (implicit feature requirement)
3. **"facing south or west"** → **OR group logic**: Two claims with same or_group=1
   - Apartment only needs to match ONE of these (south OR west)
4. **"bright"** → Correlated with south/west facing but kept as separate claim

**OR Group Handling**:
During score aggregation:
```python
# OR group 1: south-facing OR west-facing
or_group_claims = [
    {"claim": "south-facing", "score": 0.0},  # No match
    {"claim": "west-facing", "score": 0.92}   # Match!
]
# OR group is satisfied with max(0.0, 0.92) = 0.92
```

**Implicit Inference**:
- "suitable for a couple" → NOT extracted (size already handles capacity)
- "lots of plants" → Extracted as spatial requirement (not just amenity)

**Recursive Search**:
- Apartment query: "bright", "2BR", "pets allowed", ("south-facing" OR "west-facing"), "plant space"
- No neighborhood or room queries
- Filter: 2BR pet-friendly apartments that are bright AND (south OR west facing)

**Coverage Calculation**:
Total unique requirements: 6 (bright, 2BR, pets, south OR west, plant space, cats)
- Apartment matching 5/6: High coverage
- OR group counts as 1 requirement (satisfied if either matches)

---

## Summary: Domain Mapping Decision Tree

### When to assign **neighborhood** domain:
- Area character/vibe ("quiet", "trendy", "safe")
- Geographic location ("in Brooklyn", "East Village")
- Proximity to transit/amenities ("near park", "close to subway")
- General commute access

### When to assign **apartment** domain:
- Building features affecting whole unit ("high ceilings", "elevator building")
- Unit count/size ("2 bedroom", "studio")
- Policies ("pets allowed", "no smoking")
- Pricing ("rent $3,000")
- Whole-unit utilities ("heat included")
- Inter-room relationships ("open floor plan")
- Building condition ("newly renovated")

### When to assign **room** domain:
- Explicit room mention + room characteristic ("modern kitchen", "spacious bedroom")
- Room-specific features ("walk-in closet", "ensuite bathroom")
- Room-specific size ("12m² kitchen", "large living room")
- Room-specific amenities ("dishwasher in kitchen", "bay window in bedroom")

### Ambiguous case resolution:
- **"quiet"** → neighborhood (describes area, not unit)
- **"wooden floors"** → apartment (typically throughout)
- **"natural light"** → apartment (general characteristic)
- **"enough counter space"** → room (kitchen-specific)
- **"near subway"** → neighborhood (geographic proximity)
- **"parking spot"** → apartment (unit-specific amenity)

---

## Conclusion

This architecture combines two powerful concepts:

1. **Claim-Based Semantic Search**: Breaking down complex descriptions into atomic, semantically matchable facts
2. **Recursive Domain Search**: Modeling real-world hierarchies and searching across them in parallel

The result is a search system that:
- **Naturally handles complex queries** with requirements spanning multiple entity levels (room features + apartment features + location)
- **Precisely filters results** by ensuring all hierarchical constraints are satisfied
- **Scales efficiently** through parallel execution and Elasticsearch's HNSW indexing
- **Explains results** by tracking which claims matched at which domain level
- **Extends easily** to new domains or more complex hierarchies

The key innovation—recursive domain search with parallel kNN queries and filtered merging—enables precise, fast search over hierarchical data while maintaining the semantic matching power of embeddings.

**Critical Success Factors**:
1. High-quality LLM prompts for domain identification
2. Careful threshold tuning per claim type and domain
3. Efficient Elasticsearch configuration (HNSW parameters, pre-filtering)
4. Thoughtful domain weight assignment based on query patterns
5. Iterative expansion of complexity (start simple, add features incrementally)
