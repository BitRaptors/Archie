"""Tests for ArchitectureValidator."""
import pytest
from unittest.mock import AsyncMock, MagicMock


class TestArchitectureValidator:
    """Tests for architecture validator functionality."""
    
    @pytest.fixture
    def mock_resolver(self, sample_resolved_architecture):
        """Create mock resolver."""
        mock = MagicMock()
        mock.get_rules_for_repository = AsyncMock(return_value=sample_resolved_architecture)
        return mock
    
    @pytest.fixture
    def validator(self, mock_resolver):
        """Create validator instance."""
        from application.services.architecture_validator import ArchitectureValidator
        return ArchitectureValidator(resolver=mock_resolver)
    
    @pytest.mark.asyncio
    async def test_validate_file_returns_result(self, validator):
        """Verify validate_file returns a result."""
        result = await validator.validate_file(
            repository_id="test-repo-123",
            file_path="src/handlers/user.py",
            content="from src.services import UserService\nclass UserHandler: pass",
        )
        
        assert result is not None
        assert result.file_path == "src/handlers/user.py"
    
    @pytest.mark.asyncio
    async def test_validate_file_checks_rules(self, validator):
        """Verify validate_file checks rules."""
        result = await validator.validate_file(
            repository_id="test-repo-123",
            file_path="src/handlers/user.py",
            content="import os\nclass UserHandler: pass",
        )
        
        # Rules should have been checked
        assert result.rules_checked > 0
    
    @pytest.mark.asyncio
    async def test_validate_change_multiple_files(self, validator):
        """Verify validate_change handles multiple files."""
        report = await validator.validate_change(
            repository_id="test-repo-123",
            changed_files=[
                {"path": "src/handlers/user.py", "content": "class UserHandler: pass"},
                {"path": "src/services/auth.py", "content": "class AuthService: pass"},
            ],
        )
        
        assert report.total_files == 2
    
    @pytest.mark.asyncio
    async def test_check_file_location(self, validator):
        """Verify check_file_location works."""
        result = await validator.check_file_location(
            repository_id="test-repo-123",
            file_path="src/handlers/user.py",
        )
        
        assert result is not None
        assert result.file_path == "src/handlers/user.py"
    
    def test_extract_imports_python(self, validator):
        """Test Python import extraction."""
        content = """
import os
from typing import List
from src.services import UserService
from src.domain.user import User
"""
        imports = validator._extract_imports(content, "test.py")
        
        assert "os" in imports
        assert "typing" in imports
        assert "src.services" in imports
        assert "src.domain.user" in imports
    
    def test_extract_imports_typescript(self, validator):
        """Test TypeScript import extraction."""
        content = """
import React from 'react';
import { UserService } from '../services/user';
const axios = require('axios');
"""
        imports = validator._extract_imports(content, "test.ts")
        
        assert "react" in imports
        assert "../services/user" in imports
        assert "axios" in imports
    
    def test_matches_pattern(self, validator):
        """Test pattern matching."""
        assert validator._matches_pattern("user_service.py", "*_service.py")
        assert validator._matches_pattern("src/services/user.py", "src/services")
        assert not validator._matches_pattern("user.py", "*_service.py")
    
    def test_get_file_type(self, validator):
        """Test file type detection."""
        assert validator._get_file_type(".py") == "python"
        assert validator._get_file_type(".ts") == "typescript"
        assert validator._get_file_type(".js") == "javascript"
        assert validator._get_file_type(".go") == "go"
