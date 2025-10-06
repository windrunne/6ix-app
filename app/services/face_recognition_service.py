"""
AWS Rekognition Service for face recognition and analysis
"""
import asyncio
import boto3
import httpx
from typing import Dict, List, Optional, Any, Tuple
from app.config import settings
from app.utils.logger import logger
from app.database import supabase
from app.services.network_service import network_service


class FaceRecognitionService:
    """Service for AWS Rekognition face recognition operations"""
    
    def __init__(self):
        self.rekognition = boto3.client(
            'rekognition',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        self.collection_name = "six-app-faces"
        
        # Concurrency control for parallel processing
        self.max_concurrent_users = 5  # Max users processed in parallel
        self.max_concurrent_images = 3  # Max images per user processed in parallel
        self.batch_delay = 0.5  # Delay between batches to avoid rate limits
        
        self._ensure_collection_exists()
    
    async def _index_single_image(self, user_id: str, photo_url: str, photo_index: int) -> Dict[str, Any]:
        """
        Index a single profile photo for a user
        
        Args:
            user_id: User ID
            photo_url: URL of the profile photo
            photo_index: Index of the photo in the user's profile photos
            
        Returns:
            Result of indexing this single image
        """
        try:
            # Download image
            async with httpx.AsyncClient(timeout=30.0) as client:
                image_response = await client.get(photo_url)
                image_response.raise_for_status()
                image_bytes = image_response.content
            
            # Index face in collection
            face_id = f"{user_id}_photo_{photo_index}"
            
            self.rekognition.index_faces(
                CollectionId=self.collection_name,
                Image={'Bytes': image_bytes},
                ExternalImageId=face_id,
                MaxFaces=1,
                QualityFilter='AUTO',
                DetectionAttributes=['ALL']
            )
            
            logger.info(f"Indexed face {face_id} for user {user_id}")
            return {"success": True, "face_id": face_id, "error": None}
            
        except Exception as e:
            error_msg = f"Failed to index photo {photo_index} for user {user_id}: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "face_id": None, "error": error_msg}
    
    def _ensure_collection_exists(self):
        """Ensure the face collection exists"""
        try:
            # Try to describe the collection
            self.rekognition.describe_collection(CollectionId=self.collection_name)
            logger.info(f"Face collection '{self.collection_name}' exists")
        except self.rekognition.exceptions.ResourceNotFoundException:
            # Create the collection if it doesn't exist
            try:
                self.rekognition.create_collection(CollectionId=self.collection_name)
                logger.info(f"Created face collection '{self.collection_name}'")
            except Exception as e:
                logger.error(f"Error creating face collection: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking face collection: {str(e)}")
    
    async def index_user_faces(self, user_id: str) -> Dict[str, Any]:
        """
        Index all profile photos for a user in the face collection (parallel processing)
        
        Args:
            user_id: User ID
            
        Returns:
            Indexing results
        """
        try:
            # Get user's profile photos
            logger.info(f"Fetching profile photos for user {user_id}")
            response = supabase.table("users").select("profile_photos").eq("id", user_id).single().execute()
            logger.info(f"Database response for user {user_id}: {response.data}")
            
            if not response.data or not response.data.get("profile_photos"):
                logger.info(f"No profile photos found for user {user_id}")
                return {"user_id": user_id, "indexed_faces": 0, "errors": []}
            
            profile_photos = response.data["profile_photos"]
            logger.info(f"Found {len(profile_photos)} profile photos for user {user_id}")
            
            # Process images in parallel with concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrent_images)
            
            async def process_image_with_semaphore(photo_url: str, photo_index: int):
                async with semaphore:
                    return await self._index_single_image(user_id, photo_url, photo_index)
            
            # Create tasks for all images
            tasks = [
                process_image_with_semaphore(photo_url, i) 
                for i, photo_url in enumerate(profile_photos)
            ]
            
            # Execute all tasks in parallel
            logger.info(f"Processing {len(tasks)} images in parallel for user {user_id}")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            indexed_faces = 0
            errors = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error_msg = f"Failed to process photo {i} for user {user_id}: {str(result)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                elif result.get("success"):
                    indexed_faces += 1
                else:
                    errors.append(result.get("error", f"Unknown error for photo {i}"))
            
            result = {
                "user_id": user_id,
                "indexed_faces": indexed_faces,
                "total_photos": len(profile_photos),
                "errors": errors
            }
            
            logger.info(f"Face indexing completed for user {user_id}: {indexed_faces}/{len(profile_photos)} faces indexed")
            return result
            
        except Exception as e:
            logger.error(f"Error indexing faces for user {user_id}: {str(e)}")
            return {"user_id": user_id, "indexed_faces": 0, "errors": [str(e)]}
    
    async def search_faces_in_image(self, image_url: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Search for faces in an image against user's network
        
        Args:
            image_url: URL of the image to analyze
            user_id: User ID making the request
            
        Returns:
            List of matched faces with user information
        """
        try:
            # Download the image
            async with httpx.AsyncClient() as client:
                image_response = await client.get(image_url)
                image_response.raise_for_status()
                image_bytes = image_response.content
            
            # Search faces in the collection
            response = self.rekognition.search_faces_by_image(
                CollectionId=self.collection_name,
                Image={'Bytes': image_bytes},
                MaxFaces=10,
                FaceMatchThreshold=80.0  # 80% confidence threshold
            )
            
            matched_faces = []
            
            for match in response.get('FaceMatches', []):
                face = match['Face']
                similarity = match['Similarity']
                external_image_id = face.get('ExternalImageId', '')
                
                # Extract user ID from external image ID
                if '_photo_' in external_image_id:
                    matched_user_id = external_image_id.split('_photo_')[0]
                    
                    # Get user information
                    user_response = supabase.table("users").select(
                        "id, name, username, profile_photos"
                    ).eq("id", matched_user_id).single().execute()
                    
                    if user_response.data:
                        matched_faces.append({
                            "user_id": matched_user_id,
                            "name": user_response.data.get("name"),
                            "username": user_response.data.get("username"),
                            "similarity": similarity,
                            "face_id": external_image_id,
                            "confidence": face.get('Confidence', 0)
                        })
            
            # Sort by similarity
            matched_faces.sort(key=lambda x: x['similarity'], reverse=True)
            
            logger.info(f"Found {len(matched_faces)} face matches in image for user {user_id}")
            return matched_faces
            
        except Exception as e:
            logger.error(f"Error searching faces in image: {str(e)}")
            return []
    
    async def detect_faces_in_image(self, image_url: str) -> Dict[str, Any]:
        """
        Detect faces in an image and return face information
        
        Args:
            image_url: URL of the image
            
        Returns:
            Face detection results
        """
        try:
            # Download the image
            async with httpx.AsyncClient() as client:
                image_response = await client.get(image_url)
                image_response.raise_for_status()
                image_bytes = image_response.content
            
            # Detect faces
            response = self.rekognition.detect_faces(
                Image={'Bytes': image_bytes},
                Attributes=['ALL']
            )
            
            faces = []
            for face in response.get('FaceDetails', []):
                face_info = {
                    "confidence": face.get('Confidence', 0),
                    "bounding_box": face.get('BoundingBox', {}),
                    "age_range": face.get('AgeRange', {}),
                    "gender": face.get('Gender', {}),
                    "emotions": [emotion.get('Type') for emotion in face.get('Emotions', [])],
                    "landmarks": face.get('Landmarks', []),
                    "pose": face.get('Pose', {}),
                    "quality": face.get('Quality', {})
                }
                faces.append(face_info)
            
            result = {
                "face_count": len(faces),
                "faces": faces
            }
            
            logger.info(f"Detected {len(faces)} faces in image")
            return result
            
        except Exception as e:
            logger.error(f"Error detecting faces in image: {str(e)}")
            return {"face_count": 0, "faces": [], "error": str(e)}
    
    async def index_network_faces(self, user_id: str) -> Dict[str, Any]:
        """
        Index faces for all users in the requesting user's network (parallel processing)
        
        Args:
            user_id: User ID requesting the indexing
            
        Returns:
            Network indexing results
        """
        try:
            
            connections = await network_service.get_user_connections(user_id, max_degree=2)
            logger.info(f"Retrieved connections for user {user_id}: {connections}")
            
            all_user_ids = [user_id]  # Include the requesting user
            
            if connections:
                for degree, user_list in connections.items():
                    if isinstance(user_list, list):
                        for conn in user_list:
                            if isinstance(conn, dict):
                                # Check for both 'user_id' and 'connection_id' fields
                                if "user_id" in conn:
                                    all_user_ids.append(conn["user_id"])
                                elif "connection_id" in conn:
                                    all_user_ids.append(conn["connection_id"])
                                else:
                                    logger.warning(f"Connection missing user_id/connection_id: {conn}")
                            else:
                                logger.warning(f"Invalid connection format: {conn}")
                    else:
                        logger.warning(f"Invalid user_list format for degree {degree}: {user_list}")
            else:
                logger.warning(f"No connections found for user {user_id}")
            
            # Remove duplicates
            all_user_ids = list(set(all_user_ids))
            logger.info(f"Processing {len(all_user_ids)} unique users for face indexing")
            
            # Process users in parallel with concurrency control and batching
            total_indexed = 0
            total_errors = 0
            all_results = []
            
            # Process users in batches to avoid overwhelming AWS Rekognition
            batch_size = self.max_concurrent_users
            
            for i in range(0, len(all_user_ids), batch_size):
                batch = all_user_ids[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} users")
                
                # Create semaphore for this batch
                semaphore = asyncio.Semaphore(self.max_concurrent_users)
                
                async def process_user_with_semaphore(uid: str):
                    async with semaphore:
                        try:
                            logger.info(f"Indexing faces for user: {uid}")
                            result = await self.index_user_faces(uid)
                            logger.info(f"Result for user {uid}: {result}")
                            return result
                        except Exception as e:
                            logger.error(f"Error indexing faces for user {uid}: {str(e)}")
                            return {"user_id": uid, "indexed_faces": 0, "errors": [str(e)]}
                
                # Process batch in parallel
                batch_tasks = [process_user_with_semaphore(uid) for uid in batch]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Process batch results
                for result in batch_results:
                    if isinstance(result, Exception):
                        total_errors += 1
                        logger.error(f"Batch processing error: {str(result)}")
                    else:
                        all_results.append(result)
                        if "indexed_faces" in result:
                            total_indexed += result["indexed_faces"]
                        if "errors" in result:
                            total_errors += len(result["errors"])
                
                # Add delay between batches to avoid rate limits
                if i + batch_size < len(all_user_ids):
                    logger.info(f"Waiting {self.batch_delay}s before next batch...")
                    await asyncio.sleep(self.batch_delay)
            
            network_result = {
                "requesting_user": user_id,
                "total_users": len(all_user_ids),
                "total_faces_indexed": total_indexed,
                "total_errors": total_errors,
                "user_results": all_results
            }
            
            logger.info(f"Network face indexing completed: {total_indexed} faces indexed for {len(all_user_ids)} users")
            return network_result
            
        except Exception as e:
            logger.error(f"Error indexing network faces: {str(e)}")
            return {
                "requesting_user": user_id,
                "total_users": 0,
                "total_faces_indexed": 0,
                "total_errors": 1,
                "error": str(e)
            }
    
    async def delete_user_faces(self, user_id: str) -> Dict[str, Any]:
        """
        Delete all faces for a user from the collection
        
        Args:
            user_id: User ID
            
        Returns:
            Deletion results
        """
        try:
            # List faces for the user
            response = self.rekognition.list_faces(
                CollectionId=self.collection_name,
                MaxResults=100
            )
            
            faces_to_delete = []
            for face in response.get('Faces', []):
                external_image_id = face.get('ExternalImageId', '')
                if external_image_id.startswith(f"{user_id}_photo_"):
                    faces_to_delete.append(face['FaceId'])
            
            # Delete faces
            deleted_count = 0
            for face_id in faces_to_delete:
                try:
                    self.rekognition.delete_faces(
                        CollectionId=self.collection_name,
                        FaceIds=[face_id]
                    )
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting face {face_id}: {str(e)}")
            
            result = {
                "user_id": user_id,
                "deleted_faces": deleted_count,
                "total_faces_found": len(faces_to_delete)
            }
            
            logger.info(f"Deleted {deleted_count} faces for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error deleting faces for user {user_id}: {str(e)}")
            return {"user_id": user_id, "deleted_faces": 0, "error": str(e)}


# Global instance
face_recognition_service = FaceRecognitionService()
