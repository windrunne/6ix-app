"""
Chat service for managing OpenAI threads and conversation sessions
"""
import uuid
from typing import Dict, Any, Optional
from app.database import supabase
from app.services.ai_service import ai_service
from app.services.post_service import post_service
from app.utils.logger import logger


class ChatService:
    """Service for managing chat sessions with OpenAI threads"""
    
    async def get_or_create_session(
        self,
        user_id: str,
        thread_id: Optional[str] = None,
        post_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get existing session or create new one with OpenAI thread
        
        Args:
            user_id: User ID
            thread_id: Optional existing thread ID
            
        Returns:
            Dictionary with session info including thread_id
        """
        try:
            if thread_id:
                try:
                    response = supabase.table("chat_sessions").select(
                        "*"
                    ).eq("thread_id", thread_id).eq("user_id", user_id).single().execute()
                    
                    if response.data:
                        logger.info(f"Retrieved existing session with thread {thread_id} for user {user_id}")
                        return response.data
                    else:
                        raise Exception(f"Thread {thread_id} not found for user {user_id}")
                        
                except Exception as db_error:
                    if "PGRST116" in str(db_error) or "0 rows" in str(db_error):
                        raise Exception(f"Thread {thread_id} not found for user {user_id}")
                    else:
                        raise db_error
            
            thread = await ai_service.create_thread()
            thread_id = thread.id
            
            session_data = {
                "thread_id": thread_id,
                "user_id": user_id,
                "post_id": post_id,
                "created_at": "now()",
                "last_activity": "now()"
            }
            
            supabase.table("chat_sessions").insert(session_data).execute()
            
            logger.info(f"Created new session with thread {thread_id} for user {user_id}" + 
                       (f" linked to post {post_id}" if post_id else ""))
            
            return {
                "thread_id": thread_id,
                "user_id": user_id,
                "post_id": post_id,
                "created_at": "now()",
                "last_activity": "now()"
            }
            
        except Exception as e:
            logger.error(f"Error managing chat session: {str(e)}")
            raise
    
    async def send_message(
        self,
        user_id: str,
        message: str,
        thread_id: Optional[str] = None,
        post_id: Optional[str] = None,
        image_url: Optional[str] = None,
        face_matches: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Send message using OpenAI thread for conversation continuity
        
        Args:
            user_id: User ID
            message: User's message
            thread_id: Optional existing thread ID
            post_id: Optional post ID for context
            image_url: Optional image URL if user is asking about an image
            face_matches: Optional list of face matches from image analysis
            
        Returns:
            Dictionary with response and thread info
        """
        try:
            session = await self.get_or_create_session(user_id, thread_id, post_id)
            thread_id = session["thread_id"]
            session_post_id = session.get("post_id")
            
            full_message = message
            
            effective_post_id = post_id or session_post_id
            
            # Add post context if available
            if effective_post_id:
                post_insights = await post_service.get_cached_insights(effective_post_id)
                
                if post_insights:
                    context_str = f"[Post context: {post_insights}]\n\n"
                    full_message = context_str + message
                    logger.info(f"Added post context for post {effective_post_id}")
                else:
                    logger.warning(f"No cached insights found for post {effective_post_id}")
            
            # Add face recognition context if available
            if face_matches:
                face_context = self._build_face_context(face_matches)
                full_message = face_context + "\n\n" + full_message
                logger.info(f"Added face recognition context: {len(face_matches)} matches")
            
            response = await ai_service.send_thread_message(
                thread_id=thread_id,
                message=full_message,
                original_message=message
            )
            
            supabase.table("chat_sessions").update({
                "last_activity": "now()"
            }).eq("thread_id", thread_id).execute()
            
            logger.info(f"Sent message to thread {thread_id}")
            
            return {
                "success": True,
                "response": response,
                "thread_id": thread_id
            }
            
        except Exception as e:
            logger.error(f"Error sending chat message: {str(e)}")
            raise
    
    def _build_face_context(self, face_matches: list) -> str:
        """
        Build context string for face recognition results
        
        Args:
            face_matches: List of face match results
            
        Returns:
            Context string for AI
        """
        if not face_matches:
            return ""
        
        context_parts = ["[Face Recognition Results:]"]
        
        for match in face_matches:
            name = match.get("name", "Unknown")
            username = match.get("username", "")
            similarity = match.get("similarity", 0)
            confidence = match.get("confidence", 0)
            
            username_str = f" (@{username})" if username else ""
            context_parts.append(f"- {name}{username_str} (similarity: {similarity:.1f}%, confidence: {confidence:.1f}%)")
        
        context_parts.append("")
        context_parts.append("If the user is asking 'who is in this picture?' or similar questions, provide the names of the recognized people.")
        
        return "\n".join(context_parts)
    
    async def get_session_history(
        self,
        thread_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get conversation history from database
        
        Args:
            thread_id: Thread ID
            user_id: User ID
            
        Returns:
            Dictionary with conversation history
        """
        try:
            response = supabase.table("chat_sessions").select(
                "thread_id, user_id, conversation_history, created_at, last_activity"
            ).eq("thread_id", thread_id).eq("user_id", user_id).single().execute()
            
            if not response.data:
                raise Exception("Session not found")
            
            conversation_history = response.data.get("conversation_history", [])
            
            return {
                "success": True,
                "thread_id": thread_id,
                "user_id": user_id,
                "messages": conversation_history,
                "total_messages": len(conversation_history),
                "created_at": response.data.get("created_at"),
                "last_activity": response.data.get("last_activity")
            }
            
        except Exception as e:
            logger.error(f"Error getting session history: {str(e)}")
            raise
    
    async def delete_session(
        self,
        thread_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Delete chat session and OpenAI thread
        
        Args:
            thread_id: Thread ID
            user_id: User ID
            
        Returns:
            Dictionary with deletion result
        """
        try:
            response = supabase.table("chat_sessions").select(
                "*"
            ).eq("thread_id", thread_id).eq("user_id", user_id).single().execute()
            
            if not response.data:
                raise Exception("Session not found")
            
            supabase.table("chat_sessions").delete().eq("thread_id", thread_id).execute()
            
            logger.info(f"Deleted session with thread {thread_id}")
            
            return {
                "success": True,
                "message": "Session deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Error deleting session: {str(e)}")
            raise


chat_service = ChatService()
