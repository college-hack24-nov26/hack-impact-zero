import os
import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def build_structured_fallback(original_readme: str, missing_sections: list, badges: str, repo_name: str = "Project") -> str:
    sections = [
        f"# {repo_name}\n\n{badges}\n",
        "## 📌 Overview\n\nAn enhanced, high-performance open-source project designed for modern workflows.",
        "## ✨ Key Features\n\n- **Automated Processing**: Instant analysis and optimization.\n- **Modern Architecture**: Scalable, modular backend design.\n- **Rich Diagnostics**: Comprehensive evaluation metrics.",
        "## 🔄 Workflow Diagram\n\n```mermaid\ngraph TD;\n    User([User Request]) --> API[FastAPI Backend];\n    API --> Scraper[GitHub Extractor];\n    API --> Scoring[Benchmark Scoring Engine];\n    API --> LLM[Groq API Engine];\n    LLM --> UI[Dual-Pane Preview UI];\n```",
        "## 🚀 Getting Started\n\n### Prerequisites\n- Python 3.10+\n- Node.js 18+\n- Groq API Key\n\n### Installation\n```bash\n# Clone the repository\ngit clone https://github.com/example/repo.git\ncd repo\n\n# Set API key in .env or environment\nexport GROQ_API_KEY="gsk_..."
\n# Install dependencies\npip install -r backend/requirements.txt\n```",
        "## 📜 License\n\nDistributed under the MIT License. See `LICENSE` for more information."
    ]
    
    return "\n\n".join(sections) + "\n\n---\n\n### Original Documentation Context\n\n" + original_readme

def generate_beautified_readme(original_readme: str, analysis: dict, badges: str, repo_name: str = "Repository", custom_api_key: str = "") -> str:
    missing_str = ", ".join(analysis["missing_features"]) if analysis["missing_features"] else "None"

    api_key = custom_api_key.strip() or os.getenv("GROQ_API_KEY", "").strip()
    groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

    prompt = f"""You are an elite open-source documentation architect.
Restructure and expand the following README.md file into a professional, engaging, top-tier open-source document.

MUST-HAVE REQUIREMENTS:
1. Place these Shields.io badges right below the main title:
{badges}

2. Ensure all these missing key sections are seamlessly integrated: {missing_str}
3. Include a detailed Mermaid.js flowchart (```mermaid ... ```) depicting the project system flow.
4. Keep all original commands, environment variables, and technical setup steps intact.
5. Use clean Markdown tables, bold bullet points, and modern callouts.

ORIGINAL README CONTENT:
{original_readme}
"""

    if api_key:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": groq_model,
            "messages": [
                {"role": "system", "content": "You are a professional technical documentation writer."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4096
        }
        try:
            res = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                output = data["choices"][0]["message"]["content"].strip()
                if len(output) > 100:
                    return output
            else:
                print(f"Groq API Error ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"Groq API Exception: {e}")

    # Fallback response if Groq API key is missing or call fails
    return build_structured_fallback(original_readme, analysis["missing_features"], badges, repo_name)
