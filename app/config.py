from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    google_api_key: str
    google_maps_api_key: str
    elasticsearch_url: str = "http://localhost:9200"
    
    gemini_model: str = "gemini-2.5-pro"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 3072
    
    enable_grounding: bool = True
    grounding_cache_ttl_days: int = 30
    max_groundings_per_listing: int = 3
    grounding_model: str = "gemini-2.0-flash-exp"


settings = Settings()

