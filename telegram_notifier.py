import requests


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, enabled: bool):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled

    def send(self, text: str) -> None:
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
        }
        try:
            requests.post(url, json=payload, timeout=8)
        except Exception:
            # 알림 실패가 매매를 막지 않도록 무시
            return
