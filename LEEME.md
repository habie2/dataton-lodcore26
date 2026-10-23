# NidoMadrid en Oracle 21c (Autonomous Database)

Oracle es el almacén y el motor de cálculo. Las fuentes se cargan en tablas `NM_*` unidas por código INE.
Todo el índice (normalización, dimensiones, reglas de administración y ranking ponderado) se calcula en
vistas SQL. La web solo pinta el resultado de `V_NM_WEB`.

```
fuentes oficiales ─► pipeline Python ─► CSV nm_*.csv ─► tablas NM_* ─► vistas ─► V_NM_WEB ─► web
                    (limpieza, punto                        (cálculo del índice en SQL)
                     en polígono → INE)
```

## Coste

Una Autonomous Database **Always Free** (1 OCPU, 20 GB) basta de sobra: el volumen total es de unas
decenas de miles de filas. No hace falta gastar los créditos. Si la instancia que tienes es de pago, puedes
dejarla en 1 ECPU y con autoescalado desactivado; detenla cuando no la uses.

## Pasos

1. **Crear el esquema.** En la consola de OCI abre tu Autonomous Database → *Database Actions* → *SQL*,
   entra como `ADMIN` y ejecuta `00_usuario.sql` (cambia antes la contraseña). Sal y vuelve a entrar como `NIDO`.
2. **Crear las tablas.** Como `NIDO`, ejecuta `01_esquema.sql` con *Run Script* (F5).
3. **Cargar los CSV** de la carpeta `carga/`, siempre en este orden, porque el resto depende de los municipios:
   1. `nm_municipio.csv`
   2. `nm_suelo.csv`, `nm_alquiler.csv`, `nm_centro_educativo.csv`, `nm_centro_sanitario.csv`,
      `nm_parada.csv`, `nm_comercio.csv`

   En Database Actions: *Data Load* → *Load Data* → *Local File* → arrastra el CSV → icono del lápiz →
   *Option: Insert into Table* y elige la tabla `NM_…` del mismo nombre → *Start*.
   Los CSV traen cabecera con los nombres exactos de las columnas, codificación UTF-8 y separador coma.

   Alternativa por línea de comandos con SQLcl y el wallet:
   `sql nido/<clave>@<servicio>_low` y luego `LOAD nm_municipio carga/nm_municipio.csv` para cada tabla.
4. **Crear las vistas.** Ejecuta `02_vistas.sql` con *Run Script*.
5. **Comprobar.** Ejecuta `03_consultas.sql`. La primera consulta (`V_NM_CONTROL`) debe dar 179 municipios.
6. **Exportar para la web.** Ejecuta `SELECT * FROM v_nm_web ORDER BY ine;`, descarga el resultado como CSV
   y súbemelo. Con eso actualizo la web.

## Qué calcula cada vista

| Vista | Contenido |
|---|---|
| `V_NM_BRUTO` | Indicadores simples por municipio, agregados desde las tablas de detalle |
| `V_NM_INDICADORES` | Ratios por 1.000 hab., alquiler imputado donde SERPAVI no da dato y subindicadores 0-100 |
| `V_NM_DIMENSIONES` | Suelo, Servicios y Comercio en escala 0-100 |
| `V_NM_ADMIN` | Modo `EDIFICAR` / `MEJORAR_SERVICIOS` / `SIN_ACCION` y la carencia principal |
| `NM_RANKING(w1,w2,w3)` | SQL macro: índice ponderado y puesto para cualquier combinación de pesos |
| `V_NM_WEB` | Tabla plana que consume la web |
| `V_NM_CONTROL` | Filas y municipios cubiertos por cada fuente |

Ejemplo: `SELECT * FROM nm_ranking(25, 55, 20) WHERE poblacion < 50000 ORDER BY puesto;`

## Decisiones de método

- **Suelo sin edificar = parcelas urbanas sin edificar del Catastro.** Es suelo urbano por definición. La
  Red Natura 2000 se clasifica como suelo no urbanizable de protección, así que ya queda fuera. El
  porcentaje del término que es Red Natura se guarda como contexto (`pct_protegido`).
- **Alquiler.** Se usa la mediana €/m²/mes de SERPAVI del último año. Los municipios sin dato (pocos
  contratos) toman la mediana de su zona, o la regional si su zona tampoco tiene. Quedan marcados como
  `IMPUTADO`.
- **Superficie sin edificar.** El Catastro publica el número de parcelas por tramo de superficie, no los
  metros. Las hectáreas se estiman con 50, 300, 750, 3.500 y 20.000 m² por parcela según el tramo.
- **Cobertura saturada.** Cada ratio por 1.000 hab. se divide por una referencia (percentil 75 entre
  municipios de 1.000 hab. o más) y se satura en 1. Se combina al 50 % con el nivel de oferta de 0 a 4.
  Las referencias se calculan solas a partir de los datos y se pueden consultar en `V_NM_INDICADORES`.
  Sanidad es la excepción: usa un estándar fijo de 1 centro de salud por 20.000 hab., y cada consultorio
  local cuenta como 0,2. Con un percentil, el consultorio de cada pueblo hacía que todas las ciudades
  parecieran mal dotadas.
- **Transporte.** Pasos de vehículo por parada en un miércoles tipo, a partir de los GTFS del CRTM, con las
  frecuencias expandidas (la EMT se cuenta una vez por línea y franja). Las líneas 720-728, 522, 635, N702
  y N908 vienen sin horarios: sus paradas se cargan con `con_horario = 0` y los pasos medianos de su zona.
- **Comercio.** Se usa OpenStreetMap. Su cobertura es desigual entre municipios, y es la dimensión más
  débil. Un directorio oficial de locales la mejoraría.

## Regenerar los CSV

La carpeta `pipeline/` contiene los scripts Python que generan `carga/` a partir de los ficheros oficiales
(`p1_municipios.py` … `p4_comercio.py`). Se ejecutan en orden, con los ficheros originales en `fuentes/`.
- **Normalización.** Min-max 0-100. Suelo libre (escala log) y alquiler (invertido) se acotan entre los
  percentiles 5 y 95, para que Madrid capital no aplaste la escala.
