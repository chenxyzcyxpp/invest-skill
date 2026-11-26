#!/usr/bin/env python3
"""Embed all local HTML image dependencies as data URIs.

Usage:
  python render_self_contained_html.py input.html [output.html]

The output is a single portable HTML file. Remote http(s) and existing data URIs are left intact.
Missing local images are fatal.
"""
from __future__ import annotations

import argparse
import base64
import mimetypes
import re
from pathlib import Path

IMG_RE = re.compile(r'(<img\b[^>]*?\bsrc=["\'])([^"\']+)(["\'][^>]*>)', re.I)
CSS_URL_RE = re.compile(r'url\((["\']?)(?!data:|https?://|#)([^)"\']+)\1\)', re.I)


def as_data_uri(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f'Local asset not found: {path}')
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'data:{mime};base64,{encoded}'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('input_html')
    ap.add_argument('output_html', nargs='?')
    args = ap.parse_args()
    src = Path(args.input_html).resolve()
    out = Path(args.output_html).resolve() if args.output_html else src
    html = src.read_text(encoding='utf-8')
    count = 0

    def img_repl(m: re.Match[str]) -> str:
        nonlocal count
        value = m.group(2).strip()
        if value.startswith(('data:', 'http://', 'https://')):
            return m.group(0)
        target = (src.parent / value).resolve()
        count += 1
        return f'{m.group(1)}{as_data_uri(target)}{m.group(3)}'

    def css_repl(m: re.Match[str]) -> str:
        nonlocal count
        value = m.group(2).strip()
        target = (src.parent / value).resolve()
        count += 1
        return f'url("{as_data_uri(target)}")'

    html = IMG_RE.sub(img_repl, html)
    html = CSS_URL_RE.sub(css_repl, html)
    out.write_text(html, encoding='utf-8')

    local_img = re.findall(r'<img\b[^>]*?\bsrc=["\'](?!data:|https?://)([^"\']+)', html, re.I)
    local_css = CSS_URL_RE.findall(html)
    if local_img or local_css:
        raise RuntimeError(f'Portable HTML validation failed: img={local_img}, css={local_css}')
    print(f'DELIVERABLE File created: {out}')
    print(f'Embedded local assets: {count}')


if __name__ == '__main__':
    main()
