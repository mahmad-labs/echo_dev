from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import logging
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone

from echo.apps.ai_engine.provider import AIProviderError, OpenAICompatibleProvider
from echo.apps.tool_manager.execution import ToolContext, ToolExecutionError, ToolExecutor

from .computer_use import ComputerUseError, HumanInterventionRequired
from .models import ComputerAction, ComputerObservation, ComputerSession
from .local_system import (
    ApplicationDiscoveryService, ApplicationLauncherService, DesktopWindowService,
    LocalSystemError, SystemLocationResolver,
)

logger = logging.getLogger(__name__)


class DesktopUnavailable(ComputerUseError):
    pass


@dataclass(frozen=True)
class DesktopActionOutcome:
    action_id: str
    verified: bool
    result: dict[str, Any]
    observation_id: str | None = None


class LocalDesktopBackend:
    """Authorized desktop input backend. It never executes shell command strings."""

    @staticmethod
    def _pyautogui():
        try:
            import pyautogui
        except ImportError as exc:
            raise DesktopUnavailable("Desktop control requires pyautogui. Install requirements.txt on the machine Echo will control.") from exc
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = float(getattr(settings, "ECHO_DESKTOP_ACTION_PAUSE", 0.08))
        return pyautogui

    @classmethod
    def capabilities(cls) -> dict[str, Any]:
        try:
            gui = cls._pyautogui()
            width, height = gui.size()
            return {"available": True, "screen": {"width": width, "height": height}, "platform": platform.system()}
        except Exception as exc:
            return {"available": False, "reason": str(exc), "platform": platform.system()}

    @classmethod
    def screenshot_png(cls) -> bytes:
        # mss is faster and avoids some ImageGrab platform limitations; PyAutoGUI is
        # retained as a real fallback when mss is unavailable.
        try:
            import mss
            from PIL import Image
            with mss.mss() as capture:
                monitor = capture.monitors[0]
                shot = capture.grab(monitor)
                image = Image.frombytes("RGB", shot.size, shot.rgb)
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue()
        except Exception:
            gui = cls._pyautogui()
            image = gui.screenshot()
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()

    @classmethod
    def cursor(cls) -> dict[str, int]:
        gui = cls._pyautogui()
        point = gui.position()
        return {"x": int(point.x), "y": int(point.y)}

    @classmethod
    def viewport(cls) -> dict[str, int]:
        gui = cls._pyautogui()
        width, height = gui.size()
        return {"width": int(width), "height": int(height)}

    @staticmethod
    def active_window() -> dict[str, Any]:
        return DesktopWindowService.active_window()

    @classmethod
    def perform(cls, action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        gui = cls._pyautogui()
        action = str(action or "").casefold()
        x = arguments.get("x")
        y = arguments.get("y")
        if action in {"move", "click", "double_click", "right_click", "drag"} and (x is None or y is None):
            raise ValidationError("A resolved x/y target is required for this desktop action.")
        duration = min(max(float(arguments.get("duration", 0.15) or 0.15), 0), 3)
        if action == "move":
            gui.moveTo(int(x), int(y), duration=duration)
        elif action == "click":
            gui.click(int(x), int(y))
        elif action == "double_click":
            gui.doubleClick(int(x), int(y), interval=0.12)
        elif action == "right_click":
            gui.rightClick(int(x), int(y))
        elif action == "scroll":
            amount = int(arguments.get("amount", -650) or -650)
            # pyautogui uses platform-specific click units; normalize sign and bound it.
            clicks = max(-20, min(20, int(amount / 120) or (-5 if amount < 0 else 5)))
            gui.scroll(clicks)
        elif action == "drag":
            destination = arguments.get("destination") or {}
            dx, dy = destination.get("x"), destination.get("y")
            if dx is None or dy is None:
                raise ValidationError("A resolved destination is required for drag.")
            gui.moveTo(int(x), int(y), duration=duration)
            gui.dragTo(int(dx), int(dy), duration=max(duration, 0.25), button=str(arguments.get("button") or "left"))
        elif action == "type":
            text = str(arguments.get("text") or "")
            if not text:
                raise ValidationError("text is required")
            if arguments.get("clear"):
                modifier = "command" if platform.system() == "Darwin" else "ctrl"
                gui.hotkey(modifier, "a")
            gui.write(text, interval=min(max(float(arguments.get("interval", 0.01) or 0.01), 0), 0.2))
            if arguments.get("submit"):
                gui.press("enter")
        elif action == "press_key":
            key = str(arguments.get("key") or "").casefold().strip()
            if not key:
                raise ValidationError("key is required")
            gui.press(key)
        elif action == "hotkey":
            keys = arguments.get("keys") or []
            if not isinstance(keys, list) or not keys:
                raise ValidationError("keys must be a non-empty list")
            gui.hotkey(*(str(key).casefold() for key in keys[:6]))
        elif action == "wait":
            time.sleep(min(max(float(arguments.get("seconds", 1) or 1), 0), 20))
        else:
            raise ValidationError(f"Unsupported desktop action: {action}")
        return {"ok": True, "action": action, "cursor": cls.cursor(), "window": cls.active_window()}


class DesktopUITreeService:
    """Replaceable OS accessibility/UI-tree adapter with native best-effort fallbacks."""

    @classmethod
    def _linux_atspi(cls) -> dict[str, Any]:
        try:
            import pyatspi  # type: ignore
        except Exception as exc:
            return {"available": False, "reason": f"AT-SPI is unavailable: {exc}"}
        elements: list[dict[str, Any]] = []
        try:
            desktop = pyatspi.Registry.getDesktop(0)
            queue = [desktop]
            while queue and len(elements) < 700:
                node = queue.pop(0)
                try:
                    name = str(getattr(node, "name", "") or "").strip()
                    role = str(node.getRoleName() or "").strip()
                    item: dict[str, Any] = {"name": name, "label": name, "role": role}
                    try:
                        component = node.queryComponent()
                        extents = component.getExtents(pyatspi.DESKTOP_COORDS)
                        if extents.width > 0 and extents.height > 0:
                            item["bbox"] = {"x": int(extents.x), "y": int(extents.y), "width": int(extents.width), "height": int(extents.height)}
                    except Exception:
                        pass
                    if name or role:
                        elements.append(item)
                    try:
                        queue.extend(node[i] for i in range(min(int(node.childCount), 100)))
                    except Exception:
                        pass
                except Exception:
                    continue
            return {"available": True, "provider": "linux_atspi", "elements": elements}
        except Exception as exc:
            return {"available": False, "reason": f"AT-SPI inspection failed: {exc}"}

    @classmethod
    def _windows_uia(cls) -> dict[str, Any]:
        try:
            from pywinauto import Desktop  # type: ignore
        except Exception as exc:
            return {"available": False, "reason": f"Windows UI Automation is unavailable: {exc}"}
        elements: list[dict[str, Any]] = []
        try:
            desktop = Desktop(backend="uia")
            for window in desktop.windows()[:30]:
                nodes = [window, *window.descendants()[:400]]
                for node in nodes:
                    if len(elements) >= 700:
                        break
                    try:
                        rect = node.rectangle()
                        name = str(node.window_text() or "").strip()
                        role = str(getattr(node.element_info, "control_type", "") or "").strip()
                        item = {"name": name, "label": name, "role": role}
                        if rect.width() > 0 and rect.height() > 0:
                            item["bbox"] = {"x": int(rect.left), "y": int(rect.top), "width": int(rect.width()), "height": int(rect.height())}
                        if name or role:
                            elements.append(item)
                    except Exception:
                        continue
            return {"available": True, "provider": "windows_uia", "elements": elements}
        except Exception as exc:
            return {"available": False, "reason": f"Windows UI Automation inspection failed: {exc}"}

    @classmethod
    def inspect(cls) -> dict[str, Any]:
        dotted = str(getattr(settings, "ECHO_COMPUTER_UI_TREE_PROVIDER_CLASS", "") or "").strip()
        if dotted:
            module_name, _, class_name = dotted.rpartition(".")
            if not module_name or not class_name:
                return {"available": False, "reason": "Invalid UI-tree provider path."}
            try:
                provider = getattr(importlib.import_module(module_name), class_name)()
                result = provider.inspect()
                return result if isinstance(result, dict) else {"available": False, "reason": "UI-tree provider returned invalid data."}
            except Exception as exc:
                return {"available": False, "reason": str(exc)[:500]}
        if platform.system() == "Linux":
            return cls._linux_atspi()
        if platform.system() == "Windows":
            return cls._windows_uia()
        return {"available": False, "reason": "No native accessibility adapter is available on this platform; configure ECHO_COMPUTER_UI_TREE_PROVIDER_CLASS."}


class DesktopVisionService:
    """Vision/OCR fallback over a real screen capture; never fabricates elements."""

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        clean = str(content or "").strip()
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=re.I | re.S).strip()
        try:
            payload = json.loads(clean)
        except ValueError:
            return {"available": False, "reason": "Vision provider did not return valid structured JSON.", "raw": clean[:2000]}
        return payload if isinstance(payload, dict) else {"available": False, "reason": "Vision provider returned invalid structured data."}

    @classmethod
    def inspect(cls, png: bytes, *, target_hint: str = "") -> dict[str, Any]:
        if not getattr(settings, "AI_PROVIDER_BASE_URL", "") or not getattr(settings, "AI_PROVIDER_API_KEY", "") or not getattr(settings, "AI_VISION_MODEL", ""):
            return {"available": False, "reason": "Configure AI_PROVIDER_BASE_URL, AI_PROVIDER_API_KEY and AI_VISION_MODEL for desktop OCR/vision."}
        encoded = base64.b64encode(png).decode("ascii")
        prompt = (
            "Inspect this current computer screenshot. Return JSON only with keys: available=true, text, elements, summary, blockers. "
            "elements must contain only controls/text you can actually see and each item must have label, role, bbox={x,y,width,height} in screenshot pixels, confidence 0..1. "
            "blockers should identify visible CAPTCHA, MFA, login/security verification or permission dialogs. Do not infer invisible controls."
        )
        if target_hint:
            prompt += f" Pay particular attention to this requested target: {target_hint[:500]}"
        messages = [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
        ]}]
        try:
            content, _ = OpenAICompatibleProvider().complete(messages, model=settings.AI_VISION_MODEL, temperature=0.0, timeout=60)
            parsed = cls._parse_json(content)
            parsed.setdefault("available", True)
            return parsed
        except AIProviderError as exc:
            return {"available": False, "reason": str(exc)[:500]}


