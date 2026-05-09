from services.user_service import UserService


def check_login_requires_token() -> None:
    assert UserService().login("demo", "") is False
