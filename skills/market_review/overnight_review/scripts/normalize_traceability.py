#!/usr/bin/env python3
"""Normalize visible traceability labels while preserving raw data-refId values.

Usage:
  python normalize_traceability.py input.md output.html --start auto

Rules:
- Raw <a class="chat_link_a" data-refId="...">[...]</a> tags remain unchanged in Markdown.
- Visible labels in generated HTML become continuous numeric labels.
- The same data-refId always receives the same number.
- `auto` starts after the largest existing manual numeric citation in Markdown.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TAG_RE = re.compile(
    r'<a class="chat_link_a" data-refId="([^"]+)">\[([^\]]+)\]</a>'
)
NUM_RE = re.compile(r'(?<![\w>])\[(\d+)\]')
STYLE_RE = re.compile(
    r'<style id="traceability-numeric-labels">.*?</style>\s*', re.S
)
STYLE_MAP_RE = re.compile(
    r'\.chat_link_a\[data-refId="([^"]+)"\]::after\{content:"\[(\d+)\]"\}'
)


def build_mapping(markdown_text: str, start: str = "auto") -> dict[str, int]:
    existing = {ref_id: int(n) for ref_id, n in STYLE_MAP_RE.findall(markdown_text)}
    clean_text = STYLE_RE.sub('', markdown_text)
    if start == "auto":
        nums = [int(x) for x in NUM_RE.findall(clean_text)]
        next_num = max(nums, default=0) + 1
    else:
        next_num = int(start)
    mapping: dict[str, int] = {}
    for ref_id, _ in TAG_RE.findall(clean_text):
        if ref_id in existing:
            mapping[ref_id] = existing[ref_id]
        elif ref_id not in mapping:
            while next_num in mapping.values() or next_num in existing.values():
                next_num += 1
            mapping[ref_id] = next_num
            next_num += 1
    return mapping


def visible_html(html_text: str, mapping: dict[str, int]) -> str:
    def repl(match: re.Match[str]) -> str:
        ref_id = match.group(1)
        n = mapping[ref_id]
        return f'<a class="chat_link_a" data-refId="{ref_id}">[{n}]</a>'
    return TAG_RE.sub(repl, html_text)


def markdown_display_css(mapping: dict[str, int]) -> str:
    # Keeps original tags byte-for-byte; CSS only changes rendered text.
    rules = [
        '<style id="traceability-numeric-labels">',
        '.chat_link_a{font-size:0;white-space:nowrap}',
        '.chat_link_a::after{font-size:12px}',
    ]
    for ref_id, n in mapping.items():
        safe = ref_id.replace('\\', '\\\\').replace('"', '\\"')
        rules.append(
            f'.chat_link_a[data-refId="{safe}"]::after{{content:"[{n}]"}}'
        )
    rules.append('</style>')
    return '\n'.join(rules)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('input_md')
    ap.add_argument('--html-in')
    ap.add_argument('--html-out')
    ap.add_argument('--map-out')
    ap.add_argument('--start', default='auto')
    ap.add_argument('--inject-md-css', action='store_true')
    args = ap.parse_args()

    md_path = Path(args.input_md)
    md = md_path.read_text(encoding='utf-8')
    mapping = build_mapping(md, args.start)

    if args.inject_md_css and mapping:
        marker = '<style id="traceability-numeric-labels">'
        if marker in md:
            md = STYLE_RE.sub('', md)
        md = markdown_display_css(mapping) + '\n\n' + md
        md_path.write_text(md, encoding='utf-8')

    if args.html_in and args.html_out:
        html = Path(args.html_in).read_text(encoding='utf-8')
        Path(args.html_out).write_text(visible_html(html, mapping), encoding='utf-8')

    if args.map_out:
        Path(args.map_out).write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8'
        )

    print(json.dumps({"mapped": len(mapping), "mapping": mapping}, ensure_ascii=False))


if __name__ == '__main__':
    main()
