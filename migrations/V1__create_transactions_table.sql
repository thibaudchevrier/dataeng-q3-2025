-- Create transactions table
CREATE TABLE IF NOT EXISTS transactions (
    -- Original transaction data
    id VARCHAR(255) PRIMARY KEY,
    description TEXT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    merchant VARCHAR(255) NOT NULL,
    operation_type VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    
    -- Metadata for tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create predictions table (separate for better data modeling)
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(255) NOT NULL UNIQUE,  -- One prediction per transaction
    category VARCHAR(100) NOT NULL,
    
    -- Prediction metadata (for future enhancements)
    confidence_score DECIMAL(5, 4) DEFAULT 1.0, -- e.g., 0.9542
    model_version VARCHAR(50) DEFAULT 'v1.0',
    
    -- Tracking
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    CONSTRAINT fk_transaction
        FOREIGN KEY (transaction_id)
        REFERENCES transactions(id)
        ON DELETE CASCADE
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_merchant ON transactions(merchant);
CREATE INDEX IF NOT EXISTS idx_transaction_id ON predictions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_category ON predictions(category);
CREATE INDEX IF NOT EXISTS idx_predicted_at ON predictions(predicted_at);

-- Create a view for unprocessed transactions (no predictions yet)
CREATE OR REPLACE VIEW unprocessed_transactions AS
SELECT t.* 
FROM transactions t
LEFT JOIN predictions p ON t.id = p.transaction_id
WHERE p.id IS NULL;

-- Create a view for transactions with their latest prediction
CREATE OR REPLACE VIEW transactions_with_predictions AS
SELECT 
    t.*,
    p.category,
    p.confidence_score,
    p.model_version,
    p.predicted_at
FROM transactions t
LEFT JOIN LATERAL (
    SELECT category, confidence_score, model_version, predicted_at
    FROM predictions
    WHERE transaction_id = t.id
    ORDER BY predicted_at DESC
    LIMIT 1
) p ON true;

-- Create a view for transaction statistics
CREATE OR REPLACE VIEW transaction_stats AS
SELECT 
    p.category,
    COUNT(*) as transaction_count,
    SUM(t.amount) as total_amount,
    AVG(t.amount) as avg_amount,
    MIN(t.timestamp) as first_transaction,
    MAX(t.timestamp) as last_transaction
FROM transactions t
INNER JOIN (
    SELECT DISTINCT ON (transaction_id) 
        transaction_id, category
    FROM predictions
    ORDER BY transaction_id, predicted_at DESC
) p ON t.id = p.transaction_id
GROUP BY p.category;
