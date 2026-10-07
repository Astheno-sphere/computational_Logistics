import uuid
from datetime import datetime
from enum import Enum
from typing import Any, List, Dict
from pydantic import BaseModel, Field, field_validator


class QuestionType(str, Enum):
    TEXT = "text"
    RADIO = "radiogroup"
    CHECKBOX = "checkbox"
    BOOLEAN = "boolean"
    RATING = "rating"
    MATRIX = "matrix"


class Question(BaseModel):
    name: str
    title: str
    type: QuestionType
    choices: List[str] = []
    columns: List[str] = []
    rows: List[str] = []
    required: bool = True
    min_rating: int = 1
    max_rating: int = 5

    @field_validator("choices", mode="before")
    @classmethod
    def parse_choices(cls, value: Any) -> List[str]:
        if isinstance(value, list):
            choices = []
            for item in value:
                if isinstance(item, dict):
                    if "text" in item:
                        choices.append(item["text"])
                    else:
                        raise ValueError(
                            "choices must be a list of strings or dictionaries"
                        )
                elif isinstance(item, str):
                    choices.append(item)
                else:
                    raise ValueError(
                        "choices must be a list of strings or dictionaries"
                    )
            return choices
        else:
            raise ValueError("choices must be a list")


class Page(BaseModel):
    name: str
    elements: List[Question]


class Survey(BaseModel):
    """
    Represents a survey with metadata and associated pages containing questions.
    """

    id: uuid.UUID
    """Unique identifier for the survey"""
    title: str = ""
    """Title of the survey"""
    description: str = ""
    """Description of the survey"""
    pages: List[Page]
    """List of pages in the survey"""
    responses: Dict[str, dict] = {}
    """Dictionary mapping response IDs to their data"""
    created_at: datetime = Field(default_factory=datetime.now)
    """Timestamp of when the survey was created"""

    def to_prompt(self) -> List[str]:
        """
        Convert the questionnaire into a list of strings, where each string represents one question.
        
        - **Description**:
            - Converts the survey into a list of individual question prompts, each containing the survey context and one specific question.
        
        - **Returns**:
            - `List[str]`: A list of strings, each representing one question with its context and instructions.
        """
        question_prompts = []
        
        # Create the survey context that will be included in each question
        survey_context = f"""Survey Title: {self.title}
Survey Description: {self.description}

Please answer the following question in the specified format:

"""
        
        question_count = 1
        for page in self.pages:
            for question in page.elements:
                # Start with survey context for each question
                prompt = survey_context
                prompt += f"Question {question_count}: {question.title}\n"

                # Generate different prompts based on the types of questions
                if question.type == QuestionType.RADIO:
                    prompt += "Options: " + ", ".join(question.choices) + "\n"
                    prompt += "Please select ONE option\n"
                    prompt += "Format: Please reply with ONLY the selected option text, no additional content.\n"

                elif question.type == QuestionType.CHECKBOX:
                    prompt += "Options: " + ", ".join(question.choices) + "\n"
                    prompt += "You can select MULTIPLE options\n"
                    prompt += "Format: Please reply with ONLY the selected option texts separated by commas, no additional content.\n"

                elif question.type == QuestionType.RATING:
                    prompt += (
                        f"Rating range: {question.min_rating} - {question.max_rating}\n"
                    )
                    prompt += "Please provide a rating within the range\n"
                    prompt += f"Format: Please reply with ONLY a number between {question.min_rating} and {question.max_rating}, no additional content.\n"

                elif question.type == QuestionType.MATRIX:
                    prompt += "Rows: " + ", ".join(question.rows) + "\n"
                    prompt += "Columns: " + ", ".join(question.columns) + "\n"
                    prompt += "Please select ONE column option for EACH row\n"
                    prompt += "Format: Please reply with ONLY the row-column pairs in format 'Row: Column', one per line, no additional content.\n"

                elif question.type == QuestionType.TEXT:
                    prompt += "Please provide a text response\n"
                    prompt += "Format: Please provide your text response directly, no additional formatting.\n"

                elif question.type == QuestionType.BOOLEAN:
                    prompt += "Options: Yes, No\n"
                    prompt += "Please select either Yes or No\n"
                    prompt += "Format: Please reply with ONLY 'Yes' or 'No', no additional content.\n"

                prompt += "\nAnswer: [Your response here]\n"
                
                # Add instructions for this specific question
                prompt += "\nPlease ensure your response matches the question type requirements and is clear and specific."
                
                question_prompts.append(prompt)
                question_count += 1

        return question_prompts
