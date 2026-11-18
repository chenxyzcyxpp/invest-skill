#!/usr/bin/env python3
"""
股票对比报告 PDF 生成器

将 Markdown 格式的股票对比报告转换为 PDF，确保：
- 中文字体支持（避免乱码）
- 白色背景
- 专业美观的排版
- 图表清晰

依赖：
    pip install markdown2 weasyprint fonttools

使用：
    python generate_pdf.py input.md [output.pdf]
"""

import sys
import os
from pathlib import Path

try:
    import markdown2
    from weasyprint import HTML, CSS
except ImportError as e:
    print(f"[ERROR] 缺少依赖：{e}")
    print("\n请安装所需依赖:")
    print("  pip install markdown2 weasyprint")
    sys.exit(1)


# PDF 样式配置（专业证券分析报告风格）
PDF_CSS = """
@page {
    size: A4;
    margin: 2.5cm;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 9pt;
        color: #666;
    }
    @top-center {
        content: string(chapter);
        font-size: 9pt;
        color: #666;
        font-style: italic;
    }
}

@page :first {
    @top-center { content: none; }
}

body {
    font-family: "Noto Serif CJK SC", "Source Han Serif SC", "SimSun", "STSong", serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #1a1a1a;
    background: #FFFFFF;
    text-align: justify;
}

h1 {
    font-size: 18pt;
    font-weight: bold;
    color: #1a1a1a;
    text-align: center;
    margin: 2em 0 1em 0;
    string-set: chapter content();
}

h2 {
    font-size: 14pt;
    font-weight: bold;
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 0.3em;
    margin: 1.5em 0 0.8em 0;
    page-break-before: avoid;
}

h2:first-of-type {
    page-break-before: avoid;
}

h3 {
    font-size: 12pt;
    font-weight: bold;
    color: #34495e;
    margin: 1.2em 0 0.6em 0;
}

h4 {
    font-size: 10.5pt;
    font-weight: bold;
    color: #7f8c8d;
    margin: 1em 0 0.5em 0;
}

p {
    margin: 0.6em 0;
    text-indent: 2em;
}

/* 报告头部信息不缩进 */
h1 + p {
    text-indent: 0 !important;
}

ul, ol {
    margin: 0.6em 0;
    padding-left: 2em;
}

li {
    margin: 0.3em 0;
}

strong {
    font-weight: bold;
    color: #2c3e50;
}

em {
    font-style: italic;
}

blockquote {
    border-left: 4px solid #3498db;
    padding-left: 1em;
    margin: 1em 0;
    color: #555;
    font-style: italic;
    background: #f8f9fa;
    padding: 0.8em 1em;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 9.5pt;
}

th, td {
    border: 1px solid #ddd;
    padding: 0.6em 0.8em;
    text-align: left;
}

th {
    background: #3498db;
    color: white;
    font-weight: bold;
}

tr:nth-child(even) {
    background: #f8f9fa;
}

tr:hover {
    background: #e8f4f8;
}

code {
    font-family: "Courier New", Courier, monospace;
    background: #f5f5f5;
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-size: 9pt;
}

pre {
    background: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 1em;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.4;
}

pre code {
    background: none;
    padding: 0;
}

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
    border: 1px solid #ddd;
    border-radius: 4px;
}

.figure-caption {
    text-align: center;
    font-size: 9pt;
    color: #666;
    font-style: italic;
    margin-top: 0.5em;
}

/* 数据来源部分样式 */
#data-sources, .data-sources {
    font-size: 9pt;
    border-top: 2px solid #3498db;
    margin-top: 1em !important;
    padding-top: 0.5em !important;
    page-break-inside: avoid !important;
    page-break-after: avoid !important;
}

#data-sources ol, .data-sources ol {
    list-style: none !important;
    padding-left: 0 !important;
    margin: 0.3em 0 !important;
}

#data-sources li, .data-sources li {
    margin: 0.2em 0 !important;
    padding-left: 0 !important;
    page-break-inside: avoid !important;
    line-height: 1.4;
    text-indent: 0 !important;
}

/* 确保编号在行首 */
#data-sources li::before, .data-sources li::before {
    content: "" !important;
    display: none !important;
}

.disclaimer {
    page-break-inside: avoid !important;
    page-break-before: avoid !important;
    margin-top: 0.5em !important;
}

.disclaimer + p, .disclaimer + div {
    margin-top: 0.3em !important;
    page-break-before: avoid !important;
}

/* 移除 markdown 脚注的分页 */
.footnotes, .footnotes ol, .footnotes li {
    margin: 0 !important;
    padding: 0 !important;
    page-break-inside: avoid !important;
    page-break-after: avoid !important;
}

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 2em 0;
}

.header-meta {
    text-align: center;
    font-size: 9.5pt;
    color: #666;
    margin: 1em 0 2em 0;
    line-height: 1.8;
}

.warning-box {
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 4px;
    padding: 1em;
    margin: 1em 0;
    font-size: 9.5pt;
}

.disclaimer {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    padding: 1em;
    margin: 2em 0;
    font-size: 9pt;
    line-height: 1.5;
    color: #555;
}
"""


