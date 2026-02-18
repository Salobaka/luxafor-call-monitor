#!/usr/bin/env python3
# pylint: disable=c-extension-no-member
"""
Luxafor Call Monitor for macOS - VERSION 7.0 (OPTIMIZED)
Improved resource efficiency with smart checking intervals

Usage:
    python3 luxafor_call_monitor.py [--brightness BRIGHTNESS]

Options:
    --brightness BRIGHTNESS    Set LED brightness (0-100, default: 75)
"""

import subprocess
import time
import sys
import argparse
from datetime import datetime

# Hardware
LUXAFOR_VENDOR_ID = 0x04d8
LUXAFOR_PRODUCT_ID = 0xf372

# Timing (seconds)
IDLE_CACHE_DURATION = 30
IDLE_THRESHOLD = 30 * 60
OFF_THRESHOLD = 60 * 60
MIN_CALL_DURATION = 60
CALL_CHECK_INTERVAL = 3
IDLE_CHECK_INTERVAL = 30

# UI
TITLE_TRUNCATE_LENGTH = 50
TEAMS_MIN_WINDOW_WIDTH = 800
TEAMS_MIN_WINDOW_HEIGHT = 600

# Browser meeting URL → (url_fragment, display_name)
MEETING_URL_PATTERNS = {
    "MEET": ("meet.google.com", "Google Meet"),
    "TEAMS": ("teams.microsoft.com", "Teams"),
    "ZOOM": ("zoom.us/j/", "Zoom"),
    "SLACK": ("slack.com/huddle", "Slack"),
}

BANNER = """\
============================================================
Luxafor Call Monitor - VERSION 7.0 (OPTIMIZED)
============================================================
Status Colors:
  🔴 RED    - On a call (DO NOT DISTURB)
  🟢 GREEN  - Available
  🔵 BLUE   - Idle/Away (30+ min inactive)
  ⚫ OFF    - Long idle (60+ min inactive)

Press Ctrl+C to stop
============================================================
"""


def _timestamp():
    """Current time as HH:MM:SS."""
    return datetime.now().strftime('%H:%M:%S')


