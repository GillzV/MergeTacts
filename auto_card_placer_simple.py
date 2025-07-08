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

# Configure pyautogui for non-admin operation
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

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
confidence_threshold = 0.5

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
calibrated_cards_roi = None   # x, y, w, h within window for cards area

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
                resized_ref = cv2.resize(processed_ref, (new_w, new_h))
                # Bulletproof: skip if template is non-positive or larger than ROI
                if resized_ref.shape[0] <= 0 or resized_ref.shape[1] <= 0:
                    continue
                if processed_img.shape[0] < resized_ref.shape[0] or processed_img.shape[1] < resized_ref.shape[1]:
                    # print(f"[Elixir] Skipping: ROI ({processed_img.shape}) < template ({resized_ref.shape})")
                    continue
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
    if best_confidence > 0.60:
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
        
        screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
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
    img = ImageTk.PhotoImage(img_pil)
    
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
            
            crop_img = screenshot.crop((roi_x, roi_y, roi_x + roi_w, roi_y + roi_h))
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
            results_text.insert(tk.END, f"ROI: ({roi_w}x{roi_h})\n\nConfidence:\n")
            
            for num, conf in results:
                results_text.insert(tk.END, f"{num}E: {conf:.3f}\n")

            best_num, best_conf = results[0]
            if best_conf > 0.6:  # Lowered threshold from 0.8 to 0.6
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
        ### --- THIS IS THE FIX --- ###
        global calibrated_elixir_roi
        coords['x2'], coords['y2'] = canvas.canvasx(event.x), canvas.canvasy(event.y)
        x = int(min(coords['x1'], coords['x2']))
        y = int(min(coords['y1'], coords['y2']))
        w = int(abs(coords['x1'] - coords['x2']))
        h = int(abs(coords['y1'] - coords['y2']))

        if w < 10 or h < 10:
            messagebox.showerror("Error", "Selected area is too small!")
            return
            
        calibrated_elixir_roi = (x, y, w, h)
        print(f"Elixir ROI calibrated to: {calibrated_elixir_roi}")
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
                if processed_img.shape[0] >= resized_ref.shape[0] and processed_img.shape[1] >= resized_ref.shape[1] and resized_ref.shape[0] > 0 and resized_ref.shape[1] > 0:
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
        
        if best_match[1] > 0.6:  # Lowered threshold from 0.8 to 0.6
            message += "\n✓ Good match found!"
        else:
            message += "\n✗ Match confidence is low. Consider recalibrating the ROI."
        
        show_scrollable_message("Template Matching Test", message)
        
    except Exception as e:
        error_msg = f"Error testing template matching: {str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)

# --- CARD DETECTION HELPERS ---
def load_card_references():
    """Load reference card images for template matching"""
    references = {}
    card_dir = "Screenshots/Cards"
    if not os.path.isdir(card_dir):
        print(f"WARNING: Card reference directory not found at '{card_dir}'")
        return references
    for fname in os.listdir(card_dir):
        if fname.lower().endswith('.jpg'):
            path = os.path.join(card_dir, fname)
            img = cv2.imread(path)
            if img is not None:
                references[fname] = img
            else:
                print(f"Failed to load: {path}")
    return references

card_references = load_card_references()

def preprocess_card_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return gray

card_confidence_threshold = 0.4

