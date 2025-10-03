"""
Ghost Ask API endpoints
"""
from fastapi import APIRouter, HTTPException, Request
from app.models import (
    GhostAskRequest,
    GhostAskResponse,
    GhostAskSendRequest,
    GhostAskStatus
)
from app.services import ghost_ask_service
from app.utils.logger import logger
from app.database import supabase
from app.utils.rate_limiter import (
    check_user_rate_limit,
    check_ip_rate_limit,
    RateLimitConfig
)

router = APIRouter(prefix="/api/ghost-ask", tags=["Ghost Ask"])


@router.post("/create", response_model=GhostAskResponse)
async def create_ghost_ask(request: GhostAskRequest, http_request: Request):
    """
    Create a ghost ask (anonymous message)
    
    - **sender_id**: User sending the ghost ask
    - **recipient_id**: User receiving the ghost ask
    - **message**: Anonymous message content
    
    Only sends immediately if the user posted within the last 6 minutes.
    Otherwise, requires posting to unlock, with persuasive nudges.
    
    **Rate Limits:**
    - Per user: 3 ghost asks per day
    - Per IP: 10 ghost asks per day
    """
    try:
        is_allowed, error_msg = check_user_rate_limit(
            request.sender_id,
            "ghost_ask_create",
            RateLimitConfig.GHOST_ASK_CREATE_PER_USER_DAY,
            window_minutes=24 * 60  # 24 hours
        )
        
        if not is_allowed:
            return GhostAskResponse(
                success=False,
                message="Rate limit exceeded",
                error=error_msg
            )
        
        client_ip = http_request.client.host if http_request.client else "unknown"
        is_allowed_ip, error_msg_ip = check_ip_rate_limit(
            client_ip,
            "ghost_ask_create",
            10,  # 10 per day per IP
            window_minutes=24 * 60
        )
        
        if not is_allowed_ip:
            return GhostAskResponse(
                success=False,
                message="Rate limit exceeded",
                error=error_msg_ip
            )
        
        logger.info(f"Ghost ask creation from {request.sender_id} to {request.recipient_id}")
        
        result = await ghost_ask_service.create_ghost_ask(
            sender_id=request.sender_id,
            recipient_id=request.recipient_id,
            message=request.message
        )
        
        return GhostAskResponse(
            success=result.get("success", False),
            ghost_ask_id=result.get("ghost_ask_id"),
            status=GhostAskStatus(result.get("status")) if result.get("status") else None,
            message=result.get("message", ""),
            unlock_required=result.get("unlock_required", False),
            time_remaining_seconds=result.get("time_remaining_seconds"),
            persuasion_message=result.get("persuasion_message"),
            attempts=result.get("attempts"),
            can_force_send=result.get("can_force_send"),
            error=result.get("error")
        )
        
    except Exception as e:
        logger.error(f"Error in create_ghost_ask endpoint: {str(e)}")
        return GhostAskResponse(
            success=False,
            message="Error creating ghost ask",
            error=str(e)
        )


@router.post("/send", response_model=GhostAskResponse)
async def send_ghost_ask(request: GhostAskSendRequest):
    """
    Attempt to send a ghost ask
    
    - **ghost_ask_id**: Ghost ask ID
    - **sender_id**: User sending the ghost ask
    - **force_send**: Force send after 10+ persuasion attempts
    
    Checks if user has posted within 6 minutes. If not, returns persuasion message.
    After 10+ attempts, allows force sending with explicit confirmation.
    """
    try:
        logger.info(f"Attempting to send ghost ask {request.ghost_ask_id}")
        
        result = await ghost_ask_service.attempt_send_ghost_ask(
            ghost_ask_id=request.ghost_ask_id,
            sender_id=request.sender_id,
            force_send=request.force_send
        )
        
        return GhostAskResponse(
            success=result.get("success", False),
            ghost_ask_id=result.get("ghost_ask_id"),
            status=GhostAskStatus(result.get("status")) if result.get("status") else None,
            message=result.get("message", ""),
            unlock_required=result.get("unlock_required", False),
            time_remaining_seconds=result.get("time_remaining_seconds"),
            persuasion_message=result.get("persuasion_message"),
            attempts=result.get("attempts"),
            can_force_send=result.get("can_force_send"),
            error=result.get("error")
        )
        
    except Exception as e:
        logger.error(f"Error in send_ghost_ask endpoint: {str(e)}")
        return GhostAskResponse(
            success=False,
            message="Error sending ghost ask",
            error=str(e)
        )


@router.get("/status/{ghost_ask_id}")
async def get_ghost_ask_status(ghost_ask_id: str):
    """
    Get status of a ghost ask
    
    - **ghost_ask_id**: Ghost ask ID
    """
    try:
        
        response = supabase.table("ghost_asks").select(
            "id, status, created_at, sent_at, unlocked, persuasion_attempts"
        ).eq("id", ghost_ask_id).single().execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Ghost ask not found")
        
        return {
            "success": True,
            "ghost_ask": response.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ghost ask status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/sent")
async def get_sent_ghost_asks(user_id: str):
    """
    Get ghost asks sent by a user
    
    - **user_id**: User ID
    """
    try:
        
        response = supabase.table("ghost_asks").select(
            "*"
        ).eq("sender_id", user_id).order("created_at", desc=True).execute()
        
        return {
            "success": True,
            "ghost_asks": response.data
        }
        
    except Exception as e:
        logger.error(f"Error getting sent ghost asks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

