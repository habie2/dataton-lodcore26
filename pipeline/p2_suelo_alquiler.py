"""Etapa 2 · nm_suelo (Catastro, parcelas urbanas sin edificar) y nm_alquiler (SERPAVI)."""
import glob
import pandas as pd, openpyxl
from comun import F, OUT, save, load_mun

mun = load_mun()

# --- Catastro --------------------------------------------------------------
# El conjunto publica el NÚMERO de parcelas sin edificar por tramo de superficie.
# La superficie se estima con un valor representativo por tramo (m²).
TRAMO_M2 = {"De 0 a 100 m2": 50, "De 100 a 500 m2": 300, "De 500 a 1.000 m2": 750,
            "De 1.000 a 10.000 m2": 3500, "De más de 10.000 m2": 20000, "No consta la superficie": 0}
c = pd.read_csv(glob.glob(f"{F}/catastro*/*.csv")[0], sep=";", encoding="latin1", dtype=str)
c = c[c["Tipo territorio"] == "Municipios"].copy()
anio = int(c["Año"].astype(int).max())
c = c[c["Año"].astype(int) == anio]
c["ine"] = "28" + c["Código territorio"].str[:3]          # código de 4 = municipio (3) + dígito de control
c["valor"] = pd.to_numeric(c["Valor"], errors="coerce").fillna(0)
tot = c[c.Superficie == "Total"].set_index("ine")["valor"]
t = c[c.Superficie != "Total"].copy()
t["m2"] = t.Superficie.map(TRAMO_M2) * t.valor
suelo = pd.DataFrame({"parcelas_sin_edificar": tot.astype(int),
                      "sup_sin_edificar_ha": (t.groupby("ine").m2.sum() / 1e4).round(2)}).reset_index()
suelo["anio"] = anio
miss = set(mun.ine) - set(suelo.ine)
assert not miss, f"municipios sin Catastro: {miss}"
suelo = suelo[suelo.ine.isin(mun.ine)]
save(suelo.sort_values("ine"), "nm_suelo")
print(f"Catastro {anio}: {len(suelo)} municipios, {int(suelo.parcelas_sin_edificar.sum())} parcelas, "
      f"{suelo.sup_sin_edificar_ha.sum():.0f} ha estimadas")

# --- SERPAVI -----------------------------------------------------------------
# ALQM2_LV_M_VC_aa = mediana €/m²/mes, vivienda colectiva; _VU = unifamiliar.
# Regla: vivienda colectiva del año más reciente con dato (2024→2022); si no hay,
# unifamiliar en el mismo rango. Sin dato en 2022-2024 → se imputa en Oracle.
wb = openpyxl.load_workbook(glob.glob(f"{F}/*SERPAVI*/*.xlsx")[0], read_only=True)
rows = wb["Municipios"].iter_rows(values_only=True)
hdr = next(rows)
s = pd.DataFrame([r for r in rows if str(r[0]).zfill(2) == "28"], columns=hdr)
out = []
for _, r in s.iterrows():
    val = None
    for tipo in ("VC", "VU"):
        for aa in (24, 23, 22):
            v = r.get(f"ALQM2_LV_M_{tipo}_{aa}")
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv == fv and fv > 0:
                val = (round(fv, 2), 2000 + aa, tipo); break
        if val: break
    if val:
        out.append({"ine": str(r["CUMUN"]).zfill(5), "alquiler_m2": val[0], "anio": val[1], "_tipo": val[2]})
alq = pd.DataFrame(out)
alq = alq[alq.ine.isin(mun.ine)]
save(alq[["ine", "alquiler_m2", "anio"]].sort_values("ine"), "nm_alquiler")
print(f"SERPAVI: {len(alq)} de {len(mun)} municipios con dato ·", alq._tipo.value_counts().to_dict(),
      "· años", alq.anio.value_counts().to_dict())
print(alq.merge(mun[["ine", "nombre"]]).sort_values("alquiler_m2", ascending=False)
      [["nombre", "alquiler_m2", "anio"]].head(5).to_string(index=False))
