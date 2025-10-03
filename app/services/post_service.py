"""
Post analysis service
"""
from typing import Dict, Any, Optional
from app.database import supabase
from app.services.ai_service import ai_service
from app.models import PostInsights
from app.utils.logger import logger
from datetime import datetime, timedelta


class PostService:
    """Service for post analysis operations"""
    
    async def analyze_post(
        self,
        user_id: str,
        post_id: str,
        image_url: Optional[str] = None,
        caption: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PostInsights:
        """
        Analyze a post and extract insights (with caching)
        
        Args:
            user_id: User ID who owns the post
            post_id: Post ID
            image_url: Optional image URL
            caption: Optional caption text
            metadata: Optional metadata
            
        Returns:
            PostInsights object
        """
        try:
            cached_insights = await self.get_cached_insights(post_id)
            if cached_insights:
                logger.info(f"Using cached insights for post {post_id}")
                return PostInsights(**cached_insights)
            
            insights_data = {}
            
            if image_url:
                image_insights = await ai_service.analyze_post_image(image_url, caption)
                insights_data.update(image_insights)
            
            elif caption:
                text_insights = await ai_service.analyze_post_text(caption, metadata)
                insights_data.update(text_insights)
            
            if not insights_data:
                insights_data = {
                    "location_guess": None,
                    "outfit_items": [],
                    "objects": [],
                    "vibe_descriptors": [],
                    "colors": [],
                    "activities": [],
                    "interests": [],
                    "summary": caption or "No content to analyze",
                    "confidence_score": 0.0
                }
            
            insights = PostInsights(**insights_data)
            
            await self._store_post_insights(post_id, user_id, insights_data)
            
            logger.info(f"Successfully analyzed post {post_id} and cached results")
            return insights
            
        except Exception as e:
            logger.error(f"Error analyzing post {post_id}: {str(e)}")
            raise
    
    async def get_post_details(
        self,
        post_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get post details from database
        
        Args:
            post_id: Post ID
            
        Returns:
            Post details dictionary or None
        """
        try:
            response = supabase.table("posts").select(
                "id, user_id, content, category, image_url, created_at"
            ).eq("id", post_id).single().execute()
            
            return response.data if response.data else None
            
        except Exception as e:
            logger.error(f"Error getting post details: {str(e)}")
            return None
    
    async def get_user_recent_post(
        self,
        user_id: str,
        within_minutes: int = 6
    ) -> Optional[Dict[str, Any]]:
        """
        Get user's most recent post within time window
        
        Args:
            user_id: User ID
            within_minutes: Time window in minutes
            
        Returns:
            Post details or None
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=within_minutes)
            
            response = supabase.table("posts").select(
                "id, user_id, content, category, image_url, created_at"
            ).eq("user_id", user_id).gte(
                "created_at", cutoff_time.isoformat()
            ).order("created_at", desc=True).limit(1).execute()
            
            if response.data:
                return response.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting recent post: {str(e)}")
            return None
    
    async def get_cached_insights(
        self,
        post_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached post insights from database
        
        Args:
            post_id: Post ID
            
        Returns:
            Cached insights dictionary or None
        """
        try:
            response = supabase.table("post_insights").select(
                "location_guess, outfit_items, objects, vibe_descriptors, "
                "colors, activities, interests, summary, confidence_score, analyzed_at"
            ).eq("post_id", post_id).single().execute()
            
            if response.data:
                logger.info(f"Retrieved cached insights for post {post_id}")
                return response.data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached insights: {str(e)}")
            return None
    
    async def _store_post_insights(
        self,
        post_id: str,
        user_id: str,
        insights: Dict[str, Any]
    ) -> None:
        """
        Store post insights in database
        
        Args:
            post_id: Post ID
            user_id: User ID
            insights: Insights dictionary
        """
        try:
            insights_data = {
                "post_id": post_id,
                "user_id": user_id,
                "location_guess": insights.get("location_guess"),
                "outfit_items": insights.get("outfit_items", []),
                "objects": insights.get("objects", []),
                "vibe_descriptors": insights.get("vibe_descriptors", []),
                "colors": insights.get("colors", []),
                "activities": insights.get("activities", []),
                "interests": insights.get("interests", []),
                "summary": insights.get("summary", ""),
                "confidence_score": insights.get("confidence_score", 0.0),
                "analyzed_at": datetime.utcnow().isoformat()
            }
            
            supabase.table("post_insights").upsert(insights_data).execute()
            
            logger.info(f"Stored post insights for {post_id} in database")
            
        except Exception as e:
            logger.error(f"Error storing post insights: {str(e)}")


post_service = PostService()

