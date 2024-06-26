import enum
import json
import os
from typing import Optional

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

GPT_MODEL_NAME = os.environ.get("GPT_MODEL_NAME", "gpt-4o")
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]


class GPT:
    class Role(enum.Enum):
        SYSTEM = "system"
        USER = "user"
        ASSISTANT = "assistant"

    @staticmethod
    def get_question(messages: list[dict], indexes: Optional[list[int]]) -> tuple[Optional[str], Optional[dict], int]:
        tools: dict = {} if indexes is None else {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "set_param",
                        "description": "Set parameter value by index",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "index": {
                                    "type": "integer",
                                    "enum": indexes,
                                    "description": "Index of the parameter",
                                },
                                "value": {
                                    "type": "string",
                                    "description": "Parameter value"
                                }
                            },
                            "required": ["index", "value"]
                        }
                    }
                }
            ]
        }

        client = OpenAI(api_key=OPENAI_API_KEY)

        completion = client.chat.completions.create(
            messages=messages,
            model=GPT_MODEL_NAME,
            **tools,
        )

        message: ChatCompletionMessage = completion.choices[0].message
        tokens: int = completion.usage.total_tokens

        if message.tool_calls:
            call_list = []
            for call in message.tool_calls:
                call_list.append({"args": json.loads(call.function.arguments), "call_id": call.id})
            return None, {"calls": call_list, "message": message.model_dump()}, tokens

        return completion.choices[0].message.content, None, tokens

    @staticmethod
    def get_crm_data(params: list) -> Optional[dict]:
        messages: list[dict] = [{
            "role": GPT.Role.SYSTEM.value,
            "content": open("files/categorize_params_prompt.txt", "r", encoding="utf-8").read().replace(
                "<params>", json.dumps(params, ensure_ascii=False, indent=2)
            )
        }]

        completion = OpenAI(api_key=OPENAI_API_KEY).chat.completions.create(
            messages=messages,
            model=GPT_MODEL_NAME,
            tool_choice="required",
            tools=[{
                "type": "function",
                "function": {
                    "name": "send_to_crm",
                    "description": "Send user data to CRM",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "full_name": {
                                "type": "string",
                                "description": "Full name of the candidate"
                            },
                            "email": {
                                "type": "string",
                                "description": "Email address of the candidate"
                            },
                            "location": {
                                "type": "string",
                                "description": "Location of the candidate"
                            },
                            "phone_numbers": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of phone numbers"
                            },
                            "skills": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of skills"
                            },
                            "urls": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of URLs"
                            }
                        },
                        "required": ["full_name"]
                    }
                }
            }],
        )

        message: ChatCompletionMessage = completion.choices[0].message

        if completion.choices[0].message.tool_calls:
            for call in message.tool_calls:
                return json.loads(call.function.arguments)
