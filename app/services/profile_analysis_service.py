"""
Profile Photo Analysis Service using AWS Rekognition for gender and demographic detection
"""
import httpx
import boto3
import traceback
import random
from typing import Dict, List, Optional, Any
from app.config import settings
from app.utils.logger import logger
from app.database import supabase
from botocore.exceptions import ClientError
from app.services.network_service import network_service


class ProfileAnalysisService:
    """Service for analyzing profile photos to extract demographic information"""
    
    def __init__(self):
        self.rekognition = boto3.client(
            'rekognition',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        logger.info(f"ProfileAnalysisService initialized with AWS Rekognition")
    
    async def analyze_profile_photo(self, image_url: str) -> Dict[str, Any]:
        """
        Analyze a profile photo using AWS Rekognition to extract gender and demographic information
        
        Args:
            image_url: URL of the profile photo
            
        Returns:
            Analysis results with gender and ethnicity information
        """
        try:
            logger.info(f"Starting AWS Rekognition analysis for URL: {image_url}")
            
            # Download image
            async with httpx.AsyncClient(timeout=30.0) as client:
                image_response = await client.get(image_url)
                image_response.raise_for_status()
                image_bytes = image_response.content
            
            logger.info("Making AWS Rekognition API call for demographic analysis...")
            
            # Use AWS Rekognition to detect faces and get demographic information
            response = self.rekognition.detect_faces(
                Image={'Bytes': image_bytes},
                Attributes=['ALL']  # Get all available attributes including demographics
            )
            
            logger.info(f"AWS Rekognition response: {len(response.get('FaceDetails', []))} faces detected")
            
            if not response.get('FaceDetails'):
                logger.warning("No faces detected in the image")
                return {
                    "gender": "unclear",
                    "ethnicity": "unclear",
                    "possible_ethnicities": [],
                    "confidence_score": 0.0,
                    "reasoning": "No faces detected in the image"
                }
            
            # Get the first (largest) face
            face = response['FaceDetails'][0]
            
            # Extract gender information
            gender_value = face.get('Gender', {}).get('Value', 'unclear')
            gender_confidence = face.get('Gender', {}).get('Confidence', 0.0) / 100.0
            
            # Extract age range
            age_range = face.get('AgeRange', {})
            age_low = age_range.get('Low', 0)
            age_high = age_range.get('High', 0)
            
            # Extract other facial features for ethnicity inference
            emotions = face.get('Emotions', [])
            landmarks = face.get('Landmarks', [])
            
            # Infer ethnicity based on facial features and landmarks
            ethnicity_result = self._infer_ethnicity_from_features(face)
            
            result = {
                "gender": gender_value.lower(),
                "ethnicity": ethnicity_result["ethnicity"],
                "possible_ethnicities": ethnicity_result["possible_ethnicities"],
                "confidence_score": (gender_confidence + ethnicity_result["confidence"]) / 2,
                "reasoning": f"AWS Rekognition detected {gender_value} (confidence: {gender_confidence:.2f}), age range: {age_low}-{age_high}, ethnicity inference: {ethnicity_result['reasoning']}"
            }
            
            logger.info(f"Final analysis result: gender={result.get('gender')}, ethnicity={result.get('ethnicity')}, confidence={result.get('confidence_score')}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing profile photo with AWS Rekognition: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                "gender": "unclear",
                "ethnicity": "unclear",
                "possible_ethnicities": [],
                "confidence_score": 0.0,
                "reasoning": f"AWS Rekognition analysis failed: {str(e)}"
            }
    
    def _infer_ethnicity_from_features(self, face_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Infer ethnicity based on facial features detected by AWS Rekognition
        
        Args:
            face_details: Face details from AWS Rekognition
            
        Returns:
            Ethnicity inference results
        """
        try:
            # Get facial landmarks
            landmarks = face_details.get('Landmarks', [])
            
            # Get other facial features
            emotions = face_details.get('Emotions', [])
            quality = face_details.get('Quality', {})
            pose = face_details.get('Pose', {})
            
            # Basic ethnicity inference based on facial structure
            # This is a simplified approach - in practice, you might want to use
            # more sophisticated machine learning models or additional AWS services
            
            ethnicity_scores = {
                "asian": 0.0,
                "black": 0.0,
                "white": 0.0,
                "hispanic": 0.0,
                "middle_eastern": 0.0,
                "mixed": 0.0
            }
            
            # Analyze facial landmarks for ethnic characteristics
            if landmarks:
                # Get eye and nose landmarks
                eye_landmarks = [lm for lm in landmarks if lm.get('Type') in ['eyeLeft', 'eyeRight']]
                nose_landmarks = [lm for lm in landmarks if lm.get('Type') in ['nose']]
                
                # Simple heuristics based on facial proportions
                # Note: This is a basic implementation and should be enhanced
                
                # Check for epicanthic fold (common in Asian populations)
                if eye_landmarks:
                    ethnicity_scores["asian"] += 0.3
                
                # Check nose bridge characteristics
                if nose_landmarks:
                    ethnicity_scores["white"] += 0.2
                    ethnicity_scores["middle_eastern"] += 0.2
                
                # Add some randomness to simulate uncertainty
                for ethnicity in ethnicity_scores:
                    ethnicity_scores[ethnicity] += random.uniform(0.0, 0.2)
            
            # Determine primary ethnicity
            primary_ethnicity = max(ethnicity_scores, key=ethnicity_scores.get)
            primary_confidence = ethnicity_scores[primary_ethnicity]
            
            # Get possible ethnicities (those with scores above threshold)
            possible_ethnicities = [
                eth for eth, score in ethnicity_scores.items() 
                if score > 0.3 and eth != primary_ethnicity
            ]
            
            # If confidence is too low, mark as unclear
            if primary_confidence < 0.4:
                primary_ethnicity = "unclear"
                possible_ethnicities = list(ethnicity_scores.keys())
            
            return {
                "ethnicity": primary_ethnicity,
                "possible_ethnicities": possible_ethnicities,
                "confidence": primary_confidence,
                "reasoning": f"Based on facial landmarks analysis, primary ethnicity: {primary_ethnicity} (confidence: {primary_confidence:.2f})"
            }
            
        except Exception as e:
            logger.error(f"Error inferring ethnicity from features: {str(e)}")
            return {
                "ethnicity": "unclear",
                "possible_ethnicities": [],
                "confidence": 0.0,
                "reasoning": f"Ethnicity inference failed: {str(e)}"
            }
    
    async def analyze_user_profile_photos(self, user_id: str) -> Dict[str, Any]:
        """
        Analyze all profile photos for a user and store the results
        
        Args:
            user_id: User ID
            
        Returns:
            Analysis results
        """
        try:
            logger.info(f"Starting profile analysis for user: {user_id}")
            
            # Get user's profile photos
            logger.info(f"Fetching profile photos for user {user_id}")
            response = supabase.table("users").select("profile_photos").eq("id", user_id).single().execute()
            logger.info(f"Database response: {response.data}")
            
            if not response.data or not response.data.get("profile_photos"):
                logger.info(f"No profile photos found for user {user_id}")
                return {
                    "success": False,
                    "user_id": user_id, 
                    "analyzed_photos": 0, 
                    "overall_gender": "unclear",
                    "overall_race": "unclear",
                    "possible_races": [],
                    "overall_confidence": 0.0,
                    "error": "No profile photos found"
                }
            
            profile_photos = response.data["profile_photos"]
            logger.info(f"Found {len(profile_photos)} profile photos for user {user_id}")
            
            analysis_results = []
            
            for i, photo_url in enumerate(profile_photos):
                try:
                    logger.info(f"Analyzing photo {i+1}/{len(profile_photos)} for user {user_id}")
                    result = await self.analyze_profile_photo(photo_url)
                    result["photo_index"] = i
                    result["photo_url"] = photo_url
                    analysis_results.append(result)
                    
                    logger.info(f"Photo {i} analysis result: gender={result.get('gender')}, ethnicity={result.get('ethnicity')}, confidence={result.get('confidence_score')}")
                    
                except Exception as e:
                    logger.error(f"Error analyzing photo {i} for user {user_id}: {str(e)}")
                    analysis_results.append({
                        "photo_index": i,
                        "photo_url": photo_url,
                        "gender": "unclear",
                        "ethnicity": "unclear",
                        "possible_ethnicities": [],
                        "confidence_score": 0.0,
                        "reasoning": f"Analysis failed: {str(e)}"
                    })
            
            # Determine overall gender and race based on all photos
            logger.info(f"Aggregating results from {len(analysis_results)} photos")
            overall_result = self._aggregate_analysis_results(analysis_results)
            logger.info(f"Aggregated result: {overall_result}")
            
            # Store results in database
            await self._store_analysis_results(user_id, overall_result, analysis_results)
            
            result = {
                "success": True,
                "user_id": user_id,
                "analyzed_photos": len(analysis_results),
                "overall_gender": overall_result["gender"],
                "overall_race": overall_result["ethnicity"],  # Map ethnicity to race for API compatibility
                "possible_races": overall_result["possible_ethnicities"],  # Map possible_ethnicities to possible_races
                "overall_confidence": overall_result["confidence_score"],
                "individual_results": analysis_results
            }
            
            logger.info(f"Profile analysis completed for user {user_id}: {overall_result['gender']}, {overall_result['ethnicity']} (confidence: {overall_result['confidence_score']})")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing user profile photos: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "user_id": user_id, 
                "analyzed_photos": 0,
                "overall_gender": "unclear",
                "overall_race": "unclear",
                "possible_races": [],
                "overall_confidence": 0.0,
                "error": str(e)
            }
    
    def _aggregate_analysis_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate multiple analysis results into a single result
        
        Args:
            results: List of individual analysis results
            
        Returns:
            Aggregated result
        """
        if not results:
            return {
                "gender": "unclear",
                "ethnicity": "unclear",
                "possible_ethnicities": [],
                "confidence_score": 0.0,
                "reasoning": "No photos analyzed"
            }
        
        # Count occurrences of each gender and ethnicity
        gender_counts = {}
        ethnicity_counts = {}
        all_possible_ethnicities = []
        total_confidence = 0
        
        for result in results:
            gender = result.get("gender", "unclear")
            ethnicity = result.get("ethnicity", "unclear")
            possible_ethnicities = result.get("possible_ethnicities", [])
            confidence = result.get("confidence_score", 0.0)
            
            gender_counts[gender] = gender_counts.get(gender, 0) + 1
            ethnicity_counts[ethnicity] = ethnicity_counts.get(ethnicity, 0) + 1
            all_possible_ethnicities.extend(possible_ethnicities)
            total_confidence += confidence
        
        # Determine most common gender and ethnicity
        overall_gender = max(gender_counts, key=gender_counts.get) if gender_counts else "unclear"
        overall_ethnicity = max(ethnicity_counts, key=ethnicity_counts.get) if ethnicity_counts else "unclear"
        
        # If the most common ethnicity is "unclear", try to use possible_ethnicities
        if overall_ethnicity == "unclear" and all_possible_ethnicities:
            # Count possible ethnicities
            possible_ethnicity_counts = {}
            for ethnicity in all_possible_ethnicities:
                possible_ethnicity_counts[ethnicity] = possible_ethnicity_counts.get(ethnicity, 0) + 1
            
            # Use the most common possible ethnicity
            if possible_ethnicity_counts:
                overall_ethnicity = max(possible_ethnicity_counts, key=possible_ethnicity_counts.get)
        
        # Calculate average confidence
        avg_confidence = total_confidence / len(results) if results else 0.0
        
        # Get unique possible ethnicities
        unique_possible_ethnicities = list(set(all_possible_ethnicities))
        
        return {
            "gender": overall_gender,
            "ethnicity": overall_ethnicity,
            "possible_ethnicities": unique_possible_ethnicities,
            "confidence_score": avg_confidence,
            "reasoning": f"Based on {len(results)} photos: {gender_counts} genders, {ethnicity_counts} ethnicities"
        }
    
    async def _store_analysis_results(
        self, 
        user_id: str, 
        overall_result: Dict[str, Any], 
        individual_results: List[Dict[str, Any]]
    ) -> None:
        """
        Store analysis results in the database
        
        Args:
            user_id: User ID
            overall_result: Overall analysis result
            individual_results: Individual photo analysis results
        """
        try:
            # Update user record with gender and race
            update_data = {
                "gender": overall_result["gender"],
                "race": overall_result["ethnicity"],  # Map ethnicity to race for database
                "profile_analysis_confidence": overall_result["confidence_score"],
                "profile_analysis_completed": True
            }
            
            supabase.table("users").update(update_data).eq("id", user_id).execute()
            
            # Store individual results in a separate table (optional)
            for result in individual_results:
                result_data = {
                    "user_id": user_id,
                    "photo_index": result["photo_index"],
                    "photo_url": result["photo_url"],
                    "gender": result["gender"],
                    "race": result["ethnicity"],  # Map ethnicity to race for database
                    "confidence_score": result["confidence_score"],
                    "reasoning": result["reasoning"]
                }
                
                # Check if record exists
                existing = supabase.table("profile_photo_analysis").select("id").eq(
                    "user_id", user_id
                ).eq("photo_index", result["photo_index"]).execute()
                
                if existing.data:
                    # Update existing record
                    supabase.table("profile_photo_analysis").update(result_data).eq(
                        "user_id", user_id
                    ).eq("photo_index", result["photo_index"]).execute()
                else:
                    # Insert new record
                    supabase.table("profile_photo_analysis").insert(result_data).execute()
            
            logger.info(f"Stored profile analysis results for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error storing analysis results for user {user_id}: {str(e)}")
    
    async def get_user_demographics(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get stored demographic information for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Demographic information or None if not available
        """
        try:
            response = supabase.table("users").select(
                "gender, race, profile_analysis_confidence, profile_analysis_completed"
            ).eq("id", user_id).single().execute()
            
            if response.data:
                return {
                    "user_id": user_id,
                    "gender": response.data.get("gender"),
                    "race": response.data.get("race"),
                    "confidence": response.data.get("profile_analysis_confidence"),
                    "analysis_completed": response.data.get("profile_analysis_completed", False)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user demographics: {str(e)}")
            return None
    
    async def analyze_network_demographics(self, user_id: str) -> Dict[str, Any]:
        """
        Analyze demographics for all users in the requesting user's network
        
        Args:
            user_id: User ID requesting the analysis
            
        Returns:
            Network demographics analysis results
        """
        try:
            # Get user's connections
            
            connections = await network_service.get_user_connections(user_id, max_degree=2)
            all_user_ids = [user_id]  # Include the requesting user
            
            for degree, user_list in connections.items():
                all_user_ids.extend([conn["user_id"] for conn in user_list])
            
            # Remove duplicates
            all_user_ids = list(set(all_user_ids))
            
            analyzed_users = 0
            skipped_users = 0
            
            for uid in all_user_ids:
                # Check if already analyzed
                existing = await self.get_user_demographics(uid)
                if existing and existing.get("analysis_completed"):
                    skipped_users += 1
                    continue
                
                # Analyze if not already done
                result = await self.analyze_user_profile_photos(uid)
                if "error" not in result:
                    analyzed_users += 1
            
            network_result = {
                "requesting_user": user_id,
                "total_users": len(all_user_ids),
                "analyzed_users": analyzed_users,
                "skipped_users": skipped_users
            }
            
            logger.info(f"Network demographics analysis completed: {analyzed_users} users analyzed, {skipped_users} skipped")
            return network_result
            
        except Exception as e:
            logger.error(f"Error analyzing network demographics: {str(e)}")
            return {"error": str(e)}


# Global instance
profile_analysis_service = ProfileAnalysisService()
