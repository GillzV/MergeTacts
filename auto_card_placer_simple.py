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
# Adjusted confidence threshold for better matching
confidence_threshold = 0.7

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
# Load reference elixir images
def load_elixir_references():
    """Load reference elixir images for template matching"""
    references = {}
    elixir_dir = "Screenshots/Elixir"
    
    for i in range(10):  # 0-9
        filename = f"{i}E.png"
        filepath = os.path.join(elixir_dir, filename)
        if os.path.exists(filepath):
            img = cv2.imread(filepath)
            if img is not None:
                references[i] = img
                print(f"Loaded elixir reference: {filename}")
            else:
                print(f"Failed to load: {filepath}")
        else:
            print(f"Missing reference: {filepath}")
    
    return references

# Global variable to store elixir references
elixir_references = load_elixir_references()

def preprocess_elixir_image(img):
    """Preprocess elixir image for template matching"""
    # Convert to grayscale for better matching
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply some preprocessing to improve matching
    # Normalize brightness and contrast
    gray = cv2.equalizeHist(gray)
    
    # Apply slight blur to reduce noise
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    
    return gray

# Template matching-based elixir detection
def detect_elixir_from_templates(img):
    """Detect elixir using template matching with reference images"""
    if not elixir_references:
        print("No elixir references loaded, falling back to color detection")
        return detect_elixir_from_color(img)
    
    processed_img = preprocess_elixir_image(img)
    
    best_match = None
    best_confidence = 0
    best_elixir = 0
    
    # Try matching against each reference image
    for elixir_count, reference_img in elixir_references.items():
        try:
            # Preprocess reference image the same way
            processed_ref = preprocess_elixir_image(reference_img)
            
            # Multi-scale template matching
            max_confidence = 0
            for scale in np.linspace(0.5, 1.5, 20):  # Try different scales
                # Resize reference image
                h, w = processed_ref.shape
                new_h, new_w = int(h * scale), int(w * scale)
                
                if new_h > processed_img.shape[0] or new_w > processed_img.shape[1]:
                    continue
                
                resized_ref = cv2.resize(processed_ref, (new_w, new_h))
                
                # Template matching
                result = cv2.matchTemplate(processed_img, resized_ref, cv2.TM_CCOEFF_NORMED)
                _, confidence, _, _ = cv2.minMaxLoc(result)
                
                max_confidence = max(max_confidence, confidence)
            
            # Update best match if this one is better
            if max_confidence > best_confidence:
                best_confidence = max_confidence
                best_elixir = elixir_count
                best_match = max_confidence
                
        except Exception as e:
            print(f"Error matching elixir {elixir_count}: {e}")
            continue
    
    # If we found a good match, return the elixir count
    if best_match and best_confidence > 0.6:  # Adjust threshold as needed
        print(f"Template matching detected elixir: {best_elixir} (confidence: {best_confidence:.3f})")
        return best_elixir
    else:
        print(f"No good template match found (best: {best_elixir} with confidence {best_confidence:.3f})")
        # If no good match found, assume 10+ elixir
        return 10

# Enhanced OCR detection (kept as fallback)
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
    
    print("OCR failed, falling back to template matching")
    return detect_elixir_from_templates(img)

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

# Scrollable message box for long results
def show_scrollable_message(title, message):
    """Show a scrollable message box for long content"""
    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("600x400")
    
    # Create main frame
    main_frame = tk.Frame(win)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Create text widget with scrollbar
    text_frame = tk.Frame(main_frame)
    text_frame.pack(fill="both", expand=True)
    
    text_scrollbar = tk.Scrollbar(text_frame)
    text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=text_scrollbar.set)
    
    text_scrollbar.config(command=text_widget.yview)
    text_scrollbar.pack(side="right", fill="y")
    text_widget.pack(side="left", fill="both", expand=True)
    
    # Insert message
    text_widget.insert(tk.END, message)
    text_widget.config(state=tk.DISABLED)
    
    # Add close button
    close_btn = tk.Button(main_frame, text="Close", command=win.destroy)
    close_btn.pack(pady=5)

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
        if elixir_references:
            elixir = detect_elixir_from_templates(img)
            detection_method = "Template Matching"
        elif tesseract_found:
            elixir = enhanced_ocr_detection(img)
            detection_method = "OCR"
        else:
            elixir = detect_elixir_from_color(img)
            detection_method = "Color Detection"
        
        # Show results
        message = f"Detected Elixir: {elixir}\n"
        message += f"Detection Method: {detection_method}\n\n"
        message += f"ROI: ({x}, {y}, {w}, {h})\n"
        message += f"Reference Images Loaded: {len(elixir_references)}/10\n"
        message += f"Tesseract available: {tesseract_found}\n"
        message += f"Debug images saved: debug_elixir_raw.png, debug_elixir_processed.png"
        
        show_scrollable_message("Elixir Test Results", message)
        
    except Exception as e:
        error_msg = f"Error testing elixir detection: {str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)

