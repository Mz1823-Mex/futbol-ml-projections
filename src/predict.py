"""Genera proyecciones para los próximos partidos.

Salidas (se guardan en data/predictions/ y se suben al repo automáticamente):
  - predicciones_YYYY-MM-DD.csv
  - ultimas_predicciones.csv
  - ultimas_predicciones.md   (tabla legible desde el móvil)
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from scipy.stats import poisson

from .config import ROOT_DIR, load_settings, resolve_path
from .feature_engineering import (TARGET_COLUMNS, build_prediction_frame,
                                  load_matches, upcoming_matches)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def _load_models(models_dir):
    models = {}
    for key in TARGET_COLUMNS:
        path = models_dir / f"modelo_{key}.joblib"
        if path.exists():
            models[key] = joblib.load(path)
    with open(models_dir / "feature_columns.json", "r", encoding="utf-8") as f:
        feature_cols = json.load(f)
    return models, feature_cols


def main() -> None:
    settings = load_settings()
    raw_dir = resolve_path(settings, "raw")
    pred_dir = resolve_path(settings, "predictions")
    models_dir = ROOT_DIR / settings["paths"]["models"]

    models, feature_cols = _load_models(models_dir)
    if not models:
        raise SystemExit(
            "No hay modelos entrenados. Ejecuta primero el workflow '2. Entrenar modelos'.")

    matches = load_matches(raw_dir)
    fixtures = upcoming_matches(matches)
    if fixtures.empty:
        logger.info("No hay partidos próximos. Ejecuta '1. Actualizar datos' primero.")
        return

    strength_path = raw_dir / "team_strength.csv"
    team_strength = pd.read_csv(strength_path) if strength_path.exists() else None

    frame = build_prediction_frame(
        fixtures, matches, settings["model"].get("rolling_window", 10), team_strength)
    X = frame.reindex(columns=feature_cols)

    out = frame[["date", "home_name", "away_name"]].copy()
    out = out.rename(columns={"date": "fecha", "home_name": "local",
                              "away_name": "visitante"})

    expected = {}
    for key, model in models.items():
        expected[key] = np.clip(model.predict(X), 0.01, None)

    line = float(settings["model"].get("totals_line", 2.5))
    xg_h, xg_a = expected.get("goals_home"), expected.get("goals_away")

    # ---- Mercado: goles y totales ----
    if xg_h is not None and xg_a is not None:
        out["goles_esp_local"] = np.round(xg_h, 2)
        out["goles_esp_visitante"] = np.round(xg_a, 2)
        out["goles_esp_total"] = np.round(xg_h + xg_a, 2)
        floor_line = math.floor(line)
        over = np.array([1 - poisson.cdf(floor_line, lh + la)
                         for lh, la in zip(xg_h, xg_a)])
        out[f"prob_mas_de_{line}"] = np.round(over, 3)
        out[f"prob_menos_de_{line}"] = np.round(1 - over, 3)
        out["prob_ambos_anotan"] = np.round(
            (1 - poisson.pmf(0, xg_h)) * (1 - poisson.pmf(0, xg_a)), 3)

    # ---- Mercados: córners y remates al arco ----
    for prefix, keys in (("corners", ("corners_home", "corners_away")),
                         ("remates_al_arco", ("sot_home", "sot_away"))):
        kh, ka = keys
        if kh in expected and ka in expected:
            out[f"{prefix}_esp_local"] = np.round(expected[kh], 2)
            out[f"{prefix}_esp_visitante"] = np.round(expected[ka], 2)
            out[f"{prefix}_esp_total"] = np.round(expected[kh] + expected[ka], 2)

    out = out.sort_values("fecha").reset_index(drop=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    csv_path = pred_dir / f"predicciones_{stamp}.csv"
    out.to_csv(csv_path, index=False)
    out.to_csv(pred_dir / "ultimas_predicciones.csv", index=False)

    md_lines = [
        f"# Proyecciones de partidos — {stamp} (UTC)",
        "",
        "_Generado automáticamente por GitHub Actions con modelos de Poisson._",
        "",
        out.to_markdown(index=False),
        "",
    ]
    with open(pred_dir / "ultimas_predicciones.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    logger.info("Proyecciones generadas para %d partidos -> %s",
                len(out), csv_path.name)


if __name__ == "__main__":
    main()
