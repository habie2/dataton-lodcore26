-- =============================================================================
-- NidoMadrid · 03_consultas.sql   Consultas de comprobación y de demostración
-- =============================================================================

-- ¿Se ha cargado todo? Municipios debe ser 179 en la primera fila.
SELECT * FROM v_nm_control;

-- Referencias calculadas (estándares de cobertura y cortes de normalización).
SELECT DISTINCT ROUND(ref_edu,3) ref_edu, ROUND(ref_salud,3) ref_salud,
       ROUND(ref_transporte,1) ref_transporte, ROUND(ref_comercio,2) ref_comercio,
       ref_categorias, ROUND(alq_lo,2) alq_lo, ROUND(alq_hi,2) alq_hi
FROM v_nm_indicadores;

-- Perfil ciudadano: "Familia", municipios de menos de 50.000 habitantes.
SELECT puesto, nombre, poblacion, indice, suelo, servicios, comercio
FROM   nm_ranking(25, 55, 20)
WHERE  poblacion < 50000
ORDER  BY puesto
FETCH FIRST 20 ROWS ONLY;

-- Los cuatro perfiles guardados, top 5 de cada uno.
SELECT perfil, puesto, nombre, indice
FROM (
  SELECT p.nombre AS perfil, d.nombre,
         ROUND((p.w_suelo * d.suelo + p.w_servicios * d.servicios + p.w_comercio * d.comercio) / 100, 1) AS indice,
         RANK() OVER (PARTITION BY p.codigo
                      ORDER BY p.w_suelo * d.suelo + p.w_servicios * d.servicios + p.w_comercio * d.comercio DESC) AS puesto
  FROM nm_perfil p CROSS JOIN v_nm_dimensiones d
)
WHERE puesto <= 5
ORDER BY perfil, puesto;

-- Administración · modo Edificar (ordenado por suelo libre).
SELECT nombre, poblacion, suelo_libre_ha, servicios, comercio
FROM   v_nm_admin WHERE modo = 'EDIFICAR'
ORDER  BY suelo_libre_ha DESC;

-- Administración · modo Mejorar servicios, con el servicio que falta.
SELECT nombre, poblacion, suelo, servicios, carencia, n_edu, n_salud, n_transporte
FROM   v_nm_admin WHERE modo = 'MEJORAR_SERVICIOS'
ORDER  BY suelo DESC;

-- Exportación para la web: ejecuta y descarga el resultado como CSV
-- (en Database Actions: icono de descarga sobre la rejilla de resultados).
SELECT * FROM v_nm_web ORDER BY municipio_ine;

-- Alternativa: todo en un único JSON.
SELECT JSON_ARRAYAGG(JSON_OBJECT(* RETURNING CLOB) ORDER BY municipio_ine RETURNING CLOB) AS json
FROM v_nm_web;
