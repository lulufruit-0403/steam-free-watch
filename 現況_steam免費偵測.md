# 現況：Steam 限時免費偵測器

最後更新：2026-11-18｜階段：已上 GitHub、Actions 跑過一次成功；尚未設定 ntfy 推播

決定：公開 repo＋ntfy 推播。
- Repo：https://github.com/lulufruit-0403/steam-free-watch （公開，main 分支）
- 本機已裝 GitHub CLI 2.104.0（`C:\Program Files\GitHub CLI\gh.exe`），已登入 lulufruit-0403。
- 本 repo 的 commit 信箱用 GitHub noreply，不用 Gmail。
- 2026-11-18 第一次 Actions 執行成功：測試通過、Steam 可從 GitHub 機房存取（候選 0 筆）。之後加了「特價清單解析列數」健康檢查。

## 目標
偵測 Steam「限時免費領取」（原價 > 0、折扣 100%，領了永久保留），有新的就推播到手機。
執行在 GitHub Actions（電腦關機也照跑）。v1 只通知，不自動領取。

## 已實測的事實（2026-11-18）
- 搜尋端點可用、免登入、回 JSON：
  `https://store.steampowered.com/search/results/?maxprice=free&specials=1&infinite=1&count=50&cc=tw&l=tchinese`
  - 回傳 `{success, results_html, total_count, start}`，遊戲在 `results_html` 裡。
  - 每筆有 `data-ds-appid="<id>"`，折扣區塊有 `data-discount="75"`、`data-price-final="11300"`（單位：分）。
  - `specials=1` 單獨 → 11206 筆；`maxprice=free` 單獨 → 72614 筆（大多是 F2P）；兩者合併 → 當下 0 筆。
  - **還沒確認**：合併查詢在「真的有限時免費」時會不會列出該遊戲（當下 0 筆可能只是剛好沒有活動）。所以採雙保險，見下方。
- 詳細資料端點可用：`https://store.steampowered.com/api/appdetails?appids=<id>&cc=tw&filters=price_overview,basic`
  - 有 `is_free`、`price_overview.discount_percent`、`initial`、`final`。
- Reddit r/FreeGameFindings：JSON 回 403、RSS 回 404（從本機打），**不採用**。
- GitHub 官方文件：公開 repo 若 60 天沒有任何活動，排程 workflow 會被自動停用。
- **還沒確認**：私人 repo 目前的免費分鐘數（印象中是 2000 分/月，要用私人 repo 時再查）。

## 偵測邏輯
1. 主查詢：`maxprice=free&specials=1`，抓出所有 appid。
2. 雙保險：`specials=1` 依折扣排序後抓前幾頁，挑出 `data-discount="100"` 的項目（防止主查詢漏抓）。
3. 對每個候選 appid 呼叫 appdetails 確認：`is_free == false` 且 `discount_percent == 100`（排除 F2P）。
4. 類型 `type`：game / dlc 分開標示；DLC 通知加註「需要本體」。
5. 跟 `data/seen.json` 比對，只通知新的；特價結束的項目從 seen 移除（下次再送才會再通知）。
6. 截止時間：先試著從商店頁抓特價結束時間，抓不到就不顯示（v1 不硬求）。

## 推播
預設 **ntfy**（手機裝 ntfy App、訂閱一個難猜的 topic 名稱即可，免帳號）。
topic 名稱放 GitHub Secrets（`NTFY_TOPIC`），不寫進程式碼。
內容：遊戲名｜類型｜原價｜商店連結。

## Repo 結構（規劃）
```
steam-free-watch/
├─ check.py                 # 主程式（只用 requests + 標準庫）
├─ data/seen.json           # 已通知清單，由 workflow commit 回 repo
├─ tests/test_filter.py     # 含「故意放一筆假的 100% 折扣資料，必須被抓到」與「F2P 必須被排除」
└─ .github/workflows/check.yml
     ├─ on: schedule cron "17 */4 * * *"（每 4 小時，避開整點尖峰）＋ workflow_dispatch（手動測試）
     ├─ permissions: contents: write
     └─ 跑 check.py → 有變動就 commit seen.json（同時讓 repo 保持活動，避開 60 天停用）
```
- seen.json 沒有變動的期間 repo 不會有 commit → 加一個每月一次的保活 commit（或寫入 `last_run`），確保 60 天內一定有活動。

## 分階段
- v1：上面全部（Steam 限時免費 → ntfy）。
- v2：免費週末另外分類；加 IsThereAnyDeal API 交叉比對（需申請 key）。
- v3（可選）：Epic / GOG。自動領取（ASF）不在規劃內，除非使用者另外決定。

## v1 已完成（實際檔案）
- `check.py`：只用標準庫；`--dry-run`、`--test-notify`。推播用 ntfy JSON 發布（中文標題不會亂碼）。
- `tests/test_filter.py`：7 個測試。故意把 is_giveaway 改成永遠 True → 3 個失敗，確認抓得到。
- `.github/workflows/check.yml`：每 4 小時＋手動執行（可勾「只送測試通知」）；有變動才 commit seen.json。
- 本機實跑：解析 100 列中的 99 列（1 列是套組，依設計略過），appdetails 正常；當下限時免費 0 筆。

## 還沒確認
- 真的有限時免費時，兩個查詢都抓得到（目前沒有活動可驗證）。
- 手機推播實際收不收得到。

## 下一步
1. push 健康檢查 commit（需使用者同意）。
2. 使用者手機裝 ntfy、訂閱主題（Claude 已產生亂數名稱，見對話；不寫進 repo）→ `gh secret set NTFY_TOPIC` → `gh workflow run check.yml -f test_notify=true` 確認手機收到。
