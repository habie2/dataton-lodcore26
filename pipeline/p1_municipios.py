"""Etapa 1 · carga/nm_municipio.csv

Fuentes
  * Padrón continuo a 1-1-2025, INE tabla 2881 (CSV separado por ';', codificación Windows-1252).
  * Límites municipales IGN (EGRN_Municipios_WM_20201021.zip, MIVAU).
  * Red Natura 2000 de la Comunidad de Madrid: LIC/ZEC y ZEPA (WFS en SHAPE-ZIP).
  * Municipios de la Comunidad de Madrid (municipio_comunidad_madrid.csv, Comunidad de Madrid,
    CSV ';', Windows-1252): zona estadística oficial de cada municipio (nivel NUTS4).

Reglas
  R1.1  Se toman las filas cuyo campo Municipios empieza por un código de 5 dígitos.
        Se descarta la fila de total provincial ("28 Madrid").
  R1.2  municipio_ine = esos 5 dígitos. nombre = el texto que sigue, con el artículo
        pospuesto pasado delante ("Acebeda, La" -> "La Acebeda").
  R1.3  poblacion = campo Total sin el punto de miles ("3.506.730" -> 3506730).
  R1.4  Se exige que los 179 municipios del IGN tengan población (si falta uno, se detiene).
  R1.5  superficie_km2 = área del polígono IGN en ETRS89/UTM30N, en km², 2 decimales.
  R1.6  dist_sol_km = distancia del centroide del polígono a la Puerta del Sol
        (40.41678 N, -3.70379 E), en km, 1 decimal. Madrid capital = 0.
  R1.7  pct_protegido = % del término dentro de Red Natura 2000. LIC/ZEC y ZEPA se unen
        antes de medir, para no contar dos veces las zonas que son ambas cosas.
  R1.8  zona_codigo / zona = nuts4_codigo / nuts4_nombre del fichero de municipios de la
        Comunidad (11 zonas estadísticas oficiales). Se cruza por los 5 primeros dígitos de
        municipio_codigo_ine (6 cifras = INE + dígito de control: "280796" -> 28079).
        Se exige que crucen los 179 municipios.
"""
import os
import pandas as pd, geopandas as gpd
from shapely.geometry import Point
from comun import CRS, WEB, fuente, leer_shp_zip, municipios, save

mun = municipios()

# R1.1 - R1.3 · padrón
p = pd.read_csv(fuente("*padron*.csv", "*2881*.csv"), sep=";", encoding="cp1252", dtype=str)
p["ine"] = p["Municipios"].str.extract(r"^(\d{5})\s")[0]
p = p.dropna(subset=["ine"])
p["nombre"] = p["Municipios"].str.replace(r"^\d{5}\s+", "", regex=True)
p["nombre"] = p["nombre"].str.replace(r"^(.*), (El|La|Los|Las)$", r"\2 \1", regex=True)
p["poblacion"] = p["Total"].str.replace(".", "", regex=False).astype(int)
p["poblacion_anio"] = p["Periodo"].astype(int)
mun = mun.merge(p[["ine", "nombre", "poblacion", "poblacion_anio"]], on="ine", how="left")
# R1.4
assert mun.poblacion.notna().all(), mun[mun.poblacion.isna()]

# R1.5 - R1.6
mun["superficie_km2"] = (mun.area / 1e6).round(2)
sol = gpd.GeoSeries([Point(-3.70379, 40.41678)], crs="EPSG:4326").to_crs(CRS).iloc[0]
mun["dist_sol_km"] = (mun.centroid.distance(sol) / 1000).round(1)
mun.loc[mun.ine == "28079", "dist_sol_km"] = 0.0

# R1.7 · Red Natura 2000
rn = pd.concat([leer_shp_zip(fuente("*RED_NATURA_LIC_ZEC*.zip")).to_crs(CRS),
                leer_shp_zip(fuente("*RED_NATURA_ZEPA*.zip")).to_crs(CRS)])
rn_union = rn.geometry.make_valid().union_all()
mun["pct_protegido"] = (mun.geometry.intersection(rn_union).area / mun.area * 100).round(1)

# R1.8 · zona estadística oficial (NUTS4)
z = pd.read_csv(fuente("*municipio_comunidad_madrid*.csv"), sep=";", encoding="cp1252", dtype=str)
z["ine"] = z.municipio_codigo_ine.str.strip().str[:5]
z = z.set_index("ine")
mun["zona_codigo"] = mun.ine.map(z.nuts4_codigo.str.strip())
mun["zona"] = mun.ine.map(z.nuts4_nombre.str.strip())
assert mun.zona.notna().all(), mun[mun.zona.isna()]

cols = ["ine", "nombre", "zona_codigo", "zona", "poblacion", "poblacion_anio", "superficie_km2", "dist_sol_km", "pct_protegido"]
save(mun[cols].sort_values("ine"), "nm_municipio")

# Geometría simplificada (tolerancia 120 m) para pintar el mapa de la web. No va a Oracle.
w = mun[["ine", "geometry"]].copy()
w["geometry"] = w.geometry.simplify(120, preserve_topology=True)
w.to_crs("EPSG:4326").to_file(os.path.join(WEB, "municipios_web.geojson"), driver="GeoJSON", COORDINATE_PRECISION=4)

print(f"nm_municipio: {len(mun)} municipios · {mun.poblacion.sum()} hab. · Red Natura {rn_union.area/1e6:.0f} km²")
