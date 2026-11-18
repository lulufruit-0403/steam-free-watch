# steam-free-watch

每 4 小時檢查 Steam 是否有「限時免費領取」（原價 > 0、折扣 100%）的遊戲或 DLC，新出現的推播到 [ntfy](https://ntfy.sh)。

## 設定
1. 手機安裝 ntfy App，訂閱一個難猜的主題名稱（例如 `steam-free-` 加一串亂數）。
2. GitHub repo → Settings → Secrets and variables → Actions → New repository secret：
   名稱 `NTFY_TOPIC`，值填上面的主題名稱。
3. Actions 分頁 → steam-free-check → Run workflow，勾選「只送一則測試通知」，確認手機收得到。

## 本機執行
```
python -m unittest discover -s tests
python check.py --dry-run
```
