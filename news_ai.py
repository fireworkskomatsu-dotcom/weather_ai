import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")
OUT_FILE = BASE / "news.json"

QUERIES = [
    "日経平均 OR TOPIX OR 日本株",
    "半導体 OR SOXX OR NVIDIA OR NVDA",
    "日銀 OR BOJ OR CPI OR FOMC OR 雇用統計",
]

RISK_HIGH = [
    "急落", "ショック", "暴落", "戦争", "緊急", "デフォルト", "利上げ",
    "関税", "報復", "地政学", "下方修正", "破綻", "大幅安", "急変"
]

RISK_MID = [
    "警戒", "減速", "弱含み", "不透明", "下落", "売り", "慎重",
    "変動", "混乱", "リスク", "インフレ", "高止まり"
]

POSITIVE = [
    "反発", "上方修正", "緩和", "改善", "上昇", "買い", "追い風", "期待"
]

def fetch_rss(query):
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return res.read()

def score_headline(title):
    score = 0
    for k in RISK_HIGH:
        if k in title:
            score -= 2
    for k in RISK_MID:
        if k in title:
            score -= 1
    for k in POSITIVE:
        if k in title:
            score += 1
    return score

def main():
    headlines = []
    total_score = 0
    errors = []

    for q in QUERIES:
        try:
            raw = fetch_rss(q)
            root = ET.fromstring(raw)
            channel = root.find("channel")
            if channel is None:
                continue
            for item in channel.findall("item")[:5]:
                title_el = item.find("title")
                link_el = item.find("link")
                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                link = link_el.text.strip() if link_el is not None and link_el.text else ""
                if not title:
                    continue
                s = score_headline(title)
                total_score += s
                headlines.append({
                    "title": title,
                    "score": s,
                    "link": link
                })
        except Exception as e:
            errors.append(str(e))

    # 重複見出しをざっくり除去
    seen = set()
    uniq = []
    for h in headlines:
        if h["title"] in seen:
            continue
        seen.add(h["title"])
        uniq.append(h)

    uniq = uniq[:8]

    level = "LOW"
    reason = "通常ニュースフロー"

    if total_score <= -6:
        level = "HIGH"
        reason = "ネガティブニュース多発"
    elif total_score <= -3:
        level = "MID"
        reason = "やや警戒ニュースあり"
    elif total_score >= 3:
        level = "LOW"
        reason = "ポジティブ寄り"

    out = {
        "news_level": level,
        "news_reason": reason,
        "news_score": total_score,
        "headlines": uniq,
        "errors": errors[:3]
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
