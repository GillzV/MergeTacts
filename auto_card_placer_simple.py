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
pyautogui.FAILSAFE = True  # Re-enable failsafe for safety
pyautogui.PAUSE = 0.1  # Slower but more reliable

# Configure Tesseract path - try multiple common installation paths
tesseract_paths = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    r'C:\Users\GillV\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
    'tesseract'  # If it's in PATH
]

tesseract_found = False
for path in tesseract_paths:
    if os.path.exists(path) or path == 'tesseract':
        try:
            pytesseract.pytesseract.tesseract_cmd = path
            # Test if it works
            pytesseract.get_tesseract_version()
            tesseract_found = True
            print(f"Tesseract found at: {path}")
            break
        except:
            continue

if not tesseract_found:
    print("WARNING: Tesseract not found. Elixir detection will use default values.")
    print("To install Tesseract: https://github.com/tesseract-ocr/tesseract")

# --- CONFIGURATION ---
# Priority dictionary: lower number = higher priority
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
confidence_threshold = 0.8  # Adjust as needed

# Card metadata: fill in elixir cost and class for each card image
card_data = {
    # The following are placeholders for you to edit:
    "Knight.jpg": {"elixir": 2, "class": "tank,champion"},
    "Archers.jpg": {"elixir": 2, "class": "ranged,clan"},
    "SpearGoblins.jpg": {"elixir": 2, "class": "thrower,goblin"},
    "GoblinMachine.jpg": {"elixir": 2, "class": "tank,goblin"},
    "Bomber.jpg": {"elixir": 2, "class": "skeleton,thrower"},
    "Barbarians.jpg": {"elixir": 2, "class": "clan,brawler"},
    "Valkyrie.jpg": {"elixir": 3, "class": "clan,avenger"},
    "PEKKA.jpg": {"elixir": 3, "class": "tank,assassin"},
    "Prince.jpg": {"elixir": 3, "class": "champion,brawler"},
    "GiantSkeleton.jpg": {"elixir": 3, "class": "skeleton,brawler"},
    "DartGoblin.jpg": {"elixir": 3, "class": "ranged,goblin"},
    "Executioner.jpg": {"elixir": 3, "class": "thrower,assassin"},
    "Princess.jpg": {"elixir": 4, "class": "ranged,champion"},
    "MegaKnight.jpg": {"elixir": 4, "class": "brawler,assassin"},
    "RoyalGhost.jpg": {"elixir": 4, "class": "skeleton,assassin"},
    "Bandit.jpg": {"elixir": 4, "class": "assassin,avenger"},
    "Goblins.jpg": {"elixir": 2, "class": "goblin"},
    "SkeletonKing.jpg": {"elixir": 5, "class": "skeleton"},
    "GoldenKnight.jpg": {"elixir": 5, "class": "champion,assassin"},
    "ArcherQueen.jpg": {"elixir": 5, "class": "clan,avenger"},
}

# List of grid slot coordinates RELATIVE to the selected region
# Example: [(100, 400), (200, 400), ...] means 100px right, 400px down from region's top-left
grid_slots_relative = [
    (145, 800),  # Slot 1
    (145, 650),  # Slot 2
    (245, 650),  # Slot 3
    (345, 650),  # Slot 4
    (445, 650),  # Slot 5
    (545, 650),  # Slot 6
    (445, 800),  # Slot 7
]

# --- STOP EVENT AND WINDOW SELECTION ---
stop_event = threading.Event()
selected_window = None
mouse_control_active = False

# --- GLOBAL ROI VARIABLE ---
calibrated_elixir_roi = None

# --- SIMPLIFIED OCR FUNCTIONS ---
def simple_ocr_detection(img):
    """Simple OCR detection using only Tesseract"""
    if not tesseract_found:
        return 0
    
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Try OCR with different configurations
        configs = [
            '--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789',
            '--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789',
            '--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789',
        ]
        
        for config in configs:
            try:
                text = pytesseract.image_to_string(thresh, config=config)
                digits = re.findall(r'\d+', text)
                if digits:
                    number = int(digits[0])
                    if 0 <= number <= 10:
                        print(f"Tesseract detected: {number}")
                        return number
            except:
                continue
        
        return 0
    except Exception as e:
        print(f"OCR detection failed: {e}")
        return 0

