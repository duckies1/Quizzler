-- Quizzler Database Schema for Supabase PostgreSQL
-- Run this in your Supabase SQL Editor

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (this might already exist from Supabase Auth)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Quizzes table
CREATE TABLE IF NOT EXISTS quizzes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_trivia BOOLEAN DEFAULT FALSE,
    topic TEXT, -- Tag/genre for trivia, null for private
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    duration INTEGER NOT NULL, -- In minutes
    positive_mark INTEGER DEFAULT 1,
    negative_mark INTEGER DEFAULT 0,
    navigation_type TEXT DEFAULT 'omni', -- 'omni' or 'restricted'
    tab_switch_exit BOOLEAN DEFAULT TRUE,
    difficulty TEXT, -- 'easy', 'medium', 'hard' for trivia
    popularity INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_trivia_title_topic UNIQUE (title, topic)
);

-- Questions table
CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK (correct_option IN ('a', 'b', 'c', 'd')),
    mark INTEGER DEFAULT 1
);

-- Quiz Sessions table
CREATE TABLE IF NOT EXISTS quiz_sessions (
    id SERIAL PRIMARY KEY,
    quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    ended BOOLEAN DEFAULT FALSE,
    CONSTRAINT unique_quiz_user_session UNIQUE (quiz_id, user_id)
);

-- Responses table
CREATE TABLE IF NOT EXISTS responses (
    id SERIAL PRIMARY KEY,
    quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    answers JSONB NOT NULL, -- {question_id: selected_option or null}
    correct_answers JSONB, -- {question_id: correct_option}
    score INTEGER,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_quiz_user_response UNIQUE (quiz_id, user_id)
);

-- Ratings table (for trivia leaderboards)
CREATE TABLE IF NOT EXISTS ratings (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL, -- Calculated based on score and time
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_quiz_user_rating UNIQUE (quiz_id, user_id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_quizzes_creator_id ON quizzes(creator_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_is_trivia ON quizzes(is_trivia);
CREATE INDEX IF NOT EXISTS idx_quizzes_topic ON quizzes(topic);
CREATE INDEX IF NOT EXISTS idx_questions_quiz_id ON questions(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_quiz_id ON quiz_sessions(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_sessions_user_id ON quiz_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_responses_quiz_id ON responses(quiz_id);
CREATE INDEX IF NOT EXISTS idx_responses_user_id ON responses(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_quiz_id ON ratings(quiz_id);
CREATE INDEX IF NOT EXISTS idx_ratings_user_id ON ratings(user_id);

-- Enable Row Level Security (RLS) for better security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE quizzes ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratings ENABLE ROW LEVEL SECURITY;

-- Create policies for Row Level Security
-- Users can only see their own data
CREATE POLICY "Users can view own profile" ON users FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON users FOR UPDATE USING (auth.uid() = id);

-- Quiz policies (creators can manage their quizzes, others can view active ones)
CREATE POLICY "Anyone can view active quizzes" ON quizzes FOR SELECT USING (is_active = true);
CREATE POLICY "Creators can manage own quizzes" ON quizzes FOR ALL USING (auth.uid() = creator_id);

-- Question policies (follow quiz permissions)
CREATE POLICY "Anyone can view questions of active quizzes" ON questions 
FOR SELECT USING (
    quiz_id IN (SELECT id FROM quizzes WHERE is_active = true)
);
CREATE POLICY "Creators can manage questions" ON questions 
FOR ALL USING (
    quiz_id IN (SELECT id FROM quizzes WHERE creator_id = auth.uid())
);

-- Quiz session policies (users can manage their own sessions)
CREATE POLICY "Users can view own sessions" ON quiz_sessions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can create own sessions" ON quiz_sessions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own sessions" ON quiz_sessions FOR UPDATE USING (auth.uid() = user_id);

-- Response policies (users can manage their own responses)
CREATE POLICY "Users can view own responses" ON responses FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can create own responses" ON responses FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Rating policies (users can manage their own ratings)
CREATE POLICY "Users can view all ratings" ON ratings FOR SELECT TO authenticated;
CREATE POLICY "Users can manage own ratings" ON ratings FOR ALL USING (auth.uid() = user_id);
