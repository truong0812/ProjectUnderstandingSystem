class UserRepository:
    def find_user(self, username: str) -> dict | None:
        return {"name": username}

    def save(self, username: str, data: dict) -> None:
        print("save", username, data)
