"""無頭 Chrome 檢查網頁：收集 JS 錯誤、找超出畫面的元素、各寬度截圖。只用 Python 標準庫。

用法：
  python page_check.py URL [--widths 1280,393,360] [--height 800] [--wait 1.5] [--eval JS] [--out DIR]
有錯誤或有元素超出畫面時退出碼為 1。找不到 Chrome 時用環境變數 CHROME 指定路徑。
"""
import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium", "chromium-browser",
]

COLLECT = """
window.__errs = [];
addEventListener('error', e => __errs.push('error: ' + e.message + (e.filename ? ' @ ' + e.filename + ':' + e.lineno : '')));
addEventListener('unhandledrejection', e => __errs.push('reject: ' + (e.reason && e.reason.message || e.reason)));
addEventListener('securitypolicyviolation', e => __errs.push('csp: ' + e.violatedDirective + ' ' + e.blockedURI));
for (const k of ['error', 'warn']) { const o = console[k]; console[k] = (...a) => { __errs.push(k + ': ' + a.join(' ')); o.apply(console, a); }; }
"""

OVERFLOW = """(() => {
  const W = document.documentElement.clientWidth, out = [];   // innerWidth 在手機模擬下會跟著內容變寬，不能用
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (!r.width || cs.visibility === 'hidden' || cs.position === 'fixed' && r.left >= W) continue;
    if (r.right > W + 0.5) out.push((el.id ? '#' + el.id : el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : '')) + ' 右緣 ' + Math.round(r.right) + 'px');
  }
  return {W, scrollW: document.documentElement.scrollWidth, over: out.slice(0, 15)};
})()"""


def find_chrome():
    for c in [os.environ.get("CHROME")] + CANDIDATES:
        if c and (Path(c).exists() or shutil.which(c)):
            return shutil.which(c) or c
    sys.exit("找不到 Chrome，請用環境變數 CHROME 指定路徑")


class WS:
    """最小的 DevTools WebSocket 用戶端（只送文字框、只等自己那個 id 的回覆）。"""

    def __init__(self, url):
        hostport, path = url.split("://", 1)[1].split("/", 1)
        host, port = hostport.rsplit(":", 1)
        self.s = socket.create_connection((host, int(port)))
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
                        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        self.buf, self.n = buf.split(b"\r\n\r\n", 1)[1], 0

    def _read(self, k):
        while len(self.buf) < k:
            chunk = self.s.recv(1 << 20)
            if not chunk:
                raise EOFError
            self.buf += chunk
        out, self.buf = self.buf[:k], self.buf[k:]
        return out

    def call(self, method, **params):
        self.n += 1
        data = json.dumps({"id": self.n, "method": method, "params": params}).encode()
        head = bytearray([0x81])
        if len(data) < 126:
            head.append(0x80 | len(data))
        elif len(data) < 65536:
            head.append(0x80 | 126); head += struct.pack(">H", len(data))
        else:
            head.append(0x80 | 127); head += struct.pack(">Q", len(data))
        mask = os.urandom(4)
        self.s.sendall(bytes(head) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        while True:
            msg = b""
            while True:
                b1, b2 = self._read(2)
                n = b2 & 0x7F
                if n == 126:
                    n = struct.unpack(">H", self._read(2))[0]
                elif n == 127:
                    n = struct.unpack(">Q", self._read(8))[0]
                msg += self._read(n)
                if b1 & 0x80:
                    break
            m = json.loads(msg)
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    ap = argparse.ArgumentParser(description="無頭 Chrome 檢查網頁錯誤與手機跑版")
    ap.add_argument("url")
    ap.add_argument("--widths", default="1280,393,360")
    ap.add_argument("--height", type=int, default=800)
    ap.add_argument("--wait", type=float, default=1.5, help="載入後等幾秒再檢查")
    ap.add_argument("--eval", default="", help="檢查前先在頁面執行的 JS（例如切到登入後的畫面）")
    ap.add_argument("--out", default="page_check_shots")
    a = ap.parse_args()

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    port, prof = free_port(), tempfile.mkdtemp(prefix="page-check-")
    chrome = subprocess.Popen([find_chrome(), "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={prof}",
                               "--hide-scrollbars", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    bad = False
    try:
        tab = None
        for _ in range(80):
            try:
                tab = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json")) if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.25)
        if not tab:
            sys.exit("Chrome 沒有起來")
        ws = WS(tab["webSocketDebuggerUrl"])

        def js(expr):
            r = ws.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
            if "exceptionDetails" in r:
                raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"])
            return r["result"].get("value")

        ws.call("Page.enable"); ws.call("Runtime.enable")
        ws.call("Page.addScriptToEvaluateOnNewDocument", source=COLLECT)
        for w in (int(x) for x in a.widths.split(",")):
            mobile = w < 768
            ws.call("Emulation.setDeviceMetricsOverride", width=w, height=a.height, deviceScaleFactor=3 if mobile else 1, mobile=mobile)
            ws.call("Page.navigate", url=a.url)
            time.sleep(a.wait)
            if a.eval:
                try:
                    js(a.eval); time.sleep(0.5)
                except RuntimeError as e:
                    print(f"[{w}px] --eval 失敗：{e}")
            errs, ov = js("window.__errs || []"), js(OVERFLOW)
            shot = out / f"{w}.png"
            shot.write_bytes(base64.b64decode(ws.call("Page.captureScreenshot", format="png")["data"]))
            print(f"[{w}px] 錯誤 {len(errs)} 個、超出畫面 {len(ov['over'])} 個（版面寬 {ov['W']}、scrollWidth {ov['scrollW']}）→ {shot}")
            for e in errs:
                print("   ", e)
            for o in ov["over"]:
                print("    超出：", o)
            bad = bad or bool(errs) or bool(ov["over"]) or ov["scrollW"] > ov["W"]
    finally:
        chrome.terminate()
        try:
            chrome.wait(5)
        except subprocess.TimeoutExpired:
            chrome.kill()
        shutil.rmtree(prof, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
