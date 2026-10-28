/* Configuración de NidoMadrid: lo único que hay que editar al publicar la web.
   API_URL: dirección de la ruta "municipios" de tu API REST de Oracle (04_api_rest.sql). */
const CONFIG = {
  API_URL:
    "https://g0c7419060d3399-nidomadrid.adb.eu-madrid-1.oraclecloudapps.com/ords/nido/nidomadrid/municipios", // p. ej. 'https://XXXX-nidomadrid.adb.eu-madrid-1.oraclecloudapps.com/ords/nido/nidomadrid/municipios'
  GEO_URL: "datos/municipios.geojson", // contornos de los municipios (IGN), relativo a index.html
  CHAT_URL:
    "https://g0c7419060d3399-nidomadrid.adb.eu-madrid-1.oraclecloudapps.com/ords/nido/nidomadrid/chat", // ruta "chat" del asistente (05_chat.sql); vacía = sin burbuja de chat
};
