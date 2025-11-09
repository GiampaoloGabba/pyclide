"""Model definitions for multi-file refactoring tests."""


class User:
    """User model."""

    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email

    def get_display_name(self) -> str:
        """Get the display name."""
        return f"{self.username} ({self.email})"


class Product:
    """Product model."""

    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price

    def get_formatted_price(self) -> str:
        """Get formatted price."""
        return f"${self.price:.2f}"


def create_default_user() -> User:
    """Factory function for default user."""
    return User("guest", "guest@example.com")
