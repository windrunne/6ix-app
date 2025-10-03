"""
Network service for managing user connections and network queries
"""
from typing import List, Dict, Any, Optional, Tuple
from app.database import supabase
from app.models import ConnectionDegree, MutualConnection
from app.utils.logger import logger
from app.services.ai_service import ai_service
from app.config.settings import settings
import asyncio


class NetworkService:
    """Service for network operations"""
    
    async def get_user_connections(
        self,
        user_id: str,
        max_degree: int = 2
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get user's connections up to specified degree
        
        Args:
            user_id: User ID
            max_degree: Maximum connection degree to fetch
            
        Returns:
            Dictionary mapping degree to list of connections
        """
        try:
            response = supabase.table("user_connections").select(
                "connection_id, degree, is_chat, mutuals"
            ).eq("user_id", user_id).lte("degree", max_degree).execute()
            
            connections_by_degree = {1: [], 2: [], 3: []}
            
            for conn in response.data:
                degree = conn.get("degree")
                if degree in connections_by_degree:
                    connections_by_degree[degree].append(conn)
            
            logger.info(f"Fetched connections for user {user_id}: "
                       f"1°={len(connections_by_degree[1])}, "
                       f"2°={len(connections_by_degree[2])}")
            
            return connections_by_degree
            
        except Exception as e:
            logger.error(f"Error getting user connections: {str(e)}")
            raise
    
    async def get_mutual_connections(
        self,
        user_id: str,
        target_id: str
    ) -> List[MutualConnection]:
        """
        Get mutual connections between two users
        
        Args:
            user_id: First user ID
            target_id: Second user ID
            
        Returns:
            List of mutual connections
        """
        try:
            user1_conns = supabase.table("user_connections").select(
                "connection_id"
            ).eq("user_id", user_id).eq("degree", 1).execute()
            
            user2_conns = supabase.table("user_connections").select(
                "connection_id"
            ).eq("user_id", target_id).eq("degree", 1).execute()
            
            user1_conn_ids = {c["connection_id"] for c in user1_conns.data}
            user2_conn_ids = {c["connection_id"] for c in user2_conns.data}
            
            mutual_ids = user1_conn_ids.intersection(user2_conn_ids)
            
            if not mutual_ids:
                return []
            
            mutuals_response = supabase.table("users").select(
                "id, name, profile_photos"
            ).in_("id", list(mutual_ids)).execute()
            
            mutuals = [
                MutualConnection(
                    id=m["id"],
                    name=m.get("name", "Unknown"),
                    profile_photo=m.get("profile_photos", [None])[0]
                )
                for m in mutuals_response.data
            ]
            
            logger.info(f"Found {len(mutuals)} mutual connections between {user_id} and {target_id}")
            return mutuals
            
        except Exception as e:
            logger.error(f"Error getting mutual connections: {str(e)}")
            raise
    
    async def get_user_signals(
        self,
        user_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get user signals/attributes for matching
        
        Args:
            user_ids: List of user IDs
            
        Returns:
            Dictionary mapping user_id to signals
        """
        try:
            users_response = supabase.table("users").select(
                "id, name, username, school, major, graduation_year, "
                "school_type, keyword_summary, profile_photos"
            ).in_("id", user_ids).execute()
            
            users_data = {u["id"]: u for u in users_response.data}
            
            posts_response = supabase.table("posts").select(
                "user_id, content, category, created_at"
            ).in_("user_id", user_ids).order(
                "created_at", desc=True
            ).limit(100).execute()
            
            posts_by_user = {}
            for post in posts_response.data:
                uid = post["user_id"]
                if uid not in posts_by_user:
                    posts_by_user[uid] = []
                posts_by_user[uid].append(post)
            
            signals = {}
            for user_id in user_ids:
                user_data = users_data.get(user_id, {})
                user_posts = posts_by_user.get(user_id, [])
                
                signals[user_id] = {
                    "name": user_data.get("name"),
                    "username": user_data.get("username"),
                    "school": user_data.get("school"),
                    "major": user_data.get("major"),
                    "graduation_year": user_data.get("graduation_year"),
                    "school_type": user_data.get("school_type"),
                    "keyword_summary": user_data.get("keyword_summary", []),
                    "profile_photos": user_data.get("profile_photos", []),
                    "recent_posts": [
                        {
                            "content": p.get("content"),
                            "category": p.get("category"),
                            "created_at": p.get("created_at")
                        }
                        for p in user_posts[:5]
                    ]
                }
            
            logger.info(f"Retrieved signals for {len(signals)} users")
            return signals
            
        except Exception as e:
            logger.error(f"Error getting user signals: {str(e)}")
            raise
    
    async def search_network(
        self,
        user_id: str,
        criteria: Dict[str, Any],
        max_degree: int = 2
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Search user's network based on criteria
        
        Args:
            user_id: User ID performing search
            criteria: Search criteria dictionary
            max_degree: Maximum connection degree
            
        Returns:
            Tuple of (first_degree_matches, second_degree_matches)
        """
        try:
            connections = await self.get_user_connections(user_id, max_degree)
            
            all_conn_ids = []
            for degree_conns in connections.values():
                all_conn_ids.extend([c["connection_id"] for c in degree_conns])
            
            if not all_conn_ids:
                return [], []
            
            signals = await self.get_user_signals(all_conn_ids)
            
            first_degree_matches = []
            second_degree_matches = []
            
            for degree, degree_conns in connections.items():
                for conn in degree_conns:
                    conn_id = conn["connection_id"]
                    conn_signals = signals.get(conn_id, {})
                    
                    match_score, match_reasons = self._match_criteria(conn_signals, criteria)
                    
                    if match_score > 0:
                        match_data = {
                            "user_id": conn_id,
                            "degree": degree,
                            "match_score": match_score,
                            "match_reasons": match_reasons,
                            "signals": conn_signals,
                            "is_chat": conn.get("is_chat", False),
                            "mutuals_count": conn.get("mutuals", 0)
                        }
                        
                        if degree == 1:
                            first_degree_matches.append(match_data)
                        elif degree == 2:
                            second_degree_matches.append(match_data)
            
            first_degree_matches.sort(key=lambda x: x["match_score"], reverse=True)
            second_degree_matches.sort(key=lambda x: x["match_score"], reverse=True)
            
            logger.info(f"Network search for user {user_id}: "
                       f"{len(first_degree_matches)} first-degree, "
                       f"{len(second_degree_matches)} second-degree matches")
            
            return first_degree_matches, second_degree_matches
            
        except Exception as e:
            logger.error(f"Error searching network: {str(e)}")
            raise
    
    async def search_network_semantic(
        self,
        user_id: str,
        query: str,
        max_degree: int = 2,
        min_match_score: float = 3.0
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Search user's network using AI semantic matching with PARALLEL processing
        
        Args:
            user_id: User ID performing search
            query: Natural language query
            max_degree: Maximum connection degree
            min_match_score: Minimum match score to include (0-10)
            
        Returns:
            Tuple of (first_degree_matches, second_degree_matches)
        """
        try:            
            connections = await self.get_user_connections(user_id, max_degree)
            
            all_conn_ids = []
            connection_map = {}

            for degree, degree_conns in connections.items():
                for conn in degree_conns:
                    conn_id = conn["connection_id"]
                    all_conn_ids.append(conn_id)
                    connection_map[conn_id] = (degree, conn)
            
            if not all_conn_ids:
                return [], []
            
            signals = await self.get_user_signals(all_conn_ids)
            
            logger.info(f"Starting parallel semantic matching for {len(all_conn_ids)} connections "
                       f"(max {settings.max_parallel_ai_requests} concurrent requests)")
            
            async def match_single_user(conn_id: str) -> Optional[Dict[str, Any]]:
                """Match a single user (to be run in parallel)"""
                try:
                    degree, conn = connection_map[conn_id]
                    conn_signals = signals.get(conn_id, {})
                    
                    match_result = await ai_service.match_user_to_query_semantic(
                        query=query,
                        user_data=conn_signals
                    )
                    
                    if match_result["is_match"] and match_result["match_score"] >= min_match_score:
                        return {
                            "user_id": conn_id,
                            "degree": degree,
                            "match_score": match_result["match_score"],
                            "match_reasons": match_result["match_reasons"],
                            "signals": conn_signals,
                            "is_chat": conn.get("is_chat", False),
                            "mutuals_count": conn.get("mutuals", 0),
                            "confidence": match_result["confidence"],
                            "relevant_details": match_result.get("relevant_details", [])
                        }
                    return None
                except Exception as e:
                    logger.error(f"Error matching user {conn_id}: {str(e)}")
                    return None
            
            semaphore = asyncio.Semaphore(settings.max_parallel_ai_requests)
            
            async def match_with_limit(conn_id: str) -> Optional[Dict[str, Any]]:
                """Match with rate limiting"""
                async with semaphore:
                    return await match_single_user(conn_id)
            
            match_tasks = [match_with_limit(conn_id) for conn_id in all_conn_ids]
            all_results = await asyncio.gather(*match_tasks, return_exceptions=True)
            
            first_degree_matches = []
            second_degree_matches = []
            
            for result in all_results:
                if result and not isinstance(result, Exception):
                    if result["degree"] == 1:
                        first_degree_matches.append(result)
                    elif result["degree"] == 2:
                        second_degree_matches.append(result)
            
            first_degree_matches.sort(key=lambda x: x["match_score"], reverse=True)
            second_degree_matches.sort(key=lambda x: x["match_score"], reverse=True)
            
            logger.info(f"Semantic search for user {user_id}: "
                       f"{len(first_degree_matches)} first-degree, "
                       f"{len(second_degree_matches)} second-degree matches "
                       f"(processed {len(all_conn_ids)} connections in parallel)")
            
            return first_degree_matches, second_degree_matches
            
        except Exception as e:
            logger.error(f"Error in semantic network search: {str(e)}")
            raise
    
    def _match_criteria(
        self,
        signals: Dict[str, Any],
        criteria: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """
        Match user signals against search criteria (LEGACY - Basic keyword matching)
        
        Args:
            signals: User signals
            criteria: Search criteria
            
        Returns:
            Tuple of (match_score, match_reasons)
        """
        score = 0.0
        reasons = []
        
        if criteria.get("location"):
            location = criteria["location"].lower()

            if signals.get("school") and location in signals["school"].lower():
                score += 2.0
                reasons.append(f"school in {criteria['location']}")

            for post in signals.get("recent_posts", []):
                if post.get("content") and location in post["content"].lower():
                    score += 1.5
                    reasons.append(f"posted about {criteria['location']}")
                    break
        
        if criteria.get("school"):
            school = criteria["school"].lower()
            if signals.get("school") and school in signals["school"].lower():
                score += 3.0
                reasons.append(f"attends {signals['school']}")
        
        if criteria.get("interests"):
            for interest in criteria["interests"]:
                interest_lower = interest.lower()

                if signals.get("keyword_summary"):
                    for keyword in signals["keyword_summary"]:
                        if interest_lower in keyword.lower():
                            score += 1.5
                            reasons.append(f"interested in {interest}")
                            break

                for post in signals.get("recent_posts", []):
                    if post.get("content") and interest_lower in post["content"].lower():
                        score += 1.0
                        reasons.append(f"posted about {interest}")
                        break
        
        if criteria.get("objects"):
            for obj in criteria["objects"]:
                obj_lower = obj.lower()
                for post in signals.get("recent_posts", []):
                    if post.get("content") and obj_lower in post["content"].lower():
                        score += 1.5
                        reasons.append(f"mentioned {obj}")
                        break
        
        if criteria.get("keywords"):
            for keyword in criteria["keywords"]:
                keyword_lower = keyword.lower()

                if signals.get("keyword_summary"):
                    for kw in signals["keyword_summary"]:
                        if keyword_lower in kw.lower():
                            score += 1.0
                            reasons.append(f"matches '{keyword}'")
                            break
        
        return score, reasons


network_service = NetworkService()

