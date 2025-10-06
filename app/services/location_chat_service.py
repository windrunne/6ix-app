"""
Location-based chat service for handling location queries using Google Maps API
"""
import re
from typing import Dict, List, Optional, Any, Tuple
from app.database import supabase
from app.services.maps_service import MapsService
from app.services.network_service import network_service
from app.utils.logger import logger


class LocationChatService:
    """Service for handling location-based chat queries"""
    
    def __init__(self):
        self.maps_service = MapsService()
        self.location_keywords = [
            "near me", "nearby", "close to me", "around me", "in my area",
            "local", "where is", "find", "best", "coffee", "restaurant",
            "food", "shopping", "gym", "park", "hospital", "pharmacy",
            "gas station", "atm", "bank", "hotel", "bar", "club"
        ]
        self.network_location_keywords = [
            "who in my network", "who is near me", "who is close to me",
            "who is around me", "who is in my area", "who is nearby",
            "network near me", "friends near me", "connections near me"
        ]
    
    def is_location_query(self, message: str) -> bool:
        """
        Check if the message is a location-based query
        
        Args:
            message: User's message
            
        Returns:
            True if it's a location query
        """
        message_lower = message.lower()
        
        # Check for location keywords
        for keyword in self.location_keywords:
            if keyword in message_lower:
                return True
        
        # Check for network location keywords
        for keyword in self.network_location_keywords:
            if keyword in message_lower:
                return True
        
        return False
    
    def is_network_location_query(self, message: str) -> bool:
        """
        Check if the message is asking about network users near a location
        
        Args:
            message: User's message
            
        Returns:
            True if it's a network location query
        """
        message_lower = message.lower()
        
        for keyword in self.network_location_keywords:
            if keyword in message_lower:
                return True
        
        return False
    
    async def get_user_location_from_posts(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's current location from their recent post insights
        
        Args:
            user_id: User ID
            
        Returns:
            Location information or None if not found
        """
        try:
            
            # Get recent post insights with location data
            response = supabase.table("post_insights").select(
                "location_guess, analyzed_at, post_id"
            ).eq("user_id", user_id).not_.is_("location_guess", "null").order(
                "analyzed_at", desc=True
            ).limit(5).execute()
            
            if not response.data:
                logger.info(f"No location data found in post insights for user {user_id}")
                return None
            
            # Get the most recent location
            recent_location = response.data[0]
            location_guess = recent_location.get("location_guess")
            
            if not location_guess:
                logger.info(f"No location_guess found in recent post insights")
                return None
            
            
            # Try to geocode the location to get coordinates
            try:
                geocode_result = await self.maps_service.geocode_address(location_guess)
                if geocode_result:
                    return {
                        "location_name": location_guess,
                        "coordinates": geocode_result.get("coordinates"),  # Extract just the coordinates part
                        "post_id": recent_location.get("post_id"),
                        "analyzed_at": recent_location.get("analyzed_at")
                    }
                else:
                    return {
                        "location_name": location_guess,
                        "coordinates": None,
                        "post_id": recent_location.get("post_id"),
                        "analyzed_at": recent_location.get("analyzed_at")
                    }
            except Exception as e:
                logger.error(f"Error geocoding location {location_guess}: {str(e)}")
                return {
                    "location_name": location_guess,
                    "coordinates": None,
                    "post_id": recent_location.get("post_id"),
                    "analyzed_at": recent_location.get("analyzed_at")
                }
                
        except Exception as e:
            logger.error(f"Error getting user location from posts: {str(e)}")
            return None
    
    async def find_nearby_places(self, location: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        """
        Find nearby places based on user's location and query
        
        Args:
            location: User's location information
            query: User's query (e.g., "best coffee near me")
            
        Returns:
            List of nearby places
        """
        try:
            
            if not location.get("coordinates"):
                logger.warning("No coordinates available for nearby search")
                return []
            
            lat = location["coordinates"]["lat"]
            lng = location["coordinates"]["lng"]
            
            # Extract place type from query
            place_type = self._extract_place_type(query)
            
            
            # Find nearby places
            nearby_places = await self.maps_service.find_nearby_places(
                lat=lat,
                lng=lng,
                place_type=place_type,
                radius=2000  # 2km radius
            )
            
            return nearby_places
            
        except Exception as e:
            logger.error(f"Error finding nearby places: {str(e)}")
            return []
    
    async def find_network_users_near_location(self, user_id: str, location: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find users in the network who are near the given location
        
        Args:
            user_id: User ID requesting the search
            location: Location to search around
            
        Returns:
            List of network users near the location
        """
        try:
            
            if not location.get("coordinates"):
                logger.warning("No coordinates available for network search")
                return []
            
            # Get user's connections
            connections = await network_service.get_user_connections(user_id, max_degree=2)
            
            all_conn_ids = []
            for degree_conns in connections.values():
                all_conn_ids.extend([c["connection_id"] for c in degree_conns])
            
            if not all_conn_ids:
                logger.info("No connections found for user")
                return []
            
            # Get user signals with location data
            signals = await network_service.get_user_signals(all_conn_ids)
            
            nearby_users = []
            user_lat = location["coordinates"]["lat"]
            user_lng = location["coordinates"]["lng"]
            
            for conn_user_id, user_signals in signals.items():
                # Get recent location from post insights
                conn_location = await self.get_user_location_from_posts(conn_user_id)
                
                if conn_location and conn_location.get("coordinates"):
                    conn_lat = conn_location["coordinates"]["lat"]
                    conn_lng = conn_location["coordinates"]["lng"]
                    
                    # Calculate distance (simple approximation)
                    distance = self._calculate_distance(user_lat, user_lng, conn_lat, conn_lng)
                    
                    # If within 10km, consider them nearby
                    if distance <= 10.0:
                        nearby_users.append({
                            "user_id": conn_user_id,
                            "name": user_signals.get("name", "Unknown"),
                            "username": user_signals.get("username"),
                            "location": conn_location["location_name"],
                            "distance_km": round(distance, 1),
                            "coordinates": conn_location["coordinates"]
                        })
            
            # Sort by distance
            nearby_users.sort(key=lambda x: x["distance_km"])
            
            return nearby_users[:10]  # Return top 10 closest
            
        except Exception as e:
            logger.error(f"Error finding network users near location: {str(e)}")
            return []
    
    def _extract_place_type(self, query: str) -> str:
        """
        Extract place type from user query
        
        Args:
            query: User's query
            
        Returns:
            Place type for Google Places API
        """
        query_lower = query.lower()
        
        # Map common queries to Google Places types
        place_mappings = {
            "coffee": "cafe",
            "restaurant": "restaurant",
            "food": "restaurant",
            "eat": "restaurant",
            "drink": "bar",
            "bar": "bar",
            "club": "night_club",
            "gym": "gym",
            "fitness": "gym",
            "workout": "gym",
            "park": "park",
            "hospital": "hospital",
            "doctor": "hospital",
            "pharmacy": "pharmacy",
            "drugstore": "pharmacy",
            "gas": "gas_station",
            "fuel": "gas_station",
            "atm": "atm",
            "bank": "bank",
            "hotel": "lodging",
            "shopping": "shopping_mall",
            "store": "store",
            "shop": "store"
        }
        
        for keyword, place_type in place_mappings.items():
            if keyword in query_lower:
                return place_type
        
        # Default to general establishment
        return "establishment"
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two coordinates in kilometers
        
        Args:
            lat1, lng1: First coordinate
            lat2, lng2: Second coordinate
            
        Returns:
            Distance in kilometers
        """
        import math
        
        # Haversine formula
        R = 6371  # Earth's radius in kilometers
        
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlng/2) * math.sin(dlng/2))
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        return distance
    
    async def generate_location_response(self, user_id: str, query: str) -> str:
        """
        Generate a response for location-based queries
        
        Args:
            user_id: User ID
            query: User's query
            
        Returns:
            Generated response
        """
        try:
            
            # Get user's location
            user_location = await self.get_user_location_from_posts(user_id)
            
            if not user_location:
                # Return a helpful response that doesn't start with "I don't have your current location"
                # This will trigger the fallback to regular chat
                return None
            
            if self.is_network_location_query(query):
                # Find network users near location
                nearby_users = await self.find_network_users_near_location(user_id, user_location)
                
                if not nearby_users:
                    return f"I don't see anyone from your network near {user_location['location_name']}. Try expanding your search or check back later!"
                
                response = f"Here are people from your network near {user_location['location_name']}:\n\n"
                
                for i, user in enumerate(nearby_users[:5], 1):
                    response += f"{i}. **{user['name']}** - {user['distance_km']}km away in {user['location']}\n"
                
                if len(nearby_users) > 5:
                    response += f"\n...and {len(nearby_users) - 5} more people nearby!"
                
                return response
            
            else:
                # Find nearby places
                nearby_places = await self.find_nearby_places(user_location, query)
                
                if not nearby_places:
                    return f"I couldn't find any places matching your request near {user_location['location_name']}. Try a different search term!"
                
                response = f"Here are some great places near {user_location['location_name']}:\n\n"
                
                for i, place in enumerate(nearby_places[:5], 1):
                    rating = place.get('rating', 'N/A')
                    price_level = place.get('price_level', '')
                    price_text = "💰" * price_level if price_level else ""
                    
                    response += f"{i}. **{place['name']}** {price_text}\n"
                    response += f"   📍 {place.get('vicinity', 'Address not available')}\n"
                    if rating != 'N/A':
                        response += f"   ⭐ {rating}/5.0\n"
                    response += "\n"
                
                if len(nearby_places) > 5:
                    response += f"...and {len(nearby_places) - 5} more places nearby!"
                
                return response
                
        except Exception as e:
            logger.error(f"Error generating location response: {str(e)}")
            return "Sorry, I'm having trouble finding location information right now. Please try again later!"


# Create singleton instance
location_chat_service = LocationChatService()
