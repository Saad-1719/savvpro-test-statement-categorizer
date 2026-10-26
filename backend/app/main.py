"""FastAPI entry point. Routes stay thin; logic lives in ingest, brain, services and reports."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.routes import router
from app.config import settings
from app.errors import ServiceError
from app.ingest.parser import IngestError
from app.rules.loader import default_rules

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")

rules = default_rules()  # fail fast at startup on a bad rule file
logger.info("loaded %d rules and %d categories", rules.rule_count, len(rules.categories))

app = FastAPI(title="Driver Statement Categorizer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def error_response(status: int, code: str, message: str, details: dict | None = None):
    """Every error has the same shape: {"error": {"code", "message", "details"}}."""
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


@app.exception_handler(ServiceError)
async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
    logger.info("request refused: %s", exc.code)
    return error_response(exc.status, exc.code, exc.message, exc.details)


@app.exception_handler(IngestError)
async def ingest_error(_: Request, exc: IngestError) -> JSONResponse:
    logger.info("file refused: %s", exc.code)
    return error_response(422, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return error_response(422, "invalid_request", "The request is not valid.", {"errors": errors})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return error_response(exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """A bug: log the full traceback, but never send it to the browser."""
    logger.exception("unexpected error on %s %s", request.method, request.url.path)
    return error_response(500, "internal_error", "Something went wrong on our side.")


app.include_router(router)
