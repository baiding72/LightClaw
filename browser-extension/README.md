# LightClaw Browser Bridge

Load this directory as an unpacked Chrome-compatible extension.

## What it does

- Reads the tabs in the current browser window
- Marks the active tab as the default target page
- Sends the tab list back to the LightClaw Task Runner page

## How to load

1. Open `chrome://extensions` or the equivalent extensions page in your Chromium browser.
2. Enable Developer Mode.
3. Click `Load unpacked`.
4. Select `/Users/baiding/Desktop/LightClaw/browser-extension`.
5. Open LightClaw in the same browser window.
6. On the Task Runner page, click `Sync Tabs`.

## Current scope

This first version only provides page context:

- active tab
- all tabs in the current window
- title, URL, tab id, window id

It does not yet control page DOM, clicks, or form filling inside the real browser tab.
