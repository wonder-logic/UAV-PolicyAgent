from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    error_code = "domain_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    status_code = 422
    error_code = "validation_error"


class NotFoundError(DomainError):
    status_code = 404
    error_code = "not_found"


class ForbiddenError(DomainError):
    status_code = 403
    error_code = "forbidden"


class ConflictError(DomainError):
    status_code = 409
    error_code = "conflict"


class ExternalServiceError(DomainError):
    status_code = 503
    error_code = "external_service_error"
