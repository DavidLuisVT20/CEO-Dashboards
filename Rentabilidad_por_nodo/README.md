# Tablero de Servicios — Addiuva

Participación de servicios por **estatus, nodo, país, cuenta y coordinador de cabina**,
con dos perspectivas (cada una de su archivo por agente):

- **Apertura** — periodo por la fecha en que se *aperturó* el servicio · coordinador que aperturó.
- **Gestión** — periodo por la fecha en que se *gestionó* el servicio · coordinador que gestionó.

## Estructura

```
Rentabilidad_por_nodo/
├── app.py
├── requirements.txt
├── README.md
├── Nodo_apertura_x_agente.xlsx     ← fuente de APERTURA (con coordinador)
└── Nodo_gestion_x_agente.xlsx      ← fuente de GESTIÓN  (con coordinador)
```

> El `.streamlit/config.toml` (tema oscuro) vive en la **raíz del repo**, no aquí
> (requisito de Streamlit Cloud para apps en subcarpeta).

## Datos

El tablero lee **dos** Excel con estructura idéntica y los normaliza (los encabezados
difieren del estándar: `STATUS`→`ESTATUS`, `# SERVICIOS`→`SERVICIOS`, `ID CUENTA`, etc.):

- **Apertura** sale de `Nodo_apertura_x_agente.xlsx` (1,402,511 servicios tras excluir prueba).
- **Gestión** sale de `Nodo_gestion_x_agente.xlsx` (1,395,553 tras excluir prueba).
- Ambos traen `COORDINADOR` (código) y `NOMBRE`, así que la vista de coordinador
  aparece en las **dos** pestañas.

> **Nota:** en el archivo de apertura la columna de fecha viene rotulada
> `PERIODO GESTION` (parece copy-paste de la query de gestión). Se trata como fecha
> de apertura porque el total y la estructura corresponden a la apertura.

## Correr en local

```bash
pip install -r requirements.txt
# desde la RAÍZ del repo (para que tome el config.toml de la raíz):
streamlit run Rentabilidad_por_nodo/app.py
```

## El coordinador de cabina

- Aparece en **ambas** pestañas: Apertura (quien aperturó) y Gestión (quien gestionó).
- Se muestra por **NOMBRE**; si un código no tiene nombre, se muestra el código;
  sin ninguno → **"(Sin asignar)"**.
- El **filtro de coordinador** en la barra lateral aplica a **las dos** pestañas;
  sus opciones son la unión de ambas perspectivas, filtradas en cascada por
  nodo/país/cuenta/periodo.
- Son ~1,150 coordinadores, así que la gráfica es **top-N** (con el slider).

## Notas sobre los datos

- Métrica = *suma de servicios*. Las dos perspectivas **no cuadran exacto** entre
  sí (un servicio aperturado en un mes puede gestionarse en otro).
- **"En proceso" ≈ 0** (data histórica ya resuelta): aparece como rebanada mínima.
- Concentración alta: **Nodo GT ~83%** y **MCS Classicare ~44%** del total.
- **Cuentas de prueba excluidas** (IKATECH / PRUEBA / NO APERTURAR). Editable en
  `TEST_ACCOUNT_PATTERN`.
