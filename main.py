import os
import tempfile

import telebot
from dotenv import load_dotenv
from telebot import TeleBot, types

import db
import gpt
import survey

load_dotenv()

BASE_PROMPT: str = os.environ.get("BASE_PROMPT", "# Character\nВы HR специалист в компании [Название компании]. Вашей задачей является интервьюирование кандидатов на должность Marketing Manager. \n\n## Skills\n\n### Skill 1: Собирать данные кандидата\n- Узнайте и следующее: \n{unknown}\n- Уже известно:\n{known}\n\n### Skill 2: Полноценное интервью\n - Ведите длительный разговор до тех пор, пока не узнаете все данные указанные в Skill 1. Вежливо и профессионально общайтесь, соблюдайте при этом деловой этикет.\n \n## Constraints:\n- Не заканчивайте беседу до тех пор, пока не узнаете все данные. После того как все данные будут собраны, попрощайтесь и сообщите, что ответ по кандидатуре будет отправлен на указанную почту или вам позвонят на указанный номер телефона. При этом покажите в ответе эти контакты.")
HELP_TEXT: str = os.environ.get("HELP_TEXT", "START / HELP")

LIMIT_HISTORY: int = 5000

TG_API_TOKEN: str = os.environ.get("TG_API_TOKEN")

DEFAULT_PARAMS: list[str] = ["ФИО", "телефон", "почта", "пол"]


def get_question(user_survey: survey.UserSurvey, prompt: str, counter=0) -> str:
    if counter >= 3:
        raise Exception("foo")

    known_params: list[survey.Param] = []
    unknown_params: list[tuple[int, str]] = []
    for p in user_survey.get_params():
        if p.value is None:
            unknown_params.append((p.index, p.name))
        else:
            known_params.append(p)

    known_text = "\n".join([f"param_name: `{p.name}`, param_value: `{p.value}`" for p in known_params])
    unknown_text = "\n".join([f"[{ind}] - `{p}`" for ind, p in unknown_params])

    system_message: str = prompt.format(
        known=known_text,
        unknown=unknown_text or "- все данные собраны, больше ничего не надо. Заканчивайте разговор",
    )

    len_counter: int = len(system_message)

    to_send_reversed: list[dict] = []
    for message in user_survey.get_history()[::-1]:
        len_counter += len(message["content"])
        if len_counter >= LIMIT_HISTORY:
            break
        to_send_reversed.append(message)

    question, function = gpt.GPT.get_question(
        [{"role": gpt.GPT.Role.SYSTEM.value, "content": system_message}, *to_send_reversed[::-1]],
        params=unknown_text or None
    )

    if function:
        for param in function["params"]:
            user_survey.set_param(param["index"], param["value"])
        return get_question(user_survey, prompt, counter+1)

    if not question:
        raise Exception("bar")

    return question


def process_chat(tg_chat_id: int, user_text: str, t_bot: TeleBot):
    params, prompt = db.SQLite3.get_params_and_prompt()
    user_survey = survey.UserSurvey(str(tg_chat_id), survey.Survey(params))

    user_survey.add_user_answer(user_text)

    question: str = get_question(user_survey, prompt)

    user_survey.add_assistant_question(question)

    t_bot.send_message(tg_chat_id, question)


bot = telebot.TeleBot(TG_API_TOKEN)


@bot.message_handler(commands=['help', 'start'])
def send_welcome(message: types.Message):
    bot.reply_to(message, HELP_TEXT)


@bot.message_handler(commands=['выгрузи'])
def download(message: types.Message):
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir="./", encoding="utf-8-sig", delete=False, suffix=".csv") as temp_file:
            db.SQLite3.write_file(temp_file)

        with open(temp_file.name, "rb") as csv_file:
            bot.send_document(message.chat.id, csv_file)
    finally:
        os.remove(temp_file.name)


@bot.message_handler(commands=['очисти'])
def clear(message: types.Message):
    db.SQLite3.clear()

    bot.send_message(message.chat.id, "База очищена")


@bot.message_handler(commands=['промпт'])
def change_prompt(message):
    text = message.text.split('/промпт', 1)[-1].strip()

    if not all(word in text for word in ["{known}", "{unknown}"]):
        bot.reply_to(message, f"Невалидный промпт")

    db.SQLite3.set_prompt(text)
    db.SQLite3.clear()

    bot.reply_to(message, f"Новый промт принят. Старые данные удалены.")


@bot.message_handler(commands=['параметры'])
def change_params(message):
    text = message.text.split('/параметры', 1)[-1].strip()

    if not text:
        bot.reply_to(message, f"Невалидные параметры")

    db.SQLite3.set_params(list(filter(bool, [x.strip() for x in text.split("\n")])))
    db.SQLite3.clear()

    bot.reply_to(message, f"Новые параметры приняты. Старые данные удалены.")


@bot.message_handler(func=lambda message: True)
def echo_message(message: types.Message):
    bot.send_chat_action(message.chat.id, "typing")
    process_chat(message.chat.id, message.text, bot)


def main():
    db.SQLite3.create_db(DEFAULT_PARAMS, BASE_PROMPT)

    bot.infinity_polling()


if __name__ == '__main__':
    main()
