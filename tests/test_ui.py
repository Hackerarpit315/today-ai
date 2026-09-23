from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas.ui import *
from app.services.ui_service import UIService
from app.services.conversation import MockConversationBackend, InMemoryConversationRepository
from app.services.voice import MockVoiceInput, MockVoiceOutput

def ts(n=0): return datetime(2026,1,1,12,0,n,tzinfo=timezone.utc)
@pytest.fixture
def svc(): return UIService(max_messages=100)
def test_session_creation(svc):
 u=uuid4(); s=svc.create_session(u,Language.en,ts()); assert s.status==SessionStatus.active
def test_session_uuid(svc): assert svc.create_session(uuid4(),Language.hi,ts()).session_id
def test_user_isolation(svc):
 a=svc.create_session(uuid4(),Language.en,ts()); b=uuid4();
 with pytest.raises(KeyError): svc.get_session(a.session_id,b)
def test_active_session(svc): assert svc.create_session(uuid4(),Language.hinglish,ts()).status==SessionStatus.active
def test_paused_session(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); svc.repo.sessions[s.session_id]=s.model_copy(update={'status':SessionStatus.paused})
 with pytest.raises(ValueError): svc.add_message(s.session_id,s.user_id,MessageRole.user,'hi',ts(1),MessageType.text)
def test_closed_session(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); svc.repo.sessions[s.session_id]=s.model_copy(update={'status':SessionStatus.closed})
 with pytest.raises(ValueError): svc.add_message(s.session_id,s.user_id,'user','hi',ts(1),MessageType.text)
def test_message_creation(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); m=svc.add_message(s.session_id,s.user_id,MessageRole.user,'hello',ts(1),MessageType.text); assert m.message_id
def test_user_message(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); assert svc.add_message(s.session_id,s.user_id,MessageRole.user,'hello',ts(1),MessageType.text).role==MessageRole.user
def test_assistant_message(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); assert svc.add_message(s.session_id,s.user_id,MessageRole.assistant,'hello',ts(1),MessageType.text).role==MessageRole.assistant
def test_system_message(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); assert svc.add_message(s.session_id,s.user_id,MessageRole.system,'status',ts(1),MessageType.system_event).message_type==MessageType.system_event
def test_voice_transcript_message(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); assert svc.add_message(s.session_id,s.user_id,MessageRole.user,'hello',ts(1),MessageType.voice_transcript).message_type==MessageType.voice_transcript
def test_message_ordering(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); svc.add_message(s.session_id,s.user_id,MessageRole.user,'b',ts(2),MessageType.text); svc.add_message(s.session_id,s.user_id,MessageRole.user,'a',ts(1),MessageType.text); assert [m.content for m in svc.get_messages(s.session_id,s.user_id)]==['a','b']
def test_message_history(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); svc.add_message(s.session_id,s.user_id,MessageRole.user,'x',ts(1),MessageType.text); assert len(svc.get_messages(s.session_id,s.user_id))==1
def test_history_limit():
 s=UIService(max_messages=3); x=s.create_session(uuid4(),Language.en,ts());
 for i in range(4): s.add_message(x.session_id,x.user_id,MessageRole.user,str(i),ts(i+1),MessageType.text)
 assert [m.content for m in s.get_messages(x.session_id,x.user_id)]==['1','2','3']
def test_deterministic_history(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); svc.add_message(s.session_id,s.user_id,MessageRole.user,'x',ts(1),MessageType.text); assert svc.get_messages(s.session_id,s.user_id)[0].content=='x'
def test_missing_session(svc):
 with pytest.raises(KeyError): svc.get_session(uuid4(),uuid4())
def test_wrong_user_session_access(svc): test_user_isolation(svc)
def test_closed_session_message_rejection(svc): test_closed_session(svc)
def test_invalid_session_uuid():
 with pytest.raises(ValidationError): CreateSessionRequest(user_id='bad',timestamp=ts())
def test_invalid_message_uuid():
 with pytest.raises(ValidationError): ConversationMessage(message_id='bad',session_id=uuid4(),role='user',content='x',timestamp=ts(),message_type='text')