# Test template matching with reference images
def test_template_matching():
    """Test template matching against all reference images"""
    if not elixir_references:
        messagebox.showwarning("Warning", "No elixir reference images loaded!")
        return
    
    try:
        # Get screenshot of elixir area
        if not selected_window:
            messagebox.showwarning("Warning", "Please select a window first!")
            return
            
        left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
        
        if calibrated_elixir_roi:
            x, y, w, h = calibrated_elixir_roi
        else:
            w, h = 100, 100
            x, y = width - w - 20, height - h - 20
        
        screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # Test against each reference
        results = []
        for elixir_count, reference_img in elixir_references.items():
            try:
                processed_img = preprocess_elixir_image(img)
                processed_ref = preprocess_elixir_image(reference_img)
                
                max_confidence = 0
                for scale in np.linspace(0.5, 1.5, 10):
                    h, w = processed_ref.shape
                    new_h, new_w = int(h * scale), int(w * scale)
                    
                    if new_h > processed_img.shape[0] or new_w > processed_img.shape[1]:
                        continue
                    
                    resized_ref = cv2.resize(processed_ref, (new_w, new_h))
                    result = cv2.matchTemplate(processed_img, resized_ref, cv2.TM_CCOEFF_NORMED)
                    _, confidence, _, _ = cv2.minMaxLoc(result)
                    max_confidence = max(max_confidence, confidence)
                
                results.append((elixir_count, max_confidence))
                
            except Exception as e:
                print(f"Error testing elixir {elixir_count}: {e}")
                results.append((elixir_count, 0))
        
        # Sort by confidence
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Build results message
        message = "Template Matching Test Results:\n\n"
        message += f"Current ROI: ({x}, {y}, {w}, {h})\n\n"
        message += "Confidence scores:\n"
        for elixir_count, confidence in results:
            message += f"{elixir_count}E: {confidence:.3f}\n"
        
        best_match = results[0]
        message += f"\nBest match: {best_match[0]}E (confidence: {best_match[1]:.3f})"
        
        if best_match[1] > 0.6:
            message += "\n✓ Good match found!"
        else:
            message += "\n✗ No good match - assuming 10+ elixir"
        
        show_scrollable_message("Template Matching Test", message)
        
    except Exception as e:
        error_msg = f"Error testing template matching: {str(e)}"
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
            show_scrollable_message("Card ROI Test Results", message)
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
        
        # Try template matching first (most reliable with reference images)
        if elixir_references:
            return detect_elixir_from_templates(img)
        elif tesseract_found:
            return enhanced_ocr_detection(img)
        else:
            return detect_elixir_from_color(img)
            
    except Exception as e:
        print(f"Elixir detection failed: {e}")
        return get_manual_elixir_input()

