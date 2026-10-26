# Brain Atlas Explorer

A small, local 3D brain atlas for neuroscience education and research: rotate an fsLR 32k cortical
surface, switch between parcellations, click a region and read a short, referenced description.

## Quick start

```bash
git clone <this repo> && cd Brain-Explorer
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m brain_explorer.app
```

Open http://127.0.0.1:8050 in a browser. On first start the surfaces and atlases (about 6 MB)
are downloaded into `data/`; later starts take about ten seconds.

Controls: choose the atlas, the surface (folded / inflated / very inflated) and the hemispheres,
then click on the brain or search a region by name, location or function.
The selected region stays coloured while everything else is greyed out.

## Overlays

The "Overlay" dropdown colours the surface by one value per vertex instead of the atlas.
Built in is `curvature`, computed from the folded mesh (positive in sulci, negative on gyri;
a simple proxy, not FreeSurfer's `curv`). To add your own data, e.g. fMRI phase fields, put
files into `data/overlays/`:

- `<name>.npy`: a float array of 64 984 values, left hemisphere (32 492 vertices) first; or
- `<name>.L.func.gii` and `<name>.R.func.gii`: one fsLR 32k GIFTI per hemisphere.

Colours are symmetric around zero (98th percentile of |value| saturates). Names containing
`phase` use a cyclic colour scale. Clicking a region still works and keeps it in its atlas colour.

## Architecture

```
brain_explorer/
  data.py    download + load surfaces (GIFTI), parcellations (CIFTI / CSV) and overlays -> numpy arrays
  app.py     Dash layout, Plotly Mesh3d figure, two callbacks (select region, update view)
atlases/
  *.json     curated region descriptions and references, one file per atlas (hand-written)
data/        downloaded files (git-ignored, created on first run)
```

Everything is vertex based: each atlas is one integer label per vertex of the 32 492-vertex
fsLR hemispheres (left first, then right), plus a name and colour per label id.
Because all atlases live on the same vertices, the app computes how a Glasser region overlaps
with the Yeo networks directly from the data instead of storing it by hand.

Adding an atlas means writing one `load_*` function in `data.py` that returns the same dictionary
and one JSON file in `atlases/`. Adding a region description means adding an entry to the JSON.

## Region descriptions

Each entry in `atlases/*.json` has `full_name`, `location`, `function`, `status`
(`established` or `tentative`) and `references` with DOIs; anatomical atlases omit `function`. The viewer shows only what is in
the file; regions without an entry show their atlas abbreviation only.
No functional association is generated automatically. Please keep it that way when extending
the files: cite a source for every claim.

## Data sources and licences

| Data | Source | Licence / attribution |
|---|---|---|
| fsLR 32k surfaces (midthickness, inflated, very inflated) | [TemplateFlow](https://www.templateflow.org/) `tpl-fsLR`, S3 mirror | Derived from HCP/Conte69 data; see TemplateFlow and the [HCP open access terms](https://www.humanconnectome.org/study/hcp-young-adult/document/wu-minn-hcp-consortium-open-access-data-use-terms) |
| Glasser HCP-MMP1.0 labels on fsLR 32k | [micapipe](https://github.com/MICA-MNI/micapipe) `parcellations/` | micapipe is GPL-3.0; the parcellation is from Glasser et al. 2016, [10.1038/nature18933](https://doi.org/10.1038/nature18933) |
| Desikan-Killiany and Destrieux labels on fsLR 32k | [micapipe](https://github.com/MICA-MNI/micapipe) `parcellations/` | FreeSurfer atlases; cite Desikan et al. 2006, [10.1016/j.neuroimage.2006.01.021](https://doi.org/10.1016/j.neuroimage.2006.01.021) and Destrieux et al. 2010, [10.1016/j.neuroimage.2010.06.010](https://doi.org/10.1016/j.neuroimage.2010.06.010) |
| Yeo 7 and 17 networks on fsLR 32k | [CBIG](https://github.com/ThomasYeoLab/CBIG) `Yeo2011_fcMRI_clustering` | MIT (CBIG); cite Yeo et al. 2011, [10.1152/jn.00338.2011](https://doi.org/10.1152/jn.00338.2011) |
| Schaefer 200 / 400 parcels on fsLR 32k | [CBIG](https://github.com/ThomasYeoLab/CBIG) `Schaefer2018_LocalGlobal` | MIT (CBIG); cite Schaefer et al. 2018, [10.1093/cercor/bhx179](https://doi.org/10.1093/cercor/bhx179) |

If you publish results based on these data, cite the original papers.

## Roadmap

- More curated region descriptions (currently 62 of the 180 Glasser areas, plus the Yeo networks).
- Subcortical and cerebellar atlases (needs volume rendering or extra surfaces).
- Per-overlay colour scale settings and a fixed value range option.

## Using HCP surfaces instead

The loader only downloads a file if it is missing from `data/`. If you have a BALSA account you can
download the HCP S1200 group-average (or a single subject's) fsLR 32k surfaces, save them as
`data/L.inflated.surf.gii`, `data/R.midthickness.surf.gii` etc., and the app will use them.
The atlases line up unchanged because the vertex numbering is the same.
