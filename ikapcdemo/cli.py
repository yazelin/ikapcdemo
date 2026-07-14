"""CLI: list / features / get / set / snapshot / serve."""

import argparse
import subprocess
import sys

from .camera import Camera, list_cameras


def _fmt(value):
    if isinstance(value, float):
        return ("%f" % value).rstrip("0").rstrip(".")
    return str(value)


def cmd_list(args):
    cams = list_cameras()
    if not cams:
        print("no cameras found", file=sys.stderr)
        return 2
    print("%-16s %-24s %-16s %s" % ("SERIAL", "MODEL", "VENDOR", "CLASS"))
    for c in cams:
        print("%-16s %-24s %-16s %s" % (c["serial"], c["model"],
                                        c["vendor"], c["device_class"]))
    return 0


def cmd_features(args):
    from . import bindings as b
    names = {b.TYPE_INT32: "int", b.TYPE_INT64: "int", b.TYPE_FLOAT: "float",
             b.TYPE_DOUBLE: "float", b.TYPE_BOOL: "bool", b.TYPE_ENUM: "enum",
             b.TYPE_STRING: "string", b.TYPE_COMMAND: "command"}
    with Camera(args.device) as cam:
        print("%-34s %-8s %-16s %s" % ("NAME", "TYPE", "VALUE", "RANGE/ENTRIES"))
        for f in cam.list_features():
            extra = ""
            if "min" in f:
                extra = "%s..%s" % (_fmt(f["min"]), _fmt(f["max"]))
                if f.get("inc", 1) not in (0, 1):
                    extra += " step %s" % f["inc"]
            elif "entries" in f:
                extra = ", ".join(f["entries"])
            print("%-34s %-8s %-16s %s" % (
                f["name"], names.get(f["type"], f["type"]),
                _fmt(f.get("value", "")), extra))
    return 0


def cmd_get(args):
    with Camera(args.device) as cam:
        print(_fmt(cam.get(args.name)))
    return 0


def cmd_set(args):
    with Camera(args.device) as cam:
        cam.set(args.name, args.value)
        if cam.feature_type(args.name) != 8:  # command has nothing to read back
            print(_fmt(cam.get(args.name)))
    return 0


def cmd_snapshot(args):
    with Camera(args.device) as cam:
        size = None
        if args.size:
            w, h = args.size.lower().split("x")
            size = (int(w), int(h))
        ppm = cam.read_ppm(exposure_us=args.exposure, gain=args.gain, size=size)
    if args.output.lower().endswith(".ppm"):
        with open(args.output, "wb") as fh:
            fh.write(ppm)
    else:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", "pipe:0",
                        "-frames:v", "1", "-q:v", "2", args.output],
                       input=ppm, check=True)
    print("saved %s" % args.output)
    return 0


def cmd_serve(args):
    from .server import serve
    serve(serial=args.device, host=args.host, port=args.port)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ikapcdemo",
                                 description="I-Tek/MORITEX USB3 Vision camera tool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def dev(p):
        p.add_argument("-d", "--device", default=None,
                       help="camera serial (default: first camera)")

    sub.add_parser("list", help="list cameras")

    p = sub.add_parser("features", help="list camera features")
    dev(p)

    p = sub.add_parser("get", help="read a feature")
    dev(p)
    p.add_argument("name")

    p = sub.add_parser("set", help="write a feature (or run a command)")
    dev(p)
    p.add_argument("name")
    p.add_argument("value")

    p = sub.add_parser("snapshot", help="capture one frame")
    dev(p)
    p.add_argument("-e", "--exposure", type=float, default=None,
                   help="exposure time in microseconds")
    p.add_argument("-g", "--gain", type=float, default=None, help="analog gain")
    p.add_argument("-w", "--size", default=None, help="ROI as WxH (default: full)")
    p.add_argument("-o", "--output", default="snapshot.jpg",
                   help=".jpg (via ffmpeg) or .ppm (raw)")

    p = sub.add_parser("serve", help="start web UI")
    dev(p)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8601)

    args = ap.parse_args(argv)
    handler = {"list": cmd_list, "features": cmd_features, "get": cmd_get,
               "set": cmd_set, "snapshot": cmd_snapshot, "serve": cmd_serve}[args.cmd]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
