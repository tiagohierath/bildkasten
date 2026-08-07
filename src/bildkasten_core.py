from pathlib import Path
import json
import logging
import os
import shlex
import shutil
import subprocess

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / "data"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
METADATA_PATH = DATA_DIR / "metadata.json"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
MODEL_NAME = os.environ.get("BILDKASTEN_MODEL", "ViT-B-32")
PRETRAINED = os.environ.get("BILDKASTEN_PRETRAINED", "laion2b_s34b_b79k")

_model = None
_tokenizer = None


def quiet_hf_warnings():
    if os.environ.get("BILDKASTEN_VERBOSE"):
        return
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub.utils._http").setLevel(logging.ERROR)


def available_index(base=BASE):
    return (base / "data" / "embeddings.npy").exists() and (base / "data" / "metadata.json").exists()


def index_stats(base=BASE):
    if not available_index(base):
        return None
    with (base / "data" / "metadata.json").open() as fh:
        metadata = json.load(fh)
    return {
        "count": len(metadata),
        "embeddings": str(base / "data" / "embeddings.npy"),
        "metadata": str(base / "data" / "metadata.json"),
    }


def image_files(folder):
    root = Path(folder).expanduser().resolve()
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def load_text_model():
    global _model, _tokenizer
    if _model is None or _tokenizer is None:
        quiet_hf_warnings()
        import open_clip

        _model, _, _ = open_clip.create_model_and_transforms(
            MODEL_NAME,
            pretrained=PRETRAINED,
        )
        _model.eval()
        _tokenizer = open_clip.get_tokenizer(MODEL_NAME)
    return _model, _tokenizer


def encode_text(query):
    import torch

    model, tokenizer = load_text_model()
    text = tokenizer([query])
    with torch.no_grad():
        vector = model.encode_text(text)
    vector /= vector.norm(dim=-1, keepdim=True)
    return vector.cpu().numpy()[0]


def load_index(base=BASE):
    import numpy as np

    embeddings_path = base / "data" / "embeddings.npy"
    metadata_path = base / "data" / "metadata.json"
    if not embeddings_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            "No Bildkasten index found. Run: bildkasten index /path/to/images"
        )
    embeddings = np.load(embeddings_path)
    with metadata_path.open() as fh:
        metadata = json.load(fh)
    return embeddings, metadata


def search(query, limit=50, base=BASE):
    import numpy as np

    query = query.strip()
    if not query:
        return []
    embeddings, metadata = load_index(base)
    vector = encode_text(query)
    scores = embeddings @ vector
    top = np.argsort(scores)[::-1][:limit]
    return [
        {
            "score": float(scores[i]),
            "path": metadata[i],
            "name": Path(metadata[i]).name,
        }
        for i in top
    ]


def choose_viewer():
    configured = os.environ.get("BILDKASTEN_VIEWER")
    if configured:
        return shlex.split(configured)
    if shutil.which("mpv"):
        return ["mpv", "--image-display-duration=3"]
    if shutil.which("xdg-open"):
        return ["xdg-open"]
    if shutil.which("gio"):
        return ["gio", "open"]
    raise RuntimeError("No viewer found. Install mpv or set BILDKASTEN_VIEWER.")


def single_file_opener(viewer):
    name = Path(viewer[0]).name if viewer else ""
    return name in {"xdg-open", "open"} or viewer[:2] == ["gio", "open"]


def open_files(files, wait=True):
    files = [str(f) for f in files if f]
    if not files:
        return
    viewer = choose_viewer()
    if single_file_opener(viewer):
        if len(files) > 1:
            raise RuntimeError(
                "Multiple-image slideshow needs mpv or BILDKASTEN_VIEWER set to a viewer that accepts many files."
            )
        subprocess.Popen(viewer + files, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if not wait:
        subprocess.Popen(viewer + files, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    subprocess.run(viewer + files, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def reveal_file(file):
    path = Path(file).expanduser().resolve()
    target = path.parent if path.exists() else path
    opener = None
    for candidate in (["xdg-open"], ["gio", "open"], ["open"]):
        if shutil.which(candidate[0]):
            opener = candidate
            break
    if not opener:
        raise RuntimeError("No folder opener found. Install xdg-open or gio.")
    subprocess.Popen(opener + [str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def copy_text(text):
    commands = (
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["pbcopy"],
    )
    for command in commands:
        if shutil.which(command[0]):
            subprocess.run(command, input=text.encode(), check=True)
            return
    raise RuntimeError("No clipboard command found. Install wl-clipboard, xclip, or xsel.")
