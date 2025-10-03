"""
Warm Intro API endpoints
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from app.models import (
    WarmIntroRequest,
    WarmIntroResponse,
    IntroAcceptRequest,
    IntroAcceptResponse,
    IntroRequestStatus
)
from app.services import intro_service
from app.utils.logger import logger
from app.utils.rate_limiter import (
    check_user_rate_limit,
    RateLimitConfig
)
from app.database import supabase

router = APIRouter(prefix="/api/intro", tags=["Warm Intro"])


@router.post("/request", response_model=WarmIntroResponse)
async def request_warm_intro(request: WarmIntroRequest, http_request: Request):
    """
    Request a warm introduction to a 2nd degree connection
    
    - **requester_id**: User requesting the intro
    - **target_id**: User to be introduced to
    - **query_context**: Original query that led to this intro
    - **why_match**: Why this person is a match
    - **mutual_ids**: List of mutual connection IDs
    
    Creates an intro request and notifies the target user.
    If accepted, creates a chat with a warm intro message.
    """
    try:
        logger.info(f"Warm intro request from {request.requester_id} to {request.target_id}")
        
        is_allowed, error_msg = check_user_rate_limit(
            request.requester_id,
            "intro_request",
            RateLimitConfig.INTRO_REQUEST_PER_USER_DAY,
            window_minutes=24 * 60
        )
        
        if not is_allowed:
            return WarmIntroResponse(
                success=False,
                error=error_msg
            )
        
        is_allowed_hour, error_msg_hour = check_user_rate_limit(
            request.requester_id,
            "intro_request_hour",
            RateLimitConfig.INTRO_REQUEST_PER_USER_HOUR,
            window_minutes=60
        )
        
        if not is_allowed_hour:
            return WarmIntroResponse(
                success=False,
                error=error_msg_hour
            )
        
        result = await intro_service.create_intro_request(
            requester_id=request.requester_id,
            target_id=request.target_id,
            query_context=request.query_context,
            why_match=request.why_match,
            mutual_ids=request.mutual_ids
        )
        
        if not result.get("success"):
            return WarmIntroResponse(
                success=False,
                message="Failed to create intro request",
                error=result.get("error")
            )
        
        return WarmIntroResponse(
            success=True,
            intro_request_id=result["intro_request_id"],
            status=IntroRequestStatus.PENDING,
            message="Intro request sent! They'll be notified."
        )
        
    except Exception as e:
        logger.error(f"Error in request_warm_intro endpoint: {str(e)}")
        return WarmIntroResponse(
            success=False,
            message="Error creating intro request",
            error=str(e)
        )


@router.get("/my-requests/{user_id}")
async def get_my_intro_requests(user_id: str, status: Optional[str] = None):
    """
    Get all intro requests for a user (sent and received)
    
    - **user_id**: User ID
    - **status**: Optional filter by status (pending, accepted, declined, expired)
    
    Returns both sent requests (user initiated) and received requests (user is target)
    """
    try:
        result = await intro_service.get_user_intro_requests(user_id, status)
        return result
        
    except Exception as e:
        logger.error(f"Error getting intro requests: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/expire-old-requests")
async def expire_old_intro_requests():
    """
    Expire old pending intro requests (cron job endpoint)
    
    Should be called periodically to clean up expired requests.
    Changes status from PENDING to EXPIRED for requests past expiration date.
    """
    try:
        count = await intro_service.expire_old_requests()
        return {
            "success": True,
            "expired_count": count,
            "message": f"Expired {count} intro requests"
        }
        
    except Exception as e:
        logger.error(f"Error expiring intro requests: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/respond", response_model=IntroAcceptResponse)
async def respond_to_intro(request: IntroAcceptRequest):
    """
    Respond to an intro request (accept or decline)
    
    - **intro_request_id**: Intro request ID
    - **target_response**: True to accept, False to decline
    
    If accepted, creates a chat between the users with a warm intro message.
    """
    try:
        logger.info(f"Intro response for request {request.intro_request_id}: "
                   f"{'accept' if request.target_response else 'decline'}")
        
        result = await intro_service.respond_to_intro(
            intro_request_id=request.intro_request_id,
            target_response=request.target_response
        )
        
        if not result.get("success"):
            return IntroAcceptResponse(
                success=False,
                message="Failed to process intro response",
                error=result.get("error")
            )
        
        if request.target_response:
            return IntroAcceptResponse(
                success=True,
                chat_id=result.get("chat_id"),
                intro_message=result.get("intro_message"),
                message="Connection accepted! Chat created."
            )
        else:
            return IntroAcceptResponse(
                success=True,
                message="Intro request declined."
            )
        
    except Exception as e:
        logger.error(f"Error in respond_to_intro endpoint: {str(e)}")
        return IntroAcceptResponse(
            success=False,
            message="Error processing intro response",
            error=str(e)
        )


@router.get("/pending/{user_id}")
async def get_pending_intros(user_id: str):
    """
    Get pending intro requests for a user
    
    - **user_id**: User ID
    """
    try:
        
        response = supabase.table("intro_requests").select(
            "*"
        ).eq("target_id", user_id).eq(
            "status", IntroRequestStatus.PENDING.value
        ).execute()
        
        return {
            "success": True,
            "pending_intros": response.data
        }
        
    except Exception as e:
        logger.error(f"Error getting pending intros: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

