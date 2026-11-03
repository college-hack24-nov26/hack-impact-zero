from app.services.repository_analysis_service import (
    analyze_repository_structure,
)


def test_analyze_repository_structure():
    tree_result = {
        "truncated": False,
        "files": [
            {"path": "README.md", "type": "blob", "size": 500},
            {"path": "requirements.txt", "type": "blob", "size": 100},
            {"path": "backend", "type": "tree"},
            {"path": "backend/main.py", "type": "blob", "size": 300},
            {"path": "backend/routes.py", "type": "blob", "size": 200},
            {"path": "frontend/app.js", "type": "blob", "size": 400},
            {"path": "frontend", "type": "tree"},
        ],
    }

    result = analyze_repository_structure(tree_result)

    assert result["total_files"] == 5
    assert result["total_directories"] == 2
    assert result["languages"] == {
        "Python": 2,
        "JavaScript": 1,
    }
    assert result["important_files"] == [
        "README.md",
        "requirements.txt",
    ]
    assert result["truncated"] is False


def test_analyze_empty_repository():
    result = analyze_repository_structure({"files": []})

    assert result["total_files"] == 0
    assert result["total_directories"] == 0
    assert result["languages"] == {}
    assert result["extensions"] == {}
    assert result["important_files"] == []
    assert result["truncated"] is False


def test_analyze_truncated_repository():
    result = analyze_repository_structure({
        "files": [
            {"path": "src/main.py", "type": "blob", "size": 100},
        ],
        "truncated": True,
    })

    assert result["total_files"] == 1
    assert result["languages"] == {"Python": 1}
    assert result["truncated"] is True