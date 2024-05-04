### Requirements
- tested on python version 3.12  
- install requirements via command:
```shell
pip install -r requirements.txt
```

### Run bot
```shell
python main.py
```

### Environment Variables 
You need to create a `.env` file in the root of the project with the following environment variables:
```text
# required
OPENAI_API_KEY=<OPENAI_API_KEY>
TG_API_TOKEN=<TG_API_TOKEN>
# optional
#GPT_MODEL_NAME=gpt-4
#BASE_PROMPT="# Character\nВы HR специалист в компании [Название компании]. Вашей задачей является интервьюирование кандидатов на должность Marketing Manager. \n\n## Skills\n\n### Skill 1: Собирать данные кандидата\n- Узнайте и следующее: \n{unknown}\n- Уже известно:\n{known}\n\n### Skill 2: Полноценное интервью\n - Ведите длительный разговор до тех пор, пока не узнаете все данные указанные в Skill 1. Вежливо и профессионально общайтесь, соблюдайте при этом деловой этикет.\n \n## Constraints:\n- Не заканчивайте беседу до тех пор, пока не узнаете все данные. После того как все данные будут собраны, попрощайтесь и сообщите, что ответ по кандидатуре будет отправлен на указанную почту или вам позвонят на указанный номер телефона. При этом покажите в ответе эти контакты."
#HELP_TEXT=START / HELP
```

### Until MVP restrictions
- No logs.  
- Not for mass use, because SQLite is used which cannot parallelize queries. Therefore, do not try to check the work under load - the bot simply will not respond to two clients at once.  

### Bot Commands
`/help` or `/start` - help text  
`/выгрузи` - get .csv file with collected data  
`/очисти` - clears the database  
`/промпт new prompt text` - change prompt  
For changing params, use this format (new parameters separated by line breaks):
```text
/параметры
new_param1
new_param2
new_param3
```

**FYI**: After changing params or prompt, all collected user data will be deleted from the database. So if you need it, keep it before changing.
