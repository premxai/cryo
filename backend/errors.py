"""Typed API errors rendered as {"error": {type, message, request_id}} by a global handler."""


class APIError(Exception):
    """Raise anywhere in a /v1 request to return a structured JSON error.

    Handled by the api_error_handler registered in backend/main.py.
    """

    def __init__(
        self,
        status_code: int,
        error_type: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        self.headers = headers or {}
        super().__init__(message)
