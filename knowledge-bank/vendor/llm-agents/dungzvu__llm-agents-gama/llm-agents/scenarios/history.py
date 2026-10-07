
from functools import partial
import json
from typing import Optional
from settings import settings


class HistoryStreamLog:
    _instance = None

    @classmethod
    def get_instance(cls):
        """
        Get the singleton instance of HistoryStreamLog.
        If it does not exist, create it with the specified file path.
        :param file_path: The path to the log file.
        :return: The singleton instance of HistoryStreamLog.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    """
    A class to represent a log of history stream events. 
    This will log to the file in jsonl format.
    Lazy flushing is used to ensure that logs are written to the file immediately.
    The file is created if it does not exist.
    The file is opened in append mode, so new logs are added to the end of the file.
    """
    def __init__(self, file_path: str = None):
        self.file_path = file_path

        self.log_shortterm_memory = partial(self.log, context="shortterm_memory")
        self.log_longterm_memory = partial(self.log, context="longterm_memory")
        self.log_travel_plan = partial(self.log, context="travel_plan")
        self.log_query_travel_plan = partial(self.log, context="query_travel_plan")

    def log(self, context: str, timestamp: int, person_id: str, message: str, activity_id: Optional[str] = None, data: Optional[dict] = None):
        """
        Log a message with the specified person ID, message, and optional data.
        :param person_id: The ID of the person.
        :param message: The message to log.
        :param data: Optional additional data to log.
        """
        log_entry = {
            "context": context,
            "timestamp": timestamp,
            "person_id": person_id,
            "message": message,
            "activity_id": activity_id,
            "data": data or {}
        }
        file_path = self.file_path or settings.app.history_file_v2
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
