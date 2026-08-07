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
./bin/bildkasten install-user
bildkasten index ~/Pictures
bildkasten
```

If something feels wrong:

```bash
bildkasten doctor
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
./bin/bildkasten install-user
bildkasten index ~/Pictures/reference
bildkasten
```

The first run downloads the CLIP model weights from Hugging Face. After that the
model is cached locally.

## Quick Start Without Nix

You need Python 3.12+, pip, and preferably `mpv`.

```bash
git clone https://github.com/tiagohierath/bildkasten.git
cd bildkasten
./bin/bildkasten setup
./bin/bildkasten install-user
bildkasten index ~/Pictures/reference
bildkasten
```

If you do not have `mpv`, Bildkasten tries `xdg-open` or `gio open`. You can
also set your own viewer:

```bash
export BILDKASTEN_VIEWER="feh"
```

## Commands

Open the TUI:

```bash
bildkasten
```

Build or rebuild the index:

```bash
bildkasten index ~/Pictures/reference
```

Check whether dependencies, viewer, and index are ready:

```bash
bildkasten doctor
```

Search from the shell and open the top results:

```bash
bildkasten search "girl sitting"
```

Open the storyboard doodle tool:

```bash
bildkasten storyboard
```

Open storyboard mode for a specific folder and save boards somewhere else:

```bash
bildkasten storyboard ~/Pictures/reference --out ~/storyboards
```

Print results without opening a viewer:

```bash
bildkasten search "red cloak" --print
```

Limit results:

```bash
bildkasten search "foggy city" --limit 12
```

## TUI Keys

- Type normally; `Backspace`, `Delete`, `Left`, and `Right` edit the search.
- Press `Enter` to search and open one MPV slideshow with the results.
- `Up` / `Down`: move through results.
- `Ctrl+B`: open the browser storyboard tool.
- `Ctrl+O`: open the selected image.
- `Ctrl+P`: replay the whole result set as one slideshow.
- `Ctrl+Y`: copy the selected image path.
- `Ctrl+R`: reveal the selected image in its folder.
- `PageUp` / `PageDown`: move faster through results.
- `Ctrl+U`: clear the search line.
- `Esc` or `Ctrl+Q`: quit.

## Storyboard Mode

Storyboard mode opens a local browser page:

```bash
bildkasten storyboard
```

It shows one reference image on the left and a white canvas on the right. Drag
the wide divider between them when you want the reference or the drawing board
bigger; double-click the divider or press `=` in the Reference label to reset
the split. Use it for rough storyboard ideas, not polished art.

The important controls are:

- `Pen` / `p`: draw black strokes.
- `Eraser` / `e`: erase with white strokes.
- Brush slider: change stroke size.
- `Undo` / `Ctrl+Z` / `z`: undo the last stroke or clear.
- `Clear`: wipe the current board.
- `Save now`: save the current board.
- `Save + Next`: save and move forward.
- `Ctrl+Enter`: save and move forward.
- `Skip`: move forward without intentionally saving the current board.
- `Prev`: go back one image.
- Reference `-` / `=` / `+`: make the reference pane smaller, reset, or bigger.
- Search: type a CLIP query and press `Enter` to load the top 80 reference
  images; clear it and press `Enter` to return to shuffled All images.
- Aspect selector: switch between `4:3`, `16:9`, `Pan H 2:1`, and `Pan V 3:4`.
  The pan formats give you moderate extra width/height for later camera moves.

The drawing canvas uses a soft dab brush rather than straight vector strokes,
so quick sketching feels more like marking pixels on paper. The dark surround
around the board makes the composition edge easier to see. Each board includes
a thin dark-blue center cross and safe-area border, visible while drawing and
saved into the final PNG.

`All images` is the default and is shuffled each time you load it. You can also
choose the `30 most recent`, `100 most recent`, or a custom recent count.
`4:3` is the default board format. Boards autosave after each stroke and are
saved as PNG files in:

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
