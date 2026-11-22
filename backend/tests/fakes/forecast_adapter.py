"""Offline adapter for forecast integration tests; never imported by production."""


class ForecastAdapter:
    model_name = "gemini-2.5-flash"

    def __init__(self, answer=None):
        self.calls = 0
        self.answer = answer

    def forecast(self, digest, horizon_minutes, purchase_price):
        self.calls += 1
        answer = self.answer or {"direction": "UP", "confidence": "LOW",
            "reasons": [{"feature_ids": [digest["features"][0]["feature_id"]],
                         "text": "Xu hướng còn nhiều bất định."}], "risks": ["Biến động khó dự báo."]}
        return answer, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "key_index": None}
