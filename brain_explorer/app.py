"""Dash app: interactive 3D cortical atlas viewer. Run with `python -m brain_explorer.app`."""
import numpy as np
import plotly.colors
import plotly.graph_objects as go
from dash import ClientsideFunction, Dash, Input, Output, State, ctx, dcc, html

from . import data

ATLASES = {name: load() for name, load in data.ATLASES.items()}
SURFACES = {name: {h: data.load_surface(h, s) for h in "LR"} for name, s in data.SURFACES.items()}
OVERLAYS = data.load_overlays()
HEMI_SLICE = {"L": slice(0, data.N_VERTICES), "R": slice(data.N_VERTICES, None)}
GREY = np.array([200, 200, 200])


def overlay_scale(name):
    """Colour scale and range of an overlay, symmetric around 0: grey for curvature, blue-red
    otherwise, cyclic for anything named 'phase' (e.g. fMRI phase fields)."""
    scale = "Greys" if name == "curvature" else "Phase" if "phase" in name.lower() else "RdBu_r"
    return scale, np.percentile(np.abs(OVERLAYS[name]), 98) or 1


def overlay_rgb(name, values):
    scale, vmax = overlay_scale(name)
    palette = np.array([plotly.colors.unlabel_rgb(c) for c in plotly.colors.sample_colorscale(scale, np.linspace(0, 1, 64))])
    return palette[np.clip((values / vmax + 1) / 2 * 63, 0, 63).astype(int)]


def region_label(atlas, rid):
    """Short label such as 'L V1' (Glasser) or 'Default' (Yeo)."""
    return f"{atlas['hemi'][rid]} {atlas['names'][rid]}".strip()


def dropdown_options(atlas):
    options = []
    for rid, name in atlas["names"].items():
        info = atlas["info"]["regions"].get(name) or atlas["info"]["regions"].get(name.split()[0], {})
        label = region_label(atlas, rid) + (f" - {info['full_name']}" if info else "")
        search = " ".join([label, info.get("location", ""), info.get("function", "")])  # dropdown search text
        options.append({"label": label, "value": rid, "search": search})
    return options


def make_figure(atlas, surface, hemis, selected, overlay):
    fig = go.Figure()
    for hemi in hemis:
        verts, faces = SURFACES[surface][hemi]
        labels = atlas["labels"][HEMI_SLICE[hemi]]
        rgb = atlas["colors"][labels].astype(float)
        text = [region_label(atlas, rid) if rid else "medial wall" for rid in labels]
        if overlay:  # overlay replaces the atlas colours; the selected region keeps its colour
            values = OVERLAYS[overlay][HEMI_SLICE[hemi]]
            rgb[labels != selected] = overlay_rgb(overlay, values)[labels != selected]
            text = [f"{t}<br>{overlay}: {v:.3g}" for t, v in zip(text, values)]
        elif selected is not None:  # fade everything except the selected region
            rgb[labels != selected] = 0.3 * rgb[labels != selected] + 0.7 * GREY
        x = verts[:, 0] + (0 if surface == "folded" else (-50 if hemi == "L" else 50))  # inflated hemispheres overlap otherwise
        fig.add_mesh3d(
            x=x, y=verts[:, 1], z=verts[:, 2], i=faces[:, 0], j=faces[:, 1], k=faces[:, 2],
            vertexcolor=[f"rgb({r:.0f},{g:.0f},{b:.0f})" for r, g, b in rgb],
            text=text,
            hoverinfo="text", name=hemi, lighting=dict(ambient=0.6, diffuse=0.6, specular=0.1),
        )
    if overlay:  # Mesh3d with vertex colours has no colour bar, so borrow one from an invisible marker
        scale, vmax = overlay_scale(overlay)
        fig.add_scatter3d(x=[0], y=[0], z=[0], mode="markers", hoverinfo="skip", marker=dict(
            size=0.1, colorscale=scale, cmin=-vmax, cmax=vmax, showscale=True, color=[0],
            colorbar=dict(title=overlay, len=0.4, thickness=12, x=0.98)))
    axis = dict(visible=False)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), showlegend=False, uirevision="keep",
                      scene=dict(xaxis=axis, yaxis=axis, zaxis=axis, aspectmode="data"))
    return fig


