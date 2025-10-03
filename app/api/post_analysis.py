"""
    Post Analysis API endpoints
"""
from fastapi import APIRouter, HTTPException, Request
from app.models import (
    PostAnalysisRequest,
    PostAnalysisResponse,
    PostInsights
)
from app.services import post_service
from app.utils.logger import logger
from app.utils.rate_limiter import (
    check_user_rate_limit,
    check_ip_rate_limit,
    RateLimitConfig
)

router = APIRouter(prefix="/api/post-analysis", tags=["Post Analysis"])


@router.post("/analyze", response_model=PostAnalysisResponse)
async def analyze_post(request: PostAnalysisRequest, http_request: Request):
    """
    Analyze a post and extract structured insights
    
    - **user_id**: User ID who owns the post
    - **post_id**: Post ID to analyze
    - **image_url**: Optional image URL
    - **caption**: Optional caption text
    - **metadata**: Additional metadata
    
    Returns structured insights including location guess, outfit items, vibe descriptors, etc.
    """
    try:
        is_allowed, error_msg = check_user_rate_limit(
            request.user_id,
            "post_analysis",
            RateLimitConfig.POST_ANALYSIS_PER_USER_HOUR,
            window_minutes=60
        )
        
        if not is_allowed:
            return PostAnalysisResponse(
                success=False,
                error=error_msg
            )
        
        is_allowed_day, error_msg_day = check_user_rate_limit(
            request.user_id,
            "post_analysis_day",
            RateLimitConfig.POST_ANALYSIS_PER_USER_DAY,
            window_minutes=24 * 60
        )
        
        if not is_allowed_day:
            return PostAnalysisResponse(
                success=False,
                error=error_msg_day
            )
        
        client_ip = http_request.client.host if http_request.client else "unknown"
        is_allowed_ip, error_msg_ip = check_ip_rate_limit(
            client_ip,
            "post_analysis",
            50,
            window_minutes=60
        )
        
        if not is_allowed_ip:
            return PostAnalysisResponse(
                success=False,
                error=error_msg_ip
            )
        
        logger.info(f"Analyzing post {request.post_id} for user {request.user_id}")
        
        image_url = request.image_url
        caption = request.caption
        
        if not image_url and not caption:
            post_details = await post_service.get_post_details(request.post_id)
            if post_details:
                image_url = post_details.get("image_url")
                caption = post_details.get("content")
        
        insights = await post_service.analyze_post(
            user_id=request.user_id,
            post_id=request.post_id,
            image_url=image_url,
            caption=caption,
            metadata=request.metadata
        )
        
        return PostAnalysisResponse(
            success=True,
            post_id=request.post_id,
            insights=insights
        )
        
    except Exception as e:
        logger.error(f"Error in analyze_post endpoint: {str(e)}")
        return PostAnalysisResponse(
            success=False,
            post_id=request.post_id,
            error=str(e)
        )


@router.get("/post/{post_id}", response_model=PostAnalysisResponse)
async def get_post_analysis(post_id: str):
    """
    Get analysis for a specific post (fetches from database)
    
    - **post_id**: Post ID to analyze
    """
    try:
        logger.info(f"Getting analysis for post {post_id}")
        
        post_details = await post_service.get_post_details(post_id)
        
        if not post_details:
            raise HTTPException(status_code=404, detail="Post not found")
        
        insights = await post_service.analyze_post(
            user_id=post_details["user_id"],
            post_id=post_id,
            image_url=post_details.get("image_url"),
            caption=post_details.get("content")
        )
        
        return PostAnalysisResponse(
            success=True,
            post_id=post_id,
            insights=insights
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_post_analysis endpoint: {str(e)}")
        return PostAnalysisResponse(
            success=False,
            post_id=post_id,
            error=str(e)
        )

