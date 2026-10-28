-- =============================================================================
-- NidoMadrid · 05_chat_admin.sql   (ejecutar como ADMIN, una sola vez)
-- Da a NIDO permiso para usar Select AI y guardar credenciales de OCI.
-- (OCI Generative AI no necesita abrir ACL de red.)
-- =============================================================================
GRANT EXECUTE ON DBMS_CLOUD_AI TO nido;
GRANT EXECUTE ON DBMS_CLOUD    TO nido;
