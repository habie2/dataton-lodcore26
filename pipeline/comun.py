"""Utilidades compartidas del pipeline NidoMadrid."""
import unicodedata, re, os
import geopandas as gpd

BASE = "/home/claude/nido"
F = f"{BASE}/fuentes"
OUT = f"{BASE}/oracle/carga"
os.makedirs(OUT, exist_ok=True)
CRS = "EPSG:25830"  # ETRS89 / UTM 30N, metros


def norm(s: str) -> str:
    """Nombre de municipio normalizado para cruzar por nombre."""
    s = str(s).lower().strip()
    # "Acebeda (La)" / "Acebeda, La" -> "la acebeda"
    m = re.match(r"^(.*?)[,(]\s*(el|la|los|las)\)?$", s)
    if m:
        s = f"{m.group(2)} {m.group(1).strip()}"
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(w for w in s.split() if w not in ("el", "la", "los", "las", "de", "del", "y"))


def municipios():
    g = gpd.read_file(f"{F}/EGRN_Municipios_WM_20201021/EGRN_Municipios_WM_20201021.shp")
    g = g[g.CodINE.astype(str).str.startswith("28")].to_crs(CRS)
    g = g.rename(columns={"CodINE": "ine", "NAMEUNIT": "nombre_ign"})[["ine", "nombre_ign", "geometry"]]
    return g.reset_index(drop=True)


ALIAS = {  # nombres de catálogos que no coinciden con el oficial
    "lozoyuela navas sieteiglesias": "lozoyuela navas sieteiglesias",
    "san lorenzo escorial": "san lorenzo escorial",
}


def name_index(mun_df):
    """dict nombre normalizado -> INE (a partir de nm_municipio)."""
    idx = {norm(n): i for i, n in zip(mun_df.ine, mun_df.nombre)}
    for i, n in zip(mun_df.ine, mun_df.nombre_ign):
        idx.setdefault(norm(n), i)
    return idx


def points_to_ine(df, x, y, crs, mun=None):
    """Asigna INE por punto en polígono. Devuelve serie de INE (NaN fuera de la Comunidad)."""
    mun = municipios() if mun is None else mun
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[x], df[y]), crs=crs).to_crs(CRS)
    j = gpd.sjoin(pts, mun[["ine", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    return j["ine"]


def save(df, name):
    """Escribe un CSV de carga para Oracle (la columna ine se publica como municipio_ine)."""
    df.rename(columns={"ine": "municipio_ine"}).to_csv(f"{OUT}/{name}.csv", index=False)


def load_mun():
    import pandas as pd
    return pd.read_csv(f"{OUT}/nm_municipio.csv", dtype={"municipio_ine": str}).rename(columns={"municipio_ine": "ine"})
