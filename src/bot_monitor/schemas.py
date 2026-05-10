from ninja import Schema

class ControlSchema(Schema):
    command: str  # 'start' або 'stop'
