/* ==========================================================================
   NidoMadrid · aplicación web
   No contiene datos: los municipios llegan de la API REST de Oracle
   (CONFIG.API_URL) y los contornos del mapa de CONFIG.GEO_URL.

   1. Constantes y estado      2. Utilidades           3. Carga de datos
   4. Mapa                     5. Perfil ciudadano     6. Perfil administración
   7. Ficha municipal          8. Método y datos       9. Pregunta a los datos
   10. Navegación y arranque
   ========================================================================== */

/* 1. Constantes y estado --------------------------------------------------- */
const PERFILES = {
  eq: { nombre: "Equilibrado", suelo: 34, servicios: 33, comercio: 33 },
  fam: { nombre: "Familia", suelo: 25, servicios: 55, comercio: 20 },
  joven: { nombre: "Joven", suelo: 55, servicios: 15, comercio: 30 },
  tele: { nombre: "Teletrabajo", suelo: 60, servicios: 25, comercio: 15 },
};
const DIMENSIONES = [
  { clave: "suelo", nombre: "Suelo y vivienda", corto: "Suelo" },
  { clave: "servicios", nombre: "Servicios", corto: "Servicios" },
  { clave: "comercio", nombre: "Comercio", corto: "Comercio" },
];
const TAMANOS = {
  all: { nombre: "Todos", min: 0, max: Infinity },
  lt5000: { nombre: "< 5.000 hab.", min: 0, max: 5000 },
  lt20000: { nombre: "< 20.000 hab.", min: 0, max: 20000 },
  lt50000: { nombre: "< 50.000 hab.", min: 0, max: 50000 },
  ge50000: { nombre: "≥ 50.000 hab.", min: 50000, max: Infinity },
};
const CARENCIAS = {
  EDUCACION: "Educación",
  SANIDAD: "Sanidad",
  TRANSPORTE: "Transporte",
};
const NIVEL_SALUD = [
  "Sin centro",
  "Consultorio",
  "Centro de salud",
  "Urgencias (CAC/SAR)",
  "Hospital",
];
const MODOS = {
  build: "Edificar",
  fix: "Mejorar servicios",
  none: "Sin acción prioritaria",
};
const RAMPA = ["--m1", "--m2", "--m3", "--m4", "--m5"];

const estado = {
  vista: "ciud",
  pesos: { suelo: 34, servicios: 33, comercio: 33 },
  perfil: "eq",
  zona: "", // filtro de zona (solo ciudadanía)
  tamano: "lt50000", // filtro de tamaño (ciudadanía y administración)
  modo: "build", // build = Edificar, fix = Mejorar servicios
  sel: null, // municipio seleccionado (código INE)
};
let municipios = [],
  porIne = {},
  medianas = {},
  zonas = [],
  geo = null;

/* 2. Utilidades ------------------------------------------------------------ */
const $ = (sel) => document.querySelector(sel);
const fmt = (n, d = 0) =>
  Number(n ?? 0).toLocaleString("es-ES", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const css = (nombre) =>
  getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();

function indice(m) {
  const w = estado.pesos,
    total = w.suelo + w.servicios + w.comercio || 1;
  return (
    (w.suelo * m.suelo + w.servicios * m.servicios + w.comercio * m.comercio) /
    total
  );
}
function enTamano(m) {
  const t = TAMANOS[estado.tamano];
  return m.poblacion >= t.min && m.poblacion < t.max;
}
function visible(m) {
  if (estado.vista === "admin") return enTamano(m);
  return (!estado.zona || m.zona === estado.zona) && enTamano(m);
}
const claseModo = (m) =>
  m.modo === "EDIFICAR"
    ? "build"
    : m.modo === "MEJORAR_SERVICIOS"
      ? "fix"
      : "none";

function selectorTamano() {
  return `
    <label class="label" for="f-tamano">Tamaño</label>
    <select id="f-tamano">
      ${Object.entries(TAMANOS)
        .map(
          ([k, t]) =>
            `<option value="${k}" ${estado.tamano === k ? "selected" : ""}>${t.nombre}</option>`,
        )
        .join("")}
    </select>`;
}

/* 3. Carga de datos -------------------------------------------------------- */
async function pedirJSON(url, nombre) {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok)
    throw new Error(`${nombre} respondió con el código HTTP ${r.status}.`);
  return r.json();
}

async function cargarDatos() {
  if (!CONFIG.API_URL.startsWith("http")) {
    throw new Error(
      "Falta la dirección de la API: rellena API_URL en js/config.js.",
    );
  }
  const [api, contornos] = await Promise.all([
    pedirJSON(CONFIG.API_URL, "La API"),
    pedirJSON(CONFIG.GEO_URL, "El fichero de contornos"),
  ]);
  if (!Array.isArray(api.items) || !api.items.length)
    throw new Error("La API no ha devuelto municipios.");

  municipios = api.items.map((m) => ({ ...m, ine: m.municipio_ine }));
  porIne = Object.fromEntries(municipios.map((m) => [m.ine, m]));
  medianas = {
    suelo: +municipios[0].med_suelo,
    servicios: +municipios[0].med_servicios,
    comercio: +municipios[0].med_comercio,
  };
  zonas = [...new Set(municipios.map((m) => m.zona))].sort();
  geo = contornos;
}

