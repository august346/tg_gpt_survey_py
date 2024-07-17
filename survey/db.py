import csv
import enum
import logging
from typing import Optional, Any
from sqlalchemy import create_engine, Column, Integer, String, JSON, BigInteger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base()


class TgParam(enum.Enum):
    username = "username"


class Config(Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True)
    data = Column(JSON)


class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    lang = Column(String, nullable=True)
    tg_chat_id = Column(String, unique=True)
    tg_data = Column(JSON)
    data = Column(JSON)
    crm_candidate_id = Column(BigInteger, nullable=True)


class Vacancy(Base):
    __tablename__ = 'vacancy'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)


class SQLAlchemy:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def create_db(self, params: list[str], prompt: str):
        Base.metadata.create_all(self.engine)

        with self.Session() as session:
            if not session.query(Config).first():
                config = Config(data={"params": params, "prompt": prompt})
                session.add(config)
                session.commit()

    def get_params_and_prompt(self) -> tuple[list[str], str]:
        with self.Session() as session:
            config = session.query(Config).first()
            data = config.data
            return data["params"], data["prompt"]

    def get_chat_data(self, tg_chat_id: str) -> Optional[dict]:
        with self.Session() as session:
            user = session.query(Users).filter_by(tg_chat_id=tg_chat_id).first()
            return user.data if user else None

    def get_tg_data(self, tg_chat_id: str) -> Optional[dict]:
        with self.Session() as session:
            user = session.query(Users).filter_by(tg_chat_id=tg_chat_id).first()
            return user.tg_data if user else None

    def set_chat_data(self, tg_chat_id: str, data: dict):
        with self.Session() as session:
            user = session.query(Users).filter_by(tg_chat_id=tg_chat_id).first()
            if user:
                user.data = data
            else:
                user = Users(tg_chat_id=tg_chat_id, data=data, ensure_ascii=False)
                session.add(user)
            session.commit()

    def create_if_not_exist(self, tg_chat_id: str, tg_username: str):
        tg_data = {TgParam.username.value: tg_username}
        with self.Session() as session:
            user = session.query(Users).filter_by(tg_chat_id=tg_chat_id).first()
            if user:
                user.tg_data = tg_data
            else:
                user = Users(tg_chat_id=tg_chat_id, tg_data=tg_data, data={})
                session.add(user)
            session.commit()

    def clear(self):
        with self.Session() as session:
            session.query(Users).delete()
            session.commit()

    def write_file(self, temp_file, params: list[str], tg_params: list[str]):
        def formatted_username_or_same(key: str, value: str) -> Any:
            if key != TgParam.username.value:
                return value

            return value and f"@{value}"

        with self.Session() as session:
            rows = session.query(Users.tg_data, Users.data).all()
            to_write = [[*tg_params, *params]]
            for row in rows:
                tg_data, data = (row[i] if row[i] else {} for i in range(2))
                params = data.get("params", {})
                max_ind = max([int(k) for k in params.keys()] or [0])
                to_append = [
                    *(formatted_username_or_same(p, tg_data.get(p)) for p in tg_params),
                    *(params.get(str(i), None) for i in range(max_ind + 1))
                ]
                to_write.append(to_append)
            if not to_write:
                to_write = [["empty"]]
            csv_writer = csv.writer(temp_file)
            csv_writer.writerows(to_write)

    def set_prompt(self, prompt: str):
        params, _ = self.get_params_and_prompt()
        self._set_config(params, prompt)

    def set_params(self, params: list[str]):
        _, prompt = self.get_params_and_prompt()
        self._set_config(params, prompt)

    def _set_config(self, params, prompt):
        with self.Session() as session:
            session.query(Config).delete()
            config = Config(data={"params": params, "prompt": prompt})
            session.add(config)
            session.commit()

    def set_new_vacancies(self, values: list[str]):
        with self.Session() as session:
            try:
                session.query(Vacancy).delete()

                new_vacancies = [Vacancy(name=name) for name in values]
                session.add_all(new_vacancies)

                session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                logging.error(f"An error occurred while setting new vacancies: {e}")

    def get_vacancies(self):
        with self.Session() as session:
            return list(session.query(Vacancy).all())

    def get_vacancy_name_by_id(self, value: int):
        with self.Session() as session:
            return session.query(Vacancy).filter_by(id=value).first()

    def get_lang(self, tg_chat_id: str) -> Optional[dict]:
        with self.Session() as session:
            user = session.query(Users).filter_by(tg_chat_id=tg_chat_id).first()
            return user.lang if user else None

    def set_lang(self, tg_chat_id: str, value: str):
        with self.Session() as session:
            session.query(Users).filter_by(tg_chat_id=tg_chat_id).update({"lang": value})
            session.commit()

    def get_crm_candidate_id(self, tg_chat_id: str) -> Optional[int]:
        with self.Session() as session:
            return session.query(Users.crm_candidate_id).filter_by(tg_chat_id=tg_chat_id).first()[0]

    def set_crm_candidate_id(self, tg_chat_id: str, value: int):
        with self.Session() as session:
            session.query(Users).filter_by(tg_chat_id=tg_chat_id).update({"crm_candidate_id": value})
            session.commit()
