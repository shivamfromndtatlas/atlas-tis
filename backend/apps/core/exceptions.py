"""Consistent error envelope: {"error": {"code", "message", "details"}}."""

from rest_framework import exceptions
from rest_framework.views import exception_handler


def envelope_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, exceptions.ValidationError):
        code, message, details = "VALIDATION_ERROR", "Some fields are invalid.", response.data
    elif isinstance(exc, exceptions.APIException):
        detail = exc.detail
        code = getattr(exc, "error_code", None) or (
            exc.get_codes() if isinstance(exc.get_codes(), str) else exc.default_code
        )
        message = str(detail) if not isinstance(detail, dict | list) else exc.default_detail
        details = detail if isinstance(detail, dict | list) else None
    else:  # pragma: no cover
        code, message, details = "ERROR", "Unexpected error.", None

    response.data = {"error": {"code": str(code).upper(), "message": str(message), "details": details}}
    return response


def error_response(code: str, message: str, status_code: int = 400):
    """Return (not raise) an error.

    Raising inside a request with ATOMIC_REQUESTS rolls the transaction back, which would also undo
    side effects that must persist on failure (failed-login audit rows, OTP attempt counters).
    """
    from rest_framework.response import Response

    return Response({"error": {"code": code, "message": message, "details": None}}, status=status_code)


class TISError(exceptions.APIException):
    status_code = 400
    default_detail = "Request could not be processed."
    default_code = "bad_request"

    def __init__(self, message: str | None = None, code: str | None = None, status_code: int | None = None):
        super().__init__(message or self.default_detail)
        if code:
            self.error_code = code
        if status_code:
            self.status_code = status_code
