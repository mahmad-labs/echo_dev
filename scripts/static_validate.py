#!/usr/bin/env python3
"""Dependency-free release checks for the Echo source tree.

This script deliberately avoids importing Django so it can validate an extracted
release before the Python dependencies are installed. It complements, rather
than replaces, ``manage.py check`` and the Django test suite.
"""
from __future__ import annotations

import ast
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "echo" / "apps"
DOMAIN_BASE_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "owner",
    "name",
    "title",
    "description",
    "status",
    "data",
}


class ValidationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def parse_python() -> int:
    paths = [path for path in ROOT.rglob("*.py") if ".venv" not in path.parts]
    for path in paths:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            fail(f"Python parse failed for {path.relative_to(ROOT)}: {exc}")
    return len(paths)


def migration_state() -> dict[tuple[str, str], set[str]]:
    states: dict[tuple[str, str], set[str]] = {}
    for app in APP_ROOT.iterdir():
        migration_dir = app / "migrations"
        if not migration_dir.is_dir():
            continue
        for path in sorted(migration_dir.glob("[0-9]*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for call in ast.walk(tree):
                if not (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "migrations"
                ):
                    continue
                operation = call.func.attr
                keywords = {item.arg: item.value for item in call.keywords if item.arg}

                def constant(name: str):
                    value = keywords.get(name)
                    return value.value if isinstance(value, ast.Constant) else None

                if operation == "CreateModel":
                    model_name = constant("name")
                    fields_node = keywords.get("fields")
                    fields: set[str] = set()
                    if isinstance(fields_node, (ast.List, ast.Tuple)):
                        for field_node in fields_node.elts:
                            if (
                                isinstance(field_node, (ast.List, ast.Tuple))
                                and field_node.elts
                                and isinstance(field_node.elts[0], ast.Constant)
                            ):
                                fields.add(str(field_node.elts[0].value))
                    if model_name:
                        states[(app.name, str(model_name).lower())] = fields
                elif operation == "AddField":
                    model_name, field_name = constant("model_name"), constant("name")
                    if model_name and field_name:
                        states.setdefault((app.name, str(model_name).lower()), set()).add(str(field_name))
                elif operation == "RemoveField":
                    model_name, field_name = constant("model_name"), constant("name")
                    if model_name and field_name:
                        states.setdefault((app.name, str(model_name).lower()), set()).discard(str(field_name))
                elif operation == "RenameField":
                    model_name = constant("model_name")
                    old_name, new_name = constant("old_name"), constant("new_name")
                    if model_name and old_name and new_name:
                        fields = states.setdefault((app.name, str(model_name).lower()), set())
                        fields.discard(str(old_name))
                        fields.add(str(new_name))
    return states


def model_declarations() -> tuple[dict[tuple[str, str], set[str]], set[tuple[str, str]]]:
    fields_by_model: dict[tuple[str, str], set[str]] = {}
    abstract_models: set[tuple[str, str]] = set()
    all_classes: set[tuple[str, str]] = set()
    for path in APP_ROOT.glob("*/models.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            key = (path.parent.name, class_node.name.lower())
            all_classes.add(key)
            direct_fields: set[str] = set()
            is_abstract = False
            for node in class_node.body:
                if isinstance(node, ast.ClassDef) and node.name == "Meta":
                    for statement in node.body:
                        if not isinstance(statement, ast.Assign):
                            continue
                        if (
                            any(isinstance(target, ast.Name) and target.id == "abstract" for target in statement.targets)
                            and isinstance(statement.value, ast.Constant)
                            and statement.value.value is True
                        ):
                            is_abstract = True
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                value = node.value
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    field_name = node.targets[0].id
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    field_name = node.target.id
                else:
                    field_name = ""
                if (
                    field_name
                    and isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Attribute)
                    and isinstance(value.func.value, ast.Name)
                    and value.func.value.id == "models"
                ):
                    direct_fields.add(field_name)
            if is_abstract:
                abstract_models.add(key)
            elif direct_fields:
                fields_by_model[key] = direct_fields
    return fields_by_model, all_classes - abstract_models


def validate_models() -> int:
    states = migration_state()
    declarations, concrete_classes = model_declarations()
    if len(states) != 189:
        fail(f"Expected 189 migration model states; found {len(states)}")
    missing_classes = sorted(set(states) - concrete_classes)
    if missing_classes:
        fail(f"Migration models missing source declarations: {missing_classes}")
    field_errors: list[str] = []
    for key, direct_fields in sorted(declarations.items()):
        if key not in states:
            field_errors.append(f"{key[0]}.{key[1]} has no migration state")
            continue
        missing = direct_fields - states[key]
        if missing:
            field_errors.append(f"{key[0]}.{key[1]} missing fields {sorted(missing)}")
    strict_domain_models = {
        ("voice", key[1]) for key in declarations if key[0] == "voice"
    } | {
        ("internet", name)
        for name in {
            "browsersession", "browserobservation", "browseraction",
            "computeruseoperation", "mediaunderstanding", "computersession", "computerobservation", "computeraction",
        }
    } | {
        ("agent_manager", name)
        for name in {"agent", "agenttask", "agentcommunication"}
    }
    for key, direct_fields in sorted(declarations.items()):
        if key not in strict_domain_models:
            continue
        expected = direct_fields | DOMAIN_BASE_FIELDS
        missing, extra = expected - states[key], states[key] - expected
        if missing or extra:
            field_errors.append(
                f"{key[0]}.{key[1]} migration mismatch; missing={sorted(missing)} extra={sorted(extra)}"
            )
    if field_errors:
        fail("; ".join(field_errors))
    return len(states)


def validate_apps() -> int:
    apps = [path for path in APP_ROOT.iterdir() if path.is_dir() and (path / "apps.py").is_file()]
    if len(apps) != 24:
        fail(f"Expected 24 application packages; found {len(apps)}")
    required = ("apps.py", "models.py", "admin.py", "urls.py", "tests.py")
    missing = [f"{app.name}/{name}" for app in apps for name in required if not (app / name).is_file()]
    if missing:
        fail(f"Required application files missing: {missing}")
    return len(apps)


def validate_endpoints() -> int:
    path = ROOT / "echo" / "spec_catalog.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    catalog = None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SPEC_ENDPOINTS" for target in node.targets)
        ):
            catalog = ast.literal_eval(node.value)
            break
    if not isinstance(catalog, list):
        fail("SPEC_ENDPOINTS is not a literal list")
    pairs = {(item["method"], item["path"]) for item in catalog}
    if len(catalog) != 238 or len(pairs) != 238:
        fail(f"Expected 238 unique compatibility endpoints; found {len(catalog)} entries/{len(pairs)} unique")
    return len(pairs)