# --- CALIBRATION ROUTINES ---
# Elixir ROI calibration with live template matching feedback
def visual_calibrate_elixir():
    global calibrated_elixir_roi
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    
    left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    img = ImageTk.PhotoImage(screenshot)
    
    win = tk.Toplevel(root)
    win.title("Select Elixir ROI - Live Template Matching")
    win.geometry("1000x700")
    
    # Create main frame with scrollbar support
    main_frame = tk.Frame(win)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Left side - canvas for selection with scrollbars
    canvas_frame = tk.Frame(main_frame)
    canvas_frame.pack(side="left", fill="both", expand=True)
    
    # Create canvas with scrollbars
    canvas_container = tk.Frame(canvas_frame)
    canvas_container.pack(fill="both", expand=True)
    
    # Create scrollbars
    h_scrollbar = tk.Scrollbar(canvas_container, orient="horizontal")
    v_scrollbar = tk.Scrollbar(canvas_container, orient="vertical")
    
    # Create canvas with scrollbars
    canvas = tk.Canvas(canvas_container, 
                      width=min(width, 600), 
                      height=min(height, 500),
                      cursor="cross",
                      xscrollcommand=h_scrollbar.set,
                      yscrollcommand=v_scrollbar.set)
    
    # Configure scrollbars
    h_scrollbar.config(command=canvas.xview)
    v_scrollbar.config(command=canvas.yview)
    
    # Pack scrollbars and canvas
    h_scrollbar.pack(side="bottom", fill="x")
    v_scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    
    # Add image to canvas
    canvas.create_image(0, 0, anchor=tk.NW, image=img)
    canvas.config(scrollregion=canvas.bbox("all"))
    
    # Right side - feedback panel with scrollbar
    feedback_frame = tk.Frame(main_frame)
    feedback_frame.pack(side="right", fill="y", padx=(10, 0))
    
    # Feedback labels
    tk.Label(feedback_frame, text="Template Matching Results:", font=("Arial", 12, "bold")).pack(anchor="w")
    
    status_label = tk.Label(feedback_frame, text="Select an area to test template matching", fg="blue")
    status_label.pack(anchor="w", pady=5)
    
    # Create text widget with scrollbar
    text_frame = tk.Frame(feedback_frame)
    text_frame.pack(fill="y", expand=True)
    
    text_scrollbar = tk.Scrollbar(text_frame)
    results_text = tk.Text(text_frame, width=35, height=20, font=("Courier", 9),
                          yscrollcommand=text_scrollbar.set)
    
    text_scrollbar.config(command=results_text.yview)
    text_scrollbar.pack(side="right", fill="y")
    results_text.pack(side="left", fill="y", expand=True)
    
    coords = [0,0]
    rect = None
    
    def update_template_matching(x, y, w, h):
        """Update template matching results for the selected area"""
        try:
            # Take screenshot of the selected area
            screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
            img_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # Test against reference images
            if not elixir_references:
                status_label.config(text="No reference images loaded!", fg="red")
                return
            
            results = []
            for elixir_count, reference_img in elixir_references.items():
                try:
                    processed_img = preprocess_elixir_image(img_cv)
                    processed_ref = preprocess_elixir_image(reference_img)
                    
                    max_confidence = 0
                    for scale in np.linspace(0.5, 1.5, 10):
                        h_ref, w_ref = processed_ref.shape
                        new_h, new_w = int(h_ref * scale), int(w_ref * scale)
                        
                        if new_h > processed_img.shape[0] or new_w > processed_img.shape[1]:
                            continue
                        
                        resized_ref = cv2.resize(processed_ref, (new_w, new_h))
                        result = cv2.matchTemplate(processed_img, resized_ref, cv2.TM_CCOEFF_NORMED)
                        _, confidence, _, _ = cv2.minMaxLoc(result)
                        max_confidence = max(max_confidence, confidence)
                    
                    results.append((elixir_count, max_confidence))
                    
                except Exception as e:
                    results.append((elixir_count, 0))
            
            # Sort by confidence
            results.sort(key=lambda x: x[1], reverse=True)
            
            # Update display
            results_text.delete(1.0, tk.END)
            results_text.insert(tk.END, f"ROI: ({x}, {y}, {w}, {h})\n\n")
            results_text.insert(tk.END, "Confidence scores:\n")
            results_text.insert(tk.END, "-" * 30 + "\n")
            
            for elixir_count, confidence in results:
                color_tag = "good" if confidence > 0.6 else "poor"
                results_text.insert(tk.END, f"{elixir_count}E: {confidence:.3f}\n")
            
            best_match = results[0]
            if best_match[1] > 0.6:
                status_label.config(text=f"✓ Good match: {best_match[0]}E ({best_match[1]:.3f})", fg="green")
            else:
                status_label.config(text=f"✗ Poor match: {best_match[0]}E ({best_match[1]:.3f})", fg="red")
                
        except Exception as e:
            status_label.config(text=f"Error: {str(e)}", fg="red")
            results_text.delete(1.0, tk.END)
            results_text.insert(tk.END, f"Error testing template matching:\n{str(e)}")
    
    def on_down(e):
        nonlocal rect
        coords[0], coords[1] = e.x, e.y
        if rect: canvas.delete(rect)
        rect = canvas.create_rectangle(e.x,e.y,e.x,e.y, outline='red', width=2)
        status_label.config(text="Drag to select area...", fg="blue")
    
    def on_drag(e):
        canvas.coords(rect, coords[0], coords[1], e.x, e.y)
        
        # Update template matching in real-time
        x0, y0 = coords
        x1, y1 = e.x, e.y
        x, y = min(x0,x1), min(y0,y1)
        w, h = abs(x1-x0), abs(y1-y0)
        
        if w > 10 and h > 10:
            update_template_matching(x, y, w, h)
    
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
        
        # Final template matching test
        update_template_matching(x, y, w, h)
        
        # Show final results
        final_message = f"Elixir ROI calibrated: {calibrated_elixir_roi}\n\n"
        final_message += "Template matching results:\n"
        
        try:
            screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
            img_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            if elixir_references:
                results = []
                for elixir_count, reference_img in elixir_references.items():
                    try:
                        processed_img = preprocess_elixir_image(img_cv)
                        processed_ref = preprocess_elixir_image(reference_img)
                        
                        max_confidence = 0
                        for scale in np.linspace(0.5, 1.5, 10):
                            h_ref, w_ref = processed_ref.shape
                            new_h, new_w = int(h_ref * scale), int(w_ref * scale)
                            
                            if new_h > processed_img.shape[0] or new_w > processed_img.shape[1]:
                                continue
                            
                            resized_ref = cv2.resize(processed_ref, (new_w, new_h))
                            result = cv2.matchTemplate(processed_img, resized_ref, cv2.TM_CCOEFF_NORMED)
                            _, confidence, _, _ = cv2.minMaxLoc(result)
                            max_confidence = max(max_confidence, confidence)
                        
                        results.append((elixir_count, max_confidence))
                        
                    except Exception as e:
                        results.append((elixir_count, 0))
                
                results.sort(key=lambda x: x[1], reverse=True)
                best_match = results[0]
                
                final_message += f"Best match: {best_match[0]}E (confidence: {best_match[1]:.3f})\n"
                if best_match[1] > 0.6:
                    final_message += "✓ Good match found!"
                else:
                    final_message += "✗ Poor match - consider adjusting ROI"
            
        except Exception as e:
            final_message += f"Error testing: {str(e)}"
        
        messagebox.showinfo("Calibration Complete", final_message)
        win.destroy()
    
    canvas.bind("<Button-1>", on_down)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_up)
    win.image = img

