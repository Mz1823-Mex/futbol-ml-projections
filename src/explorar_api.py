"""Explora TheStatsAPI y guarda catálogos para configurar el proyecto.

Ejecuta el workflow '0. Explorar API' desde GitHub para generar:
  - data/raw/competitions.json   (IDs de competiciones disponibles)
  - data/raw/teams_sample.json   (muestra de equipos con sus IDs)
  - data/raw/matches_sample.json (muestra de partidos, para revisar campos)

Con esos archivos puedes completar 'competitions.ids' o 'teams.ids'
en config/settings.yaml directamente desde el navegador del móvil.
"""
from __future__ import annotations

import json
import logging

from .api_client import TheStatsAPIClient
from .config import get_api_key, load_settings, resolve_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def _save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Guardado %s", path)


def main() -> None:
    settings = load_settings()
    client = TheStatsAPIClient(
        base_url=settings["api"]["base_url"],
        api_key=get_api_key(),
        timeout=settings["api"].get("timeout", 30),
        max_retries=settings["api"].get("max_retries", 3),
        sleep_between_requests=settings["api"].get("sleep_between_requests", 1.5),
    )
    raw_dir = resolve_path(settings, "raw")

    competitions = client.list_competitions()
    _save_json(competitions, raw_dir / "competitions.json")
    if isinstance(competitions, list):
        logger.info("Competiciones disponibles: %d", len(competitions))
        for comp in competitions[:25]:
            if isinstance(comp, dict):
                logger.info("  id=%s | %s", comp.get("id"), comp.get("name"))

    teams = client.list_teams(per_page=100)
    _save_json(teams, raw_dir / "teams_sample.json")
    if isinstance(teams, list):
        logger.info("Equipos en muestra: %d", len(teams))
        for team in teams[:15]:
            if isinstance(team, dict):
                logger.info("  id=%s | %s", team.get("id"), team.get("name"))
        first = next((t for t in teams if isinstance(t, dict) and t.get("id")), None)
        if first:
            matches = client.list_matches(team_id=first["id"], per_page=5)
            _save_json(matches, raw_dir / "matches_sample.json")

    logger.info("Listo. Revisa los archivos en data/raw/ para elegir tus IDs.")


if __name__ == "__main__":
    main()
