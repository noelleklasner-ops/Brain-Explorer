"""Download and load fsLR 32k surfaces and parcellations. Sources are listed in README.md."""
import csv
import json
import urllib.request
from pathlib import Path

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"        # downloaded files (git-ignored)
ATLAS_DIR = ROOT / "atlases"    # curated region descriptions (JSON)
OVERLAY_DIR = DATA_DIR / "overlays"  # optional user overlays, see README

TEMPLATEFLOW = "https://templateflow.s3.amazonaws.com/tpl-fsLR/tpl-fsLR_den-32k_hemi-{hemi}_{surf}.surf.gii"
CBIG = "https://raw.githubusercontent.com/ThomasYeoLab/CBIG/master/stable_projects/brain_parcellation/"
MICAPIPE = "https://raw.githubusercontent.com/MICA-MNI/micapipe/master/parcellations/"

SURFACES = {"folded": "midthickness", "inflated": "inflated", "very inflated": "veryinflated"}
N_VERTICES = 32492  # per hemisphere; left vertices come first in all label arrays

YEO = CBIG + "Yeo2011_fcMRI_clustering/1000subjects_reference/Yeo_JNeurophysiol11_SplitLabels/fs_LR32k/"
SCHAEFER = CBIG + "Schaefer2018_LocalGlobal/Parcellations/HCP/fslr32k/cifti/"
URLS = {
    "yeo7.dlabel.nii": YEO + "Yeo2011_7Networks_N1000.dlabel.nii",
    "yeo17.dlabel.nii": YEO + "Yeo2011_17Networks_N1000.dlabel.nii",
    "schaefer200.dlabel.nii": SCHAEFER + "Schaefer2018_200Parcels_7Networks_order.dlabel.nii",
    "schaefer400.dlabel.nii": SCHAEFER + "Schaefer2018_400Parcels_7Networks_order.dlabel.nii",
    "glasser.csv": MICAPIPE + "glasser-360_conte69.csv",
    "glasser_lut.csv": MICAPIPE + "lut/lut_glasser-360_mics.csv",
    "desikan.csv": MICAPIPE + "aparc_conte69.csv",
    "desikan_lut.csv": MICAPIPE + "lut/lut_aparc_mics.csv",
    "destrieux.csv": MICAPIPE + "aparc-a2009s_conte69.csv",
    "destrieux_lut.csv": MICAPIPE + "lut/lut_aparc-a2009s_mics.csv",
}
for hemi in "LR":
    for surf in SURFACES.values():
        URLS[f"{hemi}.{surf}.surf.gii"] = TEMPLATEFLOW.format(hemi=hemi, surf=surf)


def fetch(name):
    """Return the local path of a data file, downloading it on first use."""
    path = DATA_DIR / name
    if not path.exists():
        DATA_DIR.mkdir(exist_ok=True)
        print(f"downloading {name} ...")
        urllib.request.urlretrieve(URLS[name], path)
    return path


def load_surface(hemi, surf):
    """Return (vertices, faces) of one hemisphere surface."""
    gii = nib.load(fetch(f"{hemi}.{surf}.surf.gii"))
    return gii.darrays[0].data, gii.darrays[1].data


def curvature(verts, faces):
    """Mean-curvature proxy: signed distance of each vertex from the mean of its neighbours along
    the outward normal. Positive in sulci, negative on gyral crowns (FreeSurfer sign convention)."""
    face_normals = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]], verts[faces[:, 2]] - verts[faces[:, 0]])
    normals = np.zeros_like(verts)
    np.add.at(normals, faces.ravel(), np.repeat(face_normals, 3, axis=0))
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.vstack([edges, edges[:, ::-1]])  # both directions
    neighbour_sum = np.zeros_like(verts)
    np.add.at(neighbour_sum, edges[:, 0], verts[edges[:, 1]])
    neighbour_mean = neighbour_sum / np.bincount(edges[:, 0], minlength=len(verts))[:, None]
    return np.einsum("ij,ij->i", neighbour_mean - verts, normals)


def load_overlays():
    """Per-vertex overlays (one value per vertex, left hemisphere first): the computed curvature
    plus every data/overlays/<name>.npy or data/overlays/<name>.L.func.gii + .R.func.gii pair."""
    overlays = {"curvature": np.concatenate([curvature(*load_surface(h, "midthickness")) for h in "LR"])}
    for f in sorted(OVERLAY_DIR.glob("*.npy")):
        overlays[f.stem] = np.load(f)
    for f in sorted(OVERLAY_DIR.glob("*.L.*.gii")):
        overlays[f.name.split(".")[0]] = np.concatenate(
            [nib.load(str(f).replace(".L.", f".{h}.")).darrays[0].data for h in "LR"])
    return overlays