def _format_duration(seconds):
    """Format seconds to human-readable duration string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _truncate(text, length=TITLE_TRUNCATE_LENGTH):
    """Truncate text with ellipsis if it exceeds length."""
    if len(text) > length:
        return text[:length] + "..."
    return text


# ── Luxafor USB Controller ──────────────────────────────────


class LuxaforController:
    """Controls Luxafor USB device using hidapi."""

    def __init__(self, brightness=75):
        self.device = None
        self.brightness = max(0, min(100, brightness))
        try:
            import hid
            self.hid = hid
            self.connect()
        except ImportError:
            print("ERROR: hidapi not installed. Installing...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "hidapi"],
                check=True,
            )
            import hid
            self.hid = hid
            self.connect()

    def connect(self):
        """Connect to Luxafor device."""
        try:
            self.device = self.hid.device()
            self.device.open(LUXAFOR_VENDOR_ID, LUXAFOR_PRODUCT_ID)
            print("✓ Connected to Luxafor device")
        except Exception as e:
            print(f"ERROR: Could not connect to Luxafor: {e}")
            print("Make sure your Luxafor is plugged in via USB")
            sys.exit(1)

    def _apply_brightness(self, value):
        """Scale a 0-255 colour value by the brightness percentage."""
        return int(value * self.brightness / 100)

    def set_color(self, red, green, blue, led=0xFF):
        """Set Luxafor color with brightness adjustment."""
        if not self.device:
            return
        red = self._apply_brightness(red)
        green = self._apply_brightness(green)
        blue = self._apply_brightness(blue)
        self.device.write([0, 1, led, red, green, blue, 0, 0])

    def set_red(self):
        """Set LED to red (on call)."""
        self.set_color(255, 0, 0)

    def set_green(self):
        """Set LED to green (available)."""
        self.set_color(0, 255, 0)

    def set_blue(self):
        """Set LED to blue (idle/away)."""
        self.set_color(0, 0, 255)

    def set_off(self):
        """Turn off LED."""
        self.set_color(0, 0, 0)

    def close(self):
        """Close connection to Luxafor device."""
        if self.device:
            self.device.close()


# ── Idle Detector ────────────────────────────────────────────


class IdleDetector:
    """Detects user idle time on macOS."""

    def __init__(self):
        self.debug = False
        self.last_idle_check = 0
        self.cached_idle_seconds = 0

    def get_idle_time_seconds(self, force=False):
        """Get idle time in seconds (cached to reduce system calls)."""
        current_time = time.time()
        if not force and (current_time - self.last_idle_check) < IDLE_CACHE_DURATION:
            return self.cached_idle_seconds

        try:
            result = subprocess.run(
                ['ioreg', '-c', 'IOHIDSystem'],
                capture_output=True, text=True, timeout=2,
            )
            for line in result.stdout.split('\n'):
                if 'HIDIdleTime' in line:
                    idle_ns = int(line.split('=')[1].strip())
                    self.cached_idle_seconds = idle_ns / 1_000_000_000
                    self.last_idle_check = current_time
                    if self.debug:
                        mins = int(self.cached_idle_seconds // 60)
                        secs = int(self.cached_idle_seconds % 60)
                        print(f"  [DEBUG] Idle time: {mins}m {secs}s")
                    return self.cached_idle_seconds
        except Exception as e:
            if self.debug:
                print(f"  [DEBUG] Idle check error: {e}")

        return self.cached_idle_seconds

    def is_screen_locked(self):
        """Check if the screen saver is running."""
        try:
            result = subprocess.run(
                ['osascript', '-e',
                 'tell application "System Events" to get running of screen saver preferences'],
                capture_output=True, text=True, timeout=2,
            )
            is_locked = 'true' in result.stdout.lower()
            if self.debug and is_locked:
                print("  [DEBUG] Screen is locked")
            return is_locked
        except Exception as e:
            if self.debug:
                print(f"  [DEBUG] Screen lock check error: {e}")
            return False


# ── Call Detector ────────────────────────────────────────────


class CallDetector:
    """Detects active calls on macOS using multiple methods."""

    def __init__(self):
        self.debug = False

    def _debug_log(self, platform, status, extra=""):
        """Log debug information for platform detection."""
        if not self.debug:
            return
        if isinstance(status, str):
            status_text = status
        else:
            status_text = "active" if status else "not detected"
        suffix = f" ({extra})" if extra else ""
        print(f"  [DEBUG] {platform}: {status_text}{suffix}")

    def _run_script(self, script, timeout=3):
        """Run AppleScript; returns 'NO' when the app isn't running."""
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode != 0:
                return "NO"
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            if self.debug:
                print("  [DEBUG] Script timeout (app may not be running)")
            return "NO"
        except Exception as e:
            if self.debug:
                print(f"  [DEBUG] Script exception: {e}")
            return "NO"

    # ── Desktop app detectors ────────────────────────────────

    def check_slack_huddle(self):
        """Check if Slack is in a huddle."""
        script = '''
        tell application "System Events"
            if exists (process "Slack") then
                set windowList to name of every window of process "Slack"
                repeat with windowName in windowList
                    if windowName contains "Huddle" and windowName does not contain "Start" then
                        return "YES"
                    end if
                end repeat
            end if
            return "NO"
        end tell
        '''
        is_active = self._run_script(script) == "YES"
        self._debug_log("Slack", is_active)
        return is_active

    def check_zoom_status(self):
        """Check if Zoom is in a meeting (any resolution, with or without screen sharing)."""
        script = '''
        tell application "System Events"
            if exists (process "zoom.us") then
                set windowList to name of every window of process "zoom.us"
                repeat with windowName in windowList
                    set lowerName to windowName as string
                    if windowName contains "Zoom Meeting" then return "YES"
                    if lowerName contains "zoom share" or lowerName contains "zoom floating video" then return "YES"
                    if lowerName contains "Annotation" and lowerName contains "Zoom" then return "YES"
                    if windowName contains "Meeting" and windowName does not contain "Zoom Workplace" then return "YES"
                    if windowName starts with "Zoom" and windowName contains "(" and windowName does not contain "Workplace" then return "YES"
                end repeat
                if (count of windowList) >= 3 then return "YES"
            end if
            return "NO"
        end tell
        '''
        is_meeting = self._run_script(script) == "YES"
        self._debug_log("Zoom", is_meeting)
        return is_meeting

    def check_teams_status(self):
        """
        Check if Teams is in a call.

        Uses separator counting to distinguish active meetings from tab views:
        - During meeting: "MeetingName | Microsoft Teams" (2 parts)
        - Post-meeting:   "Chat | MeetingName | Microsoft Teams" (3+ parts = tab view)
        """
        min_w = TEAMS_MIN_WINDOW_WIDTH
        min_h = TEAMS_MIN_WINDOW_HEIGHT
        script = f'''
        tell application "System Events"
            if exists (process "Microsoft Teams") then
                set windowList to name of every window of process "Microsoft Teams"
                repeat with windowName in windowList
                    -- Direct call/meeting indicators
                    if windowName contains " | Call" or windowName contains "Calling" then
                        return "YES"
                    end if

                    if windowName contains " | Microsoft Teams" then
                        -- Count " | " separators to detect tab views
                        -- 2 parts = "Title | Microsoft Teams" (potential meeting)
                        -- 3+ parts = "Tab | Title | Microsoft Teams" (tab view, not a meeting)
                        set AppleScript's text item delimiters to " | "
                        set titleParts to text items of (windowName as string)
                        set AppleScript's text item delimiters to ""
                        set partCount to count of titleParts

                        if partCount = 2 then
                            set titlePart to item 1 of titleParts
                            -- Check for "Meeting" keyword in title
                            if titlePart contains "Meeting" then
                                return "YES"
                            end if
                            -- Custom meeting title: use window size heuristic
                            -- Exclude known navigation sections
                            if titlePart is not "Activity" and titlePart is not "Chat" and titlePart is not "Calendar" and titlePart is not "Teams" then
                                try
                                    set w to window windowName of process "Microsoft Teams"
                                    set wSize to size of w
                                    set wW to item 1 of wSize
                                    set wH to item 2 of wSize
                                    if wW > {min_w} and wH > {min_h} then
                                        return "YES"
                                    end if
                                end try
                            end if
                        end if
                    end if
                end repeat
            end if
            return "NO"
        end tell
        '''
        is_call = self._run_script(script) == "YES"
        self._debug_log("Teams", is_call)
        return is_call

    def _check_messaging_app(self, process_name):
        """Generic detector for messaging apps (window titles + window count)."""
        script = f'''
        tell application "System Events"
            if exists (process "{process_name}") then
                set windowList to name of every window of process "{process_name}"
                repeat with windowName in windowList
                    if windowName contains "Call" or windowName contains "call" or windowName contains "Calling" then
                        return "YES"
                    end if
                end repeat
                if (count of windows of process "{process_name}") >= 2 then
                    return "YES"
                end if
            end if
            return "NO"
        end tell
        '''
        is_call = self._run_script(script) == "YES"
        self._debug_log(process_name, is_call, "window-based")
        return is_call

    def check_telegram_status(self):
        """Check if Telegram has a call."""
        return self._check_messaging_app("Telegram")

    def check_whatsapp_status(self):
        """Check if WhatsApp has a call."""
        return self._check_messaging_app("WhatsApp")

    def check_signal_status(self):
        """Check if Signal has a call."""
        return self._check_messaging_app("Signal")

    # ── Browser tab detector ─────────────────────────────────

    def check_browser_tabs(self):
        """Check browsers for meeting URLs; returns (bool, platform_name)."""
        browsers = [
            ("Google Chrome", "Chrome"),
            ("Safari", "Safari"),
            ("Microsoft Edge", "Edge"),
        ]

        url_checks = []
        for svc, (url, _) in MEETING_URL_PATTERNS.items():
            url_checks.append(
                f'if tabURL contains "{url}" then\n'
                f'                                return "{svc}:" & tabTitle & "|" & tabURL'
            )
        url_block = "\n                            else ".join(url_checks)

        for app_name, display_name in browsers:
            script = f'''
            tell application "{app_name}"
                if it is running then
                    repeat with w in windows
                        repeat with t in tabs of w
                            set tabURL to URL of t
                            set tabTitle to title of t
                            {url_block}
                            end if
                        end repeat
                    end repeat
                end if
                return "NO"
            end tell
            '''
            result = self._run_script(script, timeout=5)
            if result in ("NO", "ERROR", "TIMEOUT"):
                continue

            try:
                svc, rest = result.split(":", 1)
                title, _ = rest.split("|", 1)
                svc_label = MEETING_URL_PATTERNS.get(svc, (None, svc))[1]
                platform_name = f"{display_name} ({svc_label})"

                if self.debug:
                    print(f"  [DEBUG] {display_name}: {svc} meeting found")
                    print(f"  [DEBUG]   Tab: {_truncate(title)}")

                return True, platform_name
            except:  # pylint: disable=bare-except
                self._debug_log(display_name, "Meeting found")
                return True, display_name

        return False, None

    # ── Aggregated check ─────────────────────────────────────

    def is_on_call(self):
        """Check all platforms; returns (is_on_call, platform_name)."""
        if self.debug:
            print(f"\n[{_timestamp()}] Checking call status...")

        platforms = [
            (self.check_slack_huddle, "Slack Huddle (Desktop App)"),
            (self.check_zoom_status, "Zoom (Desktop App)"),
            (self.check_teams_status, "Microsoft Teams (Desktop App)"),
            (self.check_telegram_status, "Telegram (Desktop App)"),
            (self.check_whatsapp_status, "WhatsApp (Desktop App)"),
            (self.check_signal_status, "Signal (Desktop App)"),
        ]
        for check_fn, name in platforms:
            if check_fn():
                if self.debug:
                    print(f"  → ✓ {name} detected")
                return True, name

        detected, browser_name = self.check_browser_tabs()
        if detected:
            if self.debug:
                print(f"  → ✓ {browser_name} meeting detected")
            return True, browser_name

        if self.debug:
            print("  → No calls detected")
        return False, None


