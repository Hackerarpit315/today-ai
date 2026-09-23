from app.schemas.ui import ConversationRequest, BackendResult, ResponseType
from .backend import ConversationBackend
class MockConversationBackend(ConversationBackend):
    def respond(self, request):
        return BackendResult(response_type=ResponseType.text,content='Aapka request receive ho gaya.',status='success')
