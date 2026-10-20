#!/usr/bin/env python3
"""沖縄中心の求人ニュースを集めて docs/index.html を作る。APIキー不要・無料。"""
import json, re, sys, hashlib, pathlib, urllib.parse, datetime as dt
import feedparser

ROOT = pathlib.Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text("utf-8"))
DATA = ROOT / "data" / "articles.json"
JST = dt.timezone(dt.timedelta(hours=9))
KEEP_DAYS = 120      # 保存する日数
MAX_AGE = 10         # 取り込むのは「公開から10日以内」の記事だけ

# 沖縄の媒体（見出しに「県内」とあり、出典がこれらなら沖縄扱い）
OKI_SOURCES = ["沖縄", "琉球", "OTV", "QAB", "RBC", "八重山", "宮古毎日"]
TRUST = ["NHK", "沖縄タイムス", "琉球新報", "琉球放送", "OTV", "QAB", "RBC", "日本経済新聞", "労働局"]
PRSRC = ["PR TIMES", "valuepress", "@Press", "ドリームニュース", "Dellows"]
# 「採用」は商品の採用などと紛らわしいので、求人・雇用の文脈がある見出しだけ対象にする
JOBCTX = ["人材", "求人", "雇用", "従業員", "社員", "新卒", "中途", "人事", "応募", "就職", "転職", "就活",
          "人手", "募集", "スカウト", "賃金", "時給", "労働", "職場", "インターン", "採用担当", "採用活動",
          "採用強化", "採用難", "採用市場", "採用計画", "採用サイト"]
NOISE = ["写真集", "グラビア", "アイドル", "製品", "システム", "ボールペン", "新発売", "販売開始", "発売"]

# 沖縄の話題を厚くするための追加検索（config.json を触らなくてよいようここに持つ）
EXTRA_QUERIES = ["沖縄 賃上げ 企業", "沖縄 人手不足 企業", "沖縄 新規雇用 開設", "沖縄 コールセンター 開設",
                 "沖縄 観光 人材不足", "沖縄 就職 転職 説明会", "沖縄 外国人材 雇用", "沖縄 物価高 賃金",
                 "沖縄 新卒 採用 内定", "沖縄 企業 進出 雇用"]


def gnews(q):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:7d")
            + "&hl=ja&gl=JP&ceid=JP:ja")


def is_okinawa(title, source):
    if "沖縄" in title or any(p in title for p in CFG["places"]):
        return True
    return "県内" in title and any(s in source for s in OKI_SOURCES)


def classify(title):
    cats = []
    for c, ws in CFG["categories"].items():
        for w in ws:
            if w not in title:
                continue
            if w == "採用" and not any(k in title for k in JOBCTX):
                continue
            cats.append(c)
            break
    return cats


def stale(title, year):
    """見出しに過去の年（例: 2024年）しか出てこない記事は古い記事として除外。"""
    ys = [int(y) for y in re.findall(r"(20\d\d)年", title)]
    return bool(ys) and max(ys) < year


def score(a):
    t, s = a["title"], len(a["cats"])
    s += 6 if "沖縄" in t else 4 if a["oki"] else 0
    if any(k in a["source"] for k in TRUST):
        s += 2
    if any(k in a["source"] for k in PRSRC):
        s -= 1
    return s


def finish(a, year):
    """記事を（再）判定。使えない記事は None を返す。"""
    if any(n in a["title"] for n in NOISE) or stale(a["title"], year):
        return None
    cats = classify(a["title"])
    if not cats:
        return None
    a["cats"] = cats
    a["oki"] = is_okinawa(a["title"], a["source"])
    a["score"] = score(a)
    a["talk"] = CFG["talk"].get(cats[0], "")
    return a


def ingest(feed):
    """見出し・リンク・出典・公開日のみ保存（本文は保存しない）。公開日が不明な記事は捨てる。"""
    now = dt.datetime.now(JST)
    out = []
    for e in feed.entries:
        t = e.get("published_parsed")
        if not t:
            continue  # 日付不明は「新しい記事」扱いにしない
        d = dt.datetime(*t[:6], tzinfo=dt.timezone.utc).astimezone(JST)
        if d > now + dt.timedelta(days=1) or (now - d).days > MAX_AGE:
            continue
        if not e.get("link") or not e.get("title"):
            continue  # リンクや見出しのない記事は捨てる
        raw = e.get("title", "").strip()
        title = raw.rsplit(" - ", 1)[0] if " - " in raw else raw
        src = (e.get("source") or {}).get("title") or (raw.rsplit(" - ", 1)[1] if " - " in raw else "")
        a = finish({
            "id": hashlib.md5(re.sub(r"\W", "", title).encode()).hexdigest()[:12],
            "title": title, "url": e.get("link", ""), "source": src,
            "date": d.strftime("%Y-%m-%d"), "cats": [], "oki": False, "score": 0, "talk": ""}, now.year)
        if a:
            out.append(a)
    return out


def merge_and_build(new):
    today = dt.datetime.now(JST).date()
    old = json.loads(DATA.read_text("utf-8")) if DATA.exists() else []
    byid = {}
    for a in old + new:  # 保存済みの記事も新ルールで判定し直す
        a = finish(dict(a), today.year)
        if a and (a["id"] not in byid or a["score"] > byid[a["id"]]["score"]):
            byid[a["id"]] = a
    cutoff = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    limit = (today + dt.timedelta(days=1)).isoformat()
    arts = sorted((a for a in byid.values() if cutoff <= a["date"] <= limit),
                  key=lambda a: (a["date"], a["score"]), reverse=True)
    DATA.write_text(json.dumps(arts, ensure_ascii=False, indent=1), "utf-8")
    page = (ROOT / "template.html").read_text("utf-8")
    blob = json.dumps(arts, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    (ROOT / "docs" / "index.html").write_text(
        page.replace("__DATA__", blob).replace("__TODAY__", today.isoformat()), "utf-8")
    print(f"新規 {len(new)} 件 / 累計 {len(arts)} 件")


def main():
    urls = [gnews(q["q"]) for q in CFG["queries"]] + [gnews(q) for q in EXTRA_QUERIES] + list(CFG["rss"])
    new, fetched = [], 0
    for url in urls:
        try:
            feed = feedparser.parse(url)
            fetched += len(feed.entries)
            new += ingest(feed)
        except Exception as ex:  # 1つ失敗しても続行
            print("取得失敗:", url, ex)
    if fetched == 0:  # 全部の取得に失敗した日は、古いデータを「今日の更新」として出さない
        print("ニュースを1件も取得できませんでした。ページは更新しません。")
        sys.exit(1)
    merge_and_build(new)


if __name__ == "__main__":
    main()
