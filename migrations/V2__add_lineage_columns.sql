-- Add lineage tracking columns to transactions table
ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS processing_type VARCHAR(20),  -- 'batch' or 'streaming'
ADD COLUMN IF NOT EXISTS run_id VARCHAR(255);          -- Unique identifier for each processing run

-- Create index for common lineage queries
CREATE INDEX IF NOT EXISTS idx_processing_type ON transactions(processing_type);
CREATE INDEX IF NOT EXISTS idx_run_id ON transactions(run_id);

-- Update existing records with default values (optional, can be removed if not needed)
-- UPDATE transactions SET processing_type = 'batch' WHERE processing_type IS NULL;

COMMENT ON COLUMN transactions.processing_type IS 'Type of processing: batch or streaming';
COMMENT ON COLUMN transactions.run_id IS 'Unique identifier for the processing run (e.g., Airflow run_id or Kafka consumer group offset)';
