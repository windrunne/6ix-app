"""
Warm intro service for managing connection introductions
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from app.database import supabase
from app.services.ai_service import ai_service
from app.services.network_service import network_service
from app.models import IntroRequestStatus
from app.config import settings
from app.utils.logger import logger
import uuid


class IntroService:
    """Service for warm introduction operations"""
    
    async def create_intro_request(
        self,
        requester_id: str,
        target_id: str,
        query_context: str,
        why_match: str,
        mutual_ids: list
    ) -> Dict[str, Any]:
        """
        Create a warm intro request with deduplication and cooldown
        
        Args:
            requester_id: User requesting intro
            target_id: User to be introduced to
            query_context: Original query context
            why_match: Why this person matches
            mutual_ids: List of mutual connection IDs
            
        Returns:
            Dictionary with intro request details
        """
        try:
            if requester_id == target_id:
                return {
                    "success": False,
                    "error": "Cannot request intro to yourself"
                }
            
            duplicate = await self._check_duplicate_request(requester_id, target_id)
            if duplicate:
                return {
                    "success": False,
                    "error": f"You already have a pending intro request to this user. Status: {duplicate['status']}"
                }
            
            cooldown_ok, cooldown_msg = await self._check_cooldown(requester_id, target_id)
            if not cooldown_ok:
                return {
                    "success": False,
                    "error": cooldown_msg
                }
            
            can_request, reason = await self._check_rate_limits(requester_id)
            if not can_request:
                return {
                    "success": False,
                    "error": reason
                }
            
            requester = await self._get_user_name(requester_id)
            target = await self._get_user_name(target_id)
            
            mutuals = await network_service.get_mutual_connections(requester_id, target_id)
            mutual_count = len(mutuals)
            
            intro_data = {
                "requester_id": requester_id,
                "target_id": target_id,
                "query_context": query_context,
                "why_match": why_match,
                "mutual_ids": mutual_ids,
                "mutual_count": mutual_count,
                "status": IntroRequestStatus.PENDING.value,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
            }
            
            response = supabase.table("intro_requests").insert(intro_data).execute()
            
            if not response.data:
                raise Exception("Failed to create intro request")
            
            intro_request = response.data[0]
            
            await self._send_intro_notification(
                intro_request["id"],
                requester_id,
                target_id,
                requester,
                query_context
            )
            
            
            logger.info(f"Created intro request {intro_request['id']} from {requester_id} to {target_id}")
            
            return {
                "success": True,
                "intro_request_id": intro_request["id"],
                "status": intro_request["status"]
            }
            
        except Exception as e:
            logger.error(f"Error creating intro request: {str(e)}")
            raise
    
    async def respond_to_intro(
        self,
        intro_request_id: str,
        target_response: bool
    ) -> Dict[str, Any]:
        """
        Respond to an intro request (accept or decline)
        
        Args:
            intro_request_id: Intro request ID
            target_response: True for accept, False for decline
            
        Returns:
            Dictionary with response details
        """
        try:
            intro_response = supabase.table("intro_requests").select(
                "*"
            ).eq("id", intro_request_id).single().execute()
            
            if not intro_response.data:
                return {
                    "success": False,
                    "error": "Intro request not found"
                }
            
            intro = intro_response.data
            
            if intro["status"] != IntroRequestStatus.PENDING.value:
                return {
                    "success": False,
                    "error": f"Intro request already {intro['status']}"
                }
            
            new_status = IntroRequestStatus.ACCEPTED.value if target_response else IntroRequestStatus.DECLINED.value
            
            supabase.table("intro_requests").update({
                "status": new_status,
                "responded_at": datetime.utcnow().isoformat()
            }).eq("id", intro_request_id).execute()
            
            if target_response:
                chat_result = await self._create_intro_chat(intro)
                
                logger.info(f"Intro request {intro_request_id} accepted, chat created")
                
                return {
                    "success": True,
                    "status": new_status,
                    "chat_id": chat_result["chat_id"],
                    "intro_message": chat_result["intro_message"]
                }
            else:
                await self._send_decline_notification(intro["requester_id"])
                
                logger.info(f"Intro request {intro_request_id} declined")
                
                return {
                    "success": True,
                    "status": new_status
                }
                
        except Exception as e:
            logger.error(f"Error responding to intro request: {str(e)}")
            raise
    
    async def _check_rate_limits(
        self,
        user_id: str
    ) -> tuple[bool, Optional[str]]:
        """Check if user can create more intro requests"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=1)
            
            response = supabase.table("intro_requests").select(
                "id", count="exact"
            ).eq("requester_id", user_id).eq(
                "status", IntroRequestStatus.PENDING.value
            ).gte("created_at", cutoff_time.isoformat()).execute()
            
            count = response.count or 0
            
            if count >= settings.max_intro_requests_per_day:
                return False, f"You've reached the daily limit of {settings.max_intro_requests_per_day} intro requests"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking rate limits: {str(e)}")
            return True, None  # Fail open
    
    async def _create_intro_chat(
        self,
        intro: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a chat and send intro message"""
        try:
            requester_id = intro["requester_id"]
            target_id = intro["target_id"]
            
            requester = await self._get_user_name(requester_id)
            target = await self._get_user_name(target_id)
            
            requester_first = requester.split()[0] if requester else "User"
            target_first = target.split()[0] if target else "User"
            
            intro_message = await ai_service.generate_intro_message(
                requester_name=requester_first,
                target_name=target_first,
                mutual_count=intro["mutual_count"],
                query_snippet=intro["query_context"],
                why_match=intro["why_match"]
            )
            
            chat_id = f"chat_{uuid.uuid4().hex[:12]}"
            
            chat_data = {
                "chat_id": chat_id,
                "user1": requester_id,
                "user2": target_id,
                "created_at": datetime.utcnow().isoformat()
            }
            
            chat_response = supabase.table("chats").insert(chat_data).execute()
            chat = chat_response.data[0]
            
            message_data = {
                "chat_id": chat["chat_id"],
                "sender_id": None,
                "content": intro_message,
                "created_at": datetime.utcnow().isoformat(),
                "read_by": []
            }
            
            supabase.table("messages").insert(message_data).execute()
            
            logger.info(f"Created intro chat {chat['chat_id']} with message")
            
            return {
                "chat_id": chat["chat_id"],
                "intro_message": intro_message
            }
            
        except Exception as e:
            logger.error(f"Error creating intro chat: {str(e)}")
            raise
    
    async def _get_user_name(self, user_id: str) -> str:
        """Get user's name"""
        try:
            response = supabase.table("users").select(
                "name"
            ).eq("id", user_id).single().execute()
            
            return response.data.get("name", "User") if response.data else "User"
            
        except Exception as e:
            logger.error(f"Error getting user name: {str(e)}")
            return "User"
    
    async def _send_intro_notification(
        self,
        intro_request_id: str,
        requester_id: str,
        target_id: str,
        requester_name: str,
        query_context: str
    ) -> None:
        """Send notification to target about intro request"""
        try:
            notification_data = {
                "user_id": target_id,
                "sender_id": requester_id,
                "type": "intro_request",
                "title": "New Connection Request",
                "message": f"{requester_name} wants to connect about: {query_context[:100]}",
                "data": {
                    "intro_request_id": intro_request_id,
                    "requester_id": requester_id
                },
                "created_at": datetime.utcnow().isoformat(),
                "read": False
            }
            
            supabase.table("notifications").insert(notification_data).execute()
            logger.info(f"Sent intro notification to {target_id}")
            
        except Exception as e:
            logger.error(f"Error sending intro notification: {str(e)}")
    
    async def _check_duplicate_request(
        self,
        requester_id: str,
        target_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check for duplicate intro requests (deduplication)
        Returns existing request if found, None otherwise
        """
        try:
            response = supabase.table("intro_requests").select(
                "id, status, created_at"
            ).eq("requester_id", requester_id).eq("target_id", target_id).in_(
                "status", [IntroRequestStatus.PENDING.value]
            ).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking duplicate request: {str(e)}")
            return None
    
    async def _check_cooldown(
        self,
        requester_id: str,
        target_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check cooldown period after declined/expired requests
        Cooldown: 7 days after decline, 30 days after expired
        """
        try:
            response = supabase.table("intro_requests").select(
                "status, updated_at, created_at"
            ).eq("requester_id", requester_id).eq("target_id", target_id).in_(
                "status", [IntroRequestStatus.DECLINED.value, IntroRequestStatus.EXPIRED.value]
            ).order("created_at", desc=True).limit(1).execute()
            
            if not response.data or len(response.data) == 0:
                return True, None
            
            last_request = response.data[0]
            last_time_str = last_request.get("updated_at") or last_request.get("created_at")
            
            last_time = datetime.fromisoformat(last_time_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            
            if last_request["status"] == IntroRequestStatus.DECLINED.value:
                cooldown_days = 7
            else:
                cooldown_days = 30
            
            cooldown_end = last_time + timedelta(days=cooldown_days)
            
            if now < cooldown_end:
                time_remaining = cooldown_end - now
                days_remaining = time_remaining.days
                hours_remaining = time_remaining.seconds // 3600
                
                return False, (
                    f"Please wait before requesting intro again. "
                    f"Cooldown: {days_remaining} days, {hours_remaining} hours remaining."
                )
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking cooldown: {str(e)}")
            return True, None
    
    async def expire_old_requests(self) -> int:
        """
        Expire intro requests that have passed their expiration date
        Should be run periodically (cron job)
        
        Returns:
            Number of requests expired
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            response = supabase.table("intro_requests").select(
                "id"
            ).eq("status", IntroRequestStatus.PENDING.value).lt(
                "expires_at", now
            ).execute()
            
            if not response.data or len(response.data) == 0:
                return 0
            
            expired_ids = [r["id"] for r in response.data]
            
            supabase.table("intro_requests").update({
                "status": IntroRequestStatus.EXPIRED.value
            }).in_("id", expired_ids).execute()
            
            logger.info(f"Expired {len(expired_ids)} intro requests")
            return len(expired_ids)
            
        except Exception as e:
            logger.error(f"Error expiring requests: {str(e)}")
            return 0
    
    async def get_user_intro_requests(
        self,
        user_id: str,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all intro requests for a user (sent and received)
        
        Args:
            user_id: User ID
            status: Optional status filter (pending, accepted, declined, expired)
            
        Returns:
            Dictionary with sent and received requests
        """
        try:
            query_sent = supabase.table("intro_requests").select(
                "id, target_id, query_context, why_match, status, created_at, expires_at"
            ).eq("requester_id", user_id)
            
            query_received = supabase.table("intro_requests").select(
                "id, requester_id, query_context, why_match, status, created_at, expires_at"
            ).eq("target_id", user_id)
            
            if status:
                query_sent = query_sent.eq("status", status)
                query_received = query_received.eq("status", status)
            
            sent_response = query_sent.order("created_at", desc=True).execute()
            received_response = query_received.order("created_at", desc=True).execute()
            
            return {
                "success": True,
                "sent_requests": sent_response.data or [],
                "received_requests": received_response.data or [],
                "sent_count": len(sent_response.data) if sent_response.data else 0,
                "received_count": len(received_response.data) if received_response.data else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting intro requests: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_decline_notification(self, requester_id: str) -> None:
        """Send notification when intro is declined"""
        try:
            notification_data = {
                "user_id": requester_id,
                "sender_id": "system",
                "type": "intro_declined",
                "title": "Connection Request",
                "message": "Your connection request wasn't accepted this time",
                "created_at": datetime.utcnow().isoformat(),
                "read": False
            }
            
            supabase.table("notifications").insert(notification_data).execute()
            logger.info(f"Sent decline notification to {requester_id}")
            
        except Exception as e:
            logger.error(f"Error sending decline notification: {str(e)}")


intro_service = IntroService()

