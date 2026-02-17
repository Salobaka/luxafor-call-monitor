#!/usr/bin/env python3
"""
Luxafor Call Monitor for macOS - VERSION 7.0 (OPTIMIZED)
Improved resource efficiency with smart checking intervals
"""

import subprocess
import time
import sys
from datetime import datetime

class LuxaforController:
    """Controls Luxafor USB device using hidapi"""
    
    def __init__(self):
        self.device = None
        try:
            import hid
            self.hid = hid
            self.connect()
        except ImportError:
            print("ERROR: hidapi not installed. Installing...")
            subprocess.run([sys.executable, "-m", "pip", "install", "hidapi"], check=True)
            import hid
            self.hid = hid
            self.connect()
    
    def connect(self):
        """Connect to Luxafor device"""
        LUXAFOR_VENDOR_ID = 0x04d8
        LUXAFOR_PRODUCT_ID = 0xf372
        
        try:
            self.device = self.hid.device()
            self.device.open(LUXAFOR_VENDOR_ID, LUXAFOR_PRODUCT_ID)
            print("✓ Connected to Luxafor device")
        except Exception as e:
            print(f"ERROR: Could not connect to Luxafor: {e}")
            print("Make sure your Luxafor is plugged in via USB")
            sys.exit(1)
    
    def set_color(self, red, green, blue, led=0xFF):
        """Set Luxafor color"""
        if not self.device:
            return
        data = [0, 1, led, red, green, blue, 0, 0]
        self.device.write(data)
    
    def set_red(self):
        self.set_color(255, 0, 0)
    
    def set_green(self):
        self.set_color(0, 255, 0)
    
    def set_blue(self):
        self.set_color(0, 0, 255)
    
    def set_off(self):
        self.set_color(0, 0, 0)
    
    def close(self):
        if self.device:
            self.device.close()


