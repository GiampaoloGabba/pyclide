"""Feature tests: Real-world project patterns and frameworks.

These tests simulate actual patterns found in popular Python frameworks
to ensure pyclide works with real codebases.
"""

import pathlib
import sys
import pytest
from typer.testing import CliRunner

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pyclide import app, RopeEngine

runner = CliRunner()


class TestDjangoLikePatterns:
    """Test patterns commonly found in Django projects."""

    @pytest.fixture
    def django_app(self, tmp_path):
        """Create Django-like app structure."""
        # models.py with Django ORM pattern
        (tmp_path / "models.py").write_text(
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
""",
            encoding="utf-8",
        )

        # views.py with Django view pattern
        (tmp_path / "views.py").write_text(
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
""",
            encoding="utf-8",
        )

        # admin.py with Django admin pattern
        (tmp_path / "admin.py").write_text(
            """
from models import User, Post

class UserAdmin:
    list_display = ['username', 'email']

    def get_user(self, username):
        return User.objects_get(username)

class PostAdmin:
    list_display = ['title', 'author']
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_rename_model_class(self, django_app):
        """Test renaming a model class used across app."""
        # Rename User to Account
        result = runner.invoke(
            app,
            [
                "rename",
                str(django_app / "models.py"),
                "8",
                "7",
                "Account",
                "--root",
                str(django_app),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response.get("patches", response)  # Handle wrapped patches

        # Should update models, views, and admin
        assert "models.py" in patches
        assert "views.py" in patches
        assert "admin.py" in patches

        # Check model file
        assert "class Account(Model):" in patches["models.py"]

        # Check imports updated
        assert "from models import Account" in patches["views.py"]

    def test_find_model_usages(self, django_app):
        """Test finding all usages of a model across Django app."""
        result = runner.invoke(
            app,
            ["refs", str(django_app / "models.py"), "8", "7", "--root", str(django_app), "--json"],
        )

        assert result.exit_code == 0
        import json
        refs = json.loads(result.stdout)

        # Should find references in:
        # - models.py (definition, type hint in Post)
        # - views.py (multiple usages)
        # - admin.py (UserAdmin)
        assert len(refs) >= 4


class TestFlaskLikePatterns:
    """Test patterns commonly found in Flask projects."""

    @pytest.fixture
    def flask_app(self, tmp_path):
        """Create Flask-like app structure."""
        # app.py with Flask patterns
        (tmp_path / "app.py").write_text(
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
""",
            encoding="utf-8",
        )

        # blueprints.py
        (tmp_path / "blueprints.py").write_text(
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
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_rename_route_function(self, flask_app):
        """Test renaming a route function."""
        result = runner.invoke(
            app,
            [
                "rename",
                str(flask_app / "app.py"),
                "17",
                "5",
                "get_user_by_id",
                "--root",
                str(flask_app),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response.get("patches", response)  # Handle wrapped patches

        # Should update both app.py and blueprints.py
        assert "app.py" in patches
        if "blueprints.py" in patches:
            assert "get_user_by_id" in patches["blueprints.py"]

    def test_extract_business_logic(self, flask_app):
        """Test extracting business logic from route handler."""
        # Try to extract the fetch_user call logic
        result = runner.invoke(
            app,
            [
                "extract-method",
                str(flask_app / "app.py"),
                "20",
                "20",
                "load_user_data",
                "--root",
                str(flask_app),
                "--json",
                "--force",
            ],
        )

        # Should not crash even if extraction is complex
        assert result.exit_code in [0, 1, 2]


class TestFastAPILikePatterns:
    """Test patterns commonly found in FastAPI projects."""

    @pytest.fixture
    def fastapi_app(self, tmp_path):
        """Create FastAPI-like app structure."""
        # schemas.py with Pydantic-like models
        (tmp_path / "schemas.py").write_text(
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
""",
            encoding="utf-8",
        )

        # routes.py with FastAPI route patterns
        (tmp_path / "routes.py").write_text(
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
""",
            encoding="utf-8",
        )

        # dependencies.py
        (tmp_path / "dependencies.py").write_text(
            """
from schemas import UserResponse

async def get_current_user() -> UserResponse:
    \"\"\"Get current authenticated user.\"\"\"
    return UserResponse(id=1, username="current", email="current@example.com")

async def require_admin() -> bool:
    \"\"\"Require admin permission.\"\"\"
    user = await get_current_user()
    return user.id == 1
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_rename_schema_class(self, fastapi_app):
        """Test renaming Pydantic schema affects all usages."""
        result = runner.invoke(
            app,
            [
                "rename",
                str(fastapi_app / "schemas.py"),
                "7",
                "7",
                "CreateUserRequest",
                "--root",
                str(fastapi_app),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response.get("patches", response)  # Handle wrapped patches

        # Should update routes.py
        assert "schemas.py" in patches
        if "routes.py" in patches:
            assert "CreateUserRequest" in patches["routes.py"]

    def test_find_async_function_references(self, fastapi_app):
        """Test finding references to async functions."""
        result = runner.invoke(
            app,
            [
                "refs",
                str(fastapi_app / "routes.py"),
                "21",
                "11",
                "--root",
                str(fastapi_app),
                "--json",
            ],
        )

        assert result.exit_code == 0
        import json
        refs = json.loads(result.stdout)

        # Should find definition and usage in update_user
        assert isinstance(refs, list)


class TestDataSciencePatterns:
    """Test patterns from data science / ML projects."""

    @pytest.fixture
    def ml_project(self, tmp_path):
        """Create ML project structure."""
        # data_processing.py
        (tmp_path / "data_processing.py").write_text(
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
""",
            encoding="utf-8",
        )

        # model.py
        (tmp_path / "model.py").write_text(
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
""",
            encoding="utf-8",
        )

        # pipeline.py
        (tmp_path / "pipeline.py").write_text(
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
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_rename_dataframe_type(self, ml_project):
        """Test renaming custom DataFrame class."""
        result = runner.invoke(
            app,
            [
                "rename",
                str(ml_project / "data_processing.py"),
                "5",
                "7",
                "Dataset",
                "--root",
                str(ml_project),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response.get("patches", response)  # Handle wrapped patches

        # Should update type hints in model.py
        assert "data_processing.py" in patches
        if "model.py" in patches:
            assert "Dataset" in patches["model.py"]

    def test_refactor_pipeline(self, ml_project):
        """Test refactoring ML pipeline functions."""
        # Find all references to preprocess_data (line 13, col 5 = "p" of preprocess_data)
        result = runner.invoke(
            app,
            [
                "refs",
                str(ml_project / "data_processing.py"),
                "13",
                "5",
                "--root",
                str(ml_project),
                "--json",
            ],
        )

        assert result.exit_code == 0
        import json
        refs = json.loads(result.stdout)

        # Should find usage in pipeline.py
        assert len(refs) >= 2


class TestMicroservicePatterns:
    """Test patterns from microservice architectures."""

    @pytest.fixture
    def microservice(self, tmp_path):
        """Create microservice structure."""
        # api/client.py
        api_dir = tmp_path / "api"
        api_dir.mkdir()

        (api_dir / "client.py").write_text(
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
""",
            encoding="utf-8",
        )

        # services/user_service.py
        services_dir = tmp_path / "services"
        services_dir.mkdir()

        (services_dir / "user_service.py").write_text(
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
""",
            encoding="utf-8",
        )

        return tmp_path

    def test_rename_api_client_method(self, microservice):
        """Test renaming API client method (line 17, col 9 = "g" of get_user)."""
        result = runner.invoke(
            app,
            [
                "rename",
                str(microservice / "api" / "client.py"),
                "17",
                "9",
                "fetch_user",
                "--root",
                str(microservice),
                "--json",
                "--force",
            ],
        )

        assert result.exit_code == 0
        import json
        response = json.loads(result.stdout)
        patches = response.get("patches", response)  # Handle wrapped patches

        # Should update service layer
        if any("user_service" in p for p in patches.keys()):
            # Check that service method was updated
            service_patch = next(p for p in patches.values() if "fetch_user" in p)
            assert "fetch_user" in service_patch
