"""Camera: open / feature access / single-shot capture via the vendor SDK.

Designed for USB3 Vision industrial cameras used as still-photo devices
(one triggered frame at a time), e.g. I-Tek UA-series. The
streaming path is the vendor's own, so exposure/gain changes do not
destabilise the camera the way generic GenICam stacks can on this firmware.
"""

import atexit
import threading
from ctypes import byref, c_char_p, c_double, c_int64, c_uint8, c_uint32, c_void_p, create_string_buffer

from . import bindings as b

_man_lock = threading.Lock()
_man_ready = False

# Feature categories are worth skipping entirely when listing: transport
# registers and factory internals are noise for a tuning UI.
_SKIP_TYPES = {b.TYPE_CATEGORY, b.TYPE_REGISTER, 0}


def _ensure_manager():
    global _man_ready
    with _man_lock:
        if not _man_ready:
            b.call("ItkManInitialize")
            atexit.register(_terminate)
            _man_ready = True


def _terminate():
    global _man_ready
    with _man_lock:
        if _man_ready:
            try:
                b.call("ItkManTerminate")
            except Exception:
                pass
            _man_ready = False


def list_cameras():
    """Return [{index, serial, model, vendor, device_class}, ...]."""
    _ensure_manager()
    n = c_uint32(0)
    b.call("ItkManGetDeviceCount", byref(n))
    cams = []
    for i in range(n.value):
        info = b.DevInfo()
        try:
            b.call("ItkManGetDeviceInfo", c_uint32(i), byref(info))
        except b.IKapCError:
            continue
        cams.append({
            "index": i,
            "serial": info.SerialNumber.decode(errors="replace"),
            "model": info.ModelName.decode(errors="replace"),
            "vendor": info.VendorName.decode(errors="replace"),
            "device_class": info.DeviceClass.decode(errors="replace"),
        })
    return cams


