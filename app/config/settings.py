"""
Application configuration settings
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from .env file"""
    
    app_env: str = "development"
    port: int = 8000
    host: str = "0.0.0.0"
    
    supabase_url: str
    supabase_service_role_key: str
    supabase_anon_key: Optional[str] = None
    
    database_url: Optional[str] = None 
    
    openai_api_key: str
    openai_model: str = "gpt-4o"
    
    use_semantic_search: bool = True
    semantic_min_score: float = 3.0
    max_parallel_ai_requests: int = 10
    
    max_intro_requests_per_day: int = 3
    max_ghost_asks_per_day: int = 5
    
    challenge_unlock_window_minutes: int = 6
    
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        if not self.database_url and self.supabase_url:
            project_ref = self.supabase_url.split("//")[1].split(".")[0]
            password = os.getenv("SUPABASE_FIXED_PASSWORD", "")
            if password:
                self.database_url = f"postgresql://postgres:{password}@db.{project_ref}.supabase.co:5432/postgres"

    
settings = Settings()

