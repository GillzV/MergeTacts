# Card Placer - No Administrator Version

This version of the card automation script uses alternative methods to avoid requiring administrator privileges.

## Why Administrator Privileges Are Usually Required

The original script requires administrator privileges because:
1. **PyAutoGUI limitations**: On Windows, PyAutoGUI needs elevated privileges to control other applications
2. **Game protection**: Many games have anti-cheat systems that block automated input
3. **Windows security**: Modern Windows versions restrict cross-application mouse control

## Alternative Approaches (No Admin Required)

### 1. **Safer PyAutoGUI Settings**
- Re-enabled failsafe (move mouse to corner to stop)
- Longer delays between actions
- More conservative mouse control
- Better error handling

### 2. **AutoHotkey Integration**
- AutoHotkey provides better mouse control without admin privileges
- The script creates `mouse_control.ahk` automatically
- Run AutoHotkey script separately for enhanced control

### 3. **Keyboard Shortcuts**
- Use keyboard shortcuts instead of mouse control
- Set up your game to use number keys (1-8) for card selection
- Space bar for card deployment

### 4. **Windowed Mode**
- Run your game in windowed mode instead of fullscreen
- This often allows better mouse control without admin privileges

## How to Use

### Option 1: Direct Python Script
```bash
python auto_card_placer_no_admin.py
```

### Option 2: Batch File
```bash
run_no_admin.bat
```

### Option 3: AutoHotkey + Python
1. Run `mouse_control.ahk` (requires AutoHotkey to be installed)
2. Run the Python script
3. The script will detect AutoHotkey and use it for mouse control

## Installation Requirements

### Required Python Packages
```bash
pip install opencv-python numpy pyautogui pillow pygetwindow pytesseract easyocr
```

### Optional: AutoHotkey
1. Download AutoHotkey from: https://www.autohotkey.com/
2. Install it
3. The script will automatically detect and use it

### Optional: Tesseract OCR
1. Download Tesseract from: https://github.com/tesseract-ocr/tesseract
2. Install it
3. The script will automatically detect it

## Troubleshooting

### Mouse Control Not Working
1. **Try windowed mode**: Run your game in windowed mode
2. **Use AutoHotkey**: Install AutoHotkey and run the .ahk script
3. **Use keyboard shortcuts**: Set up your game to use keyboard shortcuts
4. **Check game settings**: Some games have options to allow external input

### OCR Not Working
1. **Install Tesseract**: Download and install Tesseract OCR
2. **Use manual input**: The script has a fallback for manual elixir input
3. **Calibrate elixir region**: Use the calibration feature to set the correct elixir region

### Game Detection Issues
1. **Refresh window list**: Use the "Refresh Windows" button
2. **Run game as windowed**: Fullscreen games are harder to detect
3. **Check game compatibility**: Some games may not work with automation

## Safety Features

- **Failsafe enabled**: Move mouse to screen corner to stop
- **Longer delays**: More conservative timing to avoid detection
- **Error handling**: Better error recovery
- **Manual override**: Can stop automation at any time

## Performance Tips

1. **Lower game graphics**: Higher FPS = better detection
2. **Use windowed mode**: Better compatibility
3. **Calibrate regions**: Set up elixir and card regions properly
4. **Test first**: Use the test buttons before running automation

## Legal Notice

This tool is for educational purposes only. Using automation in online games may violate terms of service. Use at your own risk and responsibility. 