# claude-skills

自己在實際任務裡踩過坑之後整理出來的 [Claude Code](https://claude.com/claude-code) skills。

## web-ship-check：網頁前端上線檢查

改完網頁（HTML／CSS／JS），要跟人說「好了、上線了」之前用。專門處理「對方看到的不是你以為的那一版」：

- 哪些改動存檔就生效、哪些要重啟伺服器（不然畫面會半新半舊）
- Cloudflare 之類 CDN 連 404 都會快取好幾小時 → css／js 加 `?v=` 版本號
- 用 `curl` 看線上實際回應與快取標頭，不要只看本機
- `scripts/page_check.py`：只用 Python 標準庫驅動無頭 Chrome，收集 JS／CSP 錯誤、找出手機寬度下超出畫面的元素、各寬度截圖（不需要 node）
- 手機與 App 內建瀏覽器（微信、LINE）的常見誤判

### 安裝

把 `web-ship-check` 整個資料夾放進 `~/.claude/skills/`（Windows：`%USERPROFILE%\.claude\skills\`），重開 Claude Code 就會出現。

```bash
git clone https://github.com/a0928077807-sudo/claude-skills.git
cp -r claude-skills/web-ship-check ~/.claude/skills/
```

### 單獨用檢查腳本

```bash
python web-ship-check/scripts/page_check.py http://127.0.0.1:8000/ --widths 1280,393,360 --out shots
```

有錯誤或有元素超出畫面時退出碼為 1。找不到 Chrome 時用環境變數 `CHROME` 指定路徑。
