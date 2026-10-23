"""Etapa 3 · nm_centro_educativo, nm_centro_sanitario, nm_parada."""
import glob, math
from datetime import date, timedelta
import pandas as pd, openpyxl
from comun import F, OUT, municipios, norm, points_to_ine, save, load_mun

mun_ref = pd.read_csv("/home/claude/nido/real/municipios_ref.csv", dtype={"ine": str})
INES = set(mun_ref.ine)
NAME2INE = {norm(n): i for i, n in zip(mun_ref.ine, mun_ref.nombre)}
for i, n in zip(mun_ref.ine, mun_ref.nombre_ign):
    NAME2INE.setdefault(norm(n), i)
GEO = municipios()


def by_name(s):
    return s.map(lambda n: NAME2INE.get(norm(n)))


# ============================ EDUCACIÓN =========================================
# Todos los centros en ALTA, con el tipo tal como lo publica la Consejería
# (COD_TIPO, TIPO_ABRV, TIPO_EXT). Las etapas se derivan en Oracle (v_nm_centro_etapas).
e = pd.read_csv(glob.glob(f"{F}/centros_educativos/*.csv")[0], sep=";", dtype=str, encoding="utf-8-sig")
e = e[e["SITUACIÓN"] == "ALTA"].copy()
e["ine"] = "28" + e.CDMUNI.str.zfill(3)
e = e[e.ine.isin(INES)]
edu = e[["CODIGO", "ine", "CENTRO", "TITULARIDAD", "COD_TIPO", "TIPO_ABRV", "TIPO_EXT"]].copy()
edu.columns = ["codigo", "ine", "nombre", "titularidad", "cod_tipo", "tipo_abrv", "tipo_ext"]
edu = edu.drop_duplicates("codigo")
save(edu, "nm_centro_educativo")
print(f"Educación: {len(edu)} centros en ALTA en {edu.ine.nunique()} municipios · {edu.cod_tipo.nunique()} tipos")

# ============================ SANIDAD ===========================================
def sheet(path, name):
    wb = openpyxl.load_workbook(path, read_only=True)
    rows = wb[name].iter_rows(values_only=True)
    h = [str(x) if x else f"c{i}" for i, x in enumerate(next(rows))]
    return pd.DataFrame(list(rows), columns=h)

san = []
ap = sheet(glob.glob(f"{F}/2026_C_Catal_Centros_AP/*.xlsx")[0], "Catálogo - 2026")
ap = ap[ap["SIAP_PROVINCIAS.NOMBRE"].astype(str).str.upper() == "MADRID"].copy()
ap["ine"] = by_name(ap.MUNICIPIO)
print("AP sin municipio:", sorted(ap[ap.ine.isna()].MUNICIPIO.unique()))
for _, r in ap.dropna(subset=["ine"]).iterrows():
    cs = "CENTRO SALUD" in str(r.TIPOCENTRO).upper()
    san.append(dict(id=f"AP{r.IDCENTRO}", ine=r.ine, nombre=r["SIAP_CENTROS.NOMBRE"],
                    tipo="CENTRO DE SALUD" if cs else "CONSULTORIO LOCAL", nivel=2 if cs else 1))

ur = sheet(glob.glob(f"{F}/2026_C_Catal_disp_urg/*.xlsx")[0], "Catálogo - 2026")
ur = ur[ur["SIAP_PROVINCIAS.NOMBRE"].astype(str).str.upper() == "MADRID"].copy()
ur["ine"] = by_name(ur.MUNICIPIO)
print("Urgencias sin municipio:", sorted(ur[ur.ine.isna()].MUNICIPIO.unique()), "· tipos", ur.T_NOMBRE.value_counts().to_dict())
for _, r in ur.dropna(subset=["ine"]).iterrows():
    san.append(dict(id=f"UR{r.DISP_EXTRA_ID}", ine=r.ine, nombre=r.T_UBICACION, tipo="URGENCIAS EXTRAHOSPITALARIAS", nivel=3))

h = sheet(glob.glob(f"{F}/CNH_2025/*.xlsx")[0], "DIRECTORIO DE HOSPITALES")
h = h[h["Cód. Provincia"].astype(str).str.zfill(2) == "28"].copy()
print("Hospitales Madrid por clase:", h["Clase de Centro"].value_counts().to_dict())
h = h[h["Cód. Clase de Centro"].isin(["C11", "C12", "C13"])]  # generales, quirúrgicos, materno-infantiles
h = h[~h["Cód. Dep. Funcional"].astype(str).eq("21")]  # mutuas: solo accidentes laborales
h["ine"] = h["Cód. Municipio"].astype(str).str.zfill(6).str[:5]
for _, r in h[h.ine.isin(INES)].iterrows():
    san.append(dict(id=f"H{r.CODCNH}", ine=r.ine, nombre=r["Nombre Centro"], tipo="HOSPITAL", nivel=4))

san = pd.DataFrame(san).drop_duplicates("id")
save(san, "nm_centro_sanitario")
print(f"Sanidad: {len(san)} centros en {san.ine.nunique()} municipios ·", san.tipo.value_counts().to_dict())

# ============================ TRANSPORTE (GTFS) =================================
MODOS = {"metro": "METRO", "cercanias": "CERCANIAS", "metroligero": "METRO_LIGERO",
         "interurbanos": "INTERURBANO", "urbanos": "URBANO", "emt": "EMT"}


def secs(t):
    h, m, s = map(int, str(t).split(":"))
    return h * 3600 + m * 60 + s


def read(d, f):
    p = f"{d}/{f}"
    try:
        return pd.read_csv(p, dtype=str, encoding="utf-8-sig")
    except FileNotFoundError:
        return pd.DataFrame()


