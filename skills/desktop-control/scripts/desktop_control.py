from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
import time
from pathlib import Path


if sys.platform != "win32":
    raise SystemExit("desktop-control currently supports Windows only.")


user32 = ctypes.windll.user32

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

VK_CODES = {
    "alt": 0x12,
    "backspace": 0x08,
    "ctrl": 0x11,
    "delete": 0x2E,
    "down": 0x28,
    "end": 0x23,
    "enter": 0x0D,
    "esc": 0x1B,
    "f5": 0x74,
    "home": 0x24,
    "left": 0x25,
    "pgdn": 0x22,
    "pgup": 0x21,
    "right": 0x27,
    "shift": 0x10,
    "space": 0x20,
    "tab": 0x09,
    "up": 0x26,
    "win": 0x5B,
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", INPUT_UNION)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def send_input(*items: INPUT) -> None:
    array = (INPUT * len(items))(*items)
    sent = user32.SendInput(len(items), ctypes.byref(array), ctypes.sizeof(INPUT))
    if sent != len(items):
        raise RuntimeError("SendInput failed")


def keyboard_input(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    return INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags)))


def mouse_input(flags: int, data: int = 0) -> INPUT:
    return INPUT(type=INPUT_MOUSE, union=INPUT_UNION(mi=MOUSEINPUT(dwFlags=flags, mouseData=data)))


def get_position() -> dict[str, int]:
    point = POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise RuntimeError("GetCursorPos failed")
    return {"x": int(point.x), "y": int(point.y)}


def get_screen_size() -> dict[str, int]:
    return {"width": int(user32.GetSystemMetrics(0)), "height": int(user32.GetSystemMetrics(1))}


def move_mouse(x: int, y: int) -> dict[str, int]:
    if not user32.SetCursorPos(int(x), int(y)):
        raise RuntimeError("SetCursorPos failed")
    time.sleep(0.05)
    return get_position()


def click(button: str, double: bool) -> dict[str, object]:
    mapping = {
        "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    }
    down, up = mapping[button]
    count = 2 if double else 1
    for _ in range(count):
        send_input(mouse_input(down), mouse_input(up))
        time.sleep(0.05)
    return {"button": button, "double": double, "position": get_position()}


def scroll(amount: int) -> dict[str, object]:
    send_input(mouse_input(MOUSEEVENTF_WHEEL, amount))
    return {"amount": amount, "position": get_position()}


def type_text(text: str) -> dict[str, object]:
    events: list[INPUT] = []
    for char in text:
        codepoint = ord(char)
        events.append(keyboard_input(scan=codepoint, flags=KEYEVENTF_UNICODE))
        events.append(keyboard_input(scan=codepoint, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    send_input(*events)
    return {"typed": text, "length": len(text)}


def press_key(name: str) -> dict[str, str]:
    vk = resolve_vk(name)
    send_input(keyboard_input(vk=vk), keyboard_input(vk=vk, flags=KEYEVENTF_KEYUP))
    return {"key": name}


def hotkey(keys: list[str]) -> dict[str, object]:
    vks = [resolve_vk(key) for key in keys]
    for vk in vks:
        send_input(keyboard_input(vk=vk))
    for vk in reversed(vks):
        send_input(keyboard_input(vk=vk, flags=KEYEVENTF_KEYUP))
    return {"keys": keys}


def screenshot(out_path: Path) -> dict[str, str]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ps = rf"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bitmap.Size)
$bitmap.Save('{str(out_path)}', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
"""
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stdout + proc.stderr).strip() or "Screenshot capture failed")
    return {"path": str(out_path.resolve())}


def resolve_vk(name: str) -> int:
    lowered = name.lower()
    if lowered in VK_CODES:
        return VK_CODES[lowered]
    if len(lowered) == 1:
        code = user32.VkKeyScanW(ord(lowered))
        if code == -1:
            raise ValueError(f"Unsupported key: {name}")
        return code & 0xFF
    raise ValueError(f"Unsupported key: {name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("position")
    sub.add_parser("screen-size")

    move_parser = sub.add_parser("move")
    move_parser.add_argument("--x", type=int, required=True)
    move_parser.add_argument("--y", type=int, required=True)

    click_parser = sub.add_parser("click")
    click_parser.add_argument("--x", type=int)
    click_parser.add_argument("--y", type=int)
    click_parser.add_argument("--button", choices=["left", "right", "middle"], default="left")
    click_parser.add_argument("--double", action="store_true")

    scroll_parser = sub.add_parser("scroll")
    scroll_parser.add_argument("--amount", type=int, required=True)

    type_parser = sub.add_parser("type")
    type_parser.add_argument("--text", required=True)

    key_parser = sub.add_parser("key")
    key_parser.add_argument("--key", required=True)

    hotkey_parser = sub.add_parser("hotkey")
    hotkey_parser.add_argument("--keys", required=True, help="Comma-separated, e.g. ctrl+l")

    screenshot_parser = sub.add_parser("screenshot")
    screenshot_parser.add_argument("--out", required=True)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "position":
        result = get_position()
    elif args.command == "screen-size":
        result = get_screen_size()
    elif args.command == "move":
        result = move_mouse(args.x, args.y)
    elif args.command == "click":
        if args.x is not None and args.y is not None:
            move_mouse(args.x, args.y)
        result = click(args.button, args.double)
    elif args.command == "scroll":
        result = scroll(args.amount)
    elif args.command == "type":
        result = type_text(args.text)
    elif args.command == "key":
        result = press_key(args.key)
    elif args.command == "hotkey":
        result = hotkey([item.strip() for item in args.keys.replace("+", ",").split(",") if item.strip()])
    elif args.command == "screenshot":
        result = screenshot(Path(args.out))
    else:
        raise AssertionError(f"Unhandled command: {args.command}")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
