import curses
from pathlib import Path
import textwrap

from bildkasten_core import available_index, copy_text, index_stats, open_files, reveal_file, search


HELP = "Enter search  Up/Down select  Space/o open  p play  c copy path  r reveal  Ctrl+U clear  q quit"


class App:
    def __init__(self, screen):
        self.screen = screen
        self.query = ""
        self.results = []
        self.selected = 0
        stats = index_stats()
        if stats:
            self.status = f"Ready. {stats['count']} indexed images."
        else:
            self.status = "No index yet. Quit and run: bildkasten index /path/to/images"

    def addstr(self, y, x, text, attr=curses.A_NORMAL):
        try:
            h, w = self.screen.getmaxyx()
            if y < h and x < w:
                self.screen.addstr(y, x, text[:max(0, w - x - 1)], attr)
        except curses.error:
            pass

    def draw(self):
        s = self.screen
        s.erase()
        h, w = s.getmaxyx()
        if h < 10 or w < 40:
            self.addstr(0, 0, "Make the terminal bigger.", curses.A_BOLD)
            s.refresh()
            return
        title = "Bildkasten"
        self.addstr(0, 0, title, curses.A_BOLD)
        self.addstr(1, 0, "Search: " + self.query)
        self.addstr(2, 0, HELP, curses.A_DIM)
        if self.status:
            for i, line in enumerate(textwrap.wrap(self.status, max(20, w - 1))[:2]):
                self.addstr(4 + i, 0, line, curses.A_DIM)

        top = 7
        visible = max(1, h - top - 1)
        offset = max(0, self.selected - visible + 1)
        for row, item in enumerate(self.results[offset:offset + visible], start=top):
            idx = offset + row - top
            marker = ">" if idx == self.selected else " "
            score = f"{item['score']:.3f}"
            name = Path(item["path"]).name
            line = f"{marker} {score}  {name}"
            attr = curses.A_REVERSE if idx == self.selected else curses.A_NORMAL
            self.addstr(row, 0, line, attr)

        if self.results:
            footer = f"{self.selected + 1}/{len(self.results)}  {self.results[self.selected]['path']}"
            self.addstr(h - 1, 0, footer, curses.A_DIM)
        else:
            self.addstr(top, 0, "No results yet.", curses.A_DIM)
        try:
            s.move(1, min(w - 1, len("Search: ") + len(self.query)))
        except curses.error:
            pass
        s.refresh()

    def do_search(self):
        if not self.query.strip():
            self.status = "Type something first, for example: red cloak, foggy forest, girl sitting."
            return
        if not available_index():
            self.status = "No index found. Run: bildkasten index /path/to/images"
            return
        self.status = "Loading CLIP and searching..."
        self.draw()
        try:
            self.results = search(self.query, limit=80)
            self.selected = 0
            self.status = f"{len(self.results)} results for: {self.query}"
        except Exception as exc:
            self.results = []
            self.status = f"Search failed: {exc}"

    def open_selected(self):
        if not self.results:
            return
        self.status = "Opening selected image..."
        self.draw()
        try:
            open_files([self.results[self.selected]["path"]], wait=False)
            self.status = "Opened selected image."
        except Exception as exc:
            self.status = f"Open failed: {exc}"

    def play_results(self):
        if not self.results:
            return
        self.status = "Playing result set..."
        self.draw()
        try:
            open_files([item["path"] for item in self.results], wait=False)
            self.status = "Sent result set to viewer."
        except Exception as exc:
            self.status = f"Play failed: {exc}"

    def copy_selected(self):
        if not self.results:
            return
        try:
            copy_text(self.results[self.selected]["path"])
            self.status = "Copied selected path."
        except Exception as exc:
            self.status = f"Copy failed: {exc}"

    def reveal_selected(self):
        if not self.results:
            return
        try:
            reveal_file(self.results[self.selected]["path"])
            self.status = "Opened containing folder."
        except Exception as exc:
            self.status = f"Reveal failed: {exc}"

    def page(self, delta):
        h, _ = self.screen.getmaxyx()
        step = max(1, h - 9)
        self.selected = min(max(0, len(self.results) - 1), max(0, self.selected + delta * step))

    def handle_key(self, key):
        if key in ("q", "\x1b"):
            return False
        if key in ("\n", "\r"):
            self.do_search()
        elif key in ("KEY_UP", "k"):
            self.selected = max(0, self.selected - 1)
        elif key in ("KEY_DOWN", "j"):
            self.selected = min(max(0, len(self.results) - 1), self.selected + 1)
        elif key == "KEY_PPAGE":
            self.page(-1)
        elif key == "KEY_NPAGE":
            self.page(1)
        elif key in (" ", "o"):
            self.open_selected()
        elif key == "p":
            self.play_results()
        elif key == "c":
            self.copy_selected()
        elif key == "r":
            self.reveal_selected()
        elif key == "\x15":
            self.query = ""
            self.status = "Cleared search."
        elif key in ("KEY_BACKSPACE", "\b", "\x7f"):
            self.query = self.query[:-1]
        elif isinstance(key, str) and len(key) == 1 and key.isprintable():
            self.query += key
        return True

    def run(self):
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        self.screen.keypad(True)
        while True:
            self.draw()
            try:
                key = self.screen.get_wch()
            except curses.error:
                continue
            if not self.handle_key(key):
                break


def main():
    curses.wrapper(lambda screen: App(screen).run())


if __name__ == "__main__":
    main()
