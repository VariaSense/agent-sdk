"""Encryption helpers for data-at-rest."""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet


def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")


def encrypt_json(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    payload = json.dumps(data).encode("utf-8")
    token = Fernet(key.encode("utf-8")).encrypt(payload)
    return {"__encrypted__": True, "data": base64.b64encode(token).decode("utf-8")}


def decrypt_json(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    if not isinstance(data, dict) or not data.get("__encrypted__"):
        return data
    token = base64.b64decode(data.get("data", ""))
    decrypted = Fernet(key.encode("utf-8")).decrypt(token)
    return json.loads(decrypted.decode("utf-8"))


def maybe_encrypt(data: Dict[str, Any], key: Optional[str]) -> Dict[str, Any]:
    if not key:
        return data
    return encrypt_json(data, key)


def maybe_decrypt(data: Dict[str, Any], key: Optional[str]) -> Dict[str, Any]:
    if not key:
        return data
    return decrypt_json(data, key)
