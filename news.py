#!/usr/bin/env python3
"""沖縄中心の求人ニュースを集めて docs/index.html を作る。APIキー不要・無料。"""
import json, re, hashlib, pathlib, urllib.parse, datetime as dt
import feedparser

ROOT = pathlib.Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text("utf-8"))
DATA = ROOT / "data" / "articles.json"
JST = dt.timezone(dt.timedelta(hours=9))
KEEP_DAYS = 400


def gnews(q):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:3d")
            + "&hl=ja&gl=JP&ceid=JP:ja")


def ingest(feed, local):
    """フィードの記事を判定して返す。見出し・リンク・出典のみ保存（本文は保存しない）。"""
    out = []
    for e in feed.entries:
        raw = e.get("title", "").strip()
        title = raw.rsplit(" - ", 1)[0] if " - " in raw else raw
        src = (e.get("source") or {}).get("title") or (raw.rsplit(" - ", 1)[1] if " - " in raw else "")
        cats = [c for c, ws in CFG["categories"].items() if any(w in title for w in ws)]
        if not cats:
            continue
        oki = 3 if "沖縄" in title else 2 if any(p in title for p in CFG["places"]) else 1 if "県内" in title else 0
        if local:
            oki = max(oki, 2)
        t = e.get("published_parsed")
        d = (dt.datetime(*t[:6], tzinfo=dt.timezone.utc).astimezone(JST) if t else dt.datetime.now(JST))
        out.append({
            "id": hashlib.md5(re.sub(r"\W", "", title).encode()).hexdigest()[:12],
            "title": title, "url": e.get("link", ""), "source": src,
            "date": d.strftime("%Y-%m-%d"), "cats": cats,
            "oki": oki >= 2, "score": oki * 2 + len(cats),
            "talk": CFG["talk"].get(cats[0], ""),
        })
    return out


def merge_and_build(new):
    old = json.loads(DATA.read_text("utf-8")) if DATA.exists() else []
    byid = {a["id"]: a for a in old}
    for a in new:
        if a["id"] not in byid or a["score"] > byid[a["id"]]["score"]:
            byid[a["id"]] = {**byid.get(a["id"], {}), **a}
    today = dt.datetime.now(JST).date()
    cutoff = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    arts = sorted((a for a in byid.values() if a["date"] >= cutoff),
                  key=lambda a: (a["date"], a["score"]), reverse=True)
    DATA.write_text(json.dumps(arts, ensure_ascii=False, indent=1), "utf-8")
    page = (ROOT / "template.html").read_text("utf-8")
    blob = json.dumps(arts, ensure_ascii=False).replace("</", "<\\/")
    (ROOT / "docs" / "index.html").write_text(
        page.replace("__DATA__", blob).replace("__TODAY__", today.isoformat()), "utf-8")
    print(f"新規 {len(new)} 件 / 累計 {len(arts)} 件")


def main():
    new = []
    jobs = [(gnews(q["q"]), q["local"]) for q in CFG["queries"]] + [(u, True) for u in CFG["rss"]]
    for url, local in jobs:
        try:
            new += ingest(feedparser.parse(url), local)
        except Exception as ex:  # 1つ失敗しても続行
            print("取得失敗:", url, ex)
    merge_and_build(new)


if __name__ == "__main__":
    main()