/* 4. Mapa ------------------------------------------------------------------ */
const svg = $("#mapa");

function dibujarMapa() {
  const k = Math.cos((40.45 * Math.PI) / 180); // corrección de longitud a la latitud de Madrid
  let x0 = Infinity,
    x1 = -Infinity,
    y0 = Infinity,
    y1 = -Infinity;
  const recorrer = (c, f) =>
    typeof c[0] === "number" ? f(c) : c.forEach((x) => recorrer(x, f));
  geo.features.forEach((f) =>
    recorrer(f.geometry.coordinates, ([x, y]) => {
      x *= k;
      x0 = Math.min(x0, x);
      x1 = Math.max(x1, x);
      y0 = Math.min(y0, y);
      y1 = Math.max(y1, y);
    }),
  );
  const ancho = 800,
    escala = ancho / (x1 - x0),
    alto = Math.round((y1 - y0) * escala);
  svg.setAttribute("viewBox", `-4 -4 ${ancho + 8} ${alto + 8}`);

  const punto = ([x, y]) =>
    `${((x * k - x0) * escala).toFixed(1)},${((y1 - y) * escala).toFixed(1)}`;
  const anillo = (r) => "M" + r.map(punto).join("L") + "Z";
  const poligono = (p) => p.map(anillo).join("");
  svg.innerHTML = geo.features
    .map((f) => {
      const g = f.geometry;
      const d =
        g.type === "Polygon"
          ? poligono(g.coordinates)
          : g.coordinates.map(poligono).join("");
      return `<path d="${d}" data-ine="${esc(f.properties.ine)}"></path>`;
    })
    .join("");

  const tip = $("#tip"),
    bloque = svg.parentElement;
  svg.addEventListener("mousemove", (e) => {
    const p = e.target.closest("path"),
      m = p && porIne[p.dataset.ine];
    if (!m) {
      tip.hidden = true;
      return;
    }
    const r = bloque.getBoundingClientRect();
    tip.textContent =
      estado.vista === "admin"
        ? `${m.nombre}: ${MODOS[claseModo(m)]}`
        : `${m.nombre}: ${fmt(indice(m))}`;
    tip.style.left = `${e.clientX - r.left}px`;
    tip.style.top = `${e.clientY - r.top}px`;
    tip.hidden = false;
  });
  svg.addEventListener("mouseleave", () => {
    tip.hidden = true;
  });
  svg.addEventListener("click", (e) => {
    const p = e.target.closest("path");
    if (p && porIne[p.dataset.ine]) seleccionar(p.dataset.ine);
  });
}

function pintarMapa() {
  const valores = municipios
    .filter(visible)
    .map(indice)
    .sort((a, b) => a - b);
  const cortes = [0.2, 0.4, 0.6, 0.8].map(
    (q) => valores[Math.floor(q * (valores.length - 1))] ?? 0,
  );
  const colorModo = css(estado.modo === "build" ? "--build" : "--fix"),
    apagado = css("--off");

  svg.querySelectorAll("path").forEach((p) => {
    const m = porIne[p.dataset.ine];
    let color = apagado;
    if (m && visible(m)) {
      color =
        estado.vista === "admin"
          ? claseModo(m) === estado.modo
            ? colorModo
            : apagado
          : css(RAMPA[cortes.filter((c) => indice(m) > c).length]);
    }
    p.style.fill = color;
    p.classList.toggle("sel", p.dataset.ine === estado.sel);
  });

  $("#leyenda").innerHTML =
    estado.vista === "admin"
      ? `<i class="dot" style="background:${colorModo}"></i> ${MODOS[estado.modo]}
       <i class="dot" style="background:${apagado}"></i> Resto o fuera del filtro`
      : `Menor índice <span class="ramp">${RAMPA.map((r) => `<i style="background:var(${r})"></i>`).join("")}</span> Mayor índice`;
  $("#mapa-titulo").textContent =
    estado.vista !== "admin"
      ? "Índice por municipio"
      : estado.modo === "build"
        ? "Dónde edificar"
        : "Dónde reforzar servicios";
}
matchMedia("(prefers-color-scheme: dark)").addEventListener(
  "change",
  () => geo && pintarMapa(),
);