def active_services(cal, cd, d):
    ds, wd = d.strftime("%Y%m%d"), ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][d.weekday()]
    act = set()
    if len(cal):
        act = set(cal[(cal[wd] == "1") & (cal.start_date <= ds) & (cal.end_date >= ds)].service_id)
    if len(cd):
        x = cd[cd.date == ds]
        act |= set(x[x.exception_type == "1"].service_id)
        act -= set(x[x.exception_type == "2"].service_id)
    return act


paradas = []
for d in sorted(glob.glob(f"{F}/google_transit_*")):
    feed = d.split("google_transit_")[1]
    modo = MODOS[feed]
    cal, cd, trips = read(d, "calendar.txt"), read(d, "calendar_dates.txt"), read(d, "trips.txt")
    st = pd.read_csv(f"{d}/stop_times.txt", dtype=str, usecols=["trip_id", "stop_id"], encoding="utf-8-sig")
    stops = read(d, "stops.txt")
    fq = read(d, "frequencies.txt")
    # salidas que representa cada viaje (1, o las que genera su tabla de frecuencias)
    mult = pd.Series(1.0, index=trips.trip_id.unique())
    if len(fq):
        fq["n"] = [math.ceil((secs(b) - secs(a)) / int(hw)) for a, b, hw in zip(fq.start_time, fq.end_time, fq.headway_secs)]
        # EMT repite la misma franja en un trip_id por autobús: la frecuencia es de la
        # línea, así que se cuenta una sola vez por línea, sentido, recorrido y franja.
        k = fq.merge(trips[["trip_id", "route_id", "service_id"] +
                           [c for c in ("direction_id", "shape_id") if c in trips]], on="trip_id")
        key = [c for c in ("route_id", "service_id", "direction_id", "shape_id") if c in k] + ["start_time", "end_time"]
        k.loc[k.duplicated(key), "n"] = 0
        mult.loc[mult.index.isin(fq.trip_id)] = 0
        mult = mult.add(k.groupby("trip_id").n.sum(), fill_value=0)
    # día laborable tipo: el miércoles del periodo del feed con más viajes en servicio
    ds = pd.concat([cal.get("start_date", pd.Series(dtype=str)), cal.get("end_date", pd.Series(dtype=str)),
                    cd.get("date", pd.Series(dtype=str))]).dropna()
    lo, hi = pd.to_datetime(ds.min()).date(), pd.to_datetime(ds.max()).date()
    best, best_n = None, -1
    day = lo
    while day <= hi:
        if day.weekday() == 2:
            act = active_services(cal, cd, day)
            n = mult.reindex(trips[trips.service_id.isin(act)].trip_id).sum()
            if n > best_n:
                best, best_n = day, n
        day += timedelta(days=1)
    act_trips = trips[trips.service_id.isin(active_services(cal, cd, best))].trip_id
    s = st[st.trip_id.isin(act_trips)].copy()
    s["n"] = s.trip_id.map(mult)
    sal = s.groupby("stop_id").n.sum()
    sp = stops[stops.stop_id.isin(sal.index)].copy()
    sp["stop_lat"], sp["stop_lon"] = sp.stop_lat.astype(float), sp.stop_lon.astype(float)
    sp["ine"] = points_to_ine(sp, "stop_lon", "stop_lat", "EPSG:4326", GEO).values
    sp = sp.dropna(subset=["ine"])
    for _, r in sp.iterrows():
        paradas.append(dict(id=f"{feed}:{r.stop_id}", ine=r.ine, modo=modo, nombre=r.stop_name,
                            salidas_dia=int(round(sal[r.stop_id])), con_horario=1))
    print(f"GTFS {feed:13s} día {best} · {len(sp):5d} paradas en {sp.ine.nunique():3d} municipios · "
          f"{int(sal[sp.stop_id].sum()):7d} salidas/día")
    if feed == "interurbanos":
        bus_stops = stops.copy()
    if feed in ("interurbanos", "urbanos"):
        served = globals().setdefault("served_bus", set())
        served |= set(st[st.trip_id.isin(trips.trip_id)].stop_id)

par = pd.DataFrame(paradas).drop_duplicates("id")

# Paradas de autobús publicadas sin ningún horario (líneas 720-728, 522, 635, N702 y
# N908 no traen viajes en el GTFS del CRTM). Se incluyen con las salidas imputadas:
# mediana de las paradas interurbanas con horario de su misma zona.
zona = load_mun().set_index("ine").zona
ns = bus_stops[~bus_stops.stop_id.isin(served_bus) & (bus_stops.get("location_type", "0").fillna("0") == "0")].copy()
ns["stop_lat"], ns["stop_lon"] = ns.stop_lat.astype(float), ns.stop_lon.astype(float)
ns["ine"] = points_to_ine(ns, "stop_lon", "stop_lat", "EPSG:4326", GEO).values
ns = ns.dropna(subset=["ine"])
iu = par[(par.modo == "INTERURBANO") & (par.con_horario == 1)].copy()
med_z = iu.assign(z=iu.ine.map(zona)).groupby("z").salidas_dia.median()
ns["salidas_dia"] = ns.ine.map(zona).map(med_z).fillna(iu.salidas_dia.median()).round().astype(int)
par = pd.concat([par, pd.DataFrame(dict(id="interurbanos:" + ns.stop_id, ine=ns.ine, modo="INTERURBANO",
                                        nombre=ns.stop_name, salidas_dia=ns.salidas_dia, con_horario=0))])
par = par.drop_duplicates("id")
print(f"Paradas sin horario añadidas: {len(ns)} en {ns.ine.nunique()} municipios")
save(par, "nm_parada")
print(f"Transporte: {len(par)} paradas en {par.ine.nunique()} municipios")
print("Municipios sin parada:", sorted(set(mun_ref.ine) - set(par.ine)))