def validate_templates() -> int:
    pairs = {
        "if": "endif",
        "for": "endfor",
        "block": "endblock",
        "with": "endwith",
        "comment": "endcomment",
        "spaceless": "endspaceless",
        "autoescape": "endautoescape",
        "filter": "endfilter",
        "verbatim": "endverbatim",
    }
    paths = list((ROOT / "templates").rglob("*.html"))
    errors: list[str] = []
    for path in paths:
        stack: list[str] = []
        for match in re.finditer(r"{%\s*(.*?)\s*%}", path.read_text(encoding="utf-8"), re.DOTALL):
            content = match.group(1).strip()
            if not content:
                continue
            token = content.split()[0]
            if token in pairs:
                stack.append(pairs[token])
            elif token in pairs.values():
                if not stack or stack[-1] != token:
                    errors.append(f"{path.relative_to(ROOT)} mismatched {token}")
                else:
                    stack.pop()
        if stack:
            errors.append(f"{path.relative_to(ROOT)} unclosed {stack}")
    if errors:
        fail("; ".join(errors))
    return len(paths)


def validate_assets() -> tuple[int, int]:
    icon_path = ROOT / "static" / "icons.svg"
    ET.parse(icon_path)
    icon_text = icon_path.read_text(encoding="utf-8")
    symbols = set(re.findall(r'<symbol\s+id="([^"]+)"', icon_text))
    references: set[str] = set()
    for path in (ROOT / "templates").rglob("*.html"):
        references.update(
            re.findall(r'<use\s+[^>]*href="[^"]*#([A-Za-z0-9_-]+)"', path.read_text(encoding="utf-8"))
        )

    dashboard_tree = ast.parse(
        (APP_ROOT / "dashboard" / "pages.py").read_text(encoding="utf-8"),
        filename="dashboard/pages.py",
    )
    constants: dict[str, object] = {}
    for node in dashboard_tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"NAV_GROUPS", "SECTION_META", "DATA_SOURCES"}
        ):
            constants[node.targets[0].id] = ast.literal_eval(node.value)
    for _, items in constants["NAV_GROUPS"]:
        references.update(item[2] for item in items)
    references.update(item["icon"] for item in constants["SECTION_META"].values())
    for sources in constants["DATA_SOURCES"].values():
        references.update(item[-1] for item in sources)

    missing = sorted(references - symbols)
    if missing:
        fail(f"Missing SVG symbols: {missing}")

    css_path = ROOT / "static" / "css" / "echo.css"
    css = re.sub(r"/\*.*?\*/", "", css_path.read_text(encoding="utf-8"), flags=re.DOTALL)
    if css.count("{") != css.count("}"):
        fail("CSS block braces are unbalanced")
    return len(symbols), css.count("{")


