from ninja import Schema
from pydantic import Field, field_validator
from typing import Optional

class ControlSchema(Schema):
    command: str = Field(..., description="Команда керування ботом: 'start' або 'stop'")

    @field_validator('command')
    @classmethod
    def validate_command(cls, value: str) -> str:
        if value not in ('start', 'stop'):
            raise ValueError("Command must be either 'start' or 'stop'")
        return value

class StatusResponseSchema(Schema):
    status: str = Field(..., description="Статус виконання запиту (success/error)")
    bot_status: str = Field(..., description="Поточний стан бота в системі (active/stopped)")
    message: Optional[str] = Field(None, description="Додаткове інформаційне повідомлення")