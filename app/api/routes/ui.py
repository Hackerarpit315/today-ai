from fastapi import APIRouter, HTTPException
from uuid import UUID
from datetime import datetime, timezone
from app.schemas.ui import *
from app.services.ui_service import UIService
router=APIRouter(prefix='/api/ui',tags=['ui'])
service=UIService()
@router.post('/session',response_model=ConversationSession)
def create(req:CreateSessionRequest): return service.create_session(req.user_id,req.language,req.timestamp)
@router.post('/message',response_model=ConversationResponse)
def message(req:ConversationRequest):
    try: return service.handle(req)
    except (KeyError,ValueError) as e: raise HTTPException(status_code=400,detail='Request could not be processed.')
@router.get('/session/{session_id}',response_model=ConversationSession)
def get_session(session_id:UUID,user_id:UUID):
    try:return service.get_session(session_id,user_id)
    except KeyError:raise HTTPException(status_code=404,detail='Session not found.')
@router.get('/session/{session_id}/messages',response_model=list[ConversationMessage])
def messages(session_id:UUID,user_id:UUID):
    try:return service.get_messages(session_id,user_id)
    except KeyError:raise HTTPException(status_code=404,detail='Session not found.')
@router.post('/session/{session_id}/clear')
def clear(session_id:UUID,user_id:UUID):
    try:service.clear_session(session_id,user_id);return {'status':'success'}
    except KeyError:raise HTTPException(status_code=404,detail='Session not found.')
@router.get('/status',response_model=SystemStatus)
def status(): return service.status(datetime.now(timezone.utc))
