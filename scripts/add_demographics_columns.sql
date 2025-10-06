-- Add gender and race columns to users table for profile analysis
-- Run this script to update the database schema

-- Add new columns to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS gender VARCHAR(20),
ADD COLUMN IF NOT EXISTS race VARCHAR(20),
ADD COLUMN IF NOT EXISTS profile_analysis_confidence DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS profile_analysis_completed BOOLEAN DEFAULT FALSE;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_users_gender ON users(gender);
CREATE INDEX IF NOT EXISTS idx_users_race ON users(race);
CREATE INDEX IF NOT EXISTS idx_users_analysis_completed ON users(profile_analysis_completed);

-- Create table for individual photo analysis results (optional)
CREATE TABLE IF NOT EXISTS profile_photo_analysis (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    photo_index INTEGER NOT NULL,
    photo_url TEXT NOT NULL,
    gender VARCHAR(20),
    race VARCHAR(20),
    confidence_score DECIMAL(3,2),
    reasoning TEXT,
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, photo_index)
);

-- Create indexes for profile photo analysis
CREATE INDEX IF NOT EXISTS idx_profile_photo_analysis_user_id ON profile_photo_analysis(user_id);
CREATE INDEX IF NOT EXISTS idx_profile_photo_analysis_gender ON profile_photo_analysis(gender);
CREATE INDEX IF NOT EXISTS idx_profile_photo_analysis_race ON profile_photo_analysis(race);

-- Add comments for documentation
COMMENT ON COLUMN users.gender IS 'Gender determined from profile photo analysis: male, female, non-binary, unclear';
COMMENT ON COLUMN users.race IS 'Race determined from profile photo analysis: asian, black, white, hispanic, middle_eastern, mixed, unclear';
COMMENT ON COLUMN users.profile_analysis_confidence IS 'Confidence score (0.0-1.0) for the demographic analysis';
COMMENT ON COLUMN users.profile_analysis_completed IS 'Whether profile photo analysis has been completed for this user';

COMMENT ON TABLE profile_photo_analysis IS 'Individual analysis results for each profile photo';
COMMENT ON COLUMN profile_photo_analysis.photo_index IS 'Index of the photo in the user profile_photos array';
COMMENT ON COLUMN profile_photo_analysis.confidence_score IS 'Confidence score (0.0-1.0) for this specific photo analysis';
