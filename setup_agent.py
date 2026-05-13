"""
ONE-TIME SETUP — run once, then store the printed IDs in aimee_agent_config.json.
Creates the reusable agent and environment that every session will reference.
"""

import json
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """\
You are Aimee — a AI professor with three decades of teaching experience.

## Voice & Style
- Blend personal narrative with domain principles — open with an anecdote when it adds warmth
- Mix medium sentences (15–25 words) with short, punchy declaratives
- Use em-dashes for asides—and rhetorical questions to engage
- Explain jargon naturally; favor active voice and confident phrasing
- Tone: measured optimism with a touch of wit
- Draw on specific names, numbers, and places from the knowledge base at /mnt/session/uploads/workspace/Aimee-AI/ — never fabricate them
- Prefer "That's genuinely fascinating" over "*laughs* That's a great question"

## Formatting
Math: use LaTeX syntax inside proper delimiters.
- Inline math: wrap in \\( ... \\) — e.g. \\(A \\cdot v = \\lambda v\\)
- Display math: wrap in \\[ ... \\] on its own line — e.g. \\[A \\cdot v = \\lambda v\\]
- Do NOT use bare parentheses or bare square brackets around math — they render as literal text.
- Do NOT use $...$ or $$...$.
"""


def setup() -> dict:
    print("Creating environment…")
    environment = client.beta.environments.create(
        name="aimee-kb-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    print(f"  ✓ environment: {environment.id}")

    print("Creating agent…")
    agent = client.beta.agents.create(
        name="Aimee Claude Agent",
        model="claude-sonnet-4-6",
        description="Aimee the AI Professor",
        system=SYSTEM_PROMPT,
        tools=[
            {
                "type": "agent_toolset_20260401",
                "default_config": {
                    "enabled": True,
                    "permission_policy": {"type": "always_allow"},
                },
                "configs": [],
            }
        ],
        skills=[
            {"type": "custom", "skill_id": "skill_01CTU6GZWPEFQeCx9cP1r9jp", "version": "latest"},
            {"type": "custom", "skill_id": "skill_01DywMbmtC7DXExMoo4ttUNh", "version": "latest"},
        ],
    )
    print(f"  ✓ agent:       {agent.id}  (version {agent.version})")

    config = {
        "agent_id": agent.id,
        "agent_version": agent.version,
        "environment_id": environment.id,
    }
    with open("aimee_agent_config.json", "w") as f:
        json.dump(config, f, indent=2)
    print("\nSaved → aimee_agent_config.json")
    return config


if __name__ == "__main__":
    setup()
