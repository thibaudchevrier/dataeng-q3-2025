"""Kafka streaming consumer for transaction processing.

This module implements a Kafka consumer that continuously consumes
transaction messages from Kafka topics, processes them (validation,
ML predictions, database persistence), and handles failures.
"""

import json
import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

from confluent_kafka import Consumer
from core import orchestrate_service, validate_transaction_records
from infrastructure import BaseService, db_transaction, get_db_session
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@contextmanager
def get_kafka_consumer(bootstrap_servers: str, group_id: str, topic: str):
    """
    Context manager for Kafka Consumer.

    Parameters
    ----------
    bootstrap_servers : str
        Kafka bootstrap servers (e.g., "localhost:9092").
    group_id : str
        Consumer group ID for coordinated consumption.
    topic : str
        Kafka topic to subscribe to.

    Yields
    ------
    Consumer
        Kafka consumer instance for message consumption.

    Notes
    -----
    Consumer automatically closes on context exit.
    Configured with 'auto.offset.reset' set to 'earliest'
    to consume from beginning if no offset exists.
    """
    c = Consumer({"bootstrap.servers": bootstrap_servers, "group.id": group_id, "auto.offset.reset": "earliest"})

    c.subscribe([topic])

    try:
        yield c
    finally:
        c.close()


class StreamingService(BaseService):
    """
    Streaming service for Kafka-based transaction processing.

    Extends BaseService to implement streaming-specific data loading
    via Kafka consumer. Polls Kafka topics for transaction messages,
    deserializes JSON, validates records, and yields batches to the
    orchestration layer. Implements adaptive batching with timeout
    strategies for variable message rates.

    Attributes
    ----------
    consumer : Consumer
        Confluent Kafka consumer instance for message polling.
    message_batch_size : int
        Target number of messages to accumulate before yielding batch.
    poll_timeout : float
        Timeout in seconds for individual Kafka poll operations.
    buffer_timeout : float
        Maximum seconds to wait for full batch before yielding partial batch.
    ml_api_url : str
        ML API endpoint URL (inherited from BaseService).
    db_session : Session
        SQLAlchemy session for database operations (inherited from BaseService).

    Methods
    -------
    read(batch_size: int) -> Iterator[tuple[list[dict], list[dict]]]
        Poll Kafka for messages and yield validated transaction batches.

    Notes
    -----
    Unlike BatchService, does not use S3 storage - data comes from Kafka stream.
    Implements dual timeout strategy:
    - Time-based: Yields partial batch after buffer_timeout seconds
    - Consecutive poll: Yields after max_consecutive_timeouts empty polls
    This ensures low-latency processing even with variable message rates.
    """

    def __init__(
        self,
        consumer: Consumer,
        ml_api_url: str,
        db_session: Session,
        message_batch_size: int = 100,
        poll_timeout: float = 1.0,
        buffer_timeout: float = 5.0,
    ) -> None:
        """
        Initialize StreamingService with Kafka consumer and configuration.

        Parameters
        ----------
        consumer : Consumer
            Confluent Kafka consumer instance (already subscribed to topic).
        ml_api_url : str
            ML API endpoint URL for fraud predictions.
        db_session : Session
            SQLAlchemy session for database operations.
        message_batch_size : int, optional
            Target messages to accumulate per batch (default: 100).
        poll_timeout : float, optional
            Kafka poll timeout in seconds (default: 1.0).
        buffer_timeout : float, optional
            Max seconds to wait for full batch before yielding partial (default: 5.0).

        Notes
        -----
        Calls parent BaseService.__init__() with ml_api_url and db_session only.
        Does not pass S3 configuration since streaming reads from Kafka, not S3.
        Consumer should be created via get_kafka_consumer context manager.
        """
        super().__init__(ml_api_url=ml_api_url, db_session=db_session)
        self.consumer = consumer
        self.message_batch_size = message_batch_size
        self.poll_timeout = poll_timeout
        self.buffer_timeout = buffer_timeout

    def read(self, batch_size: int) -> Iterator[tuple[list[dict], list[dict]]]:
        """
        Poll Kafka for messages and yield validated transaction batches.

        Implements the abstract read() method from BaseService for streaming
        processing. Polls Kafka until accumulating `batch_size` messages or
        timeout conditions are met, then deserializes, validates, and yields
        exactly ONE batch before returning control to caller.

        Parameters
        ----------
        batch_size : int
            Target number of messages to accumulate before validating and yielding.

        Yields
        ------
        tuple[list[dict], list[dict]]
            Single tuple containing:
            - List of valid transaction dictionaries (passed schema validation)
            - List of invalid transaction dictionaries with error details
              (includes both JSON deserialization errors and validation errors)

        Notes
        -----
        This generator yields exactly ONE batch then exhausts, allowing
        orchestrate_service to complete processing and return control to
        main loop. This design enables:
        - Transaction boundaries per batch (with db_transaction context)
        - Progress tracking after each batch
        - Graceful shutdown on KeyboardInterrupt

        Timeout Strategy:
        - Time-based: Yields partial batch if buffer_timeout seconds elapsed
        - Consecutive poll: Yields partial batch after 3 empty poll attempts
        - This ensures low-latency processing with variable message rates

        Validation:
        - JSON deserialization errors collected separately
        - Schema validation via validate_transaction_records from core
        - All errors combined and returned with batch

        The generator pattern enables lazy evaluation and memory efficiency
        for continuous streaming workloads.
        """
        raw_records = []
        json_errors = []
        consecutive_timeouts = 0
        max_consecutive_timeouts = 3  # Yield partial batch after 3 consecutive poll timeouts
        batch_start_time = time.time()

        while len(raw_records) < batch_size:
            msg = self.consumer.poll(self.poll_timeout)

            # Check time-based timeout (e.g., 5 seconds elapsed)
            elapsed_time = time.time() - batch_start_time
            if raw_records and elapsed_time >= self.buffer_timeout:
                logger.debug(f"Yielding partial batch after {elapsed_time:.1f}s timeout: {len(raw_records)} messages")
                # Validate accumulated records
                valid, invalid = validate_transaction_records(raw_records)
                # Combine validation errors with JSON errors
                all_invalid = invalid + json_errors
                yield (valid, all_invalid)
                return

            if msg is None:
                consecutive_timeouts += 1
                # Yield partial batch if we have data and hit consecutive timeout threshold
                if raw_records and consecutive_timeouts >= max_consecutive_timeouts:
                    logger.debug(
                        f"Yielding partial batch after {consecutive_timeouts} consecutive timeouts: "
                        f"{len(raw_records)} messages"
                    )
                    # Validate accumulated records
                    valid, invalid = validate_transaction_records(raw_records)
                    # Combine validation errors with JSON errors
                    all_invalid = invalid + json_errors
                    yield (valid, all_invalid)
                    return
                continue

            consecutive_timeouts = 0  # Reset on successful message

            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue

            value = msg.value()
            if value is None:
                logger.warning("Received message with None value, skipping")
                continue

            # Deserialize JSON
            try:
                raw_data = json.loads(value.decode("utf-8"))
                raw_records.append(raw_data)
            except json.JSONDecodeError as exc:
                logger.warning(f"Invalid JSON in message: {exc}")
                json_errors.append({"raw": value.decode("utf-8", errors="replace"), "error": str(exc)})
            except Exception as exc:
                logger.error(f"Unexpected error deserializing message: {exc}")
                json_errors.append({"error": str(exc)})

        # Validate full batch using core validation
        logger.debug(f"Validating batch: {len(raw_records)} records, {len(json_errors)} JSON errors")
        valid_transactions, invalid_transactions = validate_transaction_records(raw_records)

        # Combine validation errors with JSON deserialization errors
        all_invalid = invalid_transactions + json_errors

        logger.debug(
            f"Yielding full batch: {len(valid_transactions)} valid, {len(all_invalid)} invalid "
            f"(Pydantic: {len(invalid_transactions)}, JSON: {len(json_errors)})"
        )
        yield (valid_transactions, all_invalid)


