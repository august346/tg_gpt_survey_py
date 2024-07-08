import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Optional, Callable

import telebot
from telebot import types
from telebot.handler_backends import BaseMiddleware

from survey import (db, gpt, survey, utils, storage)

logging.basicConfig(level=logging.INFO)

DB_URL: str = os.environ.get("DB_URL", "postgresql://survey:example@pgbouncer/survey")

BASE_PROMPT: str = os.environ.get(
    "BASE_PROMPT",
    "\n".join(open("files/default_prompt.txt", "r", encoding="utf-8").readlines())
)

DEFAULT_PARAMS: list[str] = utils.extract_params_from_text(
    os.environ.get(
        "DEFAULT_PARAMS",
        "\n".join(open("files/default_params.txt", "r", encoding="utf-8").readlines())
    )
)
HELP_TEXT: str = os.environ.get("HELP_TEXT", "START / HELP")

LIMIT_HISTORY: int = int(os.environ.get("LIMIT_HISTORY", 7_000))
START_TOKENS: int = int(os.environ.get("START_TOKENS", 50_000))

TG_API_TOKEN: str = os.environ["TG_API_TOKEN"]
TG_PARAMS: list[str] = ["username"]


my_db = db.SQLAlchemy(DB_URL)
my_db.create_db(DEFAULT_PARAMS, BASE_PROMPT)

minio = storage.MinioClient()
minio.create_buckets()


@dataclass
class Config:
    params: list[str]
    prompt: str


class Mixin:
    config: Config
    user: survey.UserSurvey


class MyMessage(types.Message, Mixin):
    pass


class MyCallbackQuery(types.CallbackQuery, Mixin):
    pass


def get_question(user_survey: survey.UserSurvey, prompt: str, counter: int = 0) -> str:
    if counter >= 3:
        raise Exception("foo")

    without_answers: int = 0
    params: list[str] = []
    for p in user_survey.get_params():
        if p.value is None:
            to_add = "? (need to ask)"
            without_answers -= 1
        else:
            to_add = f"{p.value} (already set)"
        new_line = f"[{p.index}] - {p.name} - " + to_add + "\n"
        params.append(new_line)

    system_message: str = prompt.format(data="\n".join(params))

    len_counter: int = len(system_message)

    to_send_reversed: list[dict] = []
    for message in user_survey.get_history()[::-1]:
        len_counter += len(message["content"] or "")
        if len_counter >= LIMIT_HISTORY:
            break
        to_send_reversed.append(message)

    question, callbacks, tokens = gpt.GPT.get_question(
        [{"role": gpt.GPT.Role.SYSTEM.value, "content": system_message}, *to_send_reversed[::-1]],
        indexes=list(range(len(user_survey.survey.params)))
    )

    user_survey.deduct_tokens(tokens)

    if callbacks:
        user_survey.add_func_call_request(callbacks["message"])
        for call in callbacks["calls"]:
            args = call["args"]
            user_survey.set_param(args["index"], args["value"])
            user_survey.add_func_call_result(call["call_id"], "set_param", "success")

        no_more_questions: bool = sum([-1 if p.value is None else 0 for p in user_survey.get_params()]) == 0
        if without_answers < 0 and no_more_questions:
            user_survey.send_full_to_crm()

        return get_question(user_survey, prompt, counter + 1)

    if not question:
        raise Exception("Didn't get question from gpt api")

    return question


def process_chat(user_survey: survey.UserSurvey, prompt: str, tg_chat_id: int, user_text: str, bot: telebot.TeleBot):
    if user_survey.get_lang() is None:
        choose_language(tg_chat_id, user_survey.translate("choose_language"), utils.DICTIONARY["langs"], bot)
        return

    if user_survey.get_vacancy() is None:
        send_vacancies(tg_chat_id, user_survey.translate("vacancies"), bot)
        return

    if user_survey.get_resume_key() is None:
        ask_about_resume(user_survey.translate, tg_chat_id, bot)
        return

    if user_survey.get_tokens() < 1:
        logging.info(f"{tg_chat_id} no tokens")
        return

    bot.send_chat_action(tg_chat_id, "typing")

    user_survey.add_user_answer(user_text)

    question: str = get_question(user_survey, prompt)

    user_survey.add_assistant_question(question)

    bot.send_message(tg_chat_id, question)


def send_welcome(message: MyMessage, bot: telebot.TeleBot):
    choose_language(message.chat.id, message.user.translate("choose_language"), utils.DICTIONARY["langs"], bot)


