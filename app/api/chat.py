"""
Chat API endpoints
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from app.models import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatContinueRequest
)
from app.services import face_recognition_service
from app.services import chat_service
from app.services import location_chat_service
from app.utils.logger import logger
from app.utils.rate_limiter import (
    check_user_rate_limit,
    RateLimitConfig
)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post(
    "/message", 
    response_model=ChatMessageResponse,
    tags=["Chat"],
    summary="Send Chat Message",
    description="Send a message to the Six chatbot and create a new conversation",
    responses={
        200: {
            "description": "Message processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "response": "Hey! I'm doing great, thanks for asking! How about you?",
                        "thread_id": "123e4567-e89b-12d3-a456-426614174000",
                        "requires_action": False,
                        "action_type": None,
                        "action_data": None,
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
                        "response": None,
                        "thread_id": None,
                        "requires_action": False,
                        "action_type": None,
                        "action_data": None,
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
                        "response": None,
                        "thread_id": None,
                        "requires_action": False,
                        "action_type": None,
                        "action_data": None,
                        "error": "Rate limit exceeded. Please try again later."
                    }
                }
            }
        }
    }
)
async def send_chat_message(request: ChatMessageRequest, http_request: Request):
    """
    **Send Chat Message - Create New Conversation**
    
    Sends a message to the Six chatbot and creates a new conversation thread.
    
    ### Features:
    - **🤖 Intelligent AI Response**: Context-aware conversational AI
    - **🗺️ Location Detection**: Automatically detects location-based queries
    - **📸 Image Analysis**: Analyzes images for face recognition when provided
    - **🎯 Action Detection**: Identifies when user wants to analyze posts, query network, or send ghost asks
    - **🔄 Fallback Handling**: Falls back to regular chat if location services fail
    
    ### Request Parameters:
    - **user_id** (required): UUID of the user sending the message
    - **message** (required): The user's message text
    - **post_id** (optional): UUID of a post if discussing a specific post
    - **image_url** (optional): URL of an image if asking about an image
    
    ### Response:
    - **response**: AI-generated response text
    - **thread_id**: UUID for continuing this conversation
    - **requires_action**: Whether the message requires a specific action
    - **action_type**: Type of action required (analyze_post, network_query, ghost_ask)
    - **action_data**: Additional data for the action
    
    ### Rate Limits:
    - User: 100 requests per hour
    - IP: 200 requests per hour
    
    ### Example Queries:
    - Regular chat: "Hey Six, how are you?"
    - Location query: "What are the best coffee shops near me?"
    - Image analysis: "Who is in this photo?" (with image_url)
    - Post analysis: "Analyze this post" (with post_id)
    """
    try:
        is_allowed, error_msg = check_user_rate_limit(
            request.user_id,
            "chat_message",
            RateLimitConfig.CHAT_MESSAGE_PER_USER_HOUR,
            window_minutes=60
        )
        
        if not is_allowed:
            return ChatMessageResponse(
                success=False,
                error=error_msg
            )
        
        is_allowed_minute, error_msg_minute = check_user_rate_limit(
            request.user_id,
            "chat_message_minute",
            RateLimitConfig.CHAT_MESSAGE_PER_USER_MINUTE,
            window_minutes=1
        )
        
        if not is_allowed_minute:
            return ChatMessageResponse(
                success=False,
                error=error_msg_minute
            )
        
        logger.info(f"Chat message from user {request.user_id}: {request.message[:50]}...")

        is_location_query = location_chat_service.is_location_query(request.message)
        
        if is_location_query:
            logger.info(f"🗺️  Detected location-based query: {request.message}")
            try:
                location_response = await location_chat_service.generate_location_response(
                    request.user_id, 
                    request.message
                )
                
                if location_response:
                    logger.info(f"✅ Got meaningful location response: {location_response[:100]}...")
                    return ChatMessageResponse(
                        success=True,
                        response=location_response,
                        thread_id=None,  # Location queries don't need thread continuity
                        requires_action=False,
                        action_type=None,
                        action_data=None
                    )
                else:
                    logger.info(f"⚠️  No location data available, falling back to regular chat")
                    pass
                    
            except Exception as e:
                logger.error(f"Error handling location query: {str(e)}")
                pass
        
        face_matches = []
        if request.image_url:
            logger.info(f"Processing image analysis for user {request.user_id}")
            try:
                matches = await face_recognition_service.search_faces_in_image(
                    request.image_url, 
                    request.user_id
                )
                face_matches = matches
                logger.info(f"Found {len(matches)} face matches in image")
            except Exception as e:
                logger.error(f"Error in face recognition: {str(e)}")
        
        result = await chat_service.send_message(
            user_id=request.user_id,
            message=request.message,
            post_id=request.post_id,
            image_url=request.image_url,
            face_matches=face_matches
        )
        
        requires_action = False
        action_type = None
        action_data = None
        
        message_lower = request.message.lower()
        
        if any(phrase in message_lower for phrase in ["analyze", "what's in", "tell me about this post"]):
            requires_action = True
            action_type = "analyze_post"
        elif any(phrase in message_lower for phrase in ["who do i know", "find someone", "connect me"]):
            requires_action = True
            action_type = "network_query"
        elif "ghost ask" in message_lower or "anonymous" in message_lower:
            requires_action = True
            action_type = "ghost_ask"
        
        return ChatMessageResponse(
            success=True,
            response=result["response"],
            thread_id=result["thread_id"],
            requires_action=requires_action,
            action_type=action_type,
            action_data=action_data
        )
        
    except Exception as e:
        logger.error(f"Error in send_chat_message endpoint: {str(e)}")
        return ChatMessageResponse(
            success=False,
            error=str(e)
        )


@router.post(
    "/continue", 
    response_model=ChatMessageResponse,
    tags=["Chat"],
    summary="Continue Conversation",
    description="Continue an existing conversation using the thread ID",
    responses={
        200: {
            "description": "Message processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "response": "That sounds interesting! Tell me more about it.",
                        "thread_id": "123e4567-e89b-12d3-a456-426614174000",
                        "requires_action": False,
                        "action_type": None,
                        "action_data": None,
                        "error": None
                    }
                }
            }
        },
        400: {
            "description": "Bad request - invalid input or thread not found",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "response": None,
                        "thread_id": None,
                        "requires_action": False,
                        "action_type": None,
                        "action_data": None,
                        "error": "Thread not found or invalid thread_id"
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
                        "response": None,
                        "thread_id": None,
                        "requires_action": False,
                        "action_type": None,
                        "action_data": None,
                        "error": "Rate limit exceeded. Please try again later."
                    }
                }
            }
        }
    }
)
async def continue_conversation(request: ChatContinueRequest, http_request: Request):
    """
    **Continue Conversation - Resume Existing Chat**
    
    Continues an existing conversation using the thread ID from a previous chat message.
    
    ### Features:
    - **🧵 Thread Continuity**: Maintains conversation context using thread_id
    - **🗺️ Location Detection**: Automatically detects location-based queries
    - **📸 Image Analysis**: Analyzes images for face recognition when provided
    - **🎯 Action Detection**: Identifies when user wants to analyze posts, query network, or send ghost asks
    - **🔄 Fallback Handling**: Falls back to regular chat if location services fail
    
    ### Request Parameters:
    - **user_id** (required): UUID of the user sending the message
    - **thread_id** (required): UUID of the conversation thread to continue
    - **message** (required): The user's message text
    - **post_id** (optional): UUID of a post if discussing a specific post
    - **image_url** (optional): URL of an image if asking about an image
    
    ### Response:
    - **response**: AI-generated response text with conversation context
    - **thread_id**: Same thread ID for continuing the conversation
    - **requires_action**: Whether the message requires a specific action
    - **action_type**: Type of action required (analyze_post, network_query, ghost_ask)
    - **action_data**: Additional data for the action
    
    ### Rate Limits:
    - User: 100 requests per hour
    - IP: 200 requests per hour
    
    ### Example Usage:
    Use the thread_id returned from `/api/chat/message` to continue the conversation.
    """
    try:
        is_allowed, error_msg = check_user_rate_limit(
            request.user_id,
            "chat_message",
            RateLimitConfig.CHAT_MESSAGE_PER_USER_HOUR,
            window_minutes=60
        )
        
        if not is_allowed:
            return ChatMessageResponse(
                success=False,
                error=error_msg
            )
        
        is_allowed_minute, error_msg_minute = check_user_rate_limit(
            request.user_id,
            "chat_message_minute",
            RateLimitConfig.CHAT_MESSAGE_PER_USER_MINUTE,
            window_minutes=1
        )
        
        if not is_allowed_minute:
            return ChatMessageResponse(
                success=False,
                error=error_msg_minute
            )
        
        logger.info(f"Continue conversation for user {request.user_id} in thread {request.thread_id}")
        
        is_location_query = location_chat_service.is_location_query(request.message)
        
        if is_location_query:
            logger.info(f"🗺️  Detected location-based query in continue: {request.message}")
            try:
                location_response = await location_chat_service.generate_location_response(
                    request.user_id, 
                    request.message
                )
                
                if location_response:
                    logger.info(f"✅ Got meaningful location response in continue: {location_response[:100]}...")
                    return ChatMessageResponse(
                        success=True,
                        response=location_response,
                        thread_id=request.thread_id,  # Keep thread for continuity
                        requires_action=False,
                        action_type=None,
                        action_data=None
                    )
                else:
                    logger.info(f"⚠️  No location data available in continue, falling back to regular chat")
                    pass
                    
            except Exception as e:
                logger.error(f"Error handling location query in continue: {str(e)}")
                pass
        
        face_matches = []
        if request.image_url:
            logger.info(f"Processing image analysis for user {request.user_id}")
            try:
                matches = await face_recognition_service.search_faces_in_image(
                    request.image_url, 
                    request.user_id
                )
                face_matches = matches
                logger.info(f"Found {len(matches)} face matches in image")
            except Exception as e:
                logger.error(f"Error in face recognition: {str(e)}")
        
        result = await chat_service.send_message(
            user_id=request.user_id,
            message=request.message,
            thread_id=request.thread_id,
            post_id=request.post_id,
            image_url=request.image_url,
            face_matches=face_matches
        )
        
        requires_action = False
        action_type = None
        action_data = None
        
        message_lower = request.message.lower()
        
        if any(phrase in message_lower for phrase in ["analyze", "what's in", "tell me about this post"]):
            requires_action = True
            action_type = "analyze_post"
        elif any(phrase in message_lower for phrase in ["who do i know", "find someone", "connect me"]):
            requires_action = True
            action_type = "network_query"
        elif "ghost ask" in message_lower or "anonymous" in message_lower:
            requires_action = True
            action_type = "ghost_ask"
        
        return ChatMessageResponse(
            success=True,
            response=result["response"],
            thread_id=result["thread_id"],
            requires_action=requires_action,
            action_type=action_type,
            action_data=action_data
        )
        
    except Exception as e:
        logger.error(f"Error continuing conversation: {str(e)}")
        
        if "not found" in str(e).lower() or "PGRST116" in str(e):
            return ChatMessageResponse(
                success=False,
                error="Conversation session not found. The chat may have expired or been deleted. Please start a new conversation."
            )
        
        if "database" in str(e).lower() or "connection" in str(e).lower():
            return ChatMessageResponse(
                success=False,
                error="Database connection error. Please try again in a moment."
            )
        
        return ChatMessageResponse(
            success=False,
            error="An unexpected error occurred. Please try again."
        )


@router.get("/thread/{thread_id}/history")
async def get_thread_history(thread_id: str, user_id: str):
    """
    Get conversation history for a thread
    
    - **thread_id**: OpenAI thread ID
    - **user_id**: User ID
    """
    try:
        result = await chat_service.get_session_history(thread_id, user_id)
        return result
        
    except Exception as e:
        logger.error(f"Error getting thread history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/thread/{thread_id}")
async def delete_thread(thread_id: str, user_id: str):
    """
    Delete a chat session and its OpenAI thread
    
    - **thread_id**: OpenAI thread ID
    - **user_id**: User ID
    """
    try:
        result = await chat_service.delete_session(thread_id, user_id)
        return result
        
    except Exception as e:
        logger.error(f"Error deleting thread: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

