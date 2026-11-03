RECOMMENDATION_DETAILS = {
    "installation": {
        "title": "Add installation instructions",
        "description": "Explain how users can install dependencies and set up the project.",
        "priority": "high",
    },
    "usage": {
        "title": "Add usage instructions",
        "description": "Show users how to run and use the project with practical examples.",
        "priority": "high",
    },
    "features": {
        "title": "Document project features",
        "description": "Describe the main features and what makes this project useful.",
        "priority": "medium",
    },
    "requirements": {
        "title": "Document requirements",
        "description": "List required software, runtimes, dependencies, and versions.",
        "priority": "medium",
    },
    "contributing": {
        "title": "Add contribution guidelines",
        "description": "Explain how developers can report issues and contribute changes.",
        "priority": "low",
    },
    "license": {
        "title": "Add license information",
        "description": "Specify the project's license and link to its license file.",
        "priority": "medium",
    },
}


def generate_readme_recommendations(readme_analysis: dict) -> list:
    """Generate actionable recommendations from README analysis."""

    recommendations = []

    if readme_analysis.get("is_empty", False):
        return [{
            "title": "Create a README",
            "description": "This repository has no README content. Start with a project overview, installation steps, usage examples, and license information.",
            "priority": "critical",
        }]

    missing_sections = readme_analysis.get("missing_sections", [])

    for section in missing_sections:
        details = RECOMMENDATION_DETAILS.get(section)

        if details:
            recommendations.append({
                "category": section,
                **details,
            })

    if readme_analysis.get("badge_count", 0) == 0:
        recommendations.append({
            "category": "badges",
            "title": "Add project badges",
            "description": "Add relevant Shields.io badges for the project license, language, latest release, and build status where supported.",
            "priority": "medium",
        })

    if readme_analysis.get("image_count", 0) == 0:
        recommendations.append({
            "category": "visuals",
            "title": "Add project visuals",
            "description": "Add screenshots or diagrams to help users understand the project's interface and architecture.",
            "priority": "low",
        })

    if readme_analysis.get("code_block_count", 0) == 0:
        recommendations.append({
            "category": "examples",
            "title": "Add code examples",
            "description": "Include practical code snippets or terminal commands showing how to use the project.",
            "priority": "medium",
        })

    if readme_analysis.get("link_count", 0) == 0:
        recommendations.append({
            "category": "links",
            "title": "Add useful links",
            "description": "Link to relevant documentation, project resources, and official references.",
            "priority": "low",
        })

    return recommendations