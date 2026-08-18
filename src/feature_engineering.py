"""Construcción de variables (features) para entrenamiento y predicción.

Modelo de features: promedios móviles por equipo (general y por sede)
de goles, córners y remates al arco a favor/en contra, más fuerza de
equipo (posición y puntos desde standings).
"""
from __future__ import annotations

import pandas as pd

STATS = ("goals", "corners", "sot")
MIN_PERIODS = 3

TARGET_COLUMNS = {
    "goals_home": "target_home_goals",
    "goals_away": "target_away_goals",
    "corners_home": "target_home_corners",
    "corners_away": "target_away_corners",
    "sot_home": "target_home_sot",
    "sot_away": "target_away_sot",
}

ID_COLUMNS = ["match_id", "date", "home_id", "away_id", "home_name", "away_name"]


# ------------------------------------------------------------------ carga
def load_matches(raw_dir) -> pd.DataFrame:
    df = pd.read_csv(raw_dir / "matches.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    for col in ("home_goals", "away_goals", "home_corners", "away_corners",
                "home_sot", "away_sot"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


def finished_matches(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna(subset=["home_goals", "away_goals"])


def upcoming_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Partidos sin marcador y con fecha de hoy en adelante."""
    now = pd.Timestamp.now(tz="UTC")
    no_score = df["home_goals"].isna() | df["away_goals"].isna()
    future = df["date"].isna() | (df["date"] >= now - pd.Timedelta(hours=3))
    return df[no_score & future].sort_values("date").reset_index(drop=True)


# -------------------------------------------------------------- formato largo
def to_long(matches: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo por partido."""
    home = pd.DataFrame({
        "match_id": matches["id"], "date": matches["date"],
        "team_id": matches["home_id"], "team_name": matches["home_name"], "is_home": 1,
        "goals_for": matches["home_goals"], "goals_against": matches["away_goals"],
        "corners_for": matches["home_corners"], "corners_against": matches["away_corners"],
        "sot_for": matches["home_sot"], "sot_against": matches["away_sot"],
    })
    away = pd.DataFrame({
        "match_id": matches["id"], "date": matches["date"],
        "team_id": matches["away_id"], "team_name": matches["away_name"], "is_home": 0,
        "goals_for": matches["away_goals"], "goals_against": matches["home_goals"],
        "corners_for": matches["away_corners"], "corners_against": matches["home_corners"],
        "sot_for": matches["away_sot"], "sot_against": matches["home_sot"],
    })
    return pd.concat([home, away], ignore_index=True).sort_values("date").reset_index(drop=True)


def _base_cols() -> list:
    return [f"{s}_{d}" for s in STATS for d in ("for", "against")]


# ------------------------------------------------------------- entrenamiento
def add_rolling_features(long_df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Promedios móviles SIN incluir el partido actual (shift(1)) para
    evitar fuga de información en el entrenamiento."""
    df = long_df.sort_values("date").copy()
    grouped = df.groupby("team_id")
    for col in _base_cols():
        df[f"avg_{col}"] = grouped[col].transform(
            lambda s: s.shift(1).rolling(window, min_periods=MIN_PERIODS).mean())
    for venue, flag in (("home", 1), ("away", 0)):
        mask = df["is_home"] == flag
        sub = df[mask]
        for col in _base_cols():
            df.loc[mask, f"avg_{col}_{venue}"] = sub.groupby("team_id")[col].transform(
                lambda s: s.shift(1).rolling(window, min_periods=MIN_PERIODS).mean())
    return df


def _merge_strength(df: pd.DataFrame, team_strength: pd.DataFrame) -> pd.DataFrame:
    out = df
    for side in ("home", "away"):
        ts = team_strength.rename(columns={
            "team_id": f"{side}_id",
            **{c: f"{side}_{c}" for c in team_strength.columns if c != "team_id"},
        })
        out = out.merge(ts, on=f"{side}_id", how="left")
    return out


def build_match_dataset(matches: pd.DataFrame, window: int,
                        team_strength: pd.DataFrame | None = None) -> pd.DataFrame:
    """Dataset de entrenamiento: features pre-partido + objetivos reales."""
    finished = finished_matches(matches)
    long_df = add_rolling_features(to_long(finished), window)
    feat_cols = [c for c in long_df.columns if c.startswith("avg_")]

    home = long_df[long_df["is_home"] == 1][["match_id", "team_id"] + feat_cols]
    home = home.rename(columns={"team_id": "home_id",
                                **{c: f"home_{c}" for c in feat_cols}})
    away = long_df[long_df["is_home"] == 0][["match_id", "team_id"] + feat_cols]
    away = away.rename(columns={"team_id": "away_id",
                                **{c: f"away_{c}" for c in feat_cols}})

    rename_targets = {f"{side}_{stat}": f"target_{side}_{stat}"
                      for side in ("home", "away") for stat in STATS}
    targets = finished[["id", "date", "home_name", "away_name",
                        "home_goals", "away_goals", "home_corners",
                        "away_corners", "home_sot", "away_sot"]].rename(
        columns={"id": "match_id", **rename_targets})

    ds = home.merge(away, on="match_id").merge(targets, on="match_id")
    if team_strength is not None and not team_strength.empty:
        ds = _merge_strength(ds, team_strength)
    return ds.dropna(subset=["target_home_goals", "target_away_goals"])


# -------------------------------------------------------------- predicción
def current_team_features(matches: pd.DataFrame, window: int) -> pd.DataFrame:
    """Promedios móviles actuales por equipo (incluyendo su último partido)."""
    long_df = to_long(finished_matches(matches)).sort_values("date")
    rows = []
    for team_id, g in long_df.groupby("team_id"):
        row = {"team_id": team_id, "team_name": g["team_name"].iloc[-1]}
        for col in _base_cols():
            row[f"avg_{col}"] = g[col].tail(window).mean()
        for venue, flag in (("home", 1), ("away", 0)):
            gv = g[g["is_home"] == flag]
            for col in _base_cols():
                row[f"avg_{col}_{venue}"] = gv[col].tail(window).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def build_prediction_frame(fixtures: pd.DataFrame, history: pd.DataFrame,
                           window: int,
                           team_strength: pd.DataFrame | None = None) -> pd.DataFrame:
    """Features para partidos futuros, con las mismas columnas del entrenamiento."""
    current = current_team_features(history, window)
    feat_cols = [c for c in current.columns if c.startswith("avg_")]

    frame = fixtures[["id", "date", "home_id", "away_id",
                      "home_name", "away_name"]].rename(columns={"id": "match_id"})
    for side, id_col in (("home", "home_id"), ("away", "away_id")):
        feats = current.rename(columns={
            "team_id": id_col,
            **{c: f"{side}_{c}" for c in feat_cols},
        }).drop(columns=["team_name"], errors="ignore")
        frame = frame.merge(feats, on=id_col, how="left")
    if team_strength is not None and not team_strength.empty:
        frame = _merge_strength(frame, team_strength)
    return frame


# ---------------------------------------------------------------- utilidades
def get_feature_columns(df: pd.DataFrame) -> list:
    excluded = set(ID_COLUMNS) | set(TARGET_COLUMNS.values())
    return [c for c in df.columns
            if c not in excluded and pd.api.types.is_numeric_dtype(df[c])]