def validate_release_policy() -> None:
    prohibited_names = {
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
        "kubernetes",
        "k8s",
    }
    found = [str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.name in prohibited_names]
    if found:
        fail(f"Container artifacts are not allowed: {found}")
    pattern = re.compile(r"\b(TODO|FIXME|Coming Soon|Under Construction|fake AI|fake voice|mock response)\b", re.I)
    unfinished: list[str] = []
    for base in (ROOT / "echo", ROOT / "templates", ROOT / "static" / "js"):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".html", ".js"}:
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern.search(line):
                        unfinished.append(f"{path.relative_to(ROOT)}:{number}")
    if unfinished:
        fail(f"Unfinished implementation markers found: {unfinished}")



def validate_orchestration_contracts() -> None:
    orchestration = (APP_ROOT / "agent_manager" / "orchestration.py").read_text(encoding="utf-8")
    agent_registry = (APP_ROOT / "agent_manager" / "registry.py").read_text(encoding="utf-8")
    tool_registry = (APP_ROOT / "tool_manager" / "registry.py").read_text(encoding="utf-8")
    tool_execution = (APP_ROOT / "tool_manager" / "execution.py").read_text(encoding="utf-8")
    tool_apps = (APP_ROOT / "tool_manager" / "apps.py").read_text(encoding="utf-8")
    tooling = (APP_ROOT / "agent_manager" / "tooling.py").read_text(encoding="utf-8")
    desktop = (APP_ROOT / "internet" / "desktop_control.py").read_text(encoding="utf-8")
    browser = (APP_ROOT / "internet" / "computer_use.py").read_text(encoding="utf-8")
    domain_tools = (APP_ROOT / "tool_manager" / "domain_tools.py").read_text(encoding="utf-8")
    voice = (APP_ROOT / "voice" / "services.py").read_text(encoding="utf-8")

    required_agents = {"memory", "knowledge", "planner", "browser", "computer", "documents", "projects", "tasks", "workflow", "chat"}
    missing_agents = [name for name in sorted(required_agents) if f'AgentDefinition("{name}"' not in orchestration]
    if missing_agents:
        fail(f"Missing Agent Registry definitions: {missing_agents}")

    for token in ("ToolRegistry.bootstrap()", "register_core_tools", "register_computer_use_tools", "register_desktop_control_tools", "register_agent_tools", "register_domain_tools"):
        source = tool_apps + "\n" + tool_registry
        if token not in source:
            fail(f"Authoritative tool registry bootstrap contract missing {token}")
    if 'agent.execute' not in tooling or 'def register_agent_tools' not in tooling:
        fail("Workflow-to-Agent Manager bridge agent.execute is not registered through the authoritative registry")
    if 'def register_desktop_control_tools' not in desktop:
        fail("Desktop tools still rely on import side effects instead of explicit registration")
    if 'ToolExecutor.execute_named(f"computer.{action}"' not in desktop:
        fail("Computer command routing bypasses the central Tool Executor")
    if 'ToolExecutor.execute_named(tool_name, user' not in browser or 'agent="browser"' not in browser:
        fail("Browser operation execution is not routed through Tool Manager with agent identity")

    required_tools = {
        "browser.open_url", "browser.click", "browser.scroll", "browser.get_dom",
        "browser.get_accessibility_tree", "browser.get_screenshot", "media.analyze",
        "computer.observe", "computer.click", "computer.scroll", "computer.type",
        "computer.open_path", "computer.launch_application", "computer.list_applications",
        "computer.application_status", "computer.get_active_window", "computer.list_windows",
        "computer.focus_window", "computer.capture_screen", "computer.execute_task",
        "memory.search", "memory.store", "knowledge.search", "knowledge.ingest", "agent.execute",
    }
    combined = browser + "\n" + desktop + "\n" + domain_tools + "\n" + tooling
    missing_tools = []
    for name in sorted(required_tools):
        if name in combined:
            continue
        prefix, _, action = name.partition(".")
        source = browser if prefix in {"browser", "media"} else desktop if prefix == "computer" else domain_tools
        dynamic_registration = f'f"{prefix}.{{action}}"' in source or f"f'{prefix}.{{action}}'" in source
        if not dynamic_registration or not re.search(rf'["\']{re.escape(action)}["\']', source):
            missing_tools.append(name)
    if missing_tools:
        fail(f"Missing executable tool contracts: {missing_tools}")

    if 'available_handlers' not in tool_execution or 'unknown_handler' not in tool_execution:
        fail("Tool Executor does not expose structured unknown-handler discovery")
    if 'validation_report' not in tool_execution or 'validation_report' not in agent_registry:
        fail("Tool/Agent runtime validation reports are missing")
    for path in (
        APP_ROOT / "tool_manager" / "management" / "commands" / "validate_tools.py",
        APP_ROOT / "agent_manager" / "management" / "commands" / "validate_agents.py",
        APP_ROOT / "core" / "management" / "commands" / "echo_health.py",
        APP_ROOT / "voice" / "management" / "commands" / "cleanup_voice_audio.py",
    ):
        if not path.exists():
            fail(f"Required runtime validation command is missing: {path.relative_to(ROOT)}")

    if re.search(r'(?:class|def)\s+\w*YouTube\w*', browser + "\n" + desktop, re.I):
        fail("Website-specific YouTube automation symbol found in computer-use runtime")
    for token in ("WAKE_WORD", "ACTIVE", "VOICE_ACTIVE_SESSION_MINUTES", "VOICE_WAKE_WORD_COOLDOWN_SECONDS", "SpeakerAwarenessService", "AgentManagerOrchestrator"):
        if token not in voice:
            fail(f"Voice orchestration contract missing {token}")
    voice_model = (APP_ROOT / "voice" / "models.py").read_text(encoding="utf-8")
    for state in ("STARTING", "GREETING", "DISABLED", "WAKE_WORD_LISTENING", "ACTIVE_SESSION", "PROCESSING", "SPEAKING", "SLEEPING", "SHUTDOWN", "ERROR"):
        if state not in voice_model:
            fail(f"Authoritative voice lifecycle state missing {state}")
    if "default=State.STARTING" not in voice_model:
        fail("VoiceSession.state does not default to STARTING")
    voice_urls = (APP_ROOT / "voice" / "urls.py").read_text(encoding="utf-8")
    if "speech-complete" not in voice_urls or "VoiceSpeechCompleteView" not in (APP_ROOT / "voice" / "views.py").read_text(encoding="utf-8"):
        fail("Browser/server TTS completion is not connected to the authoritative Voice state machine")
    local_system = (APP_ROOT / "internet" / "local_system.py").read_text(encoding="utf-8")
    intent_router = (APP_ROOT / "agent_manager" / "intent_router.py").read_text(encoding="utf-8")
    for token in ("ApplicationDiscoveryService", "ApplicationLauncherService", "SystemLocationResolver", "DesktopWindowService", '"project directory"', '"downloads folder"'):
        if token not in local_system:
            fail(f"Universal local computer-use service missing {token}")
    for token in ("computer_task", "local_computer", "browser_search_in_application", "explicit_environment"):
        if token not in intent_router:
            fail(f"Compound local-computer routing contract missing {token}")
    if "ComputerTaskExecutionService" not in desktop or "computer.execute_task" not in desktop:
        fail("Compound local-computer execution is not routed through a single verified computer task tool")
    for token in ("local_application", "local_system_location", "web_search", "clarification"):
        if token not in intent_router:
            fail(f"Universal intent router contract missing {token}")

    voice_js = (ROOT / "static" / "js" / "echo.js").read_text(encoding="utf-8")
    voice_workspace = (ROOT / "templates" / "workspace" / "voice_workspace.html").read_text(encoding="utf-8")
    shell = (ROOT / "templates" / "workspace" / "shell.html").read_text(encoding="utf-8")
    for token in ("js-voice-toggle", "js-voice-disable", "js-voice-shutdown", "js-stop-current-task"):
        if token not in voice_workspace:
            fail(f"Voice workspace control missing {token}")
    for token in ("voiceRuntime", "recoverCaptureState", "completeSpeechPlayback", "speech-complete", "stopCapture", "active_session", "wake_word_listening", "shutdown", "Echo is announcing the inactivity timeout"):
        if token not in voice_js:
            fail(f"Singleton client voice lifecycle contract missing {token}")
    if 'voice_shutdown' not in voice:
        fail("Explicit Voice shutdown is not persisted server-side across reloads")
    for token in ("data-voice-runtime-url", "data-voice-sessions-url", "data-voice-transcript-url", "data-voice-audio-url"):
        if token not in shell:
            fail(f"Voice shell endpoint contract missing {token}")
    for token in ("/activate/", "/disable/", "/shutdown/"):
        if token not in voice_js:
            fail(f"Voice client transition endpoint missing {token}")



