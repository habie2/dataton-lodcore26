"""Etapa 4 · nm_comercio: tiendas de OpenStreetMap (shop=*) con su categoría."""
import glob
import osmium, pandas as pd
from comun import F, OUT, points_to_ine, municipios, save

EXCLUIR = {"vacant", "no", "disused", "abandoned", "closed", "empty", "none", "yes;vacant"}


class Shops(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []

    def _add(self, kind, oid, tags, lon, lat):
        v = tags.get("shop")
        if not v:
            return
        v = v.strip().lower().split(";")[0][:40]
        if v in EXCLUIR:
            return
        self.rows.append((f"{kind}{oid}", v, lon, lat))

    def node(self, n):
        if "shop" in n.tags and n.location.valid():
            self._add("n", n.id, n.tags, n.location.lon, n.location.lat)

    def area(self, a):  # edificios y recintos etiquetados como tienda
        if "shop" not in a.tags:
            return
        try:
            lons, lats = zip(*[(nd.lon, nd.lat) for ring in a.outer_rings() for nd in ring])
        except Exception:
            return
        kind, oid = ("w", a.orig_id()) if a.from_way() else ("r", a.orig_id())
        self._add(kind, oid, a.tags, sum(lons) / len(lons), sum(lats) / len(lats))


h = Shops()
h.apply_file(glob.glob(f"{F}/*osm/*.pbf")[0], locations=True)
df = pd.DataFrame(h.rows, columns=["osm_id", "categoria", "lon", "lat"]).drop_duplicates("osm_id")
df["ine"] = points_to_ine(df, "lon", "lat", "EPSG:4326", municipios()).values
df = df.dropna(subset=["ine"])
save(df[["osm_id", "ine", "categoria"]], "nm_comercio")
print(f"OSM: {len(df)} comercios en {df.ine.nunique()} municipios · {df.categoria.nunique()} categorías")
print(df.categoria.value_counts().head(15).to_dict())
