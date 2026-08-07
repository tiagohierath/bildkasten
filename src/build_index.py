import argparse
import json
from pathlib import Path
import sys

from bildkasten_core import BASE, DATA_DIR, MODEL_NAME, PRETRAINED, image_files


def build_index(folder):
    import numpy as np
    import open_clip
    import torch
    from PIL import Image

    folder = Path(folder).expanduser().resolve()
    files = image_files(folder)
    if not files:
        raise SystemExit(f"No images found in {folder}")

    model, _, preprocess = open_clip.create_model_and_transforms(
        MODEL_NAME,
        pretrained=PRETRAINED,
    )
    model.eval()

    print(f"Found {len(files)} images in {folder}")
    embeddings = []
    metadata = []

    for i, file in enumerate(files, start=1):
        try:
            image = preprocess(Image.open(file).convert("RGB")).unsqueeze(0)
            with torch.no_grad():
                vector = model.encode_image(image)
            vector /= vector.norm(dim=-1, keepdim=True)
            embeddings.append(vector.cpu().numpy()[0])
            metadata.append(str(file))
            print(f"{i}/{len(files)} {file}")
        except Exception as exc:
            print(f"Failed: {file} {exc}")

    DATA_DIR.mkdir(exist_ok=True)
    np.save(DATA_DIR / "embeddings.npy", np.array(embeddings))
    with (DATA_DIR / "metadata.json").open("w") as fh:
        json.dump(metadata, fh, indent=2)
    print(f"Saved {len(metadata)} images to {DATA_DIR}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a Bildkasten CLIP index from a folder of images."
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=str(BASE / "images"),
        help=f"image folder, default: {BASE / 'images'}",
    )
    args = parser.parse_args(argv)
    try:
        build_index(args.folder)
    except (ImportError, ModuleNotFoundError) as exc:
        print(f"Dependency error: {exc}", file=sys.stderr)
        print("Run: bildkasten setup", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
