from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from echo.apps.internet.local_system import ApplicationDiscoveryService, SystemLocationResolver


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    agent: str
    confidence: float
    target: str = ""
    query: str = ""
    url: str = ""
    clarification: str = ""
    metadata: dict[str, Any] | None = None


class WebsiteResolver:
    """Resolve explicit domains and a small set of ubiquitous site aliases.

    This is not the browser automation architecture; it is only disambiguation for
    natural-language targets such as "Open YouTube" versus "Open Firefox". Any URL
    that the user supplies directly is supported without being in this alias table.
    """

    ALIASES = {
        "youtube": "https://www.youtube.com/",
        "google": "https://www.google.com/",
        "gmail": "https://mail.google.com/",
        "github": "https://github.com/",
        "wikipedia": "https://www.wikipedia.org/",
        "reddit": "https://www.reddit.com/",
        "linkedin": "https://www.linkedin.com/",
        "upwork": "https://www.upwork.com/",
    }

    @staticmethod
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9.-]+", " ", str(value or "").casefold()).strip()

    @classmethod
    def resolve(cls, target: str) -> str:
        raw = str(target or "").strip().strip('"\'').rstrip(".,!?;:")
        normalized = cls.normalize(raw)
        if normalized in cls.ALIASES:
            return cls.ALIASES[normalized]
        if re.match(r"^https?://", raw, re.I):
            parsed = urlparse(raw)
            return raw if parsed.hostname else ""
        if re.match(r"^(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/\S*)?$", raw, re.I):
            return "https://" + raw.lstrip("/")
        return ""


