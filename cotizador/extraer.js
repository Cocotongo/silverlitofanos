// Lee los productos de una página de resultados de búsqueda.
// Se ejecuta DENTRO de la página de la tienda (page.evaluate). Recibe la
// configuración de la tienda (selectores CSS) y regresa [{titulo, precio, url, imagen}].
(cfg) => {
  const numero = (s) => {
    if (s == null) return null;
    const m = String(s).replace(/\s/g, '').match(/\d[\d,]*(\.\d+)?/);
    if (!m) return null;
    const v = parseFloat(m[0].replace(/,/g, ''));
    return Number.isFinite(v) ? v : null;
  };
  // Un selector puede traer varias opciones separadas por comas: se prueban EN ORDEN
  // (la primera que encuentre algo gana), no en el orden en que aparecen en la página.
  const opciones = (sel) => {
    const res = [];
    let prof = 0, actual = '';
    for (const ch of sel) {
      if (ch === '(' || ch === '[') prof++;
      if (ch === ')' || ch === ']') prof--;
      if (ch === ',' && prof === 0) { res.push(actual.trim()); actual = ''; } else actual += ch;
    }
    if (actual.trim()) res.push(actual.trim());
    return res;
  };
  const dentro = (raiz, sel) => {
    if (!sel) return null;
    for (const s of opciones(sel)) {
      try {
        const e = raiz.matches(s) ? raiz : raiz.querySelector(s);
        if (e) return e;
      } catch (e) { /* selector inválido: se ignora */ }
    }
    return null;
  };
  // "$99<sup>00</sup>" son $99.00: los centavos en superíndice se leen como decimales.
  const textoPrecio = (el) => {
    if (!el) return null;
    const c = el.cloneNode(true);
    c.querySelectorAll('sup').forEach((s) => { s.textContent = '.' + s.textContent.trim(); });
    return c.textContent;
  };
  const vistos = new Set();
  const salida = [];
  let items = [];
  try {
    items = document.querySelectorAll(cfg.item);
  } catch (e) {
    return { error: 'Selector de producto inválido: ' + cfg.item };
  }
  for (const it of items) {
    const t = dentro(it, cfg.titulo);
    const titulo = ((t && (t.getAttribute('title') || t.textContent)) || '').trim().replace(/\s+/g, ' ');
    let precio = cfg.precio_attr ? numero(it.getAttribute(cfg.precio_attr)) : null;
    if (precio == null) {
      const p = dentro(it, cfg.precio);
      precio = numero(textoPrecio(p));
    }
    const a = dentro(it, cfg.enlace || 'a[href]');
    const img = it.querySelector('img');
    if (!titulo || precio == null || precio <= 0) continue;
    const clave = titulo + '|' + precio;
    if (vistos.has(clave)) continue;
    vistos.add(clave);
    salida.push({
      titulo: titulo.slice(0, 200),
      precio,
      url: a && a.href ? a.href : null,
      imagen: img ? img.currentSrc || img.src || null : null,
    });
    if (salida.length >= (cfg.max || 20)) break;
  }
  return salida;
}
