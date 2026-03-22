from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path


class TelegramNotifier:
    def __init__(self, token: str | None, chat_id: str | None) -> None:
        self.token = (token or "").strip()
        self.chat_id = (chat_id or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, message: str) -> bool:
        if not self.enabled or not message.strip():
            return False
        data = urllib.parse.urlencode({"chat_id": self.chat_id, "text": message[:4000]}).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return bool(payload.get("ok"))