# ── Status Monitor ───────────────────────────────────────────


class StatusMonitor:
    """Coordinates call detection, idle detection, and LED state."""

    def __init__(self, luxafor, call_detector, idle_detector):
        self.luxafor = luxafor
        self.call_detector = call_detector
        self.idle_detector = idle_detector

        self.on_call = False
        self.is_idle = False
        self.is_off = False
        self.call_start_time = None
        self.current_platform = None
        self.idle_counter = 0

    def log(self, emoji, message):
        """Print a timestamped status line."""
        print(f"[{_timestamp()}] {emoji} {message}")

    def _handle_call_start(self, platform_name):
        """Transition to on-call state."""
        self.luxafor.set_red()
        self.call_start_time = time.time()
        self.current_platform = platform_name
        suffix = f" on {platform_name}" if platform_name else ""
        self.log("🔴", f"On call{suffix}")
        self.on_call = True
        self.is_idle = False
        self.is_off = False

    def _handle_call_end(self):
        """Transition back to available after a call."""
        self.luxafor.set_green()
        tag = f" [{self.current_platform}]" if self.current_platform else ""

        if self.call_start_time:
            duration = int(time.time() - self.call_start_time)
            if duration >= MIN_CALL_DURATION:
                dur = _format_duration(duration)
                self.log("🟢", f"Available{tag} (call ended - duration: {dur})")
            else:
                self.log("🟢", f"Available{tag} (call ended)")
        else:
            self.log("🟢", f"Available{tag} (call ended)")

        self.on_call = False
        self.call_start_time = None
        self.current_platform = None

    def _handle_idle(self, idle_seconds, screen_locked):
        """Update LED based on idle thresholds."""
        if idle_seconds >= OFF_THRESHOLD or screen_locked:
            if not self.is_off:
                self.luxafor.set_off()
                reason = "screen locked" if screen_locked else f"{int(idle_seconds // 60)} min idle"
                self.log("⚫", f"Off ({reason})")
                self.is_off = True
                self.is_idle = False

        elif idle_seconds >= IDLE_THRESHOLD:
            if not self.is_idle:
                self.luxafor.set_blue()
                self.log("🔵", f"Idle/Away ({int(idle_seconds // 60)} min inactive)")
                self.is_idle = True
                self.is_off = False

        elif self.is_idle or self.is_off:
            self.luxafor.set_green()
            self.log("🟢", "Available")
            self.is_idle = False
            self.is_off = False

    def tick(self):
        """Run one iteration of the monitoring loop."""
        in_call, platform = self.call_detector.is_on_call()

        # Idle check every IDLE_CHECK_INTERVAL seconds
        fresh_idle = self.idle_counter == 0
        idle_secs = self.idle_detector.get_idle_time_seconds(force=fresh_idle)
        screen_locked = self.idle_detector.is_screen_locked() if fresh_idle else False

        if in_call:
            if not self.on_call:
                self._handle_call_start(platform)
        else:
            if self.on_call:
                self._handle_call_end()
            if fresh_idle:
                self._handle_idle(idle_secs, screen_locked)

        self.idle_counter = (self.idle_counter + CALL_CHECK_INTERVAL) % IDLE_CHECK_INTERVAL


