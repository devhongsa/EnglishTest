# -*- coding: utf-8 -*-
"""data.json 내용을 현재 index.html 의 DATA 에만 주입한다. UI/폼은 건드리지 않음."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML_PATH = ROOT / "index.html"
DATA_PATH = ROOT / "data.json"


def inject_data(html: str, data: dict) -> str:
    marker = "const DATA = "
    fav = "const FAV_KEY"
    start = html.find(marker)
    if start < 0:
        raise ValueError("index.html 에서 'const DATA =' 를 찾지 못했습니다.")
    end = html.find(fav, start)
    if end < 0:
        raise ValueError("index.html 에서 'const FAV_KEY' 를 찾지 못했습니다.")
    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return html[:start] + marker + embedded + ";\n    " + html[end:]


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    html = HTML_PATH.read_text(encoding="utf-8")
    out = inject_data(html, data)
    HTML_PATH.write_text(out, encoding="utf-8")
    print("ok", HTML_PATH.name, HTML_PATH.stat().st_size)


if __name__ == "__main__":
    main()