def main():
    """
    Execute Kafka consumer workflow with continuous batch processing.

    This function orchestrates the streaming consumer lifecycle:
    - Loads configuration from environment variables
    - Creates Kafka consumer with group coordination
    - Creates database session for persistence
    - Continuously processes message batches through orchestration
    - Validates transactions, calls ML API, stores results

    Environment Variables
    ---------------------
    KAFKA_BOOTSTRAP_SERVERS : str
        Kafka bootstrap servers (default: 'localhost:9092').
    KAFKA_CONSUMER_GROUP : str
        Consumer group ID (default: 'transaction-consumer-group').
    KAFKA_TOPIC : str
        Source Kafka topic (default: 'transactions').
    ML_API_URL : str
        ML API endpoint (default: 'http://localhost:8000').
    MESSAGE_BATCH_SIZE : int
        Messages per batch from Kafka (default: 100).
    API_BATCH_SIZE : int
        Transactions per API request (default: 100).
    API_MAX_WORKERS : int
        Parallel API workers (default: 5).
    DB_ROW_BATCH_SIZE : int
        Threshold for bulk database writes (default: 1000).
    BUFFER_TIMEOUT : float
        Max seconds to wait for full batch before yielding partial (default: 5.0).
    DATABASE_URL : str
        PostgreSQL connection string (required).

    Notes
    -----
    Runs in infinite loop, processing batches continuously.
    Each iteration calls orchestrate_service which handles validation,
    prediction, and persistence for one batch window.
    Gracefully handles KeyboardInterrupt for clean shutdown.
    """
    # Configuration
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "transaction-consumer-group")
    topic = os.getenv("KAFKA_TOPIC", "transactions")
    ml_api_url = os.getenv("ML_API_URL", "http://localhost:8000")

    message_batch_size = int(os.getenv("MESSAGE_BATCH_SIZE", "50"))
    api_batch_size = int(os.getenv("API_BATCH_SIZE", "10"))
    api_max_workers = int(os.getenv("API_MAX_WORKERS", "5"))
    db_row_batch_size = int(os.getenv("DB_ROW_BATCH_SIZE", "50"))
    buffer_timeout = float(os.getenv("BUFFER_TIMEOUT", "5.0"))

    logger.info(f"Consumer started - Server: {bootstrap_servers}, Group: {group_id}, Topic: {topic}")
    logger.info(
        f"Batch config - Messages: {message_batch_size}, API: {api_batch_size}, "
        f"DB: {db_row_batch_size}, Buffer timeout: {buffer_timeout}s"
    )

    total_processed = 0
    total_failed = 0
    total_invalid = 0

    with (
        get_kafka_consumer(bootstrap_servers, group_id, topic) as consumer,
        get_db_session(os.environ["DATABASE_URL"]) as session,
    ):
        service = StreamingService(
            consumer=consumer,
            ml_api_url=ml_api_url,
            db_session=session,
            message_batch_size=message_batch_size,
            buffer_timeout=buffer_timeout,
        )

        try:
            logger.info("Starting continuous batch processing...")
            while True:
                # Process one batch window within a transaction
                with db_transaction(session):
                    processed, failed, invalid = orchestrate_service(
                        service=service,
                        row_batch_size=message_batch_size,
                        api_batch_size=api_batch_size,
                        api_max_workers=api_max_workers,
                        db_row_batch_size=db_row_batch_size,
                    )

                # Update totals after transaction commits
                total_processed += processed
                total_failed += len(failed)
                total_invalid += len(invalid)

                if processed > 0 or failed or invalid:
                    logger.info(
                        f"Batch complete - Processed: {processed}, Failed: {len(failed)}, "
                        f"Invalid: {len(invalid)} | Total: {total_processed} processed, "
                        f"{total_failed} failed, {total_invalid} invalid"
                    )

        except KeyboardInterrupt:
            logger.info(
                f"Consumer stopped. Final totals - Processed: {total_processed}, "
                f"Failed: {total_failed}, Invalid: {total_invalid}"
            )


if __name__ == "__main__":
    main()
