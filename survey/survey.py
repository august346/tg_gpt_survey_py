from dataclasses import dataclass
from typing import Optional, Union

from . import db, gpt, tasks, utils


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

    _lang: Union[Optional[str], bool] = None

    @property
    def _data(self) -> dict:
        return self._db.get_chat_data(self.tg_chat_id) or {}

    @property
    def _tg_username(self) -> Optional[str]:
        return (self._db.get_tg_data(self.tg_chat_id) or {}).get(db.TgParam.username.value)

    def get_tg_username(self) -> Optional[str]:
        return self._tg_username

    def get_tokens(self) -> int:
        return self._data.get("tokens") or self._start_tokens

    def deduct_tokens(self, tokens: int):
        data: dict = self._data
        if "tokens" not in data:
            data["tokens"] = self._start_tokens

        data["tokens"] -= tokens

        self._db.set_chat_data(self.tg_chat_id, data)

    def get_params(self) -> list[Param]:
        data: dict = self._data
        if data.get("is_finished"):
            return []

        stored_params: dict = data.get("params") or {}

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

    def get_vacancy(self) -> Optional[str]:
        return self._data.get("vacancy")

    def set_vacancy(self, value: str):
        data: dict = self._data
        data["vacancy"] = value

        self._db.set_chat_data(self.tg_chat_id, data)

    def get_resume_key(self) -> Optional[str]:
        return self._data.get("resume")

    def set_resume_key(self, value: str):
        data: dict = self._data
        data["resume"] = value

        self._db.set_chat_data(self.tg_chat_id, data)

    def send_short_to_crm(self):
        tasks.integrate_with_crm.delay({
            "telegram_username": self._tg_username,
            "position": self.get_vacancy(),
            "full_name": "N/A",
        }, self.get_resume_key() or None)

    def send_full_to_crm(self):
        tasks.send_full_to_srm.delay(self.tg_chat_id)

    def translate(self, text: str) -> str:
        return utils.get_text(text, self.get_lang() or "en")

    def get_lang(self) -> Optional[str]:
        if self._lang is None:
            self._lang = self._db.get_lang(self.tg_chat_id) or False

        return self._lang or None

    def set_lang(self, value: str):
        self._lang = value

        self._db.set_lang(self.tg_chat_id, value)
