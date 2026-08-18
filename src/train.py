"""Entrena los modelos de proyección (regresión de Poisson) por mercado.

Mercados cubiertos:
  - Goles esperados (local / visitante)
  - Totales (derivado de goles esperados con distribución de Poisson)
  - Córners (local / visitante)
  - Remates al arco (local / visitante)

Guarda los modelos en models/ junto con las métricas (metricas.json).
"""
from __future__ import annotations

import json
import logging

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import ROOT_DIR, load_settings, resolve_path
from .feature_engineering import (TARGET_COLUMNS, build_match_dataset,
                                  get_feature_columns, load_matches)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def train_market(ds: pd.DataFrame, target_col: str, feature_cols: list,
                 settings: dict):
    data = ds.dropna(subset=[target_col])
    min_rows = settings["model"].get("min_training_rows", 60)
    if len(data) < min_rows:
        logger.warning("%s: solo %d filas con datos (mínimo %d). Se omite.",
                       target_col, len(data), min_rows)
        return None
    X, y = data[feature_cols], data[target_col].astype(float)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=settings["model"].get("test_size", 0.2),
        random_state=settings["model"].get("random_state", 42),
    )
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("poisson", PoissonRegressor(alpha=1e-4, max_iter=1000)),
    ])
    model.fit(X_train, y_train)
    mae = mean_absolute_error(y_test, model.predict(X_test))
    baseline = mean_absolute_error(
        y_test, np.full_like(y_test, y_train.mean(), dtype=float))
    logger.info("%-22s MAE=%.3f (baseline=%.3f) filas=%d",
                target_col, mae, baseline, len(data))
    return model, {
        "mae": round(float(mae), 4),
        "mae_baseline": round(float(baseline), 4),
        "filas_entrenamiento": int(len(data)),
    }


def main() -> None:
    settings = load_settings()
    raw_dir = resolve_path(settings, "raw")
    processed_dir = resolve_path(settings, "processed")
    models_dir = ROOT_DIR / settings["paths"]["models"]
    models_dir.mkdir(parents=True, exist_ok=True)

    matches = load_matches(raw_dir)
    strength_path = raw_dir / "team_strength.csv"
    team_strength = pd.read_csv(strength_path) if strength_path.exists() else None

    ds = build_match_dataset(matches, settings["model"].get("rolling_window", 10),
                             team_strength)
    ds.to_csv(processed_dir / "training_dataset.csv", index=False)
    feature_cols = get_feature_columns(ds)
    logger.info("Dataset de entrenamiento: %d partidos, %d features",
                len(ds), len(feature_cols))

    metrics = {}
    for market_key, target_col in TARGET_COLUMNS.items():
        result = train_market(ds, target_col, feature_cols, settings)
        if result:
            model, info = result
            joblib.dump(model, models_dir / f"modelo_{market_key}.joblib")
            metrics[market_key] = info

    with open(models_dir / "feature_columns.json", "w", encoding="utf-8") as f:
        json.dump(feature_cols, f, indent=2)
    with open(models_dir / "metricas.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    logger.info("Modelos guardados: %s", ", ".join(metrics) or "ninguno")


if __name__ == "__main__":
    main()
