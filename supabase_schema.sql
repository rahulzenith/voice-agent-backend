-- Supabase Database Schema for Voice Agent Appointment Booking System
-- Run this SQL in your Supabase SQL Editor

-- Drop existing tables
DROP TABLE IF EXISTS conversation_logs CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS slots CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create users table
CREATE TABLE users (
    contact_number TEXT PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create slots table
CREATE TABLE slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slot_date DATE NOT NULL,
    slot_time TIME NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    is_available BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(slot_date, slot_time)
);

-- Create appointments table
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_number TEXT REFERENCES users(contact_number) ON DELETE CASCADE,
    slot_id UUID REFERENCES slots(id) ON DELETE CASCADE,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'cancelled', 'completed')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(slot_id),
    UNIQUE(appointment_date, appointment_time)
);

-- Create conversation logs table
CREATE TABLE conversation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    contact_number TEXT REFERENCES users(contact_number) ON DELETE SET NULL,
    transcript JSONB NOT NULL DEFAULT '{}',
    summary TEXT,
    tool_calls JSONB,
    duration_seconds INTEGER,
    cost_breakdown JSONB,
    user_preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_slots_date ON slots(slot_date);
CREATE INDEX idx_slots_date_time ON slots(slot_date, slot_time);
CREATE INDEX idx_slots_available ON slots(is_available);
CREATE INDEX idx_appointments_contact ON appointments(contact_number);
CREATE INDEX idx_appointments_date ON appointments(appointment_date);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE INDEX idx_appointments_date_time ON appointments(appointment_date, appointment_time);
CREATE INDEX idx_appointments_slot ON appointments(slot_id);
CREATE INDEX idx_conversation_logs_contact ON conversation_logs(contact_number);
CREATE INDEX idx_conversation_logs_session ON conversation_logs(session_id);
CREATE INDEX idx_conversation_logs_created ON conversation_logs(created_at);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_logs ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Enable all access for service role" ON users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Enable all access for service role" ON slots FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Enable all access for service role" ON appointments FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Enable all access for service role" ON conversation_logs FOR ALL USING (true) WITH CHECK (true);

