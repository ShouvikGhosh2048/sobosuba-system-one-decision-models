"""Window I/O for the sobosuba window: find/focus it, capture it, and drive the real mouse.

Capture uses PrintWindow, so it works even when the window is covered. Input has to be
real (SendInput) and the game must be the foreground window, or the game ignores it.
"""
import ctypes, time
from ctypes import wintypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)
import numpy as np, win32gui, win32ui, win32con, win32com.client

def find(title='sobosuba'):
    w = []
    win32gui.EnumWindows(lambda h, o: o.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) == title else None, w)
    if not w: raise RuntimeError('sobosuba window not found - is the game running?')
    return w[0]

def focus(h, tries=5):
    """Bring the game to the foreground; returns False if Windows refuses."""
    for _ in range(tries):
        if win32gui.GetForegroundWindow() == h: return True
        try:
            win32com.client.Dispatch("WScript.Shell").SendKeys('%')  # lets SetForegroundWindow succeed
            win32gui.ShowWindow(h, win32con.SW_RESTORE); win32gui.SetForegroundWindow(h)
        except Exception: pass
        time.sleep(0.4)
    return win32gui.GetForegroundWindow() == h

def is_open(h):
    return bool(win32gui.IsWindow(h))

def client_origin(h):
    """Screen coordinates of the client area's top-left corner."""
    return win32gui.ClientToScreen(h, (0, 0))

def capture(h):
    """Return BGR numpy image of the client area."""
    _, _, w, hh = win32gui.GetClientRect(h)
    hdc = win32gui.GetDC(h); mdc = win32ui.CreateDCFromHandle(hdc); sdc = mdc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap(); bmp.CreateCompatibleBitmap(mdc, w, hh); sdc.SelectObject(bmp)
    ctypes.windll.user32.PrintWindow(h, sdc.GetSafeHdc(), 3)  # PW_CLIENTONLY|PW_RENDERFULLCONTENT
    a = np.frombuffer(bmp.GetBitmapBits(True), dtype=np.uint8).reshape(hh, w, 4)[:, :, :3].copy()
    win32gui.DeleteObject(bmp.GetHandle()); sdc.DeleteDC(); mdc.DeleteDC(); win32gui.ReleaseDC(h, hdc)
    return a

# --- real mouse via SendInput ---
class _MI(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]
class _INP(ctypes.Structure):
    class _U(ctypes.Union): _fields_ = [('mi', _MI), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('u',); _fields_ = [('type', wintypes.DWORD), ('u', _U)]
_MOVE, _LDOWN, _LUP = 0x1, 0x2, 0x4

def _send(flags):
    i = _INP(type=0); i.mi = _MI(0, 0, 0, flags, 0, None)
    ctypes.windll.user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))

def cursor():
    return win32gui.GetCursorPos()

def move(x, y):
    ctypes.windll.user32.SetCursorPos(int(x), int(y)); _send(_MOVE)

def down(): _send(_LDOWN)
def up(): _send(_LUP)

# --- gestures in client coordinates; they focus the game and put the cursor back afterwards ---
def wait_for_idle_mouse(quiet=0.75):
    """Don't grab the mouse while the user is moving it."""
    last, t = cursor(), time.time()
    while time.time() - t < quiet:
        time.sleep(0.25); p = cursor()
        if p != last: last, t = p, time.time()

def in_corner():
    """Kill switch: cursor pushed into a screen corner."""
    W, H = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    return cursor() in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]

def click(h, x, y):
    home = cursor()
    if not focus(h): return False
    X, Y = client_origin(h)
    move(X + x, Y + y); time.sleep(0.15); down(); time.sleep(0.1); up(); time.sleep(0.05)
    move(*home)
    return True

def drag(h, x0, y0, x1, y1, steps=20):
    home = cursor()
    if not focus(h): return False
    X, Y = client_origin(h)
    move(X + x0, Y + y0); time.sleep(0.1); down(); time.sleep(0.15)
    for k in range(1, steps + 1):
        move(X + x0 + (x1 - x0) * k / steps, Y + y0 + (y1 - y0) * k / steps); time.sleep(0.02)
    time.sleep(0.2); up(); time.sleep(0.05)
    move(*home)
    return True
