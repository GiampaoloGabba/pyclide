"""File with nested classes, inheritance, and complex structures for testing."""


class Animal:
    """Base animal class."""

    def __init__(self, name: str):
        self.name = name

    def speak(self) -> str:
        """Make a sound."""
        return "Some sound"

    def move(self) -> str:
        """Move the animal."""
        return f"{self.name} is moving"


class Dog(Animal):
    """Dog class inheriting from Animal."""

    def __init__(self, name: str, breed: str):
        super().__init__(name)
        self.breed = breed

    def speak(self) -> str:
        """Override speak method."""
        return "Woof!"

    def fetch(self, item: str) -> str:
        """Dog-specific method."""
        return f"{self.name} fetches {item}"


class Cat(Animal):
    """Cat class inheriting from Animal."""

    def __init__(self, name: str, color: str):
        super().__init__(name)
        self.color = color

    def speak(self) -> str:
        """Override speak method."""
        return "Meow!"

    def climb(self) -> str:
        """Cat-specific method."""
        return f"{self.name} climbs"


class ServiceDog(Dog):
    """Service dog - multiple inheritance levels."""

    def __init__(self, name: str, breed: str, service_type: str):
        super().__init__(name, breed)
        self.service_type = service_type

    def assist(self) -> str:
        """Service dog specific method."""
        return f"{self.name} provides {self.service_type} assistance"


class Container:
    """Class with nested class."""

    class Inner:
        """Nested inner class."""

        def __init__(self, value: int):
            self.value = value

        def get_value(self) -> int:
            """Get the inner value."""
            return self.value

    def __init__(self):
        self.inner = self.Inner(42)

    def get_inner_value(self) -> int:
        """Get value from inner class."""
        return self.inner.get_value()


def create_animals():
    """Factory function to create various animals."""
    dog = Dog("Buddy", "Labrador")
    cat = Cat("Whiskers", "Orange")
    service_dog = ServiceDog("Max", "German Shepherd", "Guide")

    return dog, cat, service_dog


def demonstrate_polymorphism(animal: Animal):
    """Demonstrate polymorphism with base class reference."""
    return animal.speak()
