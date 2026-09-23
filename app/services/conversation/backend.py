from abc import ABC, abstractmethod
from app.schemas.ui import ConversationRequest, BackendResult
class ConversationBackend(ABC):
    @abstractmethod
    def respond(self, request: ConversationRequest)->BackendResult: ...
