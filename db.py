import csv
import json
import sqlite3
from sqlite3 import Connection
from typing import Optional


CONFIG_TABLE_NAME: str = "config"
USER_TABLE_NAME: str = "user"


class SQLite3:
    @classmethod
    def create_db(cls, params: list[str], prompt: str):
        with cls._get_conn() as con:
            cursor = con.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS {} (
                    id INTEGER PRIMARY KEY,
                    tg_chat_id TEXT,
                    data TEXT
                )
            '''.format(USER_TABLE_NAME))

            def table_exists(table_name):
                cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                result = cursor.fetchone()
                if result is not None and result[0] > 0:
                    return True

                return False

            if not table_exists(CONFIG_TABLE_NAME):
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS {} (
                        id INTEGER PRIMARY KEY,
                        data TEXT
                    )
                '''.format(CONFIG_TABLE_NAME))

                cursor.execute(
                    '''INSERT INTO {} (data) VALUES (?)'''.format(CONFIG_TABLE_NAME),
                    (json.dumps({"params": params, "prompt": prompt}, ensure_ascii=False),)
                )

            con.commit()

    @staticmethod
    def _get_conn() -> Connection:
        return sqlite3.connect("survey.sqlite")

    @classmethod
    def get_params_and_prompt(cls) -> tuple[list[str], str]:
        with cls._get_conn() as con:
            cursor = con.cursor()
            cursor.execute('''SELECT data FROM {}'''.format(CONFIG_TABLE_NAME))
            result = cursor.fetchall()

            for row in result:
                data = json.loads(row[0])
                return data["params"], data["prompt"]

    @classmethod
    def get_chat_data(cls, tg_chat_id: str) -> Optional[dict]:
        with cls._get_conn() as con:
            cursor = con.cursor()
            cursor.execute('''
                SELECT data FROM {}
                WHERE tg_chat_id = ?
                ORDER BY id
            '''.format(USER_TABLE_NAME), (tg_chat_id,))

            result = cursor.fetchall()

            for row in result:
                return json.loads(row[0])

    @classmethod
    def set_chat_data(cls, tg_chat_id: str, data: dict):
        data_str: str = json.dumps(data)

        with cls._get_conn() as con:
            cursor = con.cursor()

            if cls.get_chat_data(tg_chat_id) is None:
                cursor.execute('''
                                            INSERT INTO {} (tg_chat_id, data)
                                            VALUES (?, ?)
                                        '''.format(USER_TABLE_NAME), (tg_chat_id, data_str))
            else:
                cursor.execute('''
                            UPDATE {}
                            SET data = ?
                            WHERE tg_chat_id = ?
                        '''.format(USER_TABLE_NAME), (data_str, tg_chat_id))

            con.commit()

    @classmethod
    def clear(cls):
        with cls._get_conn() as con:
            cursor = con.cursor()
            cursor.execute("DELETE FROM {}".format(USER_TABLE_NAME))
            con.commit()

    @classmethod
    def write_file(cls, temp_file):
        with cls._get_conn() as con:
            cursor = con.cursor()
            cursor.execute("SELECT data FROM {}".format(USER_TABLE_NAME))

            rows = cursor.fetchall()

            to_write = []
            for data in [r[0] for r in rows if r[0]]:
                if isinstance(data := json.loads(data), dict):
                    if params := data.get("params", {}):
                        max_ind = int(max(params.items(), key=lambda x: x[0])[0])
                        to_append = [None] * (max_ind+1)
                        for ind, value in params.items():
                            to_append[int(ind)] = value

                        to_write.append(to_append)

            to_write = to_write or [["empty"]]

            csv_writer = csv.writer(temp_file)
            csv_writer.writerows(to_write)

    @classmethod
    def set_prompt(cls, prompt: str):
        params, _ = cls.get_params_and_prompt()
        cls._set_config(params, prompt)

    @classmethod
    def _set_config(cls, params, prompt):
        with cls._get_conn() as con:
            cursor = con.cursor()
            cursor.execute("DELETE FROM {}".format(CONFIG_TABLE_NAME))
            cursor.execute(
                '''INSERT INTO {} (data) VALUES (?)'''.format(CONFIG_TABLE_NAME),
                (json.dumps({"params": params, "prompt": prompt}, ensure_ascii=False),)
            )
            con.commit()

    @classmethod
    def set_params(cls, params: list[str]):
        _, prompt = cls.get_params_and_prompt()
        cls._set_config(params, prompt)
