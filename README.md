# Bildkasten

Bildkasten is a small terminal image search box for visual memory.

Point it at a folder of reference images, build a CLIP index, then search with
plain language in a terminal UI:

```bash
bildkasten
```

Type `red cloak`, `foggy street`, `girl sitting`, `ornate helmet`, or whatever
you remember. Bildkasten ranks your local images by visual meaning and opens the
ones you choose.

## The Friend Setup

This is the shortest path for someone who just cloned the repo:

```bash
cd bildkasten
./bin/bildkasten setup
./bin/bildkasten index ~/Pictures
./bin/bildkasten
```

If something feels wrong:

```bash
./bin/bildkasten doctor
```

## What It Does

- Searches your own image library with natural language.
- Runs locally; your images are not uploaded anywhere.
- Opens a simple TUI when you run `bildkasten`.
- Keeps the fast CLI flow: `bildkasten "girl sitting"`.
- Opens a browser storyboard doodle tool for redrawing references quickly.
- Uses `mpv` for viewing images when available.

## Quick Start With Nix

```bash
git clone https://github.com/tiagohierath/bildkasten.git
cd bildkasten
nix develop
./bin/bildkasten setup
./bin/bildkasten index ~/Pictures/reference
./bin/bildkasten
```

The first run downloads the CLIP model weights from Hugging Face. After that the
model is cached locally.

## Quick Start Without Nix

You need Python 3.12+, pip, and preferably `mpv`.

```bash
git clone https://github.com/tiagohierath/bildkasten.git
cd bildkasten
./bin/bildkasten setup
./bin/bildkasten index ~/Pictures/reference
./bin/bildkasten
```

If you do not have `mpv`, Bildkasten tries `xdg-open` or `gio open`. You can
also set your own viewer:

```bash
export BILDKASTEN_VIEWER="feh"
```

## Commands

Open the TUI:

```bash
./bin/bildkasten
```

Build or rebuild the index:

```bash
./bin/bildkasten index ~/Pictures/reference
```

Check whether dependencies, viewer, and index are ready:

```bash
./bin/bildkasten doctor
```

Search from the shell and open the top results:

```bash
./bin/bildkasten "girl sitting"
```

Open the storyboard doodle tool:

```bash
./bin/bildkasten storyboard
```

Open storyboard mode for a specific folder and save boards somewhere else:

```bash
./bin/bildkasten storyboard ~/Pictures/reference --out ~/storyboards
```

Print results without opening a viewer:

```bash
./bin/bildkasten "red cloak" --print
```

Limit results:

```bash
./bin/bildkasten "foggy city" --limit 12
```

## TUI Keys

- Type a search, then press `Enter`.
- `Up` / `Down` or `k` / `j`: move through results.
- `Space` or `o`: open the selected image.
- `p`: play the whole result set in the viewer.
- `c`: copy the selected image path.
- `r`: reveal the selected image in its folder.
- `PageUp` / `PageDown`: move faster through results.
- `Ctrl+U`: clear the search line.
- `q`: quit.

## Storyboard Mode

Storyboard mode opens a local browser page:

```bash
./bin/bildkasten storyboard
```

It shows one reference image on the left and a white canvas on the right. Use it
for rough storyboard ideas, not polished art.

The important controls are:

- `Pen` / `p`: draw black strokes.
- `Eraser` / `e`: erase with white strokes.
- Brush slider: change stroke size.
- `Undo` / `Ctrl+Z`: undo the last stroke or clear.
- `Clear`: wipe the current board.
- `Save now`: save the current board.
- `Save + Next`: save and move forward.
- `Skip`: move forward without intentionally saving the current board.
- `Prev`: go back one image.
- Aspect selector: switch between `16:9` and `4:3`.

You can choose the `30 most recent`, `100 most recent`, `All images`, or a custom
recent count. Boards autosave after each stroke and are saved as PNG files in:

```text
storyboards/
```

## Files

Bildkasten writes its local index here:

```text
data/embeddings.npy
data/metadata.json
storyboards/
```

Those files are ignored by git because they are machine-specific and can be
large. The same is true for `images/`, `.venv/`, and loose image files in the
project folder.

## Notes

The default model is `ViT-B-32` with `laion2b_s34b_b79k` weights. You can
override it:

```bash
export BILDKASTEN_MODEL="ViT-B-32"
export BILDKASTEN_PRETRAINED="laion2b_s34b_b79k"
```

On NixOS, use `nix develop`; it sets the library path that PyTorch wheels need.
