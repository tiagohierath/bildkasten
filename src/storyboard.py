import argparse
import base64
import json
import mimetypes
from pathlib import Path
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import webbrowser

from bildkasten_core import BASE, METADATA_PATH, image_files


DEFAULT_PORT = 8765


def clean_name(value):
    value = Path(value).stem.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:60] or "image"


def read_index_paths():
    if not METADATA_PATH.exists():
        return []
    with METADATA_PATH.open() as fh:
        return [Path(p) for p in json.load(fh)]


def collect_images(folder=None):
    if folder:
        paths = image_files(folder)
    else:
        paths = [p for p in read_index_paths() if p.exists()]
        if not paths:
            paths = image_files(BASE / "images")
    paths = [p.resolve() for p in paths if p.exists()]
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return paths


def image_payload(paths, mode, count):
    selected = paths
    if mode == "recent":
        selected = paths[:count]
    return [
        {
            "id": i,
            "name": p.name,
            "mtime": int(p.stat().st_mtime),
            "url": f"/image/{i}",
        }
        for i, p in enumerate(selected)
    ]


def page_html():
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bildkasten Storyboard</title>
  <style>
    :root { color-scheme: light; --bg:#f5f5f2; --fg:#171717; --muted:#666; --line:#c9c9c3; }
    * { box-sizing: border-box; }
    body { margin: 0; font: 15px/1.35 system-ui, sans-serif; background: var(--bg); color: var(--fg); }
    header { display: flex; gap: .7rem; align-items: center; flex-wrap: wrap; padding: .75rem 1rem; border-bottom: 1px solid var(--line); background: #fff; }
    header strong { margin-right: .5rem; }
    button, select, input { font: inherit; border: 1px solid var(--line); background: #fff; color: var(--fg); padding: .42rem .55rem; }
    button { cursor: pointer; }
    button:hover { background: #eee; }
    button.active { background: #171717; border-color: #171717; color: #fff; }
    input[type=number] { width: 5.5rem; }
    input[type=range] { width: 7rem; vertical-align: middle; }
    main { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(360px, 1fr); gap: 1rem; padding: 1rem; height: calc(100vh - 59px); }
    .pane { min-width: 0; display: flex; flex-direction: column; gap: .6rem; }
    .label { display: flex; justify-content: space-between; gap: 1rem; color: var(--muted); font-size: .9rem; }
    .frame { flex: 1; min-height: 0; display: grid; place-items: center; background: #fff; border: 1px solid var(--line); overflow: hidden; }
    #reference { max-width: 100%; max-height: 100%; width: auto; height: auto; object-fit: contain; }
    #board { width: 100%; max-height: 100%; height: auto; background: #fff; touch-action: none; cursor: crosshair; box-shadow: 0 0 0 1px #ddd; }
    .bar { display: grid; grid-template-columns: 1fr auto; gap: .7rem; align-items: center; }
    progress { width: 100%; height: 1rem; }
    .tools { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
    .status { color: var(--muted); min-height: 1.3rem; }
    .empty { padding: 2rem; text-align: center; color: var(--muted); }
    @media (max-width: 850px) {
      main { grid-template-columns: 1fr; height: auto; }
      .frame { min-height: 42vh; }
    }
  </style>
</head>
<body>
  <header>
    <strong>Bildkasten Storyboard</strong>
    <select id="mode">
      <option value="recent" data-count="30">30 most recent</option>
      <option value="recent" data-count="100">100 most recent</option>
      <option value="all">All images</option>
      <option value="recent" data-custom="1">Custom recent</option>
    </select>
    <input id="count" type="number" min="1" value="30" hidden>
    <select id="aspect">
      <option value="16:9">16:9</option>
      <option value="4:3">4:3</option>
    </select>
    <button id="start">Start</button>
    <button id="prev">Prev</button>
    <button id="next">Save + Next</button>
    <button id="skip">Skip</button>
    <span class="status" id="status"></span>
  </header>

  <main>
    <section class="pane">
      <div class="label"><span>Reference</span><span id="refName"></span></div>
      <div class="frame"><img id="reference" alt=""></div>
      <div class="bar"><progress id="progress" value="0" max="1"></progress><span id="counter">0/0</span></div>
    </section>
    <section class="pane">
      <div class="label"><span>Storyboard canvas</span><span id="saveState">Not saved yet</span></div>
      <div class="frame"><canvas id="board"></canvas></div>
      <div class="tools">
        <button id="pen" class="active">Pen</button>
        <button id="eraser">Eraser</button>
        <label>Brush <input id="brush" type="range" min="1" max="22" value="4"></label>
        <button id="undo">Undo</button>
        <button id="clear">Clear</button>
        <button id="save">Save now</button>
      </div>
      <div class="status">Simple doodles only: pen, eraser, undo, clear. Autosaves after each stroke.</div>
    </section>
  </main>

  <script>
    const img = document.getElementById('reference');
    const canvas = document.getElementById('board');
    const ctx = canvas.getContext('2d');
    const mode = document.getElementById('mode');
    const count = document.getElementById('count');
    const aspect = document.getElementById('aspect');
    const statusEl = document.getElementById('status');
    const saveState = document.getElementById('saveState');
    const refName = document.getElementById('refName');
    const progress = document.getElementById('progress');
    const counter = document.getElementById('counter');
    const brush = document.getElementById('brush');
    const penBtn = document.getElementById('pen');
    const eraserBtn = document.getElementById('eraser');
    let images = [];
    let index = 0;
    let drawing = false;
    let dirty = false;
    let undoStack = [];
    let saveTimer = null;
    let tool = 'pen';

    function status(text) { statusEl.textContent = text; }

    function cancelScheduledSave() {
      clearTimeout(saveTimer);
      saveTimer = null;
    }

    function canvasSize() {
      return aspect.value === '4:3' ? [1280, 960] : [1280, 720];
    }

    function resetCanvas() {
      const [w, h] = canvasSize();
      canvas.width = w;
      canvas.height = h;
      fillWhite();
      undoStack = [];
      dirty = false;
      saveState.textContent = 'Not saved yet';
    }

    function fillWhite() {
      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      applyTool();
    }

    function applyTool() {
      ctx.strokeStyle = tool === 'eraser' ? 'white' : 'black';
      ctx.lineWidth = Number(brush.value);
      penBtn.classList.toggle('active', tool === 'pen');
      eraserBtn.classList.toggle('active', tool === 'eraser');
      canvas.style.cursor = tool === 'eraser' ? 'cell' : 'crosshair';
    }

    function setTool(nextTool) {
      tool = nextTool;
      applyTool();
      status(tool === 'eraser' ? 'Eraser' : 'Pen');
    }

    function showImage() {
      cancelScheduledSave();
      if (!images.length) {
        document.querySelector('.frame').innerHTML = '<div class="empty">No images found. Run bildkasten index /path/to/images or pass a folder to storyboard.</div>';
        return;
      }
      const item = images[index];
      img.src = item.url + '?t=' + Date.now();
      img.alt = item.name;
      refName.textContent = item.name;
      progress.max = images.length;
      progress.value = index + 1;
      counter.textContent = (index + 1) + '/' + images.length;
      resetCanvas();
    }

    async function loadImages() {
      if (dirty) await saveCurrent(false);
      const opt = mode.options[mode.selectedIndex];
      count.hidden = !opt.dataset.custom;
      const n = opt.dataset.custom ? count.value : (opt.dataset.count || count.value);
      const url = '/api/images?mode=' + encodeURIComponent(mode.value) + '&count=' + encodeURIComponent(n);
      const res = await fetch(url);
      const data = await res.json();
      images = data.images;
      index = 0;
      status(data.total + ' available, ' + images.length + ' selected. Saving to ' + data.out);
      showImage();
    }

    function pointerPos(e) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: (e.clientX - rect.left) * canvas.width / rect.width,
        y: (e.clientY - rect.top) * canvas.height / rect.height,
      };
    }

    function pushUndo() {
      undoStack.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
      if (undoStack.length > 20) undoStack.shift();
    }

    canvas.addEventListener('pointerdown', e => {
      pushUndo();
      drawing = true;
      canvas.setPointerCapture(e.pointerId);
      applyTool();
      const p = pointerPos(e);
      ctx.fillStyle = ctx.strokeStyle;
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(1, ctx.lineWidth / 2), 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
      dirty = true;
      saveState.textContent = 'Unsaved changes';
    });

    canvas.addEventListener('pointermove', e => {
      if (!drawing) return;
      const p = pointerPos(e);
      applyTool();
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      dirty = true;
      saveState.textContent = 'Unsaved changes';
    });

    function endStroke() {
      if (!drawing) return;
      drawing = false;
      scheduleSave();
    }
    canvas.addEventListener('pointerup', endStroke);
    canvas.addEventListener('pointercancel', endStroke);

    function scheduleSave() {
      cancelScheduledSave();
      saveTimer = setTimeout(() => saveCurrent(false), 650);
    }

    async function saveCurrent(showStatus = true) {
      if (!images.length) return;
      cancelScheduledSave();
      const item = images[index];
      const payload = {
        index: index + 1,
        imageId: item.id,
        imageName: item.name,
        aspect: aspect.value,
        dataUrl: canvas.toDataURL('image/png'),
      };
      const res = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        const message = data.error || 'unknown error';
        saveState.textContent = 'Save failed';
        status('Save failed: ' + message);
        throw new Error(message);
      }
      dirty = false;
      saveState.textContent = 'Saved ' + data.file;
      if (showStatus) status('Saved ' + data.file);
    }

    async function next(save) {
      if (!images.length) return;
      if (save) await saveCurrent(false);
      if (index >= images.length - 1) {
        status('Finished ' + images.length + ' images.');
        saveState.textContent = save ? 'Saved final image' : 'Final image skipped';
        return;
      }
      index = Math.min(images.length - 1, index + 1);
      showImage();
    }

    function undo() {
      const prev = undoStack.pop();
      if (!prev) return;
      ctx.putImageData(prev, 0, 0);
      applyTool();
      dirty = true;
      saveState.textContent = 'Unsaved changes';
      scheduleSave();
    }

    function clearBoard() {
      pushUndo();
      fillWhite();
      dirty = true;
      saveState.textContent = 'Unsaved changes';
      scheduleSave();
    }

    document.getElementById('start').onclick = loadImages;
    document.getElementById('save').onclick = () => saveCurrent(true);
    document.getElementById('next').onclick = () => next(true);
    document.getElementById('skip').onclick = () => next(false);
    document.getElementById('prev').onclick = async () => {
      if (dirty) await saveCurrent(false);
      if (index <= 0) {
        status('Already at the first image.');
        return;
      }
      index = Math.max(0, index - 1);
      showImage();
    };
    document.getElementById('clear').onclick = clearBoard;
    document.getElementById('undo').onclick = undo;
    penBtn.onclick = () => setTool('pen');
    eraserBtn.onclick = () => setTool('eraser');
    brush.oninput = applyTool;
    aspect.onchange = async () => {
      if (dirty) await saveCurrent(false);
      resetCanvas();
    };
    mode.onchange = () => { count.hidden = !mode.options[mode.selectedIndex].dataset.custom; };
    document.addEventListener('keydown', e => {
      if (e.target.matches('input, select, textarea')) return;
      if (e.key.toLowerCase() === 'p') setTool('pen');
      if (e.key.toLowerCase() === 'e') setTool('eraser');
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        undo();
      }
    });

    resetCanvas();
    loadImages();
  </script>
</body>
</html>"""


class StoryboardHandler(BaseHTTPRequestHandler):
    server_version = "BildkastenStoryboard/1.0"

    def image_path_from_request(self):
        try:
            image_id = int(urlparse(self.path).path.rsplit("/", 1)[1])
            return self.server.paths[image_id]
        except (ValueError, IndexError):
            return None

    def send_image(self, path, include_body=True):
        if not path or not path.exists():
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        if include_body:
            with path.open("rb") as fh:
                self.wfile.write(fh.read())

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = page_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/images":
            params = parse_qs(parsed.query)
            mode = params.get("mode", ["recent"])[0]
            try:
                count = max(1, int(params.get("count", ["30"])[0]))
            except ValueError:
                count = 30
            images = image_payload(self.server.paths, mode, count)
            self.send_json({
                "images": images,
                "selected": len(images),
                "total": len(self.server.paths),
                "out": str(self.server.out_dir),
            })
            return
        if parsed.path.startswith("/image/"):
            self.send_image(self.image_path_from_request())
            return
        self.send_error(404)

    def do_HEAD(self):
        if urlparse(self.path).path.startswith("/image/"):
            self.send_image(self.image_path_from_request(), include_body=False)
            return
        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/save":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            data = json.loads(self.rfile.read(length))
            header, encoded = data["dataUrl"].split(",", 1)
            raw = base64.b64decode(encoded)
            aspect = data.get("aspect", "16:9").replace(":", "x")
            index = int(data.get("index", 1))
            name = clean_name(data.get("imageName", "image"))
            filename = f"{index:04d}_{aspect}_{name}.png"
            path = self.server.out_dir / filename
            path.write_bytes(raw)
            meta = {
                "file": filename,
                "source": str(self.server.paths[int(data["imageId"])]),
                "aspect": data.get("aspect", "16:9"),
            }
            path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
            self.send_json({"ok": True, "file": filename})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def log_message(self, fmt, *args):
        return


class StoryboardServer(ThreadingHTTPServer):
    def __init__(self, address, handler, paths, out_dir):
        super().__init__(address, handler)
        self.paths = paths
        self.out_dir = out_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open the Bildkasten storyboard browser.")
    parser.add_argument("folder", nargs="?", help="optional image folder; defaults to the indexed library")
    parser.add_argument("--out", default=str(BASE / "storyboards"), help="output folder for PNG boards")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true", help="do not open the browser automatically")
    args = parser.parse_args(argv)

    paths = collect_images(args.folder)
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    server = StoryboardServer(("127.0.0.1", args.port), StoryboardHandler, paths, out_dir)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Bildkasten storyboard: {url}")
    print(f"{len(paths)} images available. Saving to: {out_dir}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStoryboard server stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
