import logging
import os
import tempfile
from copy import deepcopy
from dataclasses import asdict
from typing import Optional, IO

import telebot
from celery import shared_task
import requests
from bs4 import BeautifulSoup
from requests import Response

from survey import cv, db, survey, gpt, utils
from survey.storage import MinioClient

DB_URL = os.environ.get("DB_URL", "postgresql://survey:example@pgbouncer/survey")
CRM_API_KEY: str = os.environ["CRM_API_KEY"]
START_TOKENS: int = int(os.environ.get("START_TOKENS", 50_000))
SOURCE_ID: Optional[str] = None if (sid := os.environ.get("SOURCE_ID")) is None else int(sid)
CRM_CRATE_URL: str = "https://smarthr.peopleforce.io/api/public/v2/recruitment/candidates"


def get_crm_update_url(crm_candidate_id: int) -> str:
    return f"https://smarthr.peopleforce.io/api/public/v2/recruitment/candidates/{crm_candidate_id}"


@shared_task(bind=True, default_retry_delay=60, max_retries=1)
def scrape_vacancies(self):
    try:
        return collect()
    except Exception as exc:
        raise self.retry(exc=exc)


def collect():
    response = requests.get("https://smarthr.peopleforce.io/careers")
    assert response.status_code == 200, f"collect vacancies response.status_code={response.status_code}"
    html_content = response.content
    soup = BeautifulSoup(html_content, 'html.parser')
    vacancies = []

    for card in soup.find_all("div", class_="card card-hover"):
        h3 = card.find("h3")
        a = h3.find("a")
        vacancy_name = a.get_text(strip=True)
        vacancies.append(vacancy_name)

    vacancies = vacancies[::-1]

    db.SQLAlchemy(DB_URL).set_new_vacancies(vacancies)

    return vacancies


@shared_task(bind=True, default_retry_delay=60, max_retries=3)
def integrate_with_crm(self, tg_chat_id: str, candidate_data: dict, resume: Optional[str]):
    payload: dict = deepcopy(candidate_data)
    for param, value in list(payload.items()):
        if value and isinstance(value, list):
            payload.pop(param)
            payload[f"{param}[]"] = value

    my_db: db.SQLAlchemy = db.SQLAlchemy(DB_URL)
    crm_candidate_id: Optional[int] = my_db.get_crm_candidate_id(tg_chat_id)

    try:
        response = send_request(crm_candidate_id, payload, resume)
    except Exception as e:
        raise self.retry(exc=e)

    try:
        if crm_candidate_id is None:
            crm_candidate_id = response.json()["data"]["id"]
            my_db.set_crm_candidate_id(tg_chat_id, crm_candidate_id)
    except Exception as e:
        logging.error(f"An error occurred while setting {crm_candidate_id=} for {tg_chat_id=}: {e}")

    return response.status_code, response.text


def send_request(crm_candidate_id: Optional[int], data: dict, resume: Optional[str]) -> Response:
    url: str
    method: str
    if crm_candidate_id is None:
        method, url = "POST", CRM_CRATE_URL
    else:
        method, url = "PUT", get_crm_update_url(crm_candidate_id)

    payload = data if SOURCE_ID is None else (data | {"source_id": SOURCE_ID})

    response = requests.request(
        method=method,
        url=url,
        data=payload,
        headers={
            "Accept": "application/json",
            "X-API-KEY": CRM_API_KEY,
        },
        files={'resume': (resume, MinioClient().get(resume), 'application/octet-stream')} if resume else None
    )

    assert response.status_code in {200, 201}, (
        f"failed crm integration: response code={response.status_code}, text={response.text}; request {method=}, {url=}, {payload=}"
    )

    return response


@shared_task
def send_full_to_crm(tg_chat_id: str, data: dict, resume: Optional[str]):
    return integrate_with_crm(tg_chat_id, data, resume)


@shared_task
def finish_survey(tg_chat_id: int):
    sql_alchemy = db.SQLAlchemy(DB_URL)

    params, __ = sql_alchemy.get_params_and_prompt()
    user_survey = survey.UserSurvey(str(tg_chat_id), survey.Survey(params), sql_alchemy, START_TOKENS)

    params = user_survey.get_params()
    additional_data: dict = {
        k: v
        for k, v in {
            "telegram_username": user_survey.get_tg_username(),
            "position": user_survey.get_vacancy()
        }.items()
        if v
    }

    crm_data = gpt.GPT.get_crm_data(list(map(asdict, params))) | additional_data
    send_full_to_crm.delay(
        user_survey.tg_chat_id,
        crm_data,
        None
    )

    gen_cv_data = {p.name: p.value for p in params} | additional_data
    send_new_cv.delay(
        gen_cv_data,
        user_survey.get_lang() or "en",
        tg_chat_id
    )

    return gen_cv_data, crm_data


@shared_task
def send_new_cv(data: dict, lang: str, tg_chat_id: int):
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', encoding="utf-8-sig", delete=False, suffix=".pdf"
        ) as file:  # type: IO[str]
            cv.save(data, result_fp=file.name)
            file.seek(0)
            file.flush()

        with open(file.name, "rb") as file2:
            bot = telebot.TeleBot(os.environ["TG_API_TOKEN"], threaded=False)
            bot.send_document(tg_chat_id, file2, caption=utils.get_text("cv_bonus", lang))
    finally:
        os.remove(file.name)


