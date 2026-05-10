# actions/image_cluster.py
# ══════════════════════════════════════════════════════════════
# JARVIS Image Clustering Tool
# Organizes photos by visual similarity OR by faces detected
#
# pip install deepface opencv-python scikit-learn imutils
# pip install tensorflow keras  (for VGG16 object clustering)
#
# JARVIS commands that trigger this:
#   "meri photos ko organize karo faces ke hisaab se"
#   "downloads mein screenshots group karo"
#   "cluster my photos by face"
#   "organize images by similarity"
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Optional


# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}


def _get_image_files(folder: str) -> list[str]:
    """Return all image file paths in a folder."""
    folder_path = Path(folder).expanduser()
    if not folder_path.exists():
        return []
    return [
        str(p) for p in folder_path.rglob("*")
        if p.suffix.lower() in IMAGE_EXTENSIONS
    ]


# ══════════════════════════════════════════════════════════════
# FACE CLUSTERING
# ══════════════════════════════════════════════════════════════

def cluster_by_face(
    source_folder: str,
    output_folder: Optional[str] = None,
    sensitivity:   float = 12.0,
    copy_files:    bool  = True,
) -> str:
    """
    Groups images by the faces that appear in them.
    Uses FaceNet (via DeepFace) embeddings + DBSCAN clustering.

    Parameters
    ----------
    source_folder : folder containing images to analyze
    output_folder : where to save grouped results (default: source_folder/face_clusters)
    sensitivity   : DBSCAN eps — smaller = stricter grouping (default 12.0)
    copy_files    : True = copy files, False = just return report

    Returns
    -------
    Human-readable result string for JARVIS to speak
    """
    try:
        import numpy as np
        from deepface import DeepFace
        from sklearn.cluster import DBSCAN
    except ImportError as e:
        return (
            f"Face clustering requires extra packages.\n"
            f"Run: pip install deepface scikit-learn\n"
            f"Error: {e}"
        )

    image_files = _get_image_files(source_folder)
    if not image_files:
        return f"No images found in: {source_folder}"

    print(f"[ImageCluster] Analyzing {len(image_files)} images for faces...")

    # Extract face embeddings
    data = []
    skipped = 0
    for img_path in image_files:
        try:
            embedding_objs = DeepFace.represent(
                img_path=img_path,
                model_name="Facenet",
                enforce_detection=False,
            )
            if embedding_objs:
                emb = embedding_objs[0]["embedding"]
                data.append({"embedding": emb, "imagePath": img_path})
        except Exception:
            skipped += 1

    if not data:
        return f"No faces detected in any of the {len(image_files)} images."

    embeddings = np.array([d["embedding"] for d in data])

    # DBSCAN clustering
    clt = DBSCAN(eps=sensitivity, metric="euclidean", min_samples=1)
    clt.fit(embeddings)

    label_ids   = set(clt.labels_)
    n_clusters  = len([l for l in label_ids if l != -1])
    n_unknown   = list(clt.labels_).count(-1)

    # Organize into output folders
    if copy_files:
        out_dir = Path(output_folder or str(Path(source_folder) / "face_clusters"))
        out_dir.mkdir(parents=True, exist_ok=True)

        for label, item in zip(clt.labels_, data):
            if label == -1:
                dest_folder = out_dir / "unknown_faces"
            else:
                dest_folder = out_dir / f"person_{label + 1}"
            dest_folder.mkdir(exist_ok=True)

            src  = Path(item["imagePath"])
            dest = dest_folder / src.name
            if not dest.exists():
                shutil.copy2(str(src), str(dest))

        result = (
            f"Face clustering complete!\n"
            f"  Images analyzed : {len(data)}\n"
            f"  Images skipped  : {skipped} (no face detected)\n"
            f"  People found    : {n_clusters}\n"
            f"  Unknown faces   : {n_unknown}\n"
            f"  Output folder   : {out_dir}"
        )
    else:
        result = (
            f"Face analysis complete (dry run):\n"
            f"  Images analyzed : {len(data)}\n"
            f"  People found    : {n_clusters}\n"
            f"  Unknown faces   : {n_unknown}"
        )

    return result


# ══════════════════════════════════════════════════════════════
# OBJECT / VISUAL SIMILARITY CLUSTERING
# ══════════════════════════════════════════════════════════════

