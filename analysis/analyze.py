#!/usr/bin/env python3
"""2bulu 深圳约伴统计分析：从本地抓取库生成 web/stats-data.json。

维度：月份×类型（每月玩什么）、时间趋势（2025 vs 2026）、目的地排行、
领队排行、新领队趋势、报名热度。结构维度（天数/费用）按 King 要求不做。

用法:
  python3 analysis/analyze.py [--db PATH] [--tagger-dir PATH] [--out PATH]

分类与目的地提取复用抓取管线的 tagger.py（单一规则源，不复制）。
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TAGGER_DIR = os.path.expanduser(
    "~/workspace/goals/2bulu-shenzhen-daily-digest/scraper")
DEFAULT_DB = os.path.join(DEFAULT_TAGGER_DIR, "data", "activities.db")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--tagger-dir", default=DEFAULT_TAGGER_DIR)
    p.add_argument("--out", default=os.path.join(REPO, "web", "stats-data.json"))
    return p.parse_args()


SEASONS = {"春": (3, 4, 5), "夏": (6, 7, 8), "秋": (9, 10, 11), "冬": (12, 1, 2)}


def season_of(month):
    for s, ms in SEASONS.items():
        if month in ms:
            return s
    return ""


def main():
    args = parse_args()
    sys.path.insert(0, args.tagger_dir)
    from tagger import classify, extract_destinations, TAG_ORDER

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    # 排除 2027 年以后的脏数据；只看 2025-01 起
    rows = conn.execute(
        "SELECT id, title, tags, date_start, leader, signup_count "
        "FROM activities WHERE date_start >= '2025-01-01' "
        "AND date_start <= '2026-12-31'").fetchall()
    conn.close()
    print(f"分析 {len(rows)} 条", flush=True)

    monthly = Counter()          # YYYY-MM -> n
    yoy = defaultdict(lambda: [0, 0])   # MM -> [2025, 2026]
    month_cat = defaultdict(Counter)   # MM -> Counter(cat)
    cat_total = Counter()
    cat_signup = defaultdict(list)
    dest = Counter()
    dest_season = defaultdict(Counter)
    leader_n = Counter()
    leader_cat = defaultdict(Counter)
    leader_first = {}
    top_signup = []

    for r in rows:
        ds = r["date_start"] or ""
        ym = ds[:7]
        mm = ds[5:7]
        cats = classify(r["title"], r["tags"])
        if not cats:
            cats = ["其他"]
        monthly[ym] += 1
        if ym.startswith("2025-"):
            yoy[mm][0] += 1
        elif ym.startswith("2026-"):
            yoy[mm][1] += 1
        for c in cats:
            month_cat[mm][c] += 1
            cat_total[c] += 1
            cat_signup[c].append(r["signup_count"] or 0)
        mo = int(mm) if mm.isdigit() else 0
        for d in extract_destinations(r["title"]):
            dest[d] += 1
            if mo:
                dest_season[d][season_of(mo)] += 1
        leader = (r["leader"] or "").strip()
        if leader:
            leader_n[leader] += 1
            for c in cats:
                leader_cat[leader][c] += 1
            if leader not in leader_first or ds < leader_first[leader]:
                leader_first[leader] = ds
        top_signup.append((r["signup_count"] or 0, r["title"], ds, leader, r["id"]))

    # 月度趋势：补齐空月份
    months = []
    d = datetime(2025, 1, 1)
    while d <= datetime(2026, 10, 1):
        k = d.strftime("%Y-%m")
        months.append({"m": k, "n": monthly.get(k, 0)})
        d = (d.replace(day=28) + timedelta(days=5)).replace(day=1)

    new_leaders = Counter()
    for ld, first in leader_first.items():
        new_leaders[first[:7]] += 1
    new_leaders_list = [{"m": m["m"], "n": new_leaders.get(m["m"], 0)} for m in months]

    top_dests = []
    for name, n in dest.most_common(25):
        top_dests.append({"name": name, "n": n,
                          "seasons": dict(dest_season[name])})

    top_leaders = []
    for name, n in leader_n.most_common(20):
        tc = leader_cat[name].most_common(1)
        top_leaders.append({"name": name, "n": n,
                            "top_cat": tc[0][0] if tc else ""})

    top_signup.sort(reverse=True)
    top10 = [{"title": t, "date": ds, "leader": ld, "n": n, "id": i}
             for n, t, ds, ld, i in top_signup[:10]]

    cat_avg = {c: round(sum(v) / len(v), 1) for c, v in cat_signup.items() if v}

    now_cst = (datetime.now(timezone.utc) + timedelta(hours=8)
               ).strftime("%Y-%m-%d %H:%M")
    data = {
        "meta": {"generated_at": now_cst, "analyzed": len(rows),
                 "note": "报名人数为抓取时刻快照，仅供相对比较"},
        "categories": list(TAG_ORDER) + ["其他"],
        "monthly_trend": months,
        "yoy": [{"m": m, "y2025": v[0], "y2026": v[1]}
                for m, v in sorted(yoy.items())],
        "month_category": {m: dict(c) for m, c in sorted(month_cat.items())},
        "category_total": dict(cat_total),
        "category_signup_avg": cat_avg,
        "destinations": top_dests,
        "leaders": top_leaders,
        "new_leaders_monthly": new_leaders_list,
        "top_signup": top10,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"写出 {args.out} ({os.path.getsize(args.out)//1024} KB)", flush=True)


if __name__ == "__main__":
    main()
