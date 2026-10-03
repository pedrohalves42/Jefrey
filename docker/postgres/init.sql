-- =============================================================================
# POSTGRESQL INIT SCRIPT - Jefrey Production
# Runs on first container startup to initialize database
# =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create application user (if not exists via POSTGRES_USER)
-- DO $$ BEGIN
--     IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'jefrey') THEN
--         CREATE ROLE jefrey WITH LOGIN PASSWORD 'changeme';
--     END IF;
-- END $$;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE jefrey TO jefrey;
GRANT ALL ON SCHEMA public TO jefrey;

-- Create audit log table (for CIPHER-025)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    thread_id VARCHAR(128) NOT NULL,
    tool_name VARCHAR(128) NOT NULL,
    actor_role VARCHAR(32) NOT NULL,
    risk_level VARCHAR(16) NOT NULL,
    decision VARCHAR(32) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_thread_id ON audit_logs(thread_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tool_name ON audit_logs(tool_name);
CREATE INDEX IF NOT EXISTS idx_audit_logs_decision ON audit_logs(decision);

-- Create rate limit counters table (for CIPHER-026)
CREATE TABLE IF NOT EXISTS rate_limit_counters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    tool_name VARCHAR(128) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_user_tool_window ON rate_limit_counters(user_id, tool_name, window_start);

-- Create approvals table (for HITL)
CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(128) NOT NULL,
    tool_name VARCHAR(128) NOT NULL,
    args JSONB NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    risk_level VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    decided_by VARCHAR(100),
    decided_at TIMESTAMPTZ,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approvals_thread_id ON approvals(thread_id);
CREATE INDEX IF NOT EXISTS idx_approvals_user_id ON approvals(user_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_expires_at ON approvals(expires_at);

-- Create OAuth2 clients table (CIPHER-031)
CREATE TABLE IF NOT EXISTS oauth2_clients (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(255) UNIQUE NOT NULL,
    client_secret_hash VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(100) NOT NULL,
    allowed_scopes JSONB DEFAULT '[]',
    is_confidential BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_oauth2_client_id ON oauth2_clients(client_id);
CREATE INDEX IF NOT EXISTS idx_oauth2_tenant_id ON oauth2_clients(tenant_id);

-- Create memory tables (for P7 - 7-layer architecture)
CREATE TABLE IF NOT EXISTS memory_working (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    thread_id VARCHAR(128) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_working_user_thread ON memory_working(user_id, thread_id);
CREATE INDEX IF NOT EXISTS idx_memory_working_created ON memory_working(created_at);

CREATE TABLE IF NOT EXISTS memory_episodic (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    importance FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_episodic_user ON memory_episodic(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_episodic_embedding ON memory_episodic USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS memory_semantic (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_semantic_user ON memory_semantic(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_semantic_embedding ON memory_semantic USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS memory_preference (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_preference_user_key ON memory_preference(user_id, key);

CREATE TABLE IF NOT EXISTS memory_procedural (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    skill_name VARCHAR(128) NOT NULL,
    procedure JSONB NOT NULL,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_procedural_user_skill ON memory_procedural(user_id, skill_name);

CREATE TABLE IF NOT EXISTS memory_operational (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    operation_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    result JSONB,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_operational_user ON memory_operational(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_operational_type ON memory_operational(operation_type);
CREATE INDEX IF NOT EXISTS idx_memory_operational_created ON memory_operational(created_at);

CREATE TABLE IF NOT EXISTS memory_approval (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    approval_id UUID NOT NULL,
    tool_name VARCHAR(128) NOT NULL,
    args JSONB NOT NULL,
    decision VARCHAR(32),
    decided_by VARCHAR(100),
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_approval_user ON memory_approval(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_approval_approval_id ON memory_approval(approval_id);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers for updated_at
DROP TRIGGER IF EXISTS update_oauth2_clients_updated_at ON oauth2_clients;
CREATE TRIGGER update_oauth2_clients_updated_at
    BEFORE UPDATE ON oauth2_clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_memory_preference_updated_at ON memory_preference;
CREATE TRIGGER update_memory_preference_updated_at
    BEFORE UPDATE ON memory_preference
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_memory_procedural_updated_at ON memory_procedural;
CREATE TRIGGER update_memory_procedural_updated_at
    BEFORE UPDATE ON memory_procedural
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions on all tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO jefrey;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jefrey;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO jefrey;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO jefrey;

-- Analyze for query planner
ANALYZE;