"""DD1 public beta icin basit sunucu-tarafi anahtar kontrolleri."""
from __future__ import annotations

import os
import secrets

from fastapi import HTTPException


def _matches_env_key(candidate: str | None, env_name: str) -> bool:
    expected = os.environ.get(env_name, "").strip()
    supplied = (candidate or "").strip()
    return bool(expected and supplied and secrets.compare_digest(supplied, expected))


def require_admin_key(candidate: str | None) -> None:
    if not os.environ.get("DD1_ADMIN_KEY", "").strip():
        raise HTTPException(503, detail="Yonetim erisimi henuz yapilandirilmadi.")
    if not _matches_env_key(candidate, "DD1_ADMIN_KEY"):
        raise HTTPException(403, detail="Yonetim yetkisi gerekli.")


def has_premium_key(candidate: str | None) -> bool:
    return _matches_env_key(candidate, "DD1_PREMIUM_KEY")
