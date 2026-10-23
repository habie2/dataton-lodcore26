-- =============================================================================
-- NidoMadrid · 01_esquema.sql   (ejecutar como NIDO)
-- Tablas de datos. Todas se unen por el código INE de municipio (5 dígitos).
-- Las tablas de detalle (centros, paradas, comercios) llegan con el código INE
-- ya asignado por punto-en-polígono en el pipeline Python.
-- =============================================================================

-- Para rehacer desde cero, descomenta:
-- BEGIN FOR t IN (SELECT table_name FROM user_tables WHERE table_name LIKE 'NM\_%' ESCAPE '\')
--   LOOP EXECUTE IMMEDIATE 'DROP TABLE '||t.table_name||' CASCADE CONSTRAINTS PURGE'; END LOOP; END;
-- /

-- Municipios: INE (población) + límites municipales (superficie, centroide) +
-- Red Natura 2000 (porcentaje del término protegido, cruce de polígonos).
CREATE TABLE nm_municipio (
  municipio_ine             VARCHAR2(5)   CONSTRAINT nm_municipio_pk PRIMARY KEY,
  nombre          VARCHAR2(100) NOT NULL,
  zona            VARCHAR2(40),
  poblacion       NUMBER(9)     NOT NULL CONSTRAINT nm_mun_pob_ck CHECK (poblacion > 0),
  poblacion_anio  NUMBER(4)     NOT NULL,
  superficie_km2  NUMBER(10,2)  NOT NULL,
  dist_sol_km     NUMBER(6,1),
  pct_protegido   NUMBER(5,1)   DEFAULT 0 NOT NULL
);

-- Catastro: parcelas urbanas sin edificar (solares). Por definición es suelo
-- urbano, así que no incluye suelo no urbanizable de protección (Red Natura).
CREATE TABLE nm_suelo (
  municipio_ine                    VARCHAR2(5) CONSTRAINT nm_suelo_pk PRIMARY KEY
                         CONSTRAINT nm_suelo_fk REFERENCES nm_municipio,
  parcelas_sin_edificar  NUMBER(9),
  sup_sin_edificar_ha    NUMBER(12,2) NOT NULL,
  anio                   NUMBER(4)    NOT NULL
);

-- SERPAVI (MIVAU): mediana de alquiler €/m²/mes del último año disponible.
-- Los municipios sin dato (pocos contratos) se imputan en la vista.
CREATE TABLE nm_alquiler (
  municipio_ine          VARCHAR2(5) CONSTRAINT nm_alquiler_pk PRIMARY KEY
               CONSTRAINT nm_alquiler_fk REFERENCES nm_municipio,
  alquiler_m2  NUMBER(6,2) NOT NULL,
  anio         NUMBER(4)   NOT NULL
);

-- Consejería de Educación: un registro por centro en situación ALTA, con el tipo
-- exactamente como lo publica la fuente (código, abreviatura y nombre completo).
-- Las etapas que imparte se derivan del nombre del tipo en v_nm_centro_etapas.
CREATE TABLE nm_centro_educativo (
  codigo         VARCHAR2(12)   CONSTRAINT nm_cedu_pk PRIMARY KEY,
  municipio_ine  VARCHAR2(5)    NOT NULL CONSTRAINT nm_cedu_fk REFERENCES nm_municipio,
  nombre         VARCHAR2(200),
  titularidad    VARCHAR2(30),
  cod_tipo       VARCHAR2(5)    NOT NULL,
  tipo_abrv      VARCHAR2(30)   NOT NULL,
  tipo_ext       VARCHAR2(200)  NOT NULL
);

-- Ministerio de Sanidad: catálogos de Atención Primaria, urgencias
-- extrahospitalarias y hospitales. Nivel de oferta:
--   1 consultorio local · 2 centro de salud · 3 urgencias extrahospitalarias · 4 hospital
CREATE TABLE nm_centro_sanitario (
  id      VARCHAR2(30)  CONSTRAINT nm_csan_pk PRIMARY KEY,
  municipio_ine     VARCHAR2(5)   NOT NULL CONSTRAINT nm_csan_fk REFERENCES nm_municipio,
  nombre  VARCHAR2(200),
  tipo    VARCHAR2(40)  NOT NULL,
  nivel   NUMBER(1)     NOT NULL CONSTRAINT nm_csan_niv_ck CHECK (nivel BETWEEN 1 AND 4)
);

-- CRTM (GTFS): una fila por parada y feed. Modo EMT = autobuses urbanos de Madrid
-- capital (feed propio de la EMT); URBANO = urbanos del resto de municipios.
-- Se guardan los pasos de vehículo en un miércoles tipo (stop_times de los servicios activos, frecuencias expandidas).
-- con_horario = 0: parada publicada cuya línea no trae horarios en el GTFS
-- (720-728, 522, 635, N702, N908); salidas imputadas con la mediana de su zona.
CREATE TABLE nm_parada (
  id           VARCHAR2(60)  CONSTRAINT nm_parada_pk PRIMARY KEY,
  municipio_ine          VARCHAR2(5)   NOT NULL CONSTRAINT nm_parada_fk REFERENCES nm_municipio,
  modo         VARCHAR2(20)  NOT NULL CONSTRAINT nm_parada_modo_ck
               CHECK (modo IN ('METRO','CERCANIAS','METRO_LIGERO','INTERURBANO','URBANO','EMT')),
  nombre       VARCHAR2(200),
  salidas_dia  NUMBER(8)     DEFAULT 0 NOT NULL,
  con_horario  NUMBER(1)     DEFAULT 1 NOT NULL CHECK (con_horario IN (0,1))
);

-- OpenStreetMap: un registro por comercio (shop=*), con su categoría.
CREATE TABLE nm_comercio (
  osm_id     VARCHAR2(24)  CONSTRAINT nm_comercio_pk PRIMARY KEY,
  municipio_ine        VARCHAR2(5)   NOT NULL CONSTRAINT nm_comercio_fk REFERENCES nm_municipio,
  categoria  VARCHAR2(40)  NOT NULL
);

-- Perfiles de partida del modo ciudadano (pesos en %, suman 100).
CREATE TABLE nm_perfil (
  codigo       VARCHAR2(10)  CONSTRAINT nm_perfil_pk PRIMARY KEY,
  nombre       VARCHAR2(40)  NOT NULL,
  w_suelo      NUMBER(3)     NOT NULL,
  w_servicios  NUMBER(3)     NOT NULL,
  w_comercio   NUMBER(3)     NOT NULL,
  CONSTRAINT nm_perfil_suma_ck CHECK (w_suelo + w_servicios + w_comercio = 100)
);

-- Valores predefinidos para los perfiles
INSERT INTO nm_perfil VALUES ('EQ',    'Equilibrado', 34, 33, 33);
INSERT INTO nm_perfil VALUES ('FAM',   'Familia',     25, 55, 20);
INSERT INTO nm_perfil VALUES ('JOVEN', 'Joven',       55, 15, 30);
INSERT INTO nm_perfil VALUES ('TELE',  'Teletrabajo', 60, 25, 15);
COMMIT;

CREATE INDEX nm_cedu_ine_ix     ON nm_centro_educativo (municipio_ine);
CREATE INDEX nm_csan_ine_ix     ON nm_centro_sanitario (municipio_ine);
CREATE INDEX nm_parada_ine_ix   ON nm_parada (municipio_ine);
CREATE INDEX nm_comercio_ine_ix ON nm_comercio (municipio_ine);
