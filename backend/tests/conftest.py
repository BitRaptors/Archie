"""Shared test fixtures for architecture enforcement tests."""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from domain.entities.architecture_rule import ArchitectureRule, RepositoryArchitectureConfig
from domain.entities.validation_result import ValidationResult, Violation, ViolationSeverity
from domain.entities.resolved_architecture import ResolvedArchitecture
from domain.entities.worker_assignment import WorkerAssignment, OrchestrationPlan


@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample Python repository structure for testing."""
    # Create directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api").mkdir()
    (tmp_path / "src" / "services").mkdir()
    (tmp_path / "src" / "domain").mkdir()
    (tmp_path / "tests").mkdir()

    # Create Python files
    (tmp_path / "src" / "api" / "routes.py").write_text("""
from fastapi import APIRouter
from src.services.user_service import UserService

router = APIRouter()

@router.get("/users/{user_id}")
async def get_user(user_id: str):
    service = UserService()
    return await service.get(user_id)
""")

    (tmp_path / "src" / "services" / "user_service.py").write_text("""
from typing import Optional
from src.domain.user import User

class UserService:
    async def get(self, user_id: str) -> Optional[User]:
        return User(id=user_id)
""")

    (tmp_path / "src" / "domain" / "user.py").write_text("""
from dataclasses import dataclass

@dataclass
class User:
    id: str
    name: str = ""
    email: str = ""
