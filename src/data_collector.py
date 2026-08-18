"""Recolector de datos de TheStatsAPI.

Descarga equipos, estadísticas de temporada, standings y partidos
(historial + próximos) y actualiza los archivos en data/raw/.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from .api_client import TheStatsAPIClient
from .config import ROOT_DIR, get_api_key, load_settings, resolve_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def _save_json(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Guardado %s", path.relative_to(ROOT_DIR))


def _first(record: dict, *keys):
    for key in keys:
        if isinstance(record, dict) and record.get(key) is not None:
            return record[key]
    return None


# ------------------------------------------------------------ normalización
def _norm_team_id(match: dict, side: str):
    team = match.get(f"{side}_team")
    if isinstance(team, dict):
        return match.get(f"{side}_team_id") or team.get("id")
    return match.get(f"{side}_team_id")


def _norm_team_name(match: dict, side: str):
    team = match.get(f"{side}_team")
    if isinstance(team, dict):
        return match.get(f"{side}_team_name") or team.get("name")
    return match.get(f"{side}_team_name")


def _norm_score(match: dict, side: str):
    direct = _first(match, f"{side}_goals", f"goals_{side}", f"{side}_score")
    if direct is not None:
        return direct
    score = match.get("score")
    if isinstance(score, dict):
        return _first(score, side, f"{side}_goals", f"{side}_score")
    return None


def _norm_stat(match: dict, side: str, stat: str):
    """stat: 'corners' o 'sot' (remates al arco / tiros a puerta)."""
    keys = {
        "corners": [f"{side}_corners", f"corners_{side}"],
        "sot": [f"{side}_shots_on_target", f"shots_on_target_{side}",
                f"{side}_sot", f"sot_{side}"],
    }[stat]
    direct = _first(match, *keys)
    if direct is not None:
        return direct
    stats = match.get("stats")
    if isinstance(stats, dict):
        side_stats = stats.get(side)
        if isinstance(side_stats, dict):
            return _first(side_stats, stat, "shots_on_target")
    return None


def normalize_match(match: dict) -> dict:
    return {
        "id": match.get("id") or match.get("match_id"),
        "date": _first(match, "date", "match_date", "kickoff", "start_time", "starting_at"),
        "status": _first(match, "status", "state"),
        "competition_id": _first(match, "competition_id", "league_id"),
        "home_id": _norm_team_id(match, "home"),
        "away_id": _norm_team_id(match, "away"),
        "home_name": _norm_team_name(match, "home"),
        "away_name": _norm_team_name(match, "away"),
        "home_goals": _norm_score(match, "home"),
        "away_goals": _norm_score(match, "away"),
        "home_corners": _norm_stat(match, "home", "corners"),
        "away_corners": _norm_stat(match, "away", "corners"),
        "home_sot": _norm_stat(match, "home", "sot"),
        "away_sot": _norm_stat(match, "away", "sot"),
    }


# ---------------------------------------------------------------- equipos
def _resolve_teams(client: TheStatsAPIClient, settings: dict) -> list:
    """Determina qué equipos seguir según config/settings.yaml."""
    team_ids = (settings.get("teams") or {}).get("ids") or []
    competition_ids = (settings.get("competitions") or {}).get("ids") or []
    max_teams = (settings.get("teams") or {}).get("max_teams", 60)

    teams: list = []
    if team_ids:
        for tid in team_ids:
            teams.append(client.get_team(tid))
    elif competition_ids:
        for cid in competition_ids:
            teams.extend(client.list_teams(competition_id=cid))
    else:
        logger.warning(
            "No hay 'competitions.ids' ni 'teams.ids' en config/settings.yaml. "
            "Se usará una muestra de hasta %d equipos. Ejecuta el workflow "
            "'0. Explorar API' para conocer los IDs disponibles.", max_teams)
        sample = client.list_teams(per_page=max_teams)
        teams = sample if isinstance(sample, list) else [sample]

    seen, unique = set(), []
    for team in teams:
        tid = team.get("id") if isinstance(team, dict) else None
        if tid is not None and tid not in seen:
            seen.add(tid)
            unique.append(team)
    if not team_ids:
        unique = unique[:max_teams]
    return unique


# -------------------------------------------------------------- strength
def _build_team_strength(standings: dict, raw_dir: Path) -> None:
    """Resume la fuerza de cada equipo (posición, puntos...) en un CSV."""
    rows = []
    for tid, team_standings in standings.items():
        entries = team_standings if isinstance(team_standings, list) else [team_standings]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rows.append({
                "team_id": tid,
                "position": _first(entry, "position", "rank"),
                "points": _first(entry, "points", "pts"),
                "played": _first(entry, "played", "matches_played", "games_played"),
                "won": _first(entry, "won", "wins"),
                "drawn": _first(entry, "drawn", "draws"),
                "lost": _first(entry, "lost", "losses"),
                "goals_for": _first(entry, "goals_for", "scored"),
                "goals_against": _first(entry, "goals_against", "conceded"),
            })
            break  # solo la tabla más reciente por equipo
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["team_id"], keep="last")
    df.to_csv(raw_dir / "team_strength.csv", index=False)
    logger.info("team_strength.csv: %d equipos", len(df))


# ------------------------------------------------------------------ main
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

    teams = _resolve_teams(client, settings)
    logger.info("Equipos a procesar: %d", len(teams))
    _save_json(teams, raw_dir / "teams.json")

    stats, standings = {}, {}
    for team in teams:
        tid = team.get("id")
        try:
            stats[str(tid)] = client.get_team_stats(tid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sin stats para equipo %s: %s", tid, exc)
        try:
            standings[str(tid)] = client.get_team_standings(tid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sin standings para equipo %s: %s", tid, exc)
    _save_json(stats, raw_dir / "team_stats.json")
    _save_json(standings, raw_dir / "standings.json")

    # Partidos (historial + próximos) de cada equipo
    raw_matches: dict = {}
    for team in teams:
        tid = team.get("id")
        try:
            for match in client.list_matches(team_id=tid, per_page=100):
                if isinstance(match, dict):
                    mid = match.get("id") or match.get("match_id")
                    if mid is not None:
                        raw_matches[mid] = match
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sin partidos para equipo %s: %s", tid, exc)

    matches_df = pd.DataFrame([normalize_match(m) for m in raw_matches.values()])
    if matches_df.empty:
        logger.warning("No se obtuvieron partidos. Revisa tu plan de TheStatsAPI.")
        return
    matches_df = matches_df.drop_duplicates(subset=["id"])
    matches_df["date"] = pd.to_datetime(matches_df["date"], errors="coerce", utc=True)
    matches_df = matches_df.sort_values("date")

    csv_path = raw_dir / "matches.csv"
    if csv_path.exists():
        previous = pd.read_csv(csv_path)
        previous["date"] = pd.to_datetime(previous["date"], errors="coerce", utc=True)
        matches_df = (
            pd.concat([previous, matches_df], ignore_index=True)
            .drop_duplicates(subset=["id"], keep="last")
            .sort_values("date")
        )
    matches_df.to_csv(csv_path, index=False)
    logger.info("Partidos totales en matches.csv: %d", len(matches_df))

    _build_team_strength(standings, raw_dir)


if __name__ == "__main__":
    main()
