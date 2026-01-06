from fastapi import Request, status
from fastapi.responses import JSONResponse
from domain.exceptions.domain_exceptions import (
    DomainException,
    NotFoundError,
    ValidationError,
    ConflictError,
    AuthorizationError,
)


EXCEPTION_STATUS_MAP = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_400_BAD_REQUEST,
    ConflictError: status.HTTP_409_CONFLICT,
    AuthorizationError: status.HTTP_403_FORBIDDEN,
}


async def domain_exception_handler(request: Request, exc: DomainException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    for exc_type, code in EXCEPTION_STATUS_MAP.items():
        if isinstance(exc, exc_type):
            status_code = code
            break

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