class ComputerSessionService:
    @staticmethod
    def _owned(user):
        query = ComputerSession.objects.all()
        return query if user.is_staff else query.filter(owner=user)

    @classmethod
    def create(cls, user) -> ComputerSession:
        capabilities = LocalDesktopBackend.capabilities()
        if not capabilities.get("available"):
            raise DesktopUnavailable(str(capabilities.get("reason") or "Desktop control is unavailable."))
        now = timezone.now()
        return ComputerSession.objects.create(
            owner=user,
            name=f"computer-{now.isoformat()}",
            title="Echo computer-control session",
            description="Authorized desktop computer-use session.",
            status="active",
            environment="desktop.local",
            display_name=str(capabilities.get("platform") or "Desktop"),
            started_at=now,
            last_activity_at=now,
            configuration={"capabilities": capabilities, "provider": "pyautogui"},
        )

    @classmethod
    def current(cls, user, *, create: bool = True) -> ComputerSession | None:
        session = cls._owned(user).filter(status="active").order_by("-last_activity_at", "-created_at").first()
        return session or (cls.create(user) if create else None)

    @classmethod
    def get(cls, user, session_id) -> ComputerSession:
        session = cls._owned(user).filter(pk=session_id).first()
        if not session:
            raise DesktopUnavailable("Computer session was not found.")
        return session

    @classmethod
    def close(cls, user, session_id) -> ComputerSession:
        session = cls.get(user, session_id)
        session.status = "completed"
        session.ended_at = timezone.now()
        session.last_activity_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "last_activity_at", "updated_at"])
        return session


