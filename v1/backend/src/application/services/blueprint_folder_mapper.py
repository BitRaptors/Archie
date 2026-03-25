"""BlueprintFolderMapper — maps StructuredBlueprint sections onto folder paths."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from domain.entities.blueprint import StructuredBlueprint
from domain.entities.intent_layer import FolderBlueprint


def _normalize_path(p: str) -> str:
    """Normalize a folder/file path for matching."""
    p = p.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def _is_child_of(child: str, parent: str) -> bool:
    """True if *child* is strictly inside *parent*."""
    if not parent:
        return bool(child)
    return child.startswith(parent + "/")


def _is_parent_of(parent: str, child: str) -> bool:
    """True if *parent* strictly contains *child*."""
    return _is_child_of(child, parent)


def _path_specificity(path: str) -> int:
    """Deeper path = higher specificity."""
    if not path:
        return 0
    return path.count("/") + 1


def _path_segments(path: str) -> set[str]:
    """Return set of path segments for keyword matching."""
    if not path:
        return set()
    return {s.lower() for s in path.split("/")}


def compute_blueprint_hash(blueprint: StructuredBlueprint) -> str:
    """Compute a deterministic SHA-256 hash of the blueprint content."""
    data = blueprint.model_dump(mode="json")
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class BlueprintFolderMapper:
    """Maps a StructuredBlueprint onto folder paths → FolderBlueprint per folder."""

    def map_all(
        self,
        blueprint: StructuredBlueprint,
        folder_paths: list[str],
    ) -> dict[str, FolderBlueprint]:
        """Map all blueprint sections onto the given folder paths.

        Returns dict[folder_path, FolderBlueprint] for every input path.
        """
        norm_paths = [_normalize_path(p) for p in folder_paths]
        result: dict[str, FolderBlueprint] = {
            p: FolderBlueprint(path=p) for p in norm_paths
        }

        # First pass: populate from blueprint sections
        self._match_components(blueprint, result)
        self._match_file_placement_rules(blueprint, result)
        self._match_naming_conventions(blueprint, result)
        self._match_where_to_put(blueprint, result)
        self._match_recipes(blueprint, result)
        self._match_pitfalls(blueprint, result)
        self._match_implementation_guidelines(blueprint, result)
        self._match_contracts(blueprint, result)
        self._match_communication_patterns(blueprint, result)
        self._match_templates(blueprint, result)

        # Set has_blueprint_coverage flag
        for fb in result.values():
            fb.has_blueprint_coverage = self._has_coverage(fb)

        # Second pass: populate navigation fields
        self._populate_navigation(result)

        return result

    # ── Component matching ──

    def _match_components(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        """Match components to folders. Most specific match wins."""
        components = blueprint.components.components
        if not components:
            return

        for folder_path, fb in fbs.items():
            best_comp = None
            best_specificity = -1
            match_type = None  # exact, child, parent

            for comp in components:
                comp_loc = _normalize_path(comp.location) if comp.location else ""
                if not comp_loc:
                    continue

                if folder_path == comp_loc:
                    specificity = _path_specificity(comp_loc) * 3  # Exact wins
                    if specificity > best_specificity:
                        best_comp = comp
                        best_specificity = specificity
                        match_type = "exact"
                elif _is_child_of(folder_path, comp_loc):
                    specificity = _path_specificity(comp_loc) * 2  # Child
                    if specificity > best_specificity:
                        best_comp = comp
                        best_specificity = specificity
                        match_type = "child"
                elif _is_parent_of(folder_path, comp_loc):
                    specificity = _path_specificity(comp_loc)  # Parent (weakest)
                    if specificity > best_specificity:
                        best_comp = comp
                        best_specificity = specificity
                        match_type = "parent"

            if best_comp:
                fb.component_name = best_comp.name
                fb.component_responsibility = best_comp.responsibility
                fb.depends_on = list(best_comp.depends_on)
                fb.exposes_to = list(best_comp.exposes_to)
                fb.key_interfaces = [
                    {"name": ki.name, "methods": list(ki.methods), "description": ki.description}
                    for ki in best_comp.key_interfaces
                ]
                fb.key_files = list(best_comp.key_files)

    # ── Architecture rules ──

    def _match_file_placement_rules(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        rules = blueprint.architecture_rules.file_placement_rules
        for rule in rules:
            rule_loc = _normalize_path(rule.location) if rule.location else ""
            entry = {
                "component_type": rule.component_type,
                "naming_pattern": rule.naming_pattern,
                "example": rule.example,
                "description": rule.description,
            }
            for folder_path, fb in fbs.items():
                if not rule_loc:
                    continue
                if folder_path == rule_loc or _is_child_of(folder_path, rule_loc):
                    fb.file_placement_rules.append(entry)

    def _match_naming_conventions(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        """Naming conventions are global — apply to all folders."""
        conventions = blueprint.architecture_rules.naming_conventions
        if not conventions:
            return
        entries = [
            {"scope": nc.scope, "pattern": nc.pattern, "examples": ", ".join(nc.examples)}
            for nc in conventions
        ]
        for fb in fbs.values():
            fb.naming_conventions = list(entries)

    # ── Quick reference ──

    def _match_where_to_put(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        """Match where_to_put_code entries whose location contains this folder path."""
        wtp = blueprint.quick_reference.where_to_put_code
        if not wtp:
            return
        for folder_path, fb in fbs.items():
            for code_type, location in wtp.items():
                loc_norm = _normalize_path(location)
                if folder_path == loc_norm or _is_child_of(loc_norm, folder_path) or _is_child_of(folder_path, loc_norm):
                    fb.where_to_put[code_type] = location

    # ── Developer guidance ──

    def _match_recipes(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        """Match recipes whose files reference this folder."""
        for recipe in blueprint.developer_recipes:
            entry = {
                "task": recipe.task,
                "files": list(recipe.files),
                "steps": list(recipe.steps),
            }
            for folder_path, fb in fbs.items():
                for f in recipe.files:
                    f_norm = _normalize_path(f)
                    f_dir = f_norm.rsplit("/", 1)[0] if "/" in f_norm else ""
                    if folder_path == f_dir or _is_child_of(f_dir, folder_path):
                        fb.recipes.append(entry)
                        break

    def _match_pitfalls(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        """Match pitfalls by keyword overlap between area and folder path segments."""
        for pitfall in blueprint.pitfalls:
            area_keywords = {w.lower() for w in pitfall.area.replace("/", " ").replace("-", " ").replace("_", " ").split() if len(w) > 2}
            entry = {
                "area": pitfall.area,
                "description": pitfall.description,
                "recommendation": pitfall.recommendation,
            }
            for folder_path, fb in fbs.items():
                folder_keywords = _path_segments(folder_path)
                if area_keywords & folder_keywords:
                    fb.pitfalls.append(entry)

    def _match_implementation_guidelines(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        """Match implementation guidelines whose key_files are in this folder."""
        for guideline in blueprint.implementation_guidelines:
            entry = {
                "capability": guideline.capability,
                "libraries": list(guideline.libraries),
                "pattern_description": guideline.pattern_description,
                "key_files": list(guideline.key_files),
            }
            for folder_path, fb in fbs.items():
                for kf in guideline.key_files:
                    kf_norm = _normalize_path(kf)
                    kf_dir = kf_norm.rsplit("/", 1)[0] if "/" in kf_norm else ""
                    if folder_path == kf_dir or _is_child_of(kf_dir, folder_path):
                        fb.implementation_guidelines.append(entry)
                        break

    # ── Contracts & communication ──

    def _match_contracts(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        """Match contracts whose implementing_files are in this folder."""
        for contract in blueprint.components.contracts:
            entry = {
                "interface_name": contract.interface_name,
                "description": contract.description,
                "methods": list(contract.methods),
            }
            for folder_path, fb in fbs.items():
                for impl_file in contract.implementing_files:
                    f_norm = _normalize_path(impl_file)
                    f_dir = f_norm.rsplit("/", 1)[0] if "/" in f_norm else ""
                    if folder_path == f_dir or _is_child_of(f_dir, folder_path):
                        fb.contracts.append(entry)
                        break

    def _match_communication_patterns(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        """Match communication patterns whose examples reference files in this folder."""
        for pattern in blueprint.communication.patterns:
            entry = {
                "name": pattern.name,
                "when_to_use": pattern.when_to_use,
                "how_it_works": pattern.how_it_works,
            }
            for folder_path, fb in fbs.items():
                for ex in pattern.examples:
                    ex_norm = _normalize_path(ex)
                    ex_dir = ex_norm.rsplit("/", 1)[0] if "/" in ex_norm else ""
                    if folder_path == ex_dir or _is_child_of(ex_dir, folder_path):
                        fb.communication_patterns.append(entry)
                        break

    # ── Templates ──

    def _match_templates(
        self,
        blueprint: StructuredBlueprint,
        fbs: dict[str, FolderBlueprint],
    ) -> None:
        """Match templates whose file_path_template is in this folder."""
        for tmpl in blueprint.technology.templates:
            entry = {
                "component_type": tmpl.component_type,
                "file_path_template": tmpl.file_path_template,
                "code": tmpl.code,
            }
            if not tmpl.file_path_template:
                continue
            tmpl_dir = _normalize_path(tmpl.file_path_template)
            tmpl_dir = tmpl_dir.rsplit("/", 1)[0] if "/" in tmpl_dir else ""
            for folder_path, fb in fbs.items():
                if folder_path == tmpl_dir or _is_child_of(tmpl_dir, folder_path):
                    fb.templates.append(entry)

    # ── Navigation (second pass) ──

    def _populate_navigation(self, fbs: dict[str, FolderBlueprint]) -> None:
        """Populate parent_path, peer_paths, children_summaries from the folder set."""
        all_paths = set(fbs.keys())

        for folder_path, fb in fbs.items():
            # Parent path
            if "/" in folder_path:
                parent = folder_path.rsplit("/", 1)[0]
            elif folder_path:
                parent = ""
            else:
                parent = ""
            fb.parent_path = parent

            # Parent component
            if parent in fbs:
                fb.parent_component = fbs[parent].component_name

            # Children summaries
            for other_path, other_fb in fbs.items():
                if other_path == folder_path:
                    continue
                if "/" in other_path:
                    other_parent = other_path.rsplit("/", 1)[0]
                elif other_path:
                    other_parent = ""
                else:
                    continue
                if other_parent == folder_path:
                    fb.children_summaries.append({
                        "path": other_path,
                        "component_name": other_fb.component_name,
                        "responsibility": other_fb.component_responsibility,
                    })

            # Peer paths (siblings sharing same parent)
            for other_path in all_paths:
                if other_path == folder_path:
                    continue
                if "/" in other_path:
                    other_parent = other_path.rsplit("/", 1)[0]
                elif other_path:
                    other_parent = ""
                else:
                    other_parent = ""
                if other_parent == parent and folder_path != "" and other_path != "":
                    fb.peer_paths.append(other_path)

            fb.peer_paths.sort()
            fb.children_summaries.sort(key=lambda x: x["path"])

    # ── Coverage check ──

    @staticmethod
    def _has_coverage(fb: FolderBlueprint) -> bool:
        """Check if a FolderBlueprint has any meaningful data from the blueprint."""
        return bool(
            fb.component_name
            or fb.file_placement_rules
            or fb.where_to_put
            or fb.recipes
            or fb.pitfalls
            or fb.implementation_guidelines
            or fb.contracts
            or fb.communication_patterns
            or fb.templates
            or fb.key_files
        )
