### Run bot
```shell
docker compose build && docker compose up -d
```

### Environment Variables 
You need to create a `.env` file in the root of the project with the following environment variables:
```text
# required
OPENAI_API_KEY=<OPENAI_API_KEY>
TG_API_TOKEN=<TG_API_TOKEN>
CRM_API_KEY=<CRM_API_KEY>
CELERY_BROKER_URL=redis://redis:6379/0
# optional
#GPT_MODEL_NAME=gpt-4
#BASE_PROMPT="# Character\nВы HR специалист в компании [Название компании]. Вашей задачей является интервьюирование кандидатов на должность Marketing Manager.\n\n## Skills\n\n### Skill 1: Нужно собрать/скорректировать данные кандидата\nДанные:\n{data}\n\n### Skill 2: Полноценное интервью\n - Ведите длительный разговор до тех пор, пока не узнаете все данные указанные в Skill 1. Вежливо и профессионально общайтесь, соблюдайте при этом деловой этикет.\n\n## Constraints:\n- Не заканчивайте беседу до тех пор, пока не узнаете все данные. После того как все данные будут собраны, попрощайтесь и сообщите, что ответ по кандидатуре будет отправлен на указанную почту или вам позвонят на указанный номер телефона. При этом покажите в ответе эти контакты."
#HELP_TEXT=START / HELP
#LIMIT_HISTORY=7000
#START_TOKENS=50000
#BACKEND_URL=db+postgresql://survey:example@localhost:5432/survey
#MINIO_URL=localhost:9000
#MINIO_ACCESS_KEY=minio
#MINIO_SECRET_KEY=minio123
#MINIO_BUCKET_NAME=cvs
#BROKER_URL=redis://redis:6379/0
#SOURCE_ID=24615   # default - without source_id in crm integration request
```

### Bot Commands
`/help` or `/start` - help text  
`/export_csv` - get .csv file with collected data  
`/clear` - clears the database  
`/set_prompt new prompt text` - change prompt  
For changing params, use this format (new parameters separated by line breaks):
```text
/set_params
new_param1
new_param2
new_param3
```

**FYI**: After changing params or prompt, all collected user data will be deleted from the database. So if you need it, keep it before changing.
