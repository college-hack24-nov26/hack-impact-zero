
import httpx


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:1.5b"
OLLAMA_TIMEOUT = 180.0
MAX_EXISTING_README_LENGTH = 12000
MAX_PREDICT_TOKENS = 2048


def build_readme_prompt(
    repository: dict,
    analysis: dict,
    existing_readme: str = "",
) -> str:
    """Build a detailed, evidence-grounded README generation prompt."""

    existing_readme = (existing_readme or "")[:MAX_EXISTING_README_LENGTH]

    return f"""
You are a senior technical writer and software documentation engineer.

TASK:
Create a comprehensive, professional, beginner-friendly README.md
for the GitHub repository described in the evidence below.

Your objective is to help a new developer understand:
- What the project does.
- What problem it addresses.
- Which features are actually implemented.
- How its architecture and components work.
- Which technologies it uses.
- How to install, configure, run, and test it when verified instructions exist.

STRICT ACCURACY RULES:
1. Use ONLY information supported by the supplied repository evidence.
2. Never invent features, dependencies, technologies, commands,
   installation steps, versions, API endpoints, or URLs.
3. Never present planned features as implemented features.
4. Never invent benchmark scores, performance statistics, or test results.
5. Never claim that tests pass unless actual test evidence confirms it.
6. If information is unavailable, write:
   [Information not available]
7. Never repeat the same explanation unnecessarily.
8. Avoid generic filler and meaningless marketing language.
9. Explain technical concepts in simple, descriptive English.
10. Use valid GitHub-flavored Markdown.
11. Return ONLY the complete README Markdown.
12. Do not include your reasoning or introductory commentary.

DOCUMENTATION STRUCTURE:

# 1. Project Title
- Use the actual repository name.
- Add a concise descriptive subtitle.
- Explain the project's purpose in one sentence.

# 2. Project Overview
- Explain what the project does.
- Describe the problem it addresses when evidence supports it.
- Explain its high-level approach.
- Identify intended users when known.
- Provide enough detail for a beginner to understand the project.

# 3. Key Features
- Include all verified implemented features.
- Explain what each feature does.
- Describe its practical benefit.
- Use descriptive subsections when useful.
- Do not invent capabilities.

# 4. Technology Stack
- Identify verified programming languages, frameworks,
  libraries, databases, and development tools.
- Explain the observed responsibility of each technology.
- Do not infer dependencies from file names alone.

# 5. How the Project Works
- Explain the verified processing workflow.
- Describe the relationship between major components.
- Include a Mermaid diagram only when the architecture
  can be established from the supplied evidence.
- Never invent connections between components.

# 6. Repository Structure
- Present important directories and files in a code block.
- Explain the responsibility of each verified component.
- Focus on meaningful project files.
- Do not invent directory contents.

# 7. Requirements
- List verified runtime and software requirements.
- Include versions only when explicitly available.
- Distinguish required tools from optional tools.

# 8. Installation and Setup
- Provide only commands supported by documentation
  or configuration evidence.
- Explain each verified setup step.
- Never fabricate commands.
- If setup instructions cannot be established,
  explicitly state that information is unavailable.

# 9. Usage
- Explain how to use the project.
- Include verified commands and examples.
- Document actual API endpoints when available.
- Explain supported inputs and outputs when evidence exists.
- Never invent example responses.

# 10. Configuration
- Document verified environment variables and settings.
- Explain their purpose when known.
- Never include real credentials, tokens, or secrets.
- Never invent configuration options.

# 11. API Documentation
- Document actual endpoints only when API evidence exists.
- Include HTTP methods, paths, parameters, and responses
  only when verified.
- Use tables when useful.
- Do not invent API behavior.

# 12. Testing and Validation
- Document verified testing tools and commands.
- Include test results only when actual results are supplied.
- Do not claim successful tests without evidence.

# 13. Troubleshooting
- Include only known problems and verified solutions.
- Avoid invented errors or unsupported fixes.

# 14. Contributing
- Explain contribution instructions when documented.
- Otherwise mark the information as unavailable.

# 15. License
- Include the actual license only when verified.
- Never assume an open-source license.

# 16. Project Links
- Include verified repository and documentation URLs only.
- Never create fictional links.

WRITING QUALITY:
- Be descriptive, specific, and technically useful.
- Explain features instead of merely naming them.
- Prefer clear paragraphs over excessive bullet lists.
- Use meaningful headings and subsections.
- Use tables for structured technical information.
- Use code blocks for verified commands and examples.
- Keep explanations understandable to beginner developers.
- Avoid repetitive statements and unnecessary promotional language.
- Do not produce empty sections filled with generic text.
- Do not sacrifice accuracy to increase document length.

BADGE HANDLING:
- Do not generate badges yourself.
- Do not invent Shields.io URLs.
- Do not create fake repository statistics.
- Preserve existing badges only when relevant.
- The application inserts verified repository-specific badges separately.

REPOSITORY METADATA:
{repository}

REPOSITORY STRUCTURE AND ANALYSIS:
{analysis}

EXISTING README:
{existing_readme}

Generate the complete, detailed README.md now.
""".strip()


async def generate_readme(
    repository: dict,
    analysis: dict,
    existing_readme: str = "",
) -> dict:
    """Generate README content using the local Ollama model."""

    prompt = build_readme_prompt(
        repository=repository,
        analysis=analysis,
        existing_readme=existing_readme,
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": MAX_PREDICT_TOKENS,
        },
    }

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
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
