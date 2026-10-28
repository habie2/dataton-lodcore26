-- =============================================================================
-- NidoMadrid · 05_chat.sql   (ejecutar como NIDO, por bloques, en este orden)
-- Asistente "Pregunta a los datos" con Select AI + OCI Generative AI.
--
--   pregunta (web) ─POST─► ORDS /nidomadrid/chat ─► DBMS_CLOUD_AI.GENERATE
--                                                    1. pregunta → SQL (LLM)
--                                                    2. ejecuta el SQL sobre V_NM_WEB
--                                                    3. redacta la respuesta (LLM)
--
-- Antes de empezar necesitas (ver la guía): tu clave de API de OCI (user OCID,
-- tenancy OCID, fingerprint y clave privada), el OCID del compartimento y la
-- región donde tengas OCI Generative AI (por defecto, Frankfurt).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- PASO A · Credencial con tu clave de API
-- Pega los valores de tu clave. En private_key va el contenido del .pem SIN las
-- líneas "-----BEGIN PRIVATE KEY-----" / "-----END PRIVATE KEY-----" y sin saltos
-- de línea (todo seguido).
-- -----------------------------------------------------------------------------
BEGIN
  DBMS_CLOUD.CREATE_CREDENTIAL(
    credential_name => 'NM_GENAI_CRED',
    user_ocid       => 'ocid1.user.oc1..PEGA_AQUI',
    tenancy_ocid    => 'ocid1.tenancy.oc1..PEGA_AQUI',
    private_key     => 'PEGA_AQUI_LA_CLAVE_PRIVADA_SIN_CABECERAS',
    fingerprint     => 'aa:bb:cc:...');
END;
/
-- Si te equivocas: EXEC DBMS_CLOUD.DROP_CREDENTIAL('NM_GENAI_CRED');  y vuelve a crearla.


-- -----------------------------------------------------------------------------
-- PASO B · Descripción de la vista para el modelo
-- Select AI envía estos comentarios al LLM ("comments": true): es lo que más
-- mejora la calidad del SQL generado.
-- -----------------------------------------------------------------------------
COMMENT ON TABLE v_nm_web IS 'Una fila por cada uno de los 179 municipios de la Comunidad de Madrid con los indicadores del índice NidoMadrid de preparación para acoger nueva población. Todas las puntuaciones van de 0 a 100 (más es mejor).';
COMMENT ON COLUMN v_nm_web.municipio_ine        IS 'Código INE del municipio, 5 dígitos (28079 = Madrid)';
COMMENT ON COLUMN v_nm_web.nombre               IS 'Nombre oficial del municipio';
COMMENT ON COLUMN v_nm_web.zona_codigo          IS 'Código de la zona estadística NUTS4 de la Comunidad de Madrid';
COMMENT ON COLUMN v_nm_web.zona                 IS 'Zona estadística: Municipio de Madrid, Norte/Este/Sur/Oeste Metropolitano, Sierra Norte, Sierra Central, Sierra Sur, Nordeste, Sudeste o Sudoeste Comunidad';
COMMENT ON COLUMN v_nm_web.poblacion            IS 'Habitantes según el padrón a 1 de enero';
COMMENT ON COLUMN v_nm_web.poblacion_anio       IS 'Año del padrón';
COMMENT ON COLUMN v_nm_web.km2                  IS 'Superficie del término municipal en km2';
COMMENT ON COLUMN v_nm_web.dist_km              IS 'Distancia en km del centro del municipio a la Puerta del Sol';
COMMENT ON COLUMN v_nm_web.protegido_pct        IS 'Porcentaje del término municipal dentro de la Red Natura 2000';
COMMENT ON COLUMN v_nm_web.suelo_libre_ha       IS 'Hectáreas estimadas de suelo urbano sin edificar (Catastro)';
COMMENT ON COLUMN v_nm_web.parcelas_sin_edificar IS 'Número de parcelas urbanas sin edificar (Catastro)';
COMMENT ON COLUMN v_nm_web.alquiler_m2          IS 'Alquiler mediano en euros por m2 al mes';
COMMENT ON COLUMN v_nm_web.alquiler_origen      IS 'SERPAVI si el alquiler es dato oficial, IMPUTADO si se estimó con la mediana de su zona';
COMMENT ON COLUMN v_nm_web.alquiler_anio        IS 'Año del dato de alquiler';
COMMENT ON COLUMN v_nm_web.centros_edu          IS 'Número de centros educativos de infantil, primaria, secundaria o FP';
COMMENT ON COLUMN v_nm_web.etapas_edu           IS 'Etapas educativas presentes en el municipio, de 0 a 4 (infantil, primaria, secundaria, FP)';
COMMENT ON COLUMN v_nm_web.edu_1000             IS 'Centros educativos por 1.000 habitantes';
COMMENT ON COLUMN v_nm_web.puntos_salud         IS 'Número de consultorios locales y centros de salud de atención primaria';
COMMENT ON COLUMN v_nm_web.nivel_salud          IS 'Mayor nivel sanitario del municipio: 0 ninguno, 1 consultorio, 2 centro de salud, 3 urgencias extrahospitalarias, 4 hospital';
COMMENT ON COLUMN v_nm_web.salud_1000           IS 'Centros de salud equivalentes por 1.000 habitantes';
COMMENT ON COLUMN v_nm_web.paradas              IS 'Número de paradas de transporte público (Metro, Cercanías, Metro Ligero, autobús)';
COMMENT ON COLUMN v_nm_web.salidas_dia          IS 'Pasos de vehículo de transporte público por las paradas del municipio en un día laborable';
COMMENT ON COLUMN v_nm_web.salidas_1000         IS 'Pasos de vehículo al día por 1.000 habitantes';
COMMENT ON COLUMN v_nm_web.ferroviario          IS '1 si tiene Metro, Cercanías o Metro Ligero; 0 si no';
COMMENT ON COLUMN v_nm_web.nivel_transporte     IS 'Nivel de transporte de 0 a 4';
COMMENT ON COLUMN v_nm_web.comercios            IS 'Número de comercios registrados en OpenStreetMap';
COMMENT ON COLUMN v_nm_web.comercio_1000        IS 'Comercios por 1.000 habitantes';
COMMENT ON COLUMN v_nm_web.categorias           IS 'Número de tipos de tienda distintos';
COMMENT ON COLUMN v_nm_web.n_suelo_libre        IS 'Puntuación 0-100 de suelo sin edificar';
COMMENT ON COLUMN v_nm_web.n_alquiler           IS 'Puntuación 0-100 de alquiler (más alta = más barato)';
COMMENT ON COLUMN v_nm_web.n_edu                IS 'Puntuación 0-100 de educación';
COMMENT ON COLUMN v_nm_web.n_salud              IS 'Puntuación 0-100 de sanidad';
COMMENT ON COLUMN v_nm_web.n_transporte         IS 'Puntuación 0-100 de transporte';
COMMENT ON COLUMN v_nm_web.n_comercio           IS 'Puntuación 0-100 de comercio';
COMMENT ON COLUMN v_nm_web.suelo                IS 'Dimensión suelo y vivienda del índice, 0-100';
COMMENT ON COLUMN v_nm_web.servicios            IS 'Dimensión servicios públicos del índice (educación, sanidad, transporte), 0-100';
COMMENT ON COLUMN v_nm_web.comercio             IS 'Dimensión comercio del índice, 0-100';
COMMENT ON COLUMN v_nm_web.modo                 IS 'Recomendación para la administración: EDIFICAR, MEJORAR_SERVICIOS o SIN_ACCION';
COMMENT ON COLUMN v_nm_web.carencia             IS 'Servicio más débil del municipio: EDUCACION, SANIDAD o TRANSPORTE';
COMMENT ON COLUMN v_nm_web.med_suelo            IS 'Mediana regional de la dimensión suelo (igual en todas las filas)';
COMMENT ON COLUMN v_nm_web.med_servicios        IS 'Mediana regional de la dimensión servicios (igual en todas las filas)';
COMMENT ON COLUMN v_nm_web.med_comercio         IS 'Mediana regional de la dimensión comercio (igual en todas las filas)';


