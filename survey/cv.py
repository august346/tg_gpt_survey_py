import os
import subprocess
import tempfile
from typing import IO

from survey import gpt

HTML_TO_PDF_FP = os.environ.get("HTML_TO_PDF_FP", "/bin/wkhtmltopdf")


def save(data: dict, result_fp: str):
    with tempfile.NamedTemporaryFile(mode='w', encoding="utf-8-sig", suffix=".html") as file:     # type: IO[str]
        html = _get_html(data)

        file.write(html)
        file.seek(0)

        _html_to_pdf(file.name, dst_fp=result_fp)


def _get_html(data: dict) -> str:
    return gpt.GPT.get_cv_html(data)


def _html_to_pdf(src_fp: str, dst_fp: str):
    subprocess.run([HTML_TO_PDF_FP, src_fp, dst_fp])
