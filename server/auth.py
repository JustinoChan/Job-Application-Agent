from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, Request, status


def _allowed_emails() -> set[str]:
    raw = os.getenv("CLOUDFLARE_ACCESS_ALLOWED_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _check_bearer(auth_header: str) -> bool:
    token = os.getenv("API_TOKEN")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_TOKEN is required when AUTH_MODE includes token auth.",
        )
    if not auth_header.startswith("Bearer "):
        return False
    return secrets.compare_digest(auth_header[7:], token)


def _check_cloudflare_access(email: str | None) -> bool:
    if not email:
        return False
    allowed = _allowed_emails()
    return not allowed or email.lower() in allowed


async def verify_request(
    request: Request,
    authorization: str = Header(default=""),
    cf_access_authenticated_user_email: str | None = Header(
        default=None,
        alias="Cf-Access-Authenticated-User-Email",
    ),
) -> None:
    mode = os.getenv("AUTH_MODE", "token").lower()
    if mode == "none":
        return

    token_ok = mode in {"token", "token_or_access"} and _check_bearer(authorization)
    access_ok = mode in {"cloudflare_access", "token_or_access"} and _check_cloudflare_access(
        cf_access_authenticated_user_email
    )

    if not (token_ok or access_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
