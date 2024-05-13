from dataclasses import dataclass
from typing import Optional

from . import db, gpt


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
    _db: db.SQLAlchemy
    _start_tokens: int

    @property
    def _data(self) -> dict:
        return self._db.get_chat_data(self.tg_chat_id) or {"tokens": self._start_tokens}

    def get_tokens(self) -> int:
        if "tokens" not in self._data:
            self._data["tokens"] = self._start_tokens

        return self._data["tokens"]

    def deduct_tokens(self, tokens: int):
        if "tokens" not in self._data:
            self._data["tokens"] = self._start_tokens

        self._data["tokens"] -= tokens

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

        self._db.set_chat_data(self.tg_chat_id, data)

    def get_history(self) -> list[dict]:
        return self._data.get("messages") or []

    def add_user_answer(self, text: str):
        self._add_message_by_role(gpt.GPT.Role.USER.value, text)

    def _add_message_by_role(self, role: str, text: str):
        self._add_message({"role": role, "content": text})

    def _add_message(self, message: dict):
        data: dict = self._data
        if "messages" not in data:
            data["messages"] = []

        data["messages"].append(message)
        self._db.set_chat_data(self.tg_chat_id, data)

    def add_assistant_question(self, text):
        self._add_message_by_role(gpt.GPT.Role.ASSISTANT.value, text)

    def add_func_call_request(self, message: dict):
        self._add_message(message)

    def add_func_call_result(self, call_id: str, func_name: str, func_resp: str):
        self._add_message({"role": "tool", "content": func_resp, "tool_call_id": call_id, "name": func_name})
