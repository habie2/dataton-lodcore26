-- =============================================================================
-- NidoMadrid · 02_vistas.sql   (ejecutar como NIDO, después de cargar los datos)
-- Todo el cálculo del índice vive aquí, en SQL. Cadena de vistas:
--   v_nm_centro_etapas  etapas de cada centro, leídas del nombre de su tipo
--   v_nm_bruto        indicadores simples por municipio (agregación de detalle)
--   v_nm_indicadores  ratios por 1.000 hab., imputación de alquiler y
--                     subindicadores normalizados 0-100
--   v_nm_dimensiones  las tres dimensiones (Suelo, Servicios, Comercio) 0-100
--   v_nm_admin        reglas de administración: EDIFICAR / MEJORAR_SERVICIOS
--   nm_ranking(...)   SQL macro con el índice ponderado del perfil ciudadano
--   v_nm_web          exportación plana para la web
--   v_nm_control      control de calidad de la carga
-- =============================================================================

-- 0. Etapas de cada centro educativo ------------------------------------------
-- Se leen literalmente del nombre del tipo publicado por la Consejería (TIPO_EXT),
-- sin suponer nada que el nombre no diga. Ejemplos:
--   "COLEGIO DE EDUCACIÓN INFANTIL Y PRIMARIA"  -> infantil, primaria
--   "INSTITUTO DE EDUCACIÓN SECUNDARIA"         -> secundaria
--   "CENTRO PRIVADO DE FORMACIÓN PROFESIONAL ESPECÍFICA" -> fp
-- Los tipos cuyo nombre no menciona ninguna etapa (escuelas de música, idiomas,
-- adultos, equipos de orientación...) se conservan en la tabla pero no cuentan.
CREATE OR REPLACE VIEW v_nm_centro_etapas AS
SELECT c.*,
       CASE WHEN INSTR(UPPER(c.tipo_ext), 'INFANTIL')   > 0 THEN 1 ELSE 0 END AS infantil,
       CASE WHEN INSTR(UPPER(c.tipo_ext), 'PRIMARIA')   > 0 THEN 1 ELSE 0 END AS primaria,
       CASE WHEN INSTR(UPPER(c.tipo_ext), 'SECUNDARIA') > 0 THEN 1 ELSE 0 END AS secundaria,
       CASE WHEN REGEXP_LIKE(UPPER(c.tipo_ext), 'FORMACI.N PROFESIONAL') THEN 1 ELSE 0 END AS fp
FROM nm_centro_educativo c;

-- 1. Indicadores simples ------------------------------------------------------
CREATE OR REPLACE VIEW v_nm_bruto AS
SELECT m.municipio_ine, m.nombre, m.zona_codigo, m.zona, m.poblacion, m.poblacion_anio,
       m.superficie_km2, m.dist_sol_km, m.pct_protegido,
       NVL(s.sup_sin_edificar_ha, 0)  AS suelo_libre_ha,
       s.parcelas_sin_edificar,
       a.alquiler_m2                  AS alquiler_serpavi,
       a.anio                         AS alquiler_anio,
       NVL(e.n_centros, 0)            AS centros_edu,
       NVL(e.n_etapas, 0)             AS etapas_edu,
       NVL(h.n_puntos, 0)             AS puntos_salud,
       NVL(h.n_equiv_cs, 0)           AS equiv_cs,
       NVL(h.nivel_max, 0)            AS nivel_salud,
       NVL(t.n_paradas, 0)            AS paradas,
       NVL(t.salidas, 0)              AS salidas_dia,
       NVL(t.ferroviario, 0)          AS ferroviario,
       NVL(c.n_comercios, 0)          AS comercios,
       NVL(c.n_categorias, 0)         AS categorias
FROM nm_municipio m
LEFT JOIN nm_suelo    s ON s.municipio_ine = m.municipio_ine
LEFT JOIN nm_alquiler a ON a.municipio_ine = m.municipio_ine
LEFT JOIN (SELECT municipio_ine, COUNT(*) AS n_centros,
                  MAX(infantil) + MAX(primaria) + MAX(secundaria) + MAX(fp) AS n_etapas
           FROM v_nm_centro_etapas
           WHERE infantil + primaria + secundaria + fp > 0      -- solo centros de enseñanza general o FP
           GROUP BY municipio_ine) e ON e.municipio_ine = m.municipio_ine
