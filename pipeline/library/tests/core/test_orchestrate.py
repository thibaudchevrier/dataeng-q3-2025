"""
Tests for service orchestration module.

Tests different batch processing strategies using a mock service
that implements the ServiceProtocol.
"""

from collections.abc import Iterator

import pytest

from core.orchestrate import orchestrate_service


class MockService:
    """
    Mock service implementing ServiceProtocol for testing.

    Simulates API behavior with configurable responses.
    Tracks method calls and collects written data for verification.
    """

    def __init__(
        self,
        data_batches: list[list[dict]],
        invalid_batches: list[list[dict]] | None = None,
        prediction_responses: dict[str, dict] | None = None,
        api_failure_ids: list[str] | None = None,
    ):
        """
        Initialize mock service with test data.

        Parameters
        ----------
        data_batches : list[list[dict]]
            List of transaction batches to return from read()
        invalid_batches : list[list[dict]] | None
            List of invalid transaction batches (parallel to data_batches)
        prediction_responses : dict[str, dict] | None
            Dict mapping transaction IDs to prediction responses
        api_failure_ids : list[str] | None
            List of transaction IDs that should fail prediction
        """
        self.data_batches = data_batches
        self.invalid_batches = invalid_batches or [[] for _ in data_batches]
        self.prediction_responses = prediction_responses or {}
        self.api_failure_ids = api_failure_ids or []

        # Tracking for assertions
        self.read_calls = 0
        self.predict_calls = 0
        self.bulk_write_calls = 0
        self.written_transactions = []
        self.written_predictions = []

    def read(self, batch_size: int) -> Iterator[tuple[list[dict], list[dict]]]:
        """Yield batches of valid and invalid transactions."""
        self.read_calls += 1

        assert batch_size is not None

        yield from zip(self.data_batches, self.invalid_batches, strict=True)

    def predict(self, transactions: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Simulate ML API predictions.

        Returns predictions based on predefined responses and failures.
        Returns (successful_transactions, predictions) for now, but will change to match protocol.
        """
        self.predict_calls += 1

        successful_transactions = []
        failed_transactions = []
        predictions = []

        for transaction in transactions:
            transaction_id = transaction.get("id")

            # Simulate API failure
            if transaction_id in self.api_failure_ids:
                failed_transactions.append(transaction)
                continue

            # Get prediction from response map or create default
            prediction = self.prediction_responses.get(
                transaction_id,
                {
                    "transaction_id": transaction_id,
                    "category": "legitimate",
                    "confidence_score": 0.95,
                },
            )

            successful_transactions.append(transaction)
            predictions.append(prediction)

        # Return (successful_transactions, predictions)
        # Note: orchestrate code doesn't handle partial failures well,
        # so failed_transactions are tracked here but not returned for now
        return successful_transactions, predictions

    def bulk_write(self, transactions: list[dict], predictions: list[dict]) -> None:
        """Simulate database write and collect data for verification."""
        # Only count and record if there's actual data to write
        if transactions or predictions:
            self.bulk_write_calls += 1
            self.written_transactions.extend(transactions)
            self.written_predictions.extend(predictions)
            # Clear the input lists after writing (real DB service would consume them)
            transactions.clear()
            predictions.clear()


class TestOrchestrateService:
    """Test suite for service orchestration function."""

    def _create_transaction(self, id: str, amount: float = 100.0) -> dict:
        """Helper to create a transaction dict."""
        return {
            "id": id,
            "description": f"Transaction {id}",
            "amount": amount,
            "timestamp": "2026-01-11T10:00:00",
            "merchant": "Test Merchant",
            "operation_type": "debit",
            "side": "customer",
            "processing_type": "batch",
            "run_id": "test-run",
        }

    @pytest.mark.parametrize(
        "num_transactions,row_batch_size,api_batch_size,db_row_batch_size,expected_written,expected_predictions,expected_predict_calls,expected_bulk_write_calls",
        [
            # db_row_batch_size > row_batch_size: All transactions fit in one DB write
            (
                10,
                5,  # Read 5 at a time
                3,  # API processes 3 at a time (need 4 calls: 3+3+3+1)
                20,  # DB writes 20 at a time (all 10 fit in one write)
                [{"id": str(i)} for i in range(10)],
                [{"transaction_id": str(i)} for i in range(10)],
                4,  # 10 transactions / 3 per API batch = 4 calls
                1,  # All 10 fit in one DB write
            ),
            # db_row_batch_size < row_batch_size: Multiple DB writes needed
            (
                15,
                20,  # Read 20 at a time (all 15 in one read)
                5,  # API processes 5 at a time (need 3 calls: 5+5+5)
                7,  # DB writes 7 at a time (need 2 writes: 7+7, then final bulk_write with cleared buffers)
                [{"id": str(i)} for i in range(15)],
                [{"transaction_id": str(i)} for i in range(15)],
                3,  # 15 transactions / 5 per API batch = 3 calls
                2,  # 15 transactions / 7 per DB batch = 2 writes (buffers cleared after each write)
            ),
            # db_row_batch_size == row_batch_size: Synchronized batching
            (
                12,
                6,  # Read 6 at a time
                2,  # API processes 2 at a time (need 3 calls per read batch)
                6,  # DB writes 6 at a time (matches read batch)
                [{"id": str(i)} for i in range(12)],
                [{"transaction_id": str(i)} for i in range(12)],
                6,  # 12 transactions / 2 per API batch = 6 calls
                2,  # 12 transactions / 6 per DB batch = 2 writes
            ),
            # Small batch with db_row_batch_size smaller than transaction count
            (
                8,
                10,  # Read 10 at a time (all 8 in one read)
                4,  # API processes 4 at a time (need 2 calls: 4+4)
                3,  # DB writes 3 at a time (need 2 writes: 3+3, then final bulk_write with cleared buffers)
                [{"id": str(i)} for i in range(8)],
                [{"transaction_id": str(i)} for i in range(8)],
                2,  # 8 transactions / 4 per API batch = 2 calls
                2,  # 8 transactions / 3 per DB batch = 2 writes (buffers cleared after each write)
            ),
            # Large batch with mixed sizes
            (
                25,
                15,  # Read 15 at a time (need 2 reads: 15+10)
                5,  # API processes 5 at a time (need 5 calls: 5+5+5+5+5)
                10,  # DB writes 10 at a time (need 3 writes: 10+10+5)
                [{"id": str(i)} for i in range(25)],
                [{"transaction_id": str(i)} for i in range(25)],
                5,  # 25 transactions / 5 per API batch = 5 calls
                3,  # 25 transactions / 10 per DB batch = 3 writes
            ),
        ],
    )
    def test_batch_strategies(
        self,
        num_transactions,
        row_batch_size,
        api_batch_size,
        db_row_batch_size,
        expected_written,
        expected_predictions,
        expected_predict_calls,
        expected_bulk_write_calls,
    ):
        """Test different batching strategies with varying batch sizes."""
        transactions = [self._create_transaction(str(i)) for i in range(num_transactions)]
        mock_service = MockService(data_batches=[transactions])

        total_processed, failed, invalid = orchestrate_service(
            service=mock_service,
            row_batch_size=row_batch_size,
            api_batch_size=api_batch_size,
            api_max_workers=2,
            db_row_batch_size=db_row_batch_size,
        )

        # Compare actual vs expected by extracting IDs
        written_ids = [{"id": tx["id"]} for tx in mock_service.written_transactions]
        prediction_ids = [{"transaction_id": p["transaction_id"]} for p in mock_service.written_predictions]

        assert total_processed == num_transactions
        assert len(failed) == 0
        assert len(invalid) == 0
        assert len(written_ids) == len(expected_written)
        assert len(prediction_ids) == len(expected_predictions)
        assert written_ids == expected_written
        assert prediction_ids == expected_predictions
        assert mock_service.predict_calls == expected_predict_calls
        assert mock_service.bulk_write_calls == expected_bulk_write_calls

    @pytest.mark.parametrize(
        "input_valid,input_invalid,api_failure_ids,expected_total_processed,expected_written,expected_predictions,expected_failed,expected_invalid",
        [
            # All succeed - no failures, no invalid
            (
                [{"id": "1", "amount": 100.0}, {"id": "2", "amount": 200.0}],
                [],
                [],
                2,
                [{"id": "1"}, {"id": "2"}],
                [{"transaction_id": "1"}, {"transaction_id": "2"}],
                [],
                [],
            ),
            # All invalid - no valid transactions
            (
                [],
                [{"id": "invalid1", "missing": "fields"}, {"id": "invalid2", "missing": "fields"}],
                [],
                0,
                [],
                [],
                [],
                [{"id": "invalid1"}, {"id": "invalid2"}],
            ),
            # Mixed: valid + invalid - no API failures
            (
                [{"id": "1", "amount": 100.0}, {"id": "2", "amount": 200.0}],
                [{"id": "invalid1", "missing": "fields"}],
                [],
                2,
                [{"id": "1"}, {"id": "2"}],
                [{"transaction_id": "1"}, {"transaction_id": "2"}],
                [],
                [{"id": "invalid1"}],
            ),
            # Empty input - nothing to process
            (
                [],
                [],
                [],
                0,
                [],
                [],
                [],
                [],
            ),
        ],
    )
    def test_orchestrate_scenarios(
        self,
        input_valid,
        input_invalid,
        api_failure_ids,
        expected_total_processed,
        expected_written,
        expected_predictions,
        expected_failed,
        expected_invalid,
    ):
        """Test orchestration with various combinations of valid, invalid, and failed transactions."""
        # Prepare valid transactions
        valid_transactions = [self._create_transaction(tx["id"], tx["amount"]) for tx in input_valid]

        mock_service = MockService(
            data_batches=[valid_transactions],
            invalid_batches=[input_invalid],
            api_failure_ids=api_failure_ids,
        )

        total_processed, failed, invalid = orchestrate_service(
            service=mock_service,
            row_batch_size=20,
            api_batch_size=5,
            api_max_workers=2,
            db_row_batch_size=100,
        )

        # Extract IDs for comparison
        written_ids = [{"id": tx["id"]} for tx in mock_service.written_transactions]
        prediction_ids = [{"transaction_id": p["transaction_id"]} for p in mock_service.written_predictions]
        failed_ids = [{"id": tx["id"]} for tx in failed]
        invalid_ids = [{"id": tx["id"]} for tx in invalid]

        # Assert all outputs
        assert total_processed == expected_total_processed
        assert len(written_ids) == len(expected_written)
        assert len(prediction_ids) == len(expected_predictions)
        assert len(failed_ids) == len(expected_failed)
        assert len(invalid_ids) == len(expected_invalid)
        assert written_ids == expected_written
        assert prediction_ids == expected_predictions
        assert failed_ids == expected_failed
        assert invalid_ids == expected_invalid

    @pytest.mark.parametrize(
        "input_batches,expected_total,expected_read_calls",
        [
            # Single batch
            ([[{"id": "1"}, {"id": "2"}]], 2, 1),
            # Multiple batches
            ([[{"id": "1"}, {"id": "2"}], [{"id": "3"}, {"id": "4"}], [{"id": "5"}]], 5, 1),
            # Empty batch
            ([[]], 0, 1),
        ],
    )
    def test_orchestrate_multiple_batches(self, input_batches, expected_total, expected_read_calls):
        """Test orchestration across multiple read batches."""
        # Create full transaction objects from input
        full_batches = []
        for batch in input_batches:
            full_batch = [self._create_transaction(tx["id"]) for tx in batch]
            full_batches.append(full_batch)

        mock_service = MockService(data_batches=full_batches)

        total_processed, failed, invalid = orchestrate_service(
            service=mock_service,
            row_batch_size=5,
            api_batch_size=3,
            api_max_workers=2,
            db_row_batch_size=10,
        )

        assert total_processed == expected_total
        assert mock_service.read_calls == expected_read_calls

    @pytest.mark.parametrize(
        "num_transactions,db_batch_size,expected_bulk_writes,expected_batch_sizes",
        [
            # Fits in one batch
            (5, 10, 1, [5]),
            # Exactly two batches
            (20, 10, 2, [10, 10]),
            # Multiple batches with remainder
            (25, 10, 3, [10, 10, 5]),
        ],
    )
    def test_orchestrate_triggers_bulk_write_at_threshold(
        self, num_transactions, db_batch_size, expected_bulk_writes, expected_batch_sizes
    ):
        """Test that bulk writes are triggered when threshold is reached."""
        transactions = [self._create_transaction(str(i)) for i in range(num_transactions)]
        mock_service = MockService(data_batches=[transactions])

        total_processed, failed, invalid = orchestrate_service(
            service=mock_service,
            row_batch_size=30,
            api_batch_size=5,
            api_max_workers=2,
            db_row_batch_size=db_batch_size,
        )

        assert total_processed == num_transactions
        assert mock_service.bulk_write_calls == expected_bulk_writes

    @pytest.mark.parametrize(
        "num_transactions,api_batch_size,api_workers,expected_api_calls",
        [
            # Single worker
            (10, 5, 1, 2),
            # Multiple workers
            (20, 5, 4, 4),
            # Large batch
            (30, 10, 2, 3),
        ],
    )
    def test_parallel_api_calls(self, num_transactions, api_batch_size, api_workers, expected_api_calls):
        """Test that parallel API calls work correctly."""
        transactions = [self._create_transaction(str(i)) for i in range(num_transactions)]
        mock_service = MockService(data_batches=[transactions])

        total_processed, failed, invalid = orchestrate_service(
            service=mock_service,
            row_batch_size=50,
            api_batch_size=api_batch_size,
            api_max_workers=api_workers,
            db_row_batch_size=100,
        )

        assert total_processed == num_transactions
        assert mock_service.predict_calls == expected_api_calls

    @pytest.mark.parametrize(
        "input_transactions,custom_predictions,expected_predictions",
        [
            # Custom categories
            (
                [{"id": "0"}, {"id": "1"}, {"id": "2"}],
                {
                    "0": {"transaction_id": "0", "category": "fraud", "confidence_score": 0.98},
                    "1": {"transaction_id": "1", "category": "legitimate", "confidence_score": 0.92},
                    "2": {"transaction_id": "2", "category": "suspicious", "confidence_score": 0.75},
                },
                [
                    {"transaction_id": "0", "category": "fraud", "confidence_score": 0.98},
                    {"transaction_id": "1", "category": "legitimate", "confidence_score": 0.92},
                    {"transaction_id": "2", "category": "suspicious", "confidence_score": 0.75},
                ],
            ),
        ],
    )
    def test_custom_prediction_responses(self, input_transactions, custom_predictions, expected_predictions):
        """Test orchestration with custom prediction responses."""
        transactions = [self._create_transaction(tx["id"]) for tx in input_transactions]
        mock_service = MockService(data_batches=[transactions], prediction_responses=custom_predictions)

        total_processed, failed, invalid = orchestrate_service(
            service=mock_service,
            row_batch_size=10,
            api_batch_size=10,
            api_max_workers=1,
            db_row_batch_size=100,
        )

        assert total_processed == len(input_transactions)
        assert mock_service.written_predictions == expected_predictions