/* 5. Perfil ciudadano ------------------------------------------------------ */
function vistaCiudadano() {
  const lateral = $("#lateral");
  lateral.innerHTML = `
    <h2>¿Qué te importa más?</h2>
    <p class="lede">Escribe el porcentaje que das a cada dimensión. Cuando los tres sumen 100 %, pulsa Calcular.</p>
    <span class="label">Empieza con un perfil</span>
    <div class="presets">
      ${Object.entries(PERFILES)
        .map(
          ([k, p]) =>
            `<button type="button" class="chip" data-perfil="${k}" aria-pressed="${estado.perfil === k}">${p.nombre}</button>`,
        )
        .join("")}
    </div>
    <form id="pesos" novalidate>
      <div class="weights">
        ${DIMENSIONES.map(
          (d) => `
          <div>
            <label for="w-${d.clave}"><i class="dot ${d.clave}"></i>${d.corto}</label>
            <div class="wfield">
              <input type="number" id="w-${d.clave}" data-dim="${d.clave}" min="0" max="100" step="1"
                     inputmode="numeric" value="${estado.pesos[d.clave]}" placeholder="0"><span>%</span>
            </div>
          </div>`,
        ).join("")}
      </div>
      <div class="calc-row">
        <span class="sum" id="suma" role="status"></span>
        <button type="submit" class="btn" id="calcular">Calcular</button>
      </div>
      <p class="stale" id="pendiente" hidden>Los porcentajes han cambiado. Pulsa Calcular para actualizar el ranking.</p>
    </form>
    <div class="formula" id="formula"></div>
    <div class="filters">
      <div>
        <label class="label" for="f-zona">Zona estadística</label>
        <select id="f-zona">
          <option value="">Toda la Comunidad</option>
          ${zonas.map((z) => `<option ${estado.zona === z ? "selected" : ""}>${esc(z)}</option>`).join("")}
        </select>
      </div>
      <div>${selectorTamano()}</div>
    </div>
    <ol class="rank" id="ranking"></ol>`;

  const entradas = [...lateral.querySelectorAll("#pesos input")];
  const botones = [...lateral.querySelectorAll("[data-perfil]")];

  function comprobar() {
    const leidos = entradas.map((i) => {
      const txt = i.value.trim(),
        n = Number(txt);
      return {
        dim: i.dataset.dim,
        el: i,
        vacio: txt === "",
        ok: txt !== "" && Number.isInteger(n) && n >= 0 && n <= 100,
        n,
      };
    });
    leidos.forEach((x) =>
      x.el.parentElement.classList.toggle("bad", !x.vacio && !x.ok),
    );
    const suma = leidos.reduce((a, x) => a + (x.ok ? x.n : 0), 0);
    const salida = $("#suma");
    let valido = false;
    if (leidos.some((x) => !x.vacio && !x.ok)) {
      salida.textContent = "Usa números enteros de 0 a 100";
      salida.className = "sum bad";
    } else if (leidos.some((x) => x.vacio)) {
      salida.textContent = `Faltan casillas (suma ${suma} %)`;
      salida.className = "sum";
    } else if (suma !== 100) {
      salida.textContent = `Suman ${suma} %: ${suma < 100 ? "faltan " + (100 - suma) : "sobran " + (suma - 100)} %`;
      salida.className = "sum bad";
    } else {
      salida.textContent = "Suman 100 %";
      salida.className = "sum ok";
      valido = true;
    }
    $("#calcular").disabled = !valido;
    $("#pendiente").hidden = leidos.every(
      (x) => x.ok && x.n === estado.pesos[x.dim],
    );
    return valido ? leidos : null;
  }

  entradas.forEach((i) =>
    i.addEventListener("input", () => {
      estado.perfil = null;
      botones.forEach((b) => b.setAttribute("aria-pressed", "false"));
      comprobar();
    }),
  );
  botones.forEach((b) =>
    b.addEventListener("click", () => {
      const p = PERFILES[b.dataset.perfil];
      estado.perfil = b.dataset.perfil;
      botones.forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      entradas.forEach((i) => {
        i.value = p[i.dataset.dim];
      });
      comprobar();
    }),
  );
  $("#pesos").addEventListener("submit", (e) => {
    e.preventDefault();
    const leidos = comprobar();
    if (!leidos) return;
    leidos.forEach((x) => {
      estado.pesos[x.dim] = x.n;
    });
    comprobar();
    actualizarRanking();
  });
  $("#f-zona").addEventListener("change", (e) => {
    estado.zona = e.target.value;
    actualizarRanking();
  });
  $("#f-tamano").addEventListener("change", (e) => {
    estado.tamano = e.target.value;
    actualizarRanking();
  });

  comprobar();
  actualizarRanking();
}

function actualizarRanking() {
  const w = estado.pesos,
    total = w.suelo + w.servicios + w.comercio || 1;
  $("#formula").textContent =
    `Índice = ${(w.suelo / total).toFixed(2)} × Suelo + ${(w.servicios / total).toFixed(2)} × Servicios + ${(w.comercio / total).toFixed(2)} × Comercio`;

  const lista = municipios
    .filter(visible)
    .map((m) => [m, indice(m)])
    .sort((a, b) => b[1] - a[1]);
  $("#ranking").innerHTML = lista.length
    ? lista
        .map(
          ([m, valor], i) => `
    <li data-ine="${esc(m.ine)}" class="${m.ine === estado.sel ? "sel" : ""}">
      <span class="pos">${i + 1}</span>
      <div>
        <div class="nm">${esc(m.nombre)}</div>
        <div class="sub">${esc(m.zona)}, ${fmt(m.poblacion)} hab.</div>
        <div class="stack">${DIMENSIONES.map((d) => `<i class="${d.clave}" style="width:${(w[d.clave] * m[d.clave]) / total}%"></i>`).join("")}</div>
      </div>
      <span class="sc">${fmt(valor)}</span>
    </li>`,
        )
        .join("")
    : '<li class="empty">Ningún municipio cumple los filtros. Prueba con otra zona o tamaño.</li>';
  document
    .querySelectorAll("#ranking li[data-ine]")
    .forEach((li) =>
      li.addEventListener("click", () => seleccionar(li.dataset.ine)),
    );

  if (!estado.sel || !visible(porIne[estado.sel]))
    estado.sel = lista[0]?.[0].ine ?? null;
  pintarMapa();
  pintarFicha();
}

