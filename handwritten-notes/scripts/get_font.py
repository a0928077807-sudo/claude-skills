"""下載手寫字型「辰宇落雁體」並移除 TrueType hinting，存成 fonts/ChenYuluoyan-nohint.ttf。

原檔在 Pillow 某些字級會丟 `OSError: too many function definitions`，去掉 hinting 就正常；字形不變。
字型授權 SIL OFL 1.1，保留名稱「辰宇落雁」「Chenyuluoyan」，所以處理後的檔只在本機用、不重新發布。
"""
import os, sys, tempfile, urllib.request

URL = 'https://github.com/Chenyu-otf/chenyuluoyan_thin/releases/download/v2.0/ChenYuluoyan-2.0-Thin.ttf'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts', 'ChenYuluoyan-nohint.ttf')

def ensure_font():
    if os.path.exists(OUT):
        return OUT
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables import ttProgram
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    print(f'第一次使用：下載字型 {URL}（約 9.5 MB）', file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, 'raw.ttf')
        urllib.request.urlretrieve(URL, raw)
        f = TTFont(raw)
        for t in ('fpgm', 'prep', 'cvt ', 'hdmx', 'LTSH', 'VDMX'):
            if t in f:
                del f[t]
        for g in f['glyf'].glyphs.values():
            if hasattr(g, 'program'):
                g.program = ttProgram.Program()
                g.program.fromBytecode(b'')
        f.save(OUT)
        f.close()
    return OUT

if __name__ == '__main__':
    print(ensure_font())
