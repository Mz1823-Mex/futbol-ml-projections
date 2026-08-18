# 📱 Guía de configuración desde el móvil

Todo el sistema funciona sin terminal. Solo necesitas el navegador de tu teléfono y tu clave de TheStatsAPI.

---

## Paso 1 — Crear el Secret con tu clave de TheStatsAPI

1. Abre el repo en el navegador: `github.com/Mz1823-Mex/futbol-ml-projections`
2. Toca **Settings** (⚙️, en el menú superior; en móvil puede estar tras el menú `...`).
3. En el menú lateral: **Secrets and variables → Actions**.
4. Toca **New repository secret**.
5. Nombre: `THESTATSAPI_KEY` — Valor: tu clave de TheStatsAPI.
6. **Add secret**.

## Paso 2 — Dar permisos de escritura a Actions

Los workflows guardan datos, modelos y proyecciones en el propio repo, así que necesitan permiso de escritura:

1. **Settings → Actions → General**.
2. Baja hasta **Workflow permissions**.
3. Selecciona **Read and write permissions** y guarda.

## Paso 3 — Crear el workflow (único paso manual)

> GitHub no permite a integraciones externas crear archivos de workflow, así que este único archivo se crea a mano. Son 2 minutos.

1. En la pestaña **Code**, toca **Add file → Create new file** (en móvil: menú `+` o `...`).
2. Como nombre escribe exactamente:
   ```
   .github/workflows/pipeline.yml
   ```
   (GitHub crea las carpetas automáticamente al escribir las `/`).
3. Abre el archivo **`docs/pipeline.yml`** de este repo, toca **Raw**, selecciona todo y cópialo.
4. Pégalo en el editor y toca **Commit changes**.

## Paso 4 — Primera ejecución: descubrir tus ligas

1. Ve a la pestaña **Actions**.
2. Selecciona **Pipeline ML Fútbol** a la izquierda.
3. Toca **Run workflow** → en *Qué ejecutar* elige **`explorar`** → **Run workflow**.
4. Cuando termine (círculo verde), abre **`data/raw/competitions.json`** y busca los IDs de las ligas que te interesan.

## Paso 5 — Configurar tus competiciones

1. Abre **`config/settings.yaml`** y toca el lápiz ✏️ (Edit).
2. En `competitions.ids` coloca los IDs, por ejemplo:
   ```yaml
   competitions:
     ids: [8, 564]
   ```
3. **Commit changes**.

## Paso 6 — Generar tus primeras proyecciones

En **Actions → Pipeline ML Fútbol → Run workflow** ejecuta, en este orden:

1. `datos` — descarga historial de partidos (puede tardar varios minutos la primera vez).
2. `entrenar` — entrena los modelos de cada mercado.
3. `predecir` — genera las proyecciones.

O ejecuta directamente **`todo`**, que hace los tres pasos seguidos.

## Paso 7 — Leer los resultados

Abre **`data/predictions/ultimas_predicciones.md`**: una tabla con fecha, equipos, goles esperados, probabilidad de más/menos de 2.5, ambos anotan, córners y remates al arco esperados.

Cada ejecución también guarda un archivo con fecha (`predicciones_YYYY-MM-DD.csv`) para tu historial.

---

## Uso diario

Después de la configuración inicial **no tienes que hacer nada**: los horarios automáticos (UTC) son:

| Hora UTC | Tarea |
|---|---|
| 06:00 diario | Actualizar datos |
| 07:00 domingos | Re-entrenar modelos |
| 09:00 diario | Generar proyecciones |

Y siempre puedes lanzar cualquier tarea a mano desde **Actions → Run workflow**.

> ⚠️ **Nota de GitHub**: si el repo pasa 60 días sin actividad, GitHub pausa los horarios automáticos. Basta con ejecutar un workflow a mano para reactivarlos.

---

## Solución de problemas

| Problema | Solución |
|---|---|
| El workflow falla con "No se encontró THESTATSAPI_KEY" | Revisa el Paso 1: el nombre del secret debe ser exactamente `THESTATSAPI_KEY` |
| Falla el paso "Guardar resultados en el repo" | Revisa el Paso 2 (permisos Read and write) |
| `entrenar` dice "solo X filas con datos" | Faltan datos históricos: ejecuta `datos` más veces o amplía las competiciones |
| Solo aparecen goles, sin córners ni remates | Tu plan de TheStatsAPI no incluye esas estadísticas por partido; el resto del sistema sigue funcionando |
| Error 429 (rate limit) | Sube `sleep_between_requests` en `config/settings.yaml` (ej. a `3`) |
| Quiero otra línea de totales (ej. 3.5) | Cambia `totals_line` en `config/settings.yaml` |