# Card ROI calibration with scrolling
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
    win.geometry("800x600")
    
    # Create main frame
    main_frame = tk.Frame(win)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Create canvas with scrollbars
    canvas_container = tk.Frame(main_frame)
    canvas_container.pack(fill="both", expand=True)
    
    # Create scrollbars
    h_scrollbar = tk.Scrollbar(canvas_container, orient="horizontal")
    v_scrollbar = tk.Scrollbar(canvas_container, orient="vertical")
    
    # Create canvas with scrollbars
    canvas = tk.Canvas(canvas_container, 
                      width=min(width, 700), 
                      height=min(height, 500),
                      cursor="cross",
                      xscrollcommand=h_scrollbar.set,
                      yscrollcommand=v_scrollbar.set)
    
    # Configure scrollbars
    h_scrollbar.config(command=canvas.xview)
    v_scrollbar.config(command=canvas.yview)
    
    # Pack scrollbars and canvas
    h_scrollbar.pack(side="bottom", fill="x")
    v_scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    
    # Add image to canvas
    canvas.create_image(0, 0, anchor=tk.NW, image=img)
    canvas.config(scrollregion=canvas.bbox("all"))
    
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

            # Multi-scale template matching
            found = None
            for scale in np.linspace(0.8, 1.2, 20)[::-1]:
                # Resize template and check if it fits within the region image
                resized_tpl = cv2.resize(tpl, (int(tpl.shape[1] * scale), int(tpl.shape[0] * scale)))
                if resized_tpl.shape[0] > region_img.shape[0] or resized_tpl.shape[1] > region_img.shape[1]:
                    continue

                res = cv2.matchTemplate(region_img, resized_tpl, cv2.TM_CCOEFF_NORMED)
                _, maxv, _, maxl = cv2.minMaxLoc(res)

                if found is None or maxv > found[0]:
                    found = (maxv, maxl)

            maxv, maxl = found
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

# Create listbox with scrollbar
listbox_frame = tk.Frame(window_frame)
listbox_frame.pack(fill="x", pady=5)

listbox_scrollbar = tk.Scrollbar(listbox_frame)
window_listbox = tk.Listbox(listbox_frame, height=4, yscrollcommand=listbox_scrollbar.set)

listbox_scrollbar.config(command=window_listbox.yview)
listbox_scrollbar.pack(side="right", fill="y")
window_listbox.pack(side="left", fill="x", expand=True)

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
    tk.Button(btns1, text="Test Templates", command=test_template_matching, bg="yellow").pack(side="left", padx=5)
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
    
    # Create text widget with scrollbar
    text_frame = tk.Frame(frame)
    text_frame.pack(fill="both", expand=True)
    
    text_scrollbar = tk.Scrollbar(text_frame)
    status_text = tk.Text(text_frame, height=8, width=80, yscrollcommand=text_scrollbar.set)
    
    text_scrollbar.config(command=status_text.yview)
    text_scrollbar.pack(side="right", fill="y")
    status_text.pack(side="left", fill="both", expand=True)
    
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