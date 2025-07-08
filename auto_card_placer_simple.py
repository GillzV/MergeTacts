import cv2
import numpy as np
import pyautogui
import os
import time
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox, simpledialog
import threading
import pygetwindow as gw
import re
import json

# Configure pyautogui for non-admin operation
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

# --- CONFIGURATION ---
priorities = {
    "ArcherQueen.png": 1,
    "Archers.png": 5,
    "Bandit.png": 3,
    "Barbarians.png": 3,
    "Bomber.png": 5,
    "DartGoblin.png": 3,
    "Executioner.png": 4,
    "GiantSkeleton.png": 4,
    "GoblinMachine.png": 2,
    "Goblins.png": 1,
    "GoldenKnight.png": 1,
    "Knight.png": 2,
    "MegaKnight.png": 3,
    "PEKKA.png": 3,
    "Prince.png": 3,
    "Princess.png": 2,
    "RoyalGhost.png": 1,
    "SkeletonKing.png": 1,
    "SpearGoblins.png": 3,
    "Valkyrie.png": 5,
}
# Adjusted confidence threshold for better matching
confidence_threshold = 0.21

# Card metadata: elixir cost for each card
card_data = {
    "Knight.png": {"elixir": 3, "class": ["tank", "champion"]},
    "Archers.png": {"elixir": 4, "class": ["ranged", "clan"]},
    "SpearGoblins.png": {"elixir": 4, "class": ["thrower", "goblin"]},
    "GoblinMachine.png": {"elixir": 2, "class": ["tank", "goblin"]},
    "Bomber.png": {"elixir": 5, "class": ["thrower", "skeleton/undead"]},
    "Barbarians.png": {"elixir": 5, "class": ["brawler", "clan"]},
    "Valkyrie.png": {"elixir": 4, "class": ["avenger", "clan"]},
    "PEKKA.png": {"elixir": 7, "class": ["ace", "tank"]},
    "Prince.png": {"elixir": 3, "class": ["brawler", "champion"]},
    "GiantSkeleton.png": {"elixir": 6, "class": ["tank", "brawler", "skeleton/undead"]},
    "DartGoblin.png": {"elixir": 3, "class": ["ranged", "goblin"]},
    "Executioner.png": {"elixir": 5, "class": ["thrower", "ace"]},
    "Princess.png": {"elixir": 5, "class": ["ranged", "champion"]},
    "MegaKnight.png": {"elixir": 5, "class": ["brawler", "ace", "tank"]},
    "RoyalGhost.png": {"elixir": 3, "class": ["assassin", "skeleton/undead"]},
    "Bandit.png": {"elixir": 3, "class": ["ace", "avenger"]},
    "Goblins.png": {"elixir": 2, "class": ["assassin", "goblin"]},
    "SkeletonKing.png": {"elixir": 3, "class": ["tank", "skeleton/undead"]},
    "GoldenKnight.png": {"elixir": 2, "class": ["assassin", "champion"]},
    "ArcherQueen.png": {"elixir": 2, "class": ["avenger", "clan"]},
}

# --- GLOBAL VARIABLES ---
stop_event = threading.Event()
selected_window = None
mouse_control_active = False
calibrated_elixir_roi = None  # x, y, w, h within window for elixir
calibrated_cards_roi = None   # x, y, w, h within window for cards area
win_border = 0
title_bar = 0
ROI_CONFIG_FILE = "roi_config.json"
elixir_zero_counter = 0
ELIXIR_ZERO_LIMIT = 5
periodic_stop_event = threading.Event()
last_click_time = {}
COOLDOWN = 2  # seconds

# --- ROI PERSISTENCE HELPERS ---
def save_roi_config():
    data = {
        "elixir_roi": calibrated_elixir_roi,
        "cards_roi": calibrated_cards_roi
    }
    with open(ROI_CONFIG_FILE, "w") as f:
        json.dump(data, f)
    print(f"Saved ROI config to {ROI_CONFIG_FILE}")

def load_roi_config():
    global calibrated_elixir_roi, calibrated_cards_roi
    try:
        with open(ROI_CONFIG_FILE, "r") as f:
            data = json.load(f)
            calibrated_elixir_roi = tuple(data["elixir_roi"]) if data["elixir_roi"] else None
            calibrated_cards_roi = tuple(data["cards_roi"]) if data["cards_roi"] else None
        print(f"Loaded ROI config from {ROI_CONFIG_FILE}: elixir={calibrated_elixir_roi}, cards={calibrated_cards_roi}")
    except Exception as e:
        print(f"No ROI config loaded: {e}")

load_roi_config()

# --- CARD DETECTION HELPERS ---
def load_card_references():
    """Load all card reference images from Screenshots/Cards/ into a dictionary."""
    references = {}
    # Use absolute path relative to this script
    cards_dir = os.path.join(os.path.dirname(__file__), "Screenshots", "Cards")
    if not os.path.isdir(cards_dir):
        print(f"WARNING: Card reference directory not found at '{cards_dir}'")
        return references
    for fname in os.listdir(cards_dir):
        if fname.lower().endswith((".jpg", ".jpeg", ".png")):
            fpath = os.path.join(cards_dir, fname)
            img = cv2.imread(fpath)
            if img is not None:
                references[fname] = img
                print(f"Loaded card reference: {fname}")
            else:
                print(f"Failed to load: {fpath}")
    if not references:
        print(f"WARNING: No card reference images loaded from '{cards_dir}'!")
    return references

