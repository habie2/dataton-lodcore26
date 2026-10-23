-- =============================================================================
-- NidoMadrid · 04_api_rest.sql   (ejecutar como NIDO, con "Run Script")
-- Publica los resultados de Oracle como API REST pública de solo lectura (ORDS).
--   GET .../ords/nido/nidomadrid/municipios   -> los 179 municipios (V_NM_WEB)
--   GET .../ords/nido/nidomadrid/perfiles     -> perfiles de pesos (NM_PERFIL)
--   GET .../ords/nido/nidomadrid/ranking?w1=25&w2=55&w3=20  -> ranking calculado en Oracle
-- =============================================================================
BEGIN
  ORDS.DEFINE_MODULE(
    p_module_name    => 'nidomadrid',
    p_base_path      => '/nidomadrid/',
    p_items_per_page => 0,
    p_status         => 'PUBLISHED',
    p_comments       => 'API pública de NidoMadrid');

  ORDS.DEFINE_TEMPLATE(p_module_name => 'nidomadrid', p_pattern => 'municipios');
  ORDS.DEFINE_HANDLER(
    p_module_name    => 'nidomadrid',
    p_pattern        => 'municipios',
    p_method         => 'GET',
    p_source_type    => ORDS.source_type_collection_feed,
    p_items_per_page => 0,
    p_source         => 'SELECT * FROM v_nm_web ORDER BY municipio_ine');

  ORDS.DEFINE_TEMPLATE(p_module_name => 'nidomadrid', p_pattern => 'perfiles');
  ORDS.DEFINE_HANDLER(
    p_module_name    => 'nidomadrid',
    p_pattern        => 'perfiles',
    p_method         => 'GET',
    p_source_type    => ORDS.source_type_collection_feed,
    p_items_per_page => 0,
    p_source         => 'SELECT codigo, nombre, w_suelo, w_servicios, w_comercio FROM nm_perfil ORDER BY codigo');

  ORDS.DEFINE_TEMPLATE(p_module_name => 'nidomadrid', p_pattern => 'ranking');
  ORDS.DEFINE_HANDLER(
    p_module_name    => 'nidomadrid',
    p_pattern        => 'ranking',
    p_method         => 'GET',
    p_source_type    => ORDS.source_type_collection_feed,
    p_items_per_page => 0,
    p_source         => q'[
      SELECT municipio_ine, nombre, poblacion, suelo, servicios, comercio,
             ROUND((:w1 * suelo + :w2 * servicios + :w3 * comercio) / NULLIF(:w1 + :w2 + :w3, 0), 1) AS indice,
             RANK() OVER (ORDER BY (:w1 * suelo + :w2 * servicios + :w3 * comercio) DESC) AS puesto
      FROM v_nm_dimensiones
      ORDER BY puesto]');

  COMMIT;
END;
/

-- Si la web alojada en otro dominio no consigue leer la API (error CORS en la
-- consola del navegador), autoriza ese origen. Ejemplo para Object Storage en Madrid:
-- BEGIN
--   ORDS.SET_MODULE_ORIGINS_ALLOWED(
--     p_module_name     => 'nidomadrid',
--     p_origins_allowed => 'https://objectstorage.eu-madrid-1.oraclecloud.com');
--   COMMIT;
-- END;
-- /