def extract_number_from_text(text):
    """Extract number from OCR text using multiple methods"""
    if not text:
        return 0
    
    # Method 1: Direct digit extraction
    digits = re.findall(r'\d+', text)
    if digits:
        number = int(digits[0])
        if 0 <= number <= 10:
            return number
    
    # Method 2: Look for common number words
    number_words = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    
    text_lower = text.lower().strip()
    for word, num in number_words.items():
        if word in text_lower:
            return num
    
    # Method 3: Look for single characters that might be misread
    text_clean = re.sub(r'[^0-9]', '', text)
    if text_clean:
        try:
            number = int(text_clean)
            if 0 <= number <= 10:
                return number
        except:
            pass
    
    return 0

def take_mouse_control():
    """Take control of the mouse with non-admin methods"""
    global mouse_control_active
    mouse_control_active = True
    
    # Use safer PyAutoGUI settings
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    
    print("=== SAFE MOUSE CONTROL ACTIVATED ===")
    print("Script now has limited control of your mouse")
    print("Move mouse to corner to stop (failsafe enabled)")
    control_label.config(text="Mouse Control: ENABLED (Safe)", fg="orange")
    
    # Test mouse control immediately
    test_mouse_control()

def release_mouse_control():
    """Release mouse control"""
    global mouse_control_active
    mouse_control_active = False
    print("Mouse control released")
    control_label.config(text="Mouse Control: DISABLED", fg="red")

def test_mouse_control():
    """Test if mouse control is working with enhanced feedback"""
    if mouse_control_active:
        current_pos = pyautogui.position()
        print(f"Current mouse position: {current_pos}")
        
        # Test movement with longer delays
        print("Testing mouse movement...")
        pyautogui.moveRel(10, 0, duration=0.2)
        time.sleep(0.2)
        pyautogui.moveRel(-10, 0, duration=0.2)
        time.sleep(0.2)
        
        # Test clicking
        print("Testing mouse clicking...")
        pyautogui.click()
        time.sleep(0.3)
        
        print("Mouse control test completed successfully")

def enhanced_click_card_simple(card_screen_pos):
    """Simple card clicking without admin privileges"""
    if not mouse_control_active:
        print("ERROR: Mouse control not active!")
        return False
    
    try:
        # Debug: Check screen size and click position
        screen_size = pyautogui.size()
        print(f"Screen size: {screen_size}")
        print(f"Attempting to click card at: {card_screen_pos}")
        
        # Validate coordinates are on screen
        if (card_screen_pos[0] < 0 or card_screen_pos[0] > screen_size[0] or 
            card_screen_pos[1] < 0 or card_screen_pos[1] > screen_size[1]):
            print(f"ERROR: Click position {card_screen_pos} is off-screen!")
            return False
        
        # Ensure window is active with multiple attempts
        if selected_window:
            try:
                selected_window.restore()  # Restore if minimized
                time.sleep(0.1)
                selected_window.activate()
                time.sleep(0.3)  # Give more time for activation
                print(f"Activated window: {selected_window.title}")
            except Exception as e:
                print(f"Warning: Could not activate window: {e}")
        
        # Method 1: Direct click with longer delays
        print(f"Moving mouse to: {card_screen_pos}")
        pyautogui.moveTo(card_screen_pos[0], card_screen_pos[1], duration=0.2)
        time.sleep(0.2)
        
        # Verify mouse position
        current_pos = pyautogui.position()
        print(f"Mouse position after move: {current_pos}")
        
        # Single click with longer delay
        print("Attempting single click...")
        pyautogui.click()
        time.sleep(0.3)
        
        print(f"Click completed at: {card_screen_pos}")
        return True
        
    except Exception as e:
        print(f"ERROR in clicking: {e}")
        return False

