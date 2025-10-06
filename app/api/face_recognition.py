"""
Face Recognition API endpoints
"""
from fastapi import APIRouter, HTTPException, Request
from app.models import FaceRecognitionResponse, FaceMatch
from app.services import face_recognition_service, profile_analysis_service
from app.utils.logger import logger
from app.utils.rate_limiter import (
    check_user_rate_limit,
    check_ip_rate_limit,
    RateLimitConfig
)

router = APIRouter(prefix="/api/face-recognition", tags=["Face Recognition"])


@router.post(
    "/analyze", 
    response_model=FaceRecognitionResponse,
    tags=["Face Recognition"],
    summary="Analyze Image Faces",
    description="Analyze faces in an image and match them against the user's network using AWS Rekognition",
    responses={
        200: {
            "description": "Face analysis completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "face_count": 2,
                        "matches": [
                            {
                                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                "name": "Sarah Chen",
                                "username": "sarahchen",
                                "similarity": 95.5,
                                "confidence": 98.2,
                                "face_id": "face-123-456"
                            }
                        ],
                        "error": None
                    }
                }
            }
        },
        400: {
            "description": "Bad request - invalid parameters",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "face_count": 0,
                        "matches": [],
                        "error": "Invalid image URL or user ID"
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
                        "face_count": 0,
                        "matches": [],
                        "error": "Rate limit exceeded. Please try again later."
                    }
                }
            }
        }
    }
)
async def analyze_image_faces(image_url: str, user_id: str, http_request: Request):
    """
    **Analyze Image Faces - Face Recognition & Matching**
    
    Analyzes faces in an image and matches them against the user's network using AWS Rekognition.
    
    ### Features:
    - **🔍 Face Detection**: Detects all faces in the provided image
    - **🎯 Network Matching**: Matches detected faces against user's network connections
    - **📊 Similarity Scoring**: Provides similarity and confidence scores for each match
    - **👥 User Information**: Returns matched user details including name and username
    
    ### Query Parameters:
    - **image_url** (required): URL of the image to analyze
    - **user_id** (required): UUID of the user making the request
    
    ### Response:
    - **face_count**: Number of faces detected in the image
    - **matches**: Array of matched faces with user information and scores
    - **similarity**: Percentage similarity to the stored face (0-100)
    - **confidence**: Confidence score for the match (0-100)
    
    ### Rate Limits:
    - User: 10 requests per hour
    - IP: 20 requests per hour
    
    ### Prerequisites:
    - User's network faces must be indexed using `/index-network` endpoint
    - Image must be accessible via the provided URL
    - Image should contain clear, visible faces for best results
    """
    try:
        is_allowed, error_msg = check_user_rate_limit(
            user_id,
            "face_recognition",
            10,     
            window_minutes=60
        )
        
        if not is_allowed:
            return FaceRecognitionResponse(
                success=False,
                error=error_msg
            )
        
        client_ip = http_request.client.host if http_request.client else "unknown"
        is_allowed_ip, error_msg_ip = check_ip_rate_limit(
            client_ip,
            "face_recognition",
            20,
            window_minutes=60
        )
        
        if not is_allowed_ip:
            return FaceRecognitionResponse(
                success=False,
                error=error_msg_ip
            )
        
        logger.info(f"Analyzing faces in image for user {user_id}")
        
        # Search for faces in the image
        matches = await face_recognition_service.search_faces_in_image(image_url, user_id)
        
        # Convert to response format
        face_matches = []
        for match in matches:
            face_match = FaceMatch(
                user_id=match["user_id"],
                name=match["name"],
                username=match.get("username"),
                similarity=match["similarity"],
                confidence=match["confidence"],
                face_id=match["face_id"]
            )
            face_matches.append(face_match)
        
        return FaceRecognitionResponse(
            success=True,
            face_count=len(face_matches),
            matches=face_matches
        )
        
    except Exception as e:
        logger.error(f"Error in face recognition analysis: {str(e)}")
        return FaceRecognitionResponse(
            success=False,
            error=str(e)
        )


@router.post(
    "/index-user",
    tags=["Face Recognition"],
    summary="Index User Faces",
    description="Index all profile photos for a user in the AWS Rekognition face collection",
    responses={
        200: {
            "description": "User faces indexed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "indexed_faces": 3,
                        "total_photos": 3,
                        "errors": []
                    }
                }
            }
        },
        400: {
            "description": "Bad request - invalid user ID",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "error": "user_id is required"
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
                        "error": "Rate limit exceeded. Please try again later."
                    }
                }
            }
        }
    }
)
async def index_user_faces(request: dict, http_request: Request):
    """
    **Index User Faces - Profile Photo Indexing**
    
    Indexes all profile photos for a user in the AWS Rekognition face collection for future matching.
    
    ### Features:
    - **📸 Profile Photo Processing**: Processes all user profile photos
    - **🔍 Face Detection**: Detects and extracts face features from each photo
    - **💾 Face Storage**: Stores face data in AWS Rekognition collection
    - **⚡ Parallel Processing**: Optimized for handling multiple photos efficiently
    
    ### Request Body:
    ```json
    {
        "user_id": "string (UUID, required)"
    }
    ```
    
    ### Response:
    - **indexed_faces**: Number of faces successfully indexed
    - **total_photos**: Total number of profile photos processed
    - **errors**: Array of any errors encountered during processing
    
    ### Rate Limits:
    - User: 5 requests per hour
    
    ### Prerequisites:
    - User must have profile photos in the database
    - AWS Rekognition collection must be configured
    - User must have valid profile photo URLs
    
    ### Use Case:
    Run this endpoint for each user before they can use face recognition features.
    """
    try:
        user_id = request.get("user_id")
        if not user_id:
            return {"success": False, "error": "user_id is required"}
        
        is_allowed, error_msg = check_user_rate_limit(
            user_id,
            "face_indexing",
            5,
            window_minutes=60
        )
        
        if not is_allowed:
            return {"success": False, "error": error_msg}
        
        logger.info(f"Indexing faces for user {user_id}")
        
        result = await face_recognition_service.index_user_faces(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "indexed_faces": result["indexed_faces"],
            "total_photos": result["total_photos"],
            "errors": result["errors"]
        }
        
    except Exception as e:
        logger.error(f"Error indexing user faces: {str(e)}")
        return {"success": False, "error": str(e)}


