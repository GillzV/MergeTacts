#NoEnv
#SingleInstance Force
SetWorkingDir %A_ScriptDir%

; Card Placer Mouse Control Script
; This script provides mouse control functions for the card automation

; Function to click at coordinates
ClickAt(x, y) {
    MouseMove, x, y
    Click
}

; Function to drag from coordinates
DragFrom(x, y, dx, dy) {
    MouseMove, x, y
    Click Down
    MouseMove, x + dx, y + dy
    Click Up
}

; Function to double click
DoubleClickAt(x, y) {
    MouseMove, x, y
    Click
    Sleep, 50
    Click
}

; Function to right click
RightClickAt(x, y) {
    MouseMove, x, y
    Click Right
}

; Hotkey to stop script
^!s::
    MsgBox, Script stopped by user
    ExitApp
return

; Hotkey to test mouse control
^!t::
    MsgBox, Testing mouse control...
    MouseMove, 100, 100
    Sleep, 500
    MouseMove, 200, 200
    Sleep, 500
    Click
    MsgBox, Mouse control test completed
return

; Show help
^!h::
    MsgBox, Card Placer Mouse Control`n`nHotkeys:`nCtrl+Alt+S: Stop script`nCtrl+Alt+T: Test mouse control`nCtrl+Alt+H: Show this help
return

; Show script info on startup
MsgBox, Card Placer Mouse Control Script Loaded`n`nPress Ctrl+Alt+H for help 