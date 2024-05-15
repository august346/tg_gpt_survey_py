import logging
import os
import tempfile

import telebot
from telebot import types

from survey import (db, gpt, survey, utils)


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


def _(key: str) -> str:
    return utils.get_text(key, "ru")


def get_question(user_survey: survey.UserSurvey, prompt: str, counter: int = 0) -> str:
    if counter >= 3:
        raise Exception("foo")

    params: list[str] = []
    for p in user_survey.get_params():
        new_line: str = f"[{p.index}] - {p.name} - " + (
            "? (need to ask)"
            if p.value is None
            else f"{p.value} (already set)"
        ) + "\n"
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
        return get_question(user_survey, prompt, counter + 1)

    if not question:
        raise Exception("bar")

    return question


def process_chat(tg_chat_id: int, user_text: str, bot):
    params, prompt = bot.db.get_params_and_prompt()
    user_survey = survey.UserSurvey(str(tg_chat_id), survey.Survey(params), bot.db, START_TOKENS)

    if user_survey.get_tokens() < 1:
        logging.info(f"{tg_chat_id} no tokens")
        return

    bot.send_chat_action(tg_chat_id, "typing")

    user_survey.add_user_answer(user_text)

    question: str = get_question(user_survey, prompt)

    user_survey.add_assistant_question(question)

    bot.send_message(tg_chat_id, question)


def send_welcome(message: types.Message, bot):
    bot.reply_to(message, HELP_TEXT)


def export_csv(message: types.Message, bot):
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', dir="./", encoding="utf-8-sig", delete=False, suffix=".csv"
        ) as temp_file:
            params, _ = bot.db.get_params_and_prompt()
            bot.db.write_file(temp_file, params, TG_PARAMS)

        with open(temp_file.name, "rb") as csv_file:
            bot.send_document(message.chat.id, csv_file)
    finally:
        os.remove(temp_file.name)


def clear(message: types.Message, bot):
    bot.db.clear()

    bot.send_message(message.chat.id, _("db_cleaned"))


def set_prompt(message: types.Message, bot):
    text = message.text.split('/set_prompt', 1)[-1].strip()

    if not all(word in text for word in ["{data}"]):
        bot.reply_to(message, _("invalid_prompt"))
        return

    bot.db.set_prompt(text)
    bot.db.clear()

    bot.reply_to(message, _("new_prompt_set"))


def set_params(message: types.Message, bot):
    text = message.text.split('/set_params', 1)[-1].strip()

    if not text:
        bot.reply_to(message, _("invalid_params"))
        return

    bot.db.set_params(utils.extract_params_from_text(text))
    bot.db.clear()

    bot.reply_to(message, _("new_params_set"))


def give_me_tokens(message: types.Message, bot):
    text = message.text.split('/give_me_tokens', 1)[-1].strip()

    if not all([text, text.isdigit()]):
        bot.reply_to(message, _("invalid_tokens"))
        return

    params, __ = bot.db.get_params_and_prompt()
    user_survey = survey.UserSurvey(str(message.chat.id), survey.Survey(params), bot.db, START_TOKENS)
    user_survey.deduct_tokens(-int(text))

    bot.reply_to(message, _("tokens_added"))


def answer(message: types.Message, bot):
    bot.db.create_if_not_exist(str(message.chat.id), message.chat.username)
    process_chat(message.chat.id, message.text, bot)


def main():
    sql_alchemy = db.SQLAlchemy(DB_URL)
    sql_alchemy.create_db(DEFAULT_PARAMS, BASE_PROMPT)

    bot = telebot.TeleBot(TG_API_TOKEN)
    bot.db = sql_alchemy

    bot.register_message_handler(send_welcome, commands=['help', 'start'], pass_bot=True)
    bot.register_message_handler(export_csv, commands=["export_csv"], pass_bot=True)
    bot.register_message_handler(clear, commands=["clear"], pass_bot=True)
    bot.register_message_handler(set_prompt, commands=["set_prompt"], pass_bot=True)
    bot.register_message_handler(set_params, commands=["set_params"], pass_bot=True)
    bot.register_message_handler(give_me_tokens, commands=["give_me_tokens"], pass_bot=True)
    bot.register_message_handler(answer, func=lambda message: True, pass_bot=True)

    logging.info("bot started")
    bot.infinity_polling()


if __name__ == '__main__':
    main()