/* 6. Perfil administración ------------------------------------------------- */
function vistaAdministracion() {
  const edificar = estado.modo === "build";
  const filas = municipios
    .filter((m) => visible(m) && claseModo(m) === estado.modo)
    .sort((a, b) =>
      edificar ? b.suelo_libre_ha - a.suelo_libre_ha : b.suelo - a.suelo,
    );

  $("#lateral").innerHTML = `
    <h2>¿Dónde actuar?</h2>
    <p class="lede">Reglas sobre las puntuaciones, comparadas con la mediana regional de los 179 municipios.</p>
    <div class="modes">
      <button type="button" class="mode build" data-modo="build" aria-pressed="${edificar}">
        <strong>Edificar</strong><span>Servicios y comercio sobre la mediana. Ordenado por suelo libre.</span>
      </button>
      <button type="button" class="mode fix" data-modo="fix" aria-pressed="${!edificar}">
        <strong>Mejorar servicios</strong><span>Suelo asequible alto y servicios bajo la mediana.</span>
      </button>
    </div>
    <div class="filters solo"><div>${selectorTamano()}</div></div>
    <div class="count-row">
      <span class="count ${estado.modo}">${filas.length}</span>
      <span class="small">municipios cumplen la regla con este filtro</span>
    </div>
    <div class="tablewrap">
      <table>
        <thead><tr>
          <th>Municipio</th>
          ${
            edificar
              ? '<th class="n">Suelo libre</th><th class="n">Servicios</th><th class="n">Comercio</th>'
              : '<th class="n">Suelo</th><th class="n">Servicios</th><th>Falta</th>'
          }
        </tr></thead>
        <tbody>
          ${
            filas
              .map(
                (m) => `
            <tr data-ine="${esc(m.ine)}" class="${m.ine === estado.sel ? "sel" : ""}">
              <td>${esc(m.nombre)}</td>
              ${
                edificar
                  ? `<td class="n">${fmt(m.suelo_libre_ha)} ha</td><td class="n">${fmt(m.servicios)}</td><td class="n">${fmt(m.comercio)}</td>`
                  : `<td class="n">${fmt(m.suelo)}</td><td class="n">${fmt(m.servicios)}</td><td><span class="gap">${CARENCIAS[m.carencia] ?? ""}</span></td>`
              }
            </tr>`,
              )
              .join("") ||
            '<tr><td colspan="4" class="small">Ningún municipio cumple la regla con este tamaño.</td></tr>'
          }
        </tbody>
      </table>
    </div>
    <p class="small mt">Medianas regionales: suelo ${fmt(medianas.suelo, 1)}, servicios ${fmt(medianas.servicios, 1)} y comercio ${fmt(medianas.comercio, 1)}.</p>`;

  document.querySelectorAll("[data-modo]").forEach((b) =>
    b.addEventListener("click", () => {
      estado.modo = b.dataset.modo;
      estado.sel = null;
      vistaAdministracion();
    }),
  );
  $("#f-tamano").addEventListener("change", (e) => {
    estado.tamano = e.target.value;
    estado.sel = null;
    vistaAdministracion();
  });
  document
    .querySelectorAll("#lateral tbody tr[data-ine]")
    .forEach((tr) =>
      tr.addEventListener("click", () => seleccionar(tr.dataset.ine)),
    );

  if (!estado.sel || !filas.some((m) => m.ine === estado.sel))
    estado.sel = filas[0]?.ine ?? null;
  pintarMapa();
  pintarFicha();
}

