# Six Chatbot API Documentation

## Overview

The Six Chatbot API provides intelligent social networking features including AI-powered chat, face recognition, location services, network queries, and post analysis. This document provides comprehensive documentation for all API endpoints.

## Base URL
```
http://localhost:8000
```

## Authentication
All endpoints require proper user identification via `user_id` parameter.

## Rate Limiting
- User-based rate limiting: Per user per endpoint
- IP-based rate limiting: Per IP address per endpoint
- Rate limits vary by endpoint complexity and resource usage

---

## 1. Chat API

### 1.1 Send Chat Message
**POST** `/api/chat/message`

Creates a new conversation with the Six chatbot. Supports location-based queries and image analysis.

#### Request Body
```json
{
  "user_id": "string (UUID, required)",
  "message": "string (required)",
  "post_id": "string (UUID, optional)",
  "image_url": "string (optional)"
}
```

#### Response
```json
{
  "success": true,
  "response": "string",
  "thread_id": "string (UUID)",
  "requires_action": false,
  "action_type": "string (optional)",
  "action_data": "object (optional)",
  "error": "string (optional)"
}
```

#### Features
- **Location Detection**: Automatically detects location-based queries (e.g., "best coffee near me")
- **Image Analysis**: Analyzes images for face recognition when `image_url` is provided
- **Action Detection**: Identifies when user wants to analyze posts, query network, or send ghost asks
- **Fallback Handling**: Falls back to regular chat if location services fail

#### Example Requests
```bash
# Regular chat
curl -X POST "http://localhost:8000/api/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "message": "Hey Six, how are you?"
  }'

# Location-based query
curl -X POST "http://localhost:8000/api/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "message": "What are the best coffee shops near me?"
  }'

# Image analysis
curl -X POST "http://localhost:8000/api/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "message": "Who is in this photo?",
    "image_url": "https://example.com/photo.jpg"
  }'
```

### 1.2 Continue Conversation
**POST** `/api/chat/continue`

Continues an existing conversation using the thread ID.

#### Request Body
```json
{
  "user_id": "string (UUID, required)",
  "thread_id": "string (UUID, required)",
  "message": "string (required)",
  "post_id": "string (UUID, optional)",
  "image_url": "string (optional)"
}
```

#### Response
```json
{
  "success": true,
  "response": "string",
  "thread_id": "string (UUID)",
  "requires_action": false,
  "action_type": "string (optional)",
  "action_data": "object (optional)",
  "error": "string (optional)"
}
```

---

## 2. Face Recognition API

### 2.1 Analyze Image Faces
**POST** `/api/face-recognition/analyze`

Analyzes faces in an image and matches them against the user's network.

#### Query Parameters
- `image_url`: URL of the image to analyze
- `user_id`: User ID making the request

#### Response
```json
{
  "success": true,
  "face_count": 2,
  "matches": [
    {
      "user_id": "string (UUID)",
      "name": "string",
      "username": "string (optional)",
      "similarity": 95.5,
      "confidence": 98.2,
      "face_id": "string"
    }
  ],
  "error": "string (optional)"
}
```

#### Rate Limits
- User: 10 requests per hour
- IP: 20 requests per hour

### 2.2 Index User Faces
**POST** `/api/face-recognition/index-user`

Indexes all profile photos for a user in the face collection.

#### Request Body
```json
{
  "user_id": "string (UUID, required)"
}
```

#### Response
```json
{
  "success": true,
  "user_id": "string (UUID)",
  "indexed_faces": 3,
  "total_photos": 3,
  "errors": []
}
```

#### Rate Limits
- User: 5 requests per hour

### 2.3 Index Network Faces
**POST** `/api/face-recognition/index-network`

Indexes faces for all users in the requesting user's network (parallelized for performance).

#### Request Body
```json
{
  "user_id": "string (UUID, required)"
}
```

#### Response
```json
{
  "success": true,
  "requesting_user": "string (UUID)",
  "total_users": 15,
  "total_faces_indexed": 45,
  "total_errors": 0
}
```

#### Rate Limits
- User: 2 requests per hour

### 2.4 Analyze User Profile
**POST** `/api/face-recognition/analyze-profile`

