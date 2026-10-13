from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from analytics.database import ConfigurationError
from backend.ai.nlsql.query_manager import QueryManager
from backend.core.config import settings
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.repositories.billing_repository import BillingRepository
from backend.repositories.automation_repository import AutomationRepository
from backend.repositories.developer_repository import DeveloperRepository
from backend.repositories.database_repository import DatabaseRepository
from backend.repositories.dataset_registry_repository import DatasetRegistryRepository
from backend.repositories.monitoring_repository import MonitoringRepository
from backend.repositories.search_repository import SearchRepository
from backend.repositories.user_repository import UserRepository
from backend.services.ai_orchestration_service import AIOrchestrationService
from backend.services.analytics_service import AnalyticsService
from backend.services.automation_service import AutomationService
from backend.services.auth_service import AuthenticationError, AuthService
from backend.services.billing_service import BillingService
from backend.services.dataset_access_service import DatasetAccessService
from backend.services.dataset_import_service import DatasetImportService
from backend.services.dataset_management_service import DatasetManagementService
from backend.services.developer_service import DeveloperAPIContext, DeveloperAPIError, DeveloperAPIService, WebhookService
from backend.services.dataset_service import DatasetService
from backend.services.gemini_service import GeminiService
from backend.services.monitoring_service import MonitoringService
from backend.services.rate_limiter import AIRateLimiter
from backend.services.search_service import SearchService
from backend.services.visualization_service import VisualizationService

_bearer = HTTPBearer(auto_error=False)
_registry: DatasetRegistryRepository | None = None
_users: UserRepository | None = None
_auth_service: AuthService | None = None
_monitoring_service: MonitoringService | None = None
_billing_service: BillingService | None = None
_automation_service: AutomationService | None = None
_developer_repository: DeveloperRepository | None = None
_developer_api_service: DeveloperAPIService | None = None
_webhook_service: WebhookService | None = None
_search_repository: SearchRepository | None = None
_search_service: SearchService | None = None


def reset_dependency_singletons() -> None:
    global _registry, _users, _auth_service, _monitoring_service, _billing_service
    global _automation_service, _developer_repository, _developer_api_service
    global _webhook_service, _search_repository, _search_service, _workspace_repository, _chat_repository
    _registry = None
    _users = None
    _auth_service = None
    _monitoring_service = None
    _billing_service = None
    _automation_service = None
    _developer_repository = None
    _developer_api_service = None
    _webhook_service = None
    _search_repository = None
    _search_service = None
    _workspace_repository = None
    _chat_repository = None


def get_user_repository() -> UserRepository:
    global _users
    if _users is None:
        config = settings.database_config()
        users = UserRepository(config)
        users.ensure_schema()
        _users = users
    return _users


def get_registry() -> DatasetRegistryRepository:
    global _registry
    if _registry is None:
        try:
            config = settings.database_config()
        except ConfigurationError as error:
            raise AppError(503, "database_configuration_missing", "Database configuration is unavailable.") from error
        users = get_user_repository()
        registry = DatasetRegistryRepository(config)
        try:
            registry.ensure_schema()
            users.migrate_dataset_ownership()
        except Exception as error:
            logger.error("Dataset registry initialization error: %s", error, exc_info=True)
            raise AppError(503, "dataset_registry_unavailable", "The dataset registry could not be initialized.") from error
        _registry = registry
    return _registry


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(get_user_repository())
    return _auth_service


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    authorization: Annotated[str | None, Header()] = None,
    service: AuthService = Depends(get_auth_service),
) -> UserRecord:
    token = credentials.credentials if credentials else None
    if token is None and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AppError(401, "authentication_required", "Authentication is required.")
    try:
        return service.resolve_token(token)
    except AuthenticationError as error:
        raise AppError(401, "authentication_failed", str(error)) from error


def require_admin_user(current_user: UserRecord = Depends(get_current_user)) -> UserRecord:
    """Dependency enforcing that the requesting user has administrative privileges."""
    if not current_user.is_admin and current_user.email.lower() not in settings.admin_emails:
        raise AppError(403, "forbidden_access", "Admin privileges are required to access this resource.")
    return current_user


