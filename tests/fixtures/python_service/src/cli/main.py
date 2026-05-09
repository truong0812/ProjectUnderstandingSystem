from services.user_service import UserService


def main() -> None:
    service = UserService()
    service.login("demo", "token")