/* 7. Ficha municipal ------------------------------------------------------- */
function pintarFicha() {
  const m = porIne[estado.sel],
    ficha = $("#ficha");
  ficha.hidden = !m;
  if (!m) return;

  const puesto =
    [...municipios]
      .sort((a, b) => indice(b) - indice(a))
      .findIndex((x) => x.ine === m.ine) + 1;
  const clase = claseModo(m);
  const diagnostico = {
    build: `Tiene servicios y comercio por encima de la mediana y unas ${fmt(m.suelo_libre_ha)} ha de suelo urbano sin edificar (${fmt(m.parcelas_sin_edificar)} parcelas). Es candidato a nuevo desarrollo residencial.`,
    fix: `Suelo abundante y asequible, pero servicios por debajo de la mediana. La carencia principal es <b>${(CARENCIAS[m.carencia] ?? "").toLowerCase()}</b>: conviene dotar antes de crecer.`,
    none: "No cumple ninguna de las dos reglas: o le falta suelo asequible, o sus servicios y comercio no superan a la vez la mediana.",
  }[clase];
  const alquiler =
    m.alquiler_origen === "IMPUTADO"
      ? "Alquiler (imputado)"
      : `Alquiler SERPAVI ${esc(m.alquiler_anio)}`;

  const dim = (clave, titulo, filas) => `
    <div class="dim ${clave}">
      <h4>${titulo}<span>${fmt(m[clave])}</span></h4>
      <div class="bar"><i style="width:${m[clave]}%"></i></div>
      <dl class="kv">${filas.map(([dt, dd]) => `<dt>${dt}</dt><dd>${dd}</dd>`).join("")}</dl>
    </div>`;

  ficha.innerHTML = `
    <div class="ficha-head">
      <div>
        <span class="zona">${esc(m.zona)} (código INE ${esc(m.ine)})</span>
        <h3>${esc(m.nombre)}</h3>
        <p class="meta">${fmt(m.poblacion)} habitantes en ${fmt(m.km2, 1)} km², a ${fmt(m.dist_km)} km de la Puerta del Sol${m.ferroviario ? ". Con Metro, Cercanías o Metro Ligero" : ""}.</p>
      </div>
      <div class="big"><strong>${fmt(indice(m))}</strong><span>Puesto ${puesto} de ${municipios.length} con tus pesos</span></div>
    </div>
    <div class="dims">
      ${dim("suelo", "Suelo y vivienda", [
        ["Parcelas sin edificar", fmt(m.parcelas_sin_edificar)],
        ["Superficie estimada", `${fmt(m.suelo_libre_ha)} ha`],
        ["Término en Red Natura", `${fmt(m.protegido_pct)} %`],
        [alquiler, `${fmt(m.alquiler_m2, 2)} €/m²`],
      ])}
      ${dim("servicios", "Servicios", [
        ["Centros educativos", fmt(m.centros_edu)],
        ["Etapas educativas", `${fmt(m.etapas_edu)} de 4`],
        ["Centros de atención primaria", fmt(m.puntos_salud)],
        ["Nivel sanitario", NIVEL_SALUD[m.nivel_salud] ?? ""],
        ["Paradas", fmt(m.paradas)],
        ["Pasos de vehículo al día", fmt(m.salidas_dia)],
        ["Puntuación educación", fmt(m.n_edu)],
        ["Puntuación sanidad", fmt(m.n_salud)],
        ["Puntuación transporte", fmt(m.n_transporte)],
      ])}
      ${dim("comercio", "Comercio", [
        ["Comercios en OSM", fmt(m.comercios)],
        ["Por 1.000 hab.", fmt(m.comercio_1000, 1)],
        ["Tipos de tienda", fmt(m.categorias)],
      ])}
    </div>
    <div class="diag ${clase}"><span class="pill ${clase}">${MODOS[clase]}</span><span>${diagnostico}</span></div>`;
}

function seleccionar(ine) {
  estado.sel = ine;
  pintarMapa();
  pintarFicha();
  document
    .querySelectorAll("#lateral [data-ine]")
    .forEach((el) => el.classList.toggle("sel", el.dataset.ine === ine));
  document
    .querySelector(`#lateral [data-ine="${CSS.escape(ine)}"]`)
    ?.scrollIntoView({ block: "nearest" });
}

/* 8. Método y datos -------------------------------------------------------- */
const FUENTES = [
  [
    "Población",
    "Padrón continuo a 1 de enero de 2025, INE (tabla 2881)",
    "https://ine.es/jaxiT3/Tabla.htm?t=2881",
  ],
  [
    "Zonas estadísticas",
    "Municipios de la Comunidad de Madrid, nivel NUTS4 (febrero 2025)",
    "https://datos.gob.es/en/catalogo/a13002908-municipios-de-la-comunidad-de-madrid1",
  ],
  [
    "Límites municipales",
    "IGN, capa EGRN publicada por MIVAU",
    "https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi",
  ],
  [
    "Red Natura 2000",
    "LIC/ZEC y ZEPA, IDEM Comunidad de Madrid",
    "https://datos.gob.es/es/catalogo/a13002908-red-natura-2000-zonas-de-especial-proteccion-para-las-aves-zepa_es30",
  ],
  [
    "Suelo sin edificar",
    "Catastro 2026: parcelas urbanas sin edificar por tramo de superficie",
    "https://datos.gob.es/es/catalogo/a13002908-catastro-inmobiliario-parcelas-catastrales-urbanas-sin-edificar-por-superficie4",
  ],
  [
    "Alquiler €/m²",
    "SERPAVI 2011-2024, MIVAU (mediana mensual)",
    "https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi",
  ],
  [
    "Centros educativos",
    "Directorio de centros de la Comunidad de Madrid (mayo 2026)",
    "https://datos.gob.es/en/catalogo/a13002908-centros-educativos-de-la-comunidad-de-madrid1",
  ],
  [
    "Atención primaria y urgencias",
    "Catálogos del SNS 2026, Ministerio de Sanidad",
    "https://www.sanidad.gob.es/estadEstudios/estadisticas/sisInfSanSNS/ofertaRecursos/centrosSalud/home.htm",
  ],
  [
    "Hospitales",
    "Catálogo Nacional de Hospitales 2025",
    "https://www.sanidad.gob.es/estadEstudios/estadisticas/sisInfSanSNS/ofertaRecursos/hospitales/home.htm",
  ],
  [
    "Transporte",
    "GTFS del Consorcio (Metro, Cercanías, Metro Ligero, interurbanos y urbanos) y de la EMT, octubre 2026",
    "https://datos-movilidad.crtm.es/",
  ],
  [
    "Comercio",
    "OpenStreetMap, extracto de Geofabrik del 20 de octubre de 2026",
    "https://download.geofabrik.de/europe/spain.html",
  ],
];