class ComputerObservationService:
    @classmethod
    def observe(cls, user, session: ComputerSession, *, vision: bool = False, target_hint: str = "", reason: str = "observe") -> ComputerObservation:
        png = LocalDesktopBackend.screenshot_png()
        window = LocalDesktopBackend.active_window()
        ui_tree = DesktopUITreeService.inspect()
        vision_data = DesktopVisionService.inspect(png, target_hint=target_hint) if vision else {"available": False, "reason": "Vision not requested for this observation."}
        sequence = (session.observations.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
        ocr_text = str(vision_data.get("text") or "")[:60000] if vision_data.get("available") else ""
        observation = ComputerObservation(
            owner=user,
            session=session,
            name=f"computer-observation-{sequence}",
            title=str(window.get("title") or f"Desktop observation {sequence}")[:255],
            description=f"Desktop observation captured for {reason}.",
            status="completed",
            sequence=sequence,
            ocr_text=ocr_text,
            vision=vision_data,
            ui_tree=ui_tree,
            window_info=window,
            cursor=LocalDesktopBackend.cursor(),
            viewport=LocalDesktopBackend.viewport(),
            content_hash=hashlib.sha256(png).hexdigest(),
            observed_at=timezone.now(),
            configuration={"reason": reason, "vision_requested": vision},
        )
        observation.screenshot.save(f"{session.pk}-{sequence}.png", ContentFile(png), save=False)
        observation.save()
        session.active_window = window
        session.last_activity_at = timezone.now()
        session.save(update_fields=["active_window", "last_activity_at", "updated_at"])
        return observation

    @staticmethod
    def blocker(observation: ComputerObservation) -> dict[str, str] | None:
        blockers = (observation.vision or {}).get("blockers") or []
        text = f"{observation.ocr_text} {json.dumps(blockers, default=str)}".casefold()
        patterns = (
            ("captcha", ("captcha", "verify you are human", "human verification")),
            ("mfa", ("two-factor", "two factor", "verification code", "authenticator", "security code")),
            ("login", ("sign in", "log in", "password")),
            ("permission", ("allow access", "permission required", "requires permission")),
        )
        for kind, needles in patterns:
            if any(needle in text for needle in needles):
                return {"type": kind, "detail": f"Desktop interaction paused because {kind} requires user intervention."}
        return None


class ComputerTargetResolver:
    @staticmethod
    def _match(items: list[dict[str, Any]], target: str) -> dict[str, Any] | None:
        needle = str(target or "").casefold().strip()
        if not needle:
            return None
        ranked = []
        for item in items:
            label = " ".join(str(item.get(key) or "") for key in ("label", "name", "text", "title", "role")).casefold()
            if not label:
                continue
            score = 100 if label.strip() == needle else 75 if needle in label else 40 if all(word in label for word in needle.split() if len(word) > 2) else 0
            if score:
                ranked.append((score, item))
        return sorted(ranked, key=lambda pair: -pair[0])[0][1] if ranked else None

    @classmethod
    def resolve(cls, user, session: ComputerSession, target: Any, *, observation: ComputerObservation | None = None) -> tuple[dict[str, int], dict[str, Any], ComputerObservation]:
        if isinstance(target, dict) and target.get("x") is not None and target.get("y") is not None:
            obs = observation or ComputerObservationService.observe(user, session, vision=False, reason="explicit-coordinate-target")
            return {"x": int(target["x"]), "y": int(target["y"])}, {"source": "explicit", "target": target}, obs
        text = str(target or "").strip()
        if not text:
            raise ValidationError("A desktop target is required.")
        obs = observation or ComputerObservationService.observe(user, session, vision=False, reason="target-resolution")
        ui_items = []
        tree = obs.ui_tree or {}
        if tree.get("available"):
            ui_items = tree.get("elements") or tree.get("nodes") or []
        match = cls._match(ui_items, text)
        source = "ui_tree"
        if not match:
            # Structured OS accessibility evidence was insufficient. Capture a fresh
            # screenshot and use vision/OCR as the fallback exactly once.
            obs = ComputerObservationService.observe(user, session, vision=True, target_hint=text, reason="vision-target-resolution")
            match = cls._match((obs.vision or {}).get("elements") or [], text)
            source = "vision"
        if not match:
            raise DesktopUnavailable(f"Echo could not identify the requested desktop control: {text}")
        bbox = match.get("bbox") or match.get("rect") or {}
        if not all(key in bbox for key in ("x", "y", "width", "height")):
            raise DesktopUnavailable("The identified control did not include a usable screen location.")
        point = {"x": int(float(bbox["x"]) + float(bbox["width"]) / 2), "y": int(float(bbox["y"]) + float(bbox["height"]) / 2)}
        return point, {"source": source, "element": match}, obs


class ComputerActionService:
    SAFE_WITHOUT_CONFIRMATION = {"move", "click", "double_click", "scroll", "press_key", "hotkey", "wait"}

    @classmethod
    def execute(cls, user, session: ComputerSession, action: str, arguments: dict[str, Any]) -> DesktopActionOutcome:
        action = str(action or "").casefold().strip()
        arguments = dict(arguments or {})
        if action not in {"move", "click", "double_click", "right_click", "scroll", "drag", "type", "press_key", "hotkey", "wait"}:
            raise ValidationError(f"Unsupported computer action: {action}")
        pre = ComputerObservationService.observe(user, session, vision=False, reason=f"before-{action}")
        blocker = ComputerObservationService.blocker(pre)
        if blocker:
            raise HumanInterventionRequired(blocker["type"], blocker["detail"])
        target_descriptor: dict[str, Any] = {}
        if action in {"move", "click", "double_click", "right_click", "drag"}:
            point, target_descriptor, pre = ComputerTargetResolver.resolve(user, session, arguments.get("target") or arguments, observation=pre)
            arguments.update(point)
            if action == "drag":
                destination, destination_descriptor, _ = ComputerTargetResolver.resolve(user, session, arguments.get("destination"), observation=pre)
                arguments["destination"] = destination
                target_descriptor["destination"] = destination_descriptor
        if action in {"type", "right_click", "drag"} and not bool(arguments.pop("confirmed", False)):
            raise HumanInterventionRequired("approval", f"Echo needs your approval before the desktop {action.replace('_', ' ')} action.")
        record = ComputerAction.objects.create(
            owner=user,
            session=session,
            name=action,
            title=f"Desktop {action.replace('_', ' ')}",
            description="Authorized computer-control action.",
            status="running",
            action_type=action,
            target=target_descriptor,
            arguments={key: value for key, value in arguments.items() if key not in {"password", "secret"}},
            pre_observation=pre,
            started_at=timezone.now(),
        )
        try:
            result = LocalDesktopBackend.perform(action, arguments)
            time.sleep(float(getattr(settings, "ECHO_DESKTOP_VERIFY_DELAY", 0.2)))
            post = ComputerObservationService.observe(user, session, vision=False, reason=f"after-{action}")
            changed = pre.content_hash != post.content_hash
            if action == "move":
                verified = post.cursor.get("x") == int(arguments["x"]) and post.cursor.get("y") == int(arguments["y"])
            elif action in {"scroll", "drag", "type", "press_key", "hotkey"}:
                verified = changed
            elif action in {"click", "double_click", "right_click"}:
                verified = changed
            else:
                verified = True
            result = {**result, "screen_changed": changed, "verification": "verified" if verified else "action_sent_but_no_observable_change"}
            record.post_observation = post
            record.result = result
            record.verified = verified
            record.status = "completed" if verified else "unverified"
            record.completed_at = timezone.now()
            record.save()
            return DesktopActionOutcome(str(record.pk), verified, result, str(post.pk))
        except Exception as exc:
            record.status = "failed"
            record.error_message = str(exc)
            record.completed_at = timezone.now()
            record.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
            raise


class DesktopPathService:
    """Compatibility facade over the authoritative system-location resolver."""

    @classmethod
    def resolve(cls, requested: str):
        return SystemLocationResolver.resolve(requested)

    @classmethod
    def open(cls, requested: str) -> dict[str, Any]:
        return SystemLocationResolver.open(requested)



class ComputerTaskPlanner:
    """Deterministic environment-aware planner for compound local-computer requests.

    The planner does not execute anything and never changes a local objective into a
    web-search objective.  Its output is intentionally structured so Agent Manager,
    Tool Manager and diagnostics can inspect the chosen environment and operations.
    """

    BROWSER_TOKENS = ("firefox", "chrome", "chromium", "edge", "safari", "brave", "browser")

    @staticmethod
    def _split_followups(text: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip(" ,.;"))
        if not cleaned:
            return []
        # Split only at conjunctions followed by an action verb.  This preserves
        # queries such as "Django and Python documentation".
        return [
            item.strip(" ,.;")
            for item in re.split(
                r"\s*(?:,\s*)?(?:and\s+then|then|and)\s+(?=(?:search|find|look\s+up|go\s+to|navigate\s+to|visit|open|click|scroll|type|press|play|pause)\b)",
                cleaned,
                flags=re.I,
            )
            if item.strip(" ,.;")
        ]

    @classmethod
    def from_request(cls, prompt: str, route_metadata: dict[str, Any] | None = None) -> dict[str, Any] | None:
        metadata = dict(route_metadata or {})
        if metadata.get("environment") == "local_computer" and metadata.get("application"):
            application = str(metadata["application"]).strip()
            raw_actions = list(metadata.get("actions") or [])
            actions = [dict(item) for item in raw_actions if isinstance(item, dict)]
            # Rebuild richer follow-up actions when the intent router supplied only a
            # single catch-all continuation.
            rest = str(metadata.get("task_text") or "").strip()
            if rest and any(item.get("type") == "continue_in_application" for item in actions):
                actions = actions[:1]
                for clause in cls._split_followups(rest):
                    actions.extend(cls._clause_actions(clause))
            return {"environment": "local_computer", "application": application, "actions": actions, "source": "intent_router"}

        text = re.sub(r"\s+", " ", str(prompt or "").strip())
        match = re.match(
            r"^(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?"
            r"(?P<application>.+?)(?=(?:\s+on\s+(?:my|this|the)\s+(?:computer|pc|desktop))|(?:\s*(?:,|\band\b|\bthen\b)\s+)|$)"
            r"(?:\s+on\s+(?:my|this|the)\s+(?:computer|pc|desktop))?"
            r"(?P<rest>\s*(?:,|\band\b|\bthen\b).+)?$",
            text,
            re.I,
        )
        if not match:
            return None
        application = match.group("application").strip(" .,:;-_")
        if not ApplicationDiscoveryService.recognizes_application_name(application):
            return None
        rest = re.sub(r"^(?:,|\band\b|\bthen\b)\s*", "", str(match.group("rest") or ""), flags=re.I)
        actions = [{"type": "open_application", "application": application}]
        for clause in cls._split_followups(rest):
            actions.extend(cls._clause_actions(clause))
        return {"environment": "local_computer", "application": application, "actions": actions, "source": "desktop_router"}

    @staticmethod
    def _clause_actions(clause: str) -> list[dict[str, Any]]:
        clause = str(clause or "").strip()
        search = re.match(r"^(?:search|find|look\s+up)(?:\s+(?:google|the\s+web|web))?\s+(?:for\s+)?(.+)$", clause, re.I)
        if search:
            return [{"type": "browser_search_in_application", "query": search.group(1).strip().rstrip(".!?")}]
        navigate = re.match(r"^(?:go\s+to|navigate\s+to|visit|open)\s+(.+)$", clause, re.I)
        if navigate:
            target = navigate.group(1).strip().rstrip(".!?")
            try:
                from echo.apps.agent_manager.intent_router import WebsiteResolver
                url = WebsiteResolver.resolve(target)
            except Exception:
                url = ""
            if url:
                return [{"type": "browser_navigate_in_application", "target": target, "url": url}]
            if SystemLocationResolver.recognizes(target):
                return [{"type": "open_system_location", "target": target}]
            return [{"type": "contextual_open", "target": target}]
        scroll = re.match(r"^scroll(?:\s+(down|up))?", clause, re.I)
        if scroll:
            return [{"type": "scroll", "direction": (scroll.group(1) or "down").casefold()}]
        click = re.match(r"^(?:click|open|select)\s+(.+)$", clause, re.I)
        if click:
            return [{"type": "click", "target": click.group(1).strip()}]
        play = re.match(r"^(play|pause)(?:\s+(.+))?$", clause, re.I)
        if play:
            return [{"type": "press_key", "key": "space", "semantic": play.group(1).casefold()}]
        return [{"type": "instruction", "text": clause}] if clause else []


class ComputerTaskExecutionService:
    """Execute a structured local-computer plan through the authoritative tools.

    Every step captures executable evidence.  The service never reports a later step
    as successful when application launch/focus or post-action observation failed.
    """

    @staticmethod
    def _browser_application(app: dict[str, Any], requested: str) -> bool:
        haystack = " ".join(
            [str(requested or ""), str(app.get("name") or ""), str(app.get("executable") or ""), str(app.get("identifier") or "")]
        ).casefold()
        return any(token in haystack for token in ComputerTaskPlanner.BROWSER_TOKENS)

    @staticmethod
    def _run_tool(user, name: str, payload: dict[str, Any], *, task_id: str = "") -> tuple[dict[str, Any], str]:
        result = ToolExecutor.execute_named(name, user, payload, agent="computer", task_id=task_id)
        return dict(result.output or {}), result.execution_id

    @classmethod
    def execute(cls, user, plan: dict[str, Any], *, task_id: str = "") -> dict[str, Any]:
        application = str(plan.get("application") or "").strip()
        if not application:
            raise ValidationError("A local application is required for this computer task.")
        steps: list[dict[str, Any]] = []

        launch, execution_id = cls._run_tool(user, "computer.launch_application", {"application": application}, task_id=task_id)
        launch_verified = bool(launch.get("verified") or launch.get("success"))
        steps.append({"tool": "computer.launch_application", "execution_id": execution_id, "success": launch_verified, "output": launch})
        if not launch_verified:
            return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": f"Could not verify that {application} launched."}

        app = dict(launch.get("application") or {})
        # Focus is an observe/verify step, not an assumption.  If the launch already
        # made the requested application active, no redundant focus action is needed.
        active = dict(launch.get("active_window") or {})
        app_tokens = [token for token in ApplicationDiscoveryService.normalize(app.get("name") or application).split() if len(token) >= 3]
        active_text = f"{active.get('title','')} {active.get('class','')}".casefold()
        if app_tokens and not any(token in active_text for token in app_tokens):
            try:
                focus, focus_execution = cls._run_tool(user, "computer.focus_window", {"window": app.get("name") or application}, task_id=task_id)
                focus_verified = bool(focus.get("verified") or focus.get("success"))
                steps.append({"tool": "computer.focus_window", "execution_id": focus_execution, "success": focus_verified, "output": focus})
                if not focus_verified:
                    return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": f"{application} launched but Echo could not verify focus."}
            except ToolExecutionError as exc:
                return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": str(exc)}

        session_id = ""
        try:
            session = ComputerSessionService.current(user, create=True)
            session_id = str(session.pk)
        except Exception:
            session = None

        baseline_hash = ""
        if session_id:
            try:
                baseline, baseline_execution = cls._run_tool(
                    user, "computer.observe", {"vision": False, "computer_session_id": session_id}, task_id=task_id
                )
                baseline_hash = str(baseline.get("content_hash") or "")
                steps.append({"tool": "computer.observe", "execution_id": baseline_execution, "success": bool(baseline.get("ok")), "output": baseline})
            except ToolExecutionError:
                baseline_hash = ""

        for action in list(plan.get("actions") or [])[1:]:
            kind = str(action.get("type") or "")
            if kind in {"browser_search_in_application", "browser_navigate_in_application"}:
                if not cls._browser_application(app, application):
                    return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": f"{application} is not recognized as a web browser, so Echo will not inject a browser search into it."}
                value = str(action.get("query") or action.get("url") or action.get("target") or "").strip()
                if not value:
                    raise ValidationError("The browser task is missing a query or destination.")
                modifier = "command" if platform.system() == "Darwin" else "ctrl"
                final_observation: dict[str, Any] = {}
                for tool_name, payload in (
                    ("computer.hotkey", {"keys": [modifier, "l"], **({"computer_session_id": session_id} if session_id else {})}),
                    # Text entry is explicitly authorized by the user's compound command
                    # and constrained to the verified browser address/search field.
                    ("computer.type", {"text": value, "confirmed": True, **({"computer_session_id": session_id} if session_id else {})}),
                    ("computer.press_key", {"key": "enter", **({"computer_session_id": session_id} if session_id else {})}),
                    ("computer.wait", {"seconds": 1.2, **({"computer_session_id": session_id} if session_id else {})}),
                    ("computer.observe", {"vision": False, "target_hint": value[:300], **({"computer_session_id": session_id} if session_id else {})}),
                ):
                    output, step_execution = cls._run_tool(user, tool_name, payload, task_id=task_id)
                    ok = bool(output.get("ok", output.get("success", False)))
                    # A focus/keyboard event can be legitimately sent without a
                    # pixel-detectable intermediate change. The significant browser
                    # step is verified by the final observation below.
                    sent_unobservable = str(output.get("verification") or "") == "action_sent_but_no_observable_change" and tool_name in {"computer.hotkey", "computer.press_key"}
                    step_ok = ok or sent_unobservable
                    steps.append({"tool": tool_name, "execution_id": step_execution, "success": step_ok, "output": output})
                    if tool_name == "computer.observe":
                        final_observation = output
                    if not step_ok:
                        return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": f"{tool_name} could not be verified."}
                final_hash = str(final_observation.get("content_hash") or "")
                final_window = dict(final_observation.get("window") or {})
                final_window_text = f"{final_window.get('title','')} {final_window.get('class','')}".casefold()
                window_matches = not app_tokens or any(token in final_window_text for token in app_tokens)
                changed = bool(final_hash and baseline_hash and final_hash != baseline_hash)
                if not window_matches or (baseline_hash and not changed):
                    return {
                        "success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps,
                        "error": "Echo sent the browser interaction but could not verify the expected screen change in the requested application.",
                    }
                baseline_hash = final_hash or baseline_hash
            elif kind == "open_system_location":
                output, step_execution = cls._run_tool(user, "computer.open_path", {"path": str(action.get("target") or "")}, task_id=task_id)
                ok = bool(output.get("verified") or output.get("success"))
                steps.append({"tool": "computer.open_path", "execution_id": step_execution, "success": ok, "output": output})
                if not ok:
                    return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": "The requested system location could not be verified."}
            elif kind == "scroll":
                amount = 650 if action.get("direction") == "up" else -650
                output, step_execution = cls._run_tool(user, "computer.scroll", {"amount": amount, **({"computer_session_id": session_id} if session_id else {})}, task_id=task_id)
                ok = bool(output.get("ok"))
                steps.append({"tool": "computer.scroll", "execution_id": step_execution, "success": ok, "output": output})
                if not ok:
                    return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": "The scroll could not be verified."}
            elif kind in {"click", "contextual_open"}:
                target = str(action.get("target") or "").strip()
                output, step_execution = cls._run_tool(user, "computer.click", {"target": target, **({"computer_session_id": session_id} if session_id else {})}, task_id=task_id)
                ok = bool(output.get("ok"))
                steps.append({"tool": "computer.click", "execution_id": step_execution, "success": ok, "output": output})
                if not ok:
                    return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": f"Echo could not verify the requested target: {target}."}
            elif kind == "press_key":
                output, step_execution = cls._run_tool(user, "computer.press_key", {"key": str(action.get("key") or ""), **({"computer_session_id": session_id} if session_id else {})}, task_id=task_id)
                ok = bool(output.get("ok"))
                steps.append({"tool": "computer.press_key", "execution_id": step_execution, "success": ok, "output": output})
                if not ok:
                    return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": "The keyboard action could not be verified."}
            elif kind == "instruction":
                return {"success": False, "verified": False, "environment": "local_computer", "application": application, "steps": steps, "error": f"Echo could not safely decompose this local follow-up: {action.get('text','')}"}

        final_active = DesktopWindowService.active_window()
        return {
            "success": True, "verified": True, "environment": "local_computer", "application": application,
            "active_window": final_active, "computer_session_id": session_id or None, "steps": steps,
        }


class ComputerControlCommandRouter:
    """Natural-language adapter over the shared desktop tools.

    This parser only handles high-confidence reversible commands. Target resolution is
    delegated to ComputerTargetResolver (OS accessibility tree first, screenshot vision
    second), so language such as "click the blue button" never becomes a hard-coded
    coordinate. Consequential actions return a durable approval payload instead of
    self-authorizing.
    """

    LOCAL_RE = re.compile(
        r"\b(?:downloads?|documents?|desktop|home|pictures?|photos?|videos?|music|trash(?:\s+bin)?|recycle\s+bin|file\s+system|file\s+manager)\b|"
        r"\b(?:open|launch|start|show|switch\s+to|focus)\s+[^\n]+|"
        r"\b(?:click|double\s+click|right\s+click|scroll|type|press|drag|move|hover|close|minimize|maximize|restore|screen|window|desktop|what(?:'s| is)\s+on\s+(?:my\s+)?screen)\b",
        re.I,
    )

    @staticmethod
    def _result(outcome: DesktopActionOutcome, *, route: str, success: str, failure: str, session: ComputerSession) -> dict[str, Any]:
        return {
            "status": "completed" if outcome.verified else "failed",
            "content": success if outcome.verified else failure,
            "route": route,
            "data": {
                "computer_session_id": str(session.pk), "action_id": outcome.action_id,
                "observation_id": outcome.observation_id, "verified": outcome.verified, **outcome.result,
            },
        }

    @staticmethod
    def _touch_local_context(user, output: dict[str, Any]) -> str:
        """Mark a verified local launch/open as the most recent desktop context.

        This lets referential follow-ups such as "scroll down" or "click that"
        route to the desktop the user just opened instead of an older BrowserSession.
        A host that can launch applications but lacks screen-control dependencies is
        still allowed to report the launch result; in that degraded case there is no
        fabricated ComputerSession.
        """
        try:
            session = ComputerSessionService.current(user, create=True)
        except Exception:
            return ""
        if not session:
            return ""
        active_window = output.get("active_window") if isinstance(output, dict) else None
        if isinstance(active_window, dict):
            session.active_window = active_window
        session.last_activity_at = timezone.now()
        session.save(update_fields=["active_window", "last_activity_at", "updated_at"] if isinstance(active_window, dict) else ["last_activity_at", "updated_at"])
        return str(session.pk)

    @classmethod
    def _execute(cls, user, session: ComputerSession, action: str, arguments: dict[str, Any], *, confirmed: bool = False) -> dict[str, Any]:
        payload = {**dict(arguments or {}), "computer_session_id": str(session.pk)}
        if confirmed:
            payload["confirmed"] = True
        try:
            execution = ToolExecutor.execute_named(f"computer.{action}", user, payload, agent="computer")
            output = dict(execution.output or {})
        except ToolExecutionError as exc:
            cause = exc.__cause__
            if isinstance(cause, HumanInterventionRequired):
                if cause.reason == "approval":
                    return {
                        "status": "waiting", "content": cause.detail, "route": "computer.approval_required",
                        "needs_confirmation": True,
                        "data": {
                            "computer_session_id": str(session.pk), "attention": {"type": cause.reason, "detail": cause.detail},
                            "pending_action": {"tool": f"computer.{action}", "input": arguments},
                        },
                    }
                return {
                    "status": "waiting", "content": cause.detail, "route": "computer.human_intervention",
                    "data": {"computer_session_id": str(session.pk), "attention": {"type": cause.reason, "detail": cause.detail}},
                }
            return {
                "status": "failed", "content": f"The computer action failed: {exc}", "route": f"computer.{action}.failed",
                "data": {"computer_session_id": str(session.pk), "error": exc.as_dict()},
            }
        labels = {
            "click": ("Clicked the requested control and verified the screen response.", "I sent the click but could not verify a visible response."),
            "double_click": ("Double-clicked the requested control and verified the screen response.", "I sent the double-click but could not verify a visible response."),
            "right_click": ("Opened the requested context control and verified the screen response.", "I sent the right-click but could not verify a visible response."),
            "scroll": ("Scrolled the current desktop view.", "I sent the scroll action but could not verify a visible change."),
            "move": ("Moved the pointer to the requested control.", "I could not verify the pointer position."),
            "type": ("Entered the requested text and verified a screen change.", "I sent the text input but could not verify a screen change."),
            "press_key": ("Pressed the requested key and verified the screen response.", "I sent the key press but could not verify a screen response."),
            "hotkey": ("Executed the requested keyboard shortcut and verified the screen response.", "I sent the shortcut but could not verify a screen response."),
            "drag": ("Completed the drag action and verified the screen response.", "I sent the drag action but could not verify a screen response."),
            "wait": ("Waited and refreshed the desktop state.", "The wait action could not be verified."),
        }
        verified = bool(output.get("ok"))
        success, failure = labels.get(action, ("The desktop action completed.", "The desktop action could not be verified."))
        return {
            "status": "completed" if verified else "failed", "content": success if verified else failure,
            "route": f"computer.{action}",
            "data": {**output, "tool_execution_id": execution.execution_id, "verified": verified},
        }

    @classmethod
    def handle(cls, user, prompt: str, *, confirmed: bool = False, route_metadata: dict[str, Any] | None = None) -> dict[str, Any] | None:
        prompt = str(prompt or "").strip()
        compound_plan = ComputerTaskPlanner.from_request(prompt, route_metadata=route_metadata)
        if compound_plan and len(compound_plan.get("actions") or []) > 1:
            try:
                execution = ToolExecutor.execute_named(
                    "computer.execute_task", user, {"plan": compound_plan}, agent="computer"
                )
                output = dict(execution.output or {})
                verified = bool(output.get("verified") and output.get("success"))
                app_name = str(output.get("application") or compound_plan.get("application") or "application")
                followups = list(compound_plan.get("actions") or [])[1:]
                query = next((str(item.get("query") or "") for item in followups if item.get("type") == "browser_search_in_application"), "")
                content = (f"{app_name} is open and the search for {query} was performed and verified." if verified and query else f"The computer task in {app_name} completed and was verified." if verified else f"I could not complete the computer task in {app_name}: {output.get('error') or 'verification failed.'}")
                return {
                    "status": "completed" if verified else "failed", "content": content, "route": "computer.execute_task",
                    "data": {**output, "tool_execution_id": execution.execution_id, "plan": compound_plan},
                }
            except ToolExecutionError as exc:
                return {"status": "failed", "content": f"The computer task failed: {exc}", "route": "computer.execute_task.failed", "data": {"error": exc.as_dict(), "plan": compound_plan}}
        if not cls.LOCAL_RE.search(prompt):
            return None
        lowered = prompt.casefold()

        # High-confidence local open commands are resolved before pointer/keyboard
        # actions. System locations and installed applications are never converted
        # into web searches here. All execution still passes through Tool Manager.
        open_match = re.match(r"^\s*(?:please\s+)?(?:open|launch|start|show)\s+(?:my\s+|the\s+)?(.+?)\s*[.!?]?\s*$", prompt, re.I)
        if open_match:
            target = open_match.group(1).strip()
            if SystemLocationResolver.recognizes(target):
                try:
                    execution = ToolExecutor.execute_named("computer.open_path", user, {"path": target}, agent="computer")
                    output = dict(execution.output or {})
                    verified = bool(output.get("verified") or output.get("success"))
                    name = str((output.get("location") or {}).get("name") or target)
                    computer_session_id = cls._touch_local_context(user, output) if verified else ""
                    return {
                        "status": "completed" if verified else "failed",
                        "content": f"{name} is open." if verified else f"I tried to open {name}, but I could not verify that it opened.",
                        "route": "computer.open_path",
                        "data": {**output, "tool_execution_id": execution.execution_id, "verified": verified, **({"computer_session_id": computer_session_id} if computer_session_id else {})},
                    }
                except ToolExecutionError as exc:
                    return {"status": "failed", "content": f"I couldn't open {target}: {exc}", "route": "computer.open_path.failed", "data": {"error": exc.as_dict()}}
            if ApplicationDiscoveryService.recognizes_application_name(target):
                try:
                    execution = ToolExecutor.execute_named("computer.launch_application", user, {"application": target}, agent="computer")
                    output = dict(execution.output or {})
                    verified = bool(output.get("verified") or output.get("success"))
                    app_name = str((output.get("application") or {}).get("name") or target)
                    computer_session_id = cls._touch_local_context(user, output) if verified else ""
                    return {
                        "status": "completed" if verified else "failed",
                        "content": f"{app_name} is open." if verified else f"I launched {app_name}, but I could not verify that it opened.",
                        "route": "computer.launch_application",
                        "data": {**output, "tool_execution_id": execution.execution_id, "verified": verified, **({"computer_session_id": computer_session_id} if computer_session_id else {})},
                    }
                except ToolExecutionError as exc:
                    return {"status": "failed", "content": f"I couldn't launch {target}: {exc}", "route": "computer.launch_application.failed", "data": {"error": exc.as_dict()}}

        if re.search(r"\bswitch\s+to\s+(?:the\s+)?previous\s+window\b", lowered):
            keys = ["command", "tab"] if platform.system() == "Darwin" else ["alt", "tab"]
            return cls._execute(user, ComputerSessionService.current(user, create=True), "hotkey", {"keys": keys}, confirmed=confirmed)

        switch = re.search(r"\b(?:switch\s+to|focus)\s+(.+)$", prompt, re.I)
        if switch:
            target = switch.group(1).strip().rstrip(".!?")
            try:
                execution = ToolExecutor.execute_named("computer.focus_window", user, {"window": target}, agent="computer")
                output = dict(execution.output or {})
                verified = bool(output.get("verified") or output.get("success"))
                return {"status": "completed" if verified else "failed", "content": f"Switched to {target}." if verified else f"I couldn't verify that {target} received focus.", "route": "computer.focus_window", "data": {**output, "tool_execution_id": execution.execution_id}}
            except ToolExecutionError as exc:
                return {"status": "failed", "content": f"I couldn't switch to {target}: {exc}", "route": "computer.focus_window.failed", "data": {"error": exc.as_dict()}}

        window_action = re.match(r"^\s*(close|minimize|maximize|restore)(?:\s+(?:the\s+)?)?(?:window|this|current window)?(?:\s+(.+?))?\s*[.!?]?\s*$", prompt, re.I)
        if window_action:
            action = window_action.group(1).casefold()
            target = (window_action.group(2) or "").strip()
            try:
                execution = ToolExecutor.execute_named(f"computer.{action}_window", user, {"window": target, "confirmed": confirmed} if target else {"confirmed": confirmed}, agent="computer")
                output = dict(execution.output or {})
                verified = bool(output.get("verified") or output.get("success"))
                verb = {"close": "Closed", "minimize": "Minimized", "maximize": "Maximized", "restore": "Restored"}[action]
                return {"status": "completed" if verified else "failed", "content": f"{verb} the window." if verified else f"I couldn't verify the {action} action.", "route": f"computer.{action}_window", "data": {**output, "tool_execution_id": execution.execution_id}}
            except HumanInterventionRequired as exc:
                return {"status": "waiting", "content": str(exc), "route": f"computer.{action}_window.approval", "data": {"attention": exc.as_dict()}}
            except ToolExecutionError as exc:
                return {"status": "failed", "content": f"I couldn't {action} the window: {exc}", "route": f"computer.{action}_window.failed", "data": {"error": exc.as_dict()}}

        session = ComputerSessionService.current(user, create=True)
        if re.search(r"\b(?:what(?:'s| is)\s+on\s+(?:my\s+)?screen|describe\s+(?:my\s+)?screen|read\s+(?:my\s+)?screen|inspect\s+(?:the\s+)?screen|current\s+screen)\b", lowered):
            observation = ComputerObservationService.observe(user, session, vision=True, reason="user-screen-question")
            blocker = ComputerObservationService.blocker(observation)
            if blocker:
                return {"status": "waiting", "content": blocker["detail"], "route": "computer.human_intervention", "data": {"computer_session_id": str(session.pk), "attention": blocker, "observation_id": str(observation.pk)}}
            visible = observation.ocr_text.strip()
            window_title = str((observation.window_info or {}).get("title") or "the active window")
            content = f"The active window is {window_title}."
            if visible:
                content += f" Visible text includes: {visible[:1800]}"
            elif (observation.ui_tree or {}).get("available"):
                nodes = (observation.ui_tree or {}).get("elements") or (observation.ui_tree or {}).get("nodes") or []
                labels = [str(item.get("label") or item.get("name") or item.get("text") or "").strip() for item in nodes[:30]]
                labels = [item for item in labels if item]
                if labels:
                    content += " Accessible controls include: " + ", ".join(labels[:12]) + "."
            else:
                content += " I captured the screen, but no reliable OCR/UI-tree text was available."
            return {"status": "completed", "content": content, "route": "computer.observe", "data": {"computer_session_id": str(session.pk), "observation_id": str(observation.pk), "window": observation.window_info, "ocr_text": visible[:5000], "vision": observation.vision, "ui_tree": observation.ui_tree}}

        if "scroll" in lowered:
            amount_match = re.search(r"\bscroll(?:\s+(up|down))?(?:\s+(\d+))?", lowered)
            direction = (amount_match.group(1) if amount_match else None) or ("up" if " up" in lowered else "down")
            magnitude = int(amount_match.group(2)) if amount_match and amount_match.group(2) else 650
            return cls._execute(user, session, "scroll", {"amount": magnitude if direction == "up" else -magnitude}, confirmed=confirmed)

        match = re.search(r"\bdouble\s+click(?:\s+(?:on|the))?\s+(.+)$", prompt, re.I)
        if match:
            return cls._execute(user, session, "double_click", {"target": match.group(1).strip()}, confirmed=confirmed)
        match = re.search(r"\bright\s+click(?:\s+(?:on|the))?\s+(.+)$", prompt, re.I)
        if match:
            return cls._execute(user, session, "right_click", {"target": match.group(1).strip()}, confirmed=confirmed)
        match = re.search(r"\bclick(?:\s+(?:on|the))?\s+(.+)$", prompt, re.I)
        if match:
            return cls._execute(user, session, "click", {"target": match.group(1).strip()}, confirmed=confirmed)
        match = re.search(r"\b(?:move|hover)(?:\s+(?:to|over|on))?\s+(.+)$", prompt, re.I)
        if match:
            return cls._execute(user, session, "move", {"target": match.group(1).strip()}, confirmed=confirmed)

        match = re.search(r"\bdrag\s+(.+?)\s+(?:to|onto)\s+(.+)$", prompt, re.I)
        if match:
            return cls._execute(user, session, "drag", {"target": match.group(1).strip(), "destination": match.group(2).strip()}, confirmed=confirmed)

        # Targeted text input first resolves/focuses the named control with a verified
        # click, then the actual text entry remains approval-gated.
        match = re.search(r"\btype\s+[\"']?(.+?)[\"']?\s+(?:into|in)\s+(.+)$", prompt, re.I)
        if match:
            text, target = match.group(1).strip().strip('\"\''), match.group(2).strip()
            if not confirmed:
                return {
                    "status": "waiting", "content": "Echo needs your approval before entering text into another application.",
                    "route": "computer.approval_required", "needs_confirmation": True,
                    "data": {"computer_session_id": str(session.pk), "pending_action": {"tool": "computer.type", "input": {"text": text, "target": target}}, "attention": {"type": "approval", "detail": "Text input requires approval."}},
                }
            focus = cls._execute(user, session, "click", {"target": target}, confirmed=True)
            if focus.get("status") != "completed":
                return focus
            return cls._execute(user, session, "type", {"text": text}, confirmed=True)
        match = re.search(r"\btype\s+[\"']?(.+?)[\"']?$", prompt, re.I)
        if match:
            return cls._execute(user, session, "type", {"text": match.group(1).strip().strip('\"\'')}, confirmed=confirmed)

        match = re.search(r"\bpress\s+(?:the\s+)?([a-z0-9_+\-]+)(?:\s+key)?\b", lowered)
        if match:
            key = match.group(1)
            if "+" in key:
                return cls._execute(user, session, "hotkey", {"keys": [item for item in key.split("+") if item]}, confirmed=confirmed)
            return cls._execute(user, session, "press_key", {"key": key}, confirmed=confirmed)

        return {"status": "waiting", "content": "I can control the desktop, but I could not identify a safe target or action from that request.", "route": "computer.waiting", "data": {"computer_session_id": str(session.pk)}}


def _session(context: ToolContext, payload: dict[str, Any]) -> ComputerSession:
    identifier = payload.get("computer_session_id")
    return ComputerSessionService.get(context.user, identifier) if identifier else ComputerSessionService.current(context.user, create=True)


def _computer_observe(payload: dict[str, Any], context: ToolContext):
    session = _session(context, payload)
    item = ComputerObservationService.observe(context.user, session, vision=bool(payload.get("vision", False)), target_hint=str(payload.get("target_hint") or ""), reason="tool")
    return {"ok": True, "computer_session_id": str(session.pk), "observation_id": str(item.pk), "content_hash": item.content_hash, "window": item.window_info, "cursor": item.cursor, "viewport": item.viewport, "ocr_text": item.ocr_text[:5000], "vision": item.vision, "ui_tree": item.ui_tree}


def _computer_action(name: str):
    def handler(payload: dict[str, Any], context: ToolContext):
        session = _session(context, payload)
        action_payload = dict(payload or {})
        # Targeted text entry is one approved unit: approval is checked before any
        # focus-changing click, then the named control is resolved from current UI
        # evidence and focused before typing. This prevents an approved target from
        # accidentally typing into whatever application happened to have focus.
        if name == "type" and action_payload.get("target"):
            if not bool(action_payload.get("confirmed")):
                raise HumanInterventionRequired("approval", "Echo needs your approval before entering text into another application.")
            target = action_payload.pop("target")
            focus = ComputerActionService.execute(context.user, session, "click", {"target": target})
            if not focus.verified:
                raise DesktopUnavailable("Echo could not verify focus on the requested text control.")
            action_payload["confirmed"] = True
        outcome = ComputerActionService.execute(context.user, session, name, action_payload)
        return {"ok": outcome.verified, "computer_session_id": str(session.pk), "action_id": outcome.action_id, "observation_id": outcome.observation_id, **outcome.result}
    return handler


def _open_path(payload: dict[str, Any], context: ToolContext):
    return DesktopPathService.open(str(payload.get("path") or payload.get("alias") or ""))


def _list_applications(payload: dict[str, Any], context: ToolContext):
    return {"success": True, "applications": ApplicationDiscoveryService.list_public(limit=int(payload.get("limit") or 200))}


def _launch_application(payload: dict[str, Any], context: ToolContext):
    return ApplicationLauncherService.launch(str(payload.get("application") or ""))


def _list_windows(payload: dict[str, Any], context: ToolContext):
    return {"success": True, "windows": DesktopWindowService.list_windows()}


def _active_window(payload: dict[str, Any], context: ToolContext):
    item = DesktopWindowService.active_window()
    return {"success": bool(item.get("available")), "active_window": item}


def _focus_window(payload: dict[str, Any], context: ToolContext):
    return DesktopWindowService.focus(str(payload.get("window") or ""))


def _window_action(action: str):
    def handler(payload: dict[str, Any], context: ToolContext):
        if action == "close" and not bool(payload.get("confirmed")):
            raise HumanInterventionRequired("approval", "Closing this window may discard unsaved work. Confirm before Echo closes it.")
        return DesktopWindowService.control(action, str(payload.get("window") or ""))
    return handler


def _application_status(payload: dict[str, Any], context: ToolContext):
    return ApplicationLauncherService.status(str(payload.get("application") or ""))


def _execute_computer_task(payload: dict[str, Any], context: ToolContext):
    plan = payload.get("plan") or {}
    if not isinstance(plan, dict):
        raise ValidationError("plan must be an object")
    return ComputerTaskExecutionService.execute(context.user, plan, task_id=context.task_id)


def _capture_screen(payload: dict[str, Any], context: ToolContext):
    session = _session(context, payload)
    item = ComputerObservationService.observe(context.user, session, vision=bool(payload.get("vision", False)), target_hint=str(payload.get("target_hint") or ""), reason="capture_screen")
    return {
        "success": True, "computer_session_id": str(session.pk), "observation_id": str(item.pk),
        "screenshot_url": item.screenshot.url if item.screenshot else None, "window": item.window_info,
        "viewport": item.viewport, "ocr_text": item.ocr_text[:5000], "ui_tree": item.ui_tree, "vision": item.vision,
    }


def _desktop_runtime_available() -> bool:
    """Return whether the local desktop backend can currently reach screen/input APIs."""

    return bool(LocalDesktopBackend.capabilities().get("available"))


def register_desktop_control_tools() -> None:
    ToolExecutor.register(
        "computer.observe", _computer_observe,
        description="Capture the current authorized desktop screen, UI tree, optional OCR/vision and window state.",
        category="computer",
        input_schema={"type": "object", "properties": {"vision": {"type": "boolean"}, "target_hint": {"type": "string"}}, "additionalProperties": True},
        output_schema={"type": "object"}, permissions=("tools.execute",), availability=_desktop_runtime_available, execution_mode="interactive", timeout=30,
        risk_level="low", agent_access=("computer", "planner", "chat", "workflow"),
    )
    schemas = {
        "move": {"type": "object", "properties": {"target": {}, "x": {"type": "integer"}, "y": {"type": "integer"}, "duration": {"type": "number", "minimum": 0, "maximum": 3}}, "additionalProperties": True},
        "click": {"type": "object", "properties": {"target": {}, "x": {"type": "integer"}, "y": {"type": "integer"}}, "additionalProperties": True},
        "double_click": {"type": "object", "properties": {"target": {}, "x": {"type": "integer"}, "y": {"type": "integer"}}, "additionalProperties": True},
        "right_click": {"type": "object", "properties": {"target": {}, "x": {"type": "integer"}, "y": {"type": "integer"}, "confirmed": {"type": "boolean"}}, "additionalProperties": True},
        "scroll": {"type": "object", "properties": {"amount": {"type": "integer"}}, "additionalProperties": True},
        "drag": {"type": "object", "required": ["destination"], "properties": {"target": {}, "x": {"type": "integer"}, "y": {"type": "integer"}, "destination": {}, "button": {"type": "string"}, "duration": {"type": "number", "minimum": 0, "maximum": 3}, "confirmed": {"type": "boolean"}}, "additionalProperties": True},
        "type": {"type": "object", "required": ["text"], "properties": {"target": {}, "text": {"type": "string", "minLength": 1}, "clear": {"type": "boolean"}, "submit": {"type": "boolean"}, "interval": {"type": "number", "minimum": 0, "maximum": 0.2}, "confirmed": {"type": "boolean"}}, "additionalProperties": True},
        "press_key": {"type": "object", "required": ["key"], "properties": {"key": {"type": "string", "minLength": 1}}, "additionalProperties": True},
        "hotkey": {"type": "object", "required": ["keys"], "properties": {"keys": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "string", "minLength": 1}}}, "additionalProperties": True},
        "wait": {"type": "object", "properties": {"seconds": {"type": "number", "minimum": 0, "maximum": 20}}, "additionalProperties": True},
    }
    for action in ("move", "click", "double_click", "right_click", "scroll", "drag", "type", "press_key", "hotkey", "wait"):
        ToolExecutor.register(
            f"computer.{action}", _computer_action(action),
            description=f"Execute a verified desktop {action.replace('_', ' ')} action.", category="computer",
            input_schema=schemas[action], output_schema={"type": "object"},
            permissions=("tools.execute",), availability=_desktop_runtime_available, confirmation="required" if action in {"type", "right_click", "drag"} else "none",
            execution_mode="interactive", timeout=45, risk_level="medium" if action in {"type", "right_click", "drag"} else "low",
            agent_access=("computer", "planner", "chat", "workflow"),
        )
    ToolExecutor.register(
        "computer.open_path", _open_path,
        description="Open an allowed local user/system location and verify the desktop response.", category="computer",
        input_schema={"type": "object", "required": ["path"], "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 1000}}, "additionalProperties": False},
        output_schema={"type": "object"}, permissions=("tools.execute",), availability=SystemLocationResolver.is_available, execution_mode="interactive", timeout=30,
        risk_level="low", agent_access=("computer", "planner", "chat", "workflow"),
    )
    ToolExecutor.register(
        "computer.list_applications", _list_applications, description="Discover installed desktop applications from OS metadata and PATH.", category="computer",
        input_schema={"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 500}}, "additionalProperties": False},
        output_schema={"type": "object"}, permissions=("tools.execute",), availability=True, execution_mode="sync", timeout=10, risk_level="low", agent_access=("computer", "planner", "chat", "workflow"),
    )
    ToolExecutor.register(
        "computer.launch_application", _launch_application, description="Launch an installed local desktop application and verify process/window evidence.", category="computer",
        input_schema={"type": "object", "required": ["application"], "properties": {"application": {"type": "string", "minLength": 1, "maxLength": 200}}, "additionalProperties": False},
        output_schema={"type": "object"}, permissions=("tools.execute",), availability=ApplicationLauncherService.is_available, execution_mode="interactive", timeout=30, risk_level="low", agent_access=("computer", "planner", "chat", "workflow"),
    )
    ToolExecutor.register(
        "computer.application_status", _application_status, description="Check whether a discovered local application is currently running and visible.", category="computer",
        input_schema={"type": "object", "required": ["application"], "properties": {"application": {"type": "string", "minLength": 1, "maxLength": 200}}, "additionalProperties": False},
        output_schema={"type": "object"}, permissions=("tools.execute",), availability=True, execution_mode="sync", timeout=10, risk_level="low", agent_access=("computer", "planner", "chat", "workflow"),
    )
    ToolExecutor.register(
        "computer.list_windows", _list_windows, description="List visible desktop windows from the active OS window manager.", category="computer", input_schema={"type": "object", "additionalProperties": False}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=lambda: bool(DesktopWindowService.capabilities().get("available")), execution_mode="sync", timeout=10, risk_level="low", agent_access=("computer", "planner", "chat", "workflow"),
    )
    ToolExecutor.register(
        "computer.get_active_window", _active_window, description="Return the currently focused desktop application/window.", category="computer", input_schema={"type": "object", "additionalProperties": False}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=lambda: bool(DesktopWindowService.capabilities().get("available")), execution_mode="sync", timeout=10, risk_level="low", agent_access=("computer", "planner", "chat", "workflow"),
    )
    ToolExecutor.register(
        "computer.focus_window", _focus_window, description="Focus an existing desktop window and verify focus.", category="computer", input_schema={"type": "object", "required": ["window"], "properties": {"window": {"type": "string", "minLength": 1, "maxLength": 300}}, "additionalProperties": False}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=lambda: bool(DesktopWindowService.capabilities().get("available")), execution_mode="interactive", timeout=15, risk_level="low", agent_access=("computer", "planner", "chat", "workflow"),
    )
    for action in ("minimize", "maximize", "restore", "close"):
        ToolExecutor.register(
            f"computer.{action}_window", _window_action(action), description=f"{action.title()} a visible desktop window and verify the result.", category="computer",
            input_schema={"type": "object", "properties": {"window": {"type": "string", "maxLength": 300}, "confirmed": {"type": "boolean"}}, "additionalProperties": False},
            output_schema={"type": "object"}, permissions=("tools.execute",), availability=lambda: bool(DesktopWindowService.capabilities().get("available")),
            confirmation="required" if action == "close" else "none", execution_mode="interactive", timeout=15, risk_level="high" if action == "close" else "low",
            agent_access=("computer", "planner", "chat", "workflow"),
        )
    ToolExecutor.register(
        "computer.capture_screen", _capture_screen, description="Capture and persist the current screen observation with optional OCR/vision evidence.", category="computer", input_schema={"type": "object", "properties": {"vision": {"type": "boolean"}, "target_hint": {"type": "string", "maxLength": 500}}, "additionalProperties": False}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=_desktop_runtime_available, execution_mode="interactive", timeout=60, risk_level="low", agent_access=("computer", "planner", "chat", "workflow"),
    )
    ToolExecutor.register(
        "computer.execute_task", _execute_computer_task,
        description="Execute a structured multi-step local-computer plan through verified application, window, keyboard, mouse and observation tools.",
        category="computer", input_schema={"type": "object", "required": ["plan"], "properties": {"plan": {"type": "object"}}, "additionalProperties": False},
        output_schema={"type": "object"}, permissions=("tools.execute",), availability=ApplicationLauncherService.is_available,
        execution_mode="interactive", timeout=120, risk_level="medium", cancellable=True, agent_access=("computer", "planner", "workflow"),
    )
