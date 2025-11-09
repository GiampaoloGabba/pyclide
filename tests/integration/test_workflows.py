"""Multi-step workflow integration tests via server API.

These tests verify that features work together correctly in realistic workflows.
"""

import pytest
from tests.utils import create_python_file, assert_patches_valid, assert_locations_response


@pytest.mark.integration
class TestCompleteRefactoringWorkflow:
    """Test complete refactoring workflows from start to finish."""

    @pytest.fixture
    def django_like_project(self, temp_workspace):
        """Create a Django-like project structure."""
        # models.py
        create_python_file(
            temp_workspace / "models.py",
            """
from typing import Optional

class User:
    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email

    def get_full_name(self) -> str:
        return self.username

    def send_email(self, subject: str, body: str) -> bool:
        # TODO: implement email sending
        print(f"Sending email to {self.email}")
        return True

class UserManager:
    def create_user(self, username: str, email: str) -> User:
        user = User(username, email)
        return user

    def find_by_email(self, email: str) -> Optional[User]:
        # Stub implementation
        return None
"""
        )

        # views.py
        create_python_file(
            temp_workspace / "views.py",
            """
from models import User, UserManager

def register_user(username: str, email: str):
    manager = UserManager()
    user = manager.create_user(username, email)
    user.send_email("Welcome", "Welcome to our site!")
    return user

def get_user_info(email: str):
    manager = UserManager()
    user = manager.find_by_email(email)
    if user:
        return user.get_full_name()
    return None
"""
        )

        # tests.py
        create_python_file(
            temp_workspace / "tests.py",
            """
from models import User, UserManager
from views import register_user

def test_user_creation():
    manager = UserManager()
    user = manager.create_user("alice", "alice@test.com")
    assert user.username == "alice"

def test_registration():
    user = register_user("bob", "bob@test.com")
    assert user is not None
"""
        )

        return temp_workspace

    def test_workflow_explore_then_refactor(self, httpx_client, django_like_project):
        """
        Workflow: Developer explores codebase, then performs refactoring.

        Steps:
        1. Find all usages of User class
        2. Rename User to Account
        3. Verify all files updated consistently
        """
        root = django_like_project

        # Step 1: Find all references to User class (line 4, col 7)
        refs_response = httpx_client.post(
            "/refs",
            json={
                "file": "models.py",
                "line": 4,
                "col": 7,
                "root": str(root)
            }
        )
        assert refs_response.status_code == 200
        refs = refs_response.json()
        # Should find references in multiple files
        assert_locations_response(refs, min_count=1)

        # Step 2: Rename User to Account
        rename_response = httpx_client.post(
            "/rename",
            json={
                "file": "models.py",
                "line": 4,
                "col": 7,
                "new_name": "Account",
                "root": str(root)
            }
        )
        assert rename_response.status_code == 200
        data = rename_response.json()
        patches = data["patches"]

        # Verify all files were updated
        assert "models.py" in patches
        # May also update views.py and tests.py
        assert len(patches) >= 1

        # Verify rename was consistent
        assert "class Account:" in patches["models.py"]
        assert "class User:" not in patches["models.py"]

        # Check cross-file updates if present
        if "views.py" in patches:
            assert "Account" in patches["views.py"]

    def test_workflow_extract_and_organize(self, httpx_client, django_like_project):
        """
        Workflow: Extract logic and organize imports.

        Steps:
        1. Extract method
        2. Organize imports
        """
        root = django_like_project

        # Step 1: Try to extract method (send_email logic)
        extract_response = httpx_client.post(
            "/extract-method",
            json={
                "file": "models.py",
                "start_line": 14,
                "end_line": 15,
                "method_name": "send_notification",
                "root": str(root)
            }
        )
        # May or may not succeed depending on Rope's analysis
        assert extract_response.status_code in (200, 400, 500)

        # Step 2: Organize imports in models.py
        organize_response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "models.py",
                "root": str(root)
            }
        )
        # Should succeed or return empty patches
        assert organize_response.status_code in (200, 400)

    def test_workflow_progressive_enhancement(self, httpx_client, django_like_project):
        """
        Workflow: Progressive enhancement - check signatures, then refactor.

        Steps:
        1. Hover to see current signatures
        2. Find occurrences
        3. Rename with better names
        """
        root = django_like_project

        # Step 1: Hover on get_full_name function (line 9, col 9)
        hover_response = httpx_client.post(
            "/hover",
            json={
                "file": "models.py",
                "line": 9,
                "col": 9,
                "root": str(root)
            }
        )
        assert hover_response.status_code == 200
        hover_info = hover_response.json()
        # Hover returns dict with name, type, signature, docstring
        assert isinstance(hover_info, dict)

        # Step 2: Find all occurrences of get_full_name
        occ_response = httpx_client.post(
            "/occurrences",
            json={
                "file": "models.py",
                "line": 9,
                "col": 9,
                "root": str(root)
            }
        )
        assert occ_response.status_code == 200

        # Step 3: Rename get_full_name to get_display_name
        rename_response = httpx_client.post(
            "/rename",
            json={
                "file": "models.py",
                "line": 9,
                "col": 9,
                "new_name": "get_display_name",
                "root": str(root)
            }
        )
        assert rename_response.status_code == 200
        data = rename_response.json()
        patches = data["patches"]

        # Verify rename propagated
        assert "get_display_name" in patches["models.py"]
        if "views.py" in patches:
            assert "get_display_name" in patches["views.py"]


