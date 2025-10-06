# Six Chatbot API - Swagger/OpenAPI Documentation

## Overview

The Six Chatbot API now includes comprehensive Swagger/OpenAPI documentation with detailed endpoint descriptions, request/response examples, and interactive API exploration capabilities.

## Accessing the Documentation

### Interactive Swagger UI
- **URL**: `http://localhost:8000/docs`
- **Features**: Interactive API testing, request/response examples, schema validation

### ReDoc Documentation
- **URL**: `http://localhost:8000/redoc`
- **Features**: Clean, readable documentation with detailed schemas

## Enhanced OpenAPI Features

### 🎯 **Comprehensive API Information**
- **Title**: Six Chatbot API
- **Description**: Intelligent Social Networking Platform with detailed feature descriptions
- **Version**: 1.0.0
- **Contact**: support@sixchatbot.com
- **License**: MIT License

### 🏷️ **Organized API Tags**
All endpoints are organized into logical categories:

1. **Chat** - Intelligent conversational AI with location awareness and image analysis
2. **Face Recognition** - AWS Rekognition-powered face detection, matching, and demographic analysis
3. **Location Services** - Google Maps integration for geocoding, nearby places, and location-aware features
4. **Network Query** - AI-powered semantic network search with demographic filtering
5. **Post Analysis** - Advanced image analysis with object detection and enhanced location information
6. **Warm Intro** - Warm introduction requests and management for network connections
7. **Ghost Ask** - Anonymous messaging system with persuasion mechanisms
8. **Health** - API health and status endpoints

### 📊 **Detailed Response Examples**
Each endpoint includes comprehensive response examples for:
- **200 Success**: Detailed success responses with realistic data
- **400 Bad Request**: Error responses for invalid input
- **429 Rate Limited**: Rate limit exceeded responses

### 🔧 **Enhanced Endpoint Documentation**

#### Chat API (`/api/chat`)
- **POST /message**: Send chat message with location detection and image analysis
- **POST /continue**: Continue existing conversation with thread continuity

#### Face Recognition API (`/api/face-recognition`)
- **POST /analyze**: Analyze faces in images with network matching
- **POST /index-user**: Index user profile photos for face recognition
- **POST /index-network**: Index network faces with parallel processing
- **POST /analyze-profile**: Analyze profile photos for demographics
- **GET /demographics/{user_id}**: Get stored demographic information
- **DELETE /user/{user_id}**: Delete user faces from collection

#### Location Services API (`/api/location`)
- **POST /query**: Process location-based queries with Google Maps
- **POST /geocode**: Convert addresses to coordinates
- **POST /reverse-geocode**: Convert coordinates to addresses
- **GET /place/{place_id}**: Get detailed place information

#### Network Query API (`/api/network`)
- **POST /query**: AI-powered semantic network search with demographic filtering

#### Post Analysis API (`/api/post-analysis`)
- **POST /analyze**: Advanced image analysis with enhanced location
- **GET /post/{post_id}**: Get cached post analysis

#### Warm Intro API (`/api/intro`)
- **POST /request**: Request warm introduction to 2nd degree connections
- **POST /accept**: Accept or decline introduction requests

#### Ghost Ask API (`/api/ghost-ask`)
- **POST /create**: Create anonymous messages with persuasion system
- **POST /force-send**: Force send ghost ask after persuasion