def _atlas(key, labels, names, hemi, colors):
    """Bundle an atlas: per-vertex label ids plus per-id name, hemisphere, colour and curated info."""
    info = json.loads((ATLAS_DIR / f"{key}.json").read_text())
    return {"labels": labels, "names": names, "hemi": hemi, "colors": colors, "info": info}


def load_micapipe(key, n_per_hemi, clean_name):
    """Load a micapipe vertex CSV plus its lookup table. Region ids are the LUT 'mics' ids:
    1001.. for the left hemisphere, 2001.. for the right (0 stays the medial wall)."""
    labels = np.loadtxt(fetch(f"{key}.csv")).astype(int)
    if labels.max() <= 2 * n_per_hemi:  # glasser and desikan CSVs count 1..2n instead of using mics ids
        labels = np.where(labels > n_per_hemi, labels - n_per_hemi + 2000, labels + 1000) * (labels > 0)
    names, hemi, colors = {}, {}, np.zeros((2001 + n_per_hemi, 3), dtype=np.uint8)
    with open(fetch(f"{key}_lut.csv")) as f:
        for row in csv.DictReader(f):
            rid, label = int(row["mics"]), row["label"].strip()
            if "medial wall" in label.lower().replace("_", " "):
                continue
            names[rid], hemi[rid] = clean_name(label), "L" if rid < 2000 else "R"
            colors[rid] = [int(row[c]) for c in "RGB"]
    labels[~np.isin(labels, list(names))] = 0  # e.g. Destrieux's own medial-wall label
    return _atlas(key, labels, names, hemi, colors)


def load_glasser():  # LUT label "V1"
    return load_micapipe("glasser", 180, lambda label: label)


def load_desikan():  # LUT label "ctx-lh-superiorfrontal"
    return load_micapipe("desikan", 35, lambda label: label.split("-")[-1])


def load_destrieux():  # LUT label "ctx_lh_G_and_S_frontomargin"
    return load_micapipe("destrieux", 75, lambda label: label.split("_", 2)[-1])


def load_dlabel(key, filename, parse_name):
    """Load a CIFTI dlabel file; parse_name turns a label-table name into (region name, hemisphere)."""
    img = nib.load(fetch(filename))
    labels = img.get_fdata()[0].astype(int)  # 0 = medial wall
    table = img.header.get_axis(0).label[0]  # id -> (name, (r, g, b, a))
    names, hemi = {}, {}
    for rid, (raw, _) in table.items():
        if rid:
            names[rid], hemi[rid] = parse_name(raw)
    colors = np.array([[int(255 * c) for c in table[i][1][:3]] for i in range(len(table))], dtype=np.uint8)
    return _atlas(key, labels, names, hemi, colors)


YEO7_NAMES = ["Visual", "Somatomotor", "Dorsal attention", "Ventral attention",
              "Limbic", "Frontoparietal", "Default"]  # order of 7Networks_1..7 in Yeo et al. 2011


def load_yeo7():  # "7Networks_3" -> "Dorsal attention"
    return load_dlabel("yeo7", "yeo7.dlabel.nii", lambda raw: (YEO7_NAMES[int(raw.split("_")[1]) - 1], ""))


def load_yeo17():  # "17Networks_3" -> "Network 3" (the 17 networks have no official names)
    return load_dlabel("yeo17", "yeo17.dlabel.nii", lambda raw: ("Network " + raw.split("_")[1], ""))


def load_schaefer(n):  # "7Networks_LH_Default_pCunPCC_3" -> ("Default pCunPCC 3", "L")
    def parse(raw):
        _, hemi, *parts = raw.split("_")
        return " ".join(parts), hemi[0]
    return lambda: load_dlabel("schaefer", f"schaefer{n}.dlabel.nii", parse)


ATLASES = {
    "Glasser HCP-MMP1.0 (360)": load_glasser,
    "Desikan-Killiany (aparc)": load_desikan,
    "Destrieux (148)": load_destrieux,
    "Schaefer 200 (7 networks)": load_schaefer(200),
    "Schaefer 400 (7 networks)": load_schaefer(400),
    "Yeo 7 networks": load_yeo7,
    "Yeo 17 networks": load_yeo17,
}