# ── Entry point ──────────────────────────────────────────────


def _get_brightness(args):
    """Resolve brightness from CLI args or interactive prompt."""
    if args.brightness is not None:
        brightness = max(0, min(100, args.brightness))
        print(f"✓ Brightness set to {brightness}% (from command line)")
        return brightness

    print("Set LED brightness (0-100, default 75, or press Enter): ", end='')
    try:
        raw = input().strip()
        if raw:
            brightness = max(0, min(100, int(raw)))
            print(f"✓ Brightness set to {brightness}%")
            return brightness
    except ValueError:
        print("Invalid input. Using default brightness: 75%")
    except:  # pylint: disable=bare-except
        pass

    print("✓ Using default brightness: 75%")
    return 75


def main():  # pylint: disable=too-many-locals
    """Main entry point: parse args, set up components, run loop."""
    parser = argparse.ArgumentParser(
        description='Luxafor Call Monitor - VERSION 7.0 (OPTIMIZED)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--brightness', type=int, default=None, metavar='LEVEL',
        help='Set LED brightness (0-100, default: 75)',
    )
    args = parser.parse_args()

    print(BANNER)
    brightness = _get_brightness(args)

    luxafor = LuxaforController(brightness=brightness)
    call_detector = CallDetector()
    idle_detector = IdleDetector()

    print("Enable debug mode? (y/n): ", end='')
    try:
        if input().strip().lower() == 'y':
            call_detector.debug = True
            idle_detector.debug = True
            print("✓ Debug mode enabled")
    except:  # pylint: disable=bare-except
        print("Using normal mode")

    print()
    monitor = StatusMonitor(luxafor, call_detector, idle_detector)
    luxafor.set_green()
    monitor.log("🟢", "Available")

    try:
        while True:
            monitor.tick()
            time.sleep(CALL_CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
        luxafor.set_off()
        luxafor.close()
        print("✓ Luxafor turned off")
        print("Goodbye!")


if __name__ == "__main__":
    main()
