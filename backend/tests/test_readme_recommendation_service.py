from app.services.readme_recommendation_service import (
    generate_readme_recommendations,
)


def test_missing_sections_generate_recommendations():
    analysis = {
        "is_empty": False,
        "missing_sections": ["installation", "usage"],
        "badge_count": 1,
        "image_count": 1,
        "code_block_count": 1,
        "link_count": 1,
    }

    recommendations = generate_readme_recommendations(analysis)

    categories = [item["category"] for item in recommendations]

    assert "installation" in categories
    assert "usage" in categories
    assert len(recommendations) == 2


def test_missing_readme_generates_critical_recommendation():
    analysis = {
        "is_empty": True,
        "missing_sections": [],
        "badge_count": 0,
        "image_count": 0,
        "code_block_count": 0,
        "link_count": 0,
    }

    recommendations = generate_readme_recommendations(analysis)

    assert len(recommendations) == 1
    assert recommendations[0]["priority"] == "critical"
    assert recommendations[0]["title"] == "Create a README"


def test_missing_badges_images_examples_and_links():
    analysis = {
        "is_empty": False,
        "missing_sections": [],
        "badge_count": 0,
        "image_count": 0,
        "code_block_count": 0,
        "link_count": 0,
    }

    recommendations = generate_readme_recommendations(analysis)

    categories = [item["category"] for item in recommendations]

    assert "badges" in categories
    assert "visuals" in categories
    assert "examples" in categories
    assert "links" in categories
    assert len(recommendations) == 4