card_references = load_card_references()
print("Loaded card templates:", list(card_references.keys()))

# --- CARD TEMPLATE CONSISTENCY CHECK ---
def check_card_template_consistency():
    loaded_templates = set(card_references.keys())
    card_data_keys = set(card_data.keys())
    priorities_keys = set(priorities.keys())

    print("\n=== CARD TEMPLATE CONSISTENCY CHECK ===")
    print(f"Loaded templates ({len(loaded_templates)}): {sorted(loaded_templates)}")
    print(f"card_data keys   ({len(card_data_keys)}): {sorted(card_data_keys)}")
    print(f"priorities keys  ({len(priorities_keys)}): {sorted(priorities_keys)}")

    missing_in_templates = card_data_keys - loaded_templates
    missing_in_card_data = loaded_templates - card_data_keys
    missing_in_priorities = loaded_templates - priorities_keys

    if missing_in_templates:
        print(f"WARNING: These card_data keys have NO matching template image: {sorted(missing_in_templates)}")
    if missing_in_card_data:
        print(f"WARNING: These template images have NO matching card_data entry: {sorted(missing_in_card_data)}")
    if missing_in_priorities:
        print(f"WARNING: These template images have NO matching priorities entry: {sorted(missing_in_priorities)}")
    if not (missing_in_templates or missing_in_card_data or missing_in_priorities):
        print("All card template names match card_data and priorities keys!\n")
    print("=======================================\n")

check_card_template_consistency()

# --- ELIXIR DETECTION HELPERS ---
def load_elixir_references():
    """Load reference elixir images for template matching"""
    references = {}
    elixir_dir = "Screenshots/Elixir"
    
    if not os.path.isdir(elixir_dir):
        print(f"WARNING: Elixir reference directory not found at '{elixir_dir}'")
        return references

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

elixir_references = load_elixir_references()

