# Tablero de Servicios — Addiuva

Participación de servicios por **estatus, nodo, país, cuenta y coordinador de cabina**,
con dos perspectivas:

- **Apertura** — periodo por la fecha en que se *aperturó* el servicio.
- **Gestión** — periodo por la fecha en que se *gestionó* el servicio, ya
  desglosado por **coordinador de cabina** (quien lo gestionó).

## Estructura

```
Rentabilidad_por_nodo/
├── app.py
├── requirements.txt
├── README.md
├── Servicios_ene2025_abr2026.xlsx     ← fuente de APERTURA (hoja de creación)
└── Nodo_gestion_x_agente.xlsx         ← fuente de GESTIÓN (con coordinador)
```

> El `.streamlit/config.toml` (tema oscuro) vive en la **raíz del repo**, no aquí
> (requisito de Streamlit Cloud para apps en subcarpeta).

## Dos archivos de datos

El tablero lee **dos** Excel y los normaliza a un esquema común (los encabezados
difieren entre archivos: `STATUS`/`ESTATUS`, `# SERVICIOS`/`SERVICIOS`, etc.):

- **Apertura** sale de `Servicios_ene2025_abr2026.xlsx` (hoja *creación*).
- **Gestión** sale de `Nodo_gestion_x_agente.xlsx`, que trae todo lo de la hoja
  de gestión **más** las columnas `COORDINADOR` (código) y `NOMBRE`. Reconcilia
  exacto con la hoja de gestión original (1,395,553 servicios tras excluir prueba).

## Correr en local

```bash
pip install -r requirements.txt
# desde la RAÍZ del repo (para que tome el config.toml de la raíz):
streamlit run dashboards/Rentabilidad_por_nodo/app.py
```

## Publicar en Streamlit Community Cloud

1. Sube el repo a GitHub (con los dos `.xlsx` y el `.streamlit/config.toml` en la raíz).
2. En https://share.streamlit.io → **Create app** → repo `rpuenteaddiuva/Addiuva`,
   branch `main`, Main file path `dashboards/Rentabilidad_por_nodo/app.py` (diagonales normales).
3. Deploy. Cloud instala `requirements.txt` (junto a `app.py`) y levanta la app.

## El coordinador de cabina

- Vive **solo en la pestaña Gestión** (el dato solo viene en gestión).
- Se muestra por **NOMBRE**; si un código no tiene nombre, se muestra el código;
  sin ninguno → **"(Sin asignar)"** (~0.4% de los servicios).
- El **filtro de coordinador** en la barra lateral solo afecta a Gestión, y sus
  opciones se filtran en cascada según nodo/país/cuenta/periodo.
- Son ~1,150 coordinadores, así que la gráfica es **top-N** (con el slider).
- Atribución = **quien gestionó** el servicio.

### Si más adelante llega "apertura por agente"

El loader y los gráficos ya están listos: bastará leer el archivo de apertura con
su columna de agente, construir la misma columna `AGENTE`, y activar `show_coord=True`
también en la pestaña de Apertura.

## Notas sobre los datos

- Métrica = *suma de servicios*. Las dos perspectivas **no cuadran exacto** entre
  sí (un servicio aperturado en un mes puede gestionarse en otro).
- **"En proceso" ≈ 0** (data histórica ya resuelta): aparece como rebanada mínima.
- Concentración alta: **Nodo GT ~83%** y **MCS Classicare ~44%** del total.
- **Cuentas de prueba excluidas** (IKATECH / PRUEBA / NO APERTURAR). Editable en
  `TEST_ACCOUNT_PATTERN`.
