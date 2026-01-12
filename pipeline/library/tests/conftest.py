"""Pytest configuration and shared fixtures for library tests."""

import sys
from pathlib import Path

import pytest

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_transaction():
    """Fixture providing a valid transaction dict."""
    return {
        "id": "test-id-123",
        "description": "Sample transaction",
        "amount": 100.0,
        "timestamp": "2026-01-11T10:00:00",
        "merchant": "Test Merchant",
        "operation_type": "debit",
        "side": "customer",
        "processing_type": "batch",
        "run_id": "test-run-123",
    }


@pytest.fixture
def sample_transactions_batch():
    """Fixture providing a batch of valid transactions."""
    return [
        {
            "id": f"tx-{i}",
            "description": f"Transaction {i}",
            "amount": float(i * 10),
            "timestamp": "2026-01-11T10:00:00",
            "merchant": f"Merchant {i}",
            "operation_type": "debit",
            "side": "customer",
            "processing_type": "batch",
            "run_id": "batch-run-001",
        }
        for i in range(1, 11)
    ]


@pytest.fixture
def invalid_transaction_missing_field():
    """Fixture providing an invalid transaction (missing required field)."""
    return {
        "id": "invalid-1",
        "description": "Missing amount field",
        "timestamp": "2026-01-11T10:00:00",
        "merchant": "Test",
        "operation_type": "debit",
        "side": "customer",
        "processing_type": "batch",
        "run_id": "test-run",
        # Missing: amount
    }


@pytest.fixture
def invalid_transaction_wrong_type():
    """Fixture providing an invalid transaction (wrong field type)."""
    return {
        "id": "invalid-2",
        "description": "Wrong amount type",
        "amount": "not-a-number",  # Should be float
        "timestamp": "2026-01-11T10:00:00",
        "merchant": "Test",
        "operation_type": "debit",
        "side": "customer",
        "processing_type": "batch",
        "run_id": "test-run",
    }


@pytest.fixture
def sample_prediction():
    """Fixture providing a sample prediction dict."""
    return {
        "transaction_id": "test-id-123",
        "category": "legitimate",
        "confidence_score": 0.95,
        "model_version": "v1.0",
    }