def preprocess_elixir_image(img):
    """
    Preprocess elixir image for more reliable template matching.
    Converts to grayscale and then applies a binary threshold to isolate the number.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    return thresh

def detect_elixir_from_templates(img):
    """Detect elixir using template matching with pre-processed reference images"""
    if not elixir_references:
        print("No elixir references loaded. Cannot detect elixir.")
        return 10
    
    processed_img = preprocess_elixir_image(img)
    
    best_confidence = 0
    best_elixir = 10 
    
    for elixir_count, reference_img in elixir_references.items():
        try:
            processed_ref = preprocess_elixir_image(reference_img)
            max_confidence_for_digit = 0
            for scale in np.linspace(0.8, 1.2, 20):
                h, w = processed_ref.shape[:2]
                new_h, new_w = int(h * scale), int(w * scale)
                
                if new_h > processed_img.shape[0] or new_w > processed_img.shape[1]:
                    continue
                
                resized_ref = cv2.resize(processed_ref, (new_w, new_h))
                result = cv2.matchTemplate(processed_img, resized_ref, cv2.TM_CCOEFF_NORMED)
                _, confidence, _, _ = cv2.minMaxLoc(result)
                
                if confidence > max_confidence_for_digit:
                    max_confidence_for_digit = confidence
            
            if max_confidence_for_digit > best_confidence:
                best_confidence = max_confidence_for_digit
                best_elixir = elixir_count
                
        except Exception as e:
            print(f"Error matching elixir {elixir_count}: {e}")
            continue
    
    if best_confidence > 0.60:  # Lowered threshold from 0.80 to 0.60
        print(f"Template matching detected elixir: {best_elixir} (confidence: {best_confidence:.3f})")
        return best_elixir
    else:
        print(f"No good template match found (best was {best_elixir} with confidence {best_confidence:.3f}). Assuming 10.")
        return 10

def get_manual_elixir_input():
    """Get manual elixir input from user"""
    val = simpledialog.askinteger("Manual Elixir", "Enter current elixir (0-10):", minvalue=0, maxvalue=10)
    return val if val is not None else 5

def show_scrollable_message(title, message):
    """Show a scrollable message box for long content"""
    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("600x400")
    
    main_frame = tk.Frame(win)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    text_frame = tk.Frame(main_frame)
    text_frame.pack(fill="both", expand=True)
    
    text_scrollbar = tk.Scrollbar(text_frame)
    text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=text_scrollbar.set)
    
    text_scrollbar.config(command=text_widget.yview)
    text_scrollbar.pack(side="right", fill="y")
    text_widget.pack(side="left", fill="both", expand=True)
    
    text_widget.insert(tk.END, message)
    text_widget.config(state=tk.DISABLED)
    
    close_btn = tk.Button(main_frame, text="Close", command=win.destroy)
    close_btn.pack(pady=5)

def test_elixir_detection():
    """Test elixir detection with debug information"""
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    
    try:
        left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
        
        if calibrated_elixir_roi:
            x, y, w, h = calibrated_elixir_roi
        else:
            w, h = 100, 100
            x, y = width - w - 20, height - h - 20
        
        screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        cv2.imwrite('debug_elixir_raw.png', img)
        processed = preprocess_elixir_image(img)
        cv2.imwrite('debug_elixir_processed.png', processed)
        
        # Use the same improved detection logic as the live feedback
        if not elixir_references:
            message = "No elixir references loaded. Cannot detect elixir."
            show_scrollable_message("Elixir Test Results", message)
            return
        
        results = []
        for elixir_count, ref_img in elixir_references.items():
            processed_ref = preprocess_elixir_image(ref_img)
            res = cv2.matchTemplate(processed, processed_ref, cv2.TM_CCOEFF_NORMED)
            _, confidence, _, _ = cv2.minMaxLoc(res)
            results.append((elixir_count, confidence))
        
        results.sort(key=lambda x: x[1], reverse=True)
        best_num, best_conf = results[0]
        
        # Determine detected elixir based on confidence threshold
        if best_conf > 0.60:  # Lowered threshold from 0.80 to 0.60
            detected_elixir = best_num
            status = "✓ Good match found!"
        else:
            detected_elixir = 10  # Assume 10+ if no good match
            status = "✗ No good match - assuming 10+ elixir"
        
        message = f"Detected Elixir: {detected_elixir}\n"
        message += f"Detection Method: Template Matching (Improved)\n"
        message += f"Status: {status}\n\n"
        message += f"ROI: ({x}, {y}, {w}, {h})\n"
        message += f"Reference Images Loaded: {len(elixir_references)}/10\n\n"
        message += "All Confidence Scores:\n"
        message += "-" * 40 + "\n"
        
        for num, conf in results:
            if num == best_num:
                message += f"→ {num}E: {conf:.3f} (BEST)\n"
            else:
                message += f"  {num}E: {conf:.3f}\n"
        
        message += f"\nDebug images saved: debug_elixir_raw.png, debug_elixir_processed.png"
        
        show_scrollable_message("Elixir Test Results", message)
        
    except Exception as e:
        error_msg = f"Error testing elixir detection: {str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)

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
            w, h = 100, 100
            x, y = width - w - 20, height - h - 20
        
        ox = int(left + win_border + x)
        oy = int(top + title_bar + y)
        w = int(w)
        h = int(h)
        screenshot = pyautogui.screenshot(region=(ox, oy, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        return detect_elixir_from_templates(img)
            
    except Exception as e:
        print(f"Elixir detection failed: {e}")
        return get_manual_elixir_input()

# --- CALIBRATION ROUTINES ---
def visual_calibrate_elixir():
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    img_pil = Image.frombytes('RGB', screenshot.size, screenshot.tobytes())
    display_scale = 0.5
    disp_w, disp_h = int(img_pil.width * display_scale), int(img_pil.height * display_scale)
    img_pil_small = img_pil.resize((disp_w, disp_h), Image.LANCZOS)
    img = ImageTk.PhotoImage(img_pil_small)
    
    win = tk.Toplevel(root)
    win.title("Select Elixir ROI - Live Template Matching")
    win.geometry("1000x700")

    main_frame = tk.Frame(win)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)

    canvas_frame = tk.Frame(main_frame)
    canvas_frame.pack(side="left", fill="both", expand=True)

    canvas = tk.Canvas(canvas_frame, cursor="cross")
    canvas.pack(side="left", fill="both", expand=True)
    
    v_scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
    v_scrollbar.pack(side="right", fill="y")
    h_scrollbar = tk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
    h_scrollbar.pack(side="bottom", fill="x")
    canvas.config(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

    canvas.create_image(0, 0, anchor=tk.NW, image=img)
    canvas.config(scrollregion=canvas.bbox("all"))

    feedback_frame = tk.Frame(main_frame, width=250)
    feedback_frame.pack(side="right", fill="y", padx=(10, 0))
    feedback_frame.pack_propagate(False)

    tk.Label(feedback_frame, text="Live Feedback:", font=("Arial", 12, "bold")).pack(anchor="w")
    status_label = tk.Label(feedback_frame, text="Draw a box around the elixir number.", fg="blue", wraplength=240)
    status_label.pack(anchor="w", pady=5)
    
    results_text = tk.Text(feedback_frame, height=20, font=("Courier", 9))
    results_text.pack(fill="both", expand=True)

    coords = {'x1': 0, 'y1': 0, 'x2': 0, 'y2': 0}
    rect = None

    def update_feedback(roi_x, roi_y, roi_w, roi_h):
        try:
            if roi_w < 10 or roi_h < 10: return
            
            # Map ROI from display to original size
            orig_x = int(roi_x / display_scale)
            orig_y = int(roi_y / display_scale)
            orig_w = int(roi_w / display_scale)
            orig_h = int(roi_h / display_scale)
            crop_img = screenshot.crop((orig_x, orig_y, orig_x + orig_w, orig_y + orig_h))
            img_cv = cv2.cvtColor(np.array(crop_img), cv2.COLOR_RGB2BGR)

            processed_img = preprocess_elixir_image(img_cv)
            cv2.imwrite('debug_calibration_processed.png', processed_img)

            results = []
            if not elixir_references:
                status_label.config(text="No reference images found!", fg="red")
                return

            for elixir_count, ref_img in elixir_references.items():
                processed_ref = preprocess_elixir_image(ref_img)
                res = cv2.matchTemplate(processed_img, processed_ref, cv2.TM_CCOEFF_NORMED)
                _, confidence, _, _ = cv2.minMaxLoc(res)
                results.append((elixir_count, confidence))
            
            results.sort(key=lambda x: x[1], reverse=True)
            
            results_text.delete(1.0, tk.END)
            results_text.insert(tk.END, f"ROI: ({orig_w}x{orig_h})\n\nConfidence:\n")
            
            for num, conf in results:
                results_text.insert(tk.END, f"{num}E: {conf:.3f}\n")

            best_num, best_conf = results[0]
            if best_conf > 0.6:
                status_label.config(text=f"✅ Good Match: {best_num}E ({best_conf:.2f})", fg="green")
            else:
                status_label.config(text=f"⚠️ Low Match: {best_num}E ({best_conf:.2f})", fg="orange")

        except Exception as e:
            status_label.config(text=f"Error: {e}", fg="red")

    def on_mouse_down(event):
        nonlocal rect
        coords['x1'], coords['y1'] = canvas.canvasx(event.x), canvas.canvasy(event.y)
        if rect: canvas.delete(rect)
        rect = canvas.create_rectangle(coords['x1'], coords['y1'], coords['x1'], coords['y1'], outline='red', width=2)

    def on_mouse_move(event):
        if not rect: return
        x2, y2 = canvas.canvasx(event.x), canvas.canvasy(event.y)
        canvas.coords(rect, coords['x1'], coords['y1'], x2, y2)
        
        x = min(coords['x1'], x2)
        y = min(coords['y1'], y2)
        w = abs(coords['x1'] - x2)
        h = abs(coords['y1'] - y2)
        update_feedback(int(x), int(y), int(w), int(h))

    def on_mouse_up(event):
        global calibrated_elixir_roi
        coords['x2'], coords['y2'] = canvas.canvasx(event.x), canvas.canvasy(event.y)
        x = int(min(coords['x1'], coords['x2']))
        y = int(min(coords['y1'], coords['y2']))
        w = int(abs(coords['x1'] - coords['x2']))
        h = int(abs(coords['y1'] - coords['y2']))
        if w < 10 or h < 10:
            messagebox.showerror("Error", "Selected area is too small!")
            return
        # Map ROI from display to original size
        orig_x = int(x / display_scale)
        orig_y = int(y / display_scale)
        orig_w = int(w / display_scale)
        orig_h = int(h / display_scale)
        calibrated_elixir_roi = (orig_x, orig_y, orig_w, orig_h)
        print(f"Elixir ROI calibrated to: {calibrated_elixir_roi}")
        save_roi_config()
        messagebox.showinfo("Success", f"Elixir ROI set to {calibrated_elixir_roi}")
        win.destroy()

    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    
    win.image = img

def test_template_matching():
    """Test template matching against all reference images"""
    if not elixir_references:
        messagebox.showwarning("Warning", "No elixir reference images loaded!")
        return
    
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
        
    try:
        left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
        
        if calibrated_elixir_roi:
            x, y, w, h = calibrated_elixir_roi
        else:
            w, h = 100, 100
            x, y = width - w - 20, height - h - 20
        
        screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        results = []
        processed_img = preprocess_elixir_image(img)

        for elixir_count, reference_img in elixir_references.items():
            processed_ref = preprocess_elixir_image(reference_img)
            
            max_confidence = 0
            for scale in np.linspace(0.8, 1.2, 20):
                h_ref, w_ref = processed_ref.shape
                new_h, new_w = int(h_ref * scale), int(w_ref * scale)
                
                if new_h > processed_img.shape[0] or new_w > processed_img.shape[1]:
                    continue
                
                resized_ref = cv2.resize(processed_ref, (new_w, new_h))
                result = cv2.matchTemplate(processed_img, resized_ref, cv2.TM_CCOEFF_NORMED)
                _, confidence, _, _ = cv2.minMaxLoc(result)
                if confidence > max_confidence:
                    max_confidence = confidence

            results.append((elixir_count, max_confidence))
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        message = "Template Matching Test Results (with new preprocessing):\n\n"
        message += f"Current ROI: ({x}, {y}, {w}, {h})\n\n"
        message += "Confidence scores:\n"
        for elixir_count, confidence in results:
            message += f"{elixir_count}E: {confidence:.3f}\n"
        
        best_match = results[0]
        message += f"\nBest match: {best_match[0]}E (confidence: {best_match[1]:.3f})"
        
        if best_match[1] > 0.6:
            message += "\n✓ Good match found!"
        else:
            message += "\n✗ Match confidence is low. Consider recalibrating the ROI."
        
        show_scrollable_message("Template Matching Test", message)
        
    except Exception as e:
        error_msg = f"Error testing template matching: {str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)

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
            x, y, w, h = 0, 0, width, height
            print(f"Using default card ROI (full window): ({x}, {y}, {w}, {h})")
        
        ox = int(left + win_border + x)
        oy = int(top + title_bar + y)
        w = int(w)
        h = int(h)
        screenshot = pyautogui.screenshot(region=(ox, oy, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        cv2.imwrite('debug_cards_roi.png', img)
        
        current_elixir = get_current_elixir()
        playable_cards = find_playable_cards(current_elixir)
        
        if playable_cards:
            matches = match_templates(img, playable_cards)
            
            message = f"Card ROI Test Results:\n\n"
            message += f"ROI: ({x}, {y}, {w}, {h})\n"
            message += f"Current Elixir: {current_elixir}\n"
            message += f"Playable Cards Checked: {len(playable_cards)}\n"
            message += f"Matches Found: {len(matches)}\n\n"
            
            if matches:
                message += "Top matches:\n"
                matches.sort(key=lambda item: item[1], reverse=True)
                for i, (name, confidence, pos, cost) in enumerate(matches[:5]):
                    message += f"{i+1}. {name.replace('.png', '')} (conf: {confidence:.3f})\n"
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

def visual_calibrate_cards():
    """
    Shows a screenshot of the selected window and allows the user to draw a
    rectangle to define the card area ROI. Provides live feedback on card
    detection within the selected area.
    """
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    img_pil = Image.frombytes('RGB', screenshot.size, screenshot.tobytes())
    display_scale = 0.5
    disp_w, disp_h = int(img_pil.width * display_scale), int(img_pil.height * display_scale)
    img_pil_small = img_pil.resize((disp_w, disp_h), Image.LANCZOS)
    img = ImageTk.PhotoImage(img_pil_small)
    
    win = tk.Toplevel(root)
    win.title("Select Card Area ROI - Live Feedback")
    win.geometry("1000x700")

    main_frame = tk.Frame(win)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)

    canvas_frame = tk.Frame(main_frame)
    canvas_frame.pack(side="left", fill="both", expand=True)

    canvas = tk.Canvas(canvas_frame, cursor="cross")
    canvas.pack(side="left", fill="both", expand=True)
    
    v_scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
    v_scrollbar.pack(side="right", fill="y")
    h_scrollbar = tk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
    h_scrollbar.pack(side="bottom", fill="x")
    canvas.config(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

    canvas.create_image(0, 0, anchor=tk.NW, image=img)
    canvas.config(scrollregion=canvas.bbox("all"))

    feedback_frame = tk.Frame(main_frame, width=250)
    feedback_frame.pack(side="right", fill="y", padx=(10, 0))
    feedback_frame.pack_propagate(False)

    tk.Label(feedback_frame, text="Live Card Detection:", font=("Arial", 12, "bold")).pack(anchor="w")
    status_label = tk.Label(feedback_frame, text="Draw a box around the cards area.", fg="blue", wraplength=240)
    status_label.pack(anchor="w", pady=5)
    
    results_text = tk.Text(feedback_frame, height=25, font=("Courier", 9))
    results_text.pack(fill="both", expand=True)

    coords = {'x1': 0, 'y1': 0}
    rect = None
    all_cards_for_test = [(name, 0) for name in card_data.keys()]

    def update_card_feedback(roi_x, roi_y, roi_w, roi_h):
        try:
            if roi_w < 50 or roi_h < 50: 
                results_text.delete(1.0, tk.END)
                status_label.config(text="Box is too small.", fg="orange")
                return
            
            # Map ROI from display to original size
            orig_x = int(roi_x / display_scale)
            orig_y = int(roi_y / display_scale)
            orig_w = int(roi_w / display_scale)
            orig_h = int(roi_h / display_scale)
            crop_img = screenshot.crop((orig_x, orig_y, orig_x + orig_w, orig_y + orig_h))
            img_cv = cv2.cvtColor(np.array(crop_img), cv2.COLOR_RGB2BGR)

            matches = match_templates(img_cv, all_cards_for_test)
            matches.sort(key=lambda item: item[1], reverse=True)

            results_text.delete(1.0, tk.END)
            results_text.insert(tk.END, f"ROI: ({orig_w}x{orig_h})\n\nDetected Cards:\n")

            if matches:
                status_label.config(text=f"✅ Found {len(matches)} potential match(es)!", fg="green")
                for name, conf, _, _ in matches[:10]: # Show top 10
                    card_name = name.replace('.png', '')
                    results_text.insert(tk.END, f"{card_name:<15} {conf:.3f}\n")
            else:
                status_label.config(text="⚠️ No cards detected in this area.", fg="red")

        except Exception as e:
            status_label.config(text=f"Error: {e}", fg="red")

    def on_mouse_down(event):
        nonlocal rect
        coords['x1'] = canvas.canvasx(event.x)
        coords['y1'] = canvas.canvasy(event.y)
        if rect: canvas.delete(rect)
        rect = canvas.create_rectangle(coords['x1'], coords['y1'], coords['x1'], coords['y1'], outline='cyan', width=2)
    
    def on_mouse_move(event):
        if not rect: return
        x2, y2 = canvas.canvasx(event.x), canvas.canvasy(event.y)
        canvas.coords(rect, coords['x1'], coords['y1'], x2, y2)
        
        x = min(coords['x1'], x2)
        y = min(coords['y1'], y2)
        w = abs(coords['x1'] - x2)
        h = abs(coords['y1'] - y2)
        update_card_feedback(int(x), int(y), int(w), int(h))
    
    def on_mouse_up(event):
        global calibrated_cards_roi
        x1, y1 = coords['x1'], coords['y1']
        x2, y2 = canvas.canvasx(event.x), canvas.canvasy(event.y)
        
        x = int(min(x1, x2))
        y = int(min(y1, y2))
        w = int(abs(x1 - x2))
        h = int(abs(y1 - y2))
        
        if w < 50 or h < 50:
            messagebox.showerror("Error", "Selected area is too small for cards!")
            return
            
        # Map ROI from display to original size
        orig_x = int(x / display_scale)
        orig_y = int(y / display_scale)
        orig_w = int(w / display_scale)
        orig_h = int(h / display_scale)
        calibrated_cards_roi = (orig_x, orig_y, orig_w, orig_h)
        print(f"Cards ROI calibrated to: {calibrated_cards_roi}")
        save_roi_config()
        messagebox.showinfo("Success", f"Card ROI calibrated: {calibrated_cards_roi}")
        win.destroy()
    
    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    
    win.image = img

def find_playable_cards(current_elixir):
    cards = [(name,data['elixir']) for name,data in card_data.items() if data['elixir'] <= current_elixir]
    cards.sort(key=lambda x: priorities.get(x[0], 999))
    return cards

def match_templates(region_img, card_list):
    matches = []
    for name, cost in card_list:
        tpl = card_references.get(name)
        if tpl is None:
            print(f"Card reference not found or failed to load: {name}")
            continue
        found = None
        tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
        region_gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
        for scale in np.linspace(0.5, 2.0, 40)[::-1]:
            new_w = int(tpl_gray.shape[1] * scale)
            new_h = int(tpl_gray.shape[0] * scale)
            if new_h > region_gray.shape[0] or new_w > region_gray.shape[1]:
                continue
            resized_tpl = cv2.resize(tpl_gray, (new_w, new_h))
            try:
                res = cv2.matchTemplate(region_gray, resized_tpl, cv2.TM_CCOEFF_NORMED)
                _, maxv, _, maxl = cv2.minMaxLoc(res)
                if found is None or maxv > found[0]:
                    found = (maxv, maxl, new_w, new_h)
            except Exception as e:
                print(f"Error in matchTemplate for {name} at scale {scale:.2f}: {e}")
                continue
        if found is not None:
            maxv, maxl, w, h = found
            if maxv >= confidence_threshold:
                print(f"{name}: confidence = {maxv:.3f}")
                center_pos = (maxl[0] + w // 2, maxl[1] + h // 2)
                matches.append((name, maxv, center_pos, cost))
    return matches

def take_mouse_control():
    global mouse_control_active
    mouse_control_active = True
    control_label.config(text="Mouse Control: ENABLED", fg="green")

def release_mouse_control():
    global mouse_control_active
    mouse_control_active = False
    control_label.config(text="Mouse Control: DISABLED", fg="red")

def click_card(pos):
    if not mouse_control_active or not selected_window:
        return False
    ox, oy = selected_window.left, selected_window.top
    if calibrated_cards_roi:
        cx, cy, _, _ = calibrated_cards_roi
        ox += cx; oy += cy
    abs_x = ox + pos[0]
    abs_y = oy + pos[1]
    
    try:
        selected_window.activate(); time.sleep(0.1)
        pyautogui.click(abs_x, abs_y)
        print(f"Clicked card at ({abs_x},{abs_y})")
        return True
    except Exception as e:
        print(f"Failed to click: {e}")
        return False

automation_active = False
def automation_thread():
    global automation_active
    global periodic_thread
    global clicked_cards
    global last_attempted_card
    global elixir_zero_counter
    global periodic_stop_event
    global last_click_time
    if automation_active:
        print("Automation is already running.")
        return
    automation_active = True
    stop_event.clear()
    periodic_stop_event.clear()
    clicked_cards = []
    last_attempted_card = None
    elixir_zero_counter = 0
    last_click_time = {}
    print("=== AUTOMATION STARTED ===")
    # Start periodic button clicker
    periodic_thread = threading.Thread(target=periodic_button_clicker, daemon=True)
    periodic_thread.start()
    # Step 1: Find and click battle button before anything else
    print("Looking for Battle button...")
    battle_clicked = find_and_click_battle_button()
    if battle_clicked:
        print("Battle button clicked, waiting 2 seconds before proceeding...")
        time.sleep(2)
    else:
        print("Battle button not found. Proceeding to automation anyway.")

    # Guarantee: no card clicks or screenshots before this point
    first_card_click = True
    while not stop_event.is_set():
        if not selected_window or not mouse_control_active:
            time.sleep(1)
            continue
        try:
            el = get_current_elixir()
            # End-of-game detection: if elixir is None, 0, or 1 for several loops, stop clicking
            if el is None or el <= 1:
                elixir_zero_counter += 1
                print(f"Elixir is {el}, skipping card click. (zero count: {elixir_zero_counter})")
                time.sleep(0.5)
                last_attempted_card = None
                if elixir_zero_counter >= ELIXIR_ZERO_LIMIT:
                    print("Elixir has been 0 or 1 for several loops. Assuming end of game. Stopping card clicks until elixir increases.")
                    # Wait for elixir to increase (handled by next loop)
                    while True:
                        if stop_event.is_set():
                            break
                        el_check = get_current_elixir()
                        if el_check is not None and el_check > 1:
                            print(f"Elixir increased to {el_check}, resuming card clicks.")
                            elixir_zero_counter = 0
                            break
                        time.sleep(1)
                continue
            else:
                elixir_zero_counter = 0
            # Extra guard: never click if elixir is 0 or 1
            if el <= 1:
                print(f"(Extra Guard) Elixir is {el}, skipping card click.")
                time.sleep(0.5)
                last_attempted_card = None
                continue
            playable = find_playable_cards(el)
            if not playable:
                print(f"No playable cards for elixir={el}, skipping card click.")
                time.sleep(0.5)
                last_attempted_card = None
                continue
            left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
            if calibrated_cards_roi:
                cx, cy, w, h = calibrated_cards_roi
                ox = int(left + win_border + cx)
                oy = int(top + title_bar + cy)
                w = int(w)
                h = int(h)
                region = (ox, oy, w, h)
            else:
                ox = int(left + win_border)
                oy = int(top + title_bar)
                w = int(width)
                h = int(height)
                region = (ox, oy, w, h)
            shot = cv2.cvtColor(np.array(pyautogui.screenshot(region=region)), cv2.COLOR_RGB2BGR)
            matches = match_templates(shot, playable)
            if matches:
                # Prefer cards already clicked
                card_names_in_matches = [m[0] for m in matches]
                preferred = None
                for c in clicked_cards:
                    if c in card_names_in_matches:
                        preferred = next(m for m in matches if m[0] == c)
                        break
                if preferred is None:
                    # Pick the best as before
                    matches.sort(key=lambda item: priorities.get(item[0], 999))
                    preferred = matches[0]
                    if preferred[0] not in clicked_cards:
                        clicked_cards.append(preferred[0])
                print(f"Card to play: {preferred[0].replace('.png','')} with cost {preferred[3]}")
                # Double check: never click if elixir is 0 or 1
                if el <= 1:
                    print(f"(Guard) Elixir is {el}, skipping card click.")
                    time.sleep(0.5)
                    last_attempted_card = None
                    continue
                # Debounce repeated clicks on the same card
                name = preferred[0]
                now = time.time()
                if name in last_click_time and now - last_click_time[name] < COOLDOWN:
                    print(f"Debounce: Skipping click on {name} (cooldown {COOLDOWN}s not elapsed)")
                    time.sleep(1)
                    continue
                # If the same card is still the only available card, keep clicking it
                if len(matches) == 1:
                    if last_attempted_card == preferred[0]:
                        print(f"Still only {preferred[0].replace('.png','')} available, clicking again (likely waiting for elixir).")
                        if preferred[1] >= confidence_threshold:
                            if click_card(preferred[2]):
                                last_click_time[name] = now
                                time.sleep(1.5)
                        else:
                            print(f"Confidence {preferred[1]:.3f} is too low, not clicking.")
                        time.sleep(1)
                        continue
                    else:
                        last_attempted_card = preferred[0]
                else:
                    last_attempted_card = preferred[0]
                if preferred[1] >= confidence_threshold:
                    if click_card(preferred[2]):
                        last_click_time[name] = now
                        time.sleep(1.5)
                else:
                    print(f"Confidence {preferred[1]:.3f} is too low, not clicking.")
                time.sleep(1)
            else:
                last_attempted_card = None
                time.sleep(1)
        except Exception as e:
            print(f"Error in automation thread: {e}")
            time.sleep(2)
    automation_active = False
    print("=== AUTOMATION STOPPED ===")

def start_automation():
    threading.Thread(target=automation_thread, daemon=True).start()

def stop_automation():
    stop_event.set()

def find_and_click_battle_button():
    battle_btn_path = os.path.join("Screenshots", "BattleButton.png")
    if not os.path.exists(battle_btn_path):
        print(f"Battle button template not found at {battle_btn_path}")
        return False
    tpl = cv2.imread(battle_btn_path)
    if tpl is None:
        print(f"Failed to load battle button template: {battle_btn_path}")
        return False
    tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    screen = pyautogui.screenshot()
    screen_bgr = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    found = None
    for scale in np.linspace(0.7, 1.3, 20)[::-1]:
        new_w = int(tpl_gray.shape[1] * scale)
        new_h = int(tpl_gray.shape[0] * scale)
        if new_h > screen_gray.shape[0] or new_w > screen_gray.shape[1]:
            continue
        resized_tpl = cv2.resize(tpl_gray, (new_w, new_h))
        try:
            res = cv2.matchTemplate(screen_gray, resized_tpl, cv2.TM_CCOEFF_NORMED)
            _, maxv, _, maxl = cv2.minMaxLoc(res)
            if found is None or maxv > found[0]:
                found = (maxv, maxl, new_w, new_h)
        except Exception as e:
            continue
    if found is not None:
        maxv, maxl, w, h = found
        if maxv >= 0.72:
            center_pos = (maxl[0] + w // 2, maxl[1] + h // 2)
            pyautogui.click(center_pos)
            print(f"Clicked Battle button at {center_pos} (confidence={maxv:.3f})")
            time.sleep(1)
            return True
    return False

def find_and_click_button(template_path, name, confidence=0.7):
    if not os.path.exists(template_path):
        return False
    tpl = cv2.imread(template_path)
    if tpl is None:
        return False
    tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    screen = pyautogui.screenshot()
    screen_bgr = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    found = None
    for scale in np.linspace(0.7, 1.3, 20)[::-1]:
        new_w = int(tpl_gray.shape[1] * scale)
        new_h = int(tpl_gray.shape[0] * scale)
        if new_h > screen_gray.shape[0] or new_w > screen_gray.shape[1]:
            continue
        resized_tpl = cv2.resize(tpl_gray, (new_w, new_h))
        try:
            res = cv2.matchTemplate(screen_gray, resized_tpl, cv2.TM_CCOEFF_NORMED)
            _, maxv, _, maxl = cv2.minMaxLoc(res)
            if found is None or maxv > found[0]:
                found = (maxv, maxl, new_w, new_h)
        except Exception as e:
            continue
    if found is not None:
        maxv, maxl, w, h = found
        # Require 0.7 confidence for PlayAgainButton and BattleButton, else use provided confidence
        required_conf = 0.7 if name in ["PlayAgainButton", "BattleButton"] else confidence
        if maxv >= required_conf:
            center_pos = (maxl[0] + w // 2, maxl[1] + h // 2)
            pyautogui.click(center_pos)
            print(f"Clicked {name} at {center_pos} (confidence={maxv:.3f})")
            time.sleep(1)
            return True
    return False

def periodic_button_clicker():
    print("Periodic button clicker started.")
    goblin_last_check = 0
    GOBLIN_INTERVAL = 1  # seconds
    other_last_check = 0
    OTHER_INTERVAL = 2  # seconds
    while not periodic_stop_event.is_set():
        now = time.time()
        # Check GoblinClick every 1 second
        if now - goblin_last_check >= GOBLIN_INTERVAL:
            find_and_click_button(os.path.join("Screenshots", "GoblinClick.png"), "GoblinClick")
            goblin_last_check = now
        # Check other buttons every 2 seconds
        if now - other_last_check >= OTHER_INTERVAL:
            for btn_name, btn_file in [
                ("PlayAgainButton", os.path.join("Screenshots", "PlayAgainButton.png")),
                ("BattleButton", os.path.join("Screenshots", "BattleButton.png")),
                ("QuitButton", os.path.join("Screenshots", "QuitButton.png")),
            ]:
                if btn_name == "BattleButton":
                    conf = 0.72
                elif btn_name == "PlayAgainButton":
                    conf = 0.7
                else:
                    conf = 0.7
                find_and_click_button(btn_file, btn_name, confidence=conf)
                if periodic_stop_event.is_set():
                    break
            other_last_check = now
        time.sleep(0.2)
    print("Periodic button clicker stopped.")

root = tk.Tk()
root.title("Card Placer")
root.geometry("700x650")

def refresh_windows():
    window_listbox.delete(0, tk.END)
    for win in gw.getAllWindows():
        if win.title.strip():
            window_listbox.insert(tk.END, win.title)

def select_window():
    global selected_window, win_border, title_bar
    sel = window_listbox.curselection()
    if sel:
        title = window_listbox.get(sel[0])
        try:
            windows = gw.getWindowsWithTitle(title)
            if windows:
                selected_window = windows[0]
                # calculate chrome offsets
                # outer.top includes title bar, inner client top is .topleft[1]
                title_bar = selected_window.top - selected_window.topleft[1]
                win_border = selected_window.left - selected_window.topleft[0]
                messagebox.showinfo("Selected", f"Selected: {selected_window.title}\nwin_border={win_border}, title_bar={title_bar}")
            else:
                messagebox.showerror("Error", f"Window '{title}' not found!")
        except Exception as e:
            messagebox.showerror("Error", f"Could not select window: {e}")

window_frame = tk.LabelFrame(root, text="1. Window Selection")
window_frame.pack(fill="x", padx=10, pady=5)
listbox_frame = tk.Frame(window_frame)
listbox_frame.pack(fill="x", pady=5, padx=5)
listbox_scrollbar = tk.Scrollbar(listbox_frame)
window_listbox = tk.Listbox(listbox_frame, height=4, yscrollcommand=listbox_scrollbar.set)
listbox_scrollbar.config(command=window_listbox.yview)
listbox_scrollbar.pack(side="right", fill="y")
window_listbox.pack(side="left", fill="x", expand=True)
btn_frame = tk.Frame(window_frame)
tk.Button(btn_frame, text="Refresh", command=refresh_windows).pack(side="left", padx=5)
tk.Button(btn_frame, text="Select", command=select_window).pack(side="left")
btn_frame.pack(pady=5)
refresh_windows()

control_panel_frame = tk.LabelFrame(root, text="2. Mouse Control")
control_panel_frame.pack(fill="x", padx=10, pady=5)
control_label = tk.Label(control_panel_frame, text="Mouse Control: DISABLED", fg="red", font=("Arial", 10, "bold"))
control_label.pack(pady=5)
control_btns = tk.Frame(control_panel_frame)
tk.Button(control_btns, text="Take Control", command=take_mouse_control).pack(side="left", padx=5)
tk.Button(control_btns, text="Release Control", command=release_mouse_control).pack(side="left", padx=5)
control_btns.pack()

calib_frame = tk.LabelFrame(root, text="3. Calibration")
calib_frame.pack(fill="x", padx=10, pady=5)
btns1 = tk.Frame(calib_frame)
tk.Button(btns1, text="Calibrate Elixir ROI", command=visual_calibrate_elixir, bg="#FFDDC1").pack(side="left", padx=5, pady=2)
tk.Button(btns1, text="Test Elixir Detection", command=test_elixir_detection, bg="#C1FFD7").pack(side="left", padx=5, pady=2)
tk.Button(btns1, text="Test All Templates", command=test_template_matching, bg="#FFFAC1").pack(side="left", padx=5, pady=2)
btns1.pack()
btns2 = tk.Frame(calib_frame)
tk.Button(btns2, text="Calibrate Card ROI", command=visual_calibrate_cards, bg="#D1C1FF").pack(side="left", padx=5, pady=2)
tk.Button(btns2, text="Test Card ROI", command=test_card_roi, bg="#C1E1FF").pack(side="left", padx=5, pady=2)
btns2.pack()

auto_frame = tk.LabelFrame(root, text="4. Automation")
auto_frame.pack(fill="x", padx=10, pady=5)
auto_btns = tk.Frame(auto_frame)
tk.Button(auto_btns, text="START", command=start_automation, bg="green", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=5)
tk.Button(auto_btns, text="STOP", command=stop_automation, bg="red", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=5)
auto_btns.pack(pady=5)

root.bind('<Escape>', lambda e: stop_automation())
print("=== Card Placer Ready ===")
root.mainloop()