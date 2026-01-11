from .api import predict_batch
from .database import db_write_results
from sqlalchemy.orm import Session


class BaseService:

    def __init__(self, s3_path: str, storage_options: dict, ml_api_url: str, db_session: Session) -> None:
        self.s3_path = s3_path
        self.storage_options = storage_options
        self.ml_api_url = ml_api_url
        self.db_session = db_session


    def predict(self, transactions: list[dict]) -> tuple[list[dict], list[dict]]:
        return predict_batch(transactions, self.ml_api_url)
    

    def bulk_write(self, transactions: list[dict], predictions: list[dict]) -> None:
        db_write_results(self.db_session, transactions, predictions)