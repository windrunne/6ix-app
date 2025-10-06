"""
Network Query API endpoints
"""
from fastapi import APIRouter, HTTPException, Request
from app.models import (
    NetworkQueryRequest,
    NetworkQueryResponse,
    NetworkMatch,
    ConnectionDegree
)
from app.services import ai_service, network_service
from app.config.settings import settings
from app.utils.logger import logger
from app.utils.rate_limiter import (
    check_user_rate_limit,
    check_ip_rate_limit,
    RateLimitConfig
)

router = APIRouter(prefix="/api/network", tags=["Network Query"])


@router.post(
    "/query", 
    response_model=NetworkQueryResponse,
    tags=["Network Query"],
    summary="Query Network with AI",
    description="Query user's network with natural language using AI semantic matching and demographic filtering",
    responses={
        200: {
            "description": "Network query completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "query": "who is a asian girl i know",
                        "matches": [
                            {
                                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                "name": "Sarah Chen",
                                "username": "sarahchen",
                                "profile_photos": ["https://example.com/photo.jpg"],
                                "degree": 1,
                                "why_match": "Sarah is Asian and female, matching your query criteria",
                                "mutuals": [
                                    {
                                        "id": "456e7890-e89b-12d3-a456-426614174001",
                                        "name": "John Doe",
                                        "profile_photo": "https://example.com/john.jpg"
                                    }
                                ],
                                "mutual_count": 3,
                                "action": "offer_intro",
                                "school": "Stanford University",
                                "major": "Computer Science",
                                "graduation_year": 2023,
                                "gender": "female",
                                "race": "asian"
                            }
                        ],
                        "total_matches": 1,
                        "has_first_degree": True,
                        "has_second_degree": False,
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
                        "matches": [],
                        "total_matches": 0,
                        "has_first_degree": False,
                        "has_second_degree": False,
                        "error": "Invalid user_id format"
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
                        "query": "who do i know",
                        "matches": [],
                        "total_matches": 0,
                        "has_first_degree": False,
                        "has_second_degree": False,
                        "error": "Rate limit exceeded. Please try again later."
                    }
                }
            }
        }
    }
)
async def query_network(request: NetworkQueryRequest, http_request: Request):
    """
    **Query Network with AI - Semantic Network Search**
    
    Queries user's network with natural language using AI semantic matching and demographic filtering.
    
    ### Features:
    - **🤖 AI Semantic Understanding**: Uses OpenAI to understand natural language queries
    - **👥 Demographic Filtering**: Supports gender and race-based queries
    - **🔗 Connection Degrees**: Searches 1st and 2nd degree connections
    - **🤝 Warm Intro Support**: Offers introduction options for 2nd degree matches
    - **📊 Detailed Matching**: Provides explanations for why each person matches
    
    ### Request Parameters:
    - **user_id** (required): UUID of the user making the query
    - **query** (required): Natural language query (3-200 characters)
    - **max_results** (optional): Maximum number of results (1-50, default: 10)
    - **include_second_degree** (optional): Include 2nd degree connections (default: true)
    
    ### Query Examples:
    - **Demographic**: "who is a asian girl i know", "find me a black guy"
    - **Location**: "who do i know in paris?", "people near me"
    - **Interests**: "who likes coffee?", "find someone into fitness"
    - **Combined**: "asian girl who likes coffee in san francisco"
    
    ### Response:
    - **matches**: Array of matched users with detailed information
    - **why_match**: Explanation of why this person matches the query
    - **degree**: Connection degree (1 = direct, 2 = mutual connection)
    - **mutuals**: List of mutual connections for 2nd degree matches
    - **action**: Suggested action (e.g., "offer_intro" for 2nd degree)
    - **demographics**: Gender and race information when available
    
    ### Rate Limits:
    - User: 30 requests per hour
    - IP: 100 requests per hour
    
    ### Prerequisites:
    - User must have network connections
    - For demographic queries, users must have analyzed profile photos
    - For location queries, users must have location data in posts
    """
    try:
        is_allowed, error_msg = check_user_rate_limit(
            request.user_id,
            "network_query",
            RateLimitConfig.NETWORK_QUERY_PER_USER_HOUR,
            window_minutes=60
        )
        
        if not is_allowed:
            return NetworkQueryResponse(
                success=False,
                query=request.query,
                matches=[],
                total_matches=0,
                error=error_msg
            )
        
        client_ip = http_request.client.host if http_request.client else "unknown"
        is_allowed_ip, error_msg_ip = check_ip_rate_limit(
            client_ip,
            "network_query",
            RateLimitConfig.NETWORK_QUERY_PER_IP_HOUR,
            window_minutes=60
        )
        
        if not is_allowed_ip:
            return NetworkQueryResponse(
                success=False,
                query=request.query,
                matches=[],
                total_matches=0,
                error=error_msg_ip
            )
        
        
        if settings.use_semantic_search:

            first_degree_matches, second_degree_matches = await network_service.search_network_semantic(
                user_id=request.user_id,
                query=request.query,
                max_degree=2 if request.include_second_degree else 1,
                min_match_score=settings.semantic_min_score
            )
        else:

            connections = await network_service.get_user_connections(
                request.user_id,
                max_degree=2 if request.include_second_degree else 1
            )
            
            all_conn_ids = []
            for degree_conns in connections.values():
                all_conn_ids.extend([c["connection_id"] for c in degree_conns])
            
            if not all_conn_ids:
                return NetworkQueryResponse(
                    success=True,
                    query=request.query,
                    matches=[],
                    total_matches=0,
                    has_first_degree=False,
                    has_second_degree=False
                )
            
            signals = await network_service.get_user_signals(all_conn_ids[:100])
            
            if signals:
                sample_user_id = list(signals.keys())[0]
                sample_signals = signals[sample_user_id]

            criteria = await ai_service.process_network_query(
                query=request.query,
                user_signals=list(signals.values()),
                connection_degree=2 if request.include_second_degree else 1
            )

            first_degree_matches, second_degree_matches = await network_service.search_network(
                user_id=request.user_id,
                criteria=criteria,
                max_degree=2 if request.include_second_degree else 1
            )
        
        matches = []
        
        for i, match in enumerate(first_degree_matches[:request.max_results]):
            user_signals = match["signals"]
            
            network_match = NetworkMatch(
                user_id=match["user_id"],
                name=user_signals.get("name", "Unknown"),
                username=user_signals.get("username"),
                profile_photos=user_signals.get("profile_photos", []),
                degree=ConnectionDegree.FIRST,
                why_match=" and ".join(match["match_reasons"]),
                mutuals=[],
                mutual_count=0,
                action=None,
                school=user_signals.get("school"),
                major=user_signals.get("major"),
                graduation_year=user_signals.get("graduation_year"),
                gender=user_signals.get("gender"),
                race=user_signals.get("race")
            )
            matches.append(network_match)
        
        if not first_degree_matches and second_degree_matches:
            for i, match in enumerate(second_degree_matches[:request.max_results]):
                user_signals = match["signals"]
                
                mutuals = await network_service.get_mutual_connections(
                    request.user_id,
                    match["user_id"]
                )
                
                network_match = NetworkMatch(
                    user_id=match["user_id"],
                    name=user_signals.get("name", "Unknown"),
                    username=user_signals.get("username"),
                    profile_photos=user_signals.get("profile_photos", []),
                    degree=ConnectionDegree.SECOND,
                    why_match=" and ".join(match["match_reasons"]),
                    mutuals=mutuals,
                    mutual_count=len(mutuals),
                    action="offer_intro",
                    school=user_signals.get("school"),
                    major=user_signals.get("major"),
                    graduation_year=user_signals.get("graduation_year"),
                    gender=user_signals.get("gender"),
                    race=user_signals.get("race")
                )
                matches.append(network_match)
        
        
        return NetworkQueryResponse(
            success=True,
            query=request.query,
            matches=matches,
            total_matches=len(matches),
            has_first_degree=len(first_degree_matches) > 0,
            has_second_degree=len(second_degree_matches) > 0
        )
        
    except Exception as e:
        logger.error(f"Error in query_network endpoint: {str(e)}")
        return NetworkQueryResponse(
            success=False,
            query=request.query,
            matches=[],
            total_matches=0,
            error=str(e)
        )


@router.get("/connections/{user_id}")
async def get_user_connections(user_id: str, max_degree: int = 2):
    """
    Get user's connections grouped by degree
    
    - **user_id**: User ID
    - **max_degree**: Maximum degree to fetch (1-3)
    """
    try:
        connections = await network_service.get_user_connections(user_id, max_degree)
        
        return {
            "success": True,
            "user_id": user_id,
            "connections": connections
        }
        
    except Exception as e:
        logger.error(f"Error getting connections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

