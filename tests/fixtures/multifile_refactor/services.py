"""Service layer for multi-file refactoring tests."""

from models import User, Product, create_default_user


class UserService:
    """Service for user operations."""

    def __init__(self):
        self.users = []

    def add_user(self, user: User) -> None:
        """Add a user to the service."""
        self.users.append(user)

    def get_user_by_username(self, username: str) -> User | None:
        """Find user by username."""
        for user in self.users:
            if user.username == username:
                return user
        return None

    def create_guest_user(self) -> User:
        """Create a guest user using factory."""
        guest = create_default_user()
        self.add_user(guest)
        return guest


class ProductService:
    """Service for product operations."""

    def __init__(self):
        self.products = []

    def add_product(self, product: Product) -> None:
        """Add a product."""
        self.products.append(product)

    def get_product_by_name(self, name: str) -> Product | None:
        """Find product by name."""
        for product in self.products:
            if product.name == name:
                return product
        return None

    def calculate_total(self, product_names: list[str]) -> float:
        """Calculate total price for given products."""
        total = 0.0
        for name in product_names:
            product = self.get_product_by_name(name)
            if product:
                total += product.price
        return total
