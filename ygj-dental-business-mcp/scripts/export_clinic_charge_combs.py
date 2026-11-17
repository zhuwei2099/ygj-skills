#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""子能力 export-clinic-charge-combs · 导出某门店的「收费组合」及其明细清单。

数据源：`basedatas_list_charge_combs`（基础字典域 · 收费组合，**嵌套返回** items 明细）
口径与坑见 ../references/export-clinic-charge-combs.md，字段契约见 ../references/price-list-and-combos.md

固定流程（六步）
  1. 门店定位（闸门）—— `employees_list_work_clinic` 白名单，clinicId 必须来自本次调用
  2. 取组合           —— `basedatas_list_charge_combs`，status=0 全量翻页（size 上限 100）
  3. 展平             —— 组合 × items[] → 10 列平铺行，保持组合内连续 + 组合序号
  4. 勾稽             —— C1–C13 三态（ok / warn=源数据缺口 / fail=口径不一致）
  5. 输出             —— xlsx（组合明细 / 组合清单 / 说明）+ csv（10 列平铺）+ _raw.json
  6. 报缺口           —— 空编码、重名、无主项目、空单位/分类等如实列示，不编造填补

输出 10 列（用户口径，顺序固定）
  组合名称 · 总价格 · 项目名称 · 主项目 · 单位 · 技耗分类 · 单价 · 数量 · 金额 · 计价说明

用法
  python export_clinic_charge_combs.py --store 宣武门店
  python export_clinic_charge_combs.py --clinic-id 8888000000000067
  python export_clinic_charge_combs.py --store 宣武门店 --include-disabled --out-dir D:/tmp

依赖：同目录或工作区的 `ygj_client.py`（读取 ~/.workbuddy/ygj-mcp-prod-credentials.json）。
      解析顺序见 `_resolve_client()`；找不到时设环境变量 `YGJ_CLIENT_DIR` 指向它所在目录。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime

COMB_TOOL = "basedatas_list_charge_combs"
WHITELIST_TOOL = "employees_list_work_clinic"
PAGE_SIZE = 100                      # 该工具 size 上限 100

COLS = ["组合名称", "总价格", "项目名称", "主项目", "单位",
        "技耗分类", "单价", "数量", "金额", "计价说明"]

CLIENT_CANDIDATES = (
    os.environ.get("YGJ_CLIENT_DIR"),           # 1) 显式指定
    os.path.dirname(os.path.abspath(__file__)),  # 2) 技能自带（scripts/ 内 vendor）
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                 "workspace-ai", "scripts"),     # 3) 同机工作区（按技能落点反推）
    r"E:\zhuwei\AI\workspace-ai\scripts",        # 4) 工作区默认位
    os.path.join(os.getcwd(), "scripts"),        # 5) 当前目录
    os.getcwd(),
)


def _resolve_client():
    """定位 ygj_client.py。返回 (Ygj 类, 客户端所在目录)。"""
    for c in CLIENT_CANDIDATES:
        if not c:
            continue
        c = os.path.abspath(c)
        if os.path.isfile(os.path.join(c, "ygj_client.py")):
            if c not in sys.path:
                sys.path.insert(0, c)
            try:
                from ygj_client import Ygj  # noqa: WPS433
            except Exception as e:                      # 导入期报错要显性化
                raise SystemExit("找到 %s/ygj_client.py 但导入失败：%s" % (c, e))
            return Ygj, c
    raise SystemExit(
        "未找到 ygj_client.py。请把环境变量 YGJ_CLIENT_DIR 指向它所在目录"
        "（凭证文件 ~/.workbuddy/ygj-mcp-prod-credentials.json 需同时就位）。")