function vistaMetodo() {
  const suma = (k) =>
    fmt(municipios.reduce((a, m) => a + (Number(m[k]) || 0), 0));
  const imputados = municipios
    .filter((m) => m.alquiler_origen === "IMPUTADO")
    .map((m) => esc(m.nombre));
  const sinComercio = municipios.filter((m) => !Number(m.comercios)).length;

  $("#metodo").innerHTML = `
    <div class="method">
      <div>
        <h3>Cómo se calcula</h3>
        <p><b>1. Integración en Oracle.</b> Cada fuente se carga en su tabla <code>NM_*</code> y todas se unen por el código INE de 5 dígitos. Centros, paradas y comercios se asignan a su municipio por coordenadas (punto en polígono, con los límites del IGN).</p>
        <p><b>2. Suelo y vivienda.</b> Media de dos subindicadores:</p>
        <ul>
          <li><b>Suelo sin edificar:</b> parcelas urbanas sin edificar del Catastro 2026, con la superficie estimada por tramos (50, 300, 750, 3.500 y 20.000 m² por parcela) y en escala logarítmica. Como es suelo urbano, ya excluye la Red Natura, que se clasifica como no urbanizable de protección.</li>
          <li><b>Alquiler:</b> mediana en €/m² al mes de SERPAVI, invertida (más barato, más puntos). Se usa vivienda colectiva de 2024 y, si no hay, la de 2023 o 2022, o la unifamiliar. Los municipios sin dato toman la mediana de su zona estadística.</li>
        </ul>
        <p>Ambos se escalan de 0 a 100 entre los percentiles 5 y 95, para que Madrid capital no aplaste la escala.</p>
        <p><b>3. Servicios.</b> Media de tres subindicadores. Cada uno combina al 50 % una cobertura por 1.000 habitantes, saturada en 100, y un nivel de oferta de 0 a 4. Las referencias de cobertura son el percentil 75 entre los municipios de 1.000 habitantes o más.</p>
        <ul>
          <li><b>Educación:</b> centros en alta cuyo tipo menciona una etapa, y etapas presentes (infantil, primaria, secundaria y FP). Las etapas se leen literalmente del nombre del tipo que publica la Consejería: un "Instituto de Educación Secundaria" cuenta como secundaria y nada más.</li>
          <li><b>Sanidad:</b> centros de salud frente a un estándar fijo de 1 por 20.000 habitantes (un consultorio cuenta como 0,2), y nivel máximo: consultorio, centro de salud, urgencias extrahospitalarias (CAC y SAR) u hospital. Hospitales generales, quirúrgicos y materno-infantiles, sin las mutuas de accidentes de trabajo.</li>
          <li><b>Transporte:</b> pasos de vehículo por parada en el miércoles con más servicio de cada GTFS, con las frecuencias expandidas. El nivel suma un punto por tener paradas, por superar 100 y 1.000 pasos al día, y por tener Metro, Cercanías o Metro Ligero.</li>
        </ul>
        <p><b>4. Comercio.</b> Comercios por 1.000 habitantes frente al percentil 75, y número de tipos de tienda distintos frente al percentil 90.</p>
        <p><b>5. Dimensiones.</b> Cada dimensión se reescala de 0 a 100 sobre los 179 municipios.</p>
        <p><b>6. Índice ciudadano.</b> <code>w₁ × Suelo + w₂ × Servicios + w₃ × Comercio</code>, con los pesos que elige cada persona. En Oracle es la SQL macro <code>nm_ranking(w1, w2, w3)</code>.</p>
        <p><b>7. Reglas de administración.</b> <i>Edificar</i>: servicios y comercio sobre la mediana, ordenado por suelo sin edificar. <i>Mejorar servicios</i>: suelo sobre la mediana y servicios bajo ella. La carencia señalada es el subindicador de servicios más bajo.</p>
      </div>
      <div>
        <h3>Fuentes</h3>
        <div class="tablewrap">
          <table class="src">
            <thead><tr><th>Indicador</th><th>Fuente</th></tr></thead>
            <tbody>${FUENTES.map(([a, b, url]) => `<tr><td>${a}</td><td><a href="${url}" target="_blank" rel="noopener">${b}</a></td></tr>`).join("")}</tbody>
          </table>
        </div>
        <p class="small">Datos cargados: ${fmt(municipios.length)} municipios, ${suma("centros_edu")} centros educativos de enseñanza general y FP, ${suma("puntos_salud")} centros de atención primaria, ${suma("paradas")} paradas y ${suma("comercios")} comercios.</p>

        <h3>Limitaciones conocidas</h3>
        <ul class="small">
          <li><b>Comercio:</b> OpenStreetMap no está igual de completo en todos los municipios. Algunas ciudades están mucho mejor cartografiadas que otras, y ${sinComercio} municipios no tienen ninguna tienda registrada. Un directorio oficial de locales mejoraría esta dimensión.</li>
          <li><b>Transporte:</b> el GTFS del Consorcio publica 295 paradas de las líneas 720-728, 522, 635, N702 y N908 sin horarios. Se les asignan los pasos medianos de su zona estadística. El GTFS de Metro trae un calendario de 2025.</li>
          <li><b>Suelo:</b> el Catastro publica el número de parcelas por tramo, no su superficie exacta. Las hectáreas son una estimación.</li>
          <li><b>Alquiler imputado</b> en ${imputados.length} municipios con pocos contratos, donde el Ministerio no publica el dato: ${imputados.join(", ")}.</li>
        </ul>

        <h3>Descargar los datos</h3>
        <p class="small">Tabla completa de los ${fmt(municipios.length)} municipios (vista <code>V_NM_WEB</code>), con el índice calculado con tus pesos actuales. Separador punto y coma y decimales con coma, listo para abrir en Excel.</p>
        <div class="export-row">
          <button class="btn" id="descargar" type="button">Descargar CSV</button>
          <span class="small" id="descargado" role="status"></span>
        </div>
      </div>
    </div>`;

  $("#descargar").addEventListener("click", descargarCSV);
}