LEFT JOIN (SELECT municipio_ine,
                  SUM(CASE WHEN nivel <= 2 THEN 1 ELSE 0 END) AS n_puntos,  -- consultorios + centros de salud
                  SUM(CASE nivel WHEN 2 THEN 1 WHEN 1 THEN 0.2 ELSE 0 END) AS n_equiv_cs,  -- consultorio = 0,2 CS
                  MAX(nivel) AS nivel_max
           FROM nm_centro_sanitario GROUP BY municipio_ine) h ON h.municipio_ine = m.municipio_ine
LEFT JOIN (SELECT municipio_ine, COUNT(*) AS n_paradas, SUM(salidas_dia) AS salidas,
                  MAX(CASE WHEN modo IN ('METRO','CERCANIAS','METRO_LIGERO') THEN 1 ELSE 0 END) AS ferroviario
           FROM nm_parada GROUP BY municipio_ine) t ON t.municipio_ine = m.municipio_ine
LEFT JOIN (SELECT municipio_ine, COUNT(*) AS n_comercios, COUNT(DISTINCT categoria) AS n_categorias
           FROM nm_comercio GROUP BY municipio_ine) c ON c.municipio_ine = m.municipio_ine;

-- 2. Ratios, imputación y normalización de subindicadores ---------------------
-- Cobertura saturada: cada ratio por 1.000 hab. se compara con una referencia
-- (percentil 75 entre municipios de 1.000 hab. o más) y se satura en 100. Así un
-- pueblo de 60 vecinos con un consultorio no supera a una ciudad. Sanidad usa un
-- estándar fijo: 1 centro de salud por 20.000 hab. (consultorio local = 0,2). Cada
-- subindicador de servicios combina al 50 % esa cobertura con el nivel de oferta:
--   educación   etapas presentes (infantil, primaria, secundaria, FP) / 4
--   sanidad     nivel máximo (consultorio, centro de salud, urgencias, hospital) / 4
--   transporte  (hay paradas) + (≥100 salidas/día) + (≥1.000 salidas/día) + (Metro/Cercanías/ML), / 4
-- Comercio combina comercios por 1.000 hab. con la variedad (categorías
-- distintas / percentil 90). Suelo libre (escala log) y alquiler (invertido) se
-- normalizan min-max entre los percentiles 5 y 95.
CREATE OR REPLACE VIEW v_nm_indicadores AS
WITH b AS (
  SELECT v.*,
         NVL(NVL(v.alquiler_serpavi,
                 MEDIAN(v.alquiler_serpavi) OVER (PARTITION BY v.zona)),
             MEDIAN(v.alquiler_serpavi) OVER ())                       AS alquiler_m2,
         CASE WHEN v.alquiler_serpavi IS NULL THEN 'IMPUTADO' ELSE 'SERPAVI' END AS alquiler_origen,
         v.centros_edu  / v.poblacion * 1000                             AS edu_1000,
         v.equiv_cs     / v.poblacion * 1000                             AS salud_1000,
         v.salidas_dia  / v.poblacion * 1000                             AS salidas_1000,
         v.comercios    / v.poblacion * 1000                             AS comercio_1000,
         LN(v.suelo_libre_ha + 1)                                        AS ln_suelo,
         CASE WHEN v.paradas > 0        THEN 1 ELSE 0 END
       + CASE WHEN v.salidas_dia >= 100  THEN 1 ELSE 0 END
       + CASE WHEN v.salidas_dia >= 1000 THEN 1 ELSE 0 END
       + v.ferroviario                                                   AS nivel_transporte
  FROM v_nm_bruto v
), ref AS (
  SELECT PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY CASE WHEN poblacion >= 1000 THEN edu_1000      END) AS ref_edu,
         0.05                                                                                              AS ref_salud,  -- 1 centro de salud / 20.000 hab.
         PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY CASE WHEN poblacion >= 1000 THEN salidas_1000  END) AS ref_transporte,
         PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY CASE WHEN poblacion >= 1000 THEN comercio_1000 END) AS ref_comercio,
         PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY CASE WHEN poblacion >= 1000 THEN categorias    END) AS ref_categorias,
         PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY ln_suelo)    AS suelo_lo,
         PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ln_suelo)    AS suelo_hi,
         PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY alquiler_m2) AS alq_lo,
         PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY alquiler_m2) AS alq_hi
  FROM b
)
SELECT b.*, ref.*,
       ROUND(100 * (LEAST(GREATEST(b.ln_suelo, ref.suelo_lo), ref.suelo_hi) - ref.suelo_lo)
                 / NULLIF(ref.suelo_hi - ref.suelo_lo, 0), 1)                         AS n_suelo_libre,
       ROUND(100 - 100 * (LEAST(GREATEST(b.alquiler_m2, ref.alq_lo), ref.alq_hi) - ref.alq_lo)
                 / NULLIF(ref.alq_hi - ref.alq_lo, 0), 1)                             AS n_alquiler,
       ROUND(50 * LEAST(1, b.edu_1000      / NULLIF(ref.ref_edu, 0))        + 50 * b.etapas_edu / 4, 1)       AS n_edu,
       ROUND(50 * LEAST(1, b.salud_1000    / NULLIF(ref.ref_salud, 0))      + 50 * b.nivel_salud / 4, 1)      AS n_salud,
       ROUND(50 * LEAST(1, b.salidas_1000  / NULLIF(ref.ref_transporte, 0)) + 50 * b.nivel_transporte / 4, 1) AS n_transporte,
       ROUND(50 * LEAST(1, b.comercio_1000 / NULLIF(ref.ref_comercio, 0))
           + 50 * LEAST(1, b.categorias    / NULLIF(ref.ref_categorias, 0)), 1)                               AS n_comercio