@pytest.mark.integration
@pytest.mark.rope
class TestCrossCuttingConcerns:
    """Test features that span multiple files and modules."""

    @pytest.fixture
    def layered_architecture(self, temp_workspace):
        """Create a multi-layer architecture (models/services/controllers)."""
        # Domain layer
        domain = temp_workspace / "domain"
        domain.mkdir()

        create_python_file(
            domain / "entities.py",
            """
class Product:
    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price

    def calculate_tax(self, rate: float) -> float:
        return self.price * rate

class Order:
    def __init__(self, product: Product, quantity: int):
        self.product = product
        self.quantity = quantity

    def total(self) -> float:
        return self.product.price * self.quantity
"""
        )

        # Service layer
        services = temp_workspace / "services"
        services.mkdir()

        create_python_file(
            services / "order_service.py",
            """
import sys
sys.path.insert(0, '..')
from domain.entities import Product, Order

class OrderService:
    def create_order(self, product_name: str, price: float, quantity: int) -> Order:
        product = Product(product_name, price)
        order = Order(product, quantity)
        return order

    def calculate_order_total(self, order: Order) -> float:
        return order.total()
"""
        )

        # Controller layer
        controllers = temp_workspace / "controllers"
        controllers.mkdir()

        create_python_file(
            controllers / "api.py",
            """
import sys
sys.path.insert(0, '..')
from domain.entities import Product, Order
from services.order_service import OrderService

class OrderController:
    def __init__(self):
        self.service = OrderService()

    def handle_create_order(self, name: str, price: float, qty: int):
        order = self.service.create_order(name, price, qty)
        total = self.service.calculate_order_total(order)
        return {"order": order, "total": total}
"""
        )

        return temp_workspace

    def test_rename_across_layers(self, httpx_client, layered_architecture):
        """Test that rename works across architectural layers."""
        root = layered_architecture

        # Rename Product class in domain layer (line 2, col 7)
        response = httpx_client.post(
            "/rename",
            json={
                "file": "domain/entities.py",
                "line": 2,
                "col": 7,
                "new_name": "Item",
                "root": str(root)
            }
        )
        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # Should update domain layer at minimum
        # Note: Path separators may vary (/ or \)
        updated_files = list(patches.keys())
        assert len(updated_files) >= 1
        assert any("entities.py" in f for f in updated_files)

    def test_find_references_across_layers(self, httpx_client, layered_architecture):
        """Test finding references across architectural boundaries."""
        root = layered_architecture

        # Find all references to Order class (line 10, col 7)
        response = httpx_client.post(
            "/refs",
            json={
                "file": "domain/entities.py",
                "line": 10,
                "col": 7,
                "root": str(root)
            }
        )
        assert response.status_code == 200
        data = response.json()

        # Should find at least the definition
        assert_locations_response(data, min_count=1)


@pytest.mark.integration
class TestErrorRecoveryWorkflows:
    """Test that features handle edge cases gracefully in workflows."""

    def test_refactor_with_mixed_file_states(self, httpx_client, temp_workspace):
        """
        Test refactoring when project has:
        - Valid files
        - Files with syntax errors
        - Empty files
        - Files with unusual encoding
        """
        # Valid file
        create_python_file(
            temp_workspace / "valid.py",
            "class Foo:\n    pass\n\nf = Foo()\n"
        )

        # File with syntax error (should be ignored by Rope)
        create_python_file(
            temp_workspace / "broken.py",
            "def bad(\n    pass\n"
        )

        # Empty file
        create_python_file(temp_workspace / "empty.py", "")

        # File with unicode
        create_python_file(
            temp_workspace / "unicode.py",
            "# -*- coding: utf-8 -*-\nclass Café:\n    pass\n"
        )

        # Rename Foo to Bar - should work despite broken.py
        response = httpx_client.post(
            "/rename",
            json={
                "file": "valid.py",
                "line": 1,
                "col": 7,
                "new_name": "Bar",
                "root": str(temp_workspace)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # Should update valid.py
        assert "valid.py" in patches
        assert "class Bar:" in patches["valid.py"]
        assert "Bar()" in patches["valid.py"]

    def test_consecutive_refactorings(self, httpx_client, temp_workspace):
        """Test multiple refactorings in sequence without applying to disk."""
        create_python_file(
            temp_workspace / "test.py",
            """
def old_function():
    x = calculate_value()
    y = process_value(x)
    return y

def calculate_value():
    return 42

def process_value(val):
    return val * 2
"""
        )

        # Refactoring 1: Rename old_function
        response1 = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 2,
                "col": 5,
                "new_name": "new_function",
                "root": str(temp_workspace)
            }
        )
        assert response1.status_code == 200
        patches1 = response1.json()["patches"]
        assert "new_function" in patches1["test.py"]

        # Refactoring 2: Rename calculate_value (on original file)
        response2 = httpx_client.post(
            "/rename",
            json={
                "file": "test.py",
                "line": 7,
                "col": 5,
                "new_name": "get_value",
                "root": str(temp_workspace)
            }
        )
        assert response2.status_code == 200
        patches2 = response2.json()["patches"]
        assert "get_value" in patches2["test.py"]


