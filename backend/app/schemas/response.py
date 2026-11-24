from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    code: str = "1000"
    message: str = "OK"
    data: Optional[T] = None

class ErrorCodes:
    OK = "1000"
    USER_NOT_VALIDATED = "9995"
    USER_EXISTED = "9996"
    METHOD_INVALID = "9997"
    TOKEN_INVALID = "9998"
    EXCEPTION_ERROR = "9999"
    CANNOT_CONNECT_DB = "1001"
    PARAMETER_NOT_ENOUGH = "1002"
    PARAMETER_TYPE_INVALID = "1003"
    PARAMETER_VALUE_INVALID = "1004"
    UNKNOWN_ERROR = "1005"
    FILE_SIZE_TOO_BIG = "1006"
    FILE_FORMAT_INVALID = "1007"
    MAXIMUM_NUMBER_OF_IMAGES = "1008"
    NOT_ACCESS = "1009"
    ACTION_DONE_PREVIOUSLY = "1010"
    COULD_NOT_PUBLISH = "1011"
    LIMITED_ACCESS = "1012"