def choose_language(chat_id: int, text: str, langs: dict[str, str], bot: telebot.TeleBot):
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton(text=lang_text, callback_data=f"set_lang:{lang_code}")
        for lang_code, lang_text in langs.items()
    ]
    markup.add(*buttons)
    bot.send_message(chat_id, text, reply_markup=markup)


def set_language(call: MyCallbackQuery, bot: telebot.TeleBot):
    lang_code: str = call.data.split(":")[1]
    tg_chat_id: int = call.message.chat.id

    call.user.set_lang(lang_code)

    bot.delete_message(tg_chat_id, call.message.id)
    send_vacancies(call.message.chat.id, call.user.translate("vacancies"), bot)


def export_csv(message: MyMessage, bot: telebot.TeleBot):
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', dir="./", encoding="utf-8-sig", delete=False, suffix=".csv"
        ) as temp_file:
            my_db.write_file(temp_file, message.config.params, TG_PARAMS)

        with open(temp_file.name, "rb") as csv_file:
            bot.send_document(message.chat.id, csv_file)
    finally:
        os.remove(temp_file.name)


def clear(message: MyMessage, bot: telebot.TeleBot):
    my_db.clear()

    bot.send_message(message.chat.id, message.user.translate("db_cleaned"))


def prompt_f(message: MyMessage, bot: telebot.TeleBot):
    text = message.text.split('/prompt', 1)[-1].strip()

    if not text:
        bot.send_message(message.chat.id, "Current prompt:\n{}".format(message.config.prompt))
        return

    if not all(word in text for word in ["{data}"]):
        bot.reply_to(message, message.user.translate("invalid_prompt"))
        return

    my_db.set_prompt(text)
    my_db.clear()

    bot.reply_to(message, message.user.translate("new_prompt_set"))


def params_f(message: MyMessage, bot: telebot.TeleBot):
    text = message.text.split('/params', 1)[-1].strip()

    if not text:
        bot.send_message(message.chat.id, "Current params:\n{}".format('\n'.join(message.config.params)))
        return

    my_db.set_params(utils.extract_params_from_text(text))
    my_db.clear()

    bot.reply_to(message, message.user.translate("new_params_set"))


def give_me_tokens(message: MyMessage, bot: telebot.TeleBot):
    text = message.text.split('/give_me_tokens', 1)[-1].strip()

    if not all([text, text.isdigit()]):
        bot.reply_to(message, message.user.translate("invalid_tokens"))
        return

    message.user.deduct_tokens(-int(text))

    bot.reply_to(message, message.user.translate("tokens_added"))


def answer(message: MyMessage, bot: telebot.TeleBot):
    process_chat(message.user, message.config.prompt, message.chat.id, message.text, bot)


def send_vacancies(chat_id: int, text: str, bot: telebot.TeleBot):
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = list(
        map(
            lambda v: types.InlineKeyboardButton(text=v.name, callback_data=f"set_vacancy:{v.id}"),
            my_db.get_vacancies()
        )
    )
    markup.add(*buttons)
    bot.send_message(chat_id, text, reply_markup=markup)


def set_vacancy(call: MyCallbackQuery, bot: telebot.TeleBot):
    vacancy_id: int = int(call.data.split(":")[1])
    tg_chat_id: int = call.message.chat.id

    vacancy: Optional[db.Vacancy] = my_db.get_vacancy_name_by_id(vacancy_id)
    if vacancy is None:
        send_vacancies(tg_chat_id, call.user.translate("old_vacancies"), bot)
        return

    call.user.set_vacancy(vacancy.name)

    bot.delete_message(tg_chat_id, call.message.id)
    ask_about_resume(call.user.translate, tg_chat_id, bot)


def ask_about_resume(translate: Callable[[str], str], tg_chat_id: int, bot: telebot.TeleBot):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            text=translate("want_to_send_resume"),
            callback_data="want_to_send_resume"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            text=translate("skip_send_resume"),
            callback_data="skip_send_resume"
        )
    )
    bot.send_message(tg_chat_id, translate("ask_resume"), reply_markup=markup)


def want_to_send_resume(call: MyCallbackQuery, bot: telebot.TeleBot):
    tg_chat_id: int = call.message.chat.id

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            text=call.user.translate("skip_send_resume"),
            callback_data="skip_send_resume"
        )
    )

    bot.delete_message(tg_chat_id, call.message.id)
    bot.send_message(tg_chat_id, call.user.translate("welcome_send_resume"), reply_markup=markup)