Analyzes user's profile photos for gender and race using AWS Rekognition.

#### Request Body
```json
{
  "user_id": "string (UUID, required)"
}
```

#### Response
```json
{
  "success": true,
  "user_id": "string (UUID)",
  "analyzed_photos": 2,
  "overall_gender": "female",
  "overall_race": "asian",
  "overall_confidence": 0.85,
  "individual_results": [
    {
      "gender": "female",
      "race": "asian",
      "confidence_score": 0.85,
      "reasoning": "Analysis based on facial features",
      "photo_index": 0,
      "photo_url": "string"
    }
  ]
}
```

#### Rate Limits
- User: 3 requests per hour

### 2.5 Get User Demographics
**GET** `/api/face-recognition/demographics/{user_id}`

Retrieves stored demographic information for a user.

#### Response
```json
{
  "success": true,
  "demographics": {
    "gender": "female",
    "race": "asian",
    "confidence": 0.85,
    "analyzed_at": "2024-01-15T10:30:00Z"
  }
}
```

### 2.6 Delete User Faces
**DELETE** `/api/face-recognition/user/{user_id}`

Deletes all faces for a user from the collection.

#### Response
```json
{
  "success": true,
  "user_id": "string (UUID)",
  "deleted_faces": 3,
  "total_faces_found": 3
}
```

#### Rate Limits
- User: 3 requests per hour

---

## 3. Location Services API

### 3.1 Query Location
**POST** `/api/location/query`

Processes location-based queries like "best coffee near me" or "who in my network is near me".

#### Request Body
```json
{
  "user_id": "string (required)",
  "query": "string (required)",
  "current_location": {
    "lat": 37.7749,
    "lng": -122.4194
  },
  "max_results": 10
}
```

#### Response
```json
{
  "success": true,
  "query": "best coffee near me",
  "current_location": {
    "address": "San Francisco, CA, USA",
    "coordinates": {
      "lat": 37.7749,
      "lng": -122.4194
    }
  },
  "nearby_places": [
    {
      "name": "Blue Bottle Coffee",
      "place_id": "ChIJ...",
      "rating": 4.5,
      "price_level": 2,
      "vicinity": "66 Mint St, San Francisco",
      "types": ["cafe", "food", "point_of_interest"],
      "coordinates": {
        "lat": 37.7749,
        "lng": -122.4194
      }
    }
  ],
  "location_insights": {
    "neighborhood": "Financial District",
    "city": "San Francisco",
    "state": "California"
  }
}
```

#### Rate Limits
- User: 20 requests per hour
- IP: 50 requests per hour

### 3.2 Geocode Address
**POST** `/api/location/geocode`

Converts an address to coordinates.

#### Query Parameters
- `address`: Address string to geocode

#### Response
```json
{
  "success": true,
  "address": "1600 Amphitheatre Parkway, Mountain View, CA",
  "location": {
    "formatted_address": "1600 Amphitheatre Pkwy, Mountain View, CA 94043, USA",
    "coordinates": {
      "lat": 37.4220656,
      "lng": -122.0840897
    },
    "place_id": "ChIJ...",
    "types": ["street_address"]
  }
}
```

#### Rate Limits
- IP: 30 requests per hour

### 3.3 Reverse Geocode
**POST** `/api/location/reverse-geocode`

Converts coordinates to an address.

#### Query Parameters
- `lat`: Latitude
- `lng`: Longitude

#### Response
```json
{
  "success": true,
  "coordinates": {
    "lat": 37.7749,
    "lng": -122.4194
  },
  "location": {
    "formatted_address": "San Francisco, CA, USA",
    "place_id": "ChIJ...",
    "types": ["locality", "political"]
  }
}
```

#### Rate Limits
- IP: 30 requests per hour

### 3.4 Get Place Details
**GET** `/api/location/place/{place_id}`

Gets detailed information about a place.

#### Response
```json
{
  "success": true,
  "place_id": "ChIJ...",
  "details": {
    "name": "Blue Bottle Coffee",
    "formatted_address": "66 Mint St, San Francisco, CA 94103, USA",
    "rating": 4.5,
    "price_level": 2,
    "phone_number": "+1 415-543-5133",
    "website": "https://bluebottlecoffee.com",
    "opening_hours": {
      "open_now": true,
      "weekday_text": ["Monday: 7:00 AM – 6:00 PM", ...]
    }
  }
}
```

