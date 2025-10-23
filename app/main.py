import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Apartment Semantic Search",
    description="Semantic search system for apartments using vector embeddings and Google Maps grounding",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "message": "Apartment Semantic Search API with Google Maps Grounding",
        "version": "0.2.0",
        "status": "running",
        "features": [
            "Claim-based semantic search",
            "Multi-domain search (Room/Apartment/Neighborhood)",
            "Google Maps grounding",
            "Geo-filtering",
            "Interactive map widgets"
        ]
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
