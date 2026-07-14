"""ikapcdemo: single-shot capture for I-Tek / MORITEX USB3 Vision cameras
via the vendor IKapC SDK (library + CLI + web UI)."""

from .camera import Camera, list_cameras, to_ppm

__version__ = "0.1.0"
__all__ = ["Camera", "list_cameras", "to_ppm", "__version__"]
