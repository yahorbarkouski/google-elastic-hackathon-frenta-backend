from app.models import ClaimType, Domain

CLAIM_TYPE_THRESHOLDS = {
    ClaimType.LOCATION: 0.92,
    ClaimType.SIZE: 0.80,
    ClaimType.FEATURES: 0.75,
    ClaimType.PRICING: 0.85,
    ClaimType.AMENITIES: 0.70,
    ClaimType.CONDITION: 0.75,
    ClaimType.ACCESSIBILITY: 0.75,
    ClaimType.POLICIES: 0.80,
    ClaimType.UTILITIES: 0.75,
    ClaimType.TRANSPORT: 0.75,
    ClaimType.NEIGHBORHOOD: 0.73,
    ClaimType.RESTRICTIONS: 0.80,
}

DOMAIN_WEIGHTS = {
    Domain.ROOM: 0.35,
    Domain.APARTMENT: 0.40,
    Domain.NEIGHBORHOOD: 0.25,
}