def test_message_length_validation():
 with pytest.raises(ValidationError): ConversationMessage(message_id=uuid4(),session_id=uuid4(),role='user',content='x'*10001,timestamp=ts(),message_type='text')
def test_secret_detection(svc):
 s=svc.create_session(uuid4(),Language.en,ts());
 with pytest.raises(ValueError): svc.add_message(s.session_id,s.user_id,MessageRole.user,'password=abc',ts(1),MessageType.text)
def test_password_protection(svc): test_secret_detection(svc)
def test_token_protection(svc):
 s=svc.create_session(uuid4(),Language.en,ts());
 with pytest.raises(ValueError): svc.add_message(s.session_id,s.user_id,MessageRole.user,'Bearer abc.def',ts(1),MessageType.text)
def test_safe_error_response():
 e=SafeError(error_id=uuid4(),code='BAD_REQUEST',message='Request could not be processed.',severity=ErrorSeverity.error,retryable=False); assert 'password' not in e.message.lower()
def test_error_severity(): assert SafeError(error_id=uuid4(),code='X',message='x',severity=ErrorSeverity.warning,retryable=True).severity==ErrorSeverity.warning
def test_retryable_error(): assert SafeError(error_id=uuid4(),code='X',message='x',severity=ErrorSeverity.error,retryable=True).retryable
def test_assistant_response_representation(): assert AssistantResponse(message='ok').message=='ok'
def test_action_reference(): assert AssistantResponse(message='ok',action_reference=uuid4()).action_reference
def test_verification_reference(): assert AssistantResponse(message='ok',verification_reference=uuid4()).verification_reference
def test_memory_reference(): assert AssistantResponse(message='ok',memory_reference=uuid4()).memory_reference
def test_security_status_representation(): assert AssistantResponse(message='ok',security_status='review').security_status=='review'
def test_system_status(svc): assert svc.status(ts()).components['ui']==ComponentStatus.available
def test_connection_status(): assert UIState(connection_status=ConnectionStatus.connected,assistant_state=AssistantState.idle,voice_state=VoiceState.idle,timestamp=ts()).connection_status==ConnectionStatus.connected
def test_assistant_state(): assert UIState(connection_status=ConnectionStatus.connected,assistant_state=AssistantState.thinking,voice_state=VoiceState.idle,timestamp=ts()).assistant_state==AssistantState.thinking
def test_voice_state(): assert VoiceStateModel(state=VoiceState.listening).state==VoiceState.listening
def test_voice_input_mock(): assert 'placeholder' in MockVoiceInput().transcribe('audio').lower()
def test_voice_output_mock(): assert 'placeholder' in MockVoiceOutput().synthesize('hello').lower()
def test_backend_adapter(): assert MockConversationBackend().respond(ConversationRequest(session_id=uuid4(),user_id=uuid4(),input_type=InputType.text,content='x',timestamp=ts())).status=='success'
def test_mock_backend_response(): assert MockConversationBackend().respond(ConversationRequest(session_id=uuid4(),user_id=uuid4(),input_type=InputType.text,content='x',timestamp=ts())).content=='Aapka request receive ho gaya.'
def test_deterministic_repeated_response():
 r=ConversationRequest(session_id=uuid4(),user_id=uuid4(),input_type=InputType.text,content='x',timestamp=ts()); a=MockConversationBackend().respond(r); b=MockConversationBackend().respond(r); assert a==b
def test_schema_extra_field_rejection():
 with pytest.raises(ValidationError): SafeError(error_id=uuid4(),code='X',message='x',severity='info',retryable=False,extra='x')
def test_invalid_enum_rejection():
 with pytest.raises(ValidationError): ConversationRequest(session_id=uuid4(),user_id=uuid4(),input_type='bad',content='x',timestamp=ts())
def test_timestamp_validation():
 with pytest.raises(ValidationError): ConversationRequest(session_id=uuid4(),user_id=uuid4(),input_type='text',content='x',timestamp=datetime(2026,1,1))
def test_clear_session(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); svc.add_message(s.session_id,s.user_id,MessageRole.user,'x',ts(1),MessageType.text); svc.clear_session(s.session_id,s.user_id); assert svc.get_messages(s.session_id,s.user_id)==[]
def test_immutable_message_behavior(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); m=svc.add_message(s.session_id,s.user_id,MessageRole.user,'x',ts(1),MessageType.text)
 with pytest.raises(ValidationError): m.content='y'
