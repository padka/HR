from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.core.settings import get_settings
from backend.domain.default_questions import DEFAULT_TEST_QUESTIONS
from backend.domain.tests.models import Test, Question, AnswerOption
from backend.core.db import async_session

async def seed_tests():
    print("🌱 Seeding tests from DEFAULT_TEST_QUESTIONS...")
    
    async with async_session() as session:
        # Check if we already have tests
        existing = await session.execute(select(Test))
        if existing.scalars().first():
            print("⚠️ Tests already exist in DB. Skipping seed.")
            return

        for test_slug, questions_data in DEFAULT_TEST_QUESTIONS.items():
            print(f"   Processing test: {test_slug}")
            
            # Create Test
            test = Test(
                title=f"Test {test_slug}", # Simple title generation
                slug=test_slug
            )
            session.add(test)
            await session.flush() # get ID

            for idx, q_data in enumerate(questions_data):
                # Handle test1 format (id, prompt, placeholder...)
                # Handle test2 format (text, options, correct, feedback...)
                
                q_text = q_data.get("text") or q_data.get("prompt") or "No text"
                q_key = q_data.get("id")
                
                # Extract payload (everything that isn't core column)
                payload = {}
                for k, v in q_data.items():
                    if k not in ["text", "prompt", "id", "options", "correct"]:
                        payload[k] = v
                
                # For test2, feedback might need to be in payload if it's per-question
                # But typically feedback corresponds to options.
                
                question = Question(
                    test_id=test.id,
                    text=q_text,
                    key=q_key,
                    order=idx,
                    type="single_choice" if "options" in q_data else "text",
                    payload=payload if payload else None
                )
                session.add(question)
                await session.flush()

                # Handle Options (test2 mainly)
                if "options" in q_data:
                    options = q_data["options"]
                    correct_idx = q_data.get("correct")
                    
                    for opt_idx, opt_text in enumerate(options):
                        is_correct = (opt_idx == correct_idx)
                        # We don't have points in default data, defaulting to 1.0 if correct?
                        # Or 0.0. User didn't specify points logic.
                        
                        option = AnswerOption(
                            question_id=question.id,
                            text=opt_text,
                            is_correct=is_correct,
                            points=1.0 if is_correct else 0.0
                        )
                        session.add(option)
        
        await session.commit()
        print("✅ Seeding complete.")

if __name__ == "__main__":
    try:
        asyncio.run(seed_tests())
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