class Camera:
    """with Camera() as cam: w, h, rgb = cam.capture(exposure_us=100000)"""

    def __init__(self, serial=None):
        _ensure_manager()
        index = None
        for cam in list_cameras():
            if serial in (None, "", cam["serial"]):
                index = cam["index"]
                self.info = cam
                break
        if index is None:
            raise LookupError("no camera found" if not serial
                              else "no camera with serial %r" % serial)
        self._h = c_void_p()
        b.call("ItkDevOpen", c_uint32(index), b.ACCESS_MODE_EXCLUSIVE,
               byref(self._h))
        self._lock = threading.Lock()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        if self._h:
            try:
                b.call("ItkDevClose", self._h)
            finally:
                self._h = c_void_p()

    # -- typed feature access -----------------------------------------------

    def feature_type(self, name):
        t = c_uint32(0)
        b.call("ItkDevGetType", self._h, name.encode(), byref(t))
        return t.value

    def get(self, name):
        t = self.feature_type(name)
        if t in (b.TYPE_INT32, b.TYPE_INT64):
            v = c_int64(0)
            b.call("ItkDevGetInt64", self._h, name.encode(), byref(v))
            return v.value
        if t in (b.TYPE_FLOAT, b.TYPE_DOUBLE):
            v = c_double(0)
            b.call("ItkDevGetDouble", self._h, name.encode(), byref(v))
            return v.value
        if t == b.TYPE_BOOL:
            v = c_uint8(0)
            b.call("ItkDevGetBool", self._h, name.encode(), byref(v))
            return bool(v.value)
        return self._to_string(name)

    def set(self, name, value):
        t = self.feature_type(name)
        if t in (b.TYPE_INT32, b.TYPE_INT64) and not isinstance(value, str):
            b.call("ItkDevSetInt64", self._h, name.encode(), c_int64(int(value)))
        elif t in (b.TYPE_FLOAT, b.TYPE_DOUBLE) and not isinstance(value, str):
            b.call("ItkDevSetDouble", self._h, name.encode(), c_double(float(value)))
        elif t == b.TYPE_BOOL and not isinstance(value, str):
            b.call("ItkDevSetBool", self._h, name.encode(), c_uint8(1 if value else 0))
        elif t == b.TYPE_COMMAND:
            b.call("ItkDevExecuteCommand", self._h, name.encode())
        else:
            b.call("ItkDevFromString", self._h, name.encode(), str(value).encode())

    def execute(self, name):
        b.call("ItkDevExecuteCommand", self._h, name.encode())

    def _to_string(self, name):
        buf = create_string_buffer(256)
        size = c_uint32(len(buf))
        b.call("ItkDevToString", self._h, name.encode(), buf, byref(size))
        return buf.value.decode(errors="replace")

    def list_features(self):
        """Readable/writable features with type, value, range, enum entries."""
        n = c_uint32(0)
        b.call("ItkDevGetFeatureCount", self._h, byref(n))
        out = []
        for i in range(n.value):
            buf = create_string_buffer(128)
            size = c_uint32(len(buf))
            try:
                b.call("ItkDevGetFeatureName", self._h, c_uint32(i), buf, byref(size))
            except b.IKapCError:
                continue
            name = buf.value.decode(errors="replace")
            try:
                t = self.feature_type(name)
                if t in _SKIP_TYPES:
                    continue
                access = c_uint32(0)
                b.call("ItkDevGetAccessMode", self._h, name.encode(), byref(access))
                if access.value not in (b.ACCESS_RW, b.ACCESS_RO, b.ACCESS_WO):
                    continue
                feat = {"name": name, "type": t, "access": access.value}
                if access.value != b.ACCESS_WO and t != b.TYPE_COMMAND:
                    feat["value"] = self.get(name)
                if t in (b.TYPE_INT32, b.TYPE_INT64):
                    lo, hi, inc = c_int64(0), c_int64(0), c_int64(1)
                    b.call("ItkDevGetInt64Min", self._h, name.encode(), byref(lo))
                    b.call("ItkDevGetInt64Max", self._h, name.encode(), byref(hi))
                    b.call("ItkDevGetInt64Inc", self._h, name.encode(), byref(inc))
                    feat.update(min=lo.value, max=hi.value, inc=inc.value or 1)
                elif t in (b.TYPE_FLOAT, b.TYPE_DOUBLE):
                    lo, hi = c_double(0), c_double(0)
                    b.call("ItkDevGetDoubleMin", self._h, name.encode(), byref(lo))
                    b.call("ItkDevGetDoubleMax", self._h, name.encode(), byref(hi))
                    feat.update(min=lo.value, max=hi.value)
                elif t == b.TYPE_ENUM:
                    feat["entries"] = self._enum_entries(name)
                out.append(feat)
            except b.IKapCError:
                continue
        return out

    def _enum_entries(self, name):
        n = c_uint32(0)
        b.call("ItkDevGetEnumCount", self._h, name.encode(), byref(n))
        entries = []
        for i in range(n.value):
            buf = create_string_buffer(128)
            size = c_uint32(len(buf))
            try:
                b.call("ItkDevGetEnumString", self._h, name.encode(),
                       c_uint32(i), buf, byref(size))
                entries.append(buf.value.decode(errors="replace"))
            except b.IKapCError:
                continue
        return entries

    # -- capture --------------------------------------------------------------

    def capture(self, exposure_us=None, gain=None, size=None, timeout_ms=15000):
        """Grab one RGB frame; returns (width, height, rgb_bytes)."""
        with self._lock:
            self.set("PixelFormat", "RGB8")
            if not size:  # photo device: default is always the full sensor
                size = (self.get("WidthMax"), self.get("HeightMax"))
            self.set("OffsetX", 0)
            self.set("OffsetY", 0)
            self.set("Width", size[0])
            self.set("Height", size[1])
            if exposure_us is not None:
                try:
                    self.set("ExposureAuto", "Off")
                except b.IKapCError:
                    pass
                self.set("ExposureTime", float(exposure_us))
            if gain is not None:
                self.set("AnalogGain", float(gain))
            w = self.get("Width")
            h = self.get("Height")

            hbuf, hstream = c_void_p(), c_void_p()
            b.call("ItkBufferNew", c_int64(w), c_int64(h),
                   b.BUFFER_FORMAT_RGB888, byref(hbuf))
            try:
                b.call("ItkDevAllocStream", self._h, c_uint32(0), hbuf,
                       byref(hstream))
                try:
                    for prm, val in ((b.STREAM_PRM_START_MODE, b.STREAM_START_MODE_NON_BLOCK),
                                     (b.STREAM_PRM_TRANSFER_MODE, b.STREAM_TRANSFER_MODE_SYNC_WITH_PROTECT),
                                     (b.STREAM_PRM_TIME_OUT, timeout_ms)):
                        b.call("ItkStreamSetPrm", hstream, c_uint32(prm),
                               byref(c_uint32(val)))
                    b.call("ItkStreamStart", hstream, c_uint32(1))
                    b.call("ItkStreamWait", hstream)

                    state = c_uint32(0)
                    b.call("ItkBufferGetPrm", hbuf, b.BUFFER_PRM_STATE, byref(state))
                    if state.value != b.BUFFER_STATE_FULL:
                        raise RuntimeError(
                            "incomplete frame (buffer state=0x%x)" % state.value)
                    nbytes = c_int64(0)
                    b.call("ItkBufferGetPrm", hbuf, b.BUFFER_PRM_SIZE, byref(nbytes))
                    data = create_string_buffer(nbytes.value)
                    b.call("ItkBufferRead", hbuf, c_uint32(0), data,
                           c_uint32(nbytes.value))
                    return w, h, data.raw
                finally:
                    for cleanup, args in (("ItkStreamRemoveBuffer", (hstream, hbuf)),
                                          ("ItkDevFreeStream", (hstream,))):
                        try:
                            b.call(cleanup, *args)
                        except b.IKapCError:
                            pass
            finally:
                try:
                    b.call("ItkBufferFree", hbuf)
                except b.IKapCError:
                    pass

    def read_ppm(self, **kwargs):
        """capture() then encode as binary PPM (P6) bytes."""
        w, h, rgb = self.capture(**kwargs)
        return to_ppm(w, h, rgb)


def to_ppm(width, height, rgb):
    return b"P6\n%d %d\n255\n" % (width, height) + rgb