def get_monitoring_service() -> MonitoringService:
    global _monitoring_service
    if _monitoring_service is None:
        try:
            config = settings.database_config()
        except ConfigurationError:
            # Fallback in environments without live DB
            from analytics.database import DatabaseConfig
            config = DatabaseConfig.from_environment()
        repo = MonitoringRepository(config)
        repo.ensure_schema()
        _monitoring_service = MonitoringService(repo)
    return _monitoring_service


def get_billing_service() -> BillingService:
    global _billing_service
    if _billing_service is None:
        try:
            config = settings.database_config()
        except ConfigurationError:
            from analytics.database import DatabaseConfig
            config = DatabaseConfig.from_environment()
        repo = BillingRepository(config)
        repo.ensure_schema()
        _billing_service = BillingService(repo)
        _billing_service.ensure_default_plans()
    return _billing_service


def get_automation_service() -> AutomationService:
    global _automation_service
    if _automation_service is None:
        config = settings.database_config()
        repository = AutomationRepository(config)
        repository.ensure_schema()
        _automation_service = AutomationService(
            repository=repository,
            registry=get_registry(),
            users=get_user_repository(),
            workspaces=get_workspace_repository(),
            billing=get_billing_service(),
            config=config,
        )
    return _automation_service


def get_developer_repository() -> DeveloperRepository:
    global _developer_repository
    if _developer_repository is None:
        repository = DeveloperRepository(settings.database_config())
        repository.ensure_schema()
        _developer_repository = repository
    return _developer_repository


def get_developer_api_service() -> DeveloperAPIService:
    global _developer_api_service
    if _developer_api_service is None:
        _developer_api_service = DeveloperAPIService(
            repository=get_developer_repository(),
            users=get_user_repository(),
            workspaces=get_workspace_repository(),
            billing=get_billing_service(),
        )
    return _developer_api_service


def get_webhook_service() -> WebhookService:
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService(get_developer_repository(), get_workspace_repository())
    return _webhook_service


def get_search_repository() -> SearchRepository:
    global _search_repository
    if _search_repository is None:
        repository = SearchRepository(settings.database_config())
        repository.ensure_schema()
        _search_repository = repository
    return _search_repository


def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        automation_repository = AutomationRepository(settings.database_config())
        automation_repository.ensure_schema()
        _search_service = SearchService(
            repository=get_search_repository(),
            registry=get_registry(),
            workspaces=get_workspace_repository(),
            chat=get_chat_repository(),
            automation=automation_repository,
        )
    return _search_service


def get_public_api_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    service: DeveloperAPIService = Depends(get_developer_api_service),
) -> DeveloperAPIContext:
    request.state.developer_api_key_id = None
    request.state.developer_api_service = service
    if credentials is None:
        raise AppError(401, "INVALID_API_KEY", "A developer API key is required.")
    try:
        return service.authenticate(request, credentials.credentials)
    except DeveloperAPIError as error:
        raise AppError(error.status_code, error.code, error.message) from error


_workspace_repository: WorkspaceRepository | None = None


def get_workspace_repository() -> WorkspaceRepository:
    global _workspace_repository
    if _workspace_repository is None:
        try:
            config = settings.database_config()
        except ConfigurationError:
            from analytics.database import DatabaseConfig
            config = DatabaseConfig.from_environment()
        from backend.repositories.workspace_repository import WorkspaceRepository
        repo = WorkspaceRepository(config)
        repo.ensure_schema()
        _workspace_repository = repo
    return _workspace_repository


def get_workspace_service(repo: WorkspaceRepository = Depends(get_workspace_repository)) -> WorkspaceService:
    from backend.services.workspace_service import WorkspaceService
    return WorkspaceService(repo)


