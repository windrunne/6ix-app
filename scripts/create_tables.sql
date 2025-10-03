-- SQL script to create required database tables for Six Chatbot Service

-- Intro Requests Table
CREATE TABLE IF NOT EXISTS intro_requests (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  query_context TEXT,
  why_match TEXT,
  mutual_ids UUID[],
  mutual_count INTEGER DEFAULT 0,
  status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  responded_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  CONSTRAINT different_users CHECK (requester_id != target_id)
);

-- Indexes for intro_requests
CREATE INDEX IF NOT EXISTS idx_intro_requests_requester ON intro_requests(requester_id);
CREATE INDEX IF NOT EXISTS idx_intro_requests_target ON intro_requests(target_id);
CREATE INDEX IF NOT EXISTS idx_intro_requests_status ON intro_requests(status);
CREATE INDEX IF NOT EXISTS idx_intro_requests_created_at ON intro_requests(created_at DESC);

-- Ghost Asks Table
CREATE TABLE IF NOT EXISTS ghost_asks (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  recipient_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  message TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'blocked')),
  unlocked BOOLEAN DEFAULT FALSE,
  persuasion_attempts INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  sent_at TIMESTAMPTZ,
  CONSTRAINT different_users_ghost CHECK (sender_id != recipient_id)
);

-- Indexes for ghost_asks
CREATE INDEX IF NOT EXISTS idx_ghost_asks_sender ON ghost_asks(sender_id);
CREATE INDEX IF NOT EXISTS idx_ghost_asks_recipient ON ghost_asks(recipient_id);
CREATE INDEX IF NOT EXISTS idx_ghost_asks_status ON ghost_asks(status);
CREATE INDEX IF NOT EXISTS idx_ghost_asks_created_at ON ghost_asks(created_at DESC);

-- Post Insights Table (optional - for caching post analysis results)
CREATE TABLE IF NOT EXISTS post_insights (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  location_guess TEXT,
  outfit_items TEXT[],
  objects TEXT[],
  vibe_descriptors TEXT[],
  colors TEXT[],
  activities TEXT[],
  interests TEXT[],
  summary TEXT,
  confidence_score DECIMAL(3,2),
  analyzed_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT unique_post_insight UNIQUE (post_id)
);

-- Index for post_insights
CREATE INDEX IF NOT EXISTS idx_post_insights_post ON post_insights(post_id);
CREATE INDEX IF NOT EXISTS idx_post_insights_user ON post_insights(user_id);

-- Chat Sessions Table (for OpenAI thread-based conversation context)
CREATE TABLE IF NOT EXISTS chat_sessions (
  thread_id TEXT PRIMARY KEY,  -- OpenAI thread ID as primary key
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  post_id UUID REFERENCES posts(id) ON DELETE SET NULL,  -- Optional linked post
  conversation_history JSONB DEFAULT '[]'::jsonb,  -- Array of {role, content, timestamp} (user messages only, no context)
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_activity TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days'
);

-- Index for chat_sessions
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_expires ON chat_sessions(expires_at);

-- Notifications Table (for system notifications and intro requests)
CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  sender_id TEXT,  -- Can be user UUID or "system"
  type TEXT NOT NULL,  -- 'intro_request', 'mutual_intro', 'intro_declined', etc.
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  data JSONB DEFAULT '{}'::jsonb,  -- Additional data (e.g., intro_request_id)
  read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for notifications
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(user_id, read);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for chat_sessions updated_at
CREATE TRIGGER update_chat_sessions_updated_at 
  BEFORE UPDATE ON chat_sessions 
  FOR EACH ROW 
  EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE intro_requests IS 'Stores warm introduction requests between users';
COMMENT ON TABLE ghost_asks IS 'Stores anonymous ghost ask messages with unlock mechanism';
COMMENT ON TABLE post_insights IS 'Cached AI analysis results for posts';
COMMENT ON TABLE chat_sessions IS 'Maintains conversation context for chatbot interactions';
COMMENT ON TABLE notifications IS 'System notifications for intro requests, acceptances, and other events';

