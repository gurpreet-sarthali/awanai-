"""Chat API routes."""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_ai_service, get_chat_service, get_current_user, get_monitoring_service
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.schemas.chat import (
    ConversationCreateRequest,
    ConversationDetail,
    ConversationRenameRequest,
    ConversationSummary,
    MessageCreateRequest,
    MessageResponse,
)
from backend.services.ai_orchestration_service import AIOrchestrationService
from backend.services.chat_service import ChatService, ChatServiceError
from backend.services.dataset_access_service import DatasetAccessError
from backend.services.gemini_service import AIConfigurationError, AIServiceError, UnsupportedQuestionError
from backend.services.monitoring_service import MonitoringService
from backend.services.rate_limiter import AIRateLimitError

router = APIRouter(prefix="/conversations", tags=["chat"])


def _handle_ai_error(error: Exception) -> AppError:
    if isinstance(error, DatasetAccessError):
        return AppError(403, "dataset_access_denied", str(error))
    if isinstance(error, AIConfigurationError):
        return AppError(503, "ai_configuration_missing", "AI service is not configured.")
    if isinstance(error, AIRateLimitError):
        return AppError(429, "ai_rate_limit", str(error))
    if isinstance(error, UnsupportedQuestionError):
        return AppError(400, "unsupported_question", str(error))
    if isinstance(error, AIServiceError):
        return AppError(503, "ai_unavailable", str(error))
    return AppError(503, "analysis_unavailable", "The requested analysis could not be completed.")


@router.post("", response_model=ConversationSummary, summary="Create a new conversation")
def create_conversation(
    request: ConversationCreateRequest,
    user: UserRecord = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> ConversationSummary:
    try:
        title = "New Conversation"
        record = service.create_conversation(user.id, title, request.dataset_id)
        monitoring_service.track_event(user.id, "conversation_created", {"conversation_id": record.id, "dataset_id": request.dataset_id})
        import dataclasses
        return ConversationSummary(**dataclasses.asdict(record))
    except Exception as error:
        import traceback; traceback.print_exc()
        raise AppError(500, "conversation_creation_failed", "Failed to create conversation.") from error


@router.get("", response_model=list[ConversationSummary], summary="List conversations for current user")
def list_conversations(
    limit: int = 50,
    offset: int = 0,
    user: UserRecord = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> list[ConversationSummary]:
    try:
        records = service.list_conversations(user.id, limit=limit, offset=offset)
        import dataclasses
        return [ConversationSummary(**dataclasses.asdict(record)) for record in records]
    except Exception as error:
        raise AppError(500, "conversation_list_failed", "Failed to retrieve conversations.") from error


@router.get("/{conversation_id}", response_model=ConversationDetail, summary="Get conversation details and messages")
def get_conversation(
    conversation_id: str,
    user: UserRecord = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ConversationDetail:
    try:
        record = service.get_conversation_for_user(conversation_id, user.id)
        messages = service.get_messages(conversation_id, user.id, limit=100)
        import dataclasses
        return ConversationDetail(
            **dataclasses.asdict(record),
            messages=[MessageResponse(**dataclasses.asdict(msg)) for msg in messages],
        )
    except ChatServiceError as error:
        raise AppError(404, "conversation_not_found", str(error)) from error
    except Exception as error:
        raise AppError(500, "conversation_load_failed", "Failed to load conversation.") from error


@router.patch("/{conversation_id}", response_model=ConversationSummary, summary="Rename a conversation")
def rename_conversation(
    conversation_id: str,
    request: ConversationRenameRequest,
    user: UserRecord = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ConversationSummary:
    try:
        record = service.rename_conversation(conversation_id, user.id, request.title)
        import dataclasses
        return ConversationSummary(**dataclasses.asdict(record))
    except ChatServiceError as error:
        raise AppError(404, "conversation_not_found", str(error)) from error
    except Exception as error:
        raise AppError(500, "conversation_rename_failed", "Failed to rename conversation.") from error


@router.delete("/{conversation_id}", summary="Delete a conversation")
def delete_conversation(
    conversation_id: str,
    user: UserRecord = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict[str, str]:
    try:
        service.delete_conversation(conversation_id, user.id)
        return {"status": "success"}
    except ChatServiceError as error:
        raise AppError(404, "conversation_not_found", str(error)) from error
    except Exception as error:
        raise AppError(500, "conversation_delete_failed", "Failed to delete conversation.") from error


@router.post("/{conversation_id}/messages", response_model=MessageResponse, summary="Send a question and get an answer")
def send_message(
    conversation_id: str,
    request: MessageCreateRequest,
    user: UserRecord = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    ai_service: AIOrchestrationService = Depends(get_ai_service),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> MessageResponse:
    try:
        # Verify ownership of conversation
        conversation = chat_service.get_conversation_for_user(conversation_id, user.id)
        dataset_id = request.dataset_id or conversation.dataset_id
        if not dataset_id:
            raise AppError(400, "missing_dataset", "A dataset ID is required for analytics.")

        monitoring_service.track_event(user.id, "message_sent", {"conversation_id": conversation_id, "dataset_id": dataset_id})

        # If it's the first message and title is default, generate title (simple rule)
        if conversation.title == "New Conversation":
            chat_service.rename_conversation(conversation_id, user.id, request.question[:50])

        # Save user message
        chat_service.add_message(
            conversation_id=conversation_id,
            user_id=user.id,
            role="user",
            message_type="question",
            content=request.question,
            dataset_id=dataset_id,
        )

        # Run analytics
        analysis_response = ai_service.analyze(request.question, dataset_id=dataset_id, user_id=user.id)
        
        # Format chart for response
        if analysis_response.chart and analysis_response.chart.get("file_path"):
            chart = dict(analysis_response.chart)
            file_name = str(chart.pop("file_path")).replace("\\", "/").rsplit("/", 1)[-1]
            chart["file_url"] = f"/api/v1/visualizations/files/{file_name}"
            analysis_response = analysis_response.model_copy(update={"chart": chart})

        # Convert AIAnalysisResponse to metadata dictionary
        result_metadata = {
            "metrics": analysis_response.metrics,
            "chart": analysis_response.chart,
            "insights": analysis_response.insights,
            "recommendations": analysis_response.recommendations,
            "warnings": analysis_response.warnings,
            "analysis": analysis_response.analysis,
        }

        # Save assistant message
        assistant_message = chat_service.add_message(
            conversation_id=conversation_id,
            user_id=user.id,
            role="assistant",
            message_type="answer",
            content=analysis_response.answer,
            dataset_id=dataset_id,
            result_metadata=result_metadata,
        )

        import dataclasses
        return MessageResponse(**dataclasses.asdict(assistant_message))

    except ChatServiceError as error:
        raise AppError(404, "conversation_not_found", str(error)) from error
    except Exception as error:
        # If AI fails, record an error message in chat history?
        # Actually it's better to just let it raise so frontend knows it failed, 
        # but we could also store the error in history if we wanted.
        raise _handle_ai_error(error) from error