def f2(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def money(v):
    x = f2(v)
    return None if x is None else float(x)


# ---------------------------------------------------------------- 1 门店定位（闸门）
def resolve_clinic(y, store, clinic_id):
    """白名单内定位门店。歧义 / 越权一律列候选并退出，不替用户选。"""
    d = y.call(WHITELIST_TOOL, {})
    rows = d if isinstance(d, list) else (d.get("records") or d.get("data") or [])
    if not rows:
        raise SystemExit("工作门店白名单为空 → fail-closed，拒绝取数")
    index = {}
    for r in rows:
        cid = str(r.get("clinicId") or "").strip()
        if cid:
            index[cid] = r

    if clinic_id:
        cid = str(clinic_id).strip()
        if cid not in index:
            raise SystemExit("clinicId %s 不在本次白名单内 → 拒绝取数" % cid)
        return index[cid], len(rows)

    if not store:
        raise SystemExit("必须给 --store 或 --clinic-id")

    kw = store.strip()
    exact, fuzzy = [], []
    for r in rows:
        names = [str(r.get(k) or "") for k in ("abbreviation", "clinicName", "oaOrgName")]
        if any(n == kw for n in names):
            exact.append(r)
        elif any(kw in n for n in names):
            fuzzy.append(r)
    hits = exact or fuzzy
    if not hits:
        raise SystemExit("白名单内无门店名匹配「%s」" % kw)
    if len(hits) > 1:
        print("⚠️ 门店名「%s」命中 %d 家，请用 --clinic-id 指定：" % (kw, len(hits)))
        for r in hits:
            print("   %-22s %-30s %s" % (r.get("clinicId"), r.get("abbreviation"),
                                         r.get("clinicStatus")))
        raise SystemExit(2)
    return hits[0], len(rows)


# ---------------------------------------------------------------- 2 取组合
def fetch_combs(y, clinic_id, status):
    recs, cur, total, pages = [], 1, None, None
    while True:
        d = y.call(COMB_TOOL, {"clinicId": clinic_id, "status": status,
                               "current": cur, "size": PAGE_SIZE})
        recs.extend(d.get("records") or [])
        total, pages = d.get("total"), d.get("pages")
        if not (d.get("records") or []) or cur >= (pages or 1):
            break
        cur += 1
    return recs, total, pages


# ---------------------------------------------------------------- 3 展平
def flatten(combs):
    """组合 → 10 列平铺行 + 组合级元信息。组合内顺序按 items[].sort。"""
    name_cnt = Counter((c.get("name") or "").strip() for c in combs)
    rows, comb_meta = [], []
    for ci, c in enumerate(combs):
        cname = (c.get("name") or "").strip()
        cprice = c.get("price")
        items = c.get("items") or []
        items = sorted(items, key=lambda x: (x.get("sort")
                                             if isinstance(x.get("sort"), int) else 9999))
        s_amt, main_names, pricing_notes = 0.0, [], []
        for it in items:
            im = it.get("isMainItem")
            if im in (1, "1", True):
                main_names.append(it.get("itemName") or "")
            note = (it.get("pricingInfo") or "").strip()
            if note:
                pricing_notes.append(note)
            amt = f2(it.get("amount"))
            if amt is not None:
                s_amt += amt
            rows.append({
                "组合序号": ci + 1,
                "组合id": c.get("id"),
                "组合编码": c.get("code"),
                "组合名称": cname,
                "总价格": money(cprice),
                "项目名称": (it.get("itemName") or "").strip(),
                "主项目": "是" if im in (1, "1", True) else ("否" if im in (0, "0", False) else ""),
                "单位": it.get("unit") or "",
                "技耗分类": it.get("chargeType") or "",
                "单价": money(it.get("price")),
                "数量": f2(it.get("count")),
                "金额": amt,
                "计价说明": note,
                # 以下为审计附属列，不进 10 列主表
                "_步骤": it.get("combStepName") or "",
                "_项目编码": it.get("itemCode") or "",
                "_市场价": money(it.get("marketPrice")),
                "_状态": c.get("statusLabel") or "",
            })
        comb_meta.append({
            "组合序号": ci + 1, "组合id": c.get("id"), "组合编码": c.get("code"),
            "组合名称": cname, "总价格": money(cprice), "明细行数": len(items),
            "Σ金额": round(s_amt, 2),
            "差额": None if cprice in (None, "") else round(float(cprice) - s_amt, 2),
            "主项目": "、".join([m for m in main_names if m]) or ("(无主项目标记)" if items else ""),
            "主项目数量": len([m for m in main_names if m]),
            "计价说明": " ｜ ".join(sorted(set(pricing_notes))),
            "计价说明行数": len(pricing_notes),
            "同名组合数": name_cnt[cname],
            "重名": "重名 ×%d" % name_cnt[cname] if name_cnt[cname] > 1 else "",
            "状态": c.get("statusLabel") or "",
            "备注": c.get("remark") or "",
        })
    return rows, comb_meta


# ---------------------------------------------------------------- 4 勾稽（三态）
def audit(combs, rows, comb_meta):
    """三态：ok=通过 / warn=源数据缺口（非导出错误）/ fail=口径不一致。"""
    out = []
    no_item = [m for m in comb_meta if m["明细行数"] == 0]
    diff = [m for m in comb_meta if m["差额"] not in (None, 0.0)]
    multi_main = [m for m in comb_meta if m["主项目数量"] > 1]
    no_main = [m for m in comb_meta if m["明细行数"] > 0 and m["主项目数量"] == 0]
    dup_name = {m["组合名称"]: m["同名组合数"] for m in comb_meta if m["同名组合数"] > 1}
    empty_code = [m for m in comb_meta if not (m["组合编码"] or "").strip()]
    miss_unit = [r for r in rows if not r["单位"]]
    miss_type = [r for r in rows if not r["技耗分类"]]
    miss_name = [r for r in rows if not r["项目名称"]]
    bad_line = [r for r in rows if None not in (r["单价"], r["数量"], r["金额"])
                and abs(r["单价"] * r["数量"] - r["金额"]) > 0.01]
    n_cmp = len([m for m in comb_meta if m["差额"] is not None])

    def chk(code, desc, level, detail=""):
        out.append({"code": code, "desc": desc, "level": level, "detail": detail})

    chk("C1", "组合数 = 组合清单行数", "ok" if len(comb_meta) == len(combs) else "fail",
        "%d = %d" % (len(comb_meta), len(combs)))
    chk("C2", "明细行数 = Σ各组合明细行数",
        "ok" if len(rows) == sum(m["明细行数"] for m in comb_meta) else "fail",
        "%d = %d" % (len(rows), sum(m["明细行数"] for m in comb_meta)))
    chk("C3", "每个组合都有明细（无空组合）", "ok" if not no_item else "warn",
        ("空组合 %d 个：%s" % (len(no_item), "、".join(m["组合名称"] for m in no_item[:8])))
        if no_item else "0 个")
    chk("C4", "总价格 = Σ明细金额（逐组合）", "ok" if not diff else "fail",
        "不一致 %d 个%s" % (len(diff), ("，例：" + "；".join(
            "%s 差 %s" % (m["组合名称"], m["差额"]) for m in diff[:5]))) if diff
        else ("%d/%d 全等" % (n_cmp, n_cmp) if n_cmp else "无可比组合"))
    chk("C5", "主项目标记不重复（每组合 ≤1 个）", "ok" if not multi_main else "fail",
        "多主项目 %d 个" % len(multi_main))
    chk("C6", "行金额 = 单价 × 数量（逐行）", "ok" if not bad_line else "fail",
        "不一致 %d 行" % len(bad_line))
    chk("C7", "项目名称无空值", "ok" if not miss_name else "warn",
        "空值 %d 行" % len(miss_name))
    chk("C8", "单位无空值", "ok" if not miss_unit else "warn",
        "空值 %d 行：%s" % (len(miss_unit), "；".join(
            "%s / %s" % (r["组合名称"], r["项目名称"]) for r in miss_unit[:8])))
    chk("C9", "技耗分类无空值", "ok" if not miss_type else "warn",
        "空值 %d 行：%s" % (len(miss_type), "；".join(
            "%s / %s" % (r["组合名称"], r["项目名称"]) for r in miss_type[:8])))
    chk("C10", "组合名称可唯一定位（无重名）", "ok" if not dup_name else "warn",
        "重名 %d 组（共 %d 个组合）：%s" % (
            len(dup_name), sum(dup_name.values()),
            "、".join("%s ×%d" % (k, v) for k, v in list(dup_name.items())[:6]))
        if dup_name else "0 组")
    chk("C11", "组合编码非空", "ok" if not empty_code else "warn",
        "空编码 %d / %d 个 → 唯一键只能用组合ID" % (len(empty_code), len(comb_meta)))
    chk("C12", "无主项目标记的组合", "ok" if not no_main else "warn",
        "%d / %d 个（源系统未勾选主项目，非导出错误）" % (len(no_main), len(comb_meta)))
    ent = [r for r in rows if any(e in r["计价说明"]
                                  for e in ("&quot;", "&amp;", "&lt;", "&gt;"))]
    chk("C13", "计价说明文本无 HTML 实体残留", "ok" if not ent else "warn",
        "含实体残留 %d 行（源文本自带，原样保留）：%s"
        % (len(ent), "；".join("%s / %s" % (r["组合名称"], r["项目名称"]) for r in ent[:4]))
        if ent else "0 行")
    return out


# ---------------------------------------------------------------- 5 输出
def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_xlsx(path, rows, comb_meta, recon, head):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    thin = Side(style="thin", color="D9D9D9")
    bd = Border(left=thin, right=thin, top=thin, bottom=thin)
    hdr_fill = PatternFill("solid", fgColor="F2F2F2")
    band = PatternFill("solid", fgColor="FAFAFA")
    hdr_font = Font(bold=True, size=10)
    body_font = Font(size=10)
    num_fmt = "#,##0.00"

    # --- Sheet1 组合明细（严格按用户指定的 10 列）
    ws = wb.active
    ws.title = "组合明细"
    ws.append(COLS)
    for i in range(1, len(COLS) + 1):
        cell = ws.cell(row=1, column=i)
        cell.font, cell.fill, cell.border = hdr_font, hdr_fill, bd
        cell.alignment = Alignment(horizontal="center", vertical="center")
    prev_seq, band_on = None, False
    for r in rows:
        if prev_seq is not None and r["组合序号"] != prev_seq:
            band_on = not band_on
        prev_seq = r["组合序号"]
        ws.append([r[c] for c in COLS])
        ri = ws.max_row
        for ci in range(1, len(COLS) + 1):
            cell = ws.cell(row=ri, column=ci)
            cell.font, cell.border = body_font, bd
            cell.alignment = Alignment(vertical="center",
                                       horizontal="right" if COLS[ci - 1] in
                                       ("总价格", "单价", "数量", "金额") else "left")
            if COLS[ci - 1] in ("总价格", "单价", "金额"):
                cell.number_format = num_fmt
            elif COLS[ci - 1] == "数量":
                cell.number_format = "0.##"
            if band_on:
                cell.fill = band
    for i, w in enumerate([26, 11, 30, 8, 8, 12, 11, 8, 12, 24], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(COLS)), ws.max_row)

    # --- Sheet2 组合清单（组合级 · 唯一键 · 重名提示）
    ws2 = wb.create_sheet("组合清单")
    h2 = ["序号", "组合名称", "组合ID", "明细行数", "总价格", "Σ明细金额", "差额",
          "主项目", "重名提示", "计价说明行数", "状态"]
    ws2.append(h2)
    for i in range(1, len(h2) + 1):
        c = ws2.cell(row=1, column=i)
        c.font, c.fill, c.border = hdr_font, hdr_fill, bd
        c.alignment = Alignment(horizontal="center", vertical="center")
    for m in comb_meta:
        ws2.append([m["组合序号"], m["组合名称"], m["组合id"], m["明细行数"], m["总价格"],
                    m["Σ金额"], m["差额"], m["主项目"], m["重名"], m["计价说明行数"],
                    m["状态"]])
        ri = ws2.max_row
        for ci in range(1, len(h2) + 1):
            c = ws2.cell(row=ri, column=ci)
            c.font, c.border = body_font, bd
            c.alignment = Alignment(vertical="center",
                                    horizontal="right" if h2[ci - 1] in
                                    ("总价格", "Σ明细金额", "差额", "明细行数",
                                     "计价说明行数") else "left")
            if h2[ci - 1] in ("总价格", "Σ明细金额", "差额"):
                c.number_format = num_fmt
    for i, w in enumerate([6, 26, 22, 10, 11, 12, 10, 20, 11, 13, 8], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w
    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(h2)), ws2.max_row)

    # --- Sheet3 说明
    ws3 = wb.create_sheet("说明")
    info = [
        ("数据源工具", COMB_TOOL + "（基础字典域 · 收费组合，嵌套返回 items 明细）"),
        ("门店", "%s（clinicId %s）" % (head["store"], head["clinicId"])),
        ("门店归属", "%s / %s / 状态 %s" % (head.get("org") or "", head.get("div") or "",
                                          head.get("status") or "")),
        ("组合范围", head["scope_desc"]),
        ("明细行数", "%d 行" % head["n_row"]),
        ("生成时刻", head["at"]),
        ("", ""),
        ("列名 → 服务端字段", ""),
        ("组合名称", "comb.name（组合名称）"),
        ("总价格", "comb.price（组合挂牌总价，非成交价）"),
        ("项目名称", "items[].itemName"),
        ("主项目", "items[].isMainItem：1=是（该组合的主项目）/ 0=否"),
        ("单位", "items[].unit"),
        ("技耗分类", "items[].chargeType（服务端 schema 中文名即「技耗分类」，"
                     "取值如 治疗费/检查费/专用耗材费）"),
        ("单价", "items[].price（字符串）"),
        ("数量", "items[].count（int）"),
        ("金额", "items[].amount（= 单价 × 数量）"),
        ("计价说明", "items[].pricingInfo"),
        ("", ""),
        ("关联方式", "同一组合的多条明细连续排列、组合名称与总价格逐行重复，并交替底色分区；"
                     "行顺序 = items[].sort；如需机器处理可用随附 CSV（同顺序、平铺 10 列）"),
        ("唯一键提示", "若「组合编码」为空或存在同名组合 → 唯一定位请用《组合清单》的「组合ID」列"
                     "（本店空编码 %d 个、重名 %d 组涉及 %d 个组合）"
                     % (head.get("n_empty_code", 0), head.get("n_dup_group", 0),
                        head.get("n_dup_comb", 0))),
        ("字段分布", "技耗分类：%s ｜ 计价说明非空行 %d / %d"
                     % (head.get("type_dist", ""), head.get("n_note", 0), head["n_row"])),
        ("", ""),
        ("校验", "（ok=通过；warn=源数据缺口，非导出错误；fail=口径不一致）"),
    ]
    for c in recon:
        mark = {"ok": "✅ 通过", "warn": "⚠️ 提示", "fail": "❌ 不通过"}[c["level"]]
        info.append((c["code"] + " " + c["desc"],
                     mark + ("　" + c["detail"] if c["detail"] else "")))
    for k, v in info:
        ws3.append([k, v])
        c1 = ws3.cell(row=ws3.max_row, column=1)
        c2 = ws3.cell(row=ws3.max_row, column=2)
        c1.font = Font(bold=True, size=10)
        c2.font = body_font
        c2.alignment = Alignment(wrap_text=True, vertical="top")
    ws3.column_dimensions["A"].width = 24
    ws3.column_dimensions["B"].width = 96
    wb.save(path)


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description="导出某门店的收费组合及明细清单")
    ap.add_argument("--store", default=None,
                    help="门店名（简称 / 诊所名 / 组织名，可模糊）；命中多家时列出候选并退出")
    ap.add_argument("--clinic-id", default=None, help="直接指定 clinicId（须在白名单内）")
    ap.add_argument("--include-disabled", action="store_true",
                    help="并入禁用组合（status=1），输出改为「全部收费组合」。默认只取启用")
    ap.add_argument("--out-dir", default=None,
                    help="输出目录，默认为客户端所在工作区的 outputs/")
    ap.add_argument("--tag", default=None, help="文件名日期标记，默认今天 YYYYMMDD")
    a = ap.parse_args()

    Ygj, client_dir = _resolve_client()
    ws_root = os.path.dirname(client_dir)                 # …/scripts → 工作区根
    out_dir = os.path.abspath(a.out_dir or os.environ.get("YGJ_OUT_DIR")
                              or os.path.join(ws_root, "outputs"))
    os.makedirs(out_dir, exist_ok=True)
    tag = a.tag or datetime.now().strftime("%Y%m%d")

    y = Ygj()
    r, n_wl = resolve_clinic(y, a.store, a.clinic_id)
    cid = str(r.get("clinicId"))
    store = r.get("abbreviation") or r.get("clinicName")
    print("门店：%s（%s）｜白名单 %d 家｜归属 %s / %s｜%s"
          % (store, cid, n_wl, r.get("divisionalName"),
             r.get("divisionalGeneralManager"), r.get("clinicStatus")))

    combs, total, pages = fetch_combs(y, cid, 0)
    print("已启用组合：total=%s pages=%s 实取=%d" % (total, pages, len(combs)))
    disabled = []
    if a.include_disabled:
        disabled, dis_total, _ = fetch_combs(y, cid, 1)
        print("禁用组合（并入）：total=%s" % dis_total)
    else:
        try:                                              # 对照数字，失败不影响主交付
            _, dis_total, _ = fetch_combs(y, cid, 1)
            print("禁用组合（对照，未并入）：total=%s" % dis_total)
        except Exception as e:
            dis_total = None
            print("禁用组合对照取数失败（不影响主口径）：%s" % str(e)[:120])

    all_combs = combs + disabled
    scope_desc = ("status=0 已启用（%d 个）" % len(combs) if not disabled
                  else "全部（已启用 %d + 禁用 %d = %d 个）"
                       % (len(combs), len(disabled), len(all_combs)))

    rows, comb_meta = flatten(all_combs)
    recon = audit(all_combs, rows, comb_meta)
    type_dist = Counter((r["技耗分类"] or "(空)") for r in rows)
    dup_map = {m["组合名称"]: m["同名组合数"] for m in comb_meta if m["同名组合数"] > 1}
    head = {"store": store, "clinicId": cid, "org": r.get("oaOrgName"),
            "div": "%s（%s）" % (r.get("divisionalName"), r.get("divisionalGeneralManager")),
            "status": r.get("clinicStatus"), "scope_desc": scope_desc,
            "n_comb": len(all_combs), "n_row": len(rows),
            "n_note": sum(1 for x in rows if x["计价说明"]),
            "n_empty_code": sum(1 for m in comb_meta if not (m["组合编码"] or "").strip()),
            "n_dup_group": len(dup_map), "n_dup_comb": sum(dup_map.values()),
            "type_dist": "、".join("%s %d 行" % (k, v) for k, v in type_dist.most_common()),
            "enabled_total": len(combs), "disabled_total": dis_total,
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    scope_tag = "已启用收费组合" if not disabled else "全部收费组合"
    stem = "%s_%s及明细_%s" % (store, scope_tag, tag)
    p_xlsx = os.path.join(out_dir, stem + ".xlsx")
    p_csv = os.path.join(out_dir, stem + ".csv")
    p_json = os.path.join(out_dir, stem + "_raw.json")

    write_csv(p_csv, rows)
    write_xlsx(p_xlsx, rows, comb_meta, recon, head)
    with open(p_json, "w", encoding="utf-8") as fh:
        json.dump({"head": head, "recon": recon, "comb_meta": comb_meta, "rows": rows,
                   "enabled_total": len(combs), "disabled_total": dis_total,
                   "raw_combs": all_combs}, fh, ensure_ascii=False, indent=1)

    print("\n勾稽：")
    for c in recon:
        print("  %s %s → %s %s" % (c["code"], c["desc"],
                                   {"ok": "OK", "warn": "WARN", "fail": "FAIL"}[c["level"]],
                                   c["detail"]))
    print("\n产物：")
    for p in (p_xlsx, p_csv, p_json):
        print("  %s  (%d bytes)" % (p, os.path.getsize(p)))


if __name__ == "__main__":
    main()