#### Rate Limits
- IP: 20 requests per hour

---

## 4. Network Query API

### 4.1 Query Network
**POST** `/api/network/query`

Queries user's network with natural language using AI semantic matching.

#### Request Body
```json
{
  "user_id": "string (UUID, required)",
  "query": "string (3-200 chars, required)",
  "max_results": 10,
  "include_second_degree": true
}
```

#### Response
```json
{
  "success": true,
  "query": "who is a asian girl i know",
  "matches": [
    {
      "user_id": "string (UUID)",
      "name": "Sarah Chen",
      "username": "sarahchen",
      "profile_photos": ["https://..."],
      "degree": 1,
      "why_match": "Sarah is Asian and female, matching your query criteria",
      "mutuals": [
        {
          "id": "string (UUID)",
          "name": "John Doe",
          "profile_photo": "https://..."
        }
      ],
      "mutual_count": 3,
      "action": "offer_intro",
      "school": "Stanford University",
      "major": "Computer Science",
      "graduation_year": 2023,
      "gender": "female",
      "race": "asian"
    }
  ],
  "total_matches": 1,
  "has_first_degree": true,
  "has_second_degree": false,
  "error": "string (optional)"
}
```

#### Features
- **AI Semantic Matching**: Uses OpenAI to understand natural language queries
- **Demographic Filtering**: Supports gender and race-based queries
- **Connection Degrees**: Searches 1st and 2nd degree connections
- **Warm Intro Support**: Offers introduction options for 2nd degree matches

#### Rate Limits
- User: 30 requests per hour
- IP: 100 requests per hour

---

## 5. Post Analysis API

### 5.1 Analyze Post
**POST** `/api/post-analysis/analyze`

Analyzes a post image and extracts insights including enhanced location information.

#### Request Body
```json
{
  "user_id": "string (UUID, required)",
  "post_id": "string (UUID, required)",
  "image_url": "string (optional)",
  "caption": "string (optional)",
  "metadata": {}
}
```

#### Response
```json
{
  "success": true,
  "post_id": "string (UUID)",
  "insights": {
    "location_guess": "Blue Bottle Coffee, 66 Mint St, San Francisco, CA 94103, USA - Popular specialty coffee shop in Financial District",
    "outfit_items": ["black jacket", "white shirt"],
    "objects": ["MacBook Air", "coffee cup", "Google Meet interface"],
    "vibe_descriptors": ["cozy", "productive"],
    "colors": ["grey", "black", "blue"],
    "activities": ["video call", "coding", "having coffee"],
    "interests": ["technology", "coffee", "remote work"],
    "summary": "A person is working on a MacBook Air while having a coffee and participating in a video call at Blue Bottle Coffee in San Francisco.",
    "confidence_score": 0.9
  },
  "error": "string (optional)"
}
```

#### Features
- **Enhanced Location**: Uses Google Maps API for detailed location information
- **Object Detection**: Identifies objects, clothing, and activities
- **Vibe Analysis**: Analyzes mood and atmosphere
- **Interest Inference**: Infers user interests from post content

### 5.2 Get Post Analysis
**GET** `/api/post-analysis/post/{post_id}`

Retrieves cached analysis for a specific post.

#### Response
```json
{
  "success": true,
  "post_id": "string (UUID)",
  "insights": {
    "location_guess": "Blue Bottle Coffee, San Francisco",
    "outfit_items": ["jacket"],
    "objects": ["MacBook Air"],
    "vibe_descriptors": ["productive"],
    "colors": ["gray", "black"],
    "activities": ["video call"],
    "interests": ["technology"],
    "summary": "Working at a coffee shop",
    "confidence_score": 0.85
  },
  "analyzed_at": "2024-01-15T10:30:00Z"
}
```

---

## 6. Warm Intro API

### 6.1 Request Warm Intro
**POST** `/api/intro/request`

Requests a warm introduction to a 2nd degree connection.