def check_chinese_fonts():
    """检查系统中可用的中文字体"""
    common_chinese_fonts = [
        "Noto Serif CJK SC",
        "Source Han Serif SC",
        "SimSun",
        "STSong",
        "KaiTi",
        "FangSong",
        "Microsoft YaHei",
        "PingFang SC",
        "Hiragino Sans GB",
    ]
    
    try:
        from weasyprint.text.fonts import get_font_names
        available_fonts = get_font_names()
    except ImportError:
        # Fallback: try to list fonts using fc-list
        import subprocess
        try:
            result = subprocess.run(['fc-list', ':family'], capture_output=True, text=True)
            available_fonts = set(result.stdout.split('\n'))
        except Exception:
            available_fonts = set()
    
    found_fonts = []
    for font in common_chinese_fonts:
        if any(font.lower() in af.lower() for af in available_fonts):
            found_fonts.append(font)
    
    return found_fonts


def generate_pdf(input_path: str, output_path: str = None):
    """
    将 Markdown 文件转换为 PDF
    
    Args:
        input_path: 输入的 Markdown 文件路径
        output_path: 输出的 PDF 文件路径（可选，默认为同名的.pdf）
    
    Returns:
        输出 PDF 文件路径
    """
    input_file = Path(input_path)
    
    if not input_file.exists():
        print(f"[ERROR] 输入文件不存在：{input_file}")
        sys.exit(1)
    
    # 确定输出路径
    if output_path:
        output_file = Path(output_path)
    else:
        output_file = input_file.with_suffix('.pdf')
    
    # 确保输出目录存在
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"[INFO] 读取 Markdown 文件：{input_file}")
    
    # 读取 Markdown 内容
    markdown_content = input_file.read_text(encoding='utf-8')
    
    # 转换为 HTML
    html_content = markdown2.markdown(
        markdown_content,
        extras=[
            'tables',
            'footnotes',
            'code-friendly',
            'fenced-code-blocks',
            'header-ids',
            'toc',
        ]
    )
    
    # 添加完整的 HTML 结构
    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票对比分析报告</title>
</head>
<body>
{html_content}
</body>
</html>"""
    
    # 检查中文字体
    print("[INFO] 检查中文字体支持...")
    available_fonts = check_chinese_fonts()
    if available_fonts:
        print(f"[OK] 找到中文字体：{', '.join(available_fonts)}")
    else:
        print("[WARNING] 未找到常见中文字体，PDF 可能出现乱码")
        print("[INFO] 建议安装：Noto Serif CJK SC 或思源宋体")
    
    print(f"[INFO] 生成 PDF: {output_file}")
    
    # 生成 PDF
    html = HTML(string=full_html)
    css = CSS(string=PDF_CSS)
    
    html.write_pdf(
        str(output_file),
        stylesheets=[css],
    )
    
    print(f"[OK] PDF 生成成功：{output_file}")
    print(f"[INFO] 文件大小：{output_file.stat().st_size / 1024:.1f} KB")
    
    return str(output_file)


def main():
    if len(sys.argv) < 2:
        print("用法：python generate_pdf.py <input.md> [output.pdf]")
        print("\n示例:")
        print("  python generate_pdf.py report.md")
        print("  python generate_pdf.py report.md ~/Desktop/report.pdf")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        generate_pdf(input_path, output_path)
    except Exception as e:
        print(f"[ERROR] PDF 生成失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
