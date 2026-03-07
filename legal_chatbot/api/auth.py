"""Supabase JWT authentication for FastAPI.

AUTH_DISABLED=true bypasses all authentication (for testing/demo).
"""

import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Anonymous user ID used when auth is disabled
ANONYMOUS_USER_ID = "00000000-0000-0000-0000-000000000000"

# Lazy-initialized Supabase client for auth verification
_supabase_client = None


def _is_auth_disabled() -> bool:
    """Check if authentication is disabled (for testing/demo)."""
    return os.getenv("AUTH_DISABLED", "").lower() in ("true", "1", "yes")


def _get_supabase_client():
    """Get Supabase client for token verification."""
    global _supabase_client
    if _supabase_client is None:
        supabase_url = os.getenv("SUPABASE_URL", "")
        anon_key = os.getenv("SUPABASE_KEY", "")
        if not supabase_url or not anon_key:
            try:
                from legal_chatbot.utils.config import get_settings
                settings = get_settings()
                supabase_url = supabase_url or settings.supabase_url or ""
                anon_key = anon_key or settings.supabase_key or ""
            except Exception:
                pass
        if not supabase_url or not anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY not configured")
        from supabase import create_client
        _supabase_client = create_client(supabase_url, anon_key)
    return _supabase_client


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """Extract and verify user_id from Supabase JWT.

    When AUTH_DISABLED=true, returns anonymous user ID without verification.
    Otherwise validates the token by calling Supabase Auth API (get_user).
    """
    # Bypass auth for testing/demo
    if _is_auth_disabled():
        # Still use real token if provided
        if credentials:
            try:
                client = _get_supabase_client()
                response = client.auth.get_user(credentials.credentials)
                if response.user and response.user.id:
                    return response.user.id
            except Exception:
                pass
        return ANONYMOUS_USER_ID

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        client = _get_supabase_client()
        response = client.auth.get_user(credentials.credentials)
        user = response.user
        if not user or not user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no user",
            )
        return user.id
    except HTTPException:
        raise
    except Exception as e:
        err_str = str(e).lower()
        if "expired" in err_str or "invalid" in err_str or "401" in err_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired or invalid",
            )
        logger.error(f"AUTH error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )
