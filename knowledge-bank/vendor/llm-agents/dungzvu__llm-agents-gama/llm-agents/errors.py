from typing import TypeAlias
from models import PersonId
from enum import Enum

class ErrorCode(str, Enum):
    MOVE_NOT_FOUND = "MOVE_NOT_FOUND"
    PERSON_NOT_FOUND = "PERSON_NOT_FOUND"
    
ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.MOVE_NOT_FOUND: "Move not found.",
    ErrorCode.PERSON_NOT_FOUND: "Person not found.",
}

class BaseException(Exception):
    error_code: str
    detail_message: str

    def __init__(self):
        self.message = ERROR_MESSAGES[self.error_code]
        super().__init__(self.message)

    def __str__(self):
        return f"{self.error_code}: {self.message} ({self.detail_message})"

class MoveNotFoundExeption(BaseException):
    error_code = ErrorCode.MOVE_NOT_FOUND

    def __init__(self, move_id: str):
        self.move_id = move_id
        self.detail_message = f"Move id: {move_id}"
        super().__init__()
    
class PersonNotFoundException(BaseException):
    error_code = ErrorCode.PERSON_NOT_FOUND

    def __init__(self, person_id: PersonId):
        self.person_id = person_id
        self.detail_message = f"Person id: {person_id}"
        super().__init__()
    
