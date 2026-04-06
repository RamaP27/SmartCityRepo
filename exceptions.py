from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class SHEMSException(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundException(SHEMSException):
    def __init__(self, resource: str, identifier: str = ""):
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(detail, status.HTTP_404_NOT_FOUND)


class AlreadyExistsException(SHEMSException):
    def __init__(self, resource: str, field: str = ""):
        detail = f"{resource} already exists"
        if field:
            detail = f"{resource} with this {field} already exists"
        super().__init__(detail, status.HTTP_409_CONFLICT)


class UnauthorizedException(SHEMSException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenException(SHEMSException):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


async def shems_exception_handler(request: Request, exc: SHEMSException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
