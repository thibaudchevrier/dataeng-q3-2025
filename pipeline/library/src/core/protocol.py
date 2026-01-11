from typing import Iterator, Protocol


class ServiceProtocol(Protocol):

    def read(self, source: str) -> Iterator[tuple[list[dict], list[dict]]]:
        ...

    def predict(self, transactions: list[dict]) -> list[dict]:
        ...

    def bulk_write(self, transactions: list[dict], predictions: list[dict]) -> None:
        ...