class UniversalIntentRouter:
    """Deterministic high-confidence routing before model interpretation.

    The router answers *where* an action belongs; it never performs the action. It
    deliberately does not turn unknown OPEN commands into web searches.
    """

    OPEN_RE = re.compile(r"^\s*(?:please\s+)?(?:open|launch|start|show|take\s+me\s+to)\s+(?:my\s+|the\s+)?(.+?)\s*[.!?]?\s*$", re.I)
    GO_RE = re.compile(r"^\s*(?:please\s+)?(?:go\s+to|navigate\s+to|visit)\s+(.+?)\s*[.!?]?\s*$", re.I)
    SEARCH_RE = re.compile(r"^\s*(?:please\s+)?search(?:\s+(google|youtube|the\s+web|web))?\s+(?:for\s+)?(.+?)\s*[.!?]?\s*$", re.I)
    AMBIGUOUS_OPEN_TARGETS = {"python", "java", "node", "nodejs", "ruby", "php", "go", "rust", "django"}
    LOCAL_ENVIRONMENT_MARKERS = (
        "on my computer", "on my pc", "on this computer", "on the computer", "on my desktop",
        "on this desktop", "on my screen", "using firefox", "using chrome", "using chromium",
        "using the browser on my computer",
    )

    @classmethod
    def _compound_local_task(cls, text: str) -> IntentDecision | None:
        """Resolve explicit/multi-step desktop objectives before web-search routing.

        The first operation establishes the execution environment.  A later word such
        as ``search`` is therefore treated as work to perform *inside* the requested
        local application instead of reclassifying the whole utterance as internet
        search.  This parser is intentionally deterministic for high-confidence local
        commands; uncertain targets still fall through to normal contextual routing.
        """
        raw = re.sub(r"\s+", " ", str(text or "").strip())
        first = re.match(
            r"^(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?"
            r"(?P<application>.+?)(?=(?:\s+on\s+(?:my|this|the)\s+(?:computer|pc|desktop))|(?:\s*(?:,|\band\b|\bthen\b)\s+)|$)"
            r"(?P<local>\s+on\s+(?:my|this|the)\s+(?:computer|pc|desktop))?"
            r"(?P<rest>\s*(?:,|\band\b|\bthen\b).+)?$",
            raw, re.I,
        )
        if not first:
            return None
        application = re.sub(r"\s+", " ", first.group("application")).strip(" .,:;-_")
        local_marker = bool(first.group("local")) or any(marker in raw.casefold() for marker in cls.LOCAL_ENVIRONMENT_MARKERS)
        if not (local_marker or ApplicationDiscoveryService.recognizes_application_name(application)):
            return None
        # Website aliases must not be stolen merely because a similarly named local
        # executable exists.  An explicit desktop marker overrides this rule.
        if not local_marker and WebsiteResolver.resolve(application):
            return None
        rest = str(first.group("rest") or "").strip()
        rest = re.sub(r"^(?:,|\band\b|\bthen\b)\s*", "", rest, flags=re.I)
        rest = re.sub(r"^on\s+(?:my|this|the)\s+(?:computer|pc|desktop)\s*(?:,|\band\b|\bthen\b)?\s*", "", rest, flags=re.I)
        actions: list[dict[str, Any]] = [{"type": "open_application", "application": application}]
        query = ""
        url = ""
        if rest:
            search = re.match(r"^(?:search|find|look\s+up)(?:\s+(?:the\s+web|web|google))?\s+(?:for\s+)?(?P<query>.+)$", rest, re.I)
            navigate = re.match(r"^(?:go\s+to|navigate\s+to|visit|open)\s+(?P<target>.+)$", rest, re.I)
            if search:
                query = search.group("query").strip().rstrip(".!?")
                actions.append({"type": "browser_search_in_application", "query": query})
            elif navigate:
                target = navigate.group("target").strip().rstrip(".!?")
                url = WebsiteResolver.resolve(target)
                actions.append({"type": "browser_navigate_in_application", "target": target, "url": url})
            else:
                actions.append({"type": "continue_in_application", "instruction": rest})
        return IntentDecision(
            "computer_task", "computer", 1.0 if local_marker else 0.98, target=application, query=query, url=url,
            metadata={
                "environment": "local_computer", "application": application, "actions": actions,
                "task_text": rest, "explicit_environment": local_marker,
            },
        )

    @classmethod
    def _explicit_application_environment_task(cls, text: str) -> IntentDecision | None:
        """Honor an explicitly named local application even when SEARCH is the first verb."""
        raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ,")
        candidates: list[tuple[str, str]] = []
        prefix = re.match(
            r"^(?:on\s+(?:my|this|the)\s+(?:computer|pc|desktop)\s*[,;:]?\s*)?"
            r"(?:using|in)\s+(?P<application>.+?)(?=\s*[,;:]\s*|\s+(?:search|find|look\s+up|go\s+to|navigate\s+to|visit)\b)"
            r"\s*[,;:]?\s*(?P<task>(?:search|find|look\s+up|go\s+to|navigate\s+to|visit).+)$",
            raw, re.I,
        )
        if prefix:
            candidates.append((prefix.group("application").strip(), prefix.group("task").strip()))
        suffix = re.match(
            r"^(?P<task>(?:search|find|look\s+up|go\s+to|navigate\s+to|visit).+?)"
            r"\s+(?:using|in)\s+(?P<application>.+?)(?:\s+on\s+(?:my|this|the)\s+(?:computer|pc|desktop))?$",
            raw, re.I,
        )
        if suffix:
            candidates.append((suffix.group("application").strip(), suffix.group("task").strip()))
        for application, task_text in candidates:
            if not ApplicationDiscoveryService.recognizes_application_name(application):
                continue
            actions: list[dict[str, Any]] = [{"type": "open_application", "application": application}]
            query = ""
            url = ""
            search = re.match(r"^(?:search|find|look\s+up)(?:\s+(?:the\s+web|web|google))?\s+(?:for\s+)?(?P<query>.+)$", task_text, re.I)
            navigate = re.match(r"^(?:go\s+to|navigate\s+to|visit)\s+(?P<target>.+)$", task_text, re.I)
            if search:
                query = search.group("query").strip().rstrip(".!?")
                actions.append({"type": "browser_search_in_application", "query": query})
            elif navigate:
                target = navigate.group("target").strip().rstrip(".!?")
                url = WebsiteResolver.resolve(target)
                actions.append({"type": "browser_navigate_in_application", "target": target, "url": url})
            else:
                continue
            return IntentDecision(
                "computer_task", "computer", 1.0, target=application, query=query, url=url,
                metadata={
                    "environment": "local_computer", "application": application, "actions": actions,
                    "task_text": task_text, "explicit_environment": True,
                },
            )
        return None

    @staticmethod
    def _recent_environment(user) -> str:
        if user is None:
            return ""
        try:
            from echo.apps.internet.models import BrowserSession, ComputerSession
            browser = BrowserSession.objects.filter(owner=user).exclude(status__in=("completed", "ended", "closed")).order_by("-last_activity_at").first()
            computer = ComputerSession.objects.filter(owner=user).exclude(status__in=("completed", "ended", "closed")).order_by("-last_activity_at").first()
            if browser and computer:
                browser_time = browser.last_activity_at or browser.updated_at
                computer_time = computer.last_activity_at or computer.updated_at
                return "browser" if browser_time >= computer_time else "computer"
            return "browser" if browser else "computer" if computer else ""
        except Exception:
            return ""

    @classmethod
    def classify(cls, prompt: str, *, user=None) -> IntentDecision | None:
        text = str(prompt or "").strip()
        lowered = text.casefold()
        if not text:
            return None

        # Compound local tasks establish their execution environment before any later
        # search/navigation verb is interpreted.  Example: ``Open Firefox on my
        # computer and search Django docs`` remains a Computer Agent objective.
        compound = cls._compound_local_task(text)
        if compound:
            return compound
        explicit_application = cls._explicit_application_environment_task(text)
        if explicit_application:
            return explicit_application

        # Explicit searches always remain searches, even when the query happens to be
        # the name of an installed application.
        match = cls.SEARCH_RE.match(text)
        if match:
            provider = (match.group(1) or "web").casefold().replace("the ", "")
            query = match.group(2).strip()
            return IntentDecision("web_search", "browser", 0.99, query=query, metadata={"provider": provider})

        match = cls.GO_RE.match(text)
        if match:
            target = match.group(1).strip()
            url = WebsiteResolver.resolve(target)
            if url:
                return IntentDecision("website_action", "browser", 0.99, target=target, url=url)

        match = cls.OPEN_RE.match(text)
        if match:
            target = match.group(1).strip().rstrip(".!?")
            normalized_reference = re.sub(r"[^a-z0-9 ]+", " ", target.casefold()).strip()
            referential = bool(re.match(r"^(?:that|this|current|the\s+(?:first|second|third|next|previous)|(?:first|second|third|next|previous)\s+one)\b", normalized_reference))
            if referential:
                environment = cls._recent_environment(user)
                browser_hint = bool(re.search(r"\b(?:video|playlist|link|result|page|tab|website)\b", normalized_reference))
                agent = "browser" if environment == "browser" or browser_hint else "computer"
                return IntentDecision("contextual_interaction", agent, 0.94, target=target, metadata={"environment": environment, "referential": True})
            normalized_target = ApplicationDiscoveryService.normalize(target)
            if normalized_target in cls.AMBIGUOUS_OPEN_TARGETS:
                return IntentDecision(
                    "ambiguous_open", "clarify", 0.45, target=target,
                    clarification=f"Do you want me to open {target} on your computer, or open/search for it on the web?",
                )
            # Local system locations are unambiguous desktop targets. Exact website
            # aliases are resolved before *fuzzy* installed-application matching so
            # "Open Google" means the Google website while "Open Google Chrome"
            # still resolves to the installed application.
            if SystemLocationResolver.recognizes(target):
                return IntentDecision("local_system_location", "computer", 1.0, target=target)
            url = WebsiteResolver.resolve(target)
            if url:
                return IntentDecision("website_action", "browser", 0.99, target=target, url=url)
            if ApplicationDiscoveryService.recognizes_application_name(target):
                return IntentDecision("local_application", "computer", 0.99, target=target)
            if re.search(r"\b(?:folder|directory|path|drive)\b", target, re.I) or target.startswith(("~/", "/")):
                return IntentDecision("file_system_action", "computer", 0.92, target=target)
            # "Open X" is not a request to search the web. Ambiguous targets remain
            # unresolved and the manager asks the user instead of guessing.
            return IntentDecision(
                "ambiguous_open", "clarify", 0.45, target=target,
                clarification=f"Do you want me to open {target} on your computer, or open/search for it on the web?",
            )

        # Context-dependent direct-manipulation language routes to whichever real
        # environment was most recently active. If no environment exists, desktop is
        # favored for mouse/keyboard language while browser-specific terms stay web.
        if re.search(r"\b(?:click|double\s+click|right\s+click|scroll|type|press|drag|hover|move|play|pause|resume|close|minimize|maximize|restore)\b", lowered):
            environment = cls._recent_environment(user)
            browser_specific = bool(re.search(r"\b(?:page|tab|link|website|browser|video|playlist|url)\b", lowered))
            agent = "browser" if environment == "browser" or browser_specific else "computer"
            return IntentDecision("contextual_interaction", agent, 0.9, metadata={"environment": environment})

        if re.fullmatch(r"\s*(?:go\s+back|back|go\s+forward|forward|refresh|reload)\s*[.!?]?\s*", lowered):
            environment = cls._recent_environment(user)
            return IntentDecision("contextual_navigation", "browser" if environment == "browser" else "computer", 0.9, metadata={"environment": environment})
        if re.search(r"\b(?:switch\s+to|focus)\s+.+", lowered) or "previous window" in lowered:
            return IntentDecision("window_action", "computer", 0.96)
        if re.search(r"\b(?:current screen|my screen|active window|list windows|list applications|installed applications)\b", lowered):
            return IntentDecision("computer_observation", "computer", 0.97)
        return None
