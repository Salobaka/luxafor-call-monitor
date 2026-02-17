#!/usr/bin/env python3
"""
Browser Detection Test Script
Run this while you have a Google Meet tab open to test if browser detection works
"""

import subprocess

print("=" * 60)
print("Browser Detection Test")
print("=" * 60)
print()
print("This script will test if we can read your browser tabs.")
print("Make sure you have Chrome or Safari open with a meeting tab!")
print()

# Test Chrome
print("Testing Chrome...")
print("-" * 60)

chrome_script = '''
tell application "Google Chrome"
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
        return "Chrome not running"
    end if
end tell
'''

try:
    result = subprocess.run(
        ['osascript', '-e', chrome_script],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        print("✓ Chrome is accessible")
        print("\nAll open tabs:")
        print(result.stdout)
        
        # Check for meeting URLs
        urls = result.stdout.lower()
        if 'meet.google.com' in urls:
            print("✓ FOUND: Google Meet tab")
        if 'teams.microsoft.com' in urls:
            print("✓ FOUND: Microsoft Teams tab")
        if 'zoom.us' in urls:
            print("✓ FOUND: Zoom tab")
        if 'slack.com/huddle' in urls:
            print("✓ FOUND: Slack Huddle tab")
        
        if not any(x in urls for x in ['meet.google.com', 'teams.microsoft.com', 'zoom.us', 'slack.com/huddle']):
            print("✗ No meeting tabs detected")
    else:
        print("✗ Chrome check failed")
        print("Error:", result.stderr)
        
except Exception as e:
    print(f"✗ Chrome check error: {e}")

print()
print("=" * 60)

# Test Safari
print("Testing Safari...")
print("-" * 60)

safari_script = '''
tell application "Safari"
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
        return "Safari not running"
    end if
end tell
'''

try:
    result = subprocess.run(
        ['osascript', '-e', safari_script],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        print("✓ Safari is accessible")
        print("\nAll open tabs:")
        print(result.stdout)
        
        # Check for meeting URLs
        urls = result.stdout.lower()
        if 'meet.google.com' in urls:
            print("✓ FOUND: Google Meet tab")
        if 'teams.microsoft.com' in urls:
            print("✓ FOUND: Microsoft Teams tab")
        if 'zoom.us' in urls:
            print("✓ FOUND: Zoom tab")
        if 'slack.com/huddle' in urls:
            print("✓ FOUND: Slack Huddle tab")
            
        if not any(x in urls for x in ['meet.google.com', 'teams.microsoft.com', 'zoom.us', 'slack.com/huddle']):
            print("✗ No meeting tabs detected")
    else:
        print("✗ Safari check failed")
        print("Error:", result.stderr)
        
except Exception as e:
    print(f"✗ Safari check error: {e}")

print()
print("=" * 60)

# Test Edge
print("Testing Microsoft Edge...")
print("-" * 60)

edge_script = '''
tell application "Microsoft Edge"
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
        return "Edge not running"
    end if
end tell
'''

try:
    result = subprocess.run(
        ['osascript', '-e', edge_script],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        print("✓ Edge is accessible")
        print("\nAll open tabs:")
        print(result.stdout)
        
        # Check for meeting URLs
        urls = result.stdout.lower()
        if 'meet.google.com' in urls:
            print("✓ FOUND: Google Meet tab")
        if 'teams.microsoft.com' in urls:
            print("✓ FOUND: Microsoft Teams tab")
        if 'zoom.us' in urls:
            print("✓ FOUND: Zoom tab")
        if 'slack.com/huddle' in urls:
            print("✓ FOUND: Slack Huddle tab")
            
        if not any(x in urls for x in ['meet.google.com', 'teams.microsoft.com', 'zoom.us', 'slack.com/huddle']):
            print("✗ No meeting tabs detected")
    else:
        print("✗ Edge check failed")
        print("Error:", result.stderr)
        
except Exception as e:
    print(f"✗ Edge check error: {e}")

print()
print("=" * 60)
print()
print("NEXT STEPS:")
print()
print("If browser detection failed:")
print("1. Go to System Preferences → Security & Privacy → Privacy")
print("2. Click 'Automation' in the left sidebar")
print("3. Find 'Terminal' and enable access to Chrome/Safari/Edge")
print("4. Run this test again")
print()
print("If browser detection worked:")
print("Run: python3 luxafor_call_monitor_v3.py")