def validate_tool_reference_integrity() -> tuple[int, int]:
    """Statically prove planner/agent tool references resolve to registered handlers.

    This deliberately mirrors the runtime validate_tools command without importing
    Django, so release packaging catches registry drift even in a constrained build
    environment where project dependencies are unavailable.
    """
    registered: set[str] = set()
    referenced: set[str] = set()

    def dotted_name(node):
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))

    def formatted_tool(node, variable: str, values: list[str]):
        if not isinstance(node, ast.JoinedStr):
            return []
        output = []
        for candidate in values:
            pieces = []
            valid = True
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    pieces.append(part.value)
                elif isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name) and part.value.id == variable:
                    pieces.append(candidate)
                else:
                    valid = False
                    break
            if valid:
                output.append("".join(pieces).lower())
        return output

    for path in APP_ROOT.rglob("*.py"):
        if "migrations" in path.parts or "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        constant_lists: dict[str, list[str]] = {}
        for top in tree.body:
            if isinstance(top, ast.Assign) and len(top.targets) == 1 and isinstance(top.targets[0], ast.Name) and isinstance(top.value, (ast.Tuple, ast.List)):
                values = [item.value for item in top.value.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
                if len(values) == len(top.value.elts):
                    constant_lists[top.targets[0].id] = values
        source_text = path.read_text(encoding="utf-8")
        if path.name == "computer_use.py":
            match = re.search(r"\bactions\s*=\s*(\[[^\]]+\])", source_text, re.S)
            if match:
                try:
                    for action in ast.literal_eval(match.group(1)):
                        if isinstance(action, str):
                            registered.add(f"browser.{action}".lower())
                except Exception:
                    pass
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and dotted_name(node.func).endswith("ToolExecutor.register") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    registered.add(first.value.lower())
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                if isinstance(node.iter, (ast.Tuple, ast.List)):
                    values = [item.value for item in node.iter.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
                    if len(values) != len(node.iter.elts):
                        continue
                elif isinstance(node.iter, ast.Name):
                    values = constant_lists.get(node.iter.id, [])
                    if not values:
                        continue
                else:
                    continue
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and dotted_name(child.func).endswith("ToolExecutor.register") and child.args:
                        registered.update(formatted_tool(child.args[0], node.target.id, values))
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "tool" and isinstance(value, ast.Constant) and isinstance(value.value, str) and "." in value.value:
                        referenced.add(value.value.lower())
            if isinstance(node, ast.Call) and dotted_name(node.func).endswith("ToolExecutor.execute_named") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    referenced.add(first.value.lower())
            if isinstance(node, ast.Call) and (dotted_name(node.func).endswith("AgentDefinition")):
                for keyword in node.keywords:
                    if keyword.arg == "required_tools" and isinstance(keyword.value, (ast.Tuple, ast.List)):
                        referenced.update(str(item.value).lower() for item in keyword.value.elts if isinstance(item, ast.Constant) and isinstance(item.value, str))

    missing = sorted(referenced - registered)
    if missing:
        fail(f"Tool references without authoritative registry entries: {missing}")
    required = {"browser.open_url", "computer.observe", "agent.execute", "memory.search", "knowledge.search"}
    absent = sorted(required - registered)
    if absent:
        fail(f"Authoritative registry is missing core Echo tools: {absent}")
    return len(registered), len(referenced)

def main() -> int:
    try:
        python_files = parse_python()
        apps = validate_apps()
        models = validate_models()
        endpoints = validate_endpoints()
        templates = validate_templates()
        icons, css_blocks = validate_assets()
        validate_orchestration_contracts()
        registry_tools, tool_references = validate_tool_reference_integrity()
        validate_release_policy()
    except ValidationError as exc:
        print(f"STATIC VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print(
        "Static validation passed: "
        f"{python_files} Python files, {apps} apps, {models} migration model states, "
        f"{endpoints} compatibility endpoints, {templates} templates, "
        f"{icons} SVG symbols, {css_blocks} CSS blocks, "
        f"{registry_tools} registered tool contracts, {tool_references} resolved tool references."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
