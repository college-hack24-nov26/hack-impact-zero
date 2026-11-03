import httpx


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:1.5b"


def build_readme_prompt(
    repository: dict,
    analysis: dict,
    existing_readme: str = "",
) -> str:
    """Build an evidence-based prompt for README generation."""

    return f"""
You are a technical documentation engineer.

Generate a comprehensive, professional README.md using ONLY
the repository evidence provided below.

STRICT RULES:
1. Never invent features, dependencies, commands, versions, or URLs.
2. Use only facts present in the supplied evidence.
3. If information is unavailable, write [Information not available].
4. Do not claim tests pass unless the evidence confirms it.
5. Do not invent installation or execution commands.
6. Use clear, descriptive explanations suitable for beginners.
7. Use valid GitHub-flavored Markdown.
8. Include useful headings and practical documentation.
9. Do not include fake badges or fake project statistics.
10. Return only the README Markdown. No introduction or commentary.

RECOMMENDED README STRUCTURE:
- Project title
- Project overview
- Key features (only verified features)
- Technology stack
- Repository structure
- Installation (only verified instructions)
- Usage (only verified commands)
- Requirements
- Project documentation links
- Contributing
- License

REPOSITORY METADATA:
{repository}

REPOSITORY ANALYSIS:
{analysis}

EXISTING README:
{existing_readme[:12000]}

Generate the improved README now.
""".strip()


async def generate_readme(
    repository: dict,
    analysis: dict,
    existing_readme: str = "",
) -> dict:
    """Generate README content using the local Ollama model."""

    prompt = build_readme_prompt(
        repository,
        analysis,
        existing_readme,
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 2048,
        },
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json=payload,
        )

        response.raise_for_status()
        result = response.json()

    generated_content = result.get("response", "").strip()

    if not generated_content:
        raise ValueError("The AI model returned an empty README.")

    return {
        "content": generated_content,
        "model": OLLAMA_MODEL,
        "provider": "ollama",
        "word_count": len(generated_content.split()),
    }