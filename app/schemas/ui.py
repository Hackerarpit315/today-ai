from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MESSAGE_LENGTH=10_000
MAX_ERROR_LENGTH=2_000

class SessionStatus(str, Enum): active='active'; paused='paused'; closed='closed'
class Language(str, Enum): en='en'; hi='hi'; hinglish='hinglish'
class MessageRole(str, Enum): user='user'; assistant='assistant'; system='system'
class MessageType(str, Enum): text='text'; voice_transcript='voice_transcript'; voice_response='voice_response'; system_event='system_event'; error='error'
class InputType(str, Enum): text='text'; voice_transcript='voice_transcript'
class ResponseType(str, Enum): text='text'; voice_response='voice_response'; system='system'; error='error'
class ComponentStatus(str, Enum): available='available'; unavailable='unavailable'; degraded='degraded'; unknown='unknown'
class ErrorSeverity(str, Enum): info='info'; warning='warning'; error='error'; critical='critical'
class VoiceState(str, Enum): idle='idle'; listening='listening'; processing='processing'; speaking='speaking'; error='error'
class ConnectionStatus(str, Enum): connected='connected'; disconnected='disconnected'; connecting='connecting'; unknown='unknown'
class AssistantState(str, Enum): idle='idle'; thinking='thinking'; responding='responding'; waiting_for_permission='waiting_for_permission'; executing='executing'; verifying='verifying'; error='error'

class Strict(BaseModel): model_config=ConfigDict(extra='forbid', frozen=True)

class ConversationSession(Strict):
    session_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    status: SessionStatus = SessionStatus.active
    language: Language = Language.en
    message_count: int = Field(default=0, ge=0)
    @field_validator('created_at','updated_at')
    @classmethod
    def aware(cls,v):
        if v.tzinfo is None or v.utcoffset() is None: raise ValueError('timestamp must be timezone-aware')
        return v

class ConversationMessage(Strict):
    message_id: UUID
    session_id: UUID
    role: MessageRole
    content: str = Field(min_length=1,max_length=MAX_MESSAGE_LENGTH)
    timestamp: datetime
    message_type: MessageType
    @field_validator('timestamp')
    @classmethod
    def aware(cls,v):
        if v.tzinfo is None or v.utcoffset() is None: raise ValueError('timestamp must be timezone-aware')
        return v
    @field_validator('content')
    @classmethod
    def no_secrets(cls,v):
        import re
        pats=[r'(?i)\bpassword\s*[:=]\s*\S+',r'(?i)\b(?:otp|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret)\s*[:=]\s*\S+',r'(?i)bearer\s+[A-Za-z0-9._~-]+',r'-----BEGIN [A-Z ]*PRIVATE KEY-----']
        if any(re.search(p,v) for p in pats): raise ValueError('sensitive content is not allowed')
        return v

class ConversationRequest(Strict):
    session_id: UUID
    user_id: UUID
    input_type: InputType
    content: str = Field(min_length=1,max_length=MAX_MESSAGE_LENGTH)
    timestamp: datetime
    @field_validator('timestamp')
    @classmethod
    def aware(cls,v):
        if v.tzinfo is None or v.utcoffset() is None: raise ValueError('timestamp must be timezone-aware')
        return v

class AssistantResponse(Strict):
    message: str = Field(min_length=1,max_length=MAX_MESSAGE_LENGTH)
    intent_reference: UUID|None=None
    plan_reference: UUID|None=None
    action_reference: UUID|None=None
    verification_reference: UUID|None=None
    memory_reference: UUID|None=None
    security_status: str|None=None

class ConversationResponse(Strict):
    session_id: UUID
    message_id: UUID
    response_type: ResponseType
    content: str = Field(min_length=1,max_length=MAX_MESSAGE_LENGTH)
    timestamp: datetime
    status: str
    intent_reference: UUID|None=None
    plan_reference: UUID|None=None
    action_reference: UUID|None=None
    verification_reference: UUID|None=None
    memory_reference: UUID|None=None
    security_status: str|None=None
    @field_validator('timestamp')
    @classmethod
    def aware(cls,v):
        if v.tzinfo is None or v.utcoffset() is None: raise ValueError('timestamp must be timezone-aware')
        return v

class SystemStatus(Strict):
    components: dict[str,ComponentStatus]

class SafeError(Strict):
    error_id: UUID
    code: str = Field(min_length=1,max_length=100)
    message: str = Field(min_length=1,max_length=MAX_ERROR_LENGTH)
    severity: ErrorSeverity
    retryable: bool

class VoiceStateModel(Strict): state: VoiceState
class UIState(Strict):
    session_id: UUID|None=None
    connection_status: ConnectionStatus
    assistant_state: AssistantState
    voice_state: VoiceState
    last_message_id: UUID|None=None
    error: SafeError|None=None
    timestamp: datetime
    @field_validator('timestamp')
    @classmethod
    def aware(cls,v):
        if v.tzinfo is None or v.utcoffset() is None: raise ValueError('timestamp must be timezone-aware')
        return v

class CreateSessionRequest(Strict):
    user_id: UUID
    language: Language=Language.en
    timestamp: datetime
    @field_validator('timestamp')
    @classmethod
    def aware(cls,v):
        if v.tzinfo is None or v.utcoffset() is None: raise ValueError('timestamp must be timezone-aware')
        return v

class BackendResult(Strict):
    response_type: ResponseType
    content: str = Field(min_length=1,max_length=MAX_MESSAGE_LENGTH)
    status: str='success'
    intent_reference: UUID|None=None
    plan_reference: UUID|None=None
    action_reference: UUID|None=None
    verification_reference: UUID|None=None
    memory_reference: UUID|None=None
    security_status: str|None=None
