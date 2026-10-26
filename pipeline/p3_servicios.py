"""Etapa 3 · carga/nm_centro_educativo.csv, carga/nm_centro_sanitario.csv, carga/nm_parada.csv

Fuentes
  * Centros educativos de la Comunidad de Madrid (CSV ';', UTF-8 con BOM).
  * Catálogo de Centros de Atención Primaria del SNS 2026 (Excel, hoja "Catálogo - 2026").
  * Catálogo de Centros de Atención Urgente Extrahospitalaria 2026 (Excel, hoja "Catálogo - 2026").
  * Catálogo Nacional de Hospitales 2025 (Excel, hoja "DIRECTORIO DE HOSPITALES").
  * GTFS del CRTM y de la EMT: google_transit_{metro, cercanias, metroligero,
    interurbanos, urbanos, emt}.zip

Reglas · nm_centro_educativo
  R3.1  Solo centros con SITUACIÓN = "ALTA" (se descartan BAJA, INACTIVO, ANULACIÓN,
        EN TRÁMITE y AUTORIZADO PENDIENTE FUNCIONAMIENTO).
  R3.2  municipio_ine = "28" + CDMUNI (3 dígitos).
  R3.3  Se copian tal cual CODIGO, CENTRO, TITULARIDAD, COD_TIPO, TIPO_ABRV y TIPO_EXT.
        No se añade ninguna clasificación: las etapas se leen en Oracle (v_nm_centro_etapas).
  R3.4  Un registro por CODIGO (si se repitiera, se queda el primero).

Reglas · nm_centro_sanitario
  R3.5  Solo filas cuya provincia es MADRID.
  R3.6  Atención Primaria y urgencias solo traen el nombre del municipio: se cruza con
        nm_municipio por nombre normalizado (comun.norm). Si un nombre no cruza, se informa
        y la fila se descarta (en los ficheros de 2026 cruzan todas).
  R3.7  Atención Primaria: TIPOCENTRO contiene "CENTRO SALUD" -> tipo CENTRO DE SALUD, nivel 2;
        cualquier otro -> CONSULTORIO LOCAL, nivel 1. id = "AP" + IDCENTRO.
  R3.8  Urgencias extrahospitalarias (CAC y SAR) -> nivel 3. id = "UR" + DISP_EXTRA_ID.
  R3.9  Hospitales -> nivel 4. Solo clase C11 (generales), C12 (quirúrgicos) y
        C13 (materno-infantiles). Se excluyen las mutuas (Cód. Dep. Funcional = 21),
        que solo atienden accidentes de trabajo. municipio_ine = 5 primeras cifras de
        "Cód. Municipio" (6 cifras = INE + dígito de control). id = "H" + CODCNH.

Reglas · nm_parada
  R3.10 modo según el feed: metro -> METRO, cercanias -> CERCANIAS, metroligero ->
        METRO_LIGERO, interurbanos -> INTERURBANO, urbanos -> URBANO, emt -> EMT.
  R3.11 Día tipo: para cada feed, el miércoles de su periodo de vigencia con más viajes
        en servicio (calendar.txt + calendar_dates.txt: excepción 1 añade, 2 quita).
  R3.12 Viajes por frecuencia (frequencies.txt): cada franja genera
        ceil((end_time - start_time) / headway_secs) salidas. La EMT repite la misma franja
        en un trip_id por autobús, así que la franja se cuenta una sola vez por
        línea + servicio + sentido + recorrido + franja horaria.
  R3.13 salidas_dia = nº de pasos de vehículo por la parada ese día
        (suma de stop_times de los viajes activos, multiplicados por R3.12).
  R3.14 Solo paradas con al menos un paso ese día y dentro de un municipio de Madrid
        (punto en polígono con stop_lat / stop_lon). id = "<feed>:<stop_id>". con_horario = 1.
  R3.15 Paradas de autobús publicadas en stops.txt sin ningún viaje en el GTFS
        (líneas 720-728, 522, 635, N702 y N908): se añaden como INTERURBANO con
        con_horario = 0 y salidas_dia = mediana de las paradas interurbanas con horario
        de su misma zona (o regional si la zona no tiene). Solo location_type = 0 (paradas,
        no estaciones).
"""
import glob, math, os
from datetime import timedelta
import openpyxl
import pandas as pd
from comun import descomprimir, fuente, load_mun, municipios, norm, points_to_ine, save, F

GEO = municipios()
MUN = load_mun()
INES = set(MUN.ine)
NAME2INE = {norm(n): i for i, n in zip(MUN.ine, MUN.nombre)}
for i, n in zip(GEO.ine, GEO.nombre_ign):
    NAME2INE.setdefault(norm(n), i)


def por_nombre(s):
    return s.map(lambda n: NAME2INE.get(norm(n)))


def hoja(path, name):
    wb = openpyxl.load_workbook(path, read_only=True)
    rows = wb[name].iter_rows(values_only=True)
    h = [str(x) if x else f"c{i}" for i, x in enumerate(next(rows))]
    return pd.DataFrame(list(rows), columns=h)


