from __future__ import annotations

from rest_framework.views import exception_handler


_STATUS_MESSAGES = {
    400: "The request could not be processed.",
    401: "Authentication is required or the supplied credentials are invalid.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found.",
    405: "The HTTP method is not allowed for this resource.",
    409: "The request conflicts with the current resource state.",
    429: "The request rate limit has been exceeded.",
}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    request = context.get("request")
    correlation_id = getattr(request, "correlation_id", None)
    default_code = getattr(exc, "default_code", exc.__class__.__name__)
    code = str(default_code).lower()
    response.data = {
        "error": {
            "code": code,
            "message": _STATUS_MESSAGES.get(
                response.status_code,
                "The operation failed.",
            ),
            "details": response.data,
            "correlation_id": correlation_id,
        }
    }
    return response