FROM b CROSS JOIN ref;

-- 3. Dimensiones (min-max 0-100 sobre los 179 municipios) ---------------------
CREATE OR REPLACE VIEW v_nm_dimensiones AS
WITH d AS (
  SELECT i.*,
         (i.n_suelo_libre + i.n_alquiler) / 2            AS suelo_raw,
         (i.n_edu + i.n_salud + i.n_transporte) / 3      AS servicios_raw,
         i.n_comercio                                    AS comercio_raw
  FROM v_nm_indicadores i
)
SELECT d.*,
       ROUND(100 * (suelo_raw - MIN(suelo_raw) OVER ())
                 / NULLIF(MAX(suelo_raw) OVER () - MIN(suelo_raw) OVER (), 0), 1)             AS suelo,
       ROUND(100 * (servicios_raw - MIN(servicios_raw) OVER ())
                 / NULLIF(MAX(servicios_raw) OVER () - MIN(servicios_raw) OVER (), 0), 1)     AS servicios,
       ROUND(100 * (comercio_raw - MIN(comercio_raw) OVER ())
                 / NULLIF(MAX(comercio_raw) OVER () - MIN(comercio_raw) OVER (), 0), 1)       AS comercio
FROM d;

-- 4. Reglas de administración -------------------------------------------------
--   EDIFICAR           servicios y comercio por encima de la mediana
--                      (ordenar por suelo_libre_ha)
--   MEJORAR_SERVICIOS  suelo por encima de la mediana y servicios por debajo
--                      (ordenar por suelo); carencia = subindicador de servicios más bajo
CREATE OR REPLACE VIEW v_nm_admin AS
WITH x AS (
  SELECT d.*,
         MEDIAN(d.suelo)     OVER () AS med_suelo,
         MEDIAN(d.servicios) OVER () AS med_servicios,
         MEDIAN(d.comercio)  OVER () AS med_comercio
  FROM v_nm_dimensiones d
)
SELECT x.*,
       CASE WHEN x.servicios > x.med_servicios AND x.comercio > x.med_comercio THEN 'EDIFICAR'
            WHEN x.suelo > x.med_suelo AND x.servicios < x.med_servicios     THEN 'MEJORAR_SERVICIOS'
            ELSE 'SIN_ACCION' END                                             AS modo,
       CASE WHEN x.n_edu <= x.n_salud AND x.n_edu <= x.n_transporte THEN 'EDUCACION'
            WHEN x.n_salud <= x.n_transporte                         THEN 'SANIDAD'
            ELSE 'TRANSPORTE' END                                     AS carencia
