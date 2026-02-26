import argparse
import pathlib
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from html.parser import HTMLParser


class TileParser(HTMLParser):
    """Parse Trading Economics homepage to extract the 6 home tile titles and summaries."""

    def __init__(self):
        super().__init__()
        self.tiles: list[dict[str, str]] = []
        self._in_tile = False
        self._in_title = False
        self._in_desc = False
        self._current: dict[str, str] = {}
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "")
        if "home-tile-outside" in classes:
            self._in_tile = True
            self._current = {"title": "", "summary": ""}
            self._depth = 0
        if self._in_tile:
            self._depth += 1
            if tag == "b" and not self._current["title"]:
                self._in_title = True
            if "home-tile-description" in classes:
                self._in_desc = True

    def handle_endtag(self, tag):
        if self._in_tile:
            self._depth -= 1
            if tag == "b":
                self._in_title = False
            if self._in_desc and tag == "div":
                self._in_desc = False
            if self._depth <= 0:
                self._in_tile = False
                if self._current.get("title"):
                    self.tiles.append(self._current)

    def handle_data(self, data):
        if self._in_title:
            self._current["title"] += data
        elif self._in_desc:
            self._current["summary"] += data


def fetch_tiles() -> list[dict[str, str]]:
    req = urllib.request.Request(
        "https://tradingeconomics.com",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode()

    parser = TileParser()
    parser.feed(html)

    # Clean up whitespace
    for tile in parser.tiles:
        tile["title"] = " ".join(tile["title"].split())
        tile["summary"] = " ".join(tile["summary"].split())

    return parser.tiles[:6]


def generate_rss(tiles: list[dict[str, str]]) -> str:
    """Build an RSS 2.0 XML string from scraped tiles."""
    now = format_datetime(datetime.now(timezone.utc))

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Trading Economics Summary"
    ET.SubElement(channel, "link").text = "https://tradingeconomics.com"
    ET.SubElement(channel, "description").text = (
        "Hourly snapshot of Trading Economics homepage tiles"
    )
    ET.SubElement(channel, "lastBuildDate").text = now

    for tile in tiles:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = tile["title"]
        ET.SubElement(item, "description").text = tile["summary"]
        ET.SubElement(item, "pubDate").text = now

    ET.indent(rss)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(
        rss, encoding="unicode"
    )


INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Trading Economics Summary</title></head>
<body>
<h1>Trading Economics Summary</h1>
<p>Subscribe to the <a href="feed.xml">RSS feed</a> for hourly updates.</p>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Trading Economics homepage tiles"
    )
    parser.add_argument(
        "--rss",
        metavar="FILE",
        help="Write RSS feed to FILE (also writes index.html next to it)",
    )
    args = parser.parse_args()

    tiles = fetch_tiles()
    if not tiles:
        raise SystemExit("Error: no tiles scraped (site may be blocking this IP)")

    if args.rss == "-":
        sys.stdout.write(generate_rss(tiles))
    elif args.rss:
        rss_path = pathlib.Path(args.rss)
        rss_path.write_text(generate_rss(tiles), encoding="utf-8")
        index_path = rss_path.parent / "index.html"
        index_path.write_text(INDEX_HTML, encoding="utf-8")
        print(f"Wrote {rss_path} and {index_path}")
    else:
        for i, tile in enumerate(tiles, 1):
            print(f"\n{'='*80}")
            print(f"Tile {i}: {tile['title']}")
            print(f"{'='*80}")
            print(tile["summary"])
        print()


if __name__ == "__main__":
    main()
