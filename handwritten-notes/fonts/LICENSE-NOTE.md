這個資料夾放手寫字型「辰宇落雁體」v2.0 Thin（授權 SIL Open Font License 1.1，
保留字型名稱「辰宇落雁」「Chenyuluoyan」）。
來源：https://github.com/Chenyu-otf/chenyuluoyan_thin （release v2.0）

字型檔不放在 repo 裡：第一次執行 `scripts/hwnotes.py` 時，`scripts/get_font.py` 會自動下載原檔，
並用 fontTools 移除 TrueType hinting 後存成 `ChenYuluoyan-nohint.ttf`
（原檔在 Pillow 某些字級會丟 `OSError: too many function definitions`，字形本身不變）。
處理過的檔只供本機使用，依 OFL 規定不可用保留名稱重新發布。
