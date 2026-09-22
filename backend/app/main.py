import uuid
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.errors import AppError
from app.llm import OpenAIClient
from app.models import RecruiterFeedback, SearchSpec
from app.profiles import load_profiles
from app.service import SearchService

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Sourcing Refinement Loop")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

service = SearchService(load_profiles(), OpenAIClient())


class CreateBody(BaseModel):
    query: str


class RefineBody(BaseModel):
    message: str = ""
    feedback: list[RecruiterFeedback] = Field(default_factory=list)


def _force(request: Request) -> str | None:
    value = request.headers.get("x-force-failure", "").strip().lower()
    if value in {"timeout", "malformed"}:
        return value
    return None


def _error_body(request: Request, code: str, message: str, retryable: bool) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "request_id": getattr(request.state, "request_id", ""),
        }
    }


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = f"req_{uuid.uuid4().hex[:8]}"
    return await call_next(request)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status, content=_error_body(request, exc.code, exc.message, exc.retryable))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, _exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_error_body(request, "INVALID_REQUEST", "The filters or rubric could not be read.", False),
    )


@app.get("/api/health")
def health() -> dict[str, Literal["ok"]]:
    return {"status": "ok"}


@app.post("/api/search-sessions")
async def create_session(body: CreateBody, request: Request):
    return await service.create(body.query, _force(request))


@app.get("/api/search-sessions/{session_id}")
def get_session(session_id: str):
    return service.get(session_id)


@app.patch("/api/search-sessions/{session_id}/spec")
async def edit_spec(session_id: str, body: SearchSpec, request: Request):
    return await service.edit(session_id, body, _force(request))


@app.post("/api/search-sessions/{session_id}/refine")
async def refine_session(session_id: str, body: RefineBody, request: Request):
    return await service.refine(session_id, body.message, body.feedback, _force(request))


@app.post("/api/search-sessions/{session_id}/freeze")
def freeze_session(session_id: str):
    return service.freeze(session_id)


@app.post("/api/search-sessions/{session_id}/retry")
async def retry_session(session_id: str, request: Request):
    return await service.retry(session_id, _force(request))
