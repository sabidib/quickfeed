import secrets

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.base import (BaseHTTPMiddleware,
                                       RequestResponseEndpoint)


class AuthMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, username: str, password: str, security: HTTPBasic = HTTPBasic()) -> None:
        self.__username = username
        self.__password = password
        self.__security = security
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Extract credentials
        try:
            credentials: HTTPBasicCredentials = await self.__security(request)
        except HTTPException:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Basic"},
            )

        # Check credentials
        if not self.authenticate(credentials):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid authentication credentials"},
                headers={"WWW-Authenticate": "Basic"},
            )

        # Proceed to endpoint
        response = await call_next(request)
        return response

    def authenticate(self, credentials: HTTPBasicCredentials) -> bool:
        is_correct_username = secrets.compare_digest(credentials.username, self.__username)
        is_correct_password = secrets.compare_digest(credentials.password, self.__password)

        return is_correct_username and is_correct_password
