import curses
from pathlib import Path
import subprocess
from urllib.request import urlopen
import webbrowser

from bildkasten_core import BASE, available_index, copy_text, index_stats, open_files, reveal_file, search


PRIMARY_HELP = "Enter slideshow   Up/Down select   Ctrl+B storyboard   Ctrl+O open   Ctrl+P replay   Esc quit"
SECONDARY_HELP = "Backspace/Delete edit   Left/Right move cursor   Ctrl+U clear   Ctrl+Y copy path   Ctrl+R reveal"

LOGO = [
    " ____  ___ _     ____  _  __    _    ____ _____ _____ _   _ ",
    "| __ )|_ _| |   |  _ \\| |/ /   / \\  / ___|_   _| ____| \\ | |",
    "|  _ \\ | || |   | | | | ' /   / _ \\ \\___ \\ | | |  _| |  \\| |",
    "| |_) || || |___| |_| | . \\  / ___ \\ ___) || | | |___| |\\  |",
    "|____/|___|_____|____/|_|\\_\\/_/   \\_\\____/ |_| |_____|_| \\_|",
]


class App:
    def __init__(self, screen):
        self.screen = screen
        self.query = ""
        self.cursor = 0
        self.input_y = 1
        self.input_x = len("Search: ")
        self.input_scroll = 0
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

    def clip(self, text, width):
        if width <= 0:
            return ""
        if len(text) <= width:
            return text
        if width <= 1:
            return text[:width]
        return text[:width - 1] + "…"

    def add_center(self, y, text, attr=curses.A_NORMAL):
        _, w = self.screen.getmaxyx()
        text = self.clip(text, max(0, w - 1))
        self.addstr(y, max(0, (w - len(text)) // 2), text, attr)

    def add_rule(self, y, left, width):
        if width > 0:
            self.addstr(y, left, "─" * width, curses.A_DIM)

    def draw(self):
        s = self.screen
        s.erase()
        h, w = s.getmaxyx()
        if h < 15 or w < 44:
            self.addstr(0, 0, "Make the terminal bigger.", curses.A_BOLD)
            s.refresh()
            return

        logo = LOGO if w >= max(len(line) for line in LOGO) + 2 and h >= 22 else ["BILDKASTEN"]
        logo_top = 1
        for i, line in enumerate(logo):
            self.add_center(logo_top + i, line, curses.A_BOLD)

        search_y = logo_top + len(logo) + 2
        self.draw_search_bar(search_y, w)
        status_y = search_y + 2
        if self.status:
            self.add_center(status_y, self.status, curses.A_DIM)

        left = max(0, (w - min(104, w - 2)) // 2)
        width = min(104, w - left - 1)
        top = status_y + 2
        bottom_help_y = h - 3
        visible = max(1, bottom_help_y - top - 2)

        self.add_rule(top, left, width)
        if self.results:
            heading = f"results {self.selected + 1}/{len(self.results)}"
            self.addstr(top, left, heading, curses.A_DIM)
        else:
            self.addstr(top, left, "results", curses.A_DIM)

        offset = max(0, self.selected - visible + 1)
        result_y = top + 2
        for row, item in enumerate(self.results[offset:offset + visible], start=result_y):
            idx = offset + row - result_y
            marker = ">" if idx == self.selected else " "
            score = f"{item['score']:.3f}"
            name = Path(item["path"]).name
            line = self.clip(f"{marker} {score}  {name}", width)
            attr = curses.A_REVERSE if idx == self.selected else curses.A_NORMAL
            self.addstr(row, left, line.ljust(width), attr)

        if self.results:
            selected_path = self.results[self.selected]["path"]
            self.addstr(bottom_help_y - 1, left, self.clip(selected_path, width), curses.A_DIM)
        else:
            self.add_center(result_y, "type a search and press Enter", curses.A_DIM)

        self.add_center(bottom_help_y, PRIMARY_HELP, curses.A_DIM)
        self.add_center(bottom_help_y + 1, SECONDARY_HELP, curses.A_DIM)
        try:
            s.move(self.input_y, min(w - 1, self.input_x + self.cursor - self.input_scroll))
        except curses.error:
            pass
        s.refresh()

    def draw_search_bar(self, y, width):
        bar_width = min(84, max(24, width - 4))
        inner_width = max(1, bar_width - 4)
        bar_x = max(0, (width - bar_width) // 2)

        if self.cursor < self.input_scroll:
            self.input_scroll = self.cursor
        elif self.cursor >= self.input_scroll + inner_width:
            self.input_scroll = self.cursor - inner_width + 1

        visible_query = self.query[self.input_scroll:self.input_scroll + inner_width]
        bar = "[ " + visible_query.ljust(inner_width) + " ]"
        label = "Search"
        self.addstr(y - 1, bar_x, label, curses.A_DIM)
        self.addstr(y, bar_x, bar, curses.A_REVERSE)
        self.input_y = y
        self.input_x = bar_x + 2

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
            if self.results:
                self.status = f"{len(self.results)} results for: {self.query}. Opening slideshow..."
                self.draw()
                self.open_result_slideshow()
            else:
                self.status = f"No results for: {self.query}"
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
        self.open_result_slideshow()

    def open_result_slideshow(self):
        try:
            open_files([item["path"] for item in self.results], wait=False)
            self.status = f"Opened one slideshow with {len(self.results)} images."
        except Exception as exc:
            self.status = f"Slideshow failed: {exc}"

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

    def open_storyboard(self):
        url = "http://127.0.0.1:8765/"
        try:
            with urlopen(url + "api/images?mode=recent&count=1", timeout=0.25):
                pass
            webbrowser.open(url)
            self.status = f"Opened existing storyboard: {url}"
            return
        except Exception:
            pass

        try:
            subprocess.Popen(
                [str(BASE / "bin" / "bildkasten"), "storyboard"],
                cwd=str(BASE),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.status = f"Started storyboard: {url}"
        except Exception as exc:
            self.status = f"Storyboard failed: {exc}"

    def page(self, delta):
        h, _ = self.screen.getmaxyx()
        step = max(1, h - 9)
        self.selected = min(max(0, len(self.results) - 1), max(0, self.selected + delta * step))

    def insert_text(self, text):
        self.query = self.query[:self.cursor] + text + self.query[self.cursor:]
        self.cursor += len(text)

    def backspace(self):
        if self.cursor <= 0:
            return
        self.query = self.query[:self.cursor - 1] + self.query[self.cursor:]
        self.cursor -= 1

    def delete_forward(self):
        if self.cursor >= len(self.query):
            return
        self.query = self.query[:self.cursor] + self.query[self.cursor + 1:]

    def handle_key(self, key):
        if key in ("\x1b", "\x11"):
            return False
        if key in ("\n", "\r"):
            self.do_search()
        elif key in ("KEY_UP", curses.KEY_UP):
            self.selected = max(0, self.selected - 1)
        elif key in ("KEY_DOWN", curses.KEY_DOWN):
            self.selected = min(max(0, len(self.results) - 1), self.selected + 1)
        elif key in ("KEY_LEFT", curses.KEY_LEFT):
            self.cursor = max(0, self.cursor - 1)
        elif key in ("KEY_RIGHT", curses.KEY_RIGHT):
            self.cursor = min(len(self.query), self.cursor + 1)
        elif key in ("\x01", "KEY_HOME", curses.KEY_HOME):
            self.cursor = 0
        elif key in ("\x05", "KEY_END", curses.KEY_END):
            self.cursor = len(self.query)
        elif key in ("KEY_PPAGE", curses.KEY_PPAGE):
            self.page(-1)
        elif key in ("KEY_NPAGE", curses.KEY_NPAGE):
            self.page(1)
        elif key == "\x02":
            self.open_storyboard()
        elif key == "\x0f":
            self.open_selected()
        elif key == "\x10":
            self.play_results()
        elif key == "\x19":
            self.copy_selected()
        elif key == "\x12":
            self.reveal_selected()
        elif key == "\x15":
            self.query = ""
            self.cursor = 0
            self.status = "Cleared search."
        elif key in ("KEY_BACKSPACE", "\b", "\x08", "\x7f", curses.KEY_BACKSPACE, 8, 127):
            self.backspace()
        elif key in ("KEY_DC", curses.KEY_DC, 330):
            self.delete_forward()
        elif isinstance(key, str) and len(key) == 1 and key.isprintable():
            self.insert_text(key)
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
