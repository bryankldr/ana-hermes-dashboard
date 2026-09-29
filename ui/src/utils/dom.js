// utils/dom.js — the one place that builds a HUD panel.
//
// Every panel used to repeat the same 4 lines: createElement, set id/class,
// innerHTML, appendChild to a rail, then a separate register() call in
// init(). This does it once and guarantees the panel is registered the
// moment it exists, so callers never have to remember.
//
// ponytail: ids + title + html is all the variation any panel needs. Add a
// options bag only when a panel actually wants placement or a class.
const RAILS = { left: '.left-rail', right: '.right-rail', center: '#coreSvg', hud: '#hud' };

/**
 * Create (or reuse) a panel and attach it to a rail.
 * @param {{id:string, title?:string, body?:string, rail?:keyof RAILS,
 *          className?:string, register?:boolean}} opts
 * @returns {HTMLElement} the panel element
 */
export function ensurePanel({ id, title = '', body = '', rail = 'left', className = '', register = true }) {
  let el = document.getElementById(id);
  if (el) {
    // Update body content if provided (for dynamic panels like voicePicker)
    if (body) {
      const bodyEl = el.querySelector('.panel-body');
      if (bodyEl) bodyEl.innerHTML = body;
    }
    return el;
  }
  el = document.createElement('div');
  el.id = id;
  el.className = ('panel ' + className).trim();
  // LayoutManager.register() runs after measure() has already emptied the
  // rail, so it cannot see which rail this panel came from — it needs the
  // side to pick the right stacking cursor.
  el.dataset.rail = rail;
  el.innerHTML = (title ? `<div class="panel-title">${title}</div>` : '')
    + (body ? `<div class="panel-body">${body}</div>` : '');
  const host = document.querySelector(RAILS[rail] || RAILS.left);
  // A missing rail must not silently drop the panel on the floor.
  if (!host) { console.warn('ensurePanel: rail not found', rail, id); return el; }
  host.appendChild(el);
  if (register && window._layoutManager) window._layoutManager.register(id);
  return el;
}
