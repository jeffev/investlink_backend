import sys
import os

# Ensure the app folder is on sys.path so imports match runtime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.user import User  # noqa: E402


def test_user_to_json_contains_expected_fields():
    data = {
        "id": 1,
        "user_name": "jdoe",
        "name": "John Doe",
        "email": "jdoe@example.com",
        "profile": "USER",
    }
    u = User(**data)
    # assign id explicitly if constructor didn't set it
    if not getattr(u, "id", None):
        u.id = data["id"]

    json = u.to_json()
    assert json["id"] == 1
    assert json["user_name"] == "jdoe"
    assert json["name"] == "John Doe"
    assert json["email"] == "jdoe@example.com"
    assert json["profile"] == "USER"
