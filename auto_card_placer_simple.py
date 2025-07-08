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
    """Enhanced preprocessing for elixir detection"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Scale up for better OCR
    gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    # Apply gaussian blur to reduce noise
    gray = cv2.GaussianBlur(gray, (5,5), 0)
    # Try multiple thresholding methods
    _, thresh1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, thresh2 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    # Use morphological operations to clean up
    kernel = np.ones((3,3), np.uint8)
    thresh1 = cv2.morphologyEx(thresh1, cv2.MORPH_CLOSE, kernel)
    thresh1 = cv2.morphologyEx(thresh1, cv2.MORPH_OPEN, kernel)
    return thresh1

# OCR-based detection with better configuration
def enhanced_ocr_detection(img):
    """Enhanced OCR detection with multiple attempts"""
    processed = preprocess_elixir_image(img)
    
    # Try different OCR configurations
    ocr_configs = [
        '--psm 8 -c tessedit_char_whitelist=0123456789',
        '--psm 7 -c tessedit_char_whitelist=0123456789',
        '--psm 6 -c tessedit_char_whitelist=0123456789',
        '--psm 13 -c tessedit_char_whitelist=0123456789'
    ]
    
    for config in ocr_configs:
        try:
            text = pytesseract.image_to_string(processed, config=config)
            digits = re.findall(r"\d+", text)
            if digits:
                val = int(digits[0])
                if 0 <= val <= 10:
                    print(f"OCR detected elixir: {val} (config: {config})")
                    return val
        except Exception as e:
            print(f"OCR attempt failed with config {config}: {e}")
            continue
    
    print("OCR failed, falling back to color detection")
    return detect_elixir_from_color(img)

# Color threshold-based detection (detect circle fill)
def detect_elixir_from_color(img):
    """Detect elixir based on color analysis"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Try multiple color ranges for elixir (purple/pink range)
    color_ranges = [
        (np.array([140, 50, 50]), np.array([180, 255, 255])),  # Purple-pink
        (np.array([120, 50, 50]), np.array([160, 255, 255])),  # Blue-purple
        (np.array([280, 50, 50]), np.array([320, 255, 255])),  # Magenta
    ]
    
    max_ratio = 0
    for lower, upper in color_ranges:
        mask = cv2.inRange(hsv, lower, upper)
        ratio = cv2.countNonZero(mask) / (img.shape[0] * img.shape[1])
        max_ratio = max(max_ratio, ratio)
    
    # Convert ratio to elixir estimate
    estimated = int(max_ratio * 15 + 0.5)  # Adjusted multiplier
    result = min(max(estimated, 0), 10)
    print(f"Color detection estimated elixir: {result} (ratio: {max_ratio:.3f})")
    return result

# Manual input fallback
def get_manual_elixir_input():
    """Get manual elixir input from user"""
    val = simpledialog.askinteger("Manual Elixir", "Enter current elixir (0-10):", minvalue=0, maxvalue=10)
    return val if val is not None else 5

# Test elixir detection and show debug info
def test_elixir_detection():
    """Test elixir detection with debug information"""
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    
    try:
        # Get screenshot of elixir area
        left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
        
        if calibrated_elixir_roi:
            x, y, w, h = calibrated_elixir_roi
            print(f"Using calibrated elixir ROI: {calibrated_elixir_roi}")
        else:
            # Default ROI near bottom-right corner
            w, h = 100, 100
            x, y = width - w - 20, height - h - 20
            print(f"Using default elixir ROI: ({x}, {y}, {w}, {h})")
        
        # Take screenshot
        screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # Save debug images
        cv2.imwrite('debug_elixir_raw.png', img)
        processed = preprocess_elixir_image(img)
        cv2.imwrite('debug_elixir_processed.png', processed)
        
        # Try detection
        if tesseract_found:
            elixir = enhanced_ocr_detection(img)
        else:
            elixir = detect_elixir_from_color(img)
        
        # Show results
        message = f"Detected Elixir: {elixir}\n\n"
        message += f"ROI: ({x}, {y}, {w}, {h})\n"
        message += f"Tesseract available: {tesseract_found}\n"
        message += f"Debug images saved: debug_elixir_raw.png, debug_elixir_processed.png"
        
        messagebox.showinfo("Elixir Test Results", message)
        
    except Exception as e:
        error_msg = f"Error testing elixir detection: {str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)