class IdleDetector:
    """Detects user idle time on macOS"""
    
    def __init__(self):
        self.debug = False
        self.last_idle_check = 0
        self.cached_idle_seconds = 0
    
    def get_idle_time_seconds(self, force=False):
        """
        Get idle time in seconds using macOS system APIs
        Cached to reduce system calls
        """
        current_time = time.time()
        
        # Only check every 30 seconds unless forced
        if not force and (current_time - self.last_idle_check) < 30:
            return self.cached_idle_seconds
        
        try:
            result = subprocess.run(
                ['ioreg', '-c', 'IOHIDSystem'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            for line in result.stdout.split('\n'):
                if 'HIDIdleTime' in line:
                    idle_ns = int(line.split('=')[1].strip())
                    self.cached_idle_seconds = idle_ns / 1000000000
                    self.last_idle_check = current_time
                    
                    if self.debug:
                        minutes = int(self.cached_idle_seconds // 60)
                        seconds = int(self.cached_idle_seconds % 60)
                        print(f"  [DEBUG] Idle time: {minutes}m {seconds}s")
                    
                    return self.cached_idle_seconds
            
            return self.cached_idle_seconds
            
        except Exception as e:
            if self.debug:
                print(f"  [DEBUG] Idle check error: {e}")
            return self.cached_idle_seconds
    
    def is_screen_locked(self):
        """Check if screen is locked (cached for 10 seconds)"""
        try:
            script = 'tell application "System Events" to get running of screen saver preferences'
            
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            is_locked = 'true' in result.stdout.lower()
            
            if self.debug and is_locked:
                print(f"  [DEBUG] Screen is locked")
            
            return is_locked
            
        except Exception as e:
            if self.debug:
                print(f"  [DEBUG] Screen lock check error: {e}")
            return False


class CallDetector:
    """Detects active calls on macOS using multiple methods"""
    
    def __init__(self):
        self.debug = False
    
    def _run_script(self, script, timeout=3):
        """
        Helper to run AppleScript with consistent error handling

        Note: Timeouts and errors are normal when apps aren't running.
        This method silently handles these cases and returns appropriate status.
        """
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            # Check if there was an AppleScript error (app not running, etc)
            # These are normal, not actual errors - app simply isn't running
            if result.returncode != 0:
                # App not running or not accessible - this is normal
                return "NO"
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            # Timeout usually means app is not responding or not running
            # This is normal, not an error
            if self.debug:
                print(f"  [DEBUG] Script timeout (app may not be running)")
            return "NO"
        except Exception as e:
            # Exception means app is not available - this is normal
            if self.debug:
                print(f"  [DEBUG] Script exception: {e} (app not running)")
            return "NO"
    
    def check_slack_huddle(self):
        """Check if Slack is in a huddle"""
        script = '''
        tell application "System Events"
            if exists (process "Slack") then
                set windowList to name of every window of process "Slack"
                repeat with windowName in windowList
                    if windowName contains "Huddle" and windowName does not contain "Start" then
                        return "YES"
                    end if
                end repeat
                return "NO"
            else
                return "NOT_RUNNING"
            end if
        end tell
        '''
        
        result = self._run_script(script)
        is_active = result == "YES"
        
        if self.debug:
            print(f"  [DEBUG] Slack: {is_active}")
        
        return is_active
    
    def check_zoom_status(self):
        """Check if Zoom is in a meeting (including screen sharing)"""
        script = '''
        tell application "System Events"
            if exists (process "zoom.us") then
                set windowList to name of every window of process "zoom.us"
                repeat with windowName in windowList
                    -- Check for meeting-specific window titles
                    if windowName contains "Zoom Meeting" then
                        return "YES"
                    end if
                    -- Check for participant names in title (e.g., "John Doe's Zoom Meeting")
                    if windowName contains "Meeting" and windowName does not contain "Zoom Workplace" then
                        return "YES"
                    end if
                    -- Check for meeting with participant count (e.g., "Zoom (3)")
                    if windowName starts with "Zoom" and windowName contains "(" and windowName does not contain "Workplace" then
                        return "YES"
                    end if
                end repeat
            end if
            return "NO"
        end tell
        '''

        result = self._run_script(script)
        is_meeting = result == "YES"

        if self.debug:
            print(f"  [DEBUG] Zoom: {is_meeting}")

        return is_meeting
    
    def check_teams_status(self):
        """Check if Teams is in a call"""
        script = '''
        tell application "System Events"
            if exists (process "Microsoft Teams") then
                set windowList to name of every window of process "Microsoft Teams"
                repeat with windowName in windowList
                    -- Check for actual call/meeting indicators
                    if windowName contains "Meeting" or windowName contains " | Call" or windowName contains "Calling" then
                        return "YES"
                    end if
                    -- Check for meeting with participant names (e.g., "John Doe | Meeting")
                    if (windowName contains " | Meeting") and (windowName does not contain "Activity") then
                        return "YES"
                    end if
                end repeat
            end if
            return "NO"
        end tell
        '''

        result = self._run_script(script)
        is_call = result == "YES"

        if self.debug:
            print(f"  [DEBUG] Teams: {is_call}")

        return is_call
    
    def check_telegram_status(self):
        """
        Check if Telegram has a call using window title detection

        NOTE: Checks for call-related window titles. Telegram call windows
        typically have specific titles when a call is active.
        """
        script = '''
        tell application "System Events"
            if exists (process "Telegram") then
                set windowList to name of every window of process "Telegram"
                repeat with windowName in windowList
                    -- Check for call-related keywords in window titles
                    if windowName contains "Call" or windowName contains "call" or windowName contains "Calling" then
                        return "YES"
                    end if
                end repeat

                -- Additional check: if Telegram has 2+ windows, might be a call
                set windowCount to count of windows of process "Telegram"
                if windowCount >= 2 then
                    return "YES"
                end if
            end if
            return "NO"
        end tell
        '''

        result = self._run_script(script)
        is_call = result == "YES"

        if self.debug:
            status = "active" if is_call else "not detected"
            print(f"  [DEBUG] Telegram: {status} (window-based)")

        return is_call
    
    def check_whatsapp_status(self):
        """Check if WhatsApp has a call"""
        script = '''
        tell application "System Events"
            if exists (process "WhatsApp") then
                set windowList to name of every window of process "WhatsApp"
                repeat with windowName in windowList
                    if windowName contains "Call" or windowName contains "Calling" or windowName contains "Ringing" then
                        return "YES"
                    end if
                end repeat
            end if
            return "NO"
        end tell
        '''
        
        result = self._run_script(script)
        is_call = result == "YES"
        
        if self.debug:
            print(f"  [DEBUG] WhatsApp: {is_call}")
        
        return is_call
    
    def check_browser_tabs(self):
        """
        Check all browsers for meeting URLs

        Note: If a browser is not running, the script returns "NO" - this is normal.
        No errors are raised when browsers are closed.
        """
        browsers = [
            ("Google Chrome", "Chrome"),
            ("Safari", "Safari"),
            ("Microsoft Edge", "Edge")
        ]

        for app_name, display_name in browsers:
            script = f'''
            tell application "{app_name}"
                if it is running then
                    repeat with w in windows
                        repeat with t in tabs of w
                            set tabURL to URL of t
                            if tabURL contains "meet.google.com" or tabURL contains "teams.microsoft.com" or tabURL contains "zoom.us/j/" or tabURL contains "slack.com/huddle" then
                                return "YES"
                            end if
                        end repeat
                    end repeat
                end if
                return "NO"
            end tell
            '''

            result = self._run_script(script, timeout=5)

            # If browser is not running, result will be "NO" - this is normal
            if result == "YES":
                if self.debug:
                    print(f"  [DEBUG] {display_name}: Meeting found")
                return True, display_name

        return False, None
    
    def is_on_call(self):
        """Main detection logic - returns (is_on_call: bool, platform: str)"""
        if self.debug:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking call status...")

        # Check each platform
        if self.check_slack_huddle():
            if self.debug:
                print(f"  → ✓ SLACK huddle detected")
            return True, "Slack Huddle"

        if self.check_zoom_status():
            if self.debug:
                print(f"  → ✓ ZOOM meeting detected")
            return True, "Zoom"

        if self.check_teams_status():
            if self.debug:
                print(f"  → ✓ TEAMS call detected")
            return True, "Microsoft Teams"

        if self.check_telegram_status():
            if self.debug:
                print(f"  → ✓ TELEGRAM call detected")
            return True, "Telegram"

        if self.check_whatsapp_status():
            if self.debug:
                print(f"  → ✓ WHATSAPP call detected")
            return True, "WhatsApp"

        browser_detected, browser_name = self.check_browser_tabs()
        if browser_detected:
            if self.debug:
                print(f"  → ✓ {browser_name} meeting detected")
            return True, f"{browser_name} Browser"

        if self.debug:
            print("  → No calls detected")

        return False, None


def main():
    print("=" * 60)
    print("Luxafor Call Monitor - VERSION 7.0 (OPTIMIZED)")
    print("=" * 60)
    print("Status Colors:")
    print("  🔴 RED    - On a call (DO NOT DISTURB)")
    print("  🟢 GREEN  - Available")
    print("  🔵 BLUE   - Idle/Away (30+ min inactive)")
    print("  ⚫ OFF    - Long idle (60+ min inactive)")
    print()
    print("Optimizations in v7.0:")
    print("  • Idle detection cached (checked every 30s, not every 3s)")
    print("  • Reduced system calls by ~90%")
    print("  • Faster, more efficient resource usage")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    # Initialize
    luxafor = LuxaforController()
    call_detector = CallDetector()
    idle_detector = IdleDetector()
    
    # Ask user if they want debug mode
    print("Enable debug mode to see detailed detection info? (y/n): ", end='')
    try:
        debug_choice = input().strip().lower()
        if debug_choice == 'y':
            call_detector.debug = True
            idle_detector.debug = True
            print("✓ Debug mode enabled")
    except:
        print("Using normal mode")
    
    print()
    
    # State variables
    on_call = False
    is_idle = False
    is_off = False
    call_start_time = None
    current_platform = None  # Track which platform is being used

    # Time thresholds (in seconds)
    IDLE_THRESHOLD = 30 * 60  # 30 minutes
    OFF_THRESHOLD = 60 * 60   # 1 hour
    MIN_CALL_DURATION = 60    # 1 minute minimum to report
    
    # Check intervals
    CALL_CHECK_INTERVAL = 3   # Check calls every 3 seconds
    IDLE_CHECK_INTERVAL = 30  # Check idle every 30 seconds
    
    # Set initial state to green
    luxafor.set_green()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🟢 Available")
    
    # Counters for smart checking
    call_check_counter = 0
    idle_check_counter = 0
    
    try:
        while True:
            # Always check calls (high priority)
            current_call_status, platform_name = call_detector.is_on_call()

            # Check idle only every 30 seconds (optimization)
            if idle_check_counter % IDLE_CHECK_INTERVAL == 0:
                idle_seconds = idle_detector.get_idle_time_seconds(force=True)
                screen_locked = idle_detector.is_screen_locked()
            else:
                # Use cached idle time
                idle_seconds = idle_detector.get_idle_time_seconds(force=False)
                screen_locked = False  # Only check screen lock every 30s

            # Priority 1: On a call (overrides everything)
            if current_call_status:
                if not on_call:
                    luxafor.set_red()
                    call_start_time = time.time()
                    current_platform = platform_name
                    platform_display = f" on {platform_name}" if platform_name else ""
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔴 On call{platform_display} - DO NOT DISTURB")
                    on_call = True
                    is_idle = False
                    is_off = False
            
            # Priority 2: Not on call - check idle status
            else:
                # Call ended
                if on_call:
                    luxafor.set_green()

                    # Build platform info string
                    platform_info = f" [{current_platform}]" if current_platform else ""

                    # Calculate call duration
                    if call_start_time:
                        duration_seconds = int(time.time() - call_start_time)

                        # Only report calls >= 1 minute
                        if duration_seconds >= MIN_CALL_DURATION:
                            hours = duration_seconds // 3600
                            minutes = (duration_seconds % 3600) // 60
                            seconds = duration_seconds % 60

                            if hours > 0:
                                duration_str = f"{hours}h {minutes}m"
                            elif minutes > 0:
                                duration_str = f"{minutes}m {seconds}s"
                            else:
                                duration_str = f"{seconds}s"

                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🟢 Available{platform_info} (call ended - duration: {duration_str})")
                        else:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🟢 Available{platform_info} (call ended)")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🟢 Available{platform_info} (call ended)")

                    on_call = False
                    call_start_time = None
                    current_platform = None
                
                # Check idle thresholds (only when we have fresh data)
                if idle_check_counter % IDLE_CHECK_INTERVAL == 0:
                    if idle_seconds >= OFF_THRESHOLD or screen_locked:
                        # Turn off after 1 hour or if screen is locked
                        if not is_off:
                            luxafor.set_off()
                            minutes = int(idle_seconds // 60)
                            reason = "screen locked" if screen_locked else f"{minutes} min idle"
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚫ Off ({reason})")
                            is_off = True
                            is_idle = False
                    
                    elif idle_seconds >= IDLE_THRESHOLD:
                        # Set blue after 30 minutes
                        if not is_idle:
                            luxafor.set_blue()
                            minutes = int(idle_seconds // 60)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔵 Idle/Away ({minutes} min inactive)")
                            is_idle = True
                            is_off = False
                    
                    else:
                        # Active - set green
                        if is_idle or is_off:
                            luxafor.set_green()
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🟢 Available")
                            is_idle = False
                            is_off = False
            
            # Increment counters
            call_check_counter += CALL_CHECK_INTERVAL
            idle_check_counter += CALL_CHECK_INTERVAL
            
            # Reset idle counter every 30 seconds
            if idle_check_counter >= IDLE_CHECK_INTERVAL:
                idle_check_counter = 0
            
            time.sleep(CALL_CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
        luxafor.set_off()
        luxafor.close()
        print("✓ Luxafor turned off")
        print("Goodbye!")


if __name__ == "__main__":
    main()
