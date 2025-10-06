"""
Location Services API endpoints
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.services import maps_service
from app.utils.logger import logger
from app.utils.rate_limiter import (
    check_user_rate_limit,
    check_ip_rate_limit,
    RateLimitConfig
)

router = APIRouter(prefix="/api/location", tags=["Location Services"])


class LocationQueryRequest(BaseModel):
    """Request for location-based queries"""
    user_id: str = Field(..., description="User ID making the request")
    query: str = Field(..., description="Location-based query")
    current_location: Optional[Dict[str, float]] = Field(None, description="Current location coordinates")
    max_results: int = Field(10, ge=1, le=50, description="Maximum number of results")


class NearbyPlace(BaseModel):
    """Nearby place information"""
    name: str
    place_id: str
    rating: Optional[float] = None
    price_level: Optional[int] = None
    vicinity: Optional[str] = None
    types: List[str] = []
    coordinates: Optional[Dict[str, float]] = None


class LocationQueryResponse(BaseModel):
    """Response from location query"""
    success: bool
    query: str
    current_location: Optional[Dict[str, Any]] = None
    nearby_places: List[NearbyPlace] = []
    location_insights: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post(
    "/query", 
    response_model=LocationQueryResponse,
    tags=["Location Services"],
    summary="Query Location Services",
    description="Process location-based queries using Google Maps integration",
    responses={
        200: {
            "description": "Location query processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "query": "best coffee near me",
                        "current_location": {
                            "address": "San Francisco, CA, USA",
                            "coordinates": {
                                "lat": 37.7749,
                                "lng": -122.4194
                            }
                        },
                        "nearby_places": [
                            {
                                "name": "Blue Bottle Coffee",
                                "place_id": "ChIJ...",
                                "rating": 4.5,
                                "price_level": 2,
                                "vicinity": "66 Mint St, San Francisco",
                                "types": ["cafe", "food", "point_of_interest"],
                                "coordinates": {
                                    "lat": 37.7749,
                                    "lng": -122.4194
                                }
                            }
                        ],
                        "location_insights": {
                            "neighborhood": "Financial District",
                            "city": "San Francisco",
                            "state": "California"
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
                        "query": "invalid query",
                        "current_location": None,
                        "nearby_places": [],
                        "location_insights": None,
                        "error": "Invalid user_id or query format"
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
                        "query": "best coffee near me",
                        "current_location": None,
                        "nearby_places": [],
                        "location_insights": None,
                        "error": "Rate limit exceeded. Please try again later."
                    }
                }
            }
        }
    }
)
async def query_location(request: LocationQueryRequest, http_request: Request):
    """
    **Query Location Services - Google Maps Integration**
    
    Processes location-based queries using Google Maps API for geocoding, nearby places, and location insights.
    
    ### Features:
    - **🗺️ Google Maps Integration**: Full Google Maps API integration
    - **📍 Geocoding**: Convert addresses to coordinates and vice versa
    - **🔍 Nearby Places**: Find nearby businesses and points of interest
    - **🏙️ Location Insights**: Get neighborhood, city, and state information
    - **☕ Smart Categories**: Automatic detection of coffee, restaurants, gyms, etc.
    
    ### Request Parameters:
    - **user_id** (required): UUID of the user making the request
    - **query** (required): Location-based query text
    - **current_location** (optional): Current location coordinates `{"lat": 37.7749, "lng": -122.4194}`
    - **max_results** (optional): Maximum number of results (1-50, default: 10)
    
    ### Query Examples:
    - **Coffee**: "best coffee near me", "coffee shops nearby"
    - **Food**: "restaurants near me", "good food places"
    - **Fitness**: "gym near me", "fitness centers"
    - **General**: "what's around me", "places near my location"
    
    ### Response:
    - **current_location**: User's current location with address and coordinates
    - **nearby_places**: Array of nearby places with ratings, prices, and details
    - **location_insights**: Neighborhood, city, and state information
    - **place_details**: Name, rating, price level, vicinity, types, coordinates
    
    ### Rate Limits:
    - User: 20 requests per hour
    - IP: 50 requests per hour
    
    ### Prerequisites:
    - Google Maps API key must be configured
    - For best results, provide current_location coordinates
    - Query should contain location-related keywords
    """
    try:
        is_allowed, error_msg = check_user_rate_limit(
            request.user_id,
            "location_query",
            20,
            window_minutes=60
        )
        
        if not is_allowed:
            return LocationQueryResponse(
                success=False,
                query=request.query,
                error=error_msg
            )
        
        client_ip = http_request.client.host if http_request.client else "unknown"
        is_allowed_ip, error_msg_ip = check_ip_rate_limit(
            client_ip,
            "location_query",
            50,
            window_minutes=60
        )
        
        if not is_allowed_ip:
            return LocationQueryResponse(
                success=False,
                query=request.query,
                error=error_msg_ip
            )
        
        logger.info(f"Processing location query for user {request.user_id}: {request.query}")
        
        location_context = await maps_service.analyze_user_location_context(
            request.user_id,
            request.current_location
        )
        
        query_lower = request.query.lower()
        nearby_places = []
        
        if "coffee" in query_lower or "cafe" in query_lower:
            if request.current_location:
                places = await maps_service.find_nearby_places(
                    request.current_location["lat"],
                    request.current_location["lng"],
                    "cafe",
                    radius=1000
                )
                nearby_places = places[:request.max_results]
        
        elif "restaurant" in query_lower or "food" in query_lower or "eat" in query_lower:
            if request.current_location:
                places = await maps_service.find_nearby_places(
                    request.current_location["lat"],
                    request.current_location["lng"],
                    "restaurant",
                    radius=1000
                )
                nearby_places = places[:request.max_results]
        
        elif "gym" in query_lower or "fitness" in query_lower:
            if request.current_location:
                places = await maps_service.find_nearby_places(
                    request.current_location["lat"],
                    request.current_location["lng"],
                    "gym",
                    radius=1000
                )
                nearby_places = places[:request.max_results]
        
        nearby_places_response = []
        for place in nearby_places:
            nearby_place = NearbyPlace(
                name=place["name"],
                place_id=place["place_id"],
                rating=place.get("rating"),
                price_level=place.get("price_level"),
                vicinity=place.get("vicinity"),
                types=place.get("types", []),
                coordinates={
                    "lat": place["geometry"]["location"]["lat"],
                    "lng": place["geometry"]["location"]["lng"]
                } if place.get("geometry", {}).get("location") else None
            )
            nearby_places_response.append(nearby_place)
        
        return LocationQueryResponse(
            success=True,
            query=request.query,
            current_location=location_context.get("current_location"),
            nearby_places=nearby_places_response,
            location_insights=location_context.get("location_insights")
        )
        
    except Exception as e:
        logger.error(f"Error in location query: {str(e)}")
        return LocationQueryResponse(
            success=False,
            query=request.query,
            error=str(e)
        )


@router.post("/geocode")
async def geocode_address(address: str, http_request: Request):
    """
    Geocode an address to get coordinates
    
    - **address**: Address string to geocode
    """
    try:
        client_ip = http_request.client.host if http_request.client else "unknown"
        is_allowed_ip, error_msg_ip = check_ip_rate_limit(
            client_ip,
            "geocoding",
            30,
            window_minutes=60
        )
        
        if not is_allowed_ip:
            return {"success": False, "error": error_msg_ip}
        
        logger.info(f"Geocoding address: {address}")
        
        location_info = await maps_service.geocode_address(address)
        
        if location_info:
            return {
                "success": True,
                "address": address,
                "location": location_info
            }
        else:
            return {
                "success": False,
                "error": "Address not found"
            }
        
    except Exception as e:
        logger.error(f"Error in geocoding: {str(e)}")
        return {"success": False, "error": str(e)}


@router.post("/reverse-geocode")
async def reverse_geocode(lat: float, lng: float, http_request: Request):
    """
    Reverse geocode coordinates to get address
    
    - **lat**: Latitude
    - **lng**: Longitude
    """
    try:
        client_ip = http_request.client.host if http_request.client else "unknown"
        is_allowed_ip, error_msg_ip = check_ip_rate_limit(
            client_ip,
            "reverse_geocoding",
            30,
            window_minutes=60
        )
        
        if not is_allowed_ip:
            return {"success": False, "error": error_msg_ip}
        
        logger.info(f"Reverse geocoding coordinates: {lat}, {lng}")
        
        location_info = await maps_service.reverse_geocode(lat, lng)
        
        if location_info:
            return {
                "success": True,
                "coordinates": {"lat": lat, "lng": lng},
                "location": location_info
            }
        else:
            return {
                "success": False,
                "error": "Location not found"
            }
        
    except Exception as e:
        logger.error(f"Error in reverse geocoding: {str(e)}")
        return {"success": False, "error": str(e)}


@router.get("/place/{place_id}")
async def get_place_details(place_id: str, http_request: Request):
    """
    Get detailed information about a place
    
    - **place_id**: Google Places place ID
    """
    try:
        client_ip = http_request.client.host if http_request.client else "unknown"
        is_allowed_ip, error_msg_ip = check_ip_rate_limit(
            client_ip,
            "place_details",
            20,
            window_minutes=60
        )
        
        if not is_allowed_ip:
            return {"success": False, "error": error_msg_ip}
        
        logger.info(f"Getting place details for: {place_id}")
        
        place_details = await maps_service.get_place_details(place_id)
        
        if place_details:
            return {
                "success": True,
                "place_id": place_id,
                "details": place_details
            }
        else:
            return {
                "success": False,
                "error": "Place not found"
            }
        
    except Exception as e:
        logger.error(f"Error getting place details: {str(e)}")
        return {"success": False, "error": str(e)}
