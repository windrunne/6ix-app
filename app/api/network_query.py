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


@router.post("/query", response_model=NetworkQueryResponse)
async def query_network(request: NetworkQueryRequest, http_request: Request):
    """
    Query user's network with natural language using AI semantic matching
    
    - **user_id**: User ID making the query
    - **query**: Natural language query (e.g., "who do i know in paris?", "who likes coffee?")
    - **max_results**: Maximum number of results to return
    - **include_second_degree**: Include 2nd degree connections
    
    Uses AI to semantically understand the query and match users based on:
    - Profile information (school, major, interests)
    - Recent posts and content
    - Semantic understanding (e.g., "coffee lover" matches cafe posts)
    
    Returns matches from 1st and 2nd degree connections with why they match.
    For 2nd degree matches, offers warm intro option.
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
        
        logger.info(f"Network query from user {request.user_id}: {request.query}")
        
        if settings.use_semantic_search:
            logger.info("Using AI semantic search")

            first_degree_matches, second_degree_matches = await network_service.search_network_semantic(
                user_id=request.user_id,
                query=request.query,
                max_degree=2 if request.include_second_degree else 1,
                min_match_score=settings.semantic_min_score
            )
        else:
            logger.info("Using keyword-based search")

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
        
        for match in first_degree_matches[:request.max_results]:
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
                keyword_summary=user_signals.get("keyword_summary", [])
            )
            matches.append(network_match)
        
        if not first_degree_matches and second_degree_matches:
            for match in second_degree_matches[:request.max_results]:
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
                    keyword_summary=user_signals.get("keyword_summary", [])
                )
                matches.append(network_match)
        
        logger.info(f"Found {len(matches)} matches for query: {request.query}")
        
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