def test_ui_state_transition():
 s=UIState(connection_status=ConnectionStatus.connected,assistant_state=AssistantState.waiting_for_permission,voice_state=VoiceState.idle,timestamp=ts()); assert s.assistant_state==AssistantState.waiting_for_permission
def test_permission_required_presentation_state(): assert AssistantState.waiting_for_permission.value=='waiting_for_permission'
def test_execution_state_presentation(): assert AssistantState.executing.value=='executing'
def test_error_state_presentation(): assert AssistantState.error.value=='error'
def test_voice_response_message_type():
 m=ConversationMessage(message_id=uuid4(),session_id=uuid4(),role=MessageRole.assistant,content='hi',timestamp=ts(),message_type=MessageType.voice_response); assert m.message_type==MessageType.voice_response
def test_conversation_request_fields(): assert ConversationRequest(session_id=uuid4(),user_id=uuid4(),input_type=InputType.text,content='x',timestamp=ts()).input_type==InputType.text
def test_handle_conversation(svc):
 s=svc.create_session(uuid4(),Language.hinglish,ts()); r=svc.handle(ConversationRequest(session_id=s.session_id,user_id=s.user_id,input_type=InputType.text,content='hello',timestamp=ts(1))); assert r.content=='Aapka request receive ho gaya.'
def test_response_references_are_optional(): assert ConversationResponse(session_id=uuid4(),message_id=uuid4(),response_type=ResponseType.text,content='x',timestamp=ts(),status='success').action_reference is None
def test_user_isolation_messages(svc):
 s=svc.create_session(uuid4(),Language.en,ts());
 with pytest.raises(KeyError): svc.get_messages(s.session_id,uuid4())
def test_session_message_count(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); svc.add_message(s.session_id,s.user_id,MessageRole.user,'x',ts(1),MessageType.text); assert svc.get_session(s.session_id,s.user_id).message_count==1
def test_closed_session_handle(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); svc.repo.sessions[s.session_id]=s.model_copy(update={'status':SessionStatus.closed})
 with pytest.raises(ValueError): svc.handle(ConversationRequest(session_id=s.session_id,user_id=s.user_id,input_type=InputType.text,content='x',timestamp=ts(1)))
def test_max_error_length():
 with pytest.raises(ValidationError): SafeError(error_id=uuid4(),code='X',message='x'*2001,severity='error',retryable=False)
def test_ui_state_timestamp():
 with pytest.raises(ValidationError): UIState(connection_status='unknown',assistant_state='idle',voice_state='idle',timestamp=datetime(2026,1,1))
def test_language_enum(): assert ConversationSession(session_id=uuid4(),user_id=uuid4(),created_at=ts(),updated_at=ts(),language='hinglish').language==Language.hinglish
def test_session_update_timestamp(svc):
 s=svc.create_session(uuid4(),Language.en,ts()); svc.add_message(s.session_id,s.user_id,MessageRole.user,'x',ts(4),MessageType.text); assert svc.get_session(s.session_id,s.user_id).updated_at==ts(4)
def test_system_messages_preserved_under_limit():
 s=UIService(max_messages=2); x=s.create_session(uuid4(),Language.en,ts()); s.add_message(x.session_id,x.user_id,MessageRole.system,'system',ts(1),MessageType.system_event); s.add_message(x.session_id,x.user_id,MessageRole.user,'1',ts(2),MessageType.text); s.add_message(x.session_id,x.user_id,MessageRole.user,'2',ts(3),MessageType.text); assert [m.role for m in s.get_messages(x.session_id,x.user_id)]==[MessageRole.system,MessageRole.user]
def test_no_update_method(): assert not hasattr(InMemoryConversationRepository(),'update_message')
def test_no_delete_method(): assert not hasattr(InMemoryConversationRepository(),'delete_message')
def test_mock_no_external_execution(): assert MockConversationBackend().respond(ConversationRequest(session_id=uuid4(),user_id=uuid4(),input_type='text',content='send email',timestamp=ts())).content=='Aapka request receive ho gaya.'
