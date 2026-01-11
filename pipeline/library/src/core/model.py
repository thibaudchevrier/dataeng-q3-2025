from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import uuid4


class Transaction(BaseModel):
    """
    Transaction model with validation.
    Used for both CSV/Kafka input (validates and assigns UUID).
    Ignores incoming 'id' field and always generates a new UUID.
    """
    id: str  # Will be replaced with UUID
    description: str
    amount: float
    timestamp: str  # Will be converted to datetime
    merchant: str | None
    operation_type: str
    side: str
    
    @field_validator('id', mode='before')
    @classmethod
    def replace_id_with_uuid(cls, _) -> str:
        """Always replace incoming id with a fresh UUID"""
        return str(uuid4())
    
    @field_validator('timestamp')
    @classmethod
    def parse_timestamp(cls, v: str) -> str:
        """Parse timestamp string to ISO format for database"""
        if isinstance(v, str):
            # Handle various timestamp formats
            try:
                # Try parsing common formats
                dt = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                return dt.isoformat()
            except ValueError:
                try:
                    dt = datetime.strptime(v, '%Y-%m-%dT%H:%M:%S')
                    return dt.isoformat()
                except ValueError:
                    raise ValueError(f'Invalid timestamp format: {v}')
        return v
    
    class Config:
        # Allow extra fields for forward compatibility
        extra = 'ignore'

