# Six Chatbot API

> AI-powered chatbot microservice for the Six social network

---

## 🌟 Features

### **Post Analysis**
Analyze images with GPT-4 Vision to extract location, outfit, objects, and vibes.

### **Network Queries**
AI-powered semantic search across 1st and 2nd-degree connections using natural language.

### **Warm Introductions**
Request intros to 2nd-degree connections with full lifecycle management and cooldown periods.

### **Conversational Chat**
Best-friend style AI companion with thread-based conversation memory.

### **Ghost Asks**
Anonymous prompts with gamified unlock mechanism (6-minute post window).

### **Security & Rate Limiting**
Comprehensive per-user and per-IP rate limiting with request validation.

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
cd 6ix-chatbot-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
python setup_env.py
# Or manually: cp env.example .env and edit
```

### 3. Setup Database

Run migrations in Supabase SQL Editor:
```bash
# Copy contents of scripts/create_tables.sql
# Paste into Supabase SQL Editor and execute
```

### 4. Start Server

```bash
uvicorn app.main:app --reload
```

### 5. Explore

- **Swagger UI**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---


## 🎯 API Endpoints

### Core Features

```
POST   /api/post/analyze              # Analyze post images
POST   /api/network/query              # Search network
POST   /api/intro/request              # Request warm intro
POST   /api/intro/respond              # Accept/decline intro
GET    /api/intro/my-requests/{id}    # Get user's intro requests
POST   /api/chat/message               # Start chat
POST   /api/chat/continue              # Continue chat
GET    /api/chat/thread/{id}/history  # Get chat history
POST   /api/ghost-ask/create           # Send ghost ask
GET    /health                         # Health check
```

### Interactive Documentation

- **Swagger**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

### Quick API Test

```bash
curl http://localhost:8000/health
```

---

## 📊 Rate Limits

| Feature | User Limit | IP Limit | Window |
|---------|-----------|----------|--------|
| Ghost Asks | 3 | 10 | 24h |
| Network Queries | 20 | 50 | 1h |
| Warm Intros | 5 (day), 3 (hour) | - | 24h, 1h |
| Chat | 100 (hour), 10 (min) | - | 1h, 1min |
| Post Analysis | 30 (hour), 100 (day) | 50 | 1h, 24h |

---

## 🛠️ Technology Stack

- **Framework**: FastAPI 0.104+
- **Language**: Python 3.10+
- **Database**: Supabase (PostgreSQL)
- **Graph DB**: Neo4j
- **AI**: OpenAI GPT-4o
- **Validation**: Pydantic
- **Async**: AsyncIO, HTTPX

---

## 📁 Project Structure

```
6ix-chatbot-service/
├── app/
│   ├── api/              # API endpoints
│   │   ├── post_analysis.py
│   │   ├── network_query.py
│   │   ├── warm_intro.py
│   │   ├── chat.py
│   │   └── ghost_ask.py
│   ├── services/         # Business logic
│   │   ├── ai_service.py
│   │   ├── network_service.py
│   │   ├── intro_service.py
│   │   ├── chat_service.py
│   │   └── ghost_ask_service.py
│   ├── models/           # Pydantic models
│   │   └── schemas.py
│   ├── utils/            # Utilities
│   │   ├── rate_limiter.py
│   │   ├── validators.py
│   │   └── logger.py
│   ├── config/           # Configuration
│   │   └── settings.py
│   ├── database/         # DB clients
│   │   └── supabase_client.py
│   └── main.py           # FastAPI app
├── scripts/
│   └── create_tables.sql # Database migrations
├── requirements.txt      # Dependencies
├── .env                  # Environment vars (create this)
├── env.example           # Example env vars
└── README.md            # This file
```

---

## 🔧 Configuration

### Environment Variables

```env
# Application
APP_ENV=development
PORT=8000

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-key

# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# AI Settings
USE_SEMANTIC_SEARCH=true
MAX_PARALLEL_AI_REQUESTS=10
```

See `env.example` for complete list.

---

## 🎨 Features in Detail

### Post Analysis
- **Input**: Image URL + caption + metadata
- **Output**: Location, outfit, objects, vibes
- **Cache**: Results saved for future queries
- **Model**: GPT-4o with Vision

### Network Queries
- **Natural Language**: "who likes coffee in SF?"
- **Semantic Matching**: AI understands intent
- **1st & 2nd Degree**: Searches direct and mutual connections
- **Parallel Processing**: Fast concurrent AI calls

### Warm Introductions
- **Lifecycle**: PENDING → ACCEPTED/DECLINED/EXPIRED
- **Deduplication**: Prevents duplicate requests
- **Cooldown**: 7 days (declined), 30 days (expired)
- **Auto-Chat**: Creates chat on acceptance

### Conversational Chat
- **Thread-Based**: Maintains conversation context
- **Post-Aware**: Knows about analyzed posts
- **Personality**: Lowercase, friendly, best-friend style
- **Memory**: Stores history in database

### Ghost Asks
- **Unlock**: Post within 6 minutes of challenge
- **Anonymous**: "From a friend in your network"
- **Persuasion**: AI gives in after 10+ attempts
- **Notifications**: Recipient notified

---

## 🚀 Deployment

### Local Development

```bash
uvicorn app.main:app --reload
```

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 🔒 Security

- ✅ Input validation on all fields
- ✅ Rate limiting (per-user and per-IP)
- ✅ SQL injection prevention
- ✅ XSS prevention (sanitized inputs)
- ✅ Request size limits
- ✅ Error sanitization

---

## 📈 Performance

### Optimizations
- **Caching**: Post analysis results cached
- **Parallel AI**: Concurrent OpenAI calls
- **Connection Pooling**: Database connections reused
- **Async**: Non-blocking I/O throughout

### Benchmarks (Local)
- Post Analysis: ~3-5s (first time), <100ms (cached)
- Network Query: ~5-15s (semantic search)
- Chat Response: ~1-3s
- Ghost Ask: ~2-4s

---
