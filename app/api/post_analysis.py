"""
    Post Analysis API endpoints
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from app.models import (
    PostAnalysisRequest,
    PostAnalysisResponse,
    PostInsights
)
from app.services import post_service, maps_service
from app.utils.logger import logger
from app.utils.rate_limiter import (
    check_user_rate_limit,
    check_ip_rate_limit,
    RateLimitConfig
)

router = APIRouter(prefix="/api/post-analysis", tags=["Post Analysis"])


async def _enhance_location_with_maps_data(location_guess: str, maps_service) -> Optional[str]:
    """
    Enhance location guess with comprehensive Google Maps data
    
    Args:
        location_guess: Basic location string from AI analysis
        maps_service: Maps service instance
        
    Returns:
        Enhanced location string with detailed information
    """
    try:
        logger.info(f"Enhancing location: {location_guess}")
        
        location_info = await maps_service.geocode_address(location_guess)
        if not location_info:
            logger.warning(f"Failed to geocode location: {location_guess}")
            return location_guess
        
        coordinates = location_info.get("coordinates", {})
        if not coordinates:
            logger.warning(f"No coordinates found for location: {location_guess}")
            return location_guess
        
        lat = coordinates.get("lat")
        lng = coordinates.get("lng")
        
        address_components = location_info.get("address_components", {})
        
        nearby_places = await maps_service.find_nearby_places(
            lat=lat,
            lng=lng,
            radius=500,
            place_type="cafe"  # Fixed: use place_type instead of place_types
        )
        
        location_parts = []
        
        neighborhood = address_components.get("neighborhood") or address_components.get("sublocality")
        if neighborhood:
            location_parts.append(neighborhood)
        
        city = address_components.get("city") or address_components.get("locality")
        if city:
            location_parts.append(city)
        
        state = address_components.get("state") or address_components.get("administrative_area_level_1")
        if state:
            location_parts.append(state)
        
        country = address_components.get("country")
        if country:
            location_parts.append(country)
        
        base_location = ", ".join(location_parts) if location_parts else location_guess
        
        if nearby_places and len(nearby_places) > 0:
            # Get the closest place
            closest_place = nearby_places[0]
            place_name = closest_place.get("name", "")
            place_type = closest_place.get("types", [""])[0] if closest_place.get("types") else ""
            
            if place_name and place_type in ["cafe", "restaurant", "store"]:
                enhanced_location = f"Near {place_name}, {base_location}"
            else:
                enhanced_location = base_location
        else:
            enhanced_location = base_location
        
        if address_components.get("postal_code"):
            postal_code = address_components["postal_code"]
            enhanced_location += f" ({postal_code})"
        
        logger.info(f"Enhanced location: {location_guess} -> {enhanced_location}")
        return enhanced_location
        
    except Exception as e:
        logger.error(f"Error enhancing location: {str(e)}")
        return location_guess


@router.post(
    "/analyze", 
    response_model=PostAnalysisResponse,
    tags=["Post Analysis"],
    summary="Analyze Post with AI",
    description="Analyze a post image and extract insights including enhanced location information",
    responses={
        200: {
            "description": "Post analysis completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "post_id": "123e4567-e89b-12d3-a456-426614174000",
                        "insights": {
                            "location_guess": "Blue Bottle Coffee, 66 Mint St, San Francisco, CA 94103, USA - Popular specialty coffee shop in Financial District",
                            "outfit_items": ["black jacket", "white shirt"],
                            "objects": ["MacBook Air", "coffee cup", "Google Meet interface"],
                            "vibe_descriptors": ["cozy", "productive"],
                            "colors": ["grey", "black", "blue"],
                            "activities": ["video call", "coding", "having coffee"],
                            "interests": ["technology", "coffee", "remote work"],
                            "summary": "A person is working on a MacBook Air while having a coffee and participating in a video call at Blue Bottle Coffee in San Francisco.",
                            "confidence_score": 0.9
                        },
                        "error": None
                    }
                }
            }
        },
        400: {
            "description": "Bad request - invalid input",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "post_id": "invalid-post-id",
                        "insights": None,
                        "error": "Invalid post_id or user_id format"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "post_id": "123e4567-e89b-12d3-a456-426614174000",
                        "insights": None,
                        "error": "Rate limit exceeded. Please try again later."
                    }
                }
            }
        }
    }
)
async def analyze_post(request: PostAnalysisRequest, http_request: Request):
    """
    **Analyze Post with AI - Advanced Image Analysis**
    
    Analyzes a post image and extracts comprehensive insights using OpenAI Vision and Google Maps integration.
    
    ### Features:
    - **📸 OpenAI Vision Analysis**: Advanced image analysis with object detection
    - **🗺️ Enhanced Location**: Google Maps integration for detailed location information
    - **👕 Outfit Detection**: Identifies clothing and accessories
    - **🎯 Object Recognition**: Detects objects, brands, and activities
    - **🎨 Color Analysis**: Extracts dominant colors from the image
    - **💭 Vibe Analysis**: Analyzes mood and atmosphere
    - **🎯 Interest Inference**: Infers user interests from post content
    - **💾 Caching**: Results are cached for performance
    
    ### Request Parameters:
    - **user_id** (required): UUID of the user who owns the post
    - **post_id** (required): UUID of the post to analyze
    - **image_url** (optional): URL of the post image (if not in database)
    - **caption** (optional): Post caption/content for additional context
    - **metadata** (optional): Additional metadata for analysis
    
    ### Response:
    - **location_guess**: Enhanced location with detailed Google Maps information
    - **outfit_items**: Array of identified clothing and accessories
    - **objects**: Array of detected objects, brands, and items
    - **vibe_descriptors**: Array of mood and atmosphere descriptors
    - **colors**: Array of dominant colors in the image
    - **activities**: Array of identified activities
    - **interests**: Array of inferred interests
    - **summary**: Brief summary of the post content
    - **confidence_score**: Analysis confidence score (0.0-1.0)
    
    ### Rate Limits:
    - User: 50 requests per hour
    - IP: 100 requests per hour
    
    ### Prerequisites:
    - OpenAI API key must be configured
    - Google Maps API key must be configured
    - Post must exist in the database
    - Image must be accessible via URL
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
        
        if insights and insights.location_guess:
            try:
                enhanced_location = await _enhance_location_with_maps_data(insights.location_guess, maps_service)
                if enhanced_location:
                    insights.location_guess = enhanced_location
                    logger.info(f"Enhanced location for post {request.post_id}: {enhanced_location}")
            except Exception as e:
                logger.warning(f"Failed to enhance location for post {request.post_id}: {str(e)}")
        
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
        
        if insights and insights.location_guess:
            try:
                enhanced_location = await _enhance_location_with_maps_data(insights.location_guess, maps_service)
                if enhanced_location:
                    insights.location_guess = enhanced_location
                    logger.info(f"Enhanced location for post {post_id}: {enhanced_location}")
            except Exception as e:
                logger.warning(f"Failed to enhance location for post {post_id}: {str(e)}")
        
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

