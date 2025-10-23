from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    url: str
    type: str
    index: int
    prompt: Optional[str] = None
    camera: Optional[str] = None


class ClaimType(str, Enum):
    LOCATION = "location"
    FEATURES = "features"
    AMENITIES = "amenities"
    SIZE = "size"
    CONDITION = "condition"
    PRICING = "pricing"
    ACCESSIBILITY = "accessibility"
    POLICIES = "policies"
    UTILITIES = "utilities"
    TRANSPORT = "transport"
    NEIGHBORHOOD = "neighborhood"
    RESTRICTIONS = "restrictions"


class Domain(str, Enum):
    NEIGHBORHOOD = "neighborhood"
    APARTMENT = "apartment"
    ROOM = "room"


class ClaimKind(str, Enum):
    BASE = "base"
    DERIVED = "derived"
    ANTI = "anti"
    VERIFIED = "verified"


class QuantifierOp(str, Enum):
    EQUALS = "EQUALS"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    APPROX = "APPROX"
    RANGE = "RANGE"


class QuantifierType(str, Enum):
    MONEY = "money"
    AREA = "area"
    COUNT = "count"
    DISTANCE = "distance"
    DURATION = "duration"


class Quantifier(BaseModel):
    qtype: QuantifierType
    noun: str
    vmin: float
    vmax: float
    op: QuantifierOp
    unit: Optional[str] = None


class ClaimSource(BaseModel):
    type: str
    image_url: Optional[str] = None
    image_index: Optional[int] = None


class GroundingMetadata(BaseModel):
    verified: bool
    source: str
    place_id: Optional[str] = None
    place_name: Optional[str] = None
    place_uri: Optional[str] = None
    coordinates: Optional[dict[str, float]] = None
    exact_distance_meters: Optional[int] = None
    walking_time_minutes: Optional[float] = None
    recommended_radius_meters: Optional[int] = None
    confidence: float = 1.0
    verified_at: Optional[str] = None
    supporting_evidence: Optional[str] = None


class Claim(BaseModel):
    claim: str
    claim_type: ClaimType
    domain: Domain
    room_type: Optional[str] = None
    is_specific: bool = False
    has_quantifiers: bool = False
    quantifiers: list[Quantifier] = Field(default_factory=list)
    kind: ClaimKind = ClaimKind.BASE
    from_claim: Optional[str] = None
    weight: float = 0.75
    or_group: Optional[int] = None
    negation: bool = False
    grounding_metadata: Optional[GroundingMetadata] = None
    source: Optional[ClaimSource] = None


class EmbeddedClaim(Claim):
    embedding: list[float]
    quantified_claim: Optional[str] = None


class AvailabilityRange(BaseModel):
    start: str
    end: Optional[str] = None


class StructuredProperty(BaseModel):
    rent_price: Optional[float] = None
    availability_dates: list[AvailabilityRange] = Field(default_factory=list)


class ApartmentDocument(BaseModel):
    apartment_id: str
    title: Optional[str] = None
    neighborhood_id: Optional[str] = None
    address: Optional[str] = None
    location: Optional[dict[str, float]] = None
    raw_description: str
    image_urls: list[str] = Field(default_factory=list)
    image_metadata: list[ImageMetadata] = Field(default_factory=list)
    claims: list[EmbeddedClaim]
    rent_price: Optional[float] = None
    availability_dates: list[AvailabilityRange] = Field(default_factory=list)
    property_summary: Optional[str] = None
    location_summary: Optional[str] = None
    location_widget_token: Optional[str] = None


class SearchResult(BaseModel):
    apartment_id: str
    title: Optional[str] = None
    address: Optional[str] = None
    final_score: float
    coverage_count: int
    coverage_ratio: float
    weight_coverage: float
    matched_claims: list[dict]
    domain_scores: dict[str, float]
    geo_proximity: Optional[dict[str, str]] = None
    grounded_sources: list[dict] = Field(default_factory=list)
    map_widget_tokens: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    image_metadata: list[ImageMetadata] = Field(default_factory=list)
    rent_price: Optional[float] = None
    availability_dates: list[dict] = Field(default_factory=list)

