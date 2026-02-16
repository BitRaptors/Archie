"""Tests for ArchitectureResolver."""
import pytest
from unittest.mock import AsyncMock


class TestArchitectureResolver:
    """Tests for architecture resolver functionality."""
    
    @pytest.fixture
    def resolver(
        self,
        mock_architecture_rule_repo,
        mock_repository_architecture_repo,
        mock_config_repo,
    ):
        """Create resolver instance with mocked repositories."""
        from application.services.architecture_resolver import ArchitectureResolver
        return ArchitectureResolver(
            architecture_rule_repo=mock_architecture_rule_repo,
            repository_architecture_repo=mock_repository_architecture_repo,
            config_repo=mock_config_repo,
        )
    
    @pytest.mark.asyncio
    async def test_get_rules_with_learned_primary_strategy(
        self,
        resolver,
        mock_config_repo,
        mock_repository_architecture_repo,
        mock_architecture_rule_repo,
        sample_learned_rules,
        sample_reference_rules,
        sample_repository_config,
    ):
        """Verify learned_primary strategy gives precedence to learned rules."""
        # Setup mocks
        sample_repository_config.merge_strategy = "learned_primary"
        mock_config_repo.get_by_repository_id.return_value = sample_repository_config
        mock_repository_architecture_repo.get_by_repository_id.return_value = sample_learned_rules
        mock_architecture_rule_repo.get_by_blueprint_id.return_value = sample_reference_rules
        
        result = await resolver.get_rules_for_repository("test-repo-123")
        
        assert result is not None
        assert result.learned_rules_count == len(sample_learned_rules)
    
    @pytest.mark.asyncio
    async def test_get_rules_with_reference_primary_strategy(
        self,
        resolver,
        mock_config_repo,
        mock_repository_architecture_repo,
        mock_architecture_rule_repo,
        sample_learned_rules,
        sample_reference_rules,
        sample_repository_config,
    ):
        """Verify reference_primary strategy gives precedence to reference rules."""
        sample_repository_config.merge_strategy = "reference_primary"
        mock_config_repo.get_by_repository_id.return_value = sample_repository_config
        mock_repository_architecture_repo.get_by_repository_id.return_value = sample_learned_rules
        mock_architecture_rule_repo.get_by_blueprint_id.return_value = sample_reference_rules
        
        result = await resolver.get_rules_for_repository("test-repo-123")
        
        assert result is not None
        assert result.reference_rules_count == len(sample_reference_rules)
    
    @pytest.mark.asyncio
    async def test_get_rules_with_learned_only_strategy(
        self,
        resolver,
        mock_config_repo,
        mock_repository_architecture_repo,
        sample_learned_rules,
        sample_repository_config,
    ):
        """Verify learned_only strategy only returns learned rules."""
        sample_repository_config.merge_strategy = "learned_only"
        mock_config_repo.get_by_repository_id.return_value = sample_repository_config
        mock_repository_architecture_repo.get_by_repository_id.return_value = sample_learned_rules
        
        result = await resolver.get_rules_for_repository("test-repo-123")
        
        assert result is not None
        assert result.reference_rules_count == 0
        assert result.learned_rules_count == len(sample_learned_rules)
    
    @pytest.mark.asyncio
    async def test_get_rules_with_reference_only_strategy(
        self,
        resolver,
        mock_config_repo,
        mock_architecture_rule_repo,
        sample_reference_rules,
        sample_repository_config,
    ):
        """Verify reference_only strategy only returns reference rules."""
        sample_repository_config.merge_strategy = "reference_only"
        mock_config_repo.get_by_repository_id.return_value = sample_repository_config
        mock_architecture_rule_repo.get_by_blueprint_id.return_value = sample_reference_rules
        
        result = await resolver.get_rules_for_repository("test-repo-123")
        
        assert result is not None
        assert result.learned_rules_count == 0
    
    @pytest.mark.asyncio
    async def test_get_rules_without_config(
        self,
        resolver,
        mock_config_repo,
        mock_repository_architecture_repo,
        sample_learned_rules,
    ):
        """Verify default behavior when no config exists."""
        mock_config_repo.get_by_repository_id.return_value = None
        mock_repository_architecture_repo.get_by_repository_id.return_value = sample_learned_rules
        
        result = await resolver.get_rules_for_repository("test-repo-123")
        
        # Should default to learned rules
        assert result is not None
        assert result.learned_rules_count == len(sample_learned_rules)
    
    @pytest.mark.asyncio
    async def test_fills_gaps_from_fallback(
        self,
        resolver,
        mock_config_repo,
        mock_repository_architecture_repo,
        mock_architecture_rule_repo,
        sample_repository_config,
    ):
        """Verify missing rules are filled from fallback source."""
        from domain.entities.architecture_rule import ArchitectureRule
        
        # Learned rules have purpose type only
        learned = [
            ArchitectureRule.create_learned_rule(
                repository_id="test-repo",
                rule_type="purpose",
                rule_id="purpose-1",
                name="Purpose Rule",
                rule_data={},
            )
        ]
        
        # Reference rules have layer type only
        reference = [
            ArchitectureRule.create_reference_rule(
                blueprint_id="python-backend",
                rule_type="layer",
                rule_id="layer-1",
                name="Layer Rule",
                rule_data={},
            )
        ]
        
        sample_repository_config.merge_strategy = "learned_primary"
        mock_config_repo.get_by_repository_id.return_value = sample_repository_config
        mock_repository_architecture_repo.get_by_repository_id.return_value = learned
        mock_architecture_rule_repo.get_by_blueprint_id.return_value = reference
        
        result = await resolver.get_rules_for_repository("test-repo-123")
        
        # Should have both purpose (learned) and layer (reference) rules
        assert result.learned_rules_count == 1
        assert result.reference_rules_count == 1
        assert len(result.rules) == 2
    
    @pytest.mark.asyncio
    async def test_configure_repository(
        self,
        resolver,
        mock_config_repo,
    ):
        """Verify repository configuration works."""
        from domain.entities.architecture_rule import RepositoryArchitectureConfig
        
        mock_config_repo.upsert.return_value = RepositoryArchitectureConfig.create(
            repository_id="test-repo-123",
            reference_blueprint_id="python-backend",
            merge_strategy="reference_primary",
        )
        
        config = await resolver.configure_repository(
            repository_id="test-repo-123",
            reference_blueprint_id="python-backend",
            merge_strategy="reference_primary",
        )
        
        assert config.merge_strategy == "reference_primary"
        mock_config_repo.upsert.assert_called_once()