#### Health API
- **GET /**: Root health check endpoint
- **GET /health**: Primary health check endpoint

## Key Documentation Features

### 🎨 **Rich Descriptions**
Each endpoint includes:
- **Feature highlights** with emojis for visual appeal
- **Detailed parameter descriptions** with types and requirements
- **Comprehensive examples** for different use cases
- **Rate limiting information** for each endpoint
- **Prerequisites** and setup requirements

### 📝 **Request/Response Schemas**
- **Pydantic models** with detailed field descriptions
- **Validation rules** with min/max constraints
- **Optional vs required** parameters clearly marked
- **Data type specifications** for all fields

### 🔒 **Security & Rate Limiting**
- **Rate limit documentation** for each endpoint
- **User-based limits** (per user per endpoint)
- **IP-based limits** (per IP address per endpoint)
- **Error responses** for rate limit exceeded

### 🌐 **Server Configuration**
- **Development server**: `http://localhost:8000`
- **Production server**: `https://api.sixchatbot.com`
- **CORS configuration** for cross-origin requests

## Example API Usage

### 1. Chat with Location Detection
```bash
curl -X POST "http://localhost:8000/api/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "message": "What are the best coffee shops near me?"
  }'
```

### 2. Face Recognition Analysis
```bash
curl -X POST "http://localhost:8000/api/face-recognition/analyze?image_url=https://example.com/photo.jpg&user_id=123e4567-e89b-12d3-a456-426614174000"
```

### 3. Network Query with Demographics
```bash
curl -X POST "http://localhost:8000/api/network/query" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "query": "who is a asian girl i know",
    "max_results": 10,
    "include_second_degree": true
  }'
```

### 4. Post Analysis with Enhanced Location
```bash
curl -X POST "http://localhost:8000/api/post-analysis/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "post_id": "456e7890-e89b-12d3-a456-426614174001",
    "image_url": "https://example.com/post.jpg"
  }'
```

## Interactive Testing

### Swagger UI Features
1. **Try it out**: Click "Try it out" on any endpoint
2. **Fill parameters**: Enter required parameters
3. **Execute**: Click "Execute" to test the endpoint
4. **View response**: See the actual API response
5. **Copy curl**: Get the exact curl command for testing

### Request Validation
- **Automatic validation** of request parameters
- **Schema validation** for request bodies
- **Error highlighting** for invalid inputs
- **Type checking** for all parameters

## Error Handling Documentation

### Standard Error Responses
All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error message",
  "detail": "Additional error details (optional)"
}
```

### HTTP Status Codes
- **200**: Success
- **400**: Bad Request - Invalid input
- **401**: Unauthorized - Missing authentication
- **403**: Forbidden - Rate limit exceeded
- **404**: Not Found - Resource not found
- **500**: Internal Server Error - Server error

## Configuration Requirements

### Environment Variables
Documented in the API description:
- **OpenAI API Key**: For AI-powered features
- **Google Maps API Key**: For location services
- **AWS Credentials**: For face recognition
- **Supabase Configuration**: For database access

### Database Schema
- **Users table**: Enhanced with `gender` and `race` columns
- **Migration script**: Available for database updates
- **Indexing requirements**: For optimal performance

## Development Workflow

### 1. Start the Server
```bash
cd 6ix-chatbot-service
python -m uvicorn app.main:app --reload
```

### 2. Access Documentation
- Open `http://localhost:8000/docs` for Swagger UI
- Open `http://localhost:8000/redoc` for ReDoc

### 3. Test Endpoints
- Use the interactive interface to test endpoints
- Copy curl commands for integration testing
- Validate request/response schemas

### 4. Integration
- Use the documented schemas for client integration
- Follow rate limiting guidelines
- Implement proper error handling

## Benefits of Enhanced Documentation

### 👨‍💻 **Developer Experience**
- **Self-documenting API** with interactive testing
- **Clear examples** for all use cases
- **Comprehensive error handling** documentation
- **Rate limiting transparency**

### 🔧 **Integration Support**
- **Copy-paste examples** for quick integration
- **Schema validation** for request/response handling
- **Error code documentation** for proper error handling
- **Authentication requirements** clearly specified

### 📊 **API Management**
- **Endpoint organization** by functionality
- **Rate limiting documentation** for capacity planning
- **Performance considerations** documented
- **Prerequisites** clearly specified

### 🚀 **Production Readiness**
- **Health check endpoints** for monitoring
- **Error response consistency** across all endpoints
- **Rate limiting protection** documented
- **Configuration requirements** specified

## Next Steps

1. **Deploy the enhanced API** with comprehensive documentation
2. **Share the Swagger UI** with frontend developers
3. **Use the documentation** for client SDK generation
4. **Monitor API usage** using the documented rate limits
5. **Iterate on documentation** based on developer feedback

The enhanced Swagger/OpenAPI documentation provides a complete, interactive, and developer-friendly interface for the Six Chatbot API, making it easy to understand, test, and integrate with all the advanced AI-powered features.
