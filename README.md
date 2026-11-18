# steam-free-watch

每 4 小時檢查 Steam 是否有「限時免費領取」（原價 > 0、折扣 100%）的遊戲或 DLC，新出現的推播到 Telegram。

## 設定
1. Telegram 找 @BotFather → `/newbot`，取得 bot token。
2. 對自己的 bot 傳一則訊息（例如 `/start`），否則 bot 不能主動傳訊息給你。
3. 用 @userinfobot 查自己的 chat id（一串數字）。
4. GitHub repo → Settings → Secrets and variables → Actions → New repository secret，新增兩個：
   - `TELEGRAM_BOT_TOKEN`：bot token
   - `TELEGRAM_CHAT_ID`：chat id
5. Actions 分頁 → steam-free-check → Run workflow，勾選「只送一則測試通知」，確認手機收得到。

## 本機執行
```
python -m unittest discover -s tests
python check.py --dry-run
```
