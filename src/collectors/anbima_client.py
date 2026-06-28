from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logger import get_logger

logger = get_logger(__name__)


class AnbimaClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
        environment: str | None = None,
        enabled: str | bool | None = None,
        timeout: int = 30,
    ) -> None:
        self.client_id = client_id if client_id is not None else os.getenv("ANBIMA_CLIENT_ID", "")
        self.client_secret = client_secret if client_secret is not None else os.getenv("ANBIMA_CLIENT_SECRET", "")
        self.access_token = access_token if access_token is not None else os.getenv("ANBIMA_ACCESS_TOKEN", "")
        self.environment = environment if environment is not None else os.getenv("ANBIMA_ENV", "sandbox")
        self.enabled = enabled if enabled is not None else os.getenv("ANBIMA_ENABLE", "false")
        self.timeout = timeout

    def is_enabled(self) -> bool:
        return str(self.enabled).strip().lower() in {"1", "true", "yes", "sim"}

    def has_credentials(self) -> bool:
        return bool(self.access_token or (self.client_id and self.client_secret))

    def get_access_token(self) -> dict[str, Any]:
        if not self.is_enabled():
            return {"status": "SKIPPED", "reason": "ANBIMA_ENABLE=false"}
        if self.access_token:
            return {"status": "SUCCESS", "access_token": self.access_token}
        if not self.client_id or not self.client_secret:
            return {"status": "SKIPPED", "reason": "Credenciais ANBIMA ausentes"}
        return {"status": "SKIPPED", "reason": "Fluxo de token preparado; endpoint deve ser configurado conforme contrato ANBIMA."}

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token_result = self.get_access_token()
        if token_result.get("status") != "SUCCESS":
            return token_result

        headers = {"Authorization": f"Bearer {token_result['access_token']}"}
        try:
            response = requests.get(endpoint, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return {"status": "SUCCESS", "data": response.json()}
        except requests.RequestException as exc:
            logger.warning("Falha em chamada ANBIMA: %s", exc)
            return {"status": "ERROR", "error": str(exc)}
