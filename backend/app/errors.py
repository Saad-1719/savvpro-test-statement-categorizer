"""The error type the API turns into {"error": {"code", "message", "details"}}."""


class ServiceError(Exception):
    """`code` is for programs, `message` is for the user, `status` is the HTTP status."""

    def __init__(self, code: str, message: str, status: int = 422, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}