function descargarCSV() {
  const columnas = Object.keys(municipios[0]).filter((k) => k !== "ine");
  const celda = (v) => {
    if (v === null || v === undefined) return "";
    if (typeof v === "number") return String(v).replace(".", ",");
    const s = String(v);
    return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const filas = [...municipios].sort((a, b) => indice(b) - indice(a));
  const csv = [
    [...columnas, "indice_tus_pesos"].join(";"),
    ...filas.map((m) =>
      [
        ...columnas.map((k) => celda(m[k])),
        celda(Math.round(indice(m) * 10) / 10),
      ].join(";"),
    ),
  ].join("\r\n");

  const url = URL.createObjectURL(
    new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }),
  );
  const a = Object.assign(document.createElement("a"), {
    href: url,
    download: "nidomadrid_municipios.csv",
  });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("#descargado").textContent = `Descargado: ${filas.length} municipios.`;
}

/* 9. Asistente flotante (Select AI) ---------------------------------------- */
/* Tres estados en #asistente[data-estado]:
     burbuja -> solo el botón redondo, abajo a la derecha
     barra   -> al pasar el ratón (o enfocar): se despliega la caja de texto
     panel   -> al escribir o preguntar: se abre la conversación encima de la barra
   No bloquea el resto de la página: se puede seguir usando el mapa con el chat abierto. */
const EJEMPLOS = [
  "¿Qué municipios de menos de 20.000 habitantes tienen hospital?",
  "¿Cuáles son los 5 municipios con el alquiler más barato y Cercanías?",
  "¿Por qué Colmenar de Oreja aparece en mejorar servicios?",
  "¿Qué zona estadística tiene más suelo sin edificar?",
];
const chat = { historial: [], pendiente: null, montado: false }; // historial: [{pregunta, respuesta, sql, error}]
const asis = () => $("#asistente");

function estadoAsis(e) {
  asis().dataset.estado = e;
  $("#asis-burbuja").setAttribute(
    "aria-label",
    e === "burbuja" ? "Abrir el asistente" : "Asistente abierto",
  );
  if (e === "panel") pintarHilo();
}

/* Vuelve a burbuja si no hay nada en marcha: caja vacía, sin foco y sin conversación abierta. */
function plegarSiInactivo() {
  const a = asis();
  if (a.dataset.estado !== "barra") return;
  if ($("#asis-pregunta").value.trim() || a.contains(document.activeElement))
    return;
  estadoAsis("burbuja");
}

function montarAsistente() {
  if (chat.montado) return;
  chat.montado = true;
  const a = asis(),
    caja = $("#asis-pregunta");

  a.addEventListener("mouseenter", () => {
    if (a.dataset.estado === "burbuja") estadoAsis("barra");
  });
  a.addEventListener("mouseleave", () => setTimeout(plegarSiInactivo, 250));
  a.addEventListener("focusin", () => {
    if (a.dataset.estado === "burbuja") estadoAsis("barra");
  });
  a.addEventListener("focusout", () => setTimeout(plegarSiInactivo, 0));

  // En móvil no hay "pasar el ratón": tocar la burbuja abre la barra y pone el cursor
  $("#asis-burbuja").addEventListener("click", () => {
    if (a.dataset.estado === "panel") return caja.focus();
    estadoAsis(chat.historial.length ? "panel" : "barra");
    caja.focus();
  });
  caja.addEventListener("input", () => {
    if (caja.value.trim() && a.dataset.estado !== "panel") estadoAsis("panel");
  });
  $("#asis-cerrar").addEventListener("click", () => {
    estadoAsis("burbuja");
    caja.blur();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && a.dataset.estado !== "burbuja") {
      estadoAsis("burbuja");
      caja.blur();
    }
  });
  $("#asis-form").addEventListener("submit", (e) => {
    e.preventDefault();
    preguntar(caja.value);
  });
  $("#asis-hilo").addEventListener("click", (e) => {
    const b = e.target.closest("[data-ejemplo]");
    if (b) preguntar(EJEMPLOS[b.dataset.ejemplo]);
  });
}