def region_info(atlas_name, atlas, rid):
    meta = atlas["info"]["atlas"]
    if rid is None:
        return html.Div([html.H3(meta["name"]), html.P(meta["description"]),
                         html.P(["Reference: "] + doi_link(meta["reference"])),
                         html.P(meta["note"], style={"color": "grey"}),
                         html.P("Click a region on the brain or use the search box.")])
    name = atlas["names"][rid]
    info = atlas["info"]["regions"].get(name) or atlas["info"]["regions"].get(name.split()[0])  # Schaefer: network entry
    overlap = network_overlap(atlas, rid)
    if info is None:
        return html.Div([html.H3(region_label(atlas, rid)), html.P(f"Atlas: {atlas_name}"),
                         html.P("No curated description yet for this region.", style={"color": "grey"}), overlap])
    return html.Div([
        html.H3(f"{region_label(atlas, rid)} - {info['full_name']}"),
        html.P(f"Atlas: {atlas_name}"),
        *[html.P([html.B(f"{key.capitalize()}: "), info[key]]) for key in ("location", "function", "status") if key in info],
        overlap,
        html.B("References"),
        html.Ul([html.Li(doi_link(ref)) for ref in info["references"]]
                + [html.Li(doi_link(meta["reference"]))]),
    ])


def network_overlap(atlas, rid):
    """Fraction of the region's vertices falling into each Yeo 7 network (computed from the data)."""
    yeo = ATLASES["Yeo 7 networks"]
    if atlas is yeo:
        return html.Div()
    counts = np.bincount(yeo["labels"][atlas["labels"] == rid], minlength=8)[1:]
    parts = [f"{yeo['names'][i + 1]} {100 * c / counts.sum():.0f}%" for i, c in enumerate(counts) if c / counts.sum() >= 0.05]
    return html.P([html.B("Yeo 7 network overlap: "), ", ".join(parts)])


def doi_link(ref):
    return [ref["text"], " ", html.A("doi", href=f"https://doi.org/{ref['doi']}", target="_blank")]


app = Dash(__name__, title="Brain Atlas Explorer")
app.layout = html.Div(style={"display": "flex", "height": "100vh", "fontFamily": "sans-serif"}, children=[
    html.Div(style={"width": "380px", "padding": "16px", "overflowY": "auto"}, children=[
        html.H2("Brain Atlas Explorer"),
        html.Label("Atlas"),
        dcc.Dropdown(id="atlas", options=list(ATLASES), value=list(ATLASES)[0], clearable=False),
        html.Label("Surface"),
        dcc.RadioItems(id="surface", options=list(SURFACES), value="inflated", inline=True),
        html.Label("Hemispheres"),
        dcc.Checklist(id="hemis", options=["L", "R"], value=["L", "R"], inline=True),
        html.Label("Search region (name, location, function)"),
        dcc.Dropdown(id="region", placeholder="e.g. V1, motion, Broca"),
        html.Label("Overlay (per-vertex data)"),
        dcc.Dropdown(id="overlay", options=list(OVERLAYS), placeholder="none"),
        html.Div(id="info"),
    ]),
    dcc.Graph(id="brain", style={"flex": 1}, config={"displaylogo": False}),
    dcc.Store(id="click"),  # clickData without the clicks that end a drag (see assets/click_filter.js)
])

app.clientside_callback(ClientsideFunction("brain", "filterClick"), Output("click", "data"), Input("brain", "clickData"))


@app.callback(Output("region", "options"), Output("region", "value"),
              Input("atlas", "value"), Input("click", "data"), State("hemis", "value"))
def select_region(atlas_name, click, hemis):
    """Reset the region list when the atlas changes; set the region when the brain is clicked."""
    atlas = ATLASES[atlas_name]
    if ctx.triggered_id == "click" and click:
        point = click["points"][0]  # curveNumber = index into hemis, pointNumber = vertex index
        rid = int(atlas["labels"][HEMI_SLICE[hemis[point["curveNumber"]]]][point["pointNumber"]])
        return dropdown_options(atlas), rid or None  # 0 = medial wall, nothing to show
    return dropdown_options(atlas), None


@app.callback(Output("brain", "figure"), Output("info", "children"),
              Input("atlas", "value"), Input("surface", "value"), Input("hemis", "value"),
              Input("region", "value"), Input("overlay", "value"))
def update_view(atlas_name, surface, hemis, rid, overlay):
    atlas = ATLASES[atlas_name]
    return make_figure(atlas, surface, hemis, rid, overlay), region_info(atlas_name, atlas, rid)


if __name__ == "__main__":
    app.run(debug=True)
