"""Cliente HTTP para TheStatsAPI (fútbol).

Documentación base: https://api.thestatsapi.com/api
Autenticación: header  Authorization: Bearer <THESTATSAPI_KEY>
"""
from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)


class TheStatsAPIError(Exception):
    """Error de comunicación con TheStatsAPI."""


class TheStatsAPIClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 30,
                 max_retries: int = 3, sleep_between_requests: float = 1.5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep_between_requests
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        })

    # ------------------------------------------------------------------ core
    def _get(self, endpoint: str, params: dict | None = None):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 429:  # límite de peticiones
                    wait = self.sleep * attempt * 2
                    logger.warning("Rate limit alcanzado. Esperando %.1fs...", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                time.sleep(self.sleep)
                return resp.json()
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("Intento %d/%d falló para %s: %s",
                               attempt, self.max_retries, endpoint, exc)
                time.sleep(self.sleep * attempt)
        raise TheStatsAPIError(f"No se pudo completar la petición a {endpoint}: {last_error}")

    @staticmethod
    def _unwrap(payload):
        """La API suele envolver los resultados en la clave 'data'."""
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def get_paginated(self, endpoint: str, params: dict | None = None):
        """Recorre todas las páginas si la respuesta viene paginada."""
        params = dict(params or {})
        params.setdefault("page", 1)
        items: list = []
        while True:
            payload = self._get(endpoint, params)
            data = self._unwrap(payload)
            if not isinstance(data, list):
                return data
            items.extend(data)
            meta = payload.get("meta") if isinstance(payload, dict) else None
            last_page = (meta or {}).get("last_page") or (meta or {}).get("total_pages")
            if not last_page or params["page"] >= last_page:
                return items
            params["page"] += 1

    # ------------------------------------------------------------- endpoints
    def list_competitions(self):
        return self.get_paginated("football/competitions")

    def list_teams(self, **params):
        return self.get_paginated("football/teams", params)

    def get_team(self, team_id):
        return self._unwrap(self._get(f"football/teams/{team_id}"))

    def get_team_stats(self, team_id, **params):
        return self._unwrap(self._get(f"football/teams/{team_id}/stats", params))

    def get_team_standings(self, team_id):
        return self._unwrap(self._get(f"football/teams/{team_id}/standings"))

    def list_matches(self, **params):
        return self.get_paginated("football/matches", params)
