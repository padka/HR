from sqladmin import ModelView
from backend.domain.tests.models import Test, Question, AnswerOption

class TestAdmin(ModelView, model=Test):
    name = "Test"
    name_plural = "Tests"
    icon = "fa-solid fa-clipboard-question"
    
    column_list = [Test.id, Test.title, Test.slug]
    column_searchable_list = [Test.title, Test.slug]
    form_columns = [Test.title, Test.slug]

class QuestionAdmin(ModelView, model=Question):
    name = "Question"
    name_plural = "Questions"
    icon = "fa-solid fa-question"
    
    column_list = [Question.id, Question.test_id, Question.key, Question.text, Question.type, Question.order, Question.payload]
    column_sortable_list = [Question.test_id, Question.order, Question.key]
    column_searchable_list = [Question.text, Question.key]
    form_columns = [Question.test, Question.key, Question.text, Question.type, Question.order, Question.payload]

class AnswerOptionAdmin(ModelView, model=AnswerOption):
    name = "Answer Option"
    name_plural = "Answer Options"
    icon = "fa-solid fa-list-ul"
    
    column_list = [AnswerOption.id, AnswerOption.question_id, AnswerOption.text, AnswerOption.is_correct, AnswerOption.points]
    column_searchable_list = [AnswerOption.text]
    form_columns = [AnswerOption.question, AnswerOption.text, AnswerOption.is_correct, AnswerOption.points]
