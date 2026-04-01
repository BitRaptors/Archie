"""Tests for ArchitectureRule domain entity."""
import pytest


class TestArchitectureRule:
    """Tests for ArchitectureRule entity."""
    
    def test_create_reference_rule(self):
        """Test creating a reference architecture rule."""
        from domain.entities.architecture_rule import ArchitectureRule
        
        rule = ArchitectureRule.create_reference_rule(
            blueprint_id="python-backend",
            rule_type="layer",
            rule_id="layer-presentation",
            name="Presentation Layer",
            rule_data={"location": "src/api/"},
        )
        
        assert rule.blueprint_id == "python-backend"
        assert rule.rule_type == "layer"
        assert rule.is_reference_rule()
        assert not rule.is_learned_rule()
    
    def test_create_learned_rule(self):
        """Test creating a learned architecture rule."""
        from domain.entities.architecture_rule import ArchitectureRule
        
        rule = ArchitectureRule.create_learned_rule(
            repository_id="repo-123",
            rule_type="purpose",
            rule_id="purpose-handlers",
            name="Purpose of handlers",
            rule_data={"purpose": "HTTP handling"},
            confidence=0.9,
        )
        
        assert rule.repository_id == "repo-123"
        assert rule.rule_type == "purpose"
        assert rule.confidence == 0.9
        assert rule.is_learned_rule()
        assert not rule.is_reference_rule()
    
    def test_to_dict(self):
        """Test converting rule to dictionary."""
        from domain.entities.architecture_rule import ArchitectureRule
        
        rule = ArchitectureRule.create_learned_rule(
            repository_id="repo-123",
            rule_type="purpose",
            rule_id="test-rule",
            name="Test Rule",
            rule_data={"key": "value"},
            confidence=0.85,
        )
        
        d = rule.to_dict()
        
        assert d["rule_type"] == "purpose"
        assert d["rule_id"] == "test-rule"
        assert d["confidence"] == 0.85
        assert d["rule_data"]["key"] == "value"


class TestRepositoryArchitectureConfig:
    """Tests for RepositoryArchitectureConfig entity."""
    
    def test_create_with_defaults(self):
        """Test creating config with defaults."""
        from domain.entities.architecture_rule import RepositoryArchitectureConfig
        
        config = RepositoryArchitectureConfig.create(repository_id="repo-123")
        
        assert config.repository_id == "repo-123"
        assert config.use_learned_architecture is True
        assert config.merge_strategy == "learned_primary"
    
    def test_create_with_custom_strategy(self):
        """Test creating config with custom merge strategy."""
        from domain.entities.architecture_rule import RepositoryArchitectureConfig
        
        config = RepositoryArchitectureConfig.create(
            repository_id="repo-123",
            merge_strategy="reference_primary",
        )
        
        assert config.merge_strategy == "reference_primary"
    
    def test_invalid_strategy_raises(self):
        """Test that invalid strategy raises error."""
        from domain.entities.architecture_rule import RepositoryArchitectureConfig
        
        with pytest.raises(ValueError):
            RepositoryArchitectureConfig.create(
                repository_id="repo-123",
                merge_strategy="invalid_strategy",
            )
    
    def test_update_strategy(self):
        """Test updating merge strategy."""
        from domain.entities.architecture_rule import RepositoryArchitectureConfig
        
        config = RepositoryArchitectureConfig.create(repository_id="repo-123")
        config.update_strategy("learned_only")
        
        assert config.merge_strategy == "learned_only"
        assert config.updated_at is not None
    
    def test_update_invalid_strategy_raises(self):
        """Test that updating with invalid strategy raises."""
        from domain.entities.architecture_rule import RepositoryArchitectureConfig
        
        config = RepositoryArchitectureConfig.create(repository_id="repo-123")
        
        with pytest.raises(ValueError):
            config.update_strategy("bad_strategy")