function pintarHilo() {
  const hilo = $("#asis-hilo");
  if (!chat.historial.length && !chat.pendiente) {
    hilo.innerHTML = `
      <li class="asis-intro">
        <p>Pregunta lo que quieras sobre los 179 municipios. Oracle lo traduce a SQL, lo ejecuta sobre la vista <code>V_NM_WEB</code> y te redacta la respuesta.</p>
        <div class="asis-ejemplos">
          ${EJEMPLOS.map((e, i) => `<button type="button" class="chip" data-ejemplo="${i}">${esc(e)}</button>`).join("")}
        </div>
      </li>`;
    return;
  }
  const turnos = chat.historial.map(
    (t) => `
    <li class="turno">
      <p class="preg">${esc(t.pregunta)}</p>
      ${
        t.error
          ? `<p class="resp error">${esc(t.error)}</p>`
          : `<div class="resp">${esc(t.respuesta).replace(/\n/g, "<br>")}
             ${t.sql ? `<details class="sql"><summary>Ver el SQL</summary><pre>${esc(t.sql)}</pre></details>` : ""}
           </div>`
      }
    </li>`,
  );
  if (chat.pendiente)
    turnos.push(`
    <li class="turno">
      <p class="preg">${esc(chat.pendiente)}</p>
      <p class="resp pensando"><span class="puntos" aria-hidden="true"><i></i><i></i><i></i></span> Consultando la base de datos…</p>
    </li>`);
  hilo.innerHTML = turnos.join("");
  hilo.scrollTop = hilo.scrollHeight; // lo último, abajo, como en cualquier chat
}

async function preguntar(texto) {
  const pregunta = texto.trim();
  const caja = $("#asis-pregunta");
  if (chat.pendiente) return; // una pregunta cada vez
  if (pregunta.length < 5) {
    caja.focus();
    return;
  }
  caja.value = "";
  chat.pendiente = pregunta;
  $("#asis-enviar").disabled = true;
  estadoAsis("panel");
  let turno = { pregunta };
  try {
    const r = await fetch(CONFIG.CHAT_URL, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=UTF-8" }, // petición simple: sin preflight CORS
      body: JSON.stringify({ pregunta }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok)
      throw new Error(
        j.error || `El asistente respondió con el código HTTP ${r.status}.`,
      );
    turno = {
      pregunta,
      respuesta: j.respuesta || "Sin respuesta.",
      sql: j.sql || "",
    };
  } catch (e) {
    turno.error =
      e instanceof TypeError
        ? "No se ha podido contactar con el asistente (red o CORS)."
        : e.message;
  }
  chat.historial.push(turno);
  chat.pendiente = null;
  $("#asis-enviar").disabled = false;
  pintarHilo();
  caja.focus();
}

/* 10. Navegación y arranque ------------------------------------------------ */
function mostrar(vista) {
  estado.vista = vista;
  estado.sel = null;
  document
    .querySelectorAll(".tabs button")
    .forEach((b) =>
      b.setAttribute("aria-selected", String(b.dataset.view === vista)),
    );
  $("#principal").hidden = vista === "met";
  $("#metodo").hidden = vista !== "met";
  ({ ciud: vistaCiudadano, admin: vistaAdministracion, met: vistaMetodo })[
    vista
  ]();
}
document
  .querySelectorAll(".tabs button")
  .forEach((b) => b.addEventListener("click", () => mostrar(b.dataset.view)));

async function arrancar() {
  $("#cargando").hidden = false;
  $("#error").hidden = true;
  try {
    await cargarDatos();
    if (!svg.childElementCount) dibujarMapa(); // el mapa solo se dibuja una vez
    $("#cargando").hidden = true;
    $(".tabs").hidden = false;
    if (CONFIG.CHAT_URL && asis()) {
      montarAsistente();
      asis().hidden = false;
    } // sin CHAT_URL no aparece la burbuja
    const ancla = location.hash.slice(1);
    mostrar(["ciud", "admin", "met"].includes(ancla) ? ancla : "ciud");
  } catch (e) {
    console.warn("NidoMadrid: no se han podido cargar los datos.", e);
    $("#error-detalle").textContent =
      e instanceof TypeError
        ? "El navegador no ha podido llegar a la API (sin red, dirección incorrecta o bloqueo CORS)."
        : e.message;
    $("#cargando").hidden = true;
    $("#principal").hidden = true;
    $("#metodo").hidden = true;
    if (asis()) asis().hidden = true;
    $(".tabs").hidden = true;
    $("#error").hidden = false;
  }
}
$("#reintentar").addEventListener("click", arrancar);
arrancar();
