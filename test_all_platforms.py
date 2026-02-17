#!/usr/bin/env python3
"""
Complete Detection Test Script - VERSION 4
Tests all supported platforms: browsers, Zoom, Teams, Slack, Telegram, WhatsApp
"""

import subprocess

print("=" * 60)
print("Complete Call Detection Test - Version 4")
print("=" * 60)
print()
print("This script will test detection for ALL supported platforms.")
print()

def test_browser(browser_name, app_name):
    """Test a browser for meeting tabs"""
    print(f"Testing {browser_name}...")
    print("-" * 60)
    
    script = f'''
    tell application "{app_name}"
        if it is running then
            set output to ""
            repeat with w in windows
                repeat with t in tabs of w
                    set tabURL to URL of t
                    set output to output & tabURL & "\\n"
                end repeat
            end repeat
            return output
        else
            return "{browser_name} not running"
        end if
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and "not running" not in result.stdout:
            print(f"✓ {browser_name} is accessible")
            urls = result.stdout.lower()
            
            # Check for meeting platforms
            found = []
            if 'meet.google.com' in urls:
                found.append("Google Meet")
            if 'teams.microsoft.com' in urls:
                found.append("Microsoft Teams")
            if 'zoom.us' in urls:
                found.append("Zoom")
            if 'slack.com/huddle' in urls:
                found.append("Slack Huddle")
            if 'web.telegram.org' in urls:
                found.append("Telegram Web")
            if 'web.whatsapp.com' in urls:
                found.append("WhatsApp Web")
            
            if found:
                print(f"✓ FOUND: {', '.join(found)}")
            else:
                print("✗ No meeting tabs detected")
        else:
            print(f"✗ {browser_name} not running or not accessible")
            if result.stderr:
                print(f"  Error: {result.stderr}")
    except Exception as e:
        print(f"✗ {browser_name} check error: {e}")
    
    print()

def test_desktop_app(app_name, display_name, call_keywords):
    """Test a desktop app for active calls"""
    print(f"Testing {display_name}...")
    print("-" * 60)
    
    script = f'''
    tell application "System Events"
        if exists (process "{app_name}") then
            set windowList to name of every window of process "{app_name}"
            set output to ""
            repeat with windowName in windowList
                set output to output & windowName & "\\n"
            end repeat
            return "RUNNING:" & output
        else
            return "NOT_RUNNING"
        end if
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            output = result.stdout
            
            if "NOT_RUNNING" in output:
                print(f"✗ {display_name} not running")
            elif "RUNNING:" in output:
                print(f"✓ {display_name} is running")
                print(f"  Window titles: {output.replace('RUNNING:', '').strip()}")
                
                # Check for call keywords
                found = False
                for keyword in call_keywords:
                    if keyword.lower() in output.lower():
                        print(f"✓ FOUND: Active call detected (keyword: '{keyword}')")
                        found = True
                        break
                
                if not found:
                    print(f"✗ No active call detected")
            else:
                print(f"✗ Unexpected response: {output}")
        else:
            print(f"✗ {display_name} check failed:", result.stderr)
    except Exception as e:
        print(f"✗ {display_name} check error: {e}")
    
    print()

# Test all browsers
print("=" * 60)
print("TESTING BROWSERS")
print("=" * 60)
print()

test_browser("Google Chrome", "Google Chrome")
test_browser("Safari", "Safari")
test_browser("Microsoft Edge", "Microsoft Edge")

# Test all desktop apps
print("=" * 60)
print("TESTING DESKTOP APPS")
print("=" * 60)
print()

test_desktop_app("zoom.us", "Zoom", ["Zoom Meeting", "meeting"])
test_desktop_app("Microsoft Teams", "Microsoft Teams", ["Meeting", "Call", "|"])
test_desktop_app("Slack", "Slack", ["Huddle", "huddle"])
test_desktop_app("Telegram", "Telegram", ["Call", "Calling", "Voice Chat"])

# Additional detailed Telegram test
print("Testing Telegram (Detailed)...")
print("-" * 60)

telegram_detailed_script = '''
tell application "System Events"
    if exists (process "Telegram") then
        set output to "Windows found: "
        set windowCount to count of windows of process "Telegram"
        set output to output & windowCount & "\\n"
        
        repeat with w in windows of process "Telegram"
            try
                set wTitle to name of w
                set wPos to position of w
                set wSize to size of w
                set output to output & "Window: '" & wTitle & "' Size: " & (item 1 of wSize) & "x" & (item 2 of wSize) & "\\n"
            end try
        end repeat
        return output
    else
        return "Telegram not running"
    end if
end tell
'''

try:
    result = subprocess.run(
        ['osascript', '-e', telegram_detailed_script],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0:
        print("Telegram window details:")
        print(result.stdout)
        
        # Check for small windows (likely call windows)
        lines = result.stdout.split('\n')
        for line in lines:
            if 'Size:' in line and 'x' in line:
                try:
                    size_part = line.split('Size: ')[1].split('x')
                    width = int(size_part[0])
                    height = int(size_part[1])
                    if width < 500 and height < 700:
                        print(f"  ✓ Small window detected (possible call window): {line}")
                except:
                    pass
    else:
        print("Error:", result.stderr)
except Exception as e:
    print(f"Error: {e}")

print()
test_desktop_app("WhatsApp", "WhatsApp", ["Call", "Calling", "Ringing"])

# Summary
print("=" * 60)
print("NEXT STEPS")
print("=" * 60)
print()
print("If browser detection failed:")
print("  1. Go to System Preferences → Security & Privacy → Privacy")
print("  2. Click 'Automation' in the left sidebar")
print("  3. Enable Terminal for: Chrome, Safari, Edge")
print()
print("If desktop app detection failed:")
print("  1. Make sure the app is actually running")
print("  2. Join a call/meeting in that app")
print("  3. Run this test again to see the window titles")
print()
print("Once detection is working:")
print("  Run: python3 luxafor_call_monitor_v4.py")
print()