@router.post("/index-network")
async def index_network_faces(request: dict, http_request: Request):
    """
    Index faces for all users in the requesting user's network
    
    - **user_id**: User ID requesting the indexing
    """
    try:
        user_id = request.get("user_id")
        if not user_id:
            return {"success": False, "error": "user_id is required"}
        
        is_allowed, error_msg = check_user_rate_limit(
            user_id,
            "network_face_indexing",
            2,
            window_minutes=60
        )
        
        if not is_allowed:
            return {"success": False, "error": error_msg}
        
        logger.info(f"Indexing network faces for user {user_id}")
        
        result = await face_recognition_service.index_network_faces(user_id)
        
        return {
            "success": True,
            "requesting_user": user_id,
            "total_users": result["total_users"],
            "total_faces_indexed": result["total_faces_indexed"],
            "total_errors": result["total_errors"]
        }
        
    except Exception as e:
        logger.error(f"Error indexing network faces: {str(e)}")
        return {"success": False, "error": str(e)}


@router.post("/analyze-profile")
async def analyze_user_profile(request: dict, http_request: Request):
    """
    Analyze user's profile photos for gender and race using OpenAI
    
    - **user_id**: User ID to analyze
    """
    try:
        user_id = request.get("user_id")
        if not user_id:
            return {"success": False, "error": "user_id is required"}
        
        is_allowed, error_msg = check_user_rate_limit(
            user_id,
            "profile_analysis",
            3,
            window_minutes=60
        )
        
        if not is_allowed:
            return {"success": False, "error": error_msg}
        
        logger.info(f"Analyzing profile photos for user {user_id}")
        
        result = await profile_analysis_service.analyze_user_profile_photos(user_id)
        
        if not result.get("success", False):
            return {
                "success": False,
                "user_id": user_id,
                "error": result.get("error", "Analysis failed"),
                "analyzed_photos": result.get("analyzed_photos", 0),
                "overall_gender": result.get("overall_gender", "unclear"),
                "overall_race": result.get("overall_race", "unclear"),
                "possible_races": result.get("possible_races", []),
                "overall_confidence": result.get("overall_confidence", 0.0)
            }
        
        if (result.get("overall_gender") == "unclear" and 
            result.get("overall_race") == "unclear" and 
            result.get("overall_confidence", 0) == 0.0):
            return {
                "success": False,
                "user_id": user_id,
                "error": "Analysis returned unclear results - check logs for details",
                "analyzed_photos": result.get("analyzed_photos", 0),
                "overall_gender": result.get("overall_gender", "unclear"),
                "overall_race": result.get("overall_race", "unclear"),
                "possible_races": result.get("possible_races", []),
                "overall_confidence": result.get("overall_confidence", 0.0),
                "individual_results": result.get("individual_results", [])
            }
        
        return {
            "success": True,
            "user_id": user_id,
            "analyzed_photos": result.get("analyzed_photos", 0),
            "overall_gender": result.get("overall_gender", "unclear"),
            "overall_race": result.get("overall_race", "unclear"),
            "possible_races": result.get("possible_races", []),
            "overall_confidence": result.get("overall_confidence", 0.0),
            "individual_results": result.get("individual_results", [])
        }
        
    except Exception as e:
        logger.error(f"Error analyzing user profile: {str(e)}")
        return {"success": False, "error": str(e)}


@router.get("/demographics/{user_id}")
async def get_user_demographics(user_id: str):
    """
    Get stored demographic information for a user
    
    - **user_id**: User ID to get demographics for
    """
    try:
        logger.info(f"Getting demographics for user {user_id}")
        
        demographics = await profile_analysis_service.get_user_demographics(user_id)
        
        if demographics:
            return {
                "success": True,
                "demographics": demographics
            }
        else:
            return {
                "success": False,
                "error": "No demographic data found for this user"
            }
        
    except Exception as e:
        logger.error(f"Error getting user demographics: {str(e)}")
        return {"success": False, "error": str(e)}


@router.delete("/user/{user_id}")
async def delete_user_faces(user_id: str, http_request: Request):
    """
    Delete all faces for a user from the collection
    
    - **user_id**: User ID to delete faces for
    """
    try:
        is_allowed, error_msg = check_user_rate_limit(
            user_id,
            "face_deletion",
            3,
            window_minutes=60
        )
        
        if not is_allowed:
            return {"success": False, "error": error_msg}
        
        logger.info(f"Deleting faces for user {user_id}")
        
        result = await face_recognition_service.delete_user_faces(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "deleted_faces": result["deleted_faces"],
            "total_faces_found": result["total_faces_found"]
        }
        
    except Exception as e:
        logger.error(f"Error deleting user faces: {str(e)}")
        return {"success": False, "error": str(e)}
