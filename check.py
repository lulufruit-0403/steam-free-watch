"""Steam 限時免費偵測：找出「原價 > 0、折扣 100%」的項目，新出現的推播到 Telegram。

用法：
  python check.py              # 正常執行（沒設 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 時只印出、不推播）
  python check.py --dry-run    # 只印出，不推播、不寫 seen.json
  python check.py --test-notify  # 送一則測試通知到手機
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

SEARCH_URL = "https://store.steampowered.com/search/results/"
DETAILS_URL = "https://store.steampowered.com/api/appdetails"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
SEEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "seen.json")
COMMON = {"cc": "tw", "l": "tchinese", "infinite": "1"}
UA = "steam-free-watch/1.0"
KEEPALIVE_DAYS = 30  # last_run 超過這麼多天才更新，讓 repo 每月至少有一次 commit（避開 60 天停用）


def http_get(url, params):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------- 純函式（測試的對象） ----------

ROW_RE = re.compile(r'<a [^>]*class="search_result_row[^"]*"[^>]*>.*?</a>', re.S)
# 每列的屬性順序不固定，所以分開抓
APPID_RE = re.compile(r'data-ds-appid="([\d,]+)"')
DISCOUNT_RE = re.compile(r'data-discount="(\d+)"')
TITLE_RE = re.compile(r'<span class="title">(.*?)</span>', re.S)


def parse_search_html(results_html):
    """回傳 [{appid, name, discount}]。只取單一 appid 的列（套組有多個 appid，略過）。"""
    rows = []
    for m in ROW_RE.finditer(results_html):
        row = m.group(0)
        a = APPID_RE.search(row)
        if not a or "," in a.group(1):
            continue
        d = DISCOUNT_RE.search(row)
        t = TITLE_RE.search(row)
        rows.append({
            "appid": a.group(1),
            "name": html.unescape(t.group(1).strip()) if t else a.group(1),
            "discount": int(d.group(1)) if d else 0,
        })
    return rows


def is_giveaway(data):
    """appdetails 的 data：不是 F2P、且折扣 100%（現價 0、原價 > 0）。"""
    if not data or data.get("is_free"):
        return False
    p = data.get("price_overview") or {}
    return p.get("discount_percent") == 100 and p.get("initial", 0) > 0 and p.get("final", 1) == 0


def diff_seen(seen_items, current):
    """回傳 (新出現的 appid 清單, 更新後的 items)。已結束的項目移除，下次再送才會再通知。"""
    new_ids = [i for i in current if i not in seen_items]
    items = {i: seen_items.get(i) or current[i] for i in current}
    return new_ids, items


def build_telegram_text(title, message, url=None):
    """組 Telegram HTML 訊息；遊戲名可能含 & < >，一律跳脫。"""
    e = html.escape
    lines = [f"<b>{e(title)}</b>", e(message)]
    if url:
        lines.append(f'<a href="{e(url, quote=True)}">{e(url)}</a>')
    return "\n".join(l for l in lines if l)


def format_message(info):
    kind = "DLC（需要本體）" if info.get("type") == "dlc" else "遊戲"
    price = info.get("initial_formatted") or ""
    return f"{kind}｜原價 {price}".strip("｜ ")


# ---------- 抓資料 ----------

def fetch_candidates():
    """兩個查詢合併：(1) 免費＋特價 (2) 特價依價格由低到高的第一頁中折扣 100% 的。"""
    found = {}
    # (1) 主查詢，可能有多頁
    start = 0
    while True:
        d = http_get(SEARCH_URL, {**COMMON, "maxprice": "free", "specials": "1", "start": start, "count": 100})
        rows = parse_search_html(d.get("results_html", ""))
        for r in rows:
            found[r["appid"]] = r
        start += 100
        if not rows or start >= d.get("total_count", 0):
            break
    # (2) 雙保險
    d = http_get(SEARCH_URL, {**COMMON, "specials": "1", "sort_by": "Price_ASC", "count": 100})
    rows = parse_search_html(d.get("results_html", ""))
    # 健康檢查：特價清單不可能是空的，空的代表被擋或格式變了
    print(f"特價清單解析：{len(rows)} 列（最低價折扣 {rows[0]['discount'] if rows else '—'}%）")
    if not rows:
        raise SystemExit("特價清單是空的：可能被 Steam 擋或網頁格式改了")
    for r in rows:
        if r["discount"] == 100:
            found.setdefault(r["appid"], r)
    return found


def fetch_details(appid):
    d = http_get(DETAILS_URL, {"appids": appid, "cc": "tw", "l": "tchinese", "filters": "basic,price_overview"})
    entry = d.get(appid) or {}
    return entry.get("data") if entry.get("success") else None


def notify(cfg, title, message, url=None):
    token, chat_id = cfg
    body = {"chat_id": chat_id, "text": build_telegram_text(title, message, url), "parse_mode": "HTML"}
    req = urllib.request.Request(TELEGRAM_URL.format(token=token), data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as err:
        # 不印 URL（含 token），只印 Telegram 回的錯誤說明
        raise SystemExit(f"Telegram 推播失敗：HTTP {err.code} {err.read().decode('utf-8', 'replace')}") from None


def load_seen():
    try:
        with open(SEEN_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_run": None, "items": {}}


def save_seen(seen):
    os.makedirs(os.path.dirname(SEEN_PATH), exist_ok=True)
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def main(argv):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    cfg = (token, chat_id) if token and chat_id else None
    dry = "--dry-run" in argv

    if "--test-notify" in argv:
        if not cfg:
            sys.exit("沒有設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
        notify(cfg, "測試通知", "Steam 免費偵測器設定成功", "https://store.steampowered.com/")
        print("已送出測試通知")
        return

    candidates = fetch_candidates()
    print(f"搜尋候選：{len(candidates)} 筆")

    current = {}
    for appid, row in candidates.items():
        data = fetch_details(appid)
        time.sleep(1.5)  # appdetails 有頻率限制
        if is_giveaway(data):
            p = data["price_overview"]
            current[appid] = {
                "name": data.get("name") or row["name"],
                "type": data.get("type"),
                "initial_formatted": p.get("initial_formatted"),
                "first_seen": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        else:
            print(f"  排除 {appid} {row['name']}（不是限時免費）")

    seen = load_seen()
    new_ids, items = diff_seen(seen.get("items", {}), current)
    print(f"目前限時免費：{len(current)} 筆，新出現：{len(new_ids)} 筆")

    for appid in new_ids:
        info = current[appid]
        url = f"https://store.steampowered.com/app/{appid}/"
        print(f"  新：{info['name']}｜{format_message(info)}｜{url}")
        if cfg and not dry:
            notify(cfg, f"Steam 限時免費：{info['name']}", format_message(info), url)

    if dry:
        return
    now = datetime.now(timezone.utc)
    last = seen.get("last_run")
    stale = not last or now - datetime.fromisoformat(last) > timedelta(days=KEEPALIVE_DAYS)
    if items != seen.get("items") or stale:
        save_seen({"last_run": now.isoformat(timespec="seconds") if stale else last, "items": items})
        print("seen.json 已更新")


if __name__ == "__main__":
    main(sys.argv[1:])