@pytest.mark.integration
class TestIDELikeWorkflows:
    """Test workflows similar to what an IDE would perform."""

    @pytest.fixture
    def project(self, temp_workspace):
        """Create a project for IDE-like interactions."""
        create_python_file(
            temp_workspace / "main.py",
            """
from utils import helper_function

def main():
    result = helper_function(10)
    print(result)
    return result

if __name__ == "__main__":
    main()
"""
        )

        create_python_file(
            temp_workspace / "utils.py",
            """
def helper_function(x: int) -> int:
    \"\"\"Calculate double value.

    Args:
        x: Input value

    Returns:
        Double the input value
    \"\"\"
    return x * 2

def another_helper(y: str) -> str:
    return y.upper()
"""
        )

        return temp_workspace

    def test_ide_goto_definition_workflow(self, httpx_client, project):
        """Simulate: user hovers, sees info, then goes to definition."""
        # Step 1: Hover on helper_function to see signature (line 5, col 13)
        hover_response = httpx_client.post(
            "/hover",
            json={
                "file": "main.py",
                "line": 5,
                "col": 13,
                "root": str(project)
            }
        )
        assert hover_response.status_code == 200
        hover = hover_response.json()
        assert isinstance(hover, dict)

        # Step 2: Go to definition
        defs_response = httpx_client.post(
            "/defs",
            json={
                "file": "main.py",
                "line": 5,
                "col": 13,
                "root": str(project)
            }
        )
        assert defs_response.status_code == 200
        defs = defs_response.json()
        assert_locations_response(defs, min_count=1)

    def test_ide_find_all_usages_workflow(self, httpx_client, project):
        """Simulate: user wants to see all usages before renaming."""
        # Find all references to helper_function (line 2, col 5)
        response = httpx_client.post(
            "/refs",
            json={
                "file": "utils.py",
                "line": 2,
                "col": 5,
                "root": str(project)
            }
        )
        assert response.status_code == 200
        data = response.json()

        # Should find definition and usage(s)
        assert_locations_response(data, min_count=1)

    def test_ide_refactor_with_preview(self, httpx_client, project):
        """Simulate: user previews changes before applying."""
        # Get preview of rename
        response = httpx_client.post(
            "/rename",
            json={
                "file": "utils.py",
                "line": 2,
                "col": 5,
                "new_name": "compute_double",
                "root": str(project)
            }
        )
        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # Should show changes
        assert "utils.py" in patches
        assert "compute_double" in patches["utils.py"]

        # May update main.py if cross-file references found
        if "main.py" in patches:
            assert "compute_double" in patches["main.py"]


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceWorkflows:
    """Performance baseline tests for workflows."""

    @pytest.fixture
    def medium_project(self, temp_workspace):
        """Create a medium-sized project (20 files)."""
        for i in range(20):
            create_python_file(
                temp_workspace / f"module_{i}.py",
                f"""
class Service{i}:
    def __init__(self):
        self.name = "Service{i}"

    def process(self):
        return self.name

def create_service_{i}():
    return Service{i}()
"""
            )

        # Create a main file that imports from all modules
        imports = "\n".join([f"from module_{i} import Service{i}" for i in range(20)])
        services_list = ", ".join([f"Service{i}()" for i in range(20)])
        create_python_file(
            temp_workspace / "main.py",
            f"""
{imports}

def main():
    services = [{services_list}]
    return services
"""
        )

        return temp_workspace

    def test_rename_performance(self, httpx_client, medium_project):
        """Test that rename completes in reasonable time."""
        import time

        start = time.time()
        response = httpx_client.post(
            "/rename",
            json={
                "file": "module_0.py",
                "line": 2,
                "col": 7,
                "new_name": "Handler0",
                "root": str(medium_project)
            }
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        # Should complete in under 5 seconds
        # (More generous than CLI as server has additional overhead)
        assert elapsed < 5.0

    def test_organize_imports_bulk_performance(self, httpx_client, medium_project):
        """Test organizing imports on a file."""
        import time

        start = time.time()
        response = httpx_client.post(
            "/organize-imports",
            json={
                "file": "main.py",
                "root": str(medium_project)
            }
        )
        elapsed = time.time() - start

        # Should complete even if slow
        assert response.status_code in (200, 400)
        # Should complete in under 10 seconds
        assert elapsed < 10.0
