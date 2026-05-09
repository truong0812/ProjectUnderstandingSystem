from storage.user_repository import UserRepository


class UserService:
    def __init__(self) -> None:
        self.repository = UserRepository()

    def login(self, username: str, token: str) -> bool:
        if not token:
            return False
        user = self.repository.find_user(username)
        return user is not None

    def save_profile(self, username: str, data: dict) -> None:
        self.repository.save(username, data)
