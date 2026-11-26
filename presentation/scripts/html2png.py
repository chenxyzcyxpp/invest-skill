"""html2png.py — 整页 HTML→PNG 截图小工具（NG-C1/NG-C2 小白卡共用）。

两遍无头 Chrome 法：先 --dump-dom 实测整页高度，再按实高 --screenshot。
截图前自动把 <details class="nv-evi"> 展开并把 summary 换成静态文案——
图片不能交互，"点开查看"印在图上会误导；交互版 HTML 不受影响。

用法：
    python -X utf8 presentation/scripts/html2png.py input.html -o out.png [--width 820]
    （Linux/root 环境若自动找不到浏览器，用环境变量 CHROME 指定，如 CHROME=/usr/bin/chromium）
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME_CANDIDATES = [
    os.environ.get('CHROME'),
    '/usr/bin/chromium',
    '/usr/bin/google-chrome',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
]

PROBE_JS = ('<script>window.addEventListener("load",function(){'
            'document.querySelectorAll("details.nv-evi").forEach(function(d){'
            'd.open=true;var s=d.querySelector("summary");'
            'if(s){s.textContent="数据与来源";}});'
            'document.documentElement.setAttribute("data-pageh",'
            'document.documentElement.scrollHeight)})</script></body>')


def _find_chrome() -> str:
    for p in CHROME_CANDIDATES:
        if p and Path(p).is_file():
            return p
    raise SystemExit('未找到 Chrome/Edge；可用环境变量 CHROME 指定浏览器 exe 路径')


def export_png(html: str, png_path: str, width: int = 820) -> None:
    """两遍无头浏览器法：先 --dump-dom 实测整页高度，再按实高 --screenshot。"""
    import shutil
    chrome = _find_chrome()
    tmp = Path(tempfile.mkstemp(suffix='.html')[1])
    tmp.write_text(html.replace('</body>', PROBE_JS, 1), encoding='utf-8')
    url = tmp.resolve().as_uri()
    profile = Path(tempfile.mkdtemp(prefix='html2png_'))  # 每次独立 profile，避免单例锁转发
    base = [chrome, '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
            '--disable-gpu', '--hide-scrollbars',
            f'--user-data-dir={profile}', '--virtual-time-budget=4000']
    try:
        r = subprocess.run(base + ['--dump-dom', url], capture_output=True, timeout=90)
        m = re.search(r'data-pageh="(\d+)"', r.stdout.decode('utf-8', 'ignore'))
        if not m:
            print('warn: dump-dom 未取到页高（探测脚本未执行？），退回卡片数估算', file=sys.stderr)
        est = 440 * html.count('class="nv-card')
        h = min(max(int(m.group(1)) if m else est, 400), 16000)
        out_png = Path(png_path).resolve()  # Chrome 对相对 --screenshot 路径解析不可靠，必须绝对
        subprocess.run(base + [f'--screenshot={out_png}', f'--window-size={width},{h}', url],
                       capture_output=True, timeout=90)
        print(f'png {png_path} ({width}x{h})')
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass  # Chrome 退出后短暂保留句柄；临时文件留在 %TEMP% 无碍
        shutil.rmtree(profile, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description='HTML→整页 PNG（无头 Chrome 两遍法）')
    ap.add_argument('input', help='输入 HTML 文件')
    ap.add_argument('-o', '--output', required=True, help='输出 PNG 路径')
    ap.add_argument('--width', type=int, default=820, help='截图宽度（默认 820）')
    a = ap.parse_args()
    html = Path(a.input).read_text(encoding='utf-8')
    export_png(html, a.output, a.width)


if __name__ == '__main__':
    main()
