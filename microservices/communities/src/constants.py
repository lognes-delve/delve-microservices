from fastapi.security import APIKeyHeader

X_USER_HEADER = APIKeyHeader(name="X-UserInfo")

__all__ = [
    X_USER_HEADER
]