# =============================== EDUCACIÓN ======================================
e = pd.read_csv(fuente("*centros_educativos*.csv"), sep=";", dtype=str, encoding="utf-8-sig")
e = e[e["SITUACIÓN"] == "ALTA"].copy()                                        # R3.1
e["ine"] = "28" + e.CDMUNI.str.zfill(3)                                       # R3.2
e = e[e.ine.isin(INES)]
edu = e[["CODIGO", "ine", "CENTRO", "TITULARIDAD", "COD_TIPO", "TIPO_ABRV", "TIPO_EXT"]].copy()   # R3.3
edu.columns = ["codigo", "ine", "nombre", "titularidad", "cod_tipo", "tipo_abrv", "tipo_ext"]
edu = edu.drop_duplicates("codigo")                                           # R3.4
save(edu, "nm_centro_educativo")
print(f"nm_centro_educativo: {len(edu)} centros en ALTA en {edu.ine.nunique()} municipios")

# ================================ SANIDAD =======================================
san = []
ap = hoja(fuente("*Catal_Centros_AP*.xlsx"), "Catálogo - 2026")
ap = ap[ap["SIAP_PROVINCIAS.NOMBRE"].astype(str).str.upper() == "MADRID"].copy()     # R3.5
ap["ine"] = por_nombre(ap.MUNICIPIO)                                                 # R3.6
print("  AP sin municipio:", sorted(ap[ap.ine.isna()].MUNICIPIO.unique()))
for _, r in ap.dropna(subset=["ine"]).iterrows():                                    # R3.7
    cs = "CENTRO SALUD" in str(r.TIPOCENTRO).upper()
    san.append(dict(id=f"AP{r.IDCENTRO}", ine=r.ine, nombre=r["SIAP_CENTROS.NOMBRE"],
                    tipo="CENTRO DE SALUD" if cs else "CONSULTORIO LOCAL", nivel=2 if cs else 1))

ur = hoja(fuente("*Catal_disp_urg*.xlsx"), "Catálogo - 2026")
ur = ur[ur["SIAP_PROVINCIAS.NOMBRE"].astype(str).str.upper() == "MADRID"].copy()     # R3.5
ur["ine"] = por_nombre(ur.MUNICIPIO)                                                 # R3.6
print("  Urgencias sin municipio:", sorted(ur[ur.ine.isna()].MUNICIPIO.unique()))
for _, r in ur.dropna(subset=["ine"]).iterrows():                                    # R3.8
    san.append(dict(id=f"UR{r.DISP_EXTRA_ID}", ine=r.ine, nombre=r.T_UBICACION,
                    tipo="URGENCIAS EXTRAHOSPITALARIAS", nivel=3))

h = hoja(fuente("*CNH_*.xlsx"), "DIRECTORIO DE HOSPITALES")
h = h[h["Cód. Provincia"].astype(str).str.zfill(2) == "28"].copy()
h = h[h["Cód. Clase de Centro"].isin(["C11", "C12", "C13"])]                         # R3.9
h = h[~h["Cód. Dep. Funcional"].astype(str).eq("21")]
h["ine"] = h["Cód. Municipio"].astype(str).str.zfill(6).str[:5]
for _, r in h[h.ine.isin(INES)].iterrows():
    san.append(dict(id=f"H{r.CODCNH}", ine=r.ine, nombre=r["Nombre Centro"], tipo="HOSPITAL", nivel=4))

san = pd.DataFrame(san).drop_duplicates("id")
save(san, "nm_centro_sanitario")
print(f"nm_centro_sanitario: {len(san)} centros · {san.tipo.value_counts().to_dict()}")

# =============================== TRANSPORTE =====================================
MODOS = {"metro": "METRO", "cercanias": "CERCANIAS", "metroligero": "METRO_LIGERO",      # R3.10
         "interurbanos": "INTERURBANO", "urbanos": "URBANO", "emt": "EMT"}


def secs(t):
    hh, mm, ss = map(int, str(t).split(":"))
    return hh * 3600 + mm * 60 + ss


def leer(d, f):
    p = os.path.join(d, f)
    return pd.read_csv(p, dtype=str, encoding="utf-8-sig") if os.path.exists(p) else pd.DataFrame()


def servicios_activos(cal, cd, dia):                                                  # R3.11
    ds = dia.strftime("%Y%m%d")
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][dia.weekday()]
    act = set()
    if len(cal):
        act = set(cal[(cal[wd] == "1") & (cal.start_date <= ds) & (cal.end_date >= ds)].service_id)
    if len(cd):
        x = cd[cd.date == ds]
        act |= set(x[x.exception_type == "1"].service_id)
        act -= set(x[x.exception_type == "2"].service_id)
    return act


feeds = {}
for z in sorted(glob.glob(os.path.join(F, "**", "*google_transit_*.zip"), recursive=True)):
    if "_descomprimido" in z:
        continue
    nombre = os.path.basename(z).split("google_transit_")[1].removesuffix(".zip")
    feeds[nombre] = descomprimir(z)
assert set(feeds) == set(MODOS), f"Faltan GTFS: {set(MODOS) - set(feeds)}"

paradas, served_bus, bus_stops = [], set(), None
for feed in sorted(feeds):
    d, modo = feeds[feed], MODOS[feed]
    cal, cd, trips = leer(d, "calendar.txt"), leer(d, "calendar_dates.txt"), leer(d, "trips.txt")
    st = pd.read_csv(os.path.join(d, "stop_times.txt"), dtype=str, usecols=["trip_id", "stop_id"], encoding="utf-8-sig")
    stops, fq = leer(d, "stops.txt"), leer(d, "frequencies.txt")

    # R3.12 · salidas que representa cada viaje
    mult = pd.Series(1.0, index=trips.trip_id.unique())
    if len(fq):
        fq["n"] = [math.ceil((secs(b) - secs(a)) / int(hw)) for a, b, hw in zip(fq.start_time, fq.end_time, fq.headway_secs)]
        k = fq.merge(trips[["trip_id", "route_id", "service_id"] +
                           [c for c in ("direction_id", "shape_id") if c in trips]], on="trip_id")
        key = [c for c in ("route_id", "service_id", "direction_id", "shape_id") if c in k] + ["start_time", "end_time"]
        k.loc[k.duplicated(key), "n"] = 0
        mult.loc[mult.index.isin(fq.trip_id)] = 0
        mult = mult.add(k.groupby("trip_id").n.sum(), fill_value=0)

    # R3.11 · miércoles con más viajes
    fechas = pd.concat([cal.get("start_date", pd.Series(dtype=str)), cal.get("end_date", pd.Series(dtype=str)),
                        cd.get("date", pd.Series(dtype=str))]).dropna()
    dia, fin = pd.to_datetime(fechas.min()).date(), pd.to_datetime(fechas.max()).date()
    mejor, mejor_n = None, -1
    while dia <= fin:
        if dia.weekday() == 2:
            n = mult.reindex(trips[trips.service_id.isin(servicios_activos(cal, cd, dia))].trip_id).sum()
            if n > mejor_n:
                mejor, mejor_n = dia, n
        dia += timedelta(days=1)

    # R3.13 · pasos por parada
    activos = trips[trips.service_id.isin(servicios_activos(cal, cd, mejor))].trip_id
    s = st[st.trip_id.isin(activos)].copy()
    s["n"] = s.trip_id.map(mult)
    sal = s.groupby("stop_id").n.sum()

    # R3.14 · paradas con servicio dentro de Madrid
    sp = stops[stops.stop_id.isin(sal.index)].copy()
    sp["stop_lat"], sp["stop_lon"] = sp.stop_lat.astype(float), sp.stop_lon.astype(float)
    sp["ine"] = points_to_ine(sp, "stop_lon", "stop_lat", "EPSG:4326", GEO).values
    sp = sp.dropna(subset=["ine"])
    for _, r in sp.iterrows():
        paradas.append(dict(id=f"{feed}:{r.stop_id}", ine=r.ine, modo=modo, nombre=r.stop_name,
                            salidas_dia=int(round(sal[r.stop_id])), con_horario=1))
    print(f"  GTFS {feed:13s} día {mejor} · {len(sp):5d} paradas · {int(sal[sp.stop_id].sum()):8d} pasos/día")
    if feed == "interurbanos":
        bus_stops = stops.copy()
    if feed in ("interurbanos", "urbanos"):
        served_bus |= set(st[st.trip_id.isin(trips.trip_id)].stop_id)

par = pd.DataFrame(paradas).drop_duplicates("id")

# R3.15 · paradas publicadas sin horarios
zona = MUN.set_index("ine").zona
ns = bus_stops[~bus_stops.stop_id.isin(served_bus) & (bus_stops.get("location_type", "0").fillna("0") == "0")].copy()
ns["stop_lat"], ns["stop_lon"] = ns.stop_lat.astype(float), ns.stop_lon.astype(float)
ns["ine"] = points_to_ine(ns, "stop_lon", "stop_lat", "EPSG:4326", GEO).values
ns = ns.dropna(subset=["ine"])
iu = par[(par.modo == "INTERURBANO") & (par.con_horario == 1)]
med_z = iu.assign(z=iu.ine.map(zona)).groupby("z").salidas_dia.median()
ns["salidas_dia"] = ns.ine.map(zona).map(med_z).fillna(iu.salidas_dia.median()).round().astype(int)
par = pd.concat([par, pd.DataFrame(dict(id="interurbanos:" + ns.stop_id, ine=ns.ine, modo="INTERURBANO",
                                        nombre=ns.stop_name, salidas_dia=ns.salidas_dia, con_horario=0))])
par = par.drop_duplicates("id")
save(par, "nm_parada")
print(f"nm_parada: {len(par)} paradas ({len(ns)} sin horario) en {par.ine.nunique()} municipios")
