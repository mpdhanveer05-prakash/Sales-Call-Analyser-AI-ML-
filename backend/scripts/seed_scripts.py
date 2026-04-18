"""
Seed the default sales script into the database.
Run: python -m scripts.seed_scripts
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.script import Script

DEFAULT_SCRIPT_NAME = "Standard Outbound Sales Script v1"

DEFAULT_SCRIPT_CONTENT = """
OUTBOUND SALES CALL SCRIPT — Standard Template
================================================

[OPENING / GREETING]
"Hello, may I speak with [Prospect Name]? ... Hi [Name], this is [Agent Name] calling
from [Company]. How are you today?"

[INTRODUCTION]
"The reason for my call is that we help [target industry] companies [key benefit].
I wanted to see if that's something that might be relevant for you."

[PERMISSION TO CONTINUE]
"Do you have just 2-3 minutes? I promise I'll keep it brief."

[DISCOVERY QUESTIONS]
- "Can you tell me a bit about how you currently handle [pain point area]?"
- "What's working well? What are the biggest challenges?"
- "If you could wave a magic wand and fix one thing about [area], what would it be?"
- "How important is solving that for you right now?"

[VALUE PROPOSITION]
"Based on what you've shared, [Company] might be a great fit because..."
- Tie each benefit directly to a pain the prospect mentioned
- Use specifics: numbers, time saved, cost reduced

[HANDLING OBJECTIONS]
PRICE: "I understand budget is always a consideration. Let me ask — if cost weren't a factor,
would this be something you'd want? [Listen] Great — let me show you the ROI..."

TIMING: "That makes sense. When do you see a better window opening up? [Listen]
Can I schedule a follow-up for [specific date]?"

AUTHORITY: "Absolutely — who else would typically be involved in a decision like this?
Could we set up a call with both of you?"

NOT INTERESTED: "I appreciate your honesty. Just out of curiosity, is there anything
that would have made this more relevant?"

[CLOSING]
"Based on our conversation, I think there's a real fit here. The logical next step would be
[a 30-min demo / a proposal / a trial]. Are you free [day] at [time]?"

[COMPLIANCE / CLOSE]
- Recap any agreed next steps clearly
- "This call may have been recorded for quality purposes."
- Thank them for their time
""".strip()

DEFAULT_RUBRIC = {
    "required_points": [
        "Introduce yourself and company by name",
        "Ask permission to continue the call",
        "Ask at least one open-ended discovery question",
        "Address the prospect's specific pain point or need",
        "Explain the product/service benefit clearly",
        "Handle any objections raised",
        "Ask for a specific next step or commitment",
        "State required compliance disclosure",
    ],
    "prohibited_phrases": [
        "I guarantee",
        "risk-free",
        "limited time offer",
    ],
    "required_disclosures": [
        "This call may be recorded for quality purposes",
    ],
}


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Script).where(Script.is_active.is_(True)))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"Active script already exists: '{existing.name}' — skipping seed")
            return

        script = Script(
            name=DEFAULT_SCRIPT_NAME,
            content=DEFAULT_SCRIPT_CONTENT,
            rubric=DEFAULT_RUBRIC,
            is_active=True,
        )
        db.add(script)
        await db.commit()
        print(f"Seeded default script: '{DEFAULT_SCRIPT_NAME}'")


if __name__ == "__main__":
    asyncio.run(seed())
