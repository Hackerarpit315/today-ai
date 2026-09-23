from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4
import re
from app.schemas.ui import *
from app.services.conversation import InMemoryConversationRepository, ConversationBackend, MockConversationBackend

SECRET_RE=re.compile(r'(?i)(?:password|passwd|pwd|otp|api[_ -]?key|apikey|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret)\s*[:=]\s*\S+|bearer\s+[A-Za-z0-9._~-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----')
class UIService:
    def __init__(self, repository=None, backend=None, max_messages=100):
        self.repo=repository or InMemoryConversationRepository(max_messages=max_messages)
        self.backend=backend or MockConversationBackend()
    def _check_user(self,s,user_id):
        if not s or s.user_id!=user_id: raise KeyError('session not found')
        return s
    def create_session(self,user_id,language,timestamp):
        s=ConversationSession(session_id=uuid4(),user_id=user_id,created_at=timestamp,updated_at=timestamp,status=SessionStatus.active,language=language)
        return self.repo.create_session(s)
    def get_session(self,sid,user_id): return self._check_user(self.repo.get_session(sid),user_id)
    def get_messages(self,sid,user_id): self.get_session(sid,user_id); return self.repo.get_messages(sid)
    def clear_session(self,sid,user_id): self.get_session(sid,user_id); self.repo.clear_session(sid)
    def add_message(self,sid,user_id,role,content,timestamp,message_type):
        s=self.get_session(sid,user_id)
        if s.status != SessionStatus.active: raise ValueError(f'session is {s.status.value}')
        if SECRET_RE.search(content): raise ValueError('sensitive content is not allowed')
        return self.repo.add_message(ConversationMessage(message_id=uuid4(),session_id=sid,role=role,content=content,timestamp=timestamp,message_type=message_type))
    def handle(self,req:ConversationRequest):
        s=self.get_session(req.session_id,req.user_id)
        if s.status != SessionStatus.active: raise ValueError(f'session is {s.status.value}')
        mt=MessageType.voice_transcript if req.input_type==InputType.voice_transcript else MessageType.text
        self.add_message(req.session_id,req.user_id,MessageRole.user,req.content,req.timestamp,mt)
        result=self.backend.respond(req)
        msg=self.add_message(req.session_id,req.user_id,MessageRole.assistant,result.content,req.timestamp,MessageType.voice_response if result.response_type==ResponseType.voice_response else MessageType.text)
        return ConversationResponse(session_id=req.session_id,message_id=msg.message_id,response_type=result.response_type,content=result.content,timestamp=req.timestamp,status=result.status,intent_reference=result.intent_reference,plan_reference=result.plan_reference,action_reference=result.action_reference,verification_reference=result.verification_reference,memory_reference=result.memory_reference,security_status=result.security_status)
    def status(self,timestamp):
        components={x:ComponentStatus.unknown for x in ['input','intent','context','research','verification','planning','priority','today','permission','action','execution','memory','audit','security','ui']}; components['ui']=ComponentStatus.available
        return SystemStatus(components=components)
    def ui_state(self,session_id,timestamp,**kwargs): return UIState(session_id=session_id,timestamp=timestamp,**kwargs)