#### Request Body
```json
{
  "requester_id": "string (UUID, required)",
  "target_id": "string (UUID, required)",
  "query_context": "string (required)",
  "why_match": "string (required)",
  "mutual_ids": ["string (UUID)"]
}
```

#### Response
```json
{
  "success": true,
  "intro_request_id": "string (UUID)",
  "status": "pending",
  "message": "Intro request sent successfully",
  "error": "string (optional)"
}
```

### 6.2 Accept/Decline Intro
**POST** `/api/intro/accept`

Accepts or declines an intro request.

#### Request Body
```json
{
  "intro_request_id": "string (UUID, required)",
  "target_response": true
}
```

#### Response
```json
{
  "success": true,
  "chat_id": "string (UUID, optional)",
  "intro_message": "string (optional)",
  "message": "Intro accepted successfully",
  "error": "string (optional)"
}
```

---

## 7. Ghost Ask API

### 7.1 Create Ghost Ask
**POST** `/api/ghost-ask/create`

Creates an anonymous message to send to another user.

#### Request Body
```json
{
  "sender_id": "string (UUID, required)",
  "recipient_id": "string (UUID, required)",
  "message": "string (1-500 chars, required)"
}
```

#### Response
```json
{
  "success": true,
  "ghost_ask_id": "string (UUID)",
  "status": "pending",
  "message": "Ghost ask created successfully",
  "unlock_required": false,
  "time_remaining_seconds": null,
  "persuasion_message": null,
  "attempts": 1,
  "can_force_send": false,
  "error": "string (optional)"
}
```

### 7.2 Force Send Ghost Ask
**POST** `/api/ghost-ask/force-send`

Force sends a ghost ask after persuasion attempts.

#### Request Body
```json
{
  "ghost_ask_id": "string (UUID, required)",
  "sender_id": "string (UUID, required)",
  "force_send": true
}
```

---

## 8. Health Check

### 8.1 Health Check
**GET** `/health`

Returns the health status of the API.

#### Response
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error message",
  "detail": "Additional error details (optional)"
}
```

### Common Error Codes
- `400`: Bad Request - Invalid input parameters
- `401`: Unauthorized - Missing or invalid authentication
- `403`: Forbidden - Rate limit exceeded
- `404`: Not Found - Resource not found
- `500`: Internal Server Error - Server error

---

## Rate Limiting Details

| Endpoint Category | User Limit | IP Limit | Window |
|------------------|------------|----------|---------|
| Chat | 100/hour | 200/hour | 60 min |
| Face Recognition | 10/hour | 20/hour | 60 min |
| Face Indexing | 5/hour | 10/hour | 60 min |
| Network Face Indexing | 2/hour | 5/hour | 60 min |
| Profile Analysis | 3/hour | 10/hour | 60 min |
| Location Query | 20/hour | 50/hour | 60 min |
| Geocoding | - | 30/hour | 60 min |
| Network Query | 30/hour | 100/hour | 60 min |
| Post Analysis | 50/hour | 100/hour | 60 min |

---

## Database Schema Updates

The following columns have been added to the `users` table:
- `gender`: VARCHAR - User's gender (male, female, other, unclear)
- `race`: VARCHAR - User's race/ethnicity (asian, black, white, hispanic, other, unclear)

To apply these changes, run the SQL migration:
```sql
ALTER TABLE users ADD COLUMN gender VARCHAR(20);
ALTER TABLE users ADD COLUMN race VARCHAR(20);
```

---

## Configuration

Required environment variables:
```bash
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Google Maps
GOOGLE_MAPS_API_KEY=your_google_maps_api_key

# AWS Rekognition
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

---

## Testing

Use the provided test scripts to verify functionality:
- `test_imports.py` - Test service imports
- `test_api_fix.py` - Test API parameter fixes
- `test_network_indexing.py` - Test network indexing
- `test_profile_analysis_debug.py` - Test profile analysis
- `test_enhanced_location.py` - Test location services
- `test_location_chat.py` - Test location-based chat
- `test_coordinates_fix.py` - Test coordinates handling

---

## Support

For issues or questions, check the logs for detailed error information. All services include comprehensive logging for debugging purposes.
