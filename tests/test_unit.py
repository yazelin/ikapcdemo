"""零硬體單元測試:PPM 編碼、CLI 解析、常數存在。"""
import unittest


class TestPpm(unittest.TestCase):
    def test_header_and_payload(self):
        from ikapcdemo.camera import to_ppm
        data = bytes(range(9))  # 3 px RGB
        ppm = to_ppm(3, 1, data)
        self.assertTrue(ppm.startswith(b"P6\n3 1\n255\n"))
        self.assertTrue(ppm.endswith(data))
        self.assertEqual(len(ppm), len(b"P6\n3 1\n255\n") + 9)


class TestCliParsing(unittest.TestCase):
    def test_snapshot_args(self):
        # 只驗 argparse 佈線,不碰硬體:給 --help 應 SystemExit(0)
        from ikapcdemo import cli
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["snapshot", "--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_requires_subcommand(self):
        from ikapcdemo import cli
        with self.assertRaises(SystemExit) as ctx:
            cli.main([])
        self.assertNotEqual(ctx.exception.code, 0)


class TestBindingsConstants(unittest.TestCase):
    def test_constants(self):
        # bindings 模組 import 需要 libIKapC;常數表不依賴它
        import importlib.util
        import pathlib
        src = pathlib.Path(__file__).resolve().parent.parent / "ikapcdemo" / "bindings.py"
        text = src.read_text()
        for const in ("BUFFER_FORMAT_RGB888 = 0x01081808",
                      "STREAM_PRM_TIME_OUT = 0x00050004",
                      "BUFFER_STATE_FULL = 0x00000002"):
            self.assertIn(const, text)



class TestSetIfDiffers(unittest.TestCase):
    def _cam(self, current):
        """不開真相機:繞過 __init__,只裝上 get/set 記錄。"""
        from ikapcdemo.camera import Camera
        cam = object.__new__(Camera)
        cam.sets = []
        cam.get = lambda name: current
        cam.set = lambda name, value: cam.sets.append((name, value))
        return cam

    def test_skips_equal_value(self):
        cam = self._cam(120000.0)
        cam.set_if_differs("ExposureTime", 120000)
        self.assertEqual(cam.sets, [])

    def test_writes_changed_value(self):
        cam = self._cam(14999.0)
        cam.set_if_differs("ExposureTime", 120000.0)
        self.assertEqual(cam.sets, [("ExposureTime", 120000.0)])

    def test_string_compare(self):
        cam = self._cam("RGB8")
        cam.set_if_differs("PixelFormat", "RGB8")
        self.assertEqual(cam.sets, [])
        cam2 = self._cam("Mono8")
        cam2.set_if_differs("PixelFormat", "RGB8")
        self.assertEqual(cam2.sets, [("PixelFormat", "RGB8")])

if __name__ == "__main__":
    unittest.main()
