"""Tests for StateManagement.global_state coercion.

The AI sometimes returns global_state items as plain strings
(especially for mobile projects) instead of the expected
[{"store": "...", "purpose": "..."}] dict format.

These tests verify that StructuredBlueprint.model_validate()
handles every shape the AI might return without crashing.
"""
import pytest

from domain.entities.blueprint import (
    Frontend,
    StateManagement,
    StructuredBlueprint,
)


class TestGlobalStateCoercion:
    """StateManagement.global_state must accept both dicts and strings."""

    def test_strings_coerced_to_dicts(self):
        """Plain strings are wrapped as {"description": "..."}."""
        sm = StateManagement(
            approach="UIKit + MVVM",
            global_state=[
                "NavigationState (current screen, navigation stack) in RootViewController",
                "AppState (user authentication, app lifecycle) in AppDelegate",
            ],
        )
        assert len(sm.global_state) == 2
        assert all(isinstance(item, dict) for item in sm.global_state)
        assert sm.global_state[0]["description"].startswith("NavigationState")
        assert sm.global_state[1]["description"].startswith("AppState")

    def test_dicts_pass_through(self):
        """Proper dict format is kept as-is."""
        sm = StateManagement(
            global_state=[
                {"store": "Redux", "purpose": "Global app state"},
                {"store": "React Query", "purpose": "Server cache"},
            ],
        )
        assert len(sm.global_state) == 2
        assert sm.global_state[0]["store"] == "Redux"
        assert sm.global_state[1]["store"] == "React Query"

    def test_mixed_strings_and_dicts(self):
        """A mix of strings and dicts both survive."""
        sm = StateManagement(
            global_state=[
                {"store": "Zustand", "purpose": "UI state"},
                "AuthState managed by Context",
            ],
        )
        assert len(sm.global_state) == 2
        assert sm.global_state[0]["store"] == "Zustand"
        assert sm.global_state[1]["description"] == "AuthState managed by Context"

    def test_empty_list(self):
        sm = StateManagement(global_state=[])
        assert sm.global_state == []

    def test_non_list_becomes_empty(self):
        """A scalar value (not a list) degrades to []."""
        sm = StateManagement(global_state="not a list")
        assert sm.global_state == []

    def test_nested_list_values_in_dict(self):
        """Dicts with list values (state_properties: [...]) are preserved."""
        sm = StateManagement(
            global_state=[
                {
                    "store": "NavigationState",
                    "state_properties": ["currentScreen", "navStack"],
                    "actions": ["push", "pop", "resetToRoot"],
                },
            ],
        )
        assert sm.global_state[0]["state_properties"] == ["currentScreen", "navStack"]
        assert sm.global_state[0]["actions"] == ["push", "pop", "resetToRoot"]


class TestFullBlueprintValidation:
    """StructuredBlueprint.model_validate() must not crash on real AI output shapes."""

    def _make_blueprint_dict(self, global_state_value):
        """Build a minimal blueprint dict with the given global_state."""
        return {
            "meta": {"repository": "Test/Repo", "schema_version": "2.0.0"},
            "frontend": {
                "framework": "UIKit",
                "state_management": {
                    "approach": "MVVM + Coordinator",
                    "global_state": global_state_value,
                    "server_state": "URLSession",
                    "local_state": "Published properties",
                },
            },
        }

    def test_validate_with_string_global_state(self):
        """The exact error case from production: strings in global_state."""
        data = self._make_blueprint_dict([
            "NavigationState (current screen, navigation stack) managed via RootViewController",
            "AppState (user authentication, app lifecycle) stored in AppDelegate or shared ViewModel",
        ])
        bp = StructuredBlueprint.model_validate(data)
        assert len(bp.frontend.state_management.global_state) == 2
        assert "NavigationState" in bp.frontend.state_management.global_state[0]["description"]

    def test_validate_with_dict_global_state(self):
        data = self._make_blueprint_dict([
            {"store": "Redux", "purpose": "Global state"},
        ])
        bp = StructuredBlueprint.model_validate(data)
        assert bp.frontend.state_management.global_state[0]["store"] == "Redux"

    def test_validate_with_empty_global_state(self):
        data = self._make_blueprint_dict([])
        bp = StructuredBlueprint.model_validate(data)
        assert bp.frontend.state_management.global_state == []

    def test_validate_with_complex_dict_global_state(self):
        """Dicts with nested lists (the other production error shape)."""
        data = self._make_blueprint_dict([
            {
                "store": "NavigationState",
                "state_properties": ["currentScreen", "navStack", "selectedTab"],
                "actions": ["navigateTo", "pop", "resetToRoot"],
                "managed_by": "Coordinator pattern in AppCoordinator",
            },
            {
                "store": "AppState",
                "state_properties": ["isAuthenticated", "currentUser"],
                "actions": ["login", "logout", "refreshToken"],
                "managed_by": "AppDelegate or shared ViewModel",
            },
        ])
        bp = StructuredBlueprint.model_validate(data)
        assert len(bp.frontend.state_management.global_state) == 2
        assert bp.frontend.state_management.global_state[0]["state_properties"] == [
            "currentScreen", "navStack", "selectedTab"
        ]
