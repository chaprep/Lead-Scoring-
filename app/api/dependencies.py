import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_internal_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Guard PII-bearing endpoints with a server-configured API key."""
    configured_key = get_settings().internal_api_key
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal contact access is not configured.",
        )
    if x_api_key is None or not hmac.compare_digest(x_api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key.",
        )
