// Plotly's 3D scene emits a click as soon as a mouse button is pressed over the mesh,
// so rotating would select regions. Hold the click back and only pass it on when the
// button is released without the mouse having moved (a plain single click).
let pending = null, pressedAt = null, dragged = false;
document.addEventListener("mousedown", e => { pressedAt = [e.clientX, e.clientY]; dragged = false; }, true);
document.addEventListener("mousemove", e => {
  if (pressedAt && Math.hypot(e.clientX - pressedAt[0], e.clientY - pressedAt[1]) > 3) dragged = true;
}, true);
document.addEventListener("mouseup", () => {
  if (pending && !dragged) window.dash_clientside.set_props("click", { data: pending });
  pending = pressedAt = null;
}, true);
window.dash_clientside = Object.assign({}, window.dash_clientside, {
  brain: { filterClick: click => { pending = click; return window.dash_clientside.no_update; } },
});
