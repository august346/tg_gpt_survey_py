import csv
import json
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base()


class Config(Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True)
    data = Column(JSON)


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    tg_chat_id = Column(String)
    data = Column(JSON)


class SQLAlchemy:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def create_db(self, params: list[str], prompt: str):
        Base.metadata.create_all(self.engine)

        with self.Session() as session:
            if not session.query(Config).first():
                config = Config(data=json.dumps({"params": params, "prompt": prompt}, ensure_ascii=False))
                session.add(config)
                session.commit()

    def get_params_and_prompt(self) -> tuple[list[str], str]:
        with self.Session() as session:
            config = session.query(Config).first()
            data = json.loads(config.data)
            return data["params"], data["prompt"]

    def get_chat_data(self, tg_chat_id: str) -> Optional[dict]:
        with self.Session() as session:
            user = session.query(User).filter_by(tg_chat_id=tg_chat_id).first()
            return json.loads(user.data) if user else None

    def set_chat_data(self, tg_chat_id: str, data: dict):
        with self.Session() as session:
            user = session.query(User).filter_by(tg_chat_id=tg_chat_id).first()
            if user:
                user.data = json.dumps(data)
            else:
                user = User(tg_chat_id=tg_chat_id, data=json.dumps(data))
                session.add(user)
            session.commit()

    def clear(self):
        with self.Session() as session:
            session.query(User).delete()
            session.commit()

    def write_file(self, temp_file, params: list[str]):
        with self.Session() as session:
            rows = session.query(User.data).all()
            to_write = [params]
            for row in rows:
                data = json.loads(row[0]) if row[0] else {}
                params = data.get("params", {})
                max_ind = max([int(k) for k in params.keys()] or [0])
                to_append = [params.get(str(i), None) for i in range(max_ind + 1)]
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
            config = Config(data=json.dumps({"params": params, "prompt": prompt}, ensure_ascii=False))
            session.add(config)
            session.commit()
