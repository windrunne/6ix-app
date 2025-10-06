"""
Pydantic schemas for request/response models
"""
from pydantic import BaseModel, Field, validator, constr, conint
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from app.utils.validators import (
    validate_uuid,
    validate_message,
    validate_query,
    validate_image_url,
    validate_limit,
    sanitize_text,
    ValidationLimits
)


class ConnectionDegree(int, Enum):
    """Connection degree levels"""
    SELF = 0
    FIRST = 1
    SECOND = 2
    THIRD = 3


class PostCategory(str, Enum):
    """Post categories"""
    GENERAL = "general"
    MEET = "meet"
    CHAT = "chat"
    OPPORTUNITY = "opportunity"
    HELP = "help"


class IntroRequestStatus(str, Enum):
    """Intro request status"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class GhostAskStatus(str, Enum):
    """Ghost ask status"""
    PENDING = "pending"
    SENT = "sent"
    BLOCKED = "blocked"


class PostAnalysisRequest(BaseModel):
    """Request for post analysis"""
    user_id: str = Field(..., description="User ID who owns the post")
    post_id: str = Field(..., description="Post ID to analyze")
    image_url: Optional[str] = Field(None, description="Image URL if available")
    caption: Optional[str] = Field(None, description="Post caption/content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class PostInsights(BaseModel):
    """Structured insights from post analysis"""
    location_guess: Optional[str] = Field(None, description="Enhanced location with detailed information")
    outfit_items: List[str] = Field(default_factory=list, description="Identified clothing/accessories")
    objects: List[str] = Field(default_factory=list, description="Identified objects/brands")
    vibe_descriptors: List[str] = Field(default_factory=list, description="Vibe/mood descriptors")
    colors: List[str] = Field(default_factory=list, description="Dominant colors")
    activities: List[str] = Field(default_factory=list, description="Identified activities")
    interests: List[str] = Field(default_factory=list, description="Inferred interests")
    summary: str = Field(..., description="Brief summary of the post")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Analysis confidence score")


class PostAnalysisResponse(BaseModel):
    """Response from post analysis"""
    success: bool
    post_id: str
    insights: Optional[PostInsights] = None
    error: Optional[str] = None


class NetworkQueryRequest(BaseModel):
    """Request for network query"""
    user_id: constr(min_length=36, max_length=36) = Field(..., description="User ID making the query")
    query: constr(min_length=3, max_length=200) = Field(..., description="Natural language query")
    max_results: conint(ge=1, le=50) = Field(10, description="Maximum number of results")
    include_second_degree: bool = Field(True, description="Include 2nd degree connections")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        return validate_uuid(v, "User ID")
    
    @validator('query')
    def validate_query_text(cls, v):
        return validate_query(v)


class MutualConnection(BaseModel):
    """Mutual connection info"""
    id: str
    name: str
    profile_photo: Optional[str] = None


class NetworkMatch(BaseModel):
    """A matched connection from network query"""
    user_id: str = Field(..., description="User ID of the match")
    name: str = Field(..., description="User's name")
    username: Optional[str] = None
    profile_photos: Optional[List[str]] = Field(default_factory=list)
    degree: ConnectionDegree = Field(..., description="Connection degree")
    why_match: str = Field(..., description="Explanation of why this person matched")
    mutuals: List[MutualConnection] = Field(default_factory=list, description="Mutual connections")
    mutual_count: int = Field(0, description="Number of mutual connections")
    action: Optional[str] = Field(None, description="Suggested action (e.g., 'offer_intro')")
    school: Optional[str] = None
    major: Optional[str] = None
    graduation_year: Optional[int] = None
    gender: Optional[str] = Field(None, description="User's gender")
    race: Optional[str] = Field(None, description="User's race/ethnicity")


class NetworkQueryResponse(BaseModel):
    """Response from network query"""
    success: bool
    query: str
    matches: List[NetworkMatch] = Field(default_factory=list)
    total_matches: int = 0
    has_first_degree: bool = False
    has_second_degree: bool = False
    error: Optional[str] = None


class WarmIntroRequest(BaseModel):
    """Request to initiate a warm intro"""
    requester_id: str = Field(..., description="User requesting the intro")
    target_id: str = Field(..., description="User to be introduced to")
    query_context: str = Field(..., description="Original query that led to this intro")
    why_match: str = Field(..., description="Why this person is a match")
    mutual_ids: List[str] = Field(default_factory=list, description="Mutual connection IDs")


class WarmIntroResponse(BaseModel):
    """Response from warm intro request"""
    success: bool
    intro_request_id: Optional[str] = None
    status: Optional[IntroRequestStatus] = None
    message: str
    error: Optional[str] = None


class IntroAcceptRequest(BaseModel):
    """Request to accept/decline an intro"""
    intro_request_id: str
    target_response: bool = Field(..., description="True for accept, False for decline")


class IntroAcceptResponse(BaseModel):
    """Response from intro accept/decline"""
    success: bool
    chat_id: Optional[str] = None
    intro_message: Optional[str] = None
    message: str
    error: Optional[str] = None


class ChatMessageRequest(BaseModel):
    """Request for chat message (creates new conversation)"""
    user_id: str = Field(..., description="User ID sending the message")
    message: str = Field(..., description="User's message")
    post_id: Optional[str] = Field(None, description="Post ID if discussing a specific post")
    image_url: Optional[str] = Field(None, description="Image URL if user is asking about an image")


class ChatMessageResponse(BaseModel):
    """Response from chat"""
    success: bool
    response: Optional[str] = None
    thread_id: Optional[str] = None  # Return thread ID for continuity
    requires_action: bool = False
    action_type: Optional[str] = None
    action_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ChatContinueRequest(BaseModel):
    """Request to continue an existing conversation"""
    user_id: str = Field(..., description="User ID")
    thread_id: str = Field(..., description="Thread ID for conversation continuity")
    message: str = Field(..., description="User's message")
    post_id: Optional[str] = Field(None, description="Post ID if discussing a specific post")
    image_url: Optional[str] = Field(None, description="Image URL if user is asking about an image")


class GhostAskRequest(BaseModel):
    """Request to create a ghost ask"""
    sender_id: constr(min_length=36, max_length=36) = Field(..., description="User sending the ghost ask")
    recipient_id: constr(min_length=36, max_length=36) = Field(..., description="User receiving the ghost ask")
    message: constr(min_length=1, max_length=500) = Field(..., description="Anonymous message to send")
    
    @validator('sender_id')
    def validate_sender_id(cls, v):
        return validate_uuid(v, "Sender ID")
    
    @validator('recipient_id')
    def validate_recipient_id(cls, v):
        return validate_uuid(v, "Recipient ID")
    
    @validator('message')
    def validate_message_text(cls, v):
        return validate_message(v, max_length=500)


class GhostAskResponse(BaseModel):
    """Response from ghost ask creation"""
    success: bool
    ghost_ask_id: Optional[str] = None
    status: Optional[GhostAskStatus] = None
    message: str
    unlock_required: bool = False
    time_remaining_seconds: Optional[int] = None
    persuasion_message: Optional[str] = None
    attempts: Optional[int] = None
    can_force_send: Optional[bool] = None
    error: Optional[str] = None


class GhostAskSendRequest(BaseModel):
    """Request to force send a ghost ask after persuasion"""
    ghost_ask_id: str
    sender_id: str
    force_send: bool = Field(False, description="Force send after persuasion")


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: datetime


class FaceMatch(BaseModel):
    """Face match result from image analysis"""
    user_id: str = Field(..., description="User ID of the matched person")
    name: str = Field(..., description="Name of the matched person")
    username: Optional[str] = Field(None, description="Username of the matched person")
    similarity: float = Field(..., ge=0.0, le=100.0, description="Similarity percentage")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Confidence score")
    face_id: str = Field(..., description="Internal face ID")


class FaceRecognitionResponse(BaseModel):
    """Response from face recognition analysis"""
    success: bool
    face_count: int = Field(0, description="Number of faces detected")
    matches: List[FaceMatch] = Field(default_factory=list, description="Matched faces")
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None