def cluster_by_similarity(
    source_folder: str,
    output_folder: Optional[str] = None,
    sensitivity:   float = 65.0,
    copy_files:    bool  = True,
    max_images:    int   = 200,
) -> str:
    """
    Groups images by visual content similarity.
    Uses VGG16 feature extraction (4096-dim) + DBSCAN clustering.
    Great for: screenshots, product photos, stock images.

    Parameters
    ----------
    source_folder : folder containing images
    output_folder : where to save groups
    sensitivity   : DBSCAN eps — larger = looser grouping (default 65)
    max_images    : limit to avoid very long processing times
    """
    try:
        import numpy as np
        from sklearn.cluster import DBSCAN
        import keras
        from keras import Model
        from keras.applications.vgg16 import VGG16, preprocess_input
        from keras.utils import load_img, img_to_array

    except ImportError as e:
        return (
            f"Object clustering requires extra packages.\n"
            f"Run: pip install tensorflow scikit-learn\n"
            f"Error: {e}"
        )

    image_files = _get_image_files(source_folder)[:max_images]
    if not image_files:
        return f"No images found in: {source_folder}"

    if len(image_files) == max_images:
        print(f"[ImageCluster] Processing first {max_images} images (limit reached)")

    print(f"[ImageCluster] Loading VGG16 model...")
    base_model = VGG16()
    model      = Model(inputs=base_model.inputs,
                       outputs=base_model.layers[-2].output)  # 4096-dim features

    print(f"[ImageCluster] Extracting features from {len(image_files)} images...")
    data    = []
    skipped = 0

    for img_path in image_files:
        try:
            img    = load_img(img_path, target_size=(224, 224))
            arr    = img_to_array(img)
            arr    = preprocess_input(arr.reshape(1, 224, 224, 3))
            feats  = model.predict(arr, verbose=0)
            feats  = feats.flatten()   # 4096-dim vector
            data.append({"encoding": feats, "imagePath": img_path})
        except Exception:
            skipped += 1

    if not data:
        return f"Could not extract features from any image in {source_folder}"

    encodings = np.array([d["encoding"] for d in data])

    # DBSCAN clustering
    clt = DBSCAN(eps=sensitivity, metric="euclidean", min_samples=1)
    clt.fit(encodings)

    label_ids  = set(clt.labels_)
    n_clusters = len([l for l in label_ids if l != -1])
    n_unique   = list(clt.labels_).count(-1)

    # Organize files
    if copy_files:
        out_dir = Path(output_folder or str(Path(source_folder) / "visual_clusters"))
        out_dir.mkdir(parents=True, exist_ok=True)

        for label, item in zip(clt.labels_, data):
            if label == -1:
                dest_folder = out_dir / "unique_images"
            else:
                dest_folder = out_dir / f"group_{label + 1}"
            dest_folder.mkdir(exist_ok=True)

            src  = Path(item["imagePath"])
            dest = dest_folder / src.name
            if not dest.exists():
                shutil.copy2(str(src), str(dest))

        result = (
            f"Visual clustering complete!\n"
            f"  Images analyzed : {len(data)}\n"
            f"  Images skipped  : {skipped}\n"
            f"  Groups found    : {n_clusters}\n"
            f"  Unique images   : {n_unique}\n"
            f"  Output folder   : {out_dir}"
        )
    else:
        result = (
            f"Visual analysis (dry run):\n"
            f"  Images analyzed : {len(data)}\n"
            f"  Groups found    : {n_clusters}"
        )

    return result


# ══════════════════════════════════════════════════════════════
# JARVIS TOOL DISPATCHER
# ══════════════════════════════════════════════════════════════

def image_cluster(parameters: dict, player=None, **kwargs) -> str:
    """
    Main JARVIS tool entry point.

    Tool parameters:
        mode          : "face" | "similarity" (default: "face")
        source_folder : path to folder with images
        output_folder : where to save results (optional)
        sensitivity   : clustering threshold (optional)
        dry_run       : if true, don't copy files, just report
    """
    mode          = parameters.get("mode", "face").lower()
    source_folder = parameters.get("source_folder", "")
    output_folder = parameters.get("output_folder", None)
    sensitivity   = float(parameters.get("sensitivity", 12.0 if mode == "face" else 65.0))
    dry_run       = parameters.get("dry_run", False)

    if not source_folder:
        return (
            "Please specify which folder to organize.\n"
            "Example: 'Cluster photos in my Downloads folder by face'"
        )

    # Expand common shortcuts
    source_folder = str(Path(source_folder).expanduser())
    if not Path(source_folder).exists():
        return f"Folder not found: {source_folder}"

    if player:
        player.write_log(f"[ImageCluster] {mode} clustering: {source_folder}")

    if mode == "face":
        return cluster_by_face(
            source_folder=source_folder,
            output_folder=output_folder,
            sensitivity=sensitivity,
            copy_files=not dry_run,
        )
    elif mode in ("similarity", "object", "visual"):
        return cluster_by_similarity(
            source_folder=source_folder,
            output_folder=output_folder,
            sensitivity=sensitivity,
            copy_files=not dry_run,
        )
    else:
        return f"Unknown mode '{mode}'. Use 'face' or 'similarity'."


# ── TOOL DECLARATION for JARVIS TOOL_DECLARATIONS list ────────
IMAGE_CLUSTER_TOOL = {
    "name": "image_cluster",
    "description": (
        "Organize and group photos/images by visual similarity or by the faces "
        "that appear in them. Can cluster screenshots by content type, group "
        "photos of the same person together, or sort images by visual similarity. "
        "Use when user says: organize photos, cluster images, group photos by face, "
        "sort screenshots by type."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["face", "similarity"],
                "description": "'face' to group by person, 'similarity' to group by visual content",
            },
            "source_folder": {
                "type": "string",
                "description": "Full path to folder containing images to organize",
            },
            "output_folder": {
                "type": "string",
                "description": "Where to save grouped results (optional — defaults to source/clusters)",
            },
            "sensitivity": {
                "type": "number",
                "description": "Clustering sensitivity: lower = stricter. Face: 12, Similarity: 65",
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, only analyze and report — don't copy any files",
            },
        },
        "required": ["mode", "source_folder"],
    },
}
