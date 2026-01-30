import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.tests.models import Test, Question, AnswerOption

logger = logging.getLogger(__name__)

# Inlined from backend/domain/default_questions.py
DEFAULT_TEST_QUESTIONS = {
    "test2": [
        {
            "text": "☁ <b>Где вы будете работать большую часть времени?</b>",
            "options": [
                "🏠 Дома 100%",
                "🏢 В офисе 100%",
                "👔 80% территория / 20% Офис",
            ],
            "correct": 2,
            "feedback": [
                "❌ <i>Работа дома 100%</i>? Это было бы здорово, но в нашей компании личное присутствие играет ключевую роль.",
                "❌ <i>Работа в офисе 100%</i>? Возможно, но наши сотрудники часто выезжают к клиентам.",
                "✅ <i>Верно!</i> Наши сотрудники совмещают работу на территории и в офисе.",
            ],
        },
        {
            "text": "👔 <b>Какой внешний вид подходит для работы в нашей компании?</b>",
            "options": [
                "👚 Опрятный деловой стиль",
                "⚽ Спортивная форма",
                "🦙 Повседневная одежда",
            ],
            "correct": 0,
            "feedback": [
                "✅ <i>Идеально!</i> Мы придерживаемся smart casual стилю.",
                "❌ <i>Спортивная форма</i> подходит только для корпоративных мероприятий.",
                "❌ <i>Повседневная одежда</i> допустима, но только в пятницу.",
            ],
        },
        {
            "text": "📌 <b>Как вы планируете пройти ознакомительный день?</b>",
            "options": [
                "🏠 Дистанционно из дома",
                "🚗 Приеду в офис и на территорию",
                "🏢 Только в офис",
            ],
            "correct": 1,
            "feedback": [
                "❌ <i>Ознакомительный день</i> требует личного присутствия.",
                "✅ <i>Правильно!</i> Это лучший способ познакомиться с командой.",
                "❌ Нужно посетить и офис, и территорию.",
            ],
        },
        {
            "text": "👀 <b>Ознакомительный день</b>\nЧто вы будете делать вместе с наставником во время ознакомительного дня?\n",
            "options": [
                "Проводить холодные звонки к клиентам",
                "Наблюдать за реальными переговорами",
                "Заполнять отчетные документы",
            ],
            "correct": 1,
            "feedback": """✅ <i>Идеально!</i> Вы увидите:
— Как презентовать услуги за 10 минут
— Какие возражения встречаются чаще всего
☕ После встречи — разбор кейсов за кофе""",
        },
    ],
    "test1": [
        {
            "id": "fio",
            "prompt": "1‰ Введите ваше <b>ФИО</b> полностью:",
            "placeholder": "Иванов Иван Иванович",
        },
        {
            "id": "city",
            "prompt": "2‰ Ваш <b>город</b>?",
            "placeholder": "Например, Москва",
            "helper": "Укажите город проживания или ближайший крупный город.",
        },
        {
            "id": "age",
            "prompt": "3‰ Сколько вам <b>полных лет</b>?",
            "placeholder": "Например, 27",
        },
        {
            "id": "status",
            "prompt": "4‰ На данный момент вы <b>учитесь</b> / <b>работаете</b>?",
            "options": [
                "Учусь",
                "Работаю",
                "Ищу работу",
                "Предприниматель",
                "Другое",
            ],
        },
        {
            "id": "salary",
            "prompt": "5‰ <b>Желаемый уровень дохода</b> в первые 3 месяца?",
            "options": [
                "до 60 000 ›",
                "60 000 – 90 000 ›",
                "90 000 – 120 000 ›",
                "120 000+ ›",
                "Обсудим индивидуально",
            ],
        },
        {
            "id": "format",
            "prompt": "6‰ <b>Готовы работать</b> в гибридном формате: 70% территория / 30% офис?",
            "options": [
                "Да, готов",
                "Нужен гибкий график",
                "Пока не готов",
            ],
        },
        {
            "id": "sales_exp",
            "prompt": "7‰ Был ли у вас <b>опыт переговоров/продаж</b> или смежных областей? Опишите в 2–3 предложениях.",
            "placeholder": "Например: 2 года менеджером по продажа…",
        },
        {
            "id": "about",
            "prompt": "8‰ Что вас <b>мотивирует</b> в работе?",
            "placeholder": "Например: хочу расти профессионально и зарабатывать",
        },
        {
            "id": "skills",
            "prompt": "9‰ Какие <b>навыки</b> или качества помогают вам достигать целей?",
            "placeholder": "Например: коммуникабельность, настойчивость...",
        },
        {
            "id": "expectations",
            "prompt": "10‰ Чего вы <b>ожидаете</b> от работы у нас?",
            "placeholder": "Например: сильная команда, прозрачный доход",
        },
    ],
}

async def bootstrap_test_questions(session: AsyncSession) -> None:
    """
    Populate the database with default test questions if they don't exist.
    """
    logger.info("Checking for default test questions...")
    
    for test_slug, questions_data in DEFAULT_TEST_QUESTIONS.items():
        # Check if test exists
        result = await session.execute(select(Test).where(Test.slug == test_slug))
        test = result.scalars().first()
        
        if not test:
            logger.info(f"Creating test: {test_slug}")
            test = Test(slug=test_slug, title=f"Test {test_slug}") # specific title logic if needed
            session.add(test)
            await session.flush() # get ID
            
            for idx, q_data in enumerate(questions_data):
                # Handle different structures of test1 (form) vs test2 (quiz)
                
                # Common fields
                text = q_data.get("text") or q_data.get("prompt")
                if not text:
                    continue
                    
                q_key = q_data.get("id")
                
                # Extract payload (everything that isn't core column)
                payload = {}
                for k, v in q_data.items():
                    if k not in ["text", "prompt", "id", "options", "correct"]:
                        payload[k] = v
                
                q_type = "single_choice"
                if "options" not in q_data:
                     q_type = "text" # open ended if no options
                
                question = Question(
                    test_id=test.id,
                    text=text,
                    key=q_key,
                    type=q_type,
                    order=idx,
                    payload=payload if payload else None
                )
                session.add(question)
                await session.flush()
                
                options = q_data.get("options", [])
                correct_idx = q_data.get("correct")
                
                if options:
                    for opt_idx, opt_text in enumerate(options):
                        is_correct = False
                        if correct_idx is not None and opt_idx == correct_idx:
                            is_correct = True
                            
                        # points logic wasn't specified in default_questions, defaulting to 1 for correct?
                        points = 1.0 if is_correct else 0.0
                        
                        answer = AnswerOption(
                            question_id=question.id,
                            text=opt_text,
                            is_correct=is_correct,
                            points=points
                        )
                        session.add(answer)
            
    await session.commit()
    logger.info("Test questions bootstrap complete.")