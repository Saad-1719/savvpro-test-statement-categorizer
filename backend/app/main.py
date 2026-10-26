"""FastAPI entry point. Routes stay thin; logic lives in ingest, brain and reports."""

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.routes import router
from app.ingest.parser import IngestError
from app.rules.loader import default_rules
from app.services import ServiceError

default_rules()  # fail fast at startup on a bad rule file

app = FastAPI(title="Driver Statement Categorizer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def _error(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


@app.exception_handler(ServiceError)
async def _service_error(_: Request, exc: ServiceError) -> JSONResponse:
    return _error(exc.status, exc.code, exc.message, exc.details)


@app.exception_handler(IngestError)
async def _ingest_error(_: Request, exc: IngestError) -> JSONResponse:
    return _error(422, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return _error(422, "invalid_request", "The request is not valid.", {"errors": errors})


@app.exception_handler(HTTPException)
async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return _error(exc.status_code, "http_error", str(exc.detail))


app.include_router(router)
