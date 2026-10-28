-- =============================================================================
-- NidoMadrid · 05c_chat_gemini.sql
-- El asistente usa Gemini (Google AI Studio, nivel gratuito) en lugar de OCI.
-- Sustituye SOLO los pasos A y C de 05_chat.sql. Los pasos B (comentarios),
-- E (registro) y F (ruta /chat) de 05_chat.sql se usan tal cual, porque el
-- perfil se sigue llamando NM_IA.
--
-- Necesitas una clave de API de https://aistudio.google.com (botón "Get API key").
-- La clave solo se guarda dentro de la base de datos: nunca va en la web.
-- Nivel gratuito: tiene límites de peticiones por minuto y por día, y Google
-- puede usar las peticiones para mejorar sus productos (los datos son públicos).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- PARTE 1 · Como ADMIN: permitir que NIDO llame a la API de Gemini
-- -----------------------------------------------------------------------------
BEGIN
  DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
    host => 'generativelanguage.googleapis.com',
    ace  => xs$ace_type(privilege_list => xs$name_list('http'),
                        principal_name => 'NIDO',
                        principal_type => xs_acl.ptype_db));
END;
/


-- -----------------------------------------------------------------------------
-- PARTE 2 · Como NIDO, bloque a bloque
-- -----------------------------------------------------------------------------

-- 2.1 · Credencial con la clave de Google AI Studio (suele empezar por AIza...)
BEGIN
  DBMS_CLOUD.CREATE_CREDENTIAL(
    credential_name => 'NM_GEMINI_CRED',
    username        => 'GOOGLE',
    password        => 'PEGA_AQUI_TU_CLAVE_DE_AI_STUDIO');
END;
/
-- Si te equivocas: EXEC DBMS_CLOUD.DROP_CREDENTIAL('NM_GEMINI_CRED');  y vuelve a crearla.


-- 2.2 · Quitar los perfiles de las pruebas anteriores
--       (si alguno no existe, ese EXEC da error: ignóralo y sigue)
EXEC DBMS_CLOUD_AI.DROP_PROFILE('NM_IA');
EXEC DBMS_CLOUD_AI.DROP_PROFILE('NM_IA_MAD');


-- 2.3 · Perfil NM_IA con Gemini. Mismo nombre que antes: la ruta /chat no cambia.
--       "gemini-flash-latest" apunta siempre al Flash vigente, así no depende de
--       que Google retire una versión concreta. Si da "model not found", pon el
--       nombre exacto de un modelo Flash que veas en AI Studio, por ejemplo:
--       EXEC DBMS_CLOUD_AI.SET_ATTRIBUTE('NM_IA', 'model', 'NOMBRE_DEL_MODELO');ç

BEGIN
  DBMS_CLOUD_AI.CREATE_PROFILE(
    profile_name => 'NM_IA',
    attributes   => '{
      "provider":            "google",
      "credential_name":     "NM_GEMINI_CRED",
      "model":               "gemini-flash-latest",   
      "object_list":         [{"owner": "NIDO", "name": "V_NM_WEB"}],
      "enforce_object_list": true,
      "comments":            true,
      "temperature":         0,
      "max_tokens":          800
    }');
END;
/

-- FIXME: cambiar y poner estos dos de abajo
EXEC DBMS_CLOUD_AI.SET_ATTRIBUTE('NM_IA', 'model', 'gemini-3.5-flash-lite');
EXEC DBMS_CLOUD_AI.SET_ATTRIBUTE('NM_IA', 'max_tokens', '4096');

-- 2.4 · Prueba (con "Ejecutar sentencia", Ctrl+Intro, de una en una)
SELECT DBMS_LOB.SUBSTR(DBMS_CLOUD_AI.GENERATE(
         prompt       => '¿Qué 5 municipios de menos de 20.000 habitantes tienen mejor puntuación de servicios?',
         profile_name => 'NM_IA',
         action       => 'showsql'), 4000, 1) AS sql_generado
FROM dual;

SELECT DBMS_LOB.SUBSTR(DBMS_CLOUD_AI.GENERATE(
         prompt       => '¿Qué 5 municipios de menos de 20.000 habitantes tienen mejor puntuación de servicios? Responde en español.',
         profile_name => 'NM_IA',
         action       => 'narrate'), 4000, 1) AS respuesta
FROM dual;

-- Si las dos funcionan: ejecuta los pasos B (si no los ejecutaste ya), E y F de 05_chat.sql.
