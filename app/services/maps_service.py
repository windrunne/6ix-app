"""
Google Maps API Service for location detection and analysis
"""
import httpx
import json
from typing import Dict, List, Optional, Any, Tuple
from app.config import settings
from app.utils.logger import logger


class MapsService:
    """Service for Google Maps API operations"""
    
    def __init__(self):
        self.api_key = settings.google_maps_api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def reverse_geocode(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """
        Reverse geocode coordinates to get location information
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Location information or None if failed
        """
        try:
            url = f"{self.base_url}/geocode/json"
            params = {
                "latlng": f"{lat},{lng}",
                "key": self.api_key
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                
                location_info = {
                    "formatted_address": result.get("formatted_address"),
                    "place_id": result.get("place_id"),
                    "types": result.get("types", []),
                    "address_components": self._extract_address_components(result.get("address_components", [])),
                    "geometry": result.get("geometry", {})
                }
                
                logger.info(f"Reverse geocoded {lat},{lng} to {location_info['formatted_address']}")
                return location_info
            
            logger.warning(f"Reverse geocoding failed for {lat},{lng}: {data.get('status')}")
            return None
            
        except Exception as e:
            logger.error(f"Error in reverse geocoding: {str(e)}")
            return None
    
    async def geocode_address(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Geocode an address to get coordinates
        
        Args:
            address: Address string
            
        Returns:
            Location information with coordinates or None if failed
        """
        try:
            url = f"{self.base_url}/geocode/json"
            params = {
                "address": address,
                "key": self.api_key
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                
                location_info = {
                    "formatted_address": result.get("formatted_address"),
                    "place_id": result.get("place_id"),
                    "types": result.get("types", []),
                    "address_components": self._extract_address_components(result.get("address_components", [])),
                    "geometry": result.get("geometry", {}),
                    "coordinates": {
                        "lat": result["geometry"]["location"]["lat"],
                        "lng": result["geometry"]["location"]["lng"]
                    }
                }
                
                logger.info(f"Geocoded '{address}' to {location_info['coordinates']}")
                return location_info
            
            logger.warning(f"Geocoding failed for '{address}': {data.get('status')}")
            return None
            
        except Exception as e:
            logger.error(f"Error in geocoding: {str(e)}")
            return None
    
    async def find_nearby_places(
        self, 
        lat: float, 
        lng: float, 
        place_type: str = "cafe",
        radius: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Find nearby places using Google Places API
        
        Args:
            lat: Latitude
            lng: Longitude
            place_type: Type of place to search for
            radius: Search radius in meters
            
        Returns:
            List of nearby places
        """
        try:
            url = f"{self.base_url}/place/nearbysearch/json"
            params = {
                "location": f"{lat},{lng}",
                "radius": radius,
                "type": place_type,
                "key": self.api_key
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "OK":
                places = []
                for place in data.get("results", []):
                    place_info = {
                        "name": place.get("name"),
                        "place_id": place.get("place_id"),
                        "rating": place.get("rating"),
                        "price_level": place.get("price_level"),
                        "vicinity": place.get("vicinity"),
                        "types": place.get("types", []),
                        "geometry": place.get("geometry", {}),
                        "photos": place.get("photos", [])
                    }
                    places.append(place_info)
                
                logger.info(f"Found {len(places)} nearby {place_type} places")
                return places
            
            logger.warning(f"Nearby places search failed: {data.get('status')}")
            return []
            
        except Exception as e:
            logger.error(f"Error finding nearby places: {str(e)}")
            return []
    
    async def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a place
        
        Args:
            place_id: Google Places place ID
            
        Returns:
            Detailed place information or None if failed
        """
        try:
            url = f"{self.base_url}/place/details/json"
            params = {
                "place_id": place_id,
                "fields": "name,formatted_address,geometry,rating,price_level,types,photos,opening_hours,website,formatted_phone_number",
                "key": self.api_key
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "OK" and data.get("result"):
                result = data["result"]
                
                place_details = {
                    "name": result.get("name"),
                    "formatted_address": result.get("formatted_address"),
                    "rating": result.get("rating"),
                    "price_level": result.get("price_level"),
                    "types": result.get("types", []),
                    "geometry": result.get("geometry", {}),
                    "photos": result.get("photos", []),
                    "opening_hours": result.get("opening_hours", {}),
                    "website": result.get("website"),
                    "formatted_phone_number": result.get("formatted_phone_number")
                }
                
                logger.info(f"Retrieved details for place: {place_details['name']}")
                return place_details
            
            logger.warning(f"Place details failed for {place_id}: {data.get('status')}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting place details: {str(e)}")
            return None
    
    async def extract_location_from_image_metadata(
        self, 
        image_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract location from image EXIF metadata
        
        Args:
            image_url: URL of the image
            
        Returns:
            Location information if found in EXIF data
        """
        try:
            # This would require downloading the image and reading EXIF data
            # For now, we'll return None as this requires additional image processing
            # In a real implementation, you'd use a library like PIL/Pillow to read EXIF
            logger.info(f"EXIF location extraction not implemented for {image_url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting location from image metadata: {str(e)}")
            return None
    
    async def analyze_user_location_context(
        self, 
        user_id: str, 
        current_location: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze user's location context for network queries
        
        Args:
            user_id: User ID
            current_location: Current location coordinates
            
        Returns:
            Location context information
        """
        try:
            context = {
                "user_id": user_id,
                "current_location": current_location,
                "nearby_places": [],
                "location_insights": {}
            }
            
            if current_location and "lat" in current_location and "lng" in current_location:
                # Get location details
                location_info = await self.reverse_geocode(
                    current_location["lat"], 
                    current_location["lng"]
                )
                
                if location_info:
                    context["location_insights"] = location_info
                    
                    # Find nearby cafes, restaurants, etc.
                    for place_type in ["cafe", "restaurant", "store", "gym"]:
                        places = await self.find_nearby_places(
                            current_location["lat"],
                            current_location["lng"],
                            place_type,
                            radius=500  # 500m radius
                        )
                        context["nearby_places"].extend(places[:3])  # Top 3 of each type
            
            logger.info(f"Analyzed location context for user {user_id}")
            return context
            
        except Exception as e:
            logger.error(f"Error analyzing user location context: {str(e)}")
            return {"user_id": user_id, "error": str(e)}
    
    def _extract_address_components(self, components: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extract key address components from Google Maps response"""
        extracted = {}
        
        for component in components:
            types = component.get("types", [])
            long_name = component.get("long_name", "")
            
            if "locality" in types:
                extracted["city"] = long_name
            elif "administrative_area_level_1" in types:
                extracted["state"] = long_name
            elif "country" in types:
                extracted["country"] = long_name
            elif "postal_code" in types:
                extracted["postal_code"] = long_name
            elif "route" in types:
                extracted["street"] = long_name
            elif "street_number" in types:
                extracted["street_number"] = long_name
        
        return extracted
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Global instance
maps_service = MapsService()
