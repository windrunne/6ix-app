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
        Get user signals/attributes for matching using post insights data
        
        Args:
            user_ids: List of user IDs
            
        Returns:
            Dictionary mapping user_id to signals
        """
        try:
            users_response = supabase.table("users").select(
                "id, name, username, school, major, graduation_year, "
                "school_type, profile_photos, gender, race"
            ).in_("id", user_ids).execute()
            
            users_data = {u["id"]: u for u in users_response.data}
            
            users_with_gender = sum(1 for u in users_response.data if u.get("gender"))
            users_with_race = sum(1 for u in users_response.data if u.get("race"))
            
            
            missing_users = set(user_ids) - set(u["id"] for u in users_response.data)

            insights_response = supabase.table("post_insights").select(
                "user_id, location_guess, outfit_items, objects, vibe_descriptors, "
                "colors, activities, interests, summary, confidence_score, analyzed_at"
            ).in_("user_id", user_ids).order(
                "analyzed_at", desc=True
            ).limit(100).execute()
                        
            insights_by_user = {}
            for insight in insights_response.data:
                uid = insight["user_id"]
                if uid not in insights_by_user:
                    insights_by_user[uid] = []
                insights_by_user[uid].append(insight)
            
            posts_response = supabase.table("posts").select(
                "user_id, content, category, created_at, image_url"
            ).in_("user_id", user_ids).order(
                "created_at", desc=True
            ).limit(50).execute()
            
            posts_by_user = {}
            for post in posts_response.data:
                uid = post["user_id"]
                if uid not in posts_by_user:
                    posts_by_user[uid] = []
                posts_by_user[uid].append(post)
            
            signals = {}
            for user_id in user_ids:
                user_data = users_data.get(user_id, {})
                user_insights = insights_by_user.get(user_id, [])
                user_posts = posts_by_user.get(user_id, [])
                
                aggregated_insights = {
                    "locations": [],
                    "outfit_items": [],
                    "objects": [],
                    "vibe_descriptors": [],
                    "colors": [],
                    "activities": [],
                    "interests": [],
                    "summaries": []
                }
                
                for insight in user_insights[:10]:  # Top 10 most recent insights
                    if insight.get("location_guess"):
                        aggregated_insights["locations"].append(insight["location_guess"])
                    if insight.get("outfit_items"):
                        aggregated_insights["outfit_items"].extend(insight["outfit_items"])
                    if insight.get("objects"):
                        aggregated_insights["objects"].extend(insight["objects"])
                    if insight.get("vibe_descriptors"):
                        aggregated_insights["vibe_descriptors"].extend(insight["vibe_descriptors"])
                    if insight.get("colors"):
                        aggregated_insights["colors"].extend(insight["colors"])
                    if insight.get("activities"):
                        aggregated_insights["activities"].extend(insight["activities"])
                    if insight.get("interests"):
                        aggregated_insights["interests"].extend(insight["interests"])
                    if insight.get("summary"):
                        aggregated_insights["summaries"].append(insight["summary"])
                
                for key in aggregated_insights:
                    if isinstance(aggregated_insights[key], list):
                        aggregated_insights[key] = list(set(aggregated_insights[key]))[:20]
                
                signals[user_id] = {
                    "id": user_id,  # Add user ID for debugging
                    "name": user_data.get("name"),
                    "username": user_data.get("username"),
                    "school": user_data.get("school"),
                    "major": user_data.get("major"),
                    "graduation_year": user_data.get("graduation_year"),
                    "school_type": user_data.get("school_type"),
                    "profile_photos": user_data.get("profile_photos", []),
                    "gender": user_data.get("gender"),  # Add gender field
                    "race": user_data.get("race"),      # Add race field
                    "post_insights": {
                        "locations": aggregated_insights["locations"],
                        "outfit_items": aggregated_insights["outfit_items"],
                        "objects": aggregated_insights["objects"],
                        "vibe_descriptors": aggregated_insights["vibe_descriptors"],
                        "colors": aggregated_insights["colors"],
                        "activities": aggregated_insights["activities"],
                        "interests": aggregated_insights["interests"],
                        "summaries": aggregated_insights["summaries"]
                    },
                    # Fallback: recent posts for users without insights
                    "recent_posts": [
                        {
                            "content": p.get("content"),
                            "category": p.get("category"),
                            "created_at": p.get("created_at"),
                            "image_url": p.get("image_url")
                        }
                        for p in user_posts[:5]
                    ]
                }
              
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
                logger.warning("No connections found for user")
                return [], []
            
            signals = await self.get_user_signals(all_conn_ids)
            
            # Log users with demographic data
            users_with_demographics = []
            for user_id, user_signals in signals.items():
                if user_signals.get("gender") or user_signals.get("race"):
                    users_with_demographics.append({
                        "id": user_id,
                        "name": user_signals.get("name", "Unknown"),
                        "gender": user_signals.get("gender", "N/A"),
                        "race": user_signals.get("race", "N/A")
                    })
            
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
        Now enhanced to use post insights data
        
        Args:
            signals: User signals (now includes post_insights)
            criteria: Search criteria
            
        Returns:
            Tuple of (match_score, match_reasons)
        """
        score = 0.0
        reasons = []
        post_insights = signals.get("post_insights", {})
        
        if criteria.get("location"):
            location = criteria["location"].lower()

            if signals.get("school") and location in signals["school"].lower():
                score += 2.0
                reasons.append(f"school in {criteria['location']}")

            for insight_location in post_insights.get("locations", []):
                if location in insight_location.lower():
                    score += 2.5
                    reasons.append(f"posted from {insight_location}")
                    break

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

                for insight_interest in post_insights.get("interests", []):
                    if interest_lower in insight_interest.lower():
                        score += 2.0
                        reasons.append(f"interested in {insight_interest}")
                        break

                for activity in post_insights.get("activities", []):
                    if interest_lower in activity.lower():
                        score += 1.5
                        reasons.append(f"does {activity}")
                        break

                for post in signals.get("recent_posts", []):
                    if post.get("content") and interest_lower in post["content"].lower():
                        score += 1.0
                        reasons.append(f"posted about {interest}")
                        break
        
        if criteria.get("objects"):
            for obj in criteria["objects"]:
                obj_lower = obj.lower()
                
                for insight_obj in post_insights.get("objects", []):
                    if obj_lower in insight_obj.lower():
                        score += 2.0
                        reasons.append(f"has {insight_obj}")
                        break

                for outfit_item in post_insights.get("outfit_items", []):
                    if obj_lower in outfit_item.lower():
                        score += 1.5
                        reasons.append(f"wears {outfit_item}")
                        break

                for post in signals.get("recent_posts", []):
                    if post.get("content") and obj_lower in post["content"].lower():
                        score += 1.5
                        reasons.append(f"mentioned {obj}")
                        break
        
        if criteria.get("keywords"):
            for keyword in criteria["keywords"]:
                keyword_lower = keyword.lower()

                for vibe in post_insights.get("vibe_descriptors", []):
                    if keyword_lower in vibe.lower():
                        score += 1.5
                        reasons.append(f"has {vibe} vibe")
                        break

                for activity in post_insights.get("activities", []):
                    if keyword_lower in activity.lower():
                        score += 1.5
                        reasons.append(f"does {activity}")
                        break

                for post in signals.get("recent_posts", []):
                    if post.get("content") and keyword_lower in post["content"].lower():
                        score += 1.0
                        reasons.append(f"matches '{keyword}'")
                        break
        
        # Add demographic matching
        if criteria.get("gender"):
            gender = criteria["gender"].lower()
            if signals.get("gender") and gender in signals["gender"].lower():
                score += 2.0
                reasons.append(f"gender matches ({signals['gender']})")
        
        if criteria.get("race") or criteria.get("ethnicity"):
            race_query = (criteria.get("race") or criteria.get("ethnicity")).lower()
            user_race = signals.get("race", "").lower()
            
            if race_query in user_race:
                score += 2.5
                reasons.append(f"race matches ({signals['race']})")
        
        # Handle common demographic keywords in the query
        if criteria.get("keywords"):
            for keyword in criteria["keywords"]:
                keyword_lower = keyword.lower()
                
                # Gender keywords
                if keyword_lower in ["guy", "boy", "man", "male"] and signals.get("gender") == "male":
                    score += 2.0
                    reasons.append("gender matches (male)")
                elif keyword_lower in ["girl", "woman", "female"] and signals.get("gender") == "female":
                    score += 2.0
                    reasons.append("gender matches (female)")
                
                # Race/ethnicity keywords
                race_keywords = {
                    "asian": ["asian", "chinese", "japanese", "korean", "vietnamese", "thai", "filipino"],
                    "black": ["black", "african", "african-american"],
                    "white": ["white", "caucasian", "european"],
                    "hispanic": ["hispanic", "latino", "latina", "mexican", "spanish"],
                    "middle_eastern": ["middle eastern", "arab", "persian", "turkish"]
                }
                
                for race, keywords in race_keywords.items():
                    if keyword_lower in keywords:
                        user_race = signals.get("race", "").lower()
                        
                        if race in user_race:
                            score += 2.5
                            reasons.append(f"race matches ({race})")
                        break
        
        return score, reasons


network_service = NetworkService()

