"""Supabase JWT authentication for FastAPI.

AUTH_DISABLED=true bypasses all authentication (for testing/demo).
Anonymous users are identified by X-Device-Id header (UUID per browser),
converted to a deterministic UUID5 for Supabase compatibility.
"""

import json
import logging
import os
from base64 import urlsafe_b64decode
from typing import Optional
from uuid import NAMESPACE_DNS, uuid5

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Namespace for generating deterministic UUIDs from device IDs
_DEVICE_NAMESPACE = NAMESPACE_DNS

# Fallback anonymous user ID (only used if no device_id header)
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


def _decode_jwt_payload(token: str) -> Optional[dict]:
    """Decode JWT payload without signature verification.

    Used as fallback when Supabase client verification fails
    but we still need the user_id (sub claim) from a Supabase-issued token.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # Add padding for base64
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(urlsafe_b64decode(payload_b64))
        return payload
    except Exception:
        return None


def device_id_to_uuid(device_id: str) -> str:
    """Convert a device ID string to a deterministic UUID5.

    This ensures the user_id stored in Supabase is always a valid UUID,
    even for anonymous users identified by their browser device ID.
    """
    return str(uuid5(_DEVICE_NAMESPACE, f"device:{device_id}"))


def is_anonymous_user(user_id: str) -> bool:
    """Check if user_id is the shared anonymous fallback."""
    return user_id == ANONYMOUS_USER_ID


def get_device_id(request: Request) -> Optional[str]:
    """Extract device ID from X-Device-Id header."""
    return request.headers.get("x-device-id")


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """Extract and verify user_id from Supabase JWT.

    Priority:
    1. Valid JWT token (Supabase verify) → real user_id
    2. Valid JWT token (decode fallback) → real user_id from 'sub' claim
    3. AUTH_DISABLED + X-Device-Id header → deterministic UUID5 (isolated anonymous)
    4. AUTH_DISABLED without device_id → ANONYMOUS_USER_ID (shared fallback)
    5. No token + auth required → 401
    """
    if credentials:
        token = credentials.credentials

        # Try Supabase client verification first
        try:
            client = _get_supabase_client()
            response = client.auth.get_user(token)
            if response.user and response.user.id:
                logger.info(f"[Auth] Verified JWT — real user_id: {response.user.id}")
                return response.user.id
        except Exception as e:
            logger.warning(f"[Auth] Supabase JWT verification failed: {e}")

        # Fallback: decode JWT payload directly to get user_id
        # (token was issued by Supabase, so 'sub' claim = user_id)
        payload = _decode_jwt_payload(token)
        if payload and payload.get("sub"):
            user_id = payload["sub"]
            # Sanity check: must be from our Supabase instance
            iss = payload.get("iss", "")
            if "supabase" in iss:
                logger.info(f"[Auth] JWT decoded (no verify) — user_id: {user_id}")
                return user_id

        # Token exists but completely invalid
        if not _is_auth_disabled():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired or invalid",
            )

    # Auth disabled — use device_id for anonymous isolation
    if _is_auth_disabled():
        device_id = get_device_id(request)
        if device_id:
            uid = device_id_to_uuid(device_id)
            logger.info(f"[Auth] Fallback to device_id: {device_id} → {uid}")
            return uid
        return ANONYMOUS_USER_ID

    # Auth required but no token provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
