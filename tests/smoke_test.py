"""真相機 smoke test:需要一台 USB3 Vision 相機 + 原廠 IKapC SDK。

python3 tests/smoke_test.py
"""
import sys
import time

sys.path.insert(0, ".")

from ikapcdemo import Camera, list_cameras  # noqa: E402


def main():
    cams = list_cameras()
    assert cams, "no camera found"
    print("cameras:", cams)

    with Camera() as cam:
        feats = cam.list_features()
        assert any(f["name"] == "ExposureTime" for f in feats), "no ExposureTime"
        print("features:", len(feats))

        exposure = cam.get("ExposureTime")
        print("ExposureTime =", exposure)

        # 小 ROI 快拍
        t0 = time.time()
        w, h, rgb = cam.capture(size=(1280, 720))
        assert (w, h) == (1280, 720) and len(rgb) == w * h * 3
        print("roi capture ok, %.1fs" % (time.time() - t0))

        # 全解析度 + 指定曝光,連兩張(驗證曝光調整不影響穩定度)
        for i in range(2):
            t0 = time.time()
            w, h, rgb = cam.capture(exposure_us=100000)
            assert len(rgb) == w * h * 3
            print("full-res #%d %dx%d ok, %.1fs" % (i + 1, w, h, time.time() - t0))

    print("SMOKE PASS")


if __name__ == "__main__":
    main()
