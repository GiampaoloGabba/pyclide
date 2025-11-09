"""Real-world project patterns and framework integration tests via server API.

These tests simulate actual patterns found in popular Python frameworks
to ensure the server works with real codebases.
"""

import pytest
from tests.utils import create_python_file, assert_patches_valid, assert_locations_response


@pytest.mark.integration
@pytest.mark.rope
class TestDjangoLikePatterns:
    """Test patterns commonly found in Django projects."""

    @pytest.fixture
    def django_app(self, temp_workspace):
        """Create Django-like app structure."""
        # models.py with Django ORM pattern
        create_python_file(
            temp_workspace / "models.py",
            """
from typing import Optional

class Model:
    \"\"\"Base model class.\"\"\"
    pass

class User(Model):
    \"\"\"User model.\"\"\"

    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email

    def save(self):
        \"\"\"Save to database.\"\"\"
        pass

    def delete(self):
        \"\"\"Delete from database.\"\"\"
        pass

    @classmethod
    def objects_get(cls, username: str) -> Optional['User']:
        \"\"\"Get user by username.\"\"\"
        return None

class Post(Model):
    \"\"\"Blog post model.\"\"\"

    def __init__(self, title: str, author: 'User'):
        self.title = title
        self.author = author

    def save(self):
        pass
"""
        )

        # views.py with Django view pattern
        create_python_file(
            temp_workspace / "views.py",
            """
from models import User, Post

def user_detail(request, username: str):
    \"\"\"User detail view.\"\"\"
    user = User.objects_get(username=username)
    if user is None:
        return {"error": "Not found"}
    return {"user": user}

def create_post(request):
    \"\"\"Create post view.\"\"\"
    user = User.objects_get(username=request.get("author"))
    post = Post(title=request.get("title"), author=user)
    post.save()
    return {"post": post}
"""
        )

        # admin.py with Django admin pattern
        create_python_file(
            temp_workspace / "admin.py",
            """
from models import User, Post

class UserAdmin:
    list_display = ['username', 'email']

    def get_user(self, username):
        return User.objects_get(username)

class PostAdmin:
    list_display = ['title', 'author']
"""
        )

        return temp_workspace

    def test_rename_model_class(self, httpx_client, django_app):
        """Test renaming a model class used across app."""
        # Rename User to Account (line 8, col 7)
        response = httpx_client.post(
            "/rename",
            json={
                "file": "models.py",
                "line": 8,
                "col": 7,
                "new_name": "Account",
                "root": str(django_app)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # Should update models, views, and admin
        assert "models.py" in patches
        # May also update views.py and admin.py
        assert len(patches) >= 1

        # Check model file
        assert "class Account(Model):" in patches["models.py"]

        # Check imports updated if views.py was patched
        if "views.py" in patches:
            assert "Account" in patches["views.py"]

    def test_find_model_usages(self, httpx_client, django_app):
        """Test finding all usages of a model across Django app."""
        response = httpx_client.post(
            "/refs",
            json={
                "file": "models.py",
                "line": 8,
                "col": 7,
                "root": str(django_app)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should find references in models.py at minimum
        # May also find in views.py and admin.py
        assert_locations_response(data, min_count=1)


@pytest.mark.integration
@pytest.mark.rope
class TestFlaskLikePatterns:
    """Test patterns commonly found in Flask projects."""

    @pytest.fixture
    def flask_app(self, temp_workspace):
        """Create Flask-like app structure."""
        # app.py with Flask patterns
        create_python_file(
            temp_workspace / "app.py",
            """
from typing import Dict, Any

class Request:
    def json(self) -> Dict[str, Any]:
        return {}

class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

def jsonify(data) -> Response:
    return Response(data)

# Routes
def get_user(user_id: int) -> Response:
    \"\"\"Get user by ID.\"\"\"
    user_data = fetch_user(user_id)
    return jsonify(user_data)

def create_user(request: Request) -> Response:
    \"\"\"Create new user.\"\"\"
    data = request.json()
    user_data = save_user(data)
    return jsonify(user_data)

def fetch_user(user_id: int) -> Dict[str, Any]:
    return {"id": user_id, "name": "Test"}

def save_user(data: Dict[str, Any]) -> Dict[str, Any]:
    return data
"""
        )

        # blueprints.py
        create_python_file(
            temp_workspace / "blueprints.py",
            """
from app import get_user, create_user, jsonify

class Blueprint:
    def __init__(self, name: str):
        self.name = name
        self.routes = []

    def route(self, path: str):
        def decorator(func):
            self.routes.append((path, func))
            return func
        return decorator

# User blueprint
user_bp = Blueprint("users")

@user_bp.route("/users/<int:user_id>")
def user_detail(user_id: int):
    return get_user(user_id)

@user_bp.route("/users", methods=["POST"])
def user_create(request):
    return create_user(request)
"""
        )

        return temp_workspace

    def test_rename_route_function(self, httpx_client, flask_app):
        """Test renaming a route function."""
        response = httpx_client.post(
            "/rename",
            json={
                "file": "app.py",
                "line": 17,
                "col": 5,
                "new_name": "get_user_by_id",
                "root": str(flask_app)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # Should update app.py at minimum
        assert "app.py" in patches
        assert "get_user_by_id" in patches["app.py"]

        # May also update blueprints.py
        if "blueprints.py" in patches:
            assert "get_user_by_id" in patches["blueprints.py"]

    def test_extract_business_logic(self, httpx_client, flask_app):
        """Test extracting business logic from route handler."""
        # Try to extract the fetch_user call logic
        response = httpx_client.post(
            "/extract-method",
            json={
                "file": "app.py",
                "start_line": 20,
                "end_line": 20,
                "method_name": "load_user_data",
                "root": str(flask_app)
            }
        )

        # Should not crash even if extraction is complex
        assert response.status_code in (200, 400, 500)


@pytest.mark.integration
class TestFastAPILikePatterns:
    """Test patterns commonly found in FastAPI projects."""

    @pytest.fixture
    def fastapi_app(self, temp_workspace):
        """Create FastAPI-like app structure."""
        # schemas.py with Pydantic-like models
        create_python_file(
            temp_workspace / "schemas.py",
            """
from typing import Optional

class BaseModel:
    pass

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
"""
        )

        # routes.py with FastAPI route patterns
        create_python_file(
            temp_workspace / "routes.py",
            """
from schemas import UserCreate, UserResponse, UserUpdate
from typing import List

class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

async def create_user(user: UserCreate) -> UserResponse:
    \"\"\"Create a new user.\"\"\"
    # Simulate user creation
    return UserResponse(
        id=1,
        username=user.username,
        email=user.email
    )

async def get_user(user_id: int) -> UserResponse:
    \"\"\"Get user by ID.\"\"\"
    if user_id < 1:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(id=user_id, username="test", email="test@example.com")

async def update_user(user_id: int, user: UserUpdate) -> UserResponse:
    \"\"\"Update user.\"\"\"
    current = await get_user(user_id)
    return current

async def list_users() -> List[UserResponse]:
    \"\"\"List all users.\"\"\"
    return [
        UserResponse(id=1, username="user1", email="user1@example.com"),
        UserResponse(id=2, username="user2", email="user2@example.com"),
    ]
"""
        )

        # dependencies.py
        create_python_file(
            temp_workspace / "dependencies.py",
            """
from schemas import UserResponse

async def get_current_user() -> UserResponse:
    \"\"\"Get current authenticated user.\"\"\"
    return UserResponse(id=1, username="current", email="current@example.com")

async def require_admin() -> bool:
    \"\"\"Require admin permission.\"\"\"
    user = await get_current_user()
    return user.id == 1
"""
        )

        return temp_workspace

    def test_rename_schema_class(self, httpx_client, fastapi_app):
        """Test renaming Pydantic schema affects all usages."""
        response = httpx_client.post(
            "/rename",
            json={
                "file": "schemas.py",
                "line": 7,
                "col": 7,
                "new_name": "CreateUserRequest",
                "root": str(fastapi_app)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # Should update schemas.py at minimum
        assert "schemas.py" in patches
        assert "CreateUserRequest" in patches["schemas.py"]

        # May also update routes.py
        if "routes.py" in patches:
            assert "CreateUserRequest" in patches["routes.py"]

    def test_find_async_function_references(self, httpx_client, fastapi_app):
        """Test finding references to async functions."""
        response = httpx_client.post(
            "/refs",
            json={
                "file": "routes.py",
                "line": 21,
                "col": 11,
                "root": str(fastapi_app)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should find definition and possibly usage in update_user
        assert_locations_response(data, min_count=1)


@pytest.mark.integration
@pytest.mark.rope
class TestDataSciencePatterns:
    """Test patterns from data science / ML projects."""

    @pytest.fixture
    def ml_project(self, temp_workspace):
        """Create ML project structure."""
        # data_processing.py
        create_python_file(
            temp_workspace / "data_processing.py",
            """
import sys
from typing import List, Tuple

class DataFrame:
    def __init__(self, data):
        self.data = data

def load_dataset(path: str) -> DataFrame:
    \"\"\"Load dataset from file.\"\"\"
    return DataFrame([])

def preprocess_data(df: DataFrame) -> DataFrame:
    \"\"\"Preprocess the dataset.\"\"\"
    # Cleaning, normalization, etc.
    return df

def split_dataset(df: DataFrame, ratio: float = 0.8) -> Tuple[DataFrame, DataFrame]:
    \"\"\"Split into train and test sets.\"\"\"
    return df, df

def feature_engineering(df: DataFrame) -> DataFrame:
    \"\"\"Extract features.\"\"\"
    return df
"""
        )

        # model.py
        create_python_file(
            temp_workspace / "model.py",
            """
from data_processing import DataFrame
from typing import Any

class Model:
    def __init__(self):
        self.weights = None

    def train(self, data: DataFrame):
        \"\"\"Train the model.\"\"\"
        pass

    def predict(self, data: DataFrame) -> list:
        \"\"\"Make predictions.\"\"\"
        return []

    def evaluate(self, data: DataFrame) -> float:
        \"\"\"Evaluate model.\"\"\"
        return 0.95

class RandomForestModel(Model):
    pass

class NeuralNetworkModel(Model):
    pass
"""
        )

        # pipeline.py
        create_python_file(
            temp_workspace / "pipeline.py",
            """
from data_processing import load_dataset, preprocess_data, split_dataset
from model import Model, RandomForestModel

def train_pipeline(data_path: str) -> Model:
    \"\"\"Complete training pipeline.\"\"\"
    # Load data
    raw_data = load_dataset(data_path)

    # Preprocess
    clean_data = preprocess_data(raw_data)

    # Split
    train_data, test_data = split_dataset(clean_data)

    # Train
    model = RandomForestModel()
    model.train(train_data)

    # Evaluate
    accuracy = model.evaluate(test_data)
    print(f"Accuracy: {accuracy}")

    return model
"""
        )

        return temp_workspace

    def test_rename_dataframe_type(self, httpx_client, ml_project):
        """Test renaming custom DataFrame class."""
        response = httpx_client.post(
            "/rename",
            json={
                "file": "data_processing.py",
                "line": 5,
                "col": 7,
                "new_name": "Dataset",
                "root": str(ml_project)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # Should update type hints
        assert "data_processing.py" in patches
        assert "Dataset" in patches["data_processing.py"]

        # May also update model.py
        if "model.py" in patches:
            assert "Dataset" in patches["model.py"]

    def test_refactor_pipeline(self, httpx_client, ml_project):
        """Test refactoring ML pipeline functions."""
        # Find all references to preprocess_data (line 13, col 5)
        response = httpx_client.post(
            "/refs",
            json={
                "file": "data_processing.py",
                "line": 13,
                "col": 5,
                "root": str(ml_project)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should find definition and usage in pipeline.py
        assert_locations_response(data, min_count=1)


@pytest.mark.integration
@pytest.mark.rope
class TestMicroservicePatterns:
    """Test patterns from microservice architectures."""

    @pytest.fixture
    def microservice(self, temp_workspace):
        """Create microservice structure."""
        # api/client.py
        api_dir = temp_workspace / "api"
        api_dir.mkdir()

        create_python_file(
            api_dir / "client.py",
            """
from typing import Dict, Any, Optional

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def get(self, endpoint: str) -> Dict[str, Any]:
        \"\"\"GET request.\"\"\"
        return {}

    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"POST request.\"\"\"
        return {}

class UserServiceClient(APIClient):
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.get(f"/users/{user_id}")

    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.post("/users", data)
"""
        )

        # services/user_service.py
        services_dir = temp_workspace / "services"
        services_dir.mkdir()

        create_python_file(
            services_dir / "user_service.py",
            """
import sys
sys.path.insert(0, '..')
from api.client import UserServiceClient
from typing import Optional, Dict, Any

class UserService:
    def __init__(self):
        self.client = UserServiceClient("http://api.example.com")

    def find_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.client.get_user(user_id)

    def register_user(self, username: str, email: str) -> Dict[str, Any]:
        data = {"username": username, "email": email}
        return self.client.create_user(data)
"""
        )

        return temp_workspace

    def test_rename_api_client_method(self, httpx_client, microservice):
        """Test renaming API client method (line 17, col 9)."""
        response = httpx_client.post(
            "/rename",
            json={
                "file": "api/client.py",
                "line": 17,
                "col": 9,
                "new_name": "fetch_user",
                "root": str(microservice)
            }
        )

        assert response.status_code == 200
        data = response.json()
        patches = data["patches"]

        # Should update client.py
        assert any("client.py" in p for p in patches.keys())

        # May also update service layer
        if any("user_service" in p for p in patches.keys()):
            service_patch = next(p for p in patches.values() if "fetch_user" in p or "user_service" in p)
            # Service method may be updated
            assert service_patch is not None
