# Data Engineer Skill Test

First of all, thanks a lot for taking the time to go through this case. We know your time is valuable, and we really appreciate your commitment.
For this test, you'll be building 2 pipelines to get incoming transactions categorized.


## Instructions

The objective of this skill test is to assess how you would build a simple, and reliable pipelines to
ingest data from a CSV file, ask predictions to a ml service, and store results to DB. The ML API has already been bootstrapped, and you can find
some code available in the `ml_api` folder.

We are asking you to build a solution, that can both read data as batch from a CSV file, and consume data in real-time with Kafka.

Additional Information:
 - An example of how to test the API is described in the last section of this README. 
 - There is a CSV file with 10k transactions that you can find in the `data` folder.
 - Use any library or framework you want to build the pipeline
 - Use any database you want to store the results
 - Update the `docker-compose.yml` file to add any additional services you need 
 - Revamp the `ml_api` if you want to add more code, tests, etc. Just keep the same prediction logic, i.e. ```category=CATEGORIES[hash(transaction.id) % len(CATEGORIES)]```
 - Feel free to add data quality, validation, and any observability tools that you think could be useful
 - Think about how to make the pipelines resilient, scalable, and flexible.


### Requirements

Expected items to deliver: 
 - **A Python service running end-to-end that will process the CSV file as batch and in real time**, call the ml service, and store results to a DB. **The two pipelines must be resilient, scalable, and maintainable**.
 - A note/README section on how to run the 2 different pipelines batch, and real-time (Kafka).
 - A note/README to explain the design choices you made, and what you had in mind, but lacked time to implement it.
Feel free to add any diagrams or notes that you think are relevant.

   
## Running the Service

### Prerequisites

- Docker & Docker Compose installed on your machine

### Installation

To help you get predictions, we have provided a very simple ml prediction system that given
a transaction, will return a category based on it's hashed id.

1. Start Docker
2. Run ```docker-compose up --build``` in the root directory of the project
3. Server should be running on http://localhost:8000
4. You can test to send a payload on the `/predict` endpoint this way:
    ```bash
    curl -X POST http://localhost:8000/predict \
      -H "Content-Type: application/json" \
      -d '[{
          "id": "b9fa6684-502b-4695-8f92-247432ba610d",
          "description": "Weekly grocery shopping at Whole Foods",
          "amount": 100,
          "timestamp": "2023-04-15T14:30:00",
          "merchant": "Whole Foods Market",
          "operation_type": "card_payment",
          "side": "credit"
      }]'
    ```

---

## 📚 Documentation

### For Reviewers & Evaluators

This project includes comprehensive documentation to help you understand and evaluate the implementation:

- **[HOWTO.md](HOWTO.md)** - Complete operational guide
  - How to run batch and streaming pipelines
  - Service endpoints and credentials
  - Monitoring and troubleshooting
  - Quick reference guide

- **[NOTES.md](NOTES.md)** - Design choices and architecture
  - Architectural decisions and rationale
  - Technology stack justification
  - Performance characteristics
  - Future enhancements and trade-offs
  - **Architecture diagrams included**

### For Developers

Component-specific documentation:
- [Library README](pipeline/library/README.md) - Hexagonal architecture & shared components
- [Batch Service](pipeline/application/batch/service/README.md) - CSV processing details
- [Streaming Consumer](pipeline/application/streaming/consumer/README.md) - Kafka consumer implementation
- [Streaming Producer](pipeline/application/streaming/producer/README.md) - Event generation
- [Orchestration](pipeline/application/batch/orchestration/README.md) - Airflow DAGs

### Quick Start

```bash
# Start all services (batch + streaming + infrastructure)
make all

# Check service status
make status

# View logs
make logs

# Stop everything
make down

# Clean everything (including volumes)
make clean
```

### Project Statistics

| Metric | Value |
|--------|-------|
| **Total Lines of Code** | ~3,500+ |
| **Documentation** | 2,700+ lines |
| **Tests** | 48 (100% passing) |
| **Services** | 10+ containerized |
| **README files** | 8 comprehensive guides |
| **Make commands** | 20+ automation tasks |

---

## ✅ Requirements Checklist

- ✅ **Batch pipeline** - CSV processing with Airflow orchestration
- ✅ **Streaming pipeline** - Kafka producers/consumers for real-time
- ✅ **ML API integration** - Classification service with retry logic
- ✅ **Database storage** - PostgreSQL with lineage tracking
- ✅ **Resilience** - Error handling, retries, DLQ, health checks
- ✅ **Scalability** - Parallel processing, partitioning, containerization
- ✅ **Maintainability** - Clean architecture, tests, documentation
- ✅ **Data quality** - Pydantic validation, error tracking
- ✅ **Observability** - Kafka UI, Adminer, Airflow UI, logging
- ✅ **Documentation** - HOWTO.md, NOTES.md, 6 component READMEs
- ✅ **Design notes** - Architectural decisions explained
- ✅ **Architecture diagrams** - System and data flow visualizations

