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
from app.services import chat_service
from app.utils.logger import logger
from app.utils.rate_limiter import (
    check_user_rate_limit,
    RateLimitConfig
)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("/message", response_model=ChatMessageResponse)
async def send_chat_message(request: ChatMessageRequest, http_request: Request):
    """
    Send a message to the Six chatbot (creates new conversation)
    
    - **user_id**: User ID sending the message
    - **message**: User's message
    - **post_id**: Optional post ID if discussing a specific post
    
    Returns a best-friend style response with thread ID for future continuity.
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
        
        result = await chat_service.send_message(
            user_id=request.user_id,
            message=request.message,
            post_id=request.post_id
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


@router.post("/continue", response_model=ChatMessageResponse)
async def continue_conversation(request: ChatContinueRequest, http_request: Request):
    """
    Continue an existing conversation session
    
    - **user_id**: User ID
    - **thread_id**: Thread ID for conversation continuity
    - **message**: User's message
    - **post_id**: Optional post ID if discussing a specific post
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
        
        result = await chat_service.send_message(
            user_id=request.user_id,
            message=request.message,
            thread_id=request.thread_id,
            post_id=request.post_id
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

