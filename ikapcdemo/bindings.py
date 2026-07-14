"""ctypes bindings for the I-Tek IKapC SDK (libIKapC).

Only the functions ikapcdemo needs. The vendor SDK (IKapInstall package)
must be installed; it registers /opt/Itek paths with ldconfig.
Constant values were extracted from the vendor headers with a one-off
C program (numeric facts, headers themselves are not redistributed).
"""

import ctypes
from ctypes import (POINTER, Structure, c_char, c_char_p, c_double, c_int,
                    c_int64, c_uint8, c_uint32, c_void_p)

STATUS_OK = 0x00000000
ACCESS_MODE_EXCLUSIVE = 0x00000004

BUFFER_FORMAT_RGB888 = 0x01081808
BUFFER_PRM_STATE = 0x00070004
BUFFER_PRM_SIZE = 0x00090008
BUFFER_STATE_FULL = 0x00000002
BUFFER_STATE_UNCOMPLETED = 0x00000008

STREAM_PRM_START_MODE = 0x00020004
STREAM_PRM_TRANSFER_MODE = 0x00030004
STREAM_PRM_TIME_OUT = 0x00050004
STREAM_START_MODE_NON_BLOCK = 0x00000000
STREAM_TRANSFER_MODE_SYNC_WITH_PROTECT = 0x00000002

TYPE_INT32 = 1
TYPE_INT64 = 2
TYPE_FLOAT = 3
TYPE_DOUBLE = 4
TYPE_BOOL = 5
TYPE_ENUM = 6
TYPE_STRING = 7
TYPE_COMMAND = 8
TYPE_CATEGORY = 9
TYPE_REGISTER = 10

ACCESS_RW = 1
ACCESS_RO = 2
ACCESS_WO = 3

_ENTRY = 64


class DevInfo(Structure):
    _fields_ = [(name, c_char * _ENTRY) for name in (
        "FullName", "FriendlyName", "VendorName", "ModelName",
        "SerialNumber", "DeviceClass", "DeviceVersion", "UserDefinedName")]


class IKapCError(RuntimeError):
    def __init__(self, func, status):
        self.func = func
        self.status = status
        super().__init__("%s failed with status 0x%08X" % (func, status))


def _load():
    for name in ("libIKapC.so.1", "libIKapC.so",
                 "/opt/Itek/IKap/Lib/lib64/libIKapC.so.1.4"):
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    raise ImportError(
        "libIKapC not found - install the I-Tek IKapInstall SDK package")


_lib = _load()

# (name, restype-is-status, argtypes)
_PROTOTYPES = [
    ("ItkManInitialize", []),
    ("ItkManTerminate", []),
    ("ItkManGetDeviceCount", [POINTER(c_uint32)]),
    ("ItkManGetDeviceInfo", [c_uint32, POINTER(DevInfo)]),
    ("ItkDevOpen", [c_uint32, c_int, POINTER(c_void_p)]),
    ("ItkDevClose", [c_void_p]),
    ("ItkDevGetFeatureCount", [c_void_p, POINTER(c_uint32)]),
    ("ItkDevGetFeatureName", [c_void_p, c_uint32, c_char_p, POINTER(c_uint32)]),
    ("ItkDevGetType", [c_void_p, c_char_p, POINTER(c_uint32)]),
    ("ItkDevGetAccessMode", [c_void_p, c_char_p, POINTER(c_uint32)]),
    ("ItkDevGetInt64", [c_void_p, c_char_p, POINTER(c_int64)]),
    ("ItkDevSetInt64", [c_void_p, c_char_p, c_int64]),
    ("ItkDevGetInt64Min", [c_void_p, c_char_p, POINTER(c_int64)]),
    ("ItkDevGetInt64Max", [c_void_p, c_char_p, POINTER(c_int64)]),
    ("ItkDevGetInt64Inc", [c_void_p, c_char_p, POINTER(c_int64)]),
    ("ItkDevGetDouble", [c_void_p, c_char_p, POINTER(c_double)]),
    ("ItkDevSetDouble", [c_void_p, c_char_p, c_double]),
    ("ItkDevGetDoubleMin", [c_void_p, c_char_p, POINTER(c_double)]),
    ("ItkDevGetDoubleMax", [c_void_p, c_char_p, POINTER(c_double)]),
    ("ItkDevGetBool", [c_void_p, c_char_p, POINTER(c_uint8)]),
    ("ItkDevSetBool", [c_void_p, c_char_p, c_uint8]),
    ("ItkDevToString", [c_void_p, c_char_p, c_char_p, POINTER(c_uint32)]),
    ("ItkDevFromString", [c_void_p, c_char_p, c_char_p]),
    ("ItkDevExecuteCommand", [c_void_p, c_char_p]),
    ("ItkDevGetEnumCount", [c_void_p, c_char_p, POINTER(c_uint32)]),
    ("ItkDevGetEnumString", [c_void_p, c_char_p, c_uint32, c_char_p, POINTER(c_uint32)]),
    ("ItkDevAllocStream", [c_void_p, c_uint32, c_void_p, POINTER(c_void_p)]),
    ("ItkDevFreeStream", [c_void_p]),
    ("ItkStreamSetPrm", [c_void_p, c_uint32, c_void_p]),
    ("ItkStreamStart", [c_void_p, c_uint32]),
    ("ItkStreamWait", [c_void_p]),
    ("ItkStreamStop", [c_void_p]),
    ("ItkStreamRemoveBuffer", [c_void_p, c_void_p]),
    ("ItkBufferNew", [c_int64, c_int64, c_uint32, POINTER(c_void_p)]),
    ("ItkBufferFree", [c_void_p]),
    ("ItkBufferGetPrm", [c_void_p, c_uint32, c_void_p]),
    ("ItkBufferRead", [c_void_p, c_uint32, c_void_p, c_uint32]),
]

for _name, _args in _PROTOTYPES:
    _fn = getattr(_lib, _name)
    _fn.argtypes = _args
    _fn.restype = c_uint32


def call(name, *args, ok=(STATUS_OK,)):
    """Invoke an IKapC function; raise IKapCError on non-OK status."""
    status = getattr(_lib, name)(*args)
    if status not in ok:
        raise IKapCError(name, status)
    return status
