"""Architecture extractor service for parsing blueprints into structured rules."""
import json
import logging
import re
from typing import Any

from anthropic import AsyncAnthropic

from domain.entities.architecture_rule import ArchitectureRule
from infrastructure.prompts.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class ArchitectureExtractor:
    """Extracts structured architecture rules from blueprints.
    
    This service parses markdown blueprints (both reference templates and
    generated analysis) into structured, queryable rules stored in Supabase.
    """
    
    def __init__(
        self,
        ai_client: AsyncAnthropic | None = None,
        prompt_loader: PromptLoader | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize extractor.
        
        Args:
            ai_client: Optional Anthropic client for AI-assisted extraction
            prompt_loader: Loader for prompts
            model: AI model to use
        """
        self._ai_client = ai_client
        self._prompt_loader = prompt_loader
        self._model = model
    
    async def extract_from_blueprint(
        self,
        blueprint_content: str,
        blueprint_id: str,
    ) -> list[ArchitectureRule]:
        """Extract rules from a markdown blueprint.
        
        Args:
            blueprint_content: Markdown content of the blueprint
            blueprint_id: Identifier for the blueprint (e.g., 'python-backend')
            
        Returns:
            List of extracted ArchitectureRule objects
        """
        rules = []
        
        # Extract layer rules
        layer_rules = await self.extract_layer_rules(blueprint_content, blueprint_id)
        rules.extend(layer_rules)
        
        # Extract pattern rules
        pattern_rules = await self.extract_pattern_rules(blueprint_content, blueprint_id)
        rules.extend(pattern_rules)
        
        # Extract location rules
        location_rules = await self.extract_location_rules(blueprint_content, blueprint_id)
        rules.extend(location_rules)
        
        # Extract principle rules
        principle_rules = await self.extract_principle_rules(blueprint_content, blueprint_id)
        rules.extend(principle_rules)
        
        # Extract anti-pattern rules
        anti_pattern_rules = await self.extract_anti_pattern_rules(blueprint_content, blueprint_id)
        rules.extend(anti_pattern_rules)
        
        logger.info(f"Extracted {len(rules)} rules from blueprint '{blueprint_id}'")
        
        return rules
    
    async def extract_layer_rules(
        self,
        content: str,
        blueprint_id: str,
    ) -> list[ArchitectureRule]:
        """Extract layer dependency rules from blueprint.
        
        Args:
            content: Blueprint content
            blueprint_id: Blueprint identifier
            
        Returns:
            List of layer rules
        """
        rules = []
        
        # Find layer section
        layer_section = self._extract_section(content, [
            "Layer Architecture",
            "Layers",
            "Layer Diagram",
            "Architecture Layers",
        ])
        
        if not layer_section:
            return rules
        
        # Parse layer definitions
        layers = self._parse_layers_from_section(layer_section)
        
        for layer in layers:
            rule = ArchitectureRule.create_reference_rule(
                blueprint_id=blueprint_id,
                rule_type="layer",
                rule_id=f"layer-{layer['name'].lower().replace(' ', '-')}",
                name=layer['name'],
                rule_data={
                    "location": layer.get("location", ""),
                    "responsibility": layer.get("responsibility", ""),
                    "contains": layer.get("contains", []),
                    "depends_on": layer.get("depends_on", []),
                    "exposes_to": layer.get("exposes_to", []),
                },
                description=layer.get("responsibility"),
            )
            rules.append(rule)
        
        # Parse dependency rules
        dep_rules_section = self._extract_section(content, [
            "Dependency Rules",
            "Import Rules",
            "Layer Dependencies",
        ])
        
        if dep_rules_section:
            allowed, forbidden = self._parse_dependency_rules(dep_rules_section)
            
            if allowed or forbidden:
                rule = ArchitectureRule.create_reference_rule(
                    blueprint_id=blueprint_id,
                    rule_type="layer",
                    rule_id="layer-dependency-rules",
                    name="Layer Dependency Rules",
                    rule_data={
                        "allowed_imports": allowed,
                        "forbidden_imports": forbidden,
                    },
                    description="Rules for layer dependencies",
                )
                rules.append(rule)
        
        return rules
    
    async def extract_pattern_rules(
        self,
        content: str,
        blueprint_id: str,
    ) -> list[ArchitectureRule]:
        """Extract design pattern rules from blueprint.
        
        Args:
            content: Blueprint content
            blueprint_id: Blueprint identifier
            
        Returns:
            List of pattern rules
        """
        rules = []
        
        # Find pattern section
        pattern_section = self._extract_section(content, [
            "Patterns",
            "Design Patterns",
            "Architectural Patterns",
            "Communication Patterns",
        ])
        
        if not pattern_section:
            return rules
        
        # Parse patterns using regex
        pattern_regex = r"###?\s+([^\n]+)\n(.*?)(?=###|$)"
        matches = re.findall(pattern_regex, pattern_section, re.DOTALL)
        
        for name, description in matches:
            name = name.strip()
            description = description.strip()
            
            if not name or len(name) > 100:
                continue
            
            # Skip non-pattern headers
            skip_words = ["table", "contents", "summary", "overview"]
            if any(word in name.lower() for word in skip_words):
                continue
            
            rule_id = f"pattern-{name.lower().replace(' ', '-')[:50]}"
            
            # Extract examples if present
            examples = self._extract_code_blocks(description)
            
            rule = ArchitectureRule.create_reference_rule(
                blueprint_id=blueprint_id,
                rule_type="pattern",
                rule_id=rule_id,
                name=name,
                rule_data={
                    "description": description[:2000],  # Limit description length
                    "usage": self._extract_usage_guidance(description),
                },
                description=description[:500] if description else None,
                examples={"code": examples} if examples else None,
            )
            rules.append(rule)
        
        return rules
    
    async def extract_location_rules(
        self,
        content: str,
        blueprint_id: str,
    ) -> list[ArchitectureRule]:
        """Extract file location convention rules from blueprint.
        
        Args:
            content: Blueprint content
            blueprint_id: Blueprint identifier
            
        Returns:
            List of location rules
        """
        rules = []
        
        # Find structure section
        structure_section = self._extract_section(content, [
            "Project Structure",
            "File Structure",
            "Directory Structure",
            "Folder Structure",
        ])
        
        if not structure_section:
            return rules
        
        # Parse directory tree
        tree_pattern = r"```[\s\S]*?```"
        tree_match = re.search(tree_pattern, structure_section)
        
        if tree_match:
            tree_content = tree_match.group(0)
            locations = self._parse_directory_tree(tree_content)
            
            for loc in locations:
                rule = ArchitectureRule.create_reference_rule(
                    blueprint_id=blueprint_id,
                    rule_type="location",
                    rule_id=f"location-{loc['path'].replace('/', '-').replace('.', '-')[:50]}",
                    name=f"Location: {loc['path']}",
                    rule_data={
                        "path": loc['path'],
                        "purpose": loc.get('purpose', ''),
                        "file_types": loc.get('file_types', []),
                    },
                    description=loc.get('purpose'),
                )
                rules.append(rule)
        
        return rules
    
    async def extract_principle_rules(
        self,
        content: str,
        blueprint_id: str,
    ) -> list[ArchitectureRule]:
        """Extract architectural principle rules from blueprint.
        
        Args:
            content: Blueprint content
            blueprint_id: Blueprint identifier
            
        Returns:
            List of principle rules
        """
        rules = []
        
        # Find principles section
        principles_section = self._extract_section(content, [
            "Core Principles",
            "Design Principles",
            "Principles",
            "Guidelines",
        ])
        
        if not principles_section:
            return rules
        
        # Parse principle items
        principle_pattern = r"[-*]\s+\*\*([^*]+)\*\*[:\s]*([^\n]+)"
        matches = re.findall(principle_pattern, principles_section)
        
        for i, (name, description) in enumerate(matches):
            name = name.strip()
            description = description.strip()
            
            rule = ArchitectureRule.create_reference_rule(
                blueprint_id=blueprint_id,
                rule_type="principle",
                rule_id=f"principle-{i}-{name.lower().replace(' ', '-')[:30]}",
                name=name,
                rule_data={
                    "principle": name,
                    "explanation": description,
                },
                description=description,
            )
            rules.append(rule)
        
        return rules
    
    async def extract_anti_pattern_rules(
        self,
        content: str,
        blueprint_id: str,
    ) -> list[ArchitectureRule]:
        """Extract anti-pattern rules from blueprint.
        
        Args:
            content: Blueprint content
            blueprint_id: Blueprint identifier
            
        Returns:
            List of anti-pattern rules
        """
        rules = []
        
        # Find anti-pattern section
        anti_section = self._extract_section(content, [
            "Anti-Patterns",
            "What to Avoid",
            "Don't Do",
            "Bad Practices",
        ])
        
        if not anti_section:
            return rules
        
        # Parse anti-pattern items
        anti_pattern = r"[-*]\s+([^\n]+)"
        matches = re.findall(anti_pattern, anti_section)
        
        for i, description in enumerate(matches):
            description = description.strip()
            if not description or len(description) < 10:
                continue
            
            rule = ArchitectureRule.create_reference_rule(
                blueprint_id=blueprint_id,
                rule_type="anti_pattern",
                rule_id=f"anti-pattern-{i}",
                name=f"Avoid: {description[:50]}",
                rule_data={
                    "pattern": description,
                    "reason": "Identified as anti-pattern in architecture blueprint",
                },
                description=description,
            )
            rules.append(rule)
        
        return rules
    
    def _extract_section(self, content: str, headers: list[str]) -> str | None:
        """Extract a section from markdown content.
        
        Args:
            content: Full markdown content
            headers: Possible section headers to look for
            
        Returns:
            Section content or None if not found
        """
        for header in headers:
            # Look for header - stop at next ## header (with space to not match ###)
            pattern = rf"##?\s+{re.escape(header)}[^\n]*\n(.*?)(?=\n## |\Z)"
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _parse_layers_from_section(self, section: str) -> list[dict[str, Any]]:
        """Parse layer definitions from a section.
        
        Args:
            section: Layer section content
            
        Returns:
            List of layer dictionaries
        """
        layers = []
        
        # Look for layer definitions (### Layer Name format)
        layer_pattern = r"###\s+([^\n]+)\n(.*?)(?=###|$)"
        matches = re.findall(layer_pattern, section, re.DOTALL)
        
        for name, content in matches:
            name = name.strip()
            content = content.strip()
            
            # Skip non-layer headers
            if any(word in name.lower() for word in ["diagram", "rules", "table"]):
                continue
            
            layer = {
                "name": name,
                "location": self._extract_field(content, ["Location", "Path", "Directory"]),
                "responsibility": self._extract_field(content, ["Responsibility", "Purpose", "Role"]),
                "contains": self._extract_list_field(content, ["Contains", "Components", "Includes"]),
                "depends_on": self._extract_list_field(content, ["Depends On", "Dependencies", "Uses"]),
                "exposes_to": self._extract_list_field(content, ["Exposes To", "Used By", "Consumers"]),
            }
            layers.append(layer)
        
        return layers
    
    def _extract_field(self, content: str, field_names: list[str]) -> str:
        """Extract a field value from content.
        
        Args:
            content: Content to search
            field_names: Possible field names
            
        Returns:
            Field value or empty string
        """
        for name in field_names:
            pattern = rf"\*?\*?{name}\*?\*?[:\s]+([^\n]+)"
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""
    
    def _extract_list_field(self, content: str, field_names: list[str]) -> list[str]:
        """Extract a list field from content.
        
        Args:
            content: Content to search
            field_names: Possible field names
            
        Returns:
            List of values
        """
        value = self._extract_field(content, field_names)
        if value:
            # Split by comma or bullet points
            items = re.split(r"[,•\-]", value)
            return [item.strip() for item in items if item.strip()]
        return []
    
    def _parse_dependency_rules(self, section: str) -> tuple[list[str], list[str]]:
        """Parse dependency rules from section.
        
        Args:
            section: Dependency rules section
            
        Returns:
            Tuple of (allowed, forbidden) rules
        """
        allowed = []
        forbidden = []
        
        # Look for allowed rules (✅ or "Allowed")
        allowed_pattern = r"[✅✓]\s*([^\n]+)|Allowed[:\s]*(.*?)(?=Forbidden|$)"
        allowed_matches = re.findall(allowed_pattern, section, re.IGNORECASE | re.DOTALL)
        for match in allowed_matches:
            text = match[0] or match[1]
            if text:
                items = [item.strip() for item in text.split("\n") if item.strip()]
                allowed.extend(items)
        
        # Look for forbidden rules (❌ or "Forbidden")
        forbidden_pattern = r"[❌✗]\s*([^\n]+)|Forbidden[:\s]*(.*?)(?=Allowed|$)"
        forbidden_matches = re.findall(forbidden_pattern, section, re.IGNORECASE | re.DOTALL)
        for match in forbidden_matches:
            text = match[0] or match[1]
            if text:
                items = [item.strip() for item in text.split("\n") if item.strip()]
                forbidden.extend(items)
        
        return allowed, forbidden
    
    def _extract_code_blocks(self, content: str) -> list[str]:
        """Extract code blocks from content.
        
        Args:
            content: Content with code blocks
            
        Returns:
            List of code block contents
        """
        pattern = r"```[\w]*\n(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)
        return [m.strip() for m in matches if m.strip()]
    
    def _extract_usage_guidance(self, content: str) -> str:
        """Extract usage guidance from pattern description.
        
        Args:
            content: Pattern description
            
        Returns:
            Usage guidance text
        """
        # Look for "When to use" or "Use when" patterns
        pattern = r"(?:When to use|Use when|Usage)[:\s]*(.*?)(?=When not|Example|$)"
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()[:500]
        return ""
    
    def _parse_directory_tree(self, tree_content: str) -> list[dict[str, Any]]:
        """Parse a directory tree code block.
        
        Args:
            tree_content: Directory tree content
            
        Returns:
            List of location dictionaries
        """
        locations = []
        
        # Remove code block markers
        tree_content = re.sub(r"```\w*\n?", "", tree_content)
        
        # Parse each line
        for line in tree_content.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Extract path (remove tree characters)
            path = re.sub(r"[│├└─\s]+", "", line)
            
            # Check if it's a directory or file
            if not path or path.startswith("#"):
                continue
            
            # Extract comment if present
            purpose = ""
            if "#" in line:
                purpose = line.split("#", 1)[1].strip()
            
            # Determine if file or directory
            is_file = "." in path.split("/")[-1]
            
            locations.append({
                "path": path,
                "purpose": purpose,
                "is_file": is_file,
                "file_types": [path.split(".")[-1]] if is_file else [],
            })
        
        return locations