def match_templates(region_img, card_list):
    matches = []
    processed_img = preprocess_card_image(region_img)
    for name, cost in card_list:
        ref_img = card_references.get(name)
        if ref_img is None:
            continue
        best_conf = 0
        best_pos = (0, 0)
        best_scale = 1.0
        best_w, best_h = 0, 0
        try:
            processed_ref = preprocess_card_image(ref_img)
            for scale in np.linspace(0.7, 1.3, 15)[::-1]:
                h, w = processed_ref.shape[:2]
                new_h, new_w = int(h * scale), int(w * scale)
                resized_ref = cv2.resize(processed_ref, (new_w, new_h))
                if resized_ref.shape[0] <= 0 or resized_ref.shape[1] <= 0:
                    continue
                if processed_img.shape[0] < resized_ref.shape[0] or processed_img.shape[1] < resized_ref.shape[1]:
                    continue
                result = cv2.matchTemplate(processed_img, resized_ref, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                if max_val > best_conf:
                    best_conf = max_val
                    best_pos = (max_loc[0] + new_w // 2, max_loc[1] + new_h // 2)
                    best_scale = scale
                    best_w, best_h = new_w, new_h
            # Always append the best match for this card, even if below threshold
            matches.append((name, best_conf, best_pos, cost, best_scale, best_w, best_h))
            if best_conf < 0.2:
                print(f"[Card] Very low confidence for {name}: {best_conf:.3f}")
        except Exception as e:
            print(f"Error matching template {name}: {e}")
    return matches

def test_card_roi():
    """Test card ROI detection with template matching and show all found cards, always showing the closest match."""
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
        screenshot = pyautogui.screenshot(region=(left + x, top + y, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        cv2.imwrite('debug_cards_roi.png', img)
        playable_cards = [(name, card_data[name]["elixir"]) for name in card_references if name in card_data]
        matches = match_templates(img, playable_cards)
        matches.sort(key=lambda item: item[1], reverse=True)
        message = f"Card ROI Test Results (Closest Match):\n\n"
        message += f"ROI: ({x}, {y}, {w}, {h})\n"
        message += f"Reference Images Loaded: {len(card_references)}\n"
        message += f"Cards Checked: {len(playable_cards)}\n"
        if matches:
            best_name, best_conf, best_pos, best_cost, best_scale, best_w, best_h = matches[0]
            message += f"\nBest Match: {best_name.replace('.jpg','')}\n"
            message += f"  Confidence: {best_conf:.3f}\n  Position: {best_pos}\n  Elixir: {best_cost}\n  Scale: {best_scale:.2f}\n  Template Size: ({best_w}x{best_h})\n"
            if best_conf > 0.4:
                message += "  Status: ✓ Good match\n"
            else:
                message += "  Status: ✗ Low confidence match\n"
            message += "\nAll Card Confidences (Top 10):\n"
            message += "-" * 40 + "\n"
            for i, (name, conf, pos, cost, scale, w, h) in enumerate(matches[:10]):
                message += f"{i+1}. {name.replace('.jpg','')}: {conf:.3f} at {pos} (elixir: {cost})\n"
        else:
            message += "No card matches found in ROI.\n"
        message += f"\nDebug image saved: debug_cards_roi.png"
        show_scrollable_message("Card ROI Test Results", message)
    except Exception as e:
        error_msg = f"Error testing card ROI: {str(e)}"
        print(error_msg)
        messagebox.showerror("Error", error_msg)

def visual_calibrate_cards():
    if not selected_window:
        messagebox.showwarning("Warning", "Please select a window first!")
        return
    
    left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    img_pil = Image.frombytes('RGB', screenshot.size, screenshot.tobytes())
    img = ImageTk.PhotoImage(img_pil)
    
    win = tk.Toplevel(root)
    win.title("Select Card Area ROI")
    win.geometry("800x600")

    canvas = tk.Canvas(win, cursor="cross")
    canvas.pack(fill="both", expand=True)
    
    v_scrollbar = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
    v_scrollbar.pack(side="right", fill="y")
    h_scrollbar = tk.Scrollbar(win, orient="horizontal", command=canvas.xview)
    h_scrollbar.pack(side="bottom", fill="x")
    canvas.config(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
    
    canvas.create_image(0, 0, anchor=tk.NW, image=img)
    canvas.config(scrollregion=canvas.bbox("all"))
    
    coords = {'x1': 0, 'y1': 0}
    rect = None

    def on_down(e):
        nonlocal rect
        coords['x1'] = canvas.canvasx(e.x)
        coords['y1'] = canvas.canvasy(e.y)
        if rect: canvas.delete(rect)
        rect = canvas.create_rectangle(coords['x1'], coords['y1'], coords['x1'], coords['y1'], outline='red', width=2)
    
    def on_drag(e):
        x2, y2 = canvas.canvasx(e.x), canvas.canvasy(e.y)
        canvas.coords(rect, coords['x1'], coords['y1'], x2, y2)
    
    def on_up(e):
        ### --- THIS IS THE FIX --- ###
        global calibrated_cards_roi
        x1, y1 = coords['x1'], coords['y1']
        x2, y2 = canvas.canvasx(e.x), canvas.canvasy(e.y)
        
        x = int(min(x1, x2))
        y = int(min(y1, y2))
        w = int(abs(x1 - x2))
        h = int(abs(y1 - y2))
        
        if w < 50 or h < 50:
            messagebox.showerror("Error", "Selected area is too small for cards!")
            return
            
        calibrated_cards_roi = (x, y, w, h)
        print(f"Cards ROI calibrated to: {calibrated_cards_roi}")
        messagebox.showinfo("Success", f"Card ROI calibrated: {calibrated_cards_roi}")
        win.destroy()
    
    canvas.bind("<Button-1>", on_down)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_up)
    
    win.image = img

def find_playable_cards(current_elixir):
    cards = [(name,data['elixir']) for name,data in card_data.items() if data['elixir'] <= current_elixir]
    cards.sort(key=lambda x: priorities.get(x[0], 999))
    return cards

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
        selected_window.activate()
        time.sleep(0.1)
        pyautogui.click(abs_x, abs_y)
        print(f"Clicked card at ({abs_x},{abs_y})")
        return True
    except Exception as e:
        print(f"Failed to click: {e}")
        return False

automation_active = False
def automation_thread():
    global automation_active
    if automation_active:
        print("Automation is already running.")
        return
    automation_active = True
    stop_event.clear()
    print("=== AUTOMATION STARTED ===")
    
    while not stop_event.is_set():
        if not selected_window or not mouse_control_active:
            time.sleep(1)
            continue
        try:
            el = get_current_elixir()
            playable = find_playable_cards(el)
            if not playable:
                time.sleep(0.5)
                continue
            
            left, top, width, height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
            if calibrated_cards_roi:
                cx, cy, w, h = calibrated_cards_roi
                region = (left+cx, top+cy, w, h)
            else:
                region = (left, top, width, height)
            
            shot = cv2.cvtColor(np.array(pyautogui.screenshot(region=region)), cv2.COLOR_RGB_BGR)
            matches = match_templates(shot, playable)
            
            if matches:
                matches.sort(key=lambda item: priorities.get(item[0], 999))
                best = matches[0]
                print(f"Best card to play: {best[0].replace('.jpg','')} with cost {best[3]}")
                if click_card(best[2]):
                    time.sleep(1)
            
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

root = tk.Tk()
root.title("Card Placer")
root.geometry("700x650")

def refresh_windows():
    window_listbox.delete(0, tk.END)
    for win in gw.getAllWindows():
        if win.title.strip():
            window_listbox.insert(tk.END, win.title)

def select_window():
    global selected_window
    sel = window_listbox.curselection()
    if sel:
        title = window_listbox.get(sel[0])
        try:
            windows = gw.getWindowsWithTitle(title)
            if windows:
                selected_window = windows[0]
                messagebox.showinfo("Selected", f"Selected: {selected_window.title}")
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