def skip_send_resume(call: MyCallbackQuery, bot: telebot.TeleBot):
    tg_chat_id: int = call.message.chat.id

    if call.user.get_resume_key() is None:
        call.user.set_resume_key("")

    bot.delete_message(tg_chat_id, call.message.id)
    process_chat(call.user, call.config.prompt, tg_chat_id, call.user.translate("lets_go"), bot)


def handle_document(message: MyMessage, bot: telebot.TeleBot):
    if message.user.get_resume_key():
        return

    document = message.document

    if document.file_name.rsplit(".", 1)[-1].lower() not in ["pdf", "doc", "docx"]:
        bot.reply_to(message, message.user.translate("invalid_cv_format"))
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            text=message.user.translate("accept_document"),
            callback_data=f"accept_document"
        )
    )

    bot.reply_to(message, message.user.translate("confirm_document"), reply_markup=markup)


def accept_document(call: MyCallbackQuery, bot: telebot.TeleBot):
    tg_chat_id: int = call.message.chat.id

    document_message = call.message.reply_to_message
    document = document_message.document
    file_info = bot.get_file(document.file_id)
    data = bot.download_file(file_info.file_path)

    call.user.set_resume_key(
        minio.save(
            document.file_name,
            data,
            document_message.content_type,
            document.file_size,
        )
    )
    call.user.send_short_to_crm()

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            text=call.user.translate("confirm_create_new_resume"),
            callback_data="confirm_create_new_resume"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            text=call.user.translate("finish"),
            callback_data="finish"
        )
    )

    bot.delete_message(tg_chat_id, call.message.id)
    bot.send_message(tg_chat_id, call.user.translate("ask_create_new_resume"), reply_markup=markup)


def confirm_create_new_resume(call: MyCallbackQuery, bot: telebot.TeleBot):
    tg_chat_id: int = call.message.chat.id

    bot.delete_message(tg_chat_id, call.message.id)
    process_chat(call.user, call.config.prompt, call.message.chat.id, call.user.translate("lets_go"), bot)


def finish(call: MyCallbackQuery, bot: telebot.TeleBot):
    tg_chat_id: int = call.message.chat.id

    bot.delete_message(tg_chat_id, call.message.id)
    bot.send_message(tg_chat_id, call.user.translate("thanks_finish"))


class LangMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.update_types = ['message', 'callback_query']
    
    def pre_process(self, obj, data):
        chat: types.Chat = obj.chat if isinstance(obj, types.Message) else obj.message.chat
        chat_id: int = chat.id
        username: Optional[str] = chat.username
        my_db.create_if_not_exist(str(chat_id), username)

        params, prompt = my_db.get_params_and_prompt()
        obj.config = Config(params=params, prompt=prompt)

        obj.user = survey.UserSurvey(str(chat_id), survey.Survey(params), my_db, START_TOKENS)

    def post_process(self, message, data, exception):
        pass


def main():
    bot = telebot.TeleBot(TG_API_TOKEN, use_class_middlewares=True)

    bot.register_message_handler(send_welcome, commands=['help', 'start'], pass_bot=True)
    bot.register_message_handler(export_csv, commands=["export_csv"], pass_bot=True)
    bot.register_message_handler(clear, commands=["clear"], pass_bot=True)
    bot.register_message_handler(prompt_f, commands=["prompt"], pass_bot=True)
    bot.register_message_handler(params_f, commands=["params"], pass_bot=True)
    bot.register_message_handler(give_me_tokens, commands=["give_me_tokens"], pass_bot=True)
    bot.register_message_handler(handle_document, content_types=['document'], pass_bot=True)
    bot.register_message_handler(answer, func=lambda message: True, pass_bot=True)
    bot.register_callback_query_handler(
        set_vacancy, func=lambda call: call.data.startswith("set_vacancy:"), pass_bot=True
    )
    bot.register_callback_query_handler(
        want_to_send_resume, func=lambda call: call.data == "want_to_send_resume", pass_bot=True
    )
    bot.register_callback_query_handler(
        skip_send_resume, func=lambda call: call.data == "skip_send_resume", pass_bot=True
    )
    bot.register_callback_query_handler(
        accept_document, func=lambda call: call.data == "accept_document", pass_bot=True
    )
    bot.register_callback_query_handler(
        confirm_create_new_resume, func=lambda call: call.data == "confirm_create_new_resume", pass_bot=True
    )
    bot.register_callback_query_handler(
        set_language, func=lambda call: call.data.startswith("set_lang:"), pass_bot=True
    )
    bot.register_callback_query_handler(finish, func=lambda call: call.data == "finish", pass_bot=True)

    bot.setup_middleware(LangMiddleware())

    logging.info("bot started")
    bot.infinity_polling()


if __name__ == '__main__':
    main()
