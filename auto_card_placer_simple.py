import cv2
import numpy as np
import pyautogui
import os
import time
from PIL import Image, ImageEnhance, ImageFilter, ImageTk
import tkinter as tk
from tkinter import messagebox, simpledialog
import threading
import pygetwindow as gw
import pytesseract
import re

# Configure pyautogui for non-admin operation
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

# Configure Tesseract path - try multiple common installation paths
tesseract_paths = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    r'C:\Users\GillV\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
    'tesseract'
]

tesseract_found = False
for path in tesseract_paths:
    try:
        pytesseract.pytesseract.tesseract_cmd = path
        pytesseract.get_tesseract_version()
        print(f"Tesseract found at: {path}")
        tesseract_found = True
        break
    except:
        continue

if not tesseract_found:
    print("WARNING: Tesseract not found. Install from: https://github.com/tesseract-ocr/tesseract")

# --- CONFIGURATION ---
priorities = {
    "ArcherQueen.jpg": 1,
    "Archers.jpg": 5,
    "Bandit.jpg": 3,
    "Barbarians.jpg": 3,
    "Bomber.jpg": 5,
    "DartGoblin.jpg": 3,
    "Executioner.jpg": 4,
    "GiantSkeleton.jpg": 4,
    "GoblinMachine.jpg": 2,
    "Goblins.jpg": 1,
    "GoldenKnight.jpg": 1,
    "Knight.jpg": 2,
    "MegaKnight.jpg": 3,
    "PEKKA.jpg": 3,
    "Prince.jpg": 3,
    "Princess.jpg": 2,
    "RoyalGhost.jpg": 1,
    "SkeletonKing.jpg": 1,
    "SpearGoblins.jpg": 3,
    "Valkyrie.jpg": 5,
}
confidence_threshold = 0.8

# Card metadata: elixir cost for each card
card_data = {
    "Knight.jpg": {"elixir": 3, "class": "tank"},
    "Archers.jpg": {"elixir": 3, "class": "ranged"},
    "SpearGoblins.jpg": {"elixir": 2, "class": "ranged"},
    "GoblinMachine.jpg": {"elixir": 2, "class": "tank"},
    "Bomber.jpg": {"elixir": 3, "class": "splash"},
    "Barbarians.jpg": {"elixir": 5, "class": "swarm"},
    "Valkyrie.jpg": {"elixir": 4, "class": "splash"},
    "PEKKA.jpg": {"elixir": 7, "class": "tank"},
    "Prince.jpg": {"elixir": 5, "class": "charge"},
    "GiantSkeleton.jpg": {"elixir": 6, "class": "tank"},
    "DartGoblin.jpg": {"elixir": 3, "class": "ranged"},
    "Executioner.jpg": {"elixir": 5, "class": "splash"},
    "Princess.jpg": {"elixir": 3, "class": "ranged"},
    "MegaKnight.jpg": {"elixir": 7, "class": "tank"},
    "RoyalGhost.jpg": {"elixir": 3, "class": "assassin"},
    "Bandit.jpg": {"elixir": 3, "class": "assassin"},
    "Goblins.jpg": {"elixir": 2, "class": "swarm"},
    "SkeletonKing.jpg": {"elixir": 4, "class": "tank"},
    "GoldenKnight.jpg": {"elixir": 4, "class": "champion"},
    "ArcherQueen.jpg": {"elixir": 5, "class": "ranged"},
}

# --- GLOBAL VARIABLES ---
stop_event = threading.Event()
selected_window = None
mouse_control_active = False
calibrated_elixir_roi = None  # x, y, w, h within window for elixir
calibrated_cards_roi = None    # x, y, w, h within window for cards area

