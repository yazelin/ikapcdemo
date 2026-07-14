# ikapcdemo — I-Tek USB3 Vision 相機拍照工具(library + CLI + web UI)

ikapcdemo 是一個純 Python(零相依,ctypes)的 I-Tek USB3 Vision 工業相機**單拍**工具,走原廠 IKapC SDK。同一套程式提供三種用法:當 **library** 匯入(`with Camera() as cam: ...`)、當 **CLI** 操作(`ikapcdemo snapshot -e 100000 -o shot.jpg`)、或啟動內建 **web UI** 拍照與調參。介面刻意做成與 [webcamdemo](https://github.com/yazelin/webcamdemo)/[visordemo](https://github.com/yazelin/visordemo) 同一家族,消費端(如品檢站)換掉 `camera_factory` 即可在 USB webcam、VISOR、USB3 Vision 相機之間切換。

實機驗證:I-Tek **UA20MARU30-19C**(20MP 5496x3672,Cypress FX3 `04b4:00f0`,配 MORITEX 鏡頭)@ Ubuntu 24.04。

## 為什麼走原廠 SDK 而不是 Aravis

這台相機用開源 Aravis(0.8.30 與 0.8.36 皆實測)有韌體互動問題:**只要寫過曝光相關參數(ExposureAuto/ExposureTime/Gain),下一次全解析度串流就 MISSING_PACKETS,而且相機會卡死到斷電重插**。原廠 IKapC 的傳輸層配自家韌體調過,同樣的「改曝光 → 全幅取像」序列完全穩定(soak 10/10)。所以:

- **拍照(單拍、可調曝光)→ 本工具(IKapC)**
- 免費串流預覽(不動曝光參數)→ Aravis 系工具仍可用

## 前置需求

1. 原廠 **IKapInstall** SDK(Linux x86_64;向 I-Tek / 代理商索取),`sudo ./install.sh` 會裝好 `libIKapC`、udev rule 與 GRUB 的 `usbcore.usbfs_memory_mb=2000`
2. `ffmpeg`(存 `.jpg` 時用;存 `.ppm` 則零相依)

## 安裝

```bash
uv tool install git+https://github.com/yazelin/ikapcdemo
# 或
pipx install git+https://github.com/yazelin/ikapcdemo
```

## 用法

```bash
ikapcdemo list                          # 列相機
ikapcdemo features                      # 列全部可調參數(型別/現值/範圍)
ikapcdemo get ExposureTime
ikapcdemo set ExposureTime 100000
ikapcdemo snapshot -e 100000 -o shot.jpg   # 拍一張(曝光 100ms)
ikapcdemo snapshot -w 1280x720 -o roi.ppm  # ROI 快拍
ikapcdemo serve                          # web UI(預設 127.0.0.1:8601)
```

Library:

```python
from ikapcdemo import Camera

with Camera() as cam:                      # 或 Camera("25110012Y") 指定序號
    w, h, rgb = cam.capture(exposure_us=100000)   # 全幅 RGB bytes
    ppm = cam.read_ppm(exposure_us=100000)        # P6 PPM bytes
    cam.set("AnalogGain", 2.0)
    print(cam.get("ExposureTime"))
```

## 設計備忘

- **單拍模型**:每次 `capture()` 開一條 stream、抓一張、關掉。工業拍照機(條碼觸發、產品留存照)不需要連續串流,單拍也正好避開韌體串流地雷
- 每次 capture 都會重設 ROI 為全幅(`size=` 參數才縮),拍照機不該默默沿用上一張的裁切
- 原廠 header/函式庫**不隨附**於本 repo(專有授權);`bindings.py` 只是 ctypes 綁定與從 header 抽出的常數值
- 本版 Linux SDK 的 `ItkBufferSave` 未實作,存檔走 `ItkBufferRead` + 自己寫 PPM

## 測試

```bash
python3 -m unittest discover -s tests -v   # 4 tests,零硬體
python3 tests/smoke_test.py                # 真相機 smoke(ROI + 全幅x2 + 曝光)
```

已用於 [qc-station](https://github.com/ching-tech/qc-station) 品檢站當拍照機(`photo_device` 設 `ikapc:<serial>`)。

## 授權

MIT — 林亞澤 Yaze Lin

---

- 原始碼 GitHub:<https://github.com/yazelin/ikapcdemo>
- Facebook:<https://www.facebook.com/yaze.lin.gm>
- Buy Me a Coffee:<https://buymeacoffee.com/yazelin>
