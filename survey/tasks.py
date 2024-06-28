import os
from dataclasses import asdict
from typing import Optional

from celery import shared_task
import requests
from bs4 import BeautifulSoup
from requests import Response

from survey import db, survey, gpt
from survey.storage import MinioClient

DB_URL = os.environ.get("DB_URL", "postgresql://survey:example@pgbouncer/survey")
CRM_API_KEY: str = os.environ["CRM_API_KEY"]
START_TOKENS: int = int(os.environ.get("START_TOKENS", 50_000))
SOURCE_ID: Optional[str] = None if (sid := os.environ.get("SOURCE_ID")) is None else int(sid)
CRM_URL: str = "https://smarthr.peopleforce.io/api/public/v2/recruitment/candidates"


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
def integrate_with_crm(self, candidate_data, resume):
    try:
        add_form(candidate_data, resume)
    except Exception as exc:
        raise self.retry(exc=exc)


def add_form(data: dict, resume: Optional[str]) -> Response:
    payload = data if SOURCE_ID is None else (data | {"source_id": SOURCE_ID})

    response = requests.post(
        CRM_URL,
        data=payload,
        headers={
            "Accept": "application/json",
            "X-API-KEY": CRM_API_KEY,
        },
        files={'resume': (resume, MinioClient().get(resume), 'application/octet-stream')} if resume else None
    )

    assert response.status_code == 201, f"failed crm integration: code={response.status_code}, text={response.text}"

    return response


@shared_task
def send_full_to_srm(tg_chat_id: int):
    sql_alchemy = db.SQLAlchemy(DB_URL)

    params, __ = sql_alchemy.get_params_and_prompt()
    user_survey = survey.UserSurvey(str(tg_chat_id), survey.Survey(params), sql_alchemy, START_TOKENS)

    params = user_survey.get_params()
    full: dict = gpt.GPT.get_crm_data(list(map(asdict, params))) | (
        {
            k: v
            for k, v in {
                "telegram_username": user_survey.get_tg_username(),
                "position": user_survey.get_vacancy()
            }.items()
            if v
        }
    )

    integrate_with_crm.delay(full, user_survey.get_resume_key() or None)
