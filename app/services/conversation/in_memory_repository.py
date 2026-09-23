from __future__ import annotations
from uuid import UUID
from app.schemas.ui import ConversationSession, ConversationMessage
from .repository import ConversationRepository
class InMemoryConversationRepository(ConversationRepository):
    def __init__(self, max_messages=100): self.sessions={}; self.messages={}; self.max_messages=max_messages
    def create_session(self,session): self.sessions[session.session_id]=session; self.messages.setdefault(session.session_id,[]); return session
    def get_session(self,sid): return self.sessions.get(sid)
    def add_message(self,msg):
        if msg.session_id not in self.sessions: raise KeyError('session not found')
        self.messages.setdefault(msg.session_id,[]).append(msg)
        items=self.messages[msg.session_id]
        if len(items)>self.max_messages:
            system=[m for m in items if m.role.value=='system']
            non=[m for m in items if m.role.value!='system']
            while len(system)+len(non)>self.max_messages:
                if non: non.pop(0)
                else: system.pop(0)
            self.messages[msg.session_id]=sorted(system+non,key=lambda m:(m.timestamp,m.message_id.hex))
        s=self.sessions[msg.session_id]; self.sessions[msg.session_id]=s.model_copy(update={'message_count':len(self.messages[msg.session_id]),'updated_at':msg.timestamp})
        return msg
    def get_messages(self,sid): return list(sorted(self.messages.get(sid,[]),key=lambda m:(m.timestamp,m.message_id.hex)))
    def clear_session(self,sid):
        if sid not in self.sessions: raise KeyError('session not found')
        self.messages[sid]=[]; s=self.sessions[sid]; self.sessions[sid]=s.model_copy(update={'message_count':0})