-- -----------------------------------------------------------------------------
-- PASO C · Perfil de IA
-- Cambia oci_compartment_id por el OCID de tu compartimento. Si tu región de
-- Generative AI no es Frankfurt, cambia "region" (y el modelo si hace falta).
-- -----------------------------------------------------------------------------
BEGIN
  DBMS_CLOUD_AI.CREATE_PROFILE(
    profile_name => 'NM_IA',
    attributes   => '{
      "provider":            "oci",
      "credential_name":     "NM_GENAI_CRED",
      "region":              "eu-frankfurt-1",
      "oci_compartment_id":  "ocid1.compartment.oc1..PEGA_AQUI",
      "model":               "meta.llama-3.3-70b-instruct",
      "object_list":         [{"owner": "NIDO", "name": "V_NM_WEB"}],
      "enforce_object_list": true,
      "comments":            true,
      "temperature":         0,
      "max_tokens":          800
    }');
END;
/
-- Para cambiar algo después:  EXEC DBMS_CLOUD_AI.DROP_PROFILE('NM_IA');  y vuelve a crearlo.


-- -----------------------------------------------------------------------------
-- PASO D · Prueba en la hoja SQL (antes de publicarlo)
-- -----------------------------------------------------------------------------
SELECT DBMS_CLOUD_AI.GENERATE(
         prompt       => '¿Qué 5 municipios de menos de 20.000 habitantes tienen mejor puntuación de servicios?',
         profile_name => 'NM_IA',
         action       => 'showsql') AS sql_generado
FROM dual;

SELECT DBMS_CLOUD_AI.GENERATE(
         prompt       => '¿Qué 5 municipios de menos de 20.000 habitantes tienen mejor puntuación de servicios? Responde en español.',
         profile_name => 'NM_IA',
         action       => 'narrate') AS respuesta
FROM dual;


