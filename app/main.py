"""
FastAPI application main entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from app.config import settings
from app.api import api_router
from app.models import HealthCheckResponse

app = FastAPI(
    title="Six Chatbot API",
    description="""
    ## Six Chatbot API - Intelligent Social Networking Platform
    
    The Six Chatbot API provides advanced AI-powered features for social networking including:
    
    ### 🤖 **Chat & AI Services**
    - Intelligent conversational AI with context awareness
    - Location-based chat responses
    - Image analysis and face recognition
    - Action detection and routing
    
    ### 👥 **Face Recognition & Demographics**
    - AWS Rekognition-powered face detection and matching
    - Profile photo analysis for gender and ethnicity
    - Network-wide face indexing with parallel processing
    - Demographic data storage and retrieval
    
    ### 🗺️ **Location Services**
    - Google Maps integration for geocoding and reverse geocoding
    - Nearby places discovery
    - Location-aware chat responses
    - Place details and recommendations
    
    ### 🔍 **Network Intelligence**
    - AI-powered semantic network queries
    - Demographic filtering (gender, race, location)
    - Connection degree analysis (1st, 2nd degree)
    - Warm introduction facilitation
    
    ### 📸 **Post Analysis**
    - Advanced image analysis with OpenAI Vision
    - Object detection and activity recognition
    - Enhanced location information with Google Maps
    - Vibe and interest inference
    
    ### 👻 **Anonymous Features**
    - Ghost ask system with persuasion mechanisms
    - Anonymous messaging with unlock requirements
    - Rate limiting and abuse prevention
    
    ### 🔗 **Social Features**
    - Warm introduction requests and management
    - Connection degree tracking
    - Mutual connection analysis
    - Chat integration
    
    ## Rate Limiting
    All endpoints include comprehensive rate limiting:
    - User-based limits (per user per endpoint)
    - IP-based limits (per IP address per endpoint)
    - Configurable windows and thresholds
    
    ## Authentication
    All endpoints require proper user identification via `user_id` parameter.
    
    ## Error Handling
    Consistent error response format across all endpoints with detailed error messages.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Six Chatbot API Support",
        "email": "support@sixchatbot.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.sixchatbot.com",
            "description": "Production server"
        }
    ],
    openapi_tags=[
        {
            "name": "Chat",
            "description": "Intelligent conversational AI with location awareness and image analysis"
        },
        {
            "name": "Face Recognition",
            "description": "AWS Rekognition-powered face detection, matching, and demographic analysis"
        },
        {
            "name": "Location Services",
            "description": "Google Maps integration for geocoding, nearby places, and location-aware features"
        },
        {
            "name": "Network Query",
            "description": "AI-powered semantic network search with demographic filtering"
        },
        {
            "name": "Post Analysis",
            "description": "Advanced image analysis with object detection and enhanced location information"
        },
        {
            "name": "Warm Intro",
            "description": "Warm introduction requests and management for network connections"
        },
        {
            "name": "Ghost Ask",
            "description": "Anonymous messaging system with persuasion mechanisms"
        },
        {
            "name": "Health",
            "description": "API health and status endpoints"
        }
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8081",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get(
    "/", 
    response_model=HealthCheckResponse,
    tags=["Health"],
    summary="Root Health Check",
    description="Returns the health status of the Six Chatbot API from the root endpoint",
    responses={
        200: {
            "description": "API is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "version": "1.0.0",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def health_check():
    """
    **Root Health Check Endpoint**
    
    Returns the current health status of the Six Chatbot API.
    
    - **status**: Current API status (always "healthy" when responding)
    - **version**: API version number
    - **timestamp**: Current UTC timestamp
    
    This endpoint can be used for basic health monitoring and load balancer health checks.
    """
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow()
    )


@app.get(
    "/health", 
    response_model=HealthCheckResponse,
    tags=["Health"],
    summary="Health Check",
    description="Returns the health status of the Six Chatbot API",
    responses={
        200: {
            "description": "API is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "version": "1.0.0",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def health():
    """
    **Health Check Endpoint**
    
    Returns the current health status of the Six Chatbot API.
    
    - **status**: Current API status (always "healthy" when responding)
    - **version**: API version number  
    - **timestamp**: Current UTC timestamp
    
    This is the primary health check endpoint for monitoring and status verification.
    """
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow()
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "development"
    )

