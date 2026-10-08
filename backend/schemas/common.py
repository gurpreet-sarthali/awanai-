from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(APIModel):
    status: str
    service: str


class DatabaseHealthResponse(APIModel):
    status: str
    database: str


class ErrorResponse(APIModel):
    error: str
    detail: str