""")

    (tmp_path / "requirements.txt").write_text("fastapi>=0.100.0\npydantic>=2.0.0\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-app"\n')

    return tmp_path


@pytest.fixture
def sample_codebase(tmp_path):
    """Create a sample codebase for testing."""
    # Create sample directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "handlers").mkdir()
    (tmp_path / "src" / "services").mkdir()
    (tmp_path / "src" / "domain").mkdir()
    (tmp_path / "tests").mkdir()
    
    # Create sample files
    (tmp_path / "src" / "handlers" / "user.py").write_text(
        "from src.services.user_service import UserService\n"
        "class UserHandler:\n"
        "    def __init__(self, service: UserService):\n"
        "        self._service = service\n"
        "    def get_user(self, user_id: str):\n"
        "        return self._service.get(user_id)\n"
    )
    
    (tmp_path / "src" / "services" / "user_service.py").write_text(
        "from src.domain.user import User\n"
        "class UserService:\n"
        "    def get(self, user_id: str) -> User:\n"
        "        return User(id=user_id)\n"
    )
    
    (tmp_path / "src" / "domain" / "user.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class User:\n"
        "    id: str\n"
        "    name: str = ''\n"
    )
    
    (tmp_path / "tests" / "test_user.py").write_text(
        "import pytest\n"
        "from src.services.user_service import UserService\n"
        "def test_get_user():\n"
        "    service = UserService()\n"
        "    user = service.get('123')\n"
        "    assert user.id == '123'\n"
    )
    
    (tmp_path / "requirements.txt").write_text("pytest>=7.0.0\nfastapi>=0.100.0\n")
    
    return tmp_path


@pytest.fixture
def sample_architecture_rules():
    """Sample architecture rules for testing."""
    return [
        ArchitectureRule.create_reference_rule(
            blueprint_id="python-backend",
            rule_type="layer",
            rule_id="layer-presentation",
            name="Presentation Layer",
            rule_data={
                "location": "src/handlers/",
                "responsibility": "HTTP request handling",
                "depends_on": ["Application Layer"],
            },
        ),
        ArchitectureRule.create_reference_rule(
            blueprint_id="python-backend",
            rule_type="layer",
            rule_id="layer-application",
            name="Application Layer",
            rule_data={
                "location": "src/services/",
                "responsibility": "Business logic orchestration",
                "depends_on": ["Domain Layer"],
            },
        ),
        ArchitectureRule.create_reference_rule(
            blueprint_id="python-backend",
            rule_type="layer",
            rule_id="layer-domain",
            name="Domain Layer",
            rule_data={
                "location": "src/domain/",
                "responsibility": "Core business entities",
                "depends_on": [],
            },
        ),
        ArchitectureRule.create_learned_rule(
            repository_id="test-repo-123",
            rule_type="purpose",
            rule_id="purpose-handlers-user",
            name="Purpose of handlers/user.py",
            rule_data={
                "file": "src/handlers/user.py",
                "purpose": "Handles user-related HTTP requests",
            },
            confidence=0.95,
            source_files=["src/handlers/user.py"],
        ),
        ArchitectureRule.create_learned_rule(
            repository_id="test-repo-123",
            rule_type="dependency",
            rule_id="dep-handlers-user",
            name="Dependencies of handlers/user.py",
            rule_data={
                "file": "src/handlers/user.py",
                "imports": ["src/services/user_service.py"],
            },
            confidence=0.9,
            source_files=["src/handlers/user.py"],
        ),
    ]


@pytest.fixture
def sample_learned_rules():
    """Sample learned architecture rules."""
    return [
        ArchitectureRule.create_learned_rule(
            repository_id="test-repo-123",
            rule_type="purpose",
            rule_id="purpose-handlers",
            name="Purpose of handlers directory",
            rule_data={
                "path": "src/handlers/",
                "purpose": "Contains HTTP request handlers",
            },
            confidence=0.9,
        ),
        ArchitectureRule.create_learned_rule(
            repository_id="test-repo-123",
            rule_type="convention",
            rule_id="conv-naming",
            name="Naming convention for services",
            rule_data={
                "pattern_type": "naming",
                "pattern": "*_service.py",
            },
            confidence=0.85,
        ),
    ]


@pytest.fixture
def sample_reference_rules():
    """Sample reference architecture rules."""
    return [
        ArchitectureRule.create_reference_rule(
            blueprint_id="python-backend",
            rule_type="layer",
            rule_id="layer-presentation",
            name="Presentation Layer",
            rule_data={
                "location": "src/api/",
                "responsibility": "HTTP handling",
            },
        ),
        ArchitectureRule.create_reference_rule(
            blueprint_id="python-backend",
            rule_type="pattern",
            rule_id="pattern-repository",
            name="Repository Pattern",
            rule_data={
                "description": "Abstract data access",
            },
        ),
    ]


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    mock = MagicMock()
    mock.anthropic_api_key = "test-api-key"
    mock.anthropic_model = "claude-3-sonnet-20240229"
    mock.default_ai_model = "claude-3-haiku-20240307"
    mock.storage_path = "/tmp/test_storage"
    return mock


@pytest.fixture
def mock_ai_client():
    """Mock Anthropic AI client for testing without API calls."""
    mock = AsyncMock()
    
    # Track call count to return different responses
    call_count = {"count": 0}
    
    # Response for observations (first call)
    observations_response = '{"file_purposes": {"src/handlers/user.py": "Handles user HTTP requests", "src/services/user_service.py": "User business logic"}, "dependencies": {"src/handlers/user.py": {"imports": ["src/services/user_service.py"], "imported_by": []}}, "observed_conventions": ["Test files follow naming pattern"], "observed_boundaries": []}'
    
    # Response for rules extraction (second call)
    rules_response = '{"rules": [{"rule_type": "purpose", "rule_id": "purpose-handlers-user", "name": "Purpose of handlers/user.py", "description": "Handles user HTTP requests", "rule_data": {"file": "src/handlers/user.py", "purpose": "HTTP handler"}, "confidence": 0.9, "source_files": ["src/handlers/user.py"]}]}'
    
    async def create_response(*args, **kwargs):
        call_count["count"] += 1
        # Alternate between observations and rules responses
        if call_count["count"] % 2 == 1:
            text = observations_response
        else:
            text = rules_response
        return MagicMock(content=[MagicMock(text=text)])
    
    mock.messages.create = create_response
    return mock


@pytest.fixture
def mock_observation_ai_client():
    """Mock AI client specifically for observation phase testing."""
    mock = AsyncMock()
    
    observation_response = '''```json
{
    "organization_style": "Layered architecture with clear separation",
    "detected_components": [
        {"type": "Handlers", "naming_pattern": "*.py in handlers/", "examples": ["user.py"]},
        {"type": "Services", "naming_pattern": "*_service.py", "examples": ["user_service.py"]},
        {"type": "Domain", "naming_pattern": "*.py in domain/", "examples": ["user.py"]}
    ],
    "dependency_flow": "Handlers -> Services -> Domain",
    "architecture_style": "Traditional layered with services",
    "unique_patterns": [],
    "standard_patterns_if_any": ["Service Layer", "Handler Pattern"],
    "key_search_terms": ["Handler", "Service", "domain"],
    "concerns": []
}
```'''
    
    async def create_response(*args, **kwargs):
        return MagicMock(content=[MagicMock(text=observation_response)])
    
    mock.messages.create = create_response
    return mock


@pytest.fixture
def sample_observation_result():
    """Sample observation phase result for testing."""
    return {
        "organization_style": "Layered architecture",
        "detected_components": [
            {"type": "Handlers", "naming_pattern": "*.py", "examples": ["user.py"]},
            {"type": "Services", "naming_pattern": "*_service.py", "examples": ["user_service.py"]},
        ],
        "architecture_style": "Traditional layered",
        "key_search_terms": ["Handler", "Service", "Repository"],
    }


@pytest.fixture
def sample_analysis_phases():
    """Sample analysis phases including observation for testing."""
    return [
        {
            "phase": "observation",
            "timestamp": "2024-01-01T00:00:00Z",
            "gathered": {"file_signatures": {"full_content": "...", "char_count": 1000}},
            "sent_to_ai": {"full_prompt": "Analyze architecture..."},
            "rag_retrieved": {},
        },
        {
            "phase": "discovery",
            "timestamp": "2024-01-01T00:01:00Z",
            "gathered": {"file_tree": {"full_content": "src/...", "char_count": 500}},
            "sent_to_ai": {"full_prompt": "Discover structure..."},
            "rag_retrieved": {"content": "...", "char_count": 200},
        },
        {
            "phase": "layers",
            "timestamp": "2024-01-01T00:02:00Z",
            "gathered": {},
            "sent_to_ai": {"full_prompt": "Identify layers..."},
            "rag_retrieved": {},
        },
        {
            "phase": "patterns",
            "timestamp": "2024-01-01T00:03:00Z",
            "gathered": {},
            "sent_to_ai": {"full_prompt": "Find patterns..."},
            "rag_retrieved": {},
        },
        {
            "phase": "communication",
            "timestamp": "2024-01-01T00:04:00Z",
            "gathered": {},
            "sent_to_ai": {"full_prompt": "Analyze communication..."},
            "rag_retrieved": {},
        },
        {
            "phase": "technology",
            "timestamp": "2024-01-01T00:05:00Z",
            "gathered": {},
            "sent_to_ai": {"full_prompt": "Identify tech stack..."},
            "rag_retrieved": {},
        },
        {
            "phase": "blueprint_synthesis",
            "timestamp": "2024-01-01T00:06:00Z",
            "gathered": {},
            "sent_to_ai": {"full_prompt": "Generate blueprint..."},
            "rag_retrieved": {},
        },
    ]


@pytest.fixture
def mock_prompt_loader():
    """Mock prompt loader."""
    mock = MagicMock()
    mock.get_prompt_by_key = MagicMock(return_value=None)
    return mock


@pytest.fixture
def sample_repository_config():
    """Sample repository architecture config."""
    return RepositoryArchitectureConfig.create(
        repository_id="test-repo-123",
        reference_blueprint_id="python-backend",
        use_learned_architecture=True,
        merge_strategy="learned_primary",
    )


@pytest.fixture
def sample_resolved_architecture(sample_architecture_rules, sample_repository_config):
    """Sample resolved architecture."""
    return ResolvedArchitecture.create(
        repository_id="test-repo-123",
        config=sample_repository_config,
        rules=sample_architecture_rules,
    )


@pytest.fixture
def mock_architecture_rule_repo():
    """Mock architecture rule repository."""
    mock = AsyncMock()
    mock.get_by_blueprint_id = AsyncMock(return_value=[])
    mock.add = AsyncMock()
    mock.delete_by_blueprint_id = AsyncMock(return_value=0)
    mock.list_blueprints = AsyncMock(return_value=["python-backend"])
    return mock


@pytest.fixture
def mock_repository_architecture_repo():
    """Mock repository architecture repository."""
    mock = AsyncMock()
    mock.get_by_repository_id = AsyncMock(return_value=[])
    mock.add_many = AsyncMock(return_value=[])
    mock.delete_by_repository_id = AsyncMock(return_value=0)
    return mock


@pytest.fixture
def mock_config_repo():
    """Mock repository architecture config repository."""
    mock = AsyncMock()
    mock.get_by_repository_id = AsyncMock(return_value=None)
    mock.upsert = AsyncMock()
    return mock
