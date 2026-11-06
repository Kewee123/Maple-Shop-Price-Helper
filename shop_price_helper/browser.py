"""Local browser assistance for the MesoWatch client-side search."""
from __future__ import annotations

import os
import base64
import subprocess


class BrowserAutomationUnavailable(RuntimeError):
    """The browser could not be controlled through macOS automation."""


def search_mesowatch(
    item_name: str,
    *,
    anchor: tuple[int, int, int, int] | None = None,
    screen_size: tuple[int, int] | None = None,
    avoid_rect: tuple[int, int, int, int] | None = None,
) -> None:
    """Open MesoWatch and select the first result matching `item_name`.

    Chrome must allow automation from Apple Events. When that permission is
    absent, the caller can fall back to opening the page and copying the name.
    """
    if not item_name.strip():
        raise ValueError("item name is empty")
    if os.uname().sysname != "Darwin":
        raise BrowserAutomationUnavailable("automatic browser control is macOS-only")

    browser = os.environ.get("MESO_WATCH_BROWSER", "Google Chrome")
    if browser != "Google Chrome":
        raise BrowserAutomationUnavailable(
            "automatic control currently supports Google Chrome only"
        )
    encoded_name = base64.b64encode(item_name.encode("utf-8")).decode("ascii")
    typed_js = (
        "(() => {const input=document.querySelector('#search');"
        "if (!input) throw new Error('MesoWatch search box not found');"
        f"const name=atob('{encoded_name}');input.scrollIntoView({{block:'center'}});"
        "input.focus();input.select();"
        "const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;"
        "setter.call(input,name);"
        "input.dispatchEvent(new InputEvent('input',{bubbles:true,data:name,inputType:'insertText'}));"
        "input.dispatchEvent(new Event('change',{bubbles:true}));"
        "input.dispatchEvent(new Event('blur',{bubbles:true}));"
        "return btoa(input.value);})()"
    )
    click_js = (
        "(() => {const result=document.querySelector('.item-select');"
        "if (!result) return 'missing';result.click();return 'clicked';})()"
    )

    def apple_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    placement = ""
    if anchor and screen_size:
        left, top, right, bottom = anchor
        screen_width, screen_height = screen_size
        gap = 12
        margin = 20
        browser_width = min(900, max(480, int(screen_width * 0.58)))
        browser_height = min(520, max(380, int(screen_height * 0.60)))
        below_height = screen_height - bottom - gap - margin
        browser_height = min(browser_height, max(260, below_height))
        if avoid_rect:
            game_left, game_top, game_right, game_bottom = avoid_rect
            available_left = max(margin, game_right + gap)
            available_width = screen_width - available_left - margin
            if available_width >= 480:
                browser_width = min(browser_width, available_width)
                window_left = available_left
            else:
                window_left = max(margin, screen_width - browser_width - margin)
        else:
            window_left = max(margin, screen_width - browser_width - margin)
        # Keep MesoWatch below the helper when possible. This is also the
        # first placement that avoids the MapleStory window's right edge.
        if below_height >= 260:
            window_top = bottom + gap
        else:
            window_top = max(margin, screen_height - browser_height - margin)
        window_right = window_left + browser_width
        window_bottom = window_top + browser_height
        placement = (
            f"set bounds of targetWindow to {{{window_left}, {window_top}, "
            f"{window_right}, {window_bottom}}}\n"
        )

    script = r'''
on run
    tell application "Google Chrome"
        activate
        if (count windows) = 0 then make new window
        set targetWindow to missing value
        set targetTab to missing value
        set targetIndex to 0
        repeat with wRef in (get windows)
            set w to contents of wRef
            set tabNumber to 0
            repeat with tRef in (get tabs of w)
                set tabNumber to tabNumber + 1
                set t to contents of tRef
                if (URL of t contains "meso.watch") then
                    set targetWindow to w
                    set targetTab to t
                    set targetIndex to tabNumber
                    exit repeat
                end if
            end repeat
            if targetTab is not missing value then exit repeat
        end repeat
        if targetTab is missing value then
            set targetWindow to front window
            set targetTab to make new tab at end of tabs of targetWindow with properties {URL:"https://meso.watch/"}
            set targetIndex to (count tabs of targetWindow)
            delay 2
        end if
        __PLACEMENT__
        set index of targetWindow to 1
        set active tab index of targetWindow to targetIndex
        tell targetTab
            repeat 30 times
                delay 0.25
                try
                    if (execute javascript "document.readyState === 'complete' && (() => {const e=document.querySelector('#search'); if (!e) return false; const r=e.getBoundingClientRect(); return !e.disabled && r.width > 0 && r.height > 0})()") is "true" then exit repeat
                end try
            end repeat
            set typedResult to execute javascript "__TYPED_JS__"
            if typedResult is not "__ITEM_B64__" then error "MesoWatch search text was not entered"
            repeat 40 times
                delay 0.25
                try
                    set resultCount to execute javascript "document.querySelectorAll('.item-select').length"
                    if resultCount > 0 then
                        set clickResult to execute javascript "__CLICK_JS__"
                        if clickResult is "clicked" then return "clicked"
                    end if
                end try
            end repeat
            error "MesoWatch did not render a matching item"
        end tell
    end tell
end run
'''
    script = (script.replace("__PLACEMENT__", placement)
                   .replace("__TYPED_JS__", apple_string(typed_js))
                   .replace("__CLICK_JS__", apple_string(click_js))
                   .replace("__ITEM_B64__", encoded_name))
    try:
        result = subprocess.run(["osascript", "-"], input=script, text=True,
                                capture_output=True, check=True, timeout=22)
        if "clicked" not in result.stdout:
            raise BrowserAutomationUnavailable(
                f"Chrome did not confirm the item click: {result.stderr.strip() or 'no result'}"
            )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        raise BrowserAutomationUnavailable(
            detail or "Chrome rejected the automation request"
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise BrowserAutomationUnavailable(
            "allow JavaScript from Apple Events in Chrome, then try again"
        ) from exc


def open_mesowatch_fallback(item_name: str) -> None:
    """Keep the current browser state and let the caller copy the name."""
    return None


def open_chrome_automation_settings() -> None:
    """Activate Chrome; its Apple Events switch is in the Develop menu."""
    if os.uname().sysname != "Darwin":
        raise BrowserAutomationUnavailable("Chrome automation settings are macOS-only")
    browser = os.environ.get("MESO_WATCH_BROWSER", "Google Chrome")
    try:
        subprocess.run(["open", "-a", browser], check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BrowserAutomationUnavailable("Google Chrome could not be opened") from exc
