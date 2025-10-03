"""
Supabase client configuration
"""
from supabase import create_client, Client
from app.config import settings


class SupabaseClient:
    """Singleton Supabase client"""
    
    _instance: Client = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance"""
        if cls._instance is None:
            cls._instance = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
        return cls._instance


supabase = SupabaseClient.get_client()