-- -----------------------------------------------------------------------------
-- PASO E · Registro de uso (y tope diario para proteger los créditos)
-- -----------------------------------------------------------------------------
CREATE TABLE nm_chat_log (
  id          NUMBER GENERATED ALWAYS AS IDENTITY CONSTRAINT nm_chat_log_pk PRIMARY KEY,
  creado      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
  pregunta    VARCHAR2(500) NOT NULL,
  sql_gen     CLOB,
  respuesta   CLOB,
  error       VARCHAR2(4000)
);


-- -----------------------------------------------------------------------------
-- PASO F · Ruta de la API: POST .../ords/nido/nidomadrid/chat
-- Cuerpo: {"pregunta": "..."}   Respuesta: {"respuesta": "...", "sql": "..."}
-- La web lo envía como text/plain para evitar la petición previa de CORS.
-- Se puede volver a ejecutar: ORDS.DEFINE_* sustituye la ruta si ya existe.
-- -----------------------------------------------------------------------------
BEGIN
  ORDS.DEFINE_TEMPLATE(p_module_name => 'nidomadrid', p_pattern => 'chat');
  ORDS.DEFINE_HANDLER(
    p_module_name => 'nidomadrid',
    p_pattern     => 'chat',
    p_method      => 'POST',
    p_source_type => ORDS.source_type_plsql,
    p_source      => q'[
DECLARE
  c_max_dia CONSTANT PLS_INTEGER := 100;          -- tope de preguntas en 24 h
  l_preg    VARCHAR2(500);
  l_sql     CLOB;
  l_resp    CLOB;
  l_json    CLOB;
  l_usadas  PLS_INTEGER;
  l_status  PLS_INTEGER := 200;
  l_err     VARCHAR2(4000);
  i         PLS_INTEGER := 1;
BEGIN
  -- Todo el trabajo va dentro de este bloque: cualquier error se registra en
  -- NM_CHAT_LOG y se devuelve como JSON (nunca un error 555 de ORDS).
  BEGIN
    l_preg := SUBSTR(TRIM(JSON_VALUE(:body_text, '$.pregunta')), 1, 400);
    IF l_preg IS NULL OR LENGTH(l_preg) < 5 THEN
      l_status := 400;
      l_json   := '{"error":"Escribe una pregunta de al menos 5 caracteres."}';
    ELSE
      SELECT COUNT(*) INTO l_usadas FROM nm_chat_log WHERE creado > SYSTIMESTAMP - INTERVAL '1' DAY;
      IF l_usadas >= c_max_dia THEN
        l_status := 429;
        l_json   := '{"error":"Se ha alcanzado el límite diario de preguntas. Vuelve a intentarlo mañana."}';
      ELSE
        l_sql  := DBMS_CLOUD_AI.GENERATE(prompt => l_preg, profile_name => 'NM_IA', action => 'showsql');
        l_resp := DBMS_CLOUD_AI.GENERATE(
                    prompt       => l_preg || ' Responde en español, en pocas frases y sin inventar datos que no estén en la consulta.',
                    profile_name => 'NM_IA',
                    action       => 'narrate');
        INSERT INTO nm_chat_log (pregunta, sql_gen, respuesta) VALUES (l_preg, l_sql, l_resp);
        COMMIT;
        SELECT JSON_OBJECT('respuesta' VALUE l_resp, 'sql' VALUE l_sql RETURNING CLOB) INTO l_json FROM dual;
      END IF;
    END IF;
  EXCEPTION WHEN OTHERS THEN
    l_err := SUBSTR(SQLERRM, 1, 4000);
    ROLLBACK;
    INSERT INTO nm_chat_log (pregunta, error) VALUES (NVL(l_preg, '(sin pregunta)'), l_err);
    COMMIT;
    l_status := 502;
    l_json   := '{"error":"El asistente no ha podido responder a esa pregunta. Prueba a formularla de otra manera."}';
  END;

  -- Respuesta HTTP: estado, cabecera y cuerpo JSON (en trozos, por si es largo)
  OWA_UTIL.STATUS_LINE(l_status, NULL, FALSE);
  OWA_UTIL.MIME_HEADER('application/json', FALSE, 'UTF-8');
  OWA_UTIL.HTTP_HEADER_CLOSE;
  WHILE i <= NVL(DBMS_LOB.GETLENGTH(l_json), 0) LOOP
    HTP.PRN(DBMS_LOB.SUBSTR(l_json, 8000, i));
    i := i + 8000;
  END LOOP;
END;]');
  COMMIT;
END;
/


-- -----------------------------------------------------------------------------
-- Consultas útiles durante el desarrollo
-- -----------------------------------------------------------------------------
-- Últimas preguntas, con el SQL generado y los errores:
--   SELECT creado, pregunta, error, DBMS_LOB.SUBSTR(sql_gen, 400) sql_gen
--   FROM nm_chat_log ORDER BY creado DESC FETCH FIRST 20 ROWS ONLY;
-- Apagar el asistente de inmediato (la web mostrará el aviso de error):
--   BEGIN ORDS.DELETE_TEMPLATE(p_module_name => 'nidomadrid', p_pattern => 'chat'); COMMIT; END;
--   /