-- Auto-update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_appointments_updated_at BEFORE UPDATE ON appointments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert slots (Jan 26 - Feb 26, 2026, weekdays only, 6 times per day)
-- January 2026 weekdays
INSERT INTO slots (slot_date, slot_time, duration_minutes) VALUES
('2026-01-26', '10:00', 30), ('2026-01-26', '12:00', 30), ('2026-01-26', '14:00', 30), ('2026-01-26', '16:00', 30), ('2026-01-26', '17:00', 30), ('2026-01-26', '19:00', 30),
('2026-01-27', '10:00', 30), ('2026-01-27', '12:00', 30), ('2026-01-27', '14:00', 30), ('2026-01-27', '16:00', 30), ('2026-01-27', '17:00', 30), ('2026-01-27', '19:00', 30),
('2026-01-28', '10:00', 30), ('2026-01-28', '12:00', 30), ('2026-01-28', '14:00', 30), ('2026-01-28', '16:00', 30), ('2026-01-28', '17:00', 30), ('2026-01-28', '19:00', 30),
('2026-01-29', '10:00', 30), ('2026-01-29', '12:00', 30), ('2026-01-29', '14:00', 30), ('2026-01-29', '16:00', 30), ('2026-01-29', '17:00', 30), ('2026-01-29', '19:00', 30),
('2026-01-30', '10:00', 30), ('2026-01-30', '12:00', 30), ('2026-01-30', '14:00', 30), ('2026-01-30', '16:00', 30), ('2026-01-30', '17:00', 30), ('2026-01-30', '19:00', 30),
('2026-02-02', '10:00', 30), ('2026-02-02', '12:00', 30), ('2026-02-02', '14:00', 30), ('2026-02-02', '16:00', 30), ('2026-02-02', '17:00', 30), ('2026-02-02', '19:00', 30),
('2026-02-03', '10:00', 30), ('2026-02-03', '12:00', 30), ('2026-02-03', '14:00', 30), ('2026-02-03', '16:00', 30), ('2026-02-03', '17:00', 30), ('2026-02-03', '19:00', 30),
('2026-02-04', '10:00', 30), ('2026-02-04', '12:00', 30), ('2026-02-04', '14:00', 30), ('2026-02-04', '16:00', 30), ('2026-02-04', '17:00', 30), ('2026-02-04', '19:00', 30),
('2026-02-05', '10:00', 30), ('2026-02-05', '12:00', 30), ('2026-02-05', '14:00', 30), ('2026-02-05', '16:00', 30), ('2026-02-05', '17:00', 30), ('2026-02-05', '19:00', 30),
('2026-02-06', '10:00', 30), ('2026-02-06', '12:00', 30), ('2026-02-06', '14:00', 30), ('2026-02-06', '16:00', 30), ('2026-02-06', '17:00', 30), ('2026-02-06', '19:00', 30),
('2026-02-09', '10:00', 30), ('2026-02-09', '12:00', 30), ('2026-02-09', '14:00', 30), ('2026-02-09', '16:00', 30), ('2026-02-09', '17:00', 30), ('2026-02-09', '19:00', 30),
('2026-02-10', '10:00', 30), ('2026-02-10', '12:00', 30), ('2026-02-10', '14:00', 30), ('2026-02-10', '16:00', 30), ('2026-02-10', '17:00', 30), ('2026-02-10', '19:00', 30),
('2026-02-11', '10:00', 30), ('2026-02-11', '12:00', 30), ('2026-02-11', '14:00', 30), ('2026-02-11', '16:00', 30), ('2026-02-11', '17:00', 30), ('2026-02-11', '19:00', 30),
('2026-02-12', '10:00', 30), ('2026-02-12', '12:00', 30), ('2026-02-12', '14:00', 30), ('2026-02-12', '16:00', 30), ('2026-02-12', '17:00', 30), ('2026-02-12', '19:00', 30),
('2026-02-13', '10:00', 30), ('2026-02-13', '12:00', 30), ('2026-02-13', '14:00', 30), ('2026-02-13', '16:00', 30), ('2026-02-13', '17:00', 30), ('2026-02-13', '19:00', 30),
('2026-02-16', '10:00', 30), ('2026-02-16', '12:00', 30), ('2026-02-16', '14:00', 30), ('2026-02-16', '16:00', 30), ('2026-02-16', '17:00', 30), ('2026-02-16', '19:00', 30),
('2026-02-17', '10:00', 30), ('2026-02-17', '12:00', 30), ('2026-02-17', '14:00', 30), ('2026-02-17', '16:00', 30), ('2026-02-17', '17:00', 30), ('2026-02-17', '19:00', 30),
('2026-02-18', '10:00', 30), ('2026-02-18', '12:00', 30), ('2026-02-18', '14:00', 30), ('2026-02-18', '16:00', 30), ('2026-02-18', '17:00', 30), ('2026-02-18', '19:00', 30),
('2026-02-19', '10:00', 30), ('2026-02-19', '12:00', 30), ('2026-02-19', '14:00', 30), ('2026-02-19', '16:00', 30), ('2026-02-19', '17:00', 30), ('2026-02-19', '19:00', 30),
('2026-02-20', '10:00', 30), ('2026-02-20', '12:00', 30), ('2026-02-20', '14:00', 30), ('2026-02-20', '16:00', 30), ('2026-02-20', '17:00', 30), ('2026-02-20', '19:00', 30),
('2026-02-23', '10:00', 30), ('2026-02-23', '12:00', 30), ('2026-02-23', '14:00', 30), ('2026-02-23', '16:00', 30), ('2026-02-23', '17:00', 30), ('2026-02-23', '19:00', 30),
('2026-02-24', '10:00', 30), ('2026-02-24', '12:00', 30), ('2026-02-24', '14:00', 30), ('2026-02-24', '16:00', 30), ('2026-02-24', '17:00', 30), ('2026-02-24', '19:00', 30),
('2026-02-25', '10:00', 30), ('2026-02-25', '12:00', 30), ('2026-02-25', '14:00', 30), ('2026-02-25', '16:00', 30), ('2026-02-25', '17:00', 30), ('2026-02-25', '19:00', 30),
('2026-02-26', '10:00', 30), ('2026-02-26', '12:00', 30), ('2026-02-26', '14:00', 30), ('2026-02-26', '16:00', 30), ('2026-02-26', '17:00', 30), ('2026-02-26', '19:00', 30);

-- Verify tables and data
SELECT COUNT(*) as total_slots FROM slots;
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
