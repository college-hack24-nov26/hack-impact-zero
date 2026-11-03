import re


EXPECTED_SECTIONS = {
    "installation": ["installation", "setup", "getting started"],
    "usage": ["usage", "how to use", "quick start"],
    "features": ["features", "key features"],
    "requirements": ["requirements", "prerequisites", "dependencies"],
    "contributing": ["contributing", "contribution"],
    "license": ["license", "licence"],
}


def analyze_readme(content: str) -> dict:
    """Analyze README content and identify documentation gaps."""

    content = content or ""

    headings = re.findall(
        r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$",
        content,
        re.MULTILINE,
    )

    normalized_headings = [
        heading.strip().lower()
        for heading in headings
    ]

    missing_sections = []

    for section, alternatives in EXPECTED_SECTIONS.items():
        found = any(
            alternative in heading
            for heading in normalized_headings
            for alternative in alternatives
        )

        if not found:
            missing_sections.append(section)

    # Detect normal Markdown links, excluding image links.
    links = re.findall(
        r'(?<!!)\[[^\]]+\]\((https?://[^)\s]+)',
        content,
    )

    # Detect Markdown images.
    images = re.findall(
        r'!\[[^\]]*\]\((https?://[^)\s]+)',
        content,
    )

    # Detect Shields.io badge URLs.
    badges = re.findall(
        r'https?://img\.shields\.io/[^)\s]+',
        content,
        re.IGNORECASE,
    )

    code_blocks = re.findall(r"```", content)

    return {
        "word_count": len(content.split()),
        "character_count": len(content),
        "headings": headings,
        "heading_count": len(headings),
        "links": links,
        "link_count": len(links),
        "images": images,
        "image_count": len(images),
        "badges": badges,
        "badge_count": len(badges),
        "code_block_count": len(code_blocks) // 2,
        "missing_sections": missing_sections,
        "is_empty": not content.strip(),
    }