# Test card ROI detection
def test_card_roi():
    """Test card ROI detection"""
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    
    try:
        left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
        
        if calibrated_cards_roi:
            x, y, w, h = calibrated_cards_roi
            print(f"Using calibrated card ROI: {calibrated_cards_roi}")
        else:
            # Default to full window
            x, y, w, h = 0, 0, width, height
            print(f"Using default card ROI (full window): ({x}, {y}, {w}, {h})")
        
        # Take screenshot of card area
        screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # Save debug image
        cv2.imwrite('debug_cards_roi.png', img)
        
        # Try to find some cards in the current elixir range
        current_elixir = get_current_elixir()
        playable_cards = find_playable_cards(current_elixir)
        
        if playable_cards:
            matches = match_templates(img, playable_cards[:5])  # Test first 5 cards
            
            message = f"Card ROI Test Results:\n\n"
            message += f"ROI: ({x}, {y}, {w}, {h})\n"
            message += f"Current Elixir: {current_elixir}\n"
            message += f"Playable Cards: {len(playable_cards)}\n"
            message += f"Matches Found: {len(matches)}\n\n"
            
            if matches:
                message += "Top matches:\n"
                for i, (name, confidence, pos, cost) in enumerate(matches[:3]):
                    message += f"{i+1}. {name.replace('.jpg', '')} (conf: {confidence:.3f})\n"
            else:
                message += "No card matches found in ROI"
            
            message += f"\nDebug image saved: debug_cards_roi.png"
            messagebox.showinfo("Card ROI Test Results", message)
        else:
            messagebox.showinfo("Card ROI Test", "No playable cards found for current elixir level")
            
    except Exception as e:
        error_msg = f"Error testing card ROI: {str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)

# Combined wrapper
def get_current_elixir():
    """Get current elixir with error handling"""
    if not selected_window:
        print("No window selected, returning default elixir")
        return 5
    
    try:
        left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
        
        if calibrated_elixir_roi:
            x, y, w, h = calibrated_elixir_roi
        else:
            # Default ROI near bottom-right corner
            w, h = 100, 100
            x, y = width - w - 20, height - h - 20
        
        screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        if tesseract_found:
            return enhanced_ocr_detection(img)
        else:
            return detect_elixir_from_color(img)
            
    except Exception as e:
        print(f"Elixir detection failed: {e}")
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
        messagebox.showinfo("Success", f"Elixir ROI calibrated: {calibrated_elixir_roi}")
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
        messagebox.showinfo("Success", f"Card ROI calibrated: {calibrated_cards_roi}")
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
        if not os.path.exists(name): 
            continue
        try:
            tpl = cv2.imread(name)
            if tpl is None:
                continue
            res = cv2.matchTemplate(region_img, tpl, cv2.TM_CCOEFF_NORMED)
            _, maxv, _, maxl = cv2.minMaxLoc(res)
            if maxv >= confidence_threshold:
                matches.append((name, maxv, maxl, cost))
        except Exception as e:
            print(f"Error matching template {name}: {e}")
            continue
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
        try:
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
        except Exception as e:
            print(f"Error in automation thread: {e}")
            time.sleep(2)
    print("=== AUTOMATION STOPPED ===")

# --- GUI SETUP ---
root = tk.Tk()
root.title("Card Placer")
root.geometry("700x650")

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
        windows = gw.getWindowsWithTitle(title)
        if windows:
            selected_window = windows[0]
            messagebox.showinfo("Selected", f"Selected: {selected_window.title}")
        else:
            messagebox.showerror("Error", "Window not found!")

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
    
    # First row of buttons
    btns1 = tk.Frame(frame)
    tk.Button(btns1, text="Calibrate Elixir ROI", command=visual_calibrate_elixir, bg="orange").pack(side="left", padx=5)
    tk.Button(btns1, text="Test Elixir", command=test_elixir_detection, bg="lightblue").pack(side="left", padx=5)
    btns1.pack(pady=2)
    
    # Second row of buttons
    btns2 = tk.Frame(frame)
    tk.Button(btns2, text="Calibrate Card ROI", command=visual_calibrate_cards, bg="purple", fg="white").pack(side="left", padx=5)
    tk.Button(btns2, text="Test Card ROI", command=test_card_roi, bg="lightgreen").pack(side="left", padx=5)
    btns2.pack(pady=2)

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

# Status display
def setup_status_panel():
    frame = tk.LabelFrame(root, text="Status")
    frame.pack(fill="x", padx=10, pady=5)
    status_text = tk.Text(frame, height=8, width=80)
    status_text.pack(fill="both", expand=True)
    status_text.insert(tk.END, "=== Card Placer Ready ===\n")
    status_text.insert(tk.END, "1. Select a window\n")
    status_text.insert(tk.END, "2. Calibrate elixir ROI and test\n")
    status_text.insert(tk.END, "3. Calibrate card ROI and test\n")
    status_text.insert(tk.END, "4. Take mouse control\n")
    status_text.insert(tk.END, "5. Start automation\n")
    status_text.config(state=tk.DISABLED)

setup_status_panel()

root.bind('<Escape>', lambda e: stop_event.set())
print("=== Card Placer Ready ===")
root.mainloop()