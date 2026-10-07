from pydantic import BaseModel

EnvObCode = str

class EnvOb(BaseModel):
    type: EnvObCode
    timestamp: int

    def describe(self) -> str:
        raise NotImplementedError("Subclasses should implement this method.")
