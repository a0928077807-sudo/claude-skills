---
name: web-ship-check
description: 改完網頁前端（HTML／CSS／JS）、要跟使用者說「好了、上線了」之前用。特別是後端框架掛靜態檔（FastAPI StaticFiles、Express static 等）、前面又有 Cloudflare 之類 CDN 的網站：分清楚哪些要重啟、幫 css/js 加快取版本號、用 curl 看線上實際回應、用無頭 Chrome 在手機寬度跑一遍抓錯誤與跑版。使用者回報「怎麼沒有」「沒更新」「手機上跑版」時也用。
---

# 網頁前端上線檢查

改完網頁最常見的翻車不是程式寫錯，而是**使用者看到的不是你以為的那一版**：一半新一半舊、被快取的舊檔或 404、只在手機寬度才壞。照下面的順序檢查完，才說「好了」。

## 1. 哪些要重啟才生效

| 改了什麼 | 什麼時候生效 |
|---|---|
| 靜態目錄裡的 html／css／js | 通常存檔就生效（伺服器每次請求讀磁碟） |
| 新增或修改 API 路由、middleware、用路由送出的檔案 | **要重啟伺服器** |
| 伺服器設定、環境變數 | 要重啟 |

兩種都改了、卻還沒重啟時，畫面會**半新半舊**：新的樣式和按鈕出現了，靠新路由的功能卻沒有。回報時要講清楚「重啟後才會有」。如果不能自己重啟（例如你就跑在那個服務裡），就請使用者重啟，不要假裝已經生效。

## 2. 快取：CDN 會把 404 也記住

- Cloudflare 的 Browser Cache TTL 會對可快取的副檔名（.css .js .png…）加上 `Cache-Control: max-age=…`，**連 404 也會加**。預設 4 小時。
- 典型事故：使用者在伺服器重啟前開過頁面 → 瀏覽器抓到新檔名的 404 並記住 → 重啟後仍然拿不到，功能靜悄悄地不出現（多半被 `try/catch` 吞掉）。
- **重啟前不要自己去打新的檔案路徑測試**：你的請求也會把 404 種進 CDN 的邊緣快取。
- 解法：html 裡每個 css／js 都帶版本號，改檔就換號。這種寫法不用重啟、也不必清 CDN：

  ```html
  <link rel="stylesheet" href="style.css?v=20261023">
  <script src="app.js?v=20261023"></script>
  ```

- html 本身要確認不被快取。`cf-cache-status: DYNAMIC` 代表 CDN 不快取它；如果被快取了，版本號就沒用了。

## 3. 看線上實際回應，不要只看本機

```bash
curl -s -D - -o /dev/null "https://網域/路徑/app.js?v=20261023" | grep -iE "^HTTP|cf-cache-status|cache-control|last-modified"
curl -s "https://網域/路徑/" | grep -c "v=20261023"     # 線上的 html 真的是新的
```

- `HTTP 200` 加上預期的 `last-modified`，才算新檔真的上線了。
- `cf-cache-status: HIT／EXPIRED` 的意思是 CDN 有一份快取；`DYNAMIC` 表示 CDN 不快取它。

## 4. 用無頭 Chrome 跑一遍（不需要 node）

`scripts/page_check.py` 只用 Python 標準庫，透過 Chrome DevTools Protocol 做下面幾件事：

- 開頁面，收集 `error`、`unhandledrejection`、CSP 違規和 `console.error`／`console.warn`；
- 在每個指定寬度找出超出畫面右緣的元素；
- 每個寬度各截一張圖。

```bash
python scripts/page_check.py http://127.0.0.1:8000/ --widths 1280,393,360 --out shots
python scripts/page_check.py http://127.0.0.1:8000/ --eval "document.getElementById('login').hidden=true"
```

- 有錯誤或有元素超出畫面，退出碼就是 1。
- 要登入才看得到的畫面，用 `--eval` 先改 DOM 或塞 localStorage，或者寫一個只綁 127.0.0.1 的假後端，把真的靜態目錄掛上去、API 回假資料，再整個流程跑一遍。
- 找不到 Chrome 時，用 `CHROME=路徑` 指定。

## 5. 手機的坑

- **至少跑 393 和 360 兩個寬度**。標題列塞太多按鈕，最常把「登出」之類的按鈕擠出畫面。
- **帶 `hidden` 屬性的元素**：只設 `style.height` 不會出現，要同時 `el.hidden = false`。
- **跟著其他元素位置畫的東西**（浮層、canvas、SVG）：位置要每一格重算，或用 ResizeObserver 同時看兩邊。輸入框長高時，下面的區塊會移動，容器大小卻沒變。
- **使用者截圖右邊被切掉時**：先在同寬度量一次。App 內建瀏覽器（微信、LINE）常常是頁面被放大了（字和按鈕等比例變大），不是版面壞了。量過沒超出就不要改。
- iPhone 上所有瀏覽器都是 WebKit。只在 Chrome 驗過的功能，要講明「iPhone 沒實測」。

## 6. 有版權或私人的素材

公開路徑只放程式，圖、音效、資料放在要登入的 API 後面。檢查公開路徑時，要確認回應裡沒有素材本身。

## 回報

一句話講清楚三件事：哪些已經生效、哪些要重啟才生效、哪些沒實測（例如 iPhone）。
