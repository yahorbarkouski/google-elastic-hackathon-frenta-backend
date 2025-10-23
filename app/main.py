import logging
import sys
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

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

def is_allowed_origin(origin: str) -> bool:
    if not origin:
        return False
    if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
        return True
    if "frenta" in origin and origin.endswith(".vercel.app"):
        return True
    return False

class SmartCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin")
        
        if request.method == "OPTIONS" and origin and is_allowed_origin(origin):
            from starlette.responses import Response
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Allow-Methods": "*",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        
        response = await call_next(request)
        
        if origin and is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
        
        return response

app.add_middleware(SmartCORSMiddleware)

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
