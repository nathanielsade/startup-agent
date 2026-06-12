from abc import ABC, abstractmethod


class DeliveryChannel(ABC):
    @abstractmethod
    def deliver(self, title: str, body: str) -> None: ...