FROM x;

-- 5. Índice del perfil ciudadano (SQL macro, Oracle 19c+/21c) -----------------
--   SELECT * FROM nm_ranking(25, 55, 20) WHERE poblacion < 50000 ORDER BY puesto;
CREATE OR REPLACE FUNCTION nm_ranking (
  w_suelo      NUMBER,
  w_servicios  NUMBER,
  w_comercio   NUMBER
) RETURN VARCHAR2 SQL_MACRO(TABLE) IS
BEGIN
  RETURN q'[
    SELECT municipio_ine, nombre, zona, poblacion, suelo, servicios, comercio, modo, carencia,
           ROUND((w_suelo * suelo + w_servicios * servicios + w_comercio * comercio)
                 / NULLIF(w_suelo + w_servicios + w_comercio, 0), 1) AS indice,
           RANK() OVER (ORDER BY (w_suelo * suelo + w_servicios * servicios + w_comercio * comercio)
                                 / NULLIF(w_suelo + w_servicios + w_comercio, 0) DESC) AS puesto
    FROM v_nm_admin]';
END nm_ranking;
/

-- 6. Exportación para la web --------------------------------------------------
CREATE OR REPLACE VIEW v_nm_web AS
SELECT municipio_ine, nombre, zona_codigo, zona, poblacion, poblacion_anio,
       superficie_km2 AS km2, dist_sol_km AS dist_km, pct_protegido AS protegido_pct,
       suelo_libre_ha, parcelas_sin_edificar,
       ROUND(alquiler_m2, 2) AS alquiler_m2, alquiler_origen, alquiler_anio,
       centros_edu, etapas_edu, ROUND(edu_1000, 3) AS edu_1000,
       puntos_salud, nivel_salud, ROUND(salud_1000, 3) AS salud_1000,
       paradas, salidas_dia, ROUND(salidas_1000, 1) AS salidas_1000, ferroviario, nivel_transporte,
       comercios, ROUND(comercio_1000, 2) AS comercio_1000, categorias,
       n_suelo_libre, n_alquiler, n_edu, n_salud, n_transporte, n_comercio,
       suelo, servicios, comercio, modo, carencia,
       ROUND(med_suelo, 1) AS med_suelo, ROUND(med_servicios, 1) AS med_servicios, ROUND(med_comercio, 1) AS med_comercio
FROM v_nm_admin;

-- 7. Control de calidad -------------------------------------------------------
CREATE OR REPLACE VIEW v_nm_control AS
SELECT 'Municipios (INE)' AS fuente, COUNT(*) AS filas, COUNT(DISTINCT municipio_ine) AS municipios FROM nm_municipio
UNION ALL SELECT 'Suelo sin edificar (Catastro)', COUNT(*), COUNT(DISTINCT municipio_ine) FROM nm_suelo
UNION ALL SELECT 'Alquiler (SERPAVI)',            COUNT(*), COUNT(DISTINCT municipio_ine) FROM nm_alquiler
UNION ALL SELECT 'Centros educativos',            COUNT(*), COUNT(DISTINCT municipio_ine) FROM nm_centro_educativo
UNION ALL SELECT 'Centros sanitarios',            COUNT(*), COUNT(DISTINCT municipio_ine) FROM nm_centro_sanitario
UNION ALL SELECT 'Paradas de transporte',         COUNT(*), COUNT(DISTINCT municipio_ine) FROM nm_parada
UNION ALL SELECT 'Comercios (OSM)',               COUNT(*), COUNT(DISTINCT municipio_ine) FROM nm_comercio;
