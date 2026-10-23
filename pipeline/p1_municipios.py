"""Etapa 1 · nm_municipio: padrón 2025 + límites IGN + Red Natura 2000."""
import json, glob
import pandas as pd, geopandas as gpd
from shapely.geometry import Point
from comun import F, OUT, CRS, municipios, norm, save

mun = municipios()

# Padrón 1-ene-2025 (INE, tabla 2881). Fichero en Windows-1252 con miles separados por punto.
p = pd.read_csv(glob.glob(f"{F}/padron*/*.csv")[0], sep=";", encoding="cp1252", dtype=str)
p["ine"] = p["Municipios"].str.extract(r"^(\d{5})\s")[0]
p = p.dropna(subset=["ine"])
p["nombre"] = p["Municipios"].str.replace(r"^\d{5}\s+", "", regex=True)
# "Acebeda, La" -> "La Acebeda"
p["nombre"] = p["nombre"].str.replace(r"^(.*), (El|La|Los|Las)$", r"\2 \1", regex=True)
p["poblacion"] = p["Total"].str.replace(".", "", regex=False).astype(int)
p["poblacion_anio"] = p["Periodo"].astype(int)
mun = mun.merge(p[["ine", "nombre", "poblacion", "poblacion_anio"]], on="ine", how="left")
assert mun.poblacion.notna().all(), mun[mun.poblacion.isna()]

mun["superficie_km2"] = (mun.area / 1e6).round(2)
sol = gpd.GeoSeries([Point(-3.70379, 40.41678)], crs="EPSG:4326").to_crs(CRS).iloc[0]
mun["dist_sol_km"] = (mun.centroid.distance(sol) / 1000).round(1)
mun.loc[mun.ine == "28079", "dist_sol_km"] = 0.0

# Red Natura 2000: unión de LIC/ZEC y ZEPA, sin contar dos veces el solape.
rn = pd.concat([gpd.read_file(glob.glob(f"{F}/IDEM_MA_RED_NATURA_LIC_ZEC/*.shp")[0]).to_crs(CRS),
                gpd.read_file(glob.glob(f"{F}/IDEM_MA_RED_NATURA_ZEPA/*.shp")[0]).to_crs(CRS)])
rn_union = rn.geometry.make_valid().union_all()
mun["pct_protegido"] = (mun.geometry.intersection(rn_union).area / mun.area * 100).round(1)

# Zona aproximada (misma regla que el prototipo), solo para filtrar en la web.
zonas = {m["ine"]: m["zona"] for m in json.load(open("/home/claude/nido/data.json"))["municipios"]}
mun["zona"] = mun.ine.map(zonas)

cols = ["ine", "nombre", "zona", "poblacion", "poblacion_anio", "superficie_km2", "dist_sol_km", "pct_protegido"]
save(mun[cols].sort_values("ine"), "nm_municipio")

# Geometría simplificada para la web (WGS84).
w = mun[["ine", "geometry"]].copy()
w["geometry"] = w.geometry.simplify(120, preserve_topology=True)
w.to_crs("EPSG:4326").to_file("/home/claude/nido/real/municipios_web.geojson", driver="GeoJSON",
                              COORDINATE_PRECISION=4)
mun[["ine", "nombre", "nombre_ign", "poblacion"]].to_csv("/home/claude/nido/real/municipios_ref.csv", index=False)

print(len(mun), "municipios ·", mun.poblacion.sum(), "hab. ·",
      f"{rn_union.area/1e6:.0f} km² Red Natura")
print(mun.sort_values("pct_protegido", ascending=False)[["nombre", "pct_protegido"]].head(6).to_string(index=False))
