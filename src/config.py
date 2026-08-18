"""Carga de configuración del proyecto."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "settings.yaml"


def load_settings() -> dict:
    """Lee config/settings.yaml y devuelve la configuración."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_api_key() -> str:
    """Obtiene la clave de TheStatsAPI desde el entorno (GitHub Secret)."""
    key = os.environ.get("THESTATSAPI_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "No se encontró la variable de entorno THESTATSAPI_KEY. "
            "Agrégala como Secret en: Settings -> Secrets and variables -> Actions."
        )
    return key


def resolve_path(settings: dict, key: str) -> Path:
    """Resuelve una ruta de settings['paths'] y crea la carpeta si no existe."""
    path = ROOT_DIR / settings["paths"][key]
    path.mkdir(parents=True, exist_ok=True)
    return path
