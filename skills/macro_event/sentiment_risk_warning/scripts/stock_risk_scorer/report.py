# -*- coding: utf-8 -*-
# Authors: 姜青、Warwick
"""
report.py — 个股模式报告输出（控制台 / HTML / JSON）
"""

import json
import os


def risk_badge(grade):
    return {"高": "🔴 高", "中": "🟠 中", "低": "🟢 低"}.get(grade, grade)


def render_stock_report(result, meta, out_dir="."):
    """result: 模型结果 dict；meta: 标的与舆情信息 dict。

    输出 risk_report_<code>.json 与 risk_report_<code>.html，返回控制台文本。
    """
    code = meta.get("code", "")
    lines = []
    lines.append("=" * 60)
    lines.append("舆情风险预警 · 个股模式")
    lines.append("=" * 60)
    lines.append("标的          : %s（%s）" % (meta.get("name", ""), code))
    lines.append("数据日期      : %s" % meta.get("data_date", ""))
    lines.append("训练窗口      : %d 交易日（%.0f 个月）" % (
        result.get("hist_n", 0), meta.get("months", 60)))
    lines.append("-" * 60)
    lines.append("【下一交易日预测】")
    lines.append("  预测波动率    : %.2f%%" % result["pred_vol"])
    lines.append("  风险等级      : %s" % risk_badge(result["grade"]))
    lines.append("  综合风险分    : %d / 100" % result["score"])
    lines.append("  模型后端      : %s" % result.get("backend", ""))
    if result.get("note"):
        lines.append("  ⚠️  %s" % result["note"])
    lines.append("-" * 60)
    lines.append("【舆情维度】")
    lines.append("  舆情指数      : %+.3f（%s）" % (
        meta.get("opinion", 0.0),
        "看多" if meta.get("opinion", 0) > 0.05 else
        ("看空" if meta.get("opinion", 0) < -0.05 else "中性")))
    ch = meta.get("channels_meta") or []
    if ch:
        ch_desc = " + ".join(
            "%s%d条" % (c.get("name", ""), (c.get("detail") or {}).get("count", 0))
            for c in ch)
        lines.append("  舆情通道      : %s" % ch_desc)
        for c in ch:
            d = c.get("detail") or {}
            lines.append("    · %s：%d 条文本 / %d 个情感词 / %d 个稀疏日" % (
                c.get("name", ""), d.get("count", 0), d.get("scored_terms", 0),
                d.get("sparse_days", 0)))
    lines.append("  舆情样本      : %s" % meta.get("opinion_detail", {}).get("note", ""))
    nts = meta.get("news_titles") or []
    if nts:
        lines.append("  近期新闻标题  :")
        for t in nts[:6]:
            lines.append("    · %s" % (t if len(t) <= 52 else t[:49] + "..."))
    if meta.get("opinion_detail"):
        od = meta["opinion_detail"]
        lines.append("  文本/命中词    : %s" % ", ".join(
            "%s=%s" % (k, v) for k, v in od.items() if k != "note"))
    lines.append("-" * 60)
    lines.append("【特征重要性】")
    imp = result.get("importances", {})
    ranked = sorted(imp.items(), key=lambda kv: (kv[1] if kv[1] is not None else -1), reverse=True)
    for nm, v in ranked:
        if v is None:
            lines.append("  %-16s  —（降级模型无此输出）" % nm)
        else:
            bars = int(round(v * 30))
            lines.append("  %-16s %5.1f%%  %s" % (nm, v * 100, "#" * bars))
    if result.get("removed_vif"):
        lines.append("  （VIF 剔除：%s）" % ", ".join(result["removed_vif"]))
    lines.append("-" * 60)
    lines.append("【数据口径说明】")
    for note in meta.get("notes", []):
        lines.append("  • %s" % note)
    if meta.get("ind_industry"):
        lines.append("  • 所属行业：%s（当日板块涨跌 %.2f%%）" % (
            meta["ind_industry"], meta.get("ind_pct_used", 0)))
    lines.append("-" * 60)
    lines.append("【模型拟合质量（固定模型前向验证）】")
    if result.get("fit_mae") is not None:
        lines.append("  MAE = %.3f%%  相关系数 r = %s" % (
            result["fit_mae"],
            "%.3f" % result["fit_r"] if result.get("fit_r") is not None else "N/A"))
    else:
        lines.append("  样本不足，未做前向验证")
    lines.append("-" * 60)
    lines.append("【解读要点】")
    lines.append("  1. 个股波动率天然高于指数，参考综合风险分与舆情方向。")
    lines.append("  2. 股吧存在水军噪声，长周期舆情需自备历史语料。")
    lines.append("  3. 样本外 R²≈0.52，黑天鹅事件预测能力有限，重大事件人工二次研判。")
    lines.append("  4. 本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。")
    lines.append("=" * 60)
    text = "\n".join(lines)

    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "risk_report_%s.json" % code)
    html_path = os.path.join(out_dir, "risk_report_%s.html" % code)

    payload = {
        "mode": "stock",
        "code": code,
        "name": meta.get("name", ""),
        "data_date": meta.get("data_date", ""),
        "pred_vol": result["pred_vol"],
        "grade": result["grade"],
        "score": result["score"],
        "backend": result.get("backend", ""),
        "opinion_index": meta.get("opinion", 0.0),
        "opinion_detail": meta.get("opinion_detail", {}),
        "channels_meta": meta.get("channels_meta", []),
        "news_titles": meta.get("news_titles", []),
        "importances": result.get("importances", {}),
        "notes": meta.get("notes", []),
        "fit_mae": result.get("fit_mae"),
        "fit_r": result.get("fit_r"),
        "hist_n": result.get("hist_n", 0),
        "months": meta.get("months", 60),
        "ind_industry": meta.get("ind_industry"),
        "ind_pct_used": meta.get("ind_pct_used"),
        "note": result.get("note", ""),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # HTML（自包含，简洁结论卡片）
    html = _render_html(payload)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return text, json_path, html_path


def _render_html(p):
    grade_color = {"高": "#c0392b", "中": "#e67e22", "低": "#27ae60"}.get(p["grade"], "#333")
    imp_rows = "".join(
        '<tr><td>%s</td><td><div class="bar"><div class="fill" style="width:%.0f%%"></div></div></td>'
        '<td>%.1f%%</td></tr>' % (k, v * 100, v * 100)
        for k, v in sorted(p["importances"].items(),
                           key=lambda kv: (kv[1] if kv[1] is not None else -1), reverse=True)
        if v is not None
    )
    notes_html = "".join("<li>%s</li>" % n for n in p.get("notes", []))
    channels_html = ""
    for c in p.get("channels_meta", []):
        d = c.get("detail") or {}
        channels_html += (
            "<div style='font-size:13px;color:#57606a;margin:4px 0'>"
            "<b>%s</b>：%d 条文本 / %d 个情感词 / %d 个稀疏日</div>"
            % (c.get("name", ""), d.get("count", 0), d.get("scored_terms", 0),
               d.get("sparse_days", 0)))
    news_html = ""
    for t in (p.get("news_titles") or [])[:6]:
        news_html += "<li>%s</li>" % t
    news_block = ('<div class="card"><h2>近期新闻标题</h2><ul style="color:#24292f">%s</ul></div>'
                  % news_html) if news_html else ""
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>舆情风险预警 %(code)s</title>
<style>
 body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f6f8fa;margin:0;padding:24px;color:#24292f}
 .card{background:#fff;border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
 h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:0 0 10px;color:#57606a}
 .grid{display:flex;gap:16px;flex-wrap:wrap}
 .metric{flex:1;min-width:140px;background:#f6f8fa;border-radius:8px;padding:14px;text-align:center}
 .metric .v{font-size:26px;font-weight:700} .metric .l{font-size:12px;color:#57606a;margin-top:4px}
 table{width:100%%;border-collapse:collapse;font-size:13px}
 td,th{padding:6px 8px;border-bottom:1px solid #eee;text-align:left}
 .bar{background:#eee;border-radius:4px;height:10px;width:180px}
 .fill{background:#0366d6;height:10px;border-radius:4px}
 .tag{display:inline-block;padding:2px 10px;border-radius:12px;color:#fff;font-size:12px}
 ul{margin:6px 0;padding-left:18px;font-size:13px;color:#57606a}
 .warn{background:#fff8e1;border-left:4px solid #f9a825;padding:10px 14px;border-radius:6px;font-size:13px;margin-top:8px}
</style></head><body>
<div class="card">
  <h1>舆情风险预警 · 个股模式 <span style="font-weight:400;font-size:14px;color:#57606a">%(name)s（%(code)s）</span></h1>
  <div style="font-size:12px;color:#8b949e">数据日期 %(data_date)s · 训练窗口 %(hist_n)s 交易日（%(months)s 个月）· 后端 %(backend)s</div>
  <div class="grid" style="margin-top:16px">
    <div class="metric"><div class="v">%(pred_vol)0.2f%%</div><div class="l">预测波动率</div></div>
    <div class="metric"><div class="v" style="color:%(grade_color)s">%(grade)s</div><div class="l">风险等级</div></div>
    <div class="metric"><div class="v">%(score)d</div><div class="l">综合风险分 / 100</div></div>
    <div class="metric"><div class="v">%(opinion_index)+.3f</div><div class="l">舆情指数</div></div>
  </div>
  %(channels_html)s
</div>
%(news_block)s
<div class="card">
  <h2>特征重要性</h2><table><tr><th>特征</th><th style="width:220px">贡献</th><th>占比</th></tr>%(imp_rows)s</table>
</div>
<div class="card">
  <h2>数据口径说明</h2><ul>%(notes_html)s</ul>
</div>
<div class="card">
  <h2>免责声明</h2>
  <div class="disclaimer">本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。</div>
</div>
</body></html>
""" % {
        "code": p["code"], "name": p.get("name", ""),
        "data_date": p.get("data_date", ""), "hist_n": p.get("hist_n", 0),
        "months": p.get("months", 60), "backend": p.get("backend", ""),
        "pred_vol": p["pred_vol"], "grade": p["grade"], "grade_color": grade_color,
        "score": p["score"], "opinion_index": p.get("opinion_index", 0.0),
        "imp_rows": imp_rows, "notes_html": notes_html,
        "channels_html": channels_html, "news_block": news_block,
    }
