"""NidoMadrid · utilidades compartidas del pipeline de limpieza.

Estructura de carpetas esperada (todo relativo a la carpeta del proyecto):

    nidomadrid/
      fuentes/     <- los ficheros originales, tal como se descargan (sin descomprimir)
      pipeline/    <- estos scripts
      carga/       <- aquí se escriben los CSV que se cargan en Oracle
      salida_web/  <- geometría simplificada para la web

Convenciones de salida (iguales en todos los CSV de carga):
  * UTF-8, separador coma, cabecera con el nombre exacto de la columna en Oracle.
  * El código de municipio se llama municipio_ine: 5 dígitos INE como texto (28079).
  * Solo se escriben filas de los 179 municipios de la Comunidad de Madrid.
"""
import glob, os, re, unicodedata, zipfile
import geopandas as gpd
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(BASE, "fuentes")
OUT = os.path.join(BASE, "carga")
WEB = os.path.join(BASE, "salida_web")
TMP = os.path.join(F, "_descomprimido")
for d in (OUT, WEB, TMP):
    os.makedirs(d, exist_ok=True)

CRS = "EPSG:25830"  # ETRS89 / UTM huso 30N, en metros: se usa para áreas y distancias


def fuente(*patrones):
    """Devuelve la ruta del fichero de fuentes/ que encaje con alguno de los patrones."""
    for p in patrones:
        hits = sorted(glob.glob(os.path.join(F, "**", p), recursive=True))
        hits = [h for h in hits if "_descomprimido" not in h]
        if hits:
            return hits[0]
    raise FileNotFoundError(f"No encuentro en fuentes/ ningún fichero tipo {patrones}")


def descomprimir(zip_path):
    """Descomprime un zip en fuentes/_descomprimido/<nombre>/ (una sola vez) y devuelve la carpeta."""
    dest = os.path.join(TMP, os.path.splitext(os.path.basename(zip_path))[0])
    if not os.path.isdir(dest):
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(dest)
    return dest


def leer_shp_zip(zip_path):
    """Lee el primer .shp de un zip (formato en que lo sirven IGN/MIVAU y el WFS de la Comunidad)."""
    d = descomprimir(zip_path)
    shp = sorted(glob.glob(os.path.join(d, "**", "*.shp"), recursive=True))[0]
    return gpd.read_file(shp)


def norm(s) -> str:
    """Normaliza un nombre de municipio para poder cruzar catálogos que solo traen el nombre.

    Reglas: minúsculas; artículo pospuesto al principio ("Acebeda, La" / "Acebeda (La)"
    -> "la acebeda"); sin tildes ni diéresis; signos -> espacio; se eliminan las
    palabras vacías el, la, los, las, de, del, y.
    """
    s = str(s).lower().strip()
    m = re.match(r"^(.*?)[,(]\s*(el|la|los|las)\)?$", s)
    if m:
        s = f"{m.group(2)} {m.group(1).strip()}"
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(w for w in s.split() if w not in ("el", "la", "los", "las", "de", "del", "y"))


def municipios():
    """Polígonos oficiales (IGN, capa EGRN de MIVAU) de los 179 municipios de Madrid (código INE 28xxx)."""
    g = leer_shp_zip(fuente("EGRN_Municipios*.zip"))
    g = g[g.CodINE.astype(str).str.startswith("28")].to_crs(CRS)
    g = g.rename(columns={"CodINE": "ine", "NAMEUNIT": "nombre_ign"})[["ine", "nombre_ign", "geometry"]]
    assert len(g) == 179, f"Se esperaban 179 municipios y hay {len(g)}"
    return g.reset_index(drop=True)


def points_to_ine(df, x, y, crs, mun):
    """Asigna a cada punto el municipio cuyo polígono lo contiene (punto en polígono).

    Puntos fuera de la Comunidad de Madrid -> NaN (el llamador los descarta).
    Si un punto cae justo en una frontera y toca dos polígonos, se queda con el primero.
    """
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[x], df[y]), crs=crs).to_crs(CRS)
    j = gpd.sjoin(pts, mun[["ine", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    return j["ine"]


def save(df, name):
    """Escribe carga/<name>.csv. La columna interna 'ine' se publica como 'municipio_ine'."""
    df.rename(columns={"ine": "municipio_ine"}).to_csv(os.path.join(OUT, f"{name}.csv"), index=False)


def load_mun():
    """Lee carga/nm_municipio.csv (generado por p1) con el código como texto."""
    return (pd.read_csv(os.path.join(OUT, "nm_municipio.csv"), dtype={"municipio_ine": str})
              .rename(columns={"municipio_ine": "ine"}))
