"""Shared production-mode and secret-key validation helpers."""
from __future__ import annotations

import os
import secrets
import warnings


def is_production() -> bool:
    return (
        os.getenv("APP_ENV", "").lower() == "production"
        or os.getenv("FLASK_ENV", "").lower() == "production"
    )


def secret_key_from_env(variable_name: str) -> str:
    """Require deployment secrets; generate only ephemeral development secrets."""
    configured = os.getenv(variable_name, "")
    if configured:
        if len(configured) < 32 or len(set(configured)) < 12:
            raise RuntimeError(
                f"{variable_name} must be a high-entropy random value of at least 32 "
                "characters. Generate it with Python secrets; do not use a phrase or repeated characters."
            )
        return configured

    if is_production():
        raise RuntimeError(
            f"{variable_name} is required in production. Configure it in the "
            "hosting environment before starting the application."
        )

    warnings.warn(
        f"{variable_name} is unset; using an ephemeral development-only key. "
        "Set a stable random value in your local environment for persistent sessions.",
        RuntimeWarning,
        stacklevel=2,
    )
    return secrets.token_urlsafe(48)


def rate_limit_storage_uri() -> str:
    """Use a shared limiter backend in production, in-memory storage for local dev.

    In-memory counters are per process and are not sufficient for multi-worker hosting.
    Configure RATELIMIT_STORAGE_URI to the private Redis-compatible URL supplied by your hosting provider.
    """
    configured = os.getenv("RATELIMIT_STORAGE_URI") or os.getenv("REDIS_URL")
    if configured:
        return configured
    if is_production():
        raise RuntimeError(
            "RATELIMIT_STORAGE_URI is required in production. Configure a private Redis-"
            "compatible connection so rate limits are shared across WSGI workers."
        )
    return "memory://"
