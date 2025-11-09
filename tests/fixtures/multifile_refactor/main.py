"""Main application using models and services."""

from models import User, Product
from services import UserService, ProductService


def setup_application():
    """Initialize the application with sample data."""
    # Create services
    user_service = UserService()
    product_service = ProductService()

    # Create and add users
    user1 = User("alice", "alice@example.com")
    user2 = User("bob", "bob@example.com")
    user_service.add_user(user1)
    user_service.add_user(user2)

    # Create guest user
    guest = user_service.create_guest_user()

    # Create and add products
    product1 = Product("Laptop", 999.99)
    product2 = Product("Mouse", 29.99)
    product3 = Product("Keyboard", 79.99)
    product_service.add_product(product1)
    product_service.add_product(product2)
    product_service.add_product(product3)

    return user_service, product_service


def main():
    """Main application entry point."""
    user_service, product_service = setup_application()

    # Find a user
    alice = user_service.get_user_by_username("alice")
    if alice:
        print(f"Found user: {alice.get_display_name()}")

    # Calculate shopping cart total
    cart = ["Laptop", "Mouse"]
    total = product_service.calculate_total(cart)
    print(f"Cart total: ${total:.2f}")


if __name__ == "__main__":
    main()
