"""Etapa 2 · carga/nm_suelo.csv y carga/nm_alquiler.csv

Fuentes
  * Catastro inmobiliario: parcelas catastrales urbanas sin edificar por superficie,
    municipios (Comunidad de Madrid, CSV ';', Latin-1).
  * SERPAVI 2011-2024, MIVAU (Excel, hoja "Municipios").

Reglas · nm_suelo
  R2.1  Solo filas con Tipo territorio = "Municipios" (se descartan Comunidad y zonas estadísticas).
  R2.2  Solo el año más reciente del fichero (2026).
  R2.3  municipio_ine = "28" + 3 primeros dígitos del Código territorio
        (el código de 4 cifras es municipio + dígito de control: "0796" -> 28079).
  R2.4  parcelas_sin_edificar = valor de la fila "Total".
  R2.5  sup_sin_edificar_ha = suma por tramo de (nº de parcelas x superficie representativa)
        / 10.000. El Catastro no publica la superficie, solo el número de parcelas por tramo.
        Superficie representativa: 0-100 m² -> 50 · 100-500 -> 300 · 500-1.000 -> 750 ·
        1.000-10.000 -> 3.500 · >10.000 -> 20.000 · "No consta" -> 0.
  R2.6  Valores no numéricos se toman como 0. Se exige que los 179 municipios tengan dato.

Reglas · nm_alquiler
  R2.7  Solo filas de la provincia 28.
  R2.8  alquiler_m2 = mediana de renta €/m²/mes. Orden de preferencia:
        vivienda colectiva 2024, 2023, 2022 (ALQM2_LV_M_VC_aa) y, si no hay ninguna,
        vivienda unifamiliar 2024, 2023, 2022 (ALQM2_LV_M_VU_aa). anio = el año usado.
  R2.9  Una celda vale como dato si es numérica y mayor que 0 (las vacías o "" no cuentan).
  R2.10 Municipios sin dato en 2022-2024 no se escriben: el MIVAU no publica el dato cuando
        hay muy pocos contratos declarados (secreto estadístico). Se imputan en Oracle,
        en la vista v_nm_indicadores, y quedan marcados como IMPUTADO.
"""
import openpyxl
import pandas as pd
from comun import fuente, load_mun, save

mun = load_mun()

# ----------------------------- Catastro -------------------------------------
TRAMO_M2 = {"De 0 a 100 m2": 50, "De 100 a 500 m2": 300, "De 500 a 1.000 m2": 750,
            "De 1.000 a 10.000 m2": 3500, "De más de 10.000 m2": 20000, "No consta la superficie": 0}
c = pd.read_csv(fuente("*parcelas-catastrales-urbanas-sin-edificar*.csv"), sep=";", encoding="latin1", dtype=str)
c = c[c["Tipo territorio"] == "Municipios"].copy()                         # R2.1
anio = int(c["Año"].astype(int).max())                                      # R2.2
c = c[c["Año"].astype(int) == anio]
c["ine"] = "28" + c["Código territorio"].str[:3]                            # R2.3
c["valor"] = pd.to_numeric(c["Valor"], errors="coerce").fillna(0)           # R2.6
tot = c[c.Superficie == "Total"].set_index("ine")["valor"]                  # R2.4
t = c[c.Superficie != "Total"].copy()
t["m2"] = t.Superficie.map(TRAMO_M2) * t.valor                              # R2.5
suelo = pd.DataFrame({"parcelas_sin_edificar": tot.astype(int),
                      "sup_sin_edificar_ha": (t.groupby("ine").m2.sum() / 1e4).round(2)}).reset_index()
suelo["anio"] = anio
miss = set(mun.ine) - set(suelo.ine)
assert not miss, f"municipios sin Catastro: {miss}"                         # R2.6
suelo = suelo[suelo.ine.isin(mun.ine)]
save(suelo.sort_values("ine"), "nm_suelo")
print(f"nm_suelo: Catastro {anio} · {len(suelo)} municipios · {int(suelo.parcelas_sin_edificar.sum())} parcelas")

# ------------------------------ SERPAVI -------------------------------------
wb = openpyxl.load_workbook(fuente("*SERPAVI*.xlsx"), read_only=True)
rows = wb["Municipios"].iter_rows(values_only=True)
hdr = next(rows)
s = pd.DataFrame([r for r in rows if str(r[0]).zfill(2) == "28"], columns=hdr)   # R2.7
out = []
for _, r in s.iterrows():
    val = None
    for tipo in ("VC", "VU"):                                                   # R2.8
        for aa in (24, 23, 22):
            v = r.get(f"ALQM2_LV_M_{tipo}_{aa}")
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv == fv and fv > 0:                                             # R2.9
                val = (round(fv, 2), 2000 + aa, tipo); break
        if val: break
    if val:                                                                     # R2.10
        out.append({"ine": str(r["CUMUN"]).zfill(5), "alquiler_m2": val[0], "anio": val[1], "_tipo": val[2]})
alq = pd.DataFrame(out)
alq = alq[alq.ine.isin(mun.ine)]
save(alq[["ine", "alquiler_m2", "anio"]].sort_values("ine"), "nm_alquiler")
print(f"nm_alquiler: {len(alq)} de {len(mun)} municipios con dato · {alq._tipo.value_counts().to_dict()}")
