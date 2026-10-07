import uuid
from datetime import datetime
from agentsociety.survey.models import Survey, Page, Question, QuestionType

def personality_survey() -> Survey:
    survey_id = uuid.uuid4()
    
    # Create questions for the survey
    questions = [
        Question(
            name="scenario",
            title="你在参与一个抽奖活动，你可以任选其一，哪一个最符合你的偏好？",
            type=QuestionType.RADIO,
            choices=[
                "A. 直接获得1000元",
                "B. 有50%概率获得2500元，有50%概率获得0元",
            ]
        ),
    ]
    
    # Create the page containing all questions
    page = Page(
        name="prospect_theory",
        elements=questions
    )
    
    # Create the complete survey
    survey = Survey(
        id=survey_id,
        title="稳妥还是冒险？",
        description="请结合你的背景信息，回答问卷中的问题",
        pages=[page],
        created_at=datetime.now()
    )
    
    return survey


def happiness_survey() -> Survey:
    survey_id = uuid.uuid4()
    
    # Create questions for the survey
    questions = [
        Question(
            name="life_satisfaction",
            title="我对自己目前的生活感到满意。（1 = 非常不同意，7 = 非常同意）",
            type=QuestionType.RATING,
            min_rating=1,
            max_rating=7,
        ),
        Question(
            name="life_ideal",
            title="我的生活接近我理想中的状态。（1 = 非常不同意，7 = 非常同意）",
            type=QuestionType.RATING,
            min_rating=1,
            max_rating=7,
        ),
        Question(
            name="life_contentment",
            title="我对我的生活条件感到满意。（1 = 非常不同意，7 = 非常同意）",
            type=QuestionType.RATING,
            min_rating=1,
            max_rating=7,
        ),
        Question(
            name="life_achievement",
            title="到目前为止，我已经从生活中得到了我想要的大部分东西。（1 = 非常不同意，7 = 非常同意）",
            type=QuestionType.RATING,
            min_rating=1,
            max_rating=7,
        ),
        Question(
            name="life_change",
            title="如果能重新来过，我几乎不会改变什么。（1 = 非常不同意，7 = 非常同意）",
            type=QuestionType.RATING,
            min_rating=1,
            max_rating=7,
        ),
    ]
    
    # Create the page containing all questions
    page = Page(
        name="happiness",
        elements=questions
    )
    
    # Create the complete survey
    survey = Survey(
        id=survey_id,
        title="幸福指数调查",
        description="请根据你的真实想法回答问卷中的问题",
        pages=[page],
        created_at=datetime.now()
    )
    
    return survey
