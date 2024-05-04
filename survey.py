from dataclasses import dataclass
from typing import Optional

import db
import gpt


@dataclass
class Survey:
    params: list[str]


@dataclass
class Param:
    index: int
    name: str
    value: Optional[str] = None


@dataclass
class UserSurvey:
    tg_chat_id: str
    survey: Survey

    @property
    def _data(self) -> dict:
        return db.SQLite3.get_chat_data(self.tg_chat_id) or {}

    def get_params(self) -> list[Param]:
        stored_params: dict = self._data.get("params") or {}

        return [
            Param(**{"index": str(ind), "name": param, "value": stored_params.get(str(ind))})
            for ind, param in enumerate(self.survey.params)
        ]

    def set_param(self, ind: int, value: str):
        data: dict = self._data
        if "params" not in data:
            data["params"] = {}

        data["params"][str(ind)] = value

        db.SQLite3.set_chat_data(self.tg_chat_id, data)

    def get_history(self) -> list[dict]:
        return self._data.get("messages") or []

    def add_user_answer(self, text: str):
        self._add_message(gpt.GPT.Role.USER.value, text)

    def _add_message(self, role: str, text: str):
        data: dict = self._data
        if "messages" not in data:
            data["messages"] = []

        data["messages"].append({"role": role, "content": text})
        db.SQLite3.set_chat_data(self.tg_chat_id, data)

    def add_assistant_question(self, text):
        self._add_message(gpt.GPT.Role.ASSISTANT.value, text)