def get_dataset_access(
    user: UserRecord = Depends(get_current_user),
    registry: DatasetRegistryRepository = Depends(get_registry),
    ws_repo: WorkspaceRepository = Depends(get_workspace_repository),
) -> DatasetAccessService:
    return DatasetAccessService(registry, user, workspace_repo=ws_repo)


def get_repository(user: UserRecord = Depends(get_current_user)) -> DatabaseRepository:
    try:
        config = settings.database_config()
    except ConfigurationError as error:
        raise AppError(503, "database_configuration_missing", "Database configuration is unavailable.") from error
    try:
        registry = get_registry()
    except AppError:
        registry = None
    return DatabaseRepository(config, registry=registry, user_id=user.id)


def get_dataset_service(repository: DatabaseRepository = Depends(get_repository)) -> DatasetService:
    return DatasetService(repository)


def get_dataset_management_service(
    access: DatasetAccessService = Depends(get_dataset_access),
    registry: DatasetRegistryRepository = Depends(get_registry),
) -> DatasetManagementService:
    uploads_root = Path(__file__).resolve().parents[2] / settings.dataset_uploads_dir
    return DatasetManagementService(registry, DatasetImportService(registry.config), uploads_root, access)


def get_analytics_service(repository: DatabaseRepository = Depends(get_repository)) -> AnalyticsService:
    return AnalyticsService(repository)


def get_visualization_service(analytics_service: AnalyticsService = Depends(get_analytics_service)) -> VisualizationService:
    output_dir = Path(__file__).resolve().parents[2] / "visualization" / "results"
    return VisualizationService(analytics_service, output_dir)


_ai_rate_limiter = AIRateLimiter(settings.ai_max_requests_per_minute, settings.ai_max_requests_per_day)


def get_ai_service(
    repository: DatabaseRepository = Depends(get_repository),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    access: DatasetAccessService = Depends(get_dataset_access),
) -> AIOrchestrationService:
    return AIOrchestrationService(
        repository=repository,
        analytics_service=analytics_service,
        visualization_service=VisualizationService(analytics_service, Path(__file__).resolve().parents[2] / "visualization" / "results"),
        gemini_service=GeminiService(model=settings.gemini_model),
        rate_limiter=_ai_rate_limiter,
        dataset_access=access,
    )


def build_ai_service_for_user(user: UserRecord, registry: DatasetRegistryRepository | None = None, ws_repo: WorkspaceRepository | None = None) -> AIOrchestrationService:
    active_registry = registry or get_registry()
    active_workspace_repo = ws_repo or get_workspace_repository()
    repository = DatabaseRepository(active_registry.config, registry=active_registry)
    analytics_service = AnalyticsService(repository)
    return AIOrchestrationService(
        repository=repository,
        analytics_service=analytics_service,
        visualization_service=VisualizationService(analytics_service, Path(__file__).resolve().parents[2] / "visualization" / "results"),
        gemini_service=GeminiService(model=settings.gemini_model),
        rate_limiter=_ai_rate_limiter,
        dataset_access=DatasetAccessService(active_registry, user, workspace_repo=active_workspace_repo),
    )


def get_query_manager(repository: DatabaseRepository = Depends(get_repository), access: DatasetAccessService = Depends(get_dataset_access)) -> QueryManager:
    return QueryManager(repository, dataset_access=access)


_chat_repository: "backend.repositories.chat_repository.ChatRepository" | None = None

def get_chat_repository() -> "backend.repositories.chat_repository.ChatRepository":
    global _chat_repository
    if _chat_repository is None:
        try:
            config = settings.database_config()
        except ConfigurationError as error:
            raise AppError(503, "database_configuration_missing", "Database configuration is unavailable.") from error
        from backend.repositories.chat_repository import ChatRepository
        repo = ChatRepository(config)
        repo.ensure_schema()
        _chat_repository = repo
    return _chat_repository

def get_chat_service(repository: "backend.repositories.chat_repository.ChatRepository" = Depends(get_chat_repository)) -> "backend.services.chat_service.ChatService":
    from backend.services.chat_service import ChatService
    return ChatService(repository)
