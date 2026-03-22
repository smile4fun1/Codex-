---
name: desktop-control
description: Control the local desktop on Windows with keyboard, mouse, and screenshots. Use when Codex needs to inspect the current screen, move or click the mouse, type text, send hotkeys, scroll, or capture screenshots to see what is happening on the user's PC.
---

# Desktop Control

Use `scripts/desktop_control.py` for deterministic local desktop actions on Windows.

## Scope

- Capture the current desktop to PNG for visual inspection.
- Read screen size and current cursor position.
- Move the mouse, click, double-click, right-click, and scroll.
- Type text and send single keys or hotkeys.

## Safety rules

- Treat desktop control as high-impact. Confirm before actions that can change data, submit forms, close apps, or type into unknown fields.
- Prefer `screenshot` before and after any click sequence when state matters.
- Prefer `move` + `position` before `click` if the target location is uncertain.
- Do not automate passwords, 2FA codes, or secrets.

## Commands

- Screenshot:
  - `python skills/desktop-control/scripts/desktop_control.py screenshot --out tmp/desktop.png`
- Screen info:
  - `python skills/desktop-control/scripts/desktop_control.py screen-size`
  - `python skills/desktop-control/scripts/desktop_control.py position`
- Mouse:
  - `python skills/desktop-control/scripts/desktop_control.py move --x 960 --y 540`
  - `python skills/desktop-control/scripts/desktop_control.py click --x 960 --y 540 --button left`
  - `python skills/desktop-control/scripts/desktop_control.py click --button right`
  - `python skills/desktop-control/scripts/desktop_control.py click --button left --double`
  - `python skills/desktop-control/scripts/desktop_control.py scroll --amount -400`
- Keyboard:
  - `python skills/desktop-control/scripts/desktop_control.py type --text "hello world"`
  - `python skills/desktop-control/scripts/desktop_control.py key --key enter`
  - `python skills/desktop-control/scripts/desktop_control.py hotkey --keys ctrl+l`

## Operating pattern

- For “see what’s on screen”, run `screenshot`.
- For “go there and click”, take a screenshot first, then `move`, then `click`.
- For “type into the current field”, confirm focus first with a screenshot or a deliberate click.
- For browser or app navigation, combine `hotkey`, `type`, and `key`.
