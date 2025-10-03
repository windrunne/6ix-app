"""
Ghost Ask service for anonymous messaging
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from app.database import supabase
from app.services.ai_service import ai_service
from app.services.post_service import post_service
from app.models import GhostAskStatus
from app.config import settings
from app.utils.logger import logger


class GhostAskService:
    """Service for ghost ask operations"""
    
    async def _check_user_posted_in_challenge_window(self, user_id: str) -> bool:
        """
        Check if user has posted within the daily challenge 6-minute window
        Uses daily_challenges.has_posted field instead of querying posts directly
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if user posted during challenge window, False otherwise
        """
        try:
            
            response = supabase.table("daily_challenges").select(
                "challenge_time, has_posted"
            ).eq("user_id", user_id).order(
                "challenge_date", desc=True
            ).limit(1).execute()
            
            if not response.data or len(response.data) == 0:
                logger.warning(f"No daily challenge found for user {user_id}")
                return False
            
            challenge = response.data[0]
            
            challenge_time = datetime.fromisoformat(challenge["challenge_time"].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            
            challenge_end_time = challenge_time + timedelta(minutes=settings.challenge_unlock_window_minutes)
            
            if challenge_time <= now <= challenge_end_time and challenge["has_posted"]:
                logger.info(f"User {user_id} posted during challenge window (has_posted=True)")
                return True
            
            if challenge["has_posted"] and now < challenge_end_time + timedelta(minutes=5):
                logger.info(f"User {user_id} posted during challenge (grace period)")
                return True
            
            logger.info(f"User {user_id} has_posted={challenge['has_posted']}, challenge_time={challenge_time}, now={now}")
            return False
            
        except Exception as e:
            logger.error(f"Error checking challenge post status: {str(e)}")
            return False
    
    async def create_ghost_ask(
        self,
        sender_id: str,
        recipient_id: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Create a ghost ask (anonymous message)
        
        Args:
            sender_id: User sending the message
            recipient_id: User receiving the message
            message: Anonymous message content
            
        Returns:
            Dictionary with ghost ask details
        """
        try:
            has_posted_in_window = await self._check_user_posted_in_challenge_window(sender_id)
            
            can_send, reason = await self._check_rate_limits(sender_id)
            if not can_send:
                return {
                    "success": False,
                    "error": reason,
                    "unlock_required": False
                }
            
            ghost_ask_data = {
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "message": message,
                "status": GhostAskStatus.PENDING.value,
                "created_at": datetime.utcnow().isoformat(),
                "unlocked": has_posted_in_window,
                "persuasion_attempts": 0
            }
            
            response = supabase.table("ghost_asks").insert(ghost_ask_data).execute()
            
            if not response.data:
                raise Exception("Failed to create ghost ask")
            
            ghost_ask = response.data[0]
            
            if has_posted_in_window:
                await self._send_ghost_ask(ghost_ask["id"], sender_id, recipient_id, message)
                
                logger.info(f"Ghost ask {ghost_ask['id']} sent immediately (unlocked)")
                
                return {
                    "success": True,
                    "ghost_ask_id": ghost_ask["id"],
                    "status": GhostAskStatus.SENT.value,
                    "message": "your ghost ask has been sent! 👻",
                    "unlock_required": False
                }
            else:
                persuasion = await ai_service.generate_persuasion_message(
                    sender_id,
                    message,
                    attempt_count=1
                )
                
                time_remaining = await self._get_time_until_unlock(sender_id)
                
                logger.info(f"Ghost ask {ghost_ask['id']} created but not unlocked")
                
                return {
                    "success": True,
                    "ghost_ask_id": ghost_ask["id"],
                    "status": GhostAskStatus.PENDING.value,
                    "message": "ghost ask created but locked",
                    "unlock_required": True,
                    "time_remaining_seconds": time_remaining,
                    "persuasion_message": persuasion
                }
                
        except Exception as e:
            logger.error(f"Error creating ghost ask: {str(e)}")
            raise
    
    async def attempt_send_ghost_ask(
        self,
        ghost_ask_id: str,
        sender_id: str,
        force_send: bool = False
    ) -> Dict[str, Any]:
        """
        Attempt to send a ghost ask (with persuasion logic)
        
        Args:
            ghost_ask_id: Ghost ask ID
            sender_id: User sending the message
            force_send: Force send after persuasion
            
        Returns:
            Dictionary with send attempt result
        """
        try:
            response = supabase.table("ghost_asks").select(
                "*"
            ).eq("id", ghost_ask_id).eq("sender_id", sender_id).execute()
            
            if not response.data or len(response.data) == 0:
                logger.warning(f"Ghost ask {ghost_ask_id} not found for user {sender_id}")
                return {
                    "success": False,
                    "error": "Ghost ask not found"
                }
            
            ghost_ask = response.data[0]
            logger.info(f"Retrieved ghost ask: status={ghost_ask.get('status')}, unlocked={ghost_ask.get('unlocked')}")
            
            if ghost_ask.get("status") == GhostAskStatus.SENT.value:
                return {
                    "success": False,
                    "error": "Ghost ask already sent"
                }
            
            logger.info(f"Checking if user {sender_id} posted during challenge window")
            has_posted_in_window = await self._check_user_posted_in_challenge_window(sender_id)
            logger.info(f"User posted in challenge window: {has_posted_in_window}")
            
            if has_posted_in_window:
                await self._send_ghost_ask(
                    ghost_ask_id,
                    sender_id,
                    ghost_ask["recipient_id"],
                    ghost_ask["message"]
                )
                
                logger.info(f"Ghost ask {ghost_ask_id} unlocked and sent")
                
                return {
                    "success": True,
                    "ghost_ask_id": ghost_ask_id,
                    "status": GhostAskStatus.SENT.value,
                    "message": "your ghost ask has been sent! 👻"
                }
            
            attempts = ghost_ask.get("persuasion_attempts", 0) + 1
            
            supabase.table("ghost_asks").update({
                "persuasion_attempts": attempts
            }).eq("id", ghost_ask_id).execute()
            
            if attempts > 10:
                await self._send_ghost_ask(
                    ghost_ask_id,
                    sender_id,
                    ghost_ask["recipient_id"],
                    ghost_ask["message"]
                )
                
                logger.info(f"Ghost ask {ghost_ask_id} force sent after {attempts} attempts (chatbot gave in)")
                
                return {
                    "success": True,
                    "ghost_ask_id": ghost_ask_id,
                    "status": GhostAskStatus.SENT.value,
                    "message": "okay okay, you win. i'll send it this ONE time 🙄👻",
                    "attempts": attempts
                }
            
            persuasion = await ai_service.generate_persuasion_message(
                sender_id,
                ghost_ask["message"],
                attempt_count=attempts
            )
            
            time_remaining = await self._get_time_until_unlock(sender_id)
            
            logger.info(f"Ghost ask {ghost_ask_id} persuasion attempt {attempts}")
            
            return {
                "success": False,
                "ghost_ask_id": ghost_ask_id,
                "status": GhostAskStatus.PENDING.value,
                "message": "still locked",
                "unlock_required": True,
                "time_remaining_seconds": time_remaining,
                "persuasion_message": persuasion,
                "attempts": attempts,
                "can_force_send": attempts > 10
            }
            
        except Exception as e:
            logger.error(f"Error attempting to send ghost ask: {str(e)}")
            raise
    
    async def _send_ghost_ask(
        self,
        ghost_ask_id: str,
        sender_id: str,
        recipient_id: str,
        message: str
    ) -> None:
        """Actually send the ghost ask"""
        try:
            supabase.table("ghost_asks").update({
                "status": GhostAskStatus.SENT.value,
                "sent_at": datetime.utcnow().isoformat()
            }).eq("id", ghost_ask_id).execute()
            
            notification_data = {
                "user_id": recipient_id,
                "sender_id": "anonymous",
                "type": "ghost_ask",
                "title": "👻 Ghost Ask",
                "message": f"from a friend in your network: {message}",
                "data": {
                    "ghost_ask_id": ghost_ask_id,
                    "is_anonymous": True
                },
                "created_at": datetime.utcnow().isoformat(),
                "read": False
            }
            
            supabase.table("notifications").insert(notification_data).execute()
            
            logger.info(f"Sent ghost ask {ghost_ask_id} to {recipient_id}")
            
        except Exception as e:
            logger.error(f"Error sending ghost ask: {str(e)}")
            raise
    
    async def _check_rate_limits(
        self,
        user_id: str
    ) -> tuple[bool, Optional[str]]:
        """Check if user can send more ghost asks"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=1)
            
            response = supabase.table("ghost_asks").select(
                "id", count="exact"
            ).eq("sender_id", user_id).gte(
                "created_at", cutoff_time.isoformat()
            ).execute()
            
            count = response.count or 0
            
            if count >= settings.max_ghost_asks_per_day:
                return False, f"you've reached the daily limit of {settings.max_ghost_asks_per_day} ghost asks"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking ghost ask rate limits: {str(e)}")
            return True, None  # Fail open
    
    async def _get_time_until_unlock(self, user_id: str) -> int:
        """Get seconds until next challenge unlock opportunity"""
        try:
            
            response = supabase.table("daily_challenges").select(
                "challenge_time, has_posted"
            ).eq("user_id", user_id).order(
                "challenge_date", desc=True
            ).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                challenge = response.data[0]
                
                challenge_time = datetime.fromisoformat(challenge["challenge_time"].replace('Z', '+00:00'))
                
                now = datetime.now(timezone.utc)
                
                if challenge_time > now:
                    return int((challenge_time - now).total_seconds())
                
                challenge_end_time = challenge_time + timedelta(minutes=settings.challenge_unlock_window_minutes)
                if now < challenge_end_time and not challenge["has_posted"]:
                    return int((challenge_end_time - now).total_seconds())
            
            return 6 * 3600
            
        except Exception as e:
            logger.error(f"Error getting time until unlock: {str(e)}")
            return 6 * 3600


ghost_ask_service = GhostAskService()

