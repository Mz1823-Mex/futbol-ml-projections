# ⚽ Fútbol ML Projections

Sistema de **Machine Learning para proyección de mercados de fútbol** que corre 100% en **GitHub Actions** — sin terminal, sin servidor, todo se opera desde el navegador del móvil.

Los datos en tiempo real vienen de **TheStatsAPI** (`https://api.thestatsapi.com/api`).

## Mercados que proyecta

| Mercado | Salida del modelo |
|---|---|
| ⚽ Goles | Goles esperados por equipo (xG propio) |
| 🔢 Totales | Probabilidad de más/menos de 2.5 goles (línea configurable) |
| 🚩 Córners | Córners esperados por equipo y totales |
| 🎯 Remates al arco | Tiros a puerta esperados por equipo y totales |
| ➕ Extra | Probabilidad de "ambos equipos anotan" |

## Arquitectura

```
TheStatsAPI ──► src/data_collector.py ──► data/raw/matches.csv
                                                │
                              src/feature_engineering.py
                                                │
                              src/train.py ──► models/*.joblib  (Poisson)
                                                │
                              src/predict.py ──► data/predictions/
                                                 (CSV + Markdown)
```

Todo el flujo lo ejecuta GitHub Actions: **datos diarios (06:00 UTC) → entrenamiento semanal (domingos 07:00 UTC) → proyecciones diarias (09:00 UTC)**. Los resultados se guardan solos en este repo.

## Estructura del repositorio

```
futbol-ml-projections/
├── .github/workflows/pipeline.yml   ← único archivo que debes crear a mano (ver docs)
├── config/settings.yaml             ← competiciones, mercados y parámetros del modelo
├── src/
│   ├── api_client.py                ← cliente de TheStatsAPI (Bearer, reintentos, paginación)
│   ├── explorar_api.py              ← descubre IDs de competiciones y equipos
│   ├── data_collector.py            ← descarga equipos, stats, standings y partidos
│   ├── feature_engineering.py       ← promedios móviles por equipo y sede
│   ├── train.py                     ← entrena modelos de Poisson por mercado
│   └── predict.py                   ← genera proyecciones y probabilidades
├── data/
│   ├── raw/                         ← datos crudos (matches.csv, standings, stats)
│   ├── processed/                   ← dataset de entrenamiento
│   └── predictions/                 ← proyecciones diarias (CSV + .md)
├── models/                          ← modelos entrenados + métricas (metricas.json)
└── docs/
    ├── GUIA_MOVIL.md                ← configuración paso a paso desde el móvil
    └── pipeline.yml                 ← workflow listo para copiar
```

## Configuración inicial (5 minutos desde el móvil)

1. **Crear el Secret** `THESTATSAPI_KEY` en *Settings → Secrets and variables → Actions*.
2. **Permisos de escritura**: *Settings → Actions → General → Workflow permissions → Read and write*.
3. **Crear el workflow**: copia `docs/pipeline.yml` en `.github/workflows/pipeline.yml` desde el navegador (instrucciones detalladas en `docs/GUIA_MOVIL.md`).
4. En la pestaña **Actions** ejecuta *Pipeline ML Fútbol* con la tarea `explorar`, revisa `data/raw/competitions.json` y anota los IDs de tus ligas.
5. Edita `config/settings.yaml` (icono ✏️) con esos IDs y ejecuta las tareas `datos` → `entrenar` → `predecir` (o `todo`).

Las proyecciones aparecen en **`data/predictions/ultimas_predicciones.md`**, con formato de tabla legible desde el teléfono.

## Cómo funciona el modelo

- **Features**: promedios móviles (10 partidos por defecto) de goles, córners y remates al arco a favor/en contra, separados por localía, más posición y puntos desde el standings. Para el entrenamiento se usa `shift(1)` para no filtrar información del propio partido.
- **Modelo**: regresión de **Poisson** por cada variable objetivo (goles, córners y tiros a puerta de cada equipo), con imputación de medianas y escalado.
- **Probabilidades**: del goles esperados se deriva la distribución de Poisson del total para calcular *más/menos de la línea* y *ambos anotan*.
- **Métricas**: cada entrenamiento guarda el MAE contra un baseline en `models/metricas.json`.

Si tu plan de TheStatsAPI no incluye córners o tiros a puerta por partido, esos mercados se omiten automáticamente y el sistema sigue funcionando con goles y totales.

## Aviso

Este proyecto es educativo. Ninguna proyección estadística garantiza resultados; úsalo con responsabilidad.
