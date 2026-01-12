"""
Tests for data validation module.

Covers validation of transaction records with various scenarios:
all valid, all invalid, and mixed batches.
"""

import pytest

from core.data_validation import validate_transaction_records


class TestValidateTransactionRecords:
    """Test suite for transaction validation function."""

    @pytest.mark.parametrize(
        "valid_records,expected_count",
        [
            # Single valid transaction
            (
                [
                    {
                        "id": "1",
                        "description": "Payment",
                        "amount": 100.0,
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Acme Corp",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-1",
                    }
                ],
                1,
            ),
            # Multiple valid transactions
            (
                [
                    {
                        "id": f"{i}",
                        "description": f"Transaction {i}",
                        "amount": float(i * 10),
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": f"Merchant {i}",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-1",
                    }
                    for i in range(1, 6)
                ],
                5,
            ),
            # Valid transaction with None merchant
            (
                [
                    {
                        "id": "1",
                        "description": "Online payment",
                        "amount": 50.0,
                        "timestamp": "2026-01-11T11:00:00",
                        "merchant": None,
                        "operation_type": "credit",
                        "side": "merchant",
                        "processing_type": "streaming",
                        "run_id": "kafka-123",
                    }
                ],
                1,
            ),
            # Large batch of valid transactions
            (
                [
                    {
                        "id": f"{i}",
                        "description": f"Bulk transaction {i}",
                        "amount": 1.0,
                        "timestamp": "2026-01-11T12:00:00",
                        "merchant": "Bulk Merchant",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "bulk-run",
                    }
                    for i in range(100)
                ],
                100,
            ),
        ],
    )
    def test_all_valid_transactions(self, valid_records, expected_count):
        """Test validation with all valid transactions."""
        validated, invalid = validate_transaction_records(valid_records)

        assert len(validated) == expected_count
        assert len(invalid) == 0

        # Check that UUIDs were generated for all validated transactions
        for transaction in validated:
            assert "id" in transaction
            assert transaction["id"] != ""
            assert len(transaction["id"]) == 36  # UUID length with hyphens

    @pytest.mark.parametrize(
        "invalid_records,expected_invalid_count",
        [
            # Missing description
            (
                [
                    {
                        "id": "1",
                        "amount": 100.0,
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Test",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-1",
                    }
                ],
                1,
            ),
            # Missing amount
            (
                [
                    {
                        "id": "1",
                        "description": "Payment",
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Test",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-1",
                    }
                ],
                1,
            ),
            # Invalid amount type
            (
                [
                    {
                        "id": "1",
                        "description": "Payment",
                        "amount": "not-a-number",
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Test",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-1",
                    }
                ],
                1,
            ),
            # Missing timestamp
            (
                [
                    {
                        "id": "1",
                        "description": "Payment",
                        "amount": 100.0,
                        "merchant": "Test",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-1",
                    }
                ],
                1,
            ),
            # Missing processing_type (lineage field)
            (
                [
                    {
                        "id": "1",
                        "description": "Payment",
                        "amount": 100.0,
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Test",
                        "operation_type": "debit",
                        "side": "customer",
                        "run_id": "run-1",
                    }
                ],
                1,
            ),
            # Missing run_id (lineage field)
            (
                [
                    {
                        "id": "1",
                        "description": "Payment",
                        "amount": 100.0,
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Test",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                    }
                ],
                1,
            ),
            # Multiple invalid transactions
            (
                [
                    {"id": "1", "description": "Missing amount"},
                    {"id": "2", "amount": 100.0},
                    {"id": "3"},
                ],
                3,
            ),
        ],
    )
    def test_all_invalid_transactions(self, invalid_records, expected_invalid_count):
        """Test validation with all invalid transactions."""
        validated, invalid = validate_transaction_records(invalid_records)

        assert len(validated) == 0
        assert len(invalid) == expected_invalid_count

    @pytest.mark.parametrize(
        "mixed_records,expected_valid,expected_invalid",
        [
            # Mix of valid and invalid (missing field)
            (
                [
                    {
                        "id": "1",
                        "description": "Valid payment",
                        "amount": 100.0,
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Acme",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-1",
                    },
                    {
                        "id": "2",
                        "description": "Missing amount",
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Test",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-1",
                    },
                ],
                1,
                1,
            ),
            # Mix with invalid types
            (
                [
                    {
                        "id": "1",
                        "description": "Valid",
                        "amount": 50.0,
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Valid Merchant",
                        "operation_type": "credit",
                        "side": "merchant",
                        "processing_type": "streaming",
                        "run_id": "kafka-123",
                    },
                    {
                        "id": "2",
                        "description": "Invalid amount type",
                        "amount": "string-amount",
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": "Test",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-1",
                    },
                    {
                        "id": "3",
                        "description": "Another valid",
                        "amount": 75.0,
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": None,
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "run-2",
                    },
                ],
                2,
                1,
            ),
            # Mostly valid with few invalid
            (
                [
                    {
                        "id": f"{i}",
                        "description": f"Transaction {i}",
                        "amount": float(i * 10),
                        "timestamp": "2026-01-11T10:00:00",
                        "merchant": f"Merchant {i}",
                        "operation_type": "debit",
                        "side": "customer",
                        "processing_type": "batch",
                        "run_id": "bulk-run",
                    }
                    for i in range(1, 11)
                ]
                + [
                    {"id": "invalid1", "description": "Missing fields"},
                    {"id": "invalid2", "amount": "wrong-type"},
                ],
                10,
                2,
            ),
        ],
    )
    def test_mixed_valid_and_invalid_transactions(self, mixed_records, expected_valid, expected_invalid):
        """Test validation with mix of valid and invalid transactions."""
        validated, invalid = validate_transaction_records(mixed_records)

        assert len(validated) == expected_valid
        assert len(invalid) == expected_invalid

        # Verify all validated have UUIDs
        for transaction in validated:
            assert "id" in transaction
            assert len(transaction["id"]) == 36

    def test_empty_input(self):
        """Test validation with empty list."""
        validated, invalid = validate_transaction_records([])

        assert len(validated) == 0
        assert len(invalid) == 0

    def test_validated_transactions_have_all_fields(self):
        """Test that validated transactions preserve all fields."""
        records = [
            {
                "id": "original-id",
                "description": "Test payment",
                "amount": 123.45,
                "timestamp": "2026-01-11T10:00:00",
                "merchant": "Test Merchant",
                "operation_type": "debit",
                "side": "customer",
                "processing_type": "batch",
                "run_id": "test-run-123",
            }
        ]

        validated, _ = validate_transaction_records(records)

        assert len(validated) == 1
        transaction = validated[0]

        # Check all fields are present
        assert "description" in transaction
        assert "amount" in transaction
        assert "timestamp" in transaction
        assert "merchant" in transaction
        assert "operation_type" in transaction
        assert "side" in transaction
        assert "processing_type" in transaction
        assert "run_id" in transaction

        # Check lineage fields have correct values
        assert transaction["processing_type"] == "batch"
        assert transaction["run_id"] == "test-run-123"

        # Check UUID was generated (not original id)
        assert transaction["id"] != "original-id"