# --- SIMPLIFIED ELIXIR DETECTION ---
def visual_calibrate_elixir():
    """Visual calibration for elixir region using Tkinter Canvas"""
    global calibrated_elixir_roi, selected_window
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    # Take screenshot
    left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    screenshot.save("roi_calibration_simple.jpg")
    screenshot_np = np.array(screenshot)
    
    # Tkinter ROI selection window
    roi_win = tk.Toplevel(root)
    roi_win.title("Select Elixir ROI")
    img = ImageTk.PhotoImage(screenshot)
    canvas = tk.Canvas(roi_win, width=img.width(), height=img.height(), cursor="cross")
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=img)
    
    roi_coords = [None, None, None, None]  # x0, y0, x1, y1
    rect = [None]
    
    def on_mouse_down(event):
        roi_coords[0] = event.x
        roi_coords[1] = event.y
        if rect[0]:
            canvas.delete(rect[0])
        rect[0] = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='orange', width=2)
    
    def on_mouse_drag(event):
        if rect[0]:
            canvas.coords(rect[0], roi_coords[0], roi_coords[1], event.x, event.y)
    
    def on_mouse_up(event):
        global calibrated_elixir_roi
        roi_coords[2] = event.x
        roi_coords[3] = event.y
        x0, y0, x1, y1 = roi_coords
        x, y = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0), abs(y1 - y0)
        if w > 0 and h > 0:
            calibrated_elixir_roi = (x, y, w, h)
            print(f"Elixir ROI calibrated: {calibrated_elixir_roi}")
            # Test the ROI
            elixir_img = pyautogui.screenshot(region=(left + x, top + y, w, h))
            elixir_img_np = np.array(elixir_img)
            elixir_img_bgr = cv2.cvtColor(elixir_img_np, cv2.COLOR_RGB2BGR)
            cv2.imwrite("test_ocr_elixir.jpg", elixir_img_bgr)
            result = simple_ocr_detection(elixir_img_bgr)
            messagebox.showinfo("ROI Saved", f"Test detected elixir: {result}\nDebug image saved as: test_ocr_elixir.jpg")
            roi_win.destroy()
        else:
            messagebox.showerror("Error", "Please select a valid region!")
    
    canvas.bind("<Button-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_drag)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    roi_win.mainloop()

# Replace manual_calibrate_elixir with visual_calibrate_elixir
manual_calibrate_elixir = visual_calibrate_elixir

def get_current_elixir_simple(region_x, region_y, region_w, region_h, elixir_roi=None):
    global calibrated_elixir_roi
    if calibrated_elixir_roi is not None:
        elixir_roi = calibrated_elixir_roi
    elif elixir_roi is None:
        print("[WARNING] No elixir ROI set. Using default region. Please use 'Set Elixir ROI' for best results.")
        elixir_roi = (region_w - 120, region_h - 120, 100, 100)
    elixir_roi = tuple(int(x) if x is not None else 0 for x in elixir_roi)
    elixir_region = (region_x + elixir_roi[0], region_y + elixir_roi[1], elixir_roi[2], elixir_roi[3])
    elixir_img = pyautogui.screenshot(region=elixir_region)
    elixir_img_np = np.array(elixir_img)
    elixir_img_bgr = cv2.cvtColor(elixir_img_np, cv2.COLOR_RGB2BGR)
    cv2.imwrite("debug_elixir_region.jpg", elixir_img_bgr)
    print(f"Saved elixir region debug image (ROI: {elixir_roi})")
    elixir_number = simple_ocr_detection(elixir_img_bgr)
    if elixir_number > 0:
        print(f"Detected elixir: {elixir_number}")
        return elixir_number
    print("Elixir detection failed, using default value 10")
    return 10

def match_elixir_number_templates(img):
    """Use template matching for common elixir numbers (1-10)"""
    try:
        # Create simple number templates (you can improve these)
        templates = {}
        for i in range(1, 11):
            # Create a simple template for each number
            template = np.zeros((30, 20), dtype=np.uint8)
            cv2.putText(template, str(i), (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 255, 2)
            templates[i] = template
        
        # Convert image to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        best_match = 0
        best_confidence = 0
        
        for number, template in templates.items():
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            if max_val > best_confidence and max_val > 0.6:
                best_confidence = max_val
                best_match = number
        
        return best_match
    except Exception as e:
        print(f"Template matching failed: {e}")
        return 0

def detect_elixir_from_bar(img):
    """Detect elixir from the elixir bar fill level"""
    try:
        # Convert to HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Look for purple/blue colors typical of elixir
        lower_purple = np.array([120, 50, 50])
        upper_purple = np.array([140, 255, 255])
        
        mask = cv2.inRange(hsv, lower_purple, upper_purple)
        
        # Count filled pixels
        filled_pixels = cv2.countNonZero(mask)
        total_pixels = mask.shape[0] * mask.shape[1]
        
        if total_pixels > 0:
            fill_percentage = filled_pixels / total_pixels
            # Estimate elixir based on fill percentage (0-10)
            estimated_elixir = int(fill_percentage * 10)
            return max(0, min(10, estimated_elixir))
        
        return 0
    except Exception as e:
        print(f"Bar detection failed: {e}")
        return 0

# --- AUTOMATION THREAD ---
def automation_thread():
    """Main automation loop with simplified features"""
    global selected_window, stop_event
    print("=== AUTOMATION THREAD STARTED ===")
    print("Press Ctrl+C or click Force Stop to stop automation")
    # Get window selection
    if not selected_window:
        print("ERROR: No window selected!")
        return
    # Get window region
    region_x = selected_window.left
    region_y = selected_window.top
    region_w = selected_window.width
    region_h = selected_window.height
    print(f"Selected window: {selected_window.title}")
    print(f"Window region: ({region_x}, {region_y}, {region_w}, {region_h})")
    # Main automation loop
    loop_count = 0
    while not stop_event.is_set():
        loop_count += 1
        print(f"\n=== LOOP {loop_count} ===")
        try:
            # Take fresh screenshot
            print("Taking fresh screenshot...")
            screenshot = pyautogui.screenshot(region=(region_x, region_y, region_w, region_h))
            screenshot_np = np.array(screenshot)
            screenshot_bgr = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            # Save debug screenshot
            cv2.imwrite(f"debug_screenshot_{loop_count}.jpg", screenshot_bgr)
            print(f"Saved debug screenshot: debug_screenshot_{loop_count}.jpg")
            # Get current elixir
            print("Detecting current elixir...")
            current_elixir = get_current_elixir_simple(region_x, region_y, region_w, region_h)
            print(f"Current elixir: {current_elixir}")
            # Find matching cards
            print("Finding matching cards...")
            matches = match_templates(screenshot_bgr, priorities, confidence_threshold)
            if matches:
                print(f"Found {len(matches)} matching cards:")
                for card_name, confidence, (x, y) in matches:
                    print(f"  - {card_name} (confidence: {confidence:.2f}) at ({x}, {y})")
            else:
                print("No matching cards found")
            print("Waiting 2 seconds before next loop...")
            time.sleep(2)
        except Exception as e:
            print(f"Error in automation loop: {e}")
            time.sleep(2)

# --- GUI FUNCTIONS ---
def get_current_elixir(region_x, region_y, region_w, region_h, elixir_roi=None):
    """Get current elixir using simple detection"""
    return get_current_elixir_simple(region_x, region_y, region_w, region_h, elixir_roi)

def detect_number_in_orb(img):
    """Detect number in elixir orb"""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold to isolate text
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Try OCR on the thresholded image
        text = pytesseract.image_to_string(thresh, config='--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789')
        
        # Extract number
        digits = re.findall(r'\d+', text)
        if digits:
            number = int(digits[0])
            if 0 <= number <= 10:
                return number
        
        return 0
    except Exception as e:
        print(f"Orb detection failed: {e}")
        return 0

def detect_number_in_region(region_img):
    """Detect number in a region using multiple methods"""
    try:
        # Method 1: Direct OCR
        text = pytesseract.image_to_string(region_img, config='--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789')
        digits = re.findall(r'\d+', text)
        if digits:
            number = int(digits[0])
            if 0 <= number <= 10:
                return number
        
        # Method 2: Template matching
        gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
        for i in range(1, 11):
            template = np.zeros((30, 20), dtype=np.uint8)
            cv2.putText(template, str(i), (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 255, 2)
            
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            if max_val > 0.7:
                return i
        
        return 0
    except Exception as e:
        print(f"Region detection failed: {e}")
        return 0

def match_templates(region_img, priorities, confidence_threshold):
    """Match card templates in the region"""
    matches = []
    
    # Get list of card images
    card_images = [f for f in os.listdir('.') if f.endswith('.jpg') and f in priorities]
    
    for card_name in card_images:
        try:
            # Load template
            template = cv2.imread(card_name)
            if template is None:
                continue
            
            # Match template
            result = cv2.matchTemplate(region_img, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= confidence_threshold:
                matches.append((card_name, max_val, max_loc))
        
        except Exception as e:
            print(f"Error matching {card_name}: {e}")
    
    # Sort by priority (lower number = higher priority)
    matches.sort(key=lambda x: priorities.get(x[0], 999))
    
    return matches

def start_automation():
    """Start the automation thread"""
    threading.Thread(target=automation_thread, daemon=True).start()

def stop_automation():
    """Stop the automation thread"""
    stop_event.set()

def visualize_grid_slots():
    """Visualize grid slots on the selected window"""
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    
    # Take screenshot
    screenshot = pyautogui.screenshot(region=(selected_window.left, selected_window.top, 
                                            selected_window.width, selected_window.height))
    screenshot_np = np.array(screenshot)
    screenshot_bgr = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
    
    # Draw grid slots
    for i, (x, y) in enumerate(grid_slots_relative):
        cv2.circle(screenshot_bgr, (x, y), 10, (0, 255, 0), 2)
        cv2.putText(screenshot_bgr, str(i+1), (x+15, y+5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    # Save visualization
    cv2.imwrite("grid_slots_visualization.jpg", screenshot_bgr)
    print("Grid slots visualization saved as: grid_slots_visualization.jpg")

def on_key_press(event):
    """Handle keyboard shortcuts"""
    if event.keysym == 'Escape':
        stop_automation()
        print("Automation stopped by Escape key")
    elif event.keysym == 'F1':
        take_mouse_control()
    elif event.keysym == 'F2':
        release_mouse_control()

def test_ocr_on_elixir():
    """Test OCR on the elixir region"""
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    
    # Get elixir region
    region_x = selected_window.left
    region_y = selected_window.top
    region_w = selected_window.width
    region_h = selected_window.height
    
    # Default elixir region (bottom right)
    elixir_region = (region_x + region_w - 120, region_y + region_h - 120, 100, 100)
    
    # Take screenshot of elixir region
    elixir_img = pyautogui.screenshot(region=elixir_region)
    elixir_img_np = np.array(elixir_img)
    elixir_img_bgr = cv2.cvtColor(elixir_img_np, cv2.COLOR_RGB2BGR)
    
    # Save debug image
    cv2.imwrite("test_ocr_elixir.jpg", elixir_img_bgr)
    
    # Test OCR
    result = simple_ocr_detection(elixir_img_bgr)
    
    messagebox.showinfo("OCR Test Result", f"Detected elixir: {result}\nDebug image saved as: test_ocr_elixir.jpg")

# --- GUI SETUP ---
root = tk.Tk()
root.title("Card Placer - Simple Version (No EasyOCR)")
root.geometry("600x500")

# Window selection
window_frame = tk.Frame(root)
window_frame.pack(pady=10)

tk.Label(window_frame, text="Select Game Window:").pack()

window_listbox = tk.Listbox(window_frame, height=5)
window_listbox.pack()

def refresh_windows():
    """Refresh the list of windows"""
    window_listbox.delete(0, tk.END)
    windows = gw.getAllTitles()
    for window in windows:
        if window:  # Skip empty titles
            window_listbox.insert(tk.END, window)

def select_window():
    """Select the highlighted window"""
    global selected_window
    selection = window_listbox.curselection()
    if selection:
        window_title = window_listbox.get(selection[0])
        selected_window = gw.getWindowsWithTitle(window_title)[0]
        print(f"Selected window: {selected_window.title}")
        messagebox.showinfo("Window Selected", f"Selected: {selected_window.title}")

refresh_windows()

tk.Button(window_frame, text="Refresh Windows", command=refresh_windows).pack()
tk.Button(window_frame, text="Select Window", command=select_window).pack()

# Control buttons
control_frame = tk.Frame(root)
control_frame.pack(pady=10)

control_label = tk.Label(control_frame, text="Mouse Control: DISABLED", fg="red")
control_label.pack()

tk.Button(control_frame, text="Take Mouse Control", command=take_mouse_control).pack()
tk.Button(control_frame, text="Release Mouse Control", command=release_mouse_control).pack()
tk.Button(control_frame, text="Test Mouse Control", command=test_mouse_control).pack()

# Automation buttons
automation_frame = tk.Frame(root)
automation_frame.pack(pady=10)

tk.Button(automation_frame, text="Start Automation", command=start_automation).pack()
tk.Button(automation_frame, text="Force Stop", command=stop_automation).pack()

# Utility buttons
utility_frame = tk.Frame(root)
utility_frame.pack(pady=10)

tk.Button(utility_frame, text="Visualize Grid Slots", command=visualize_grid_slots).pack()
tk.Button(utility_frame, text="Test OCR on Elixir", command=test_ocr_on_elixir).pack()

# Add Set Elixir ROI button to utility_frame
btn_set_elixir_roi = tk.Button(utility_frame, text="Set Elixir ROI", command=visual_calibrate_elixir, bg="orange", fg="white")
btn_set_elixir_roi.pack()

# Keyboard shortcuts
root.bind('<Escape>', on_key_press)
root.bind('<F1>', on_key_press)
root.bind('<F2>', on_key_press)

# Instructions
instructions_frame = tk.Frame(root)
instructions_frame.pack(pady=10)

instructions_text = """
SIMPLE VERSION - Instructions:
1. Select your game window
2. Take mouse control (F1)
3. Start automation
4. Press Escape or Force Stop to stop

This version uses minimal dependencies:
- No EasyOCR required
- Only Tesseract for OCR
- Safer mouse control settings

If OCR doesn't work well:
- Install Tesseract OCR
- Use manual elixir input
- Calibrate elixir region
"""

tk.Label(instructions_frame, text=instructions_text, justify=tk.LEFT).pack()

print("=== CARD PLACER - SIMPLE VERSION ===")
print("This version uses minimal dependencies and doesn't require EasyOCR")
print("If Tesseract is not installed, OCR will use manual input fallback")

root.mainloop() 