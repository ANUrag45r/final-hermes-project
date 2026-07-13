"""Chat endpoint: retrieve from GBrain, reason with Hermes."""
from fastapi import APIRouter, Depends

from app.core.dependencies import get_chat_service
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.chat.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
):
    return service.ask(request)