# --- ELIXIR DETECTION HELPERS ---
def preprocess_elixir_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((2,2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    return thresh

# OCR-based detection
def enhanced_ocr_detection(img):
    proc = preprocess_elixir_image(img)
    text = pytesseract.image_to_string(proc, config='--psm 7 digits')
    digits = re.findall(r"\d+", text)
    if digits:
        try:
            val = int(digits[0])
            return min(max(val, 0), 10)
        except:
            pass
    # fallback to color detection
    return detect_elixir_from_color(img)

# Color threshold-based detection (detect circle fill)
def detect_elixir_from_color(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # assume elixir bar is blue/purple
    lower = np.array([120,50,50])
    upper = np.array([160,255,255])
    mask = cv2.inRange(hsv, lower, upper)
    ratio = cv2.countNonZero(mask) / (img.shape[0]*img.shape[1])
    est = int(ratio * 10 + 0.5)
    return min(max(est, 0), 10)

# Manual input fallback
def get_manual_elixir_input():
    val = simpledialog.askinteger("Manual Elixir", "Enter current elixir (0-10):", minvalue=0, maxvalue=10)
    return val if val is not None else 5

# Combined wrapper
def get_current_elixir():
    if not selected_window:
        return 5
    left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
    if calibrated_elixir_roi:
        x,y,w,h = calibrated_elixir_roi
    else:
        # default ROI near bottom-left
        w,h = 100, 100
        x,y = width - w - 20, height - h - 20
    screenshot = pyautogui.screenshot(region=(left+x, top+y, w, h))
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    try:
        return enhanced_ocr_detection(img)
    except Exception as e:
        print(f"Elixir OCR failed: {e}")
        return get_manual_elixir_input()

# --- CALIBRATION ROUTINES ---
# Elixir ROI calibration

def visual_calibrate_elixir():
    global calibrated_elixir_roi
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    img = ImageTk.PhotoImage(screenshot)
    win = tk.Toplevel(root)
    win.title("Select Elixir ROI")
    canvas = tk.Canvas(win, width=width, height=height, cursor="cross")
    canvas.pack()
    canvas.create_image(0,0,anchor=tk.NW, image=img)
    coords = [0,0]
    rect = None
    def on_down(e):
        nonlocal rect
        coords[0], coords[1] = e.x, e.y
        if rect: canvas.delete(rect)
        rect = canvas.create_rectangle(e.x,e.y,e.x,e.y, outline='red', width=2)
    def on_drag(e):
        canvas.coords(rect, coords[0], coords[1], e.x, e.y)
    def on_up(e):
        x0,y0 = coords
        x1,y1 = e.x, e.y
        x, y = min(x0,x1), min(y0,y1)
        w, h = abs(x1-x0), abs(y1-y0)
        if w<10 or h<10:
            messagebox.showerror("Error", "Select a larger area!")
            return
        calibrated_elixir_roi = (x, y, w, h)
        print(f"Elixir ROI = {calibrated_elixir_roi}")
        win.destroy()
    canvas.bind("<Button-1>", on_down)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_up)
    win.image = img

# Card ROI calibration

def visual_calibrate_cards():
    global calibrated_cards_roi
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    img = ImageTk.PhotoImage(screenshot)
    win = tk.Toplevel(root)
    win.title("Select Card ROI")
    canvas = tk.Canvas(win, width=width, height=height, cursor="cross")
    canvas.pack()
    canvas.create_image(0,0,anchor=tk.NW, image=img)
    coords = [0,0]
    rect = None
    def on_down(e):
        nonlocal rect
        coords[0], coords[1] = e.x, e.y
        if rect: canvas.delete(rect)
        rect = canvas.create_rectangle(e.x,e.y,e.x,e.y, outline='red', width=2)
    def on_drag(e):
        canvas.coords(rect, coords[0], coords[1], e.x, e.y)
    def on_up(e):
        x0,y0 = coords
        x1,y1 = e.x, e.y
        x, y = min(x0,x1), min(y0,y1)
        w, h = abs(x1-x0), abs(y1-y0)
        if w<10 or h<10:
            messagebox.showerror("Error", "Select a larger area!")
            return
        calibrated_cards_roi = (x, y, w, h)
        print(f"Cards ROI = {calibrated_cards_roi}")
        win.destroy()
    canvas.bind("<Button-1>", on_down)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_up)
    win.image = img

# --- CARD MATCHING ---
def find_playable_cards(current_elixir):
    cards = [(name,data['elixir']) for name,data in card_data.items() if data['elixir'] <= current_elixir]
    cards.sort(key=lambda x: priorities.get(x[0], 999))
    return cards

# Template matching within ROI

def match_templates(region_img, card_list):
    matches = []
    for name, cost in card_list:
        if not os.path.exists(name): continue
        tpl = cv2.imread(name)
        res = cv2.matchTemplate(region_img, tpl, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxl = cv2.minMaxLoc(res)
        if maxv >= confidence_threshold:
            matches.append((name, maxv, maxl, cost))
    return matches

# --- MOUSE CONTROL & CLICKING ---
def take_mouse_control():
    global mouse_control_active
    mouse_control_active = True
    control_label.config(text="Mouse Control: ENABLED", fg="green")

def release_mouse_control():
    global mouse_control_active
    mouse_control_active = False
    control_label.config(text="Mouse Control: DISABLED", fg="red")

# Click based on ROI offsets

def click_card(pos):
    if not mouse_control_active or not selected_window:
        return False
    ox, oy = selected_window.left, selected_window.top
    if calibrated_cards_roi:
        cx, cy, _, _ = calibrated_cards_roi
        ox += cx; oy += cy
    abs_x = ox + pos[0]
    abs_y = oy + pos[1]
    selected_window.activate(); time.sleep(0.2)
    pyautogui.click(abs_x, abs_y)
    print(f"Clicked at ({abs_x},{abs_y})")
    return True

# --- AUTOMATION THREAD ---
def automation_thread():
    print("=== AUTOMATION STARTED ===")
    while not stop_event.is_set():
        el = get_current_elixir()
        playable = find_playable_cards(el)
        if not playable:
            time.sleep(1)
            continue
        left, top = selected_window.left, selected_window.top
        if calibrated_cards_roi:
            cx, cy, w, h = calibrated_cards_roi
            region = (left+cx, top+cy, w, h)
        else:
            region = (left, top, selected_window.width, selected_window.height)
        shot = cv2.cvtColor(np.array(pyautogui.screenshot(region=region)), cv2.COLOR_RGB2BGR)
        matches = match_templates(shot, playable)
        if matches:
            best = max(matches, key=lambda x: x[1])
            click_card(best[2])
            time.sleep(1)
        time.sleep(2)
    print("=== AUTOMATION STOPPED ===")

# --- GUI SETUP ---
root = tk.Tk()
root.title("Card Placer")
root.geometry("700x600")

# Window selection
def refresh_windows():
    window_listbox.delete(0, tk.END)
    for title in gw.getAllTitles():
        if title.strip(): window_listbox.insert(tk.END, title)

def select_window():
    global selected_window
    sel = window_listbox.curselection()
    if sel:
        title = window_listbox.get(sel[0])
        selected_window = gw.getWindowsWithTitle(title)[0]
        messagebox.showinfo("Selected", selected_window.title)

window_frame = tk.LabelFrame(root, text="Window Selection")
window_frame.pack(fill="x", padx=10, pady=5)
window_listbox = tk.Listbox(window_frame, height=4)
window_listbox.pack(fill="x", pady=5)
btn_frame = tk.Frame(window_frame)
tk.Button(btn_frame, text="Refresh", command=refresh_windows).pack(side="left")
tk.Button(btn_frame, text="Select", command=select_window).pack(side="left")
btn_frame.pack()
refresh_windows()

# Mouse control
def setup_control_panel():
    frame = tk.LabelFrame(root, text="Mouse Control")
    frame.pack(fill="x", padx=10, pady=5)
    global control_label
    control_label = tk.Label(frame, text="Mouse Control: DISABLED", fg="red")
    control_label.pack()
    btns = tk.Frame(frame)
    tk.Button(btns, text="Take Control", command=take_mouse_control).pack(side="left")
    tk.Button(btns, text="Release Control", command=release_mouse_control).pack(side="left")
    btns.pack()
setup_control_panel()

# Calibration panel
def setup_calibration_panel():
    frame = tk.LabelFrame(root, text="Calibration")
    frame.pack(fill="x", padx=10, pady=5)
    btns = tk.Frame(frame)
    tk.Button(btns, text="Calibrate Elixir ROI", command=visual_calibrate_elixir, bg="orange").pack(side="left", padx=5)
    tk.Button(btns, text="Test Elixir", command=lambda: messagebox.showinfo("Elixir", get_current_elixir()), bg="blue").pack(side="left", padx=5)
    tk.Button(btns, text="Calibrate Card ROI", command=visual_calibrate_cards, bg="purple").pack(side="left", padx=5)
    btns.pack()
setup_calibration_panel()

# Automation controls
def setup_automation_panel():
    frame = tk.LabelFrame(root, text="Automation")
    frame.pack(fill="x", padx=10, pady=5)
    btns = tk.Frame(frame)
    tk.Button(btns, text="Start", command=lambda: threading.Thread(target=automation_thread, daemon=True).start(), bg="green").pack(side="left", padx=5)
    tk.Button(btns, text="Stop", command=lambda: stop_event.set(), bg="red").pack(side="left", padx=5)
    btns.pack()
setup_automation_panel()

root.bind('<Escape>', lambda e: stop_event.set())
print("=== Card Placer Ready ===")
root.mainloop()
