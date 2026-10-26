"""Etapa 4 · carga/nm_comercio.csv

Fuente
  * Extracto de OpenStreetMap de la Comunidad de Madrid (Geofabrik, madrid-*.osm.pbf).

Reglas
  R4.1  Se toman los nodos y las áreas (edificios o recintos) con la etiqueta shop=*.
  R4.2  categoria = valor de shop en minúsculas; si trae varios separados por ';', el primero;
        recortado a 40 caracteres.
  R4.3  Se excluyen los valores que no son un comercio en funcionamiento:
        vacant, no, disused, abandoned, closed, empty, none.
  R4.4  Posición: el nodo; en las áreas, la media de las coordenadas de su contorno exterior.
  R4.5  municipio_ine por punto en polígono; los que caen fuera de Madrid se descartan.
  R4.6  osm_id = "n" (nodo), "w" (vía) o "r" (relación) + identificador OSM; sin repetidos.
"""
import osmium
import pandas as pd
from comun import fuente, municipios, points_to_ine, save

EXCLUIR = {"vacant", "no", "disused", "abandoned", "closed", "empty", "none", "yes;vacant"}


class Tiendas(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []

    def _add(self, kind, oid, tags, lon, lat):
        v = tags.get("shop")
        if not v:
            return
        v = v.strip().lower().split(";")[0][:40]                    # R4.2
        if v in EXCLUIR:                                             # R4.3
            return
        self.rows.append((f"{kind}{oid}", v, lon, lat))             # R4.6

    def node(self, n):                                               # R4.1
        if "shop" in n.tags and n.location.valid():
            self._add("n", n.id, n.tags, n.location.lon, n.location.lat)

    def area(self, a):                                               # R4.1 · R4.4
        if "shop" not in a.tags:
            return
        try:
            lons, lats = zip(*[(nd.lon, nd.lat) for ring in a.outer_rings() for nd in ring])
        except Exception:
            return
        kind = "w" if a.from_way() else "r"
        self._add(kind, a.orig_id(), a.tags, sum(lons) / len(lons), sum(lats) / len(lats))


h = Tiendas()
h.apply_file(fuente("*osm*.pbf"), locations=True)
df = pd.DataFrame(h.rows, columns=["osm_id", "categoria", "lon", "lat"]).drop_duplicates("osm_id")
df["ine"] = points_to_ine(df, "lon", "lat", "EPSG:4326", municipios()).values      # R4.5
df = df.dropna(subset=["ine"])
save(df[["osm_id", "ine", "categoria"]], "nm_comercio")
print(f"nm_comercio: {len(df)} comercios en {df.ine.nunique()} municipios · {df.categoria.nunique()} categorías")
