from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import logging
import os
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, transaction
from django.utils import timezone

from echo.apps.ai_engine.provider import AIProviderError, OpenAICompatibleProvider
from echo.apps.tool_manager.execution import ToolContext, ToolExecutionError, ToolExecutor

from .models import BrowserAction, BrowserObservation, BrowserSession, ComputerUseOperation, MediaUnderstanding
from .safe_fetch import UnsafeURL, validate_public_url

logger = logging.getLogger(__name__)


class ComputerUseError(RuntimeError):
    pass


class BrowserUnavailable(ComputerUseError):
    pass


class BrowserTargetNotFound(ComputerUseError):
    pass


class ComputerUseCancelled(ComputerUseError):
    pass


class HumanInterventionRequired(ComputerUseError):
    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class ActionOutcome:
    action_id: str
    verified: bool
    result: dict[str, Any]
    observation_id: str | None = None


_ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3, "fifth": 4, "5th": 4}
_SITE_ALIASES = {
    "youtube": "https://www.youtube.com/",
    "google": "https://www.google.com/",
    "gmail": "https://mail.google.com/",
    "github": "https://github.com/",
    "wikipedia": "https://www.wikipedia.org/",
    "reddit": "https://www.reddit.com/",
    "linkedin": "https://www.linkedin.com/",
    "upwork": "https://www.upwork.com/",
}


def normalize_url(target: str) -> str:
    value = str(target or "").strip().strip('"\'').rstrip(".,")
    if not value:
        raise ValidationError("A destination is required.")
    alias = _SITE_ALIASES.get(value.casefold())
    if alias:
        return alias
    if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}(?:/.*)?", value, re.I):
        return f"https://{value}"
    if value.startswith(("http://", "https://")):
        return value
    raise ValidationError("That destination is not a recognized website or URL. Use browser.search for an explicit web search.")


def validate_browser_url(url: str) -> str:
    """Validate browser navigation while preserving an explicit localhost opt-in."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if host in {"localhost", "127.0.0.1", "::1"} and getattr(settings, "ECHO_BROWSER_ALLOW_LOCALHOST", False):
        if parsed.scheme not in {"http", "https"}:
            raise UnsafeURL("Only HTTP and HTTPS localhost URLs are allowed.")
        return url
    if getattr(settings, "ECHO_BROWSER_ALLOW_PRIVATE_NETWORKS", False):
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise UnsafeURL("Only HTTP and HTTPS URLs are allowed.")
        if parsed.username or parsed.password:
            raise UnsafeURL("Credentials embedded in URLs are not allowed.")
        return url
    validate_public_url(url)
    return url


class SeleniumBrowserBackend:
    """General browser backend using Selenium and page structure before vision.

    The backend is intentionally website-neutral.  It annotates currently visible
    interactive elements with ephemeral ``data-echo-node`` identifiers, allowing
    the orchestrator to resolve targets from DOM/accessibility evidence instead of
    hard-coded coordinates.
    """

    def __init__(self, session: BrowserSession):
        self.session = session
        self._driver = None

    @staticmethod
    def capabilities() -> dict[str, Any]:
        available = importlib.util.find_spec("selenium") is not None
        return {
            "available": available,
            "provider": "selenium",
            "engine": str(getattr(settings, "ECHO_BROWSER_ENGINE", "chrome")),
            "remote": bool(str(getattr(settings, "ECHO_BROWSER_REMOTE_URL", "") or "").strip()),
            "reason": "" if available else "Selenium is not installed.",
        }

    @staticmethod
    def _selenium():
        try:
            from selenium import webdriver
            from selenium.webdriver import ActionChains, Keys
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import Select
        except ImportError as exc:
            raise BrowserUnavailable("Selenium is not installed. Run pip install -r requirements.txt.") from exc
        return webdriver, ActionChains, Keys, By, Select

    def download_dir(self) -> Path:
        path = Path(settings.MEDIA_ROOT) / "browser_downloads" / str(self.session.owner_id) / str(self.session.pk)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _driver_options(self):
        webdriver, *_ = self._selenium()
        engine = (self.session.engine or getattr(settings, "ECHO_BROWSER_ENGINE", "chrome")).casefold()
        headless = bool(self.session.headless)
        profile_dir = Path(settings.MEDIA_ROOT) / "browser_profiles" / str(self.session.owner_id) / str(self.session.pk)
        profile_dir.mkdir(parents=True, exist_ok=True)
        download_dir = self.download_dir()
        if engine in {"chrome", "chromium", "edge"}:
            options = webdriver.EdgeOptions() if engine == "edge" else webdriver.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument("--window-size=1440,960")
            binary = getattr(settings, "ECHO_BROWSER_BINARY", "")
            if binary:
                options.binary_location = binary
            if engine != "edge":
                options.add_experimental_option("prefs", {
                    "download.default_directory": str(download_dir.resolve()),
                    "download.prompt_for_download": False,
                    "safebrowsing.enabled": True,
                })
            return engine, options
        if engine == "firefox":
            options = webdriver.FirefoxOptions()
            if headless:
                options.add_argument("-headless")
            if getattr(settings, "ECHO_BROWSER_BINARY", ""):
                options.binary_location = settings.ECHO_BROWSER_BINARY
            options.set_preference("browser.download.folderList", 2)
            options.set_preference("browser.download.dir", str(download_dir.resolve()))
            options.set_preference("browser.download.useDownloadDir", True)
            options.set_preference("browser.download.manager.showWhenStarting", False)
            return engine, options
        raise BrowserUnavailable(f"Unsupported browser engine: {engine}")

    def start(self):
        if self._driver is not None:
            try:
                _ = self._driver.current_url
                return self._driver
            except Exception:
                self._driver = None
        webdriver, *_ = self._selenium()
        engine, options = self._driver_options()
        try:
            remote_url = str(getattr(settings, "ECHO_BROWSER_REMOTE_URL", "") or "").strip()
            if remote_url:
                driver = webdriver.Remote(command_executor=remote_url, options=options)
            elif engine == "edge":
                driver = webdriver.Edge(options=options)
            elif engine == "firefox":
                driver = webdriver.Firefox(options=options)
            else:
                driver = webdriver.Chrome(options=options)
        except Exception as exc:
            raise BrowserUnavailable(
                "Echo could not start a controlled browser. Install a supported Chrome/Chromium, Edge, or Firefox browser and verify ECHO_BROWSER_ENGINE/ECHO_BROWSER_BINARY. "
                f"Driver error: {exc}"
            ) from exc
        driver.set_page_load_timeout(int(getattr(settings, "ECHO_BROWSER_PAGELOAD_TIMEOUT", 30)))
        driver.set_script_timeout(int(getattr(settings, "ECHO_BROWSER_SCRIPT_TIMEOUT", 20)))
        self._driver = driver
        return driver

    @property
    def driver(self):
        return self.start()

    def close(self):
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def current_state(self) -> dict[str, Any]:
        driver = self.driver
        try:
            handles = list(driver.window_handles)
            current = driver.current_window_handle
        except Exception:
            handles, current = [], ""
        return {
            "url": driver.current_url,
            "title": driver.title,
            "window_handles": handles,
            "active_tab_handle": current,
        }

    def get_accessibility_tree(self) -> dict[str, Any]:
        driver = self.driver
        if not hasattr(driver, "execute_cdp_cmd"):
            return {"available": False, "reason": "CDP accessibility tree is unavailable for this browser engine."}
        try:
            raw = driver.execute_cdp_cmd("Accessibility.getFullAXTree", {})
            nodes = []
            for node in (raw.get("nodes") or [])[:1500]:
                role = ((node.get("role") or {}).get("value") if isinstance(node.get("role"), dict) else node.get("role")) or ""
                name = ((node.get("name") or {}).get("value") if isinstance(node.get("name"), dict) else node.get("name")) or ""
                value = ((node.get("value") or {}).get("value") if isinstance(node.get("value"), dict) else node.get("value")) or ""
                if role or name or value:
                    nodes.append({
                        "node_id": node.get("nodeId"),
                        "backend_dom_node_id": node.get("backendDOMNodeId"),
                        "role": str(role)[:120],
                        "name": str(name)[:500],
                        "value": str(value)[:500],
                        "ignored": bool(node.get("ignored")),
                    })
            return {"available": True, "nodes": nodes}
        except Exception as exc:
            return {"available": False, "reason": str(exc)[:500]}

    def get_structured_page(self) -> dict[str, Any]:
        script = r"""
        const maxItems = 350;
        const interactiveSelector = [
          'a[href]','button','input','textarea','select','option','summary','details',
          '[role="button"]','[role="link"]','[role="menuitem"]','[role="tab"]','[role="checkbox"]',
          '[role="radio"]','[role="switch"]','[role="searchbox"]','[contenteditable="true"]','video','audio'
        ].join(',');
        const isVisible = (el) => {
          const s = getComputedStyle(el); const r = el.getBoundingClientRect();
          return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) > 0 && r.width > 1 && r.height > 1;
        };
        const clean = (v, n=700) => String(v || '').replace(/\s+/g,' ').trim().slice(0,n);
        const elements = [];
        let counter = Number(document.documentElement.dataset.echoNodeCounter || 0);
        for (const el of document.querySelectorAll(interactiveSelector)) {
          if (elements.length >= maxItems || !isVisible(el)) continue;
          if (!el.dataset.echoNode) { counter += 1; el.dataset.echoNode = `echo-${counter}`; }
          const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
          elements.push({
            echo_id: el.dataset.echoNode,
            tag: el.tagName.toLowerCase(),
            role: clean(el.getAttribute('role') || ''),
            text: clean(el.innerText || el.textContent || ''),
            aria_label: clean(el.getAttribute('aria-label') || ''),
            title: clean(el.getAttribute('title') || ''),
            placeholder: clean(el.getAttribute('placeholder') || ''),
            name: clean(el.getAttribute('name') || ''),
            type: clean(el.getAttribute('type') || ''),
            href: clean(el.href || ''),
            value: clean(el.value || ''),
            download: el.hasAttribute('download'),
            disabled: Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true'),
            checked: Boolean(el.checked || el.getAttribute('aria-checked') === 'true'),
            rect: {x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height)},
            style: {color: s.color, background_color: s.backgroundColor, cursor: s.cursor}
          });
        }
        document.documentElement.dataset.echoNodeCounter = String(counter);
        const headings = Array.from(document.querySelectorAll('h1,h2,h3,[role="heading"]')).filter(isVisible).slice(0,80).map(el => clean(el.innerText || el.textContent));
        const media = Array.from(document.querySelectorAll('video,audio')).filter(isVisible).slice(0,12).map((el, index) => {
          let cues = [];
          try {
            for (const track of Array.from(el.textTracks || [])) {
              if (!track.cues) continue;
              for (const cue of Array.from(track.cues).slice(0,1000)) cues.push({start: cue.startTime, end: cue.endTime, text: clean(cue.text, 2000), label: track.label || '', language: track.language || ''});
            }
          } catch (_) {}
          return {index, tag: el.tagName.toLowerCase(), current_src: clean(el.currentSrc || el.src || '', 3000), current_time: Number(el.currentTime || 0), duration: Number.isFinite(el.duration) ? Number(el.duration) : null, paused: Boolean(el.paused), ended: Boolean(el.ended), muted: Boolean(el.muted), volume: Number(el.volume ?? 1), ready_state: Number(el.readyState || 0), captions: cues.slice(0,2500)};
        });
        const liveText = Array.from(document.querySelectorAll('[aria-live], [class*="caption" i], [class*="subtitle" i]')).filter(isVisible).slice(0,40).map(el => clean(el.innerText || el.textContent, 3000)).filter(Boolean);
        return {
          url: location.href,
          title: document.title,
          visible_text: clean(document.body?.innerText || '', 60000),
          elements,
          headings,
          media,
          live_text: [...new Set(liveText)].slice(0,40),
          viewport: {width: innerWidth, height: innerHeight, scroll_x: scrollX, scroll_y: scrollY, document_width: document.documentElement.scrollWidth, document_height: document.documentElement.scrollHeight, device_pixel_ratio: devicePixelRatio || 1}
        };
        """
        return self.driver.execute_script(script)

    def screenshot_png(self) -> bytes:
        return self.driver.get_screenshot_as_png()

    def capture_media_audio(self, index: int = 0, *, seconds: float = 6.0) -> dict[str, Any]:
        """Capture rendered audio only when the page/browser exposes it legitimately.

        This uses HTMLMediaElement.captureStream/MediaRecorder. Encrypted-media
        elements are rejected and unsupported pages return a factual capability
        result rather than falling back to downloading media.
        """
        seconds = min(max(float(seconds or 6.0), 1.0), 8.0)
        script = r"""
        const idx = arguments[0], durationMs = arguments[1], done = arguments[arguments.length - 1];
        const media = [...document.querySelectorAll('video,audio')].filter(el => {
          const r = el.getBoundingClientRect(), s = getComputedStyle(el);
          return r.width > 1 && r.height > 1 && s.display !== 'none' && s.visibility !== 'hidden';
        });
        if (idx < 0 || idx >= media.length) { done({ok:false, reason:'media_not_found'}); return; }
        const el = media[idx];
        if (el.mediaKeys) { done({ok:false, reason:'encrypted_media'}); return; }
        const capture = el.captureStream || el.mozCaptureStream;
        if (!capture || typeof MediaRecorder === 'undefined') { done({ok:false, reason:'capture_unsupported'}); return; }
        let stream;
        try { stream = capture.call(el); } catch (e) { done({ok:false, reason:'capture_failed', error:String(e)}); return; }
        const tracks = stream.getAudioTracks();
        if (!tracks.length) { done({ok:false, reason:'audio_track_unavailable'}); return; }
        const audioStream = new MediaStream(tracks);
        const types = ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/ogg'];
        const mime = types.find(t => MediaRecorder.isTypeSupported(t)) || '';
        const chunks = []; let recorder; const wasPaused = el.paused;
        const finish = (payload) => { try { audioStream.getTracks().forEach(t => t.stop()); } catch(e) {} done(payload); };
        try { recorder = mime ? new MediaRecorder(audioStream, {mimeType:mime}) : new MediaRecorder(audioStream); }
        catch (e) { finish({ok:false, reason:'recorder_unavailable', error:String(e)}); return; }
        recorder.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
        recorder.onerror = e => finish({ok:false, reason:'recording_failed', error:String(e.error || e)});
        recorder.onstop = () => {
          if (wasPaused) { try { el.pause(); } catch(e) {} }
          const blob = new Blob(chunks, {type: recorder.mimeType || mime || 'audio/webm'});
          if (!blob.size) { finish({ok:false, reason:'empty_audio'}); return; }
          const reader = new FileReader();
          reader.onerror = () => finish({ok:false, reason:'audio_encoding_failed'});
          reader.onloadend = () => finish({ok:true, mime_type:blob.type || 'audio/webm', audio_base64:String(reader.result || '').split(',').pop(), size:blob.size});
          reader.readAsDataURL(blob);
        };
        Promise.resolve(el.play()).then(() => { recorder.start(250); setTimeout(() => { if (recorder.state !== 'inactive') recorder.stop(); }, durationMs); })
          .catch(e => finish({ok:false, reason:'playback_rejected', error:String(e)}));
        """
        try:
            return dict(self.driver.execute_async_script(script, int(index), int(seconds * 1000)) or {})
        except Exception as exc:
            return {"ok": False, "reason": "capture_failed", "error": str(exc)[:500]}

    def _element_by_echo_id(self, echo_id: str):
        _, _, _, By, _ = self._selenium()
        found = self.driver.find_elements(By.CSS_SELECTOR, f'[data-echo-node="{echo_id}"]')
        return found[0] if found else None

    @staticmethod
    def _element_score(item: dict[str, Any], target: str) -> int:
        needle = target.casefold().strip()
        if not needle:
            return 0
        fields = [item.get("text", ""), item.get("aria_label", ""), item.get("title", ""), item.get("placeholder", ""), item.get("name", "")]
        score = 0
        for value in fields:
            text = str(value or "").casefold()
            if text == needle:
                score = max(score, 100)
            elif needle in text:
                score = max(score, 70)
            elif all(token in text for token in needle.split() if len(token) > 2):
                score = max(score, 45)
        if "button" in needle and (item.get("tag") == "button" or item.get("role") == "button"):
            score += 12
        if "link" in needle and (item.get("tag") == "a" or item.get("role") == "link"):
            score += 12
        if "blue" in needle and "rgb(0" in str((item.get("style") or {}).get("background_color", "")):
            score += 8
        return score

    def resolve_element(self, target: Any, *, page: dict[str, Any] | None = None):
        page = page or self.get_structured_page()
        elements = list(page.get("elements") or [])
        if isinstance(target, dict):
            if target.get("echo_id"):
                element = self._element_by_echo_id(str(target["echo_id"]))
                if element:
                    return element, next((item for item in elements if item.get("echo_id") == target["echo_id"]), {})
            selector = str(target.get("selector") or "").strip()
            if selector:
                _, _, _, By, _ = self._selenium()
                matches = self.driver.find_elements(By.CSS_SELECTOR, selector)
                visible = [item for item in matches if item.is_displayed()]
                index = max(0, int(target.get("index", 0) or 0))
                if index < len(visible):
                    return visible[index], {"selector": selector, "index": index}
            kind = str(target.get("kind") or "").casefold()
            index = max(0, int(target.get("index", 0) or 0))
            candidates = elements
            if kind in {"video", "media", "media_link"}:
                candidates = [item for item in elements if item.get("tag") == "video" or any(token in f"{item.get('text','')} {item.get('href','')}".casefold() for token in ("video", "watch", "playlist"))]
                if not candidates:
                    candidates = [item for item in elements if item.get("tag") == "a" and item.get("href")]
            elif kind == "result":
                candidates = [item for item in elements if item.get("tag") == "a" and item.get("href")]
            elif kind == "button":
                candidates = [item for item in elements if item.get("tag") == "button" or item.get("role") == "button"]
            elif kind == "menu":
                candidates = [item for item in elements if item.get("tag") == "button" or item.get("role") in {"button", "menuitem"}]
            elif kind in {"search", "searchbox"}:
                candidates = [item for item in elements if item.get("role") == "searchbox" or item.get("type") == "search" or "search" in f"{item.get('name','')} {item.get('placeholder','')} {item.get('aria_label','')}".casefold()]
            if target.get("text"):
                needle = str(target["text"])
                candidates = sorted(candidates, key=lambda item: self._element_score(item, needle), reverse=True)
                candidates = [item for item in candidates if self._element_score(item, needle) > 0]
            if index < len(candidates):
                descriptor = candidates[index]
                element = self._element_by_echo_id(str(descriptor.get("echo_id", "")))
                if element:
                    return element, descriptor
        text = str(target or "").strip()
        ranked = sorted(((self._element_score(item, text), item) for item in elements), key=lambda pair: pair[0], reverse=True)
        if ranked and ranked[0][0] > 0:
            descriptor = ranked[0][1]
            element = self._element_by_echo_id(str(descriptor.get("echo_id", "")))
            if element:
                return element, descriptor
        raise BrowserTargetNotFound(f"Echo could not identify the requested control: {target!r}.")

    def perform(self, action: str, arguments: dict[str, Any], *, page: dict[str, Any] | None = None) -> dict[str, Any]:
        webdriver, ActionChains, Keys, _, Select = self._selenium()
        driver = self.driver
        action = action.casefold().strip()
        target = arguments.get("target")
        if action in {"open_url", "navigate"}:
            url = validate_browser_url(normalize_url(str(arguments.get("url") or target or "")))
            try:
                driver.get(url)
            except Exception as exc:
                # A page-load timeout does not necessarily mean navigation failed. Stop
                # the pending load and let the normal post-observation verifier decide
                # from the browser's actual URL/DOM. Other driver failures remain real
                # failures and are never reported as success.
                if exc.__class__.__name__ != "TimeoutException":
                    raise
                try:
                    driver.execute_script("window.stop()")
                    validate_browser_url(str(driver.current_url or ""))
                except Exception:
                    raise exc
            return {"url": driver.current_url, "title": driver.title}
        if action == "back":
            driver.back(); return self.current_state()
        if action == "forward":
            driver.forward(); return self.current_state()
        if action == "refresh":
            driver.refresh(); return self.current_state()
        if action == "new_tab":
            url = str(arguments.get("url") or "about:blank")
            if url != "about:blank":
                validate_browser_url(normalize_url(url)); url = normalize_url(url)
            driver.switch_to.new_window("tab")
            if url != "about:blank":
                try:
                    driver.get(url)
                except Exception as exc:
                    if exc.__class__.__name__ != "TimeoutException":
                        raise
                    try:
                        driver.execute_script("window.stop()")
                        validate_browser_url(str(driver.current_url or ""))
                    except Exception:
                        raise exc
            return self.current_state()
        if action == "switch_tab":
            handles = list(driver.window_handles)
            if "handle" in arguments:
                handle = str(arguments["handle"])
            else:
                index = int(arguments.get("index", -1))
                handle = handles[index]
            if handle not in handles: raise BrowserTargetNotFound("The requested browser tab is unavailable.")
            driver.switch_to.window(handle); return self.current_state()
        if action == "close_tab":
            if len(driver.window_handles) <= 1:
                raise ComputerUseError("Echo will not close the final controlled browser tab; end the browser session instead.")
            driver.close(); driver.switch_to.window(driver.window_handles[-1]); return self.current_state()
        if action == "wait":
            seconds = min(max(float(arguments.get("seconds", 1)), 0), float(getattr(settings, "ECHO_BROWSER_MAX_WAIT", 20)))
            time.sleep(seconds); return {"waited_seconds": seconds}
        if action == "scroll":
            direction = str(arguments.get("direction") or "down").casefold()
            amount = abs(int(arguments.get("amount", 700) or 700))
            delta = -amount if direction in {"up", "top"} else amount
            driver.execute_script("window.scrollBy({top: arguments[0], left: 0, behavior: 'instant'});", delta)
            return {"direction": direction, "amount": amount, "scroll_y": driver.execute_script("return window.scrollY")}
        if action == "scroll_to":
            destination = str(arguments.get("destination") or target or "").casefold()
            if destination in {"top", "start"}:
                driver.execute_script("window.scrollTo(0,0)"); return {"scroll_y": 0}
            if destination in {"bottom", "end"}:
                driver.execute_script("window.scrollTo(0,document.documentElement.scrollHeight)"); return {"scroll_y": driver.execute_script("return window.scrollY")}
            element, descriptor = self.resolve_element(target or destination, page=page)
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", element)
            return {"target": descriptor, "scroll_y": driver.execute_script("return window.scrollY")}
        if action == "find":
            needle = str(arguments.get("query") or target or "").strip()
            structured = page or self.get_structured_page()
            matches = [item for item in structured.get("elements", []) if self._element_score(item, needle) > 0]
            body_match = needle.casefold() in str(structured.get("visible_text", "")).casefold()
            return {"query": needle, "count": len(matches), "body_match": body_match, "matches": matches[:25]}
        if action in {"get_page", "get_dom", "get_accessibility_tree", "get_screenshot"}:
            if action == "get_accessibility_tree": return self.get_accessibility_tree()
            if action == "get_screenshot": return {"captured": True}
            structured = page or self.get_structured_page()
            if action == "get_dom": return {"elements": structured.get("elements", []), "headings": structured.get("headings", []), "visible_text": structured.get("visible_text", "")}
            return structured
        if action in {"play", "pause", "resume", "seek", "volume", "media_action"}:
            media_action = str(arguments.get("media_action") or action).casefold()
            index = max(0, int(arguments.get("index", 0) or 0))
            media = driver.find_elements("css selector", "video,audio")
            visible = [item for item in media if item.is_displayed()]
            if index >= len(visible): raise BrowserTargetNotFound("No accessible media element was found on the current page.")
            element = visible[index]
            if media_action in {"play", "resume"}:
                result = driver.execute_async_script("const el=arguments[0], done=arguments[arguments.length-1]; Promise.resolve(el.play()).then(()=>done({ok:true})).catch(e=>done({ok:false,error:String(e)}));", element)
                if not result.get("ok"): raise ComputerUseError(f"The media player rejected playback: {result.get('error','unknown error')}")
            elif media_action == "pause": driver.execute_script("arguments[0].pause()", element)
            elif media_action in {"seek", "skip", "rewind"}:
                seconds = float(arguments.get("seconds", 0) or 0)
                if media_action == "rewind" and seconds > 0: seconds = -seconds
                if arguments.get("absolute") is not None: driver.execute_script("arguments[0].currentTime = arguments[1]", element, float(arguments["absolute"]))
                else: driver.execute_script("arguments[0].currentTime = Math.max(0, Math.min(arguments[0].duration || Infinity, arguments[0].currentTime + arguments[1]))", element, seconds)
            elif media_action == "volume":
                volume = min(1, max(0, float(arguments.get("volume", 0.5))))
                driver.execute_script("arguments[0].volume = arguments[1]; arguments[0].muted = false", element, volume)
            return driver.execute_script("return {current_time:arguments[0].currentTime,duration:Number.isFinite(arguments[0].duration)?arguments[0].duration:null,paused:arguments[0].paused,muted:arguments[0].muted,volume:arguments[0].volume,current_src:arguments[0].currentSrc||arguments[0].src||''}", element)

        page = page or self.get_structured_page()
        element, descriptor = self.resolve_element(target, page=page)
        if action == "download_if_permitted":
            href = str(descriptor.get("href") or "")
            if href and href.startswith(("http://", "https://")):
                validate_browser_url(href)
            if not descriptor.get("download") and not bool(arguments.get("permission_confirmed")):
                raise HumanInterventionRequired(
                    "confirmation",
                    "This download is not explicitly marked as a browser download. Confirm the download before Echo continues.",
                )
            directory = self.download_dir()
            before = {item.name: item.stat().st_size for item in directory.iterdir() if item.is_file()}
            element.click()
            deadline = time.monotonic() + min(float(getattr(settings, "ECHO_BROWSER_DOWNLOAD_TIMEOUT", 20)), 60.0)
            completed = None
            while time.monotonic() < deadline:
                time.sleep(0.25)
                for item in directory.iterdir():
                    if not item.is_file() or item.name.endswith((".crdownload", ".part", ".tmp")):
                        continue
                    size = item.stat().st_size
                    if item.name not in before or before.get(item.name) != size:
                        completed = item
                        break
                if completed:
                    break
            if not completed:
                raise ComputerUseError("The download action ran, but Echo could not verify a completed permitted download.")
            return {"target": descriptor, "downloaded": True, "filename": completed.name, "size": completed.stat().st_size}
        if action == "click": element.click()
        elif action == "double_click": ActionChains(driver).double_click(element).perform()
        elif action == "right_click": ActionChains(driver).context_click(element).perform()
        elif action == "hover": ActionChains(driver).move_to_element(element).perform()
        elif action == "focus": driver.execute_script("arguments[0].focus()", element)
        elif action == "type":
            text = str(arguments.get("text", ""))
            if arguments.get("clear", True):
                try: element.clear()
                except Exception: pass
            element.send_keys(text)
            if arguments.get("submit"): element.send_keys(Keys.ENTER)
        elif action == "press_key":
            key_name = str(arguments.get("key") or "ENTER").upper().replace(" ", "_")
            key_value = getattr(Keys, key_name, None)
            if key_value is None: raise ValidationError(f"Unsupported key: {key_name}")
            element.send_keys(key_value)
        elif action == "select":
            selection = str(arguments.get("value") or arguments.get("text") or "")
            selector = Select(element)
            try: selector.select_by_visible_text(selection)
            except Exception: selector.select_by_value(selection)
        elif action == "drag":
            destination, dest_descriptor = self.resolve_element(arguments.get("destination"), page=page)
            ActionChains(driver).drag_and_drop(element, destination).perform()
            descriptor = {"source": descriptor, "destination": dest_descriptor}
        else:
            raise ValidationError(f"Unsupported browser action: {action}")
        return {"target": descriptor, **self.current_state()}


class ComputerEnvironmentRegistry:
    """Registry boundary for computer-use environments.

    Echo ships with the controlled browser environment. Future authorized desktop,
    file, or terminal environments can register their own backend without changing
    the command/orchestration contract or the Tool Manager. Unregistered
    environments are never simulated.
    """

    _providers: dict[str, type] = {"browser.selenium": SeleniumBrowserBackend}

    @classmethod
    def register(cls, name: str, backend_class: type) -> None:
        if not name or not callable(backend_class):
            raise ValueError("A computer-use environment requires a name and backend class.")
        cls._providers[str(name)] = backend_class

    @classmethod
    def create_backend(cls, name: str, session: BrowserSession):
        backend_class = cls._providers.get(name)
        if backend_class is None:
            raise BrowserUnavailable(f"Computer-use environment is not configured: {name}")
        return backend_class(session)

    @classmethod
    def capabilities(cls) -> list[dict[str, Any]]:
        rows = []
        for name, backend_class in sorted(cls._providers.items()):
            probe = getattr(backend_class, "capabilities", None)
            if callable(probe):
                try:
                    details = dict(probe() or {})
                except Exception as exc:
                    details = {"available": False, "reason": str(exc)}
            else:
                details = {"available": True}
            rows.append({"name": name, **details})
        return rows


class BrowserSessionService:
    _backends: dict[str, SeleniumBrowserBackend] = {}
    _locks: dict[str, threading.RLock] = {}
    _guard = threading.RLock()

    @classmethod
    def _owned(cls, user):
        query = BrowserSession.objects.all()
        return query if user.is_staff else query.filter(owner=user)

    @classmethod
    def create(cls, user, *, engine: str | None = None, headless: bool | None = None) -> BrowserSession:
        now = timezone.now()
        engine = str(engine or getattr(settings, "ECHO_BROWSER_ENGINE", "chrome"))[:32]
        headless = bool(getattr(settings, "ECHO_BROWSER_HEADLESS", False) if headless is None else headless)
        return BrowserSession.objects.create(
            owner=user,
            name=f"browser-{now.isoformat()}",
            title="Echo computer-use browser",
            description="Controlled browser session for evidence-backed computer use.",
            status="active",
            engine=engine,
            headless=headless,
            started_at=now,
            last_activity_at=now,
            configuration={"environment": "browser.selenium", "provider": "selenium", "remote": bool(getattr(settings, "ECHO_BROWSER_REMOTE_URL", "")), "security": "public-network-only" if not getattr(settings, "ECHO_BROWSER_ALLOW_PRIVATE_NETWORKS", False) else "private-network-opt-in"},
        )

    @classmethod
    def get(cls, user, session_id) -> BrowserSession:
        try:
            return cls._owned(user).get(pk=session_id)
        except (BrowserSession.DoesNotExist, ValueError, TypeError) as exc:
            raise BrowserTargetNotFound("Browser session was not found.") from exc

    @classmethod
    def current(cls, user, *, create: bool = True) -> BrowserSession | None:
        session = cls._owned(user).filter(status="active").order_by("-last_activity_at", "-created_at").first()
        return session or (cls.create(user) if create else None)

    @classmethod
    def lock(cls, session: BrowserSession) -> threading.RLock:
        key = str(session.pk)
        with cls._guard:
            return cls._locks.setdefault(key, threading.RLock())

    @classmethod
    def backend(cls, session: BrowserSession) -> SeleniumBrowserBackend:
        key = str(session.pk)
        with cls._guard:
            backend = cls._backends.get(key)
            if backend is None:
                environment = str((session.configuration or {}).get("environment") or "browser.selenium")
                backend = ComputerEnvironmentRegistry.create_backend(environment, session)
                cls._backends[key] = backend
            return backend

    @classmethod
    def close(cls, user, session_id) -> BrowserSession:
        session = cls.get(user, session_id)
        backend = cls._backends.pop(str(session.pk), None)
        if backend: backend.close()
        session.status = "completed"
        session.ended_at = timezone.now()
        session.last_activity_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "last_activity_at", "updated_at"])
        return session


class BrowserObservationService:
    @staticmethod
    def _sanitize_ax(tree: dict[str, Any]) -> dict[str, Any]:
        return tree if isinstance(tree, dict) else {"available": False}

    @classmethod
    def observe(cls, user, session: BrowserSession, *, screenshot: bool = True, reason: str = "observe") -> BrowserObservation:
        backend = BrowserSessionService.backend(session)
        with BrowserSessionService.lock(session):
            page = backend.get_structured_page()
            current_url = str(page.get("url") or "")
            if current_url.startswith(("http://", "https://")):
                try:
                    validate_browser_url(current_url)
                except UnsafeURL as exc:
                    try:
                        backend.driver.execute_script("window.stop()")
                    except Exception:
                        pass
                    raise HumanInterventionRequired(
                        "security_boundary",
                        f"Echo stopped because the browser reached a blocked network destination: {exc}",
                    ) from exc
            ax = backend.get_accessibility_tree()
            png = backend.screenshot_png() if screenshot else b""
        sequence = (session.observations.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
        digest_source = json.dumps({"url": page.get("url"), "title": page.get("title"), "elements": page.get("elements"), "media": page.get("media"), "visible_text": page.get("visible_text", "")[:20000]}, sort_keys=True, default=str).encode()
        observation = BrowserObservation(
            owner=user,
            session=session,
            name=f"observation-{sequence}",
            title=page.get("title") or page.get("url") or f"Observation {sequence}",
            description=f"Browser observation captured for {reason}.",
            status="completed",
            sequence=sequence,
            url=str(page.get("url") or "")[:4096],
            page_title=str(page.get("title") or "")[:512],
            visible_text=str(page.get("visible_text") or "")[:60000],
            dom={"elements": page.get("elements", []), "headings": page.get("headings", []), "live_text": page.get("live_text", [])},
            accessibility_tree=cls._sanitize_ax(ax),
            viewport=page.get("viewport") or {},
            media=page.get("media") or [],
            content_hash=hashlib.sha256(digest_source).hexdigest(),
            observed_at=timezone.now(),
            configuration={"reason": reason},
        )
        if png:
            observation.screenshot.save(f"{session.pk}-{sequence}.png", ContentFile(png), save=False)
        observation.save()
        session.current_url = observation.url
        session.current_title = observation.page_title
        try: session.active_tab_handle = BrowserSessionService.backend(session).current_state().get("active_tab_handle", "")[:255]
        except Exception: pass
        session.last_activity_at = timezone.now()
        session.save(update_fields=["current_url", "current_title", "active_tab_handle", "last_activity_at", "updated_at"])
        return observation

    @staticmethod
    def blocker(observation: BrowserObservation) -> dict[str, str] | None:
        text = f"{observation.visible_text}\n{observation.page_title}".casefold()
        elements = list((observation.dom or {}).get("elements") or [])
        if any(token in text for token in ("captcha", "verify you are human", "i'm not a robot", "security check")):
            return {"type": "captcha", "detail": "The page requires human verification. Echo will not bypass CAPTCHA or security checks."}
        if any(item.get("type") == "password" for item in elements):
            return {"type": "login", "detail": "The page requires credentials or a signed-in session. Complete login manually, then resume Echo."}
        if any(token in text for token in ("two-factor authentication", "verification code", "multi-factor authentication", "enter the code we sent")):
            return {"type": "mfa", "detail": "The page requires MFA or a verification code. Complete verification manually, then resume Echo."}
        return None


class VisionTargetResolver:
    """Resolve ambiguous visual targets to existing DOM nodes using screenshot + structure.

    Vision never invents raw coordinates.  It may only select an ``echo_id`` that
    was observed in the current DOM snapshot, keeping execution anchored to live
    browser structure and making the selected target auditable.
    """

    @classmethod
    def resolve(cls, observation: BrowserObservation, target: Any) -> dict[str, str] | None:
        if not observation.screenshot or not settings.AI_PROVIDER_BASE_URL or not settings.AI_PROVIDER_API_KEY:
            return None
        elements = list((observation.dom or {}).get("elements") or [])[:180]
        if not elements:
            return None
        model = getattr(settings, "AI_VISION_MODEL", "") or settings.AI_PROVIDER_MODEL
        if not model:
            return None
        compact = [{k: item.get(k) for k in ("echo_id", "tag", "role", "text", "aria_label", "title", "placeholder", "href", "rect", "style")} for item in elements]
        try:
            with observation.screenshot.open("rb") as handle:
                image_b64 = base64.b64encode(handle.read()).decode("ascii")
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": (
                        "Choose the single current DOM element that best matches the user's visual target. "
                        "Return strict JSON only: {\"echo_id\":\"echo-N\"} or {\"echo_id\":null}. "
                        "You may only choose an echo_id from the supplied elements; never invent coordinates. "
                        f"Target: {target!r}\nElements: {json.dumps(compact, default=str)[:30000]}"
                    )},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }]
            content, _ = OpenAICompatibleProvider().complete(messages, model=model, temperature=0.0, timeout=60)
            match = re.search(r"\{.*\}", str(content), re.S)
            payload = json.loads(match.group(0) if match else str(content))
            echo_id = payload.get("echo_id") if isinstance(payload, dict) else None
            if echo_id and any(item.get("echo_id") == echo_id for item in elements):
                return {"echo_id": str(echo_id)}
        except Exception as exc:
            logger.info("Visual target resolution unavailable: %s", exc)
        return None


class PageUnderstandingService:
    @classmethod
    def answer(cls, user, session: BrowserSession, question: str) -> dict[str, Any]:
        observation = BrowserObservationService.observe(user, session, screenshot=True, reason="page-understanding")
        blocker = BrowserObservationService.blocker(observation)
        structured = {
            "url": observation.url,
            "title": observation.page_title,
            "headings": (observation.dom or {}).get("headings", [])[:80],
            "visible_text": observation.visible_text[:35000],
            "elements": (observation.dom or {}).get("elements", [])[:100],
            "accessibility": (observation.accessibility_tree or {}).get("nodes", [])[:150],
        }
        visual = MediaUnderstandingService._vision_note(observation)
        if settings.AI_PROVIDER_BASE_URL and settings.AI_PROVIDER_API_KEY:
            messages = [
                {"role": "system", "content": "Answer only from the supplied current-page evidence. Prefer DOM/accessibility evidence; use visual notes only when relevant. If evidence is insufficient, say so. Never claim an action occurred."},
                {"role": "user", "content": f"Question: {question}\nCurrent page: {json.dumps(structured, default=str)}\nVisual notes: {visual[:10000]}"},
            ]
            try:
                content, _ = OpenAICompatibleProvider().complete(messages, model=settings.AI_PROVIDER_MODEL or None, temperature=0.1, timeout=60)
            except AIProviderError as exc:
                raise ComputerUseError(f"Page understanding failed: {exc}") from exc
        else:
            if question.casefold().startswith(("summarize", "what does", "read")) and observation.visible_text:
                content = observation.visible_text[:3500]
            else:
                raise ComputerUseError("A configured AI provider is required for visual/current-page questions beyond direct text retrieval.")
        return {"ok": True, "content": str(content).strip(), "observation_id": str(observation.pk), "url": observation.url, "title": observation.page_title, "attention": blocker}


class BrowserSafetyPolicy:
    """Require human approval for consequential browser actions without blocking navigation."""

    SENSITIVE_TERMS = (
        "delete", "remove account", "close account", "erase", "cancel subscription",
        "publish", "post", "send", "submit", "place order", "buy", "purchase",
        "checkout", "pay", "payment", "transfer", "wire", "unsubscribe", "confirm order",
        "accept offer", "sign contract", "authorize", "book now", "place bid",
    )
    SENSITIVE_INPUT_TERMS = (
        "password", "passcode", "card number", "credit card", "cvv", "cvc",
        "security code", "bank account", "routing number", "social security", "ssn",
    )

    @classmethod
    def _descriptor(cls, observation: BrowserObservation, target: Any) -> dict[str, Any]:
        elements = list((observation.dom or {}).get("elements") or [])
        if not target:
            return {}
        if isinstance(target, dict):
            echo_id = str(target.get("echo_id") or "")
            if echo_id:
                return next((item for item in elements if str(item.get("echo_id")) == echo_id), {})
            kind = str(target.get("kind") or "").casefold()
            index = max(0, int(target.get("index", 0) or 0))
            candidates = elements
            if kind in {"button", "menu"}:
                candidates = [item for item in elements if item.get("tag") == "button" or item.get("role") in {"button", "menuitem"}]
            elif kind in {"result", "link", "video", "playlist", "media_link"}:
                candidates = [item for item in elements if item.get("tag") == "a" and item.get("href")]
            if target.get("text"):
                needle = str(target.get("text") or "").casefold()
                candidates = [item for item in candidates if needle in " ".join(str(item.get(k) or "") for k in ("text", "aria_label", "title", "name", "placeholder")).casefold()]
            return candidates[index] if index < len(candidates) else {}
        needle = str(target).casefold().strip()
        if not needle:
            return {}
        return next((item for item in elements if needle in " ".join(str(item.get(k) or "") for k in ("text", "aria_label", "title", "name", "placeholder")).casefold()), {})

    @classmethod
    def require_confirmation(cls, observation: BrowserObservation, action_type: str, arguments: dict[str, Any]) -> str | None:
        if arguments.get("confirmed"):
            return None
        action = action_type.casefold()
        if action not in {"click", "double_click", "type", "press_key", "select", "drag", "download_if_permitted"}:
            return None
        descriptor = cls._descriptor(observation, arguments.get("target"))
        evidence = " ".join(
            str(value or "") for value in (
                descriptor.get("text"), descriptor.get("aria_label"), descriptor.get("title"),
                descriptor.get("name"), descriptor.get("placeholder"), descriptor.get("href"),
                arguments.get("text") if action != "type" else "",
                str(arguments.get("target") or ""),
            )
        ).casefold()
        if any(term in evidence for term in cls.SENSITIVE_TERMS):
            return "This browser action appears consequential or externally visible and requires your confirmation before Echo continues."
        if action == "type":
            input_evidence = " ".join(str(descriptor.get(key) or "") for key in ("type", "name", "placeholder", "aria_label", "title")).casefold()
            if any(term in input_evidence for term in cls.SENSITIVE_INPUT_TERMS) or descriptor.get("type") == "password":
                return "Echo will not enter sensitive credentials or financial information without explicit user control and confirmation."
        if action == "download_if_permitted" and not arguments.get("permission_confirmed"):
            return "This download requires your confirmation before Echo saves the file."
        return None


class BrowserActionService:
    READ_ONLY_ACTIONS = {"get_page", "get_dom", "get_accessibility_tree", "get_screenshot", "find"}

    @classmethod
    def execute(cls, user, session: BrowserSession, action_type: str, arguments: dict[str, Any] | None = None) -> ActionOutcome:
        arguments = dict(arguments or {})
        backend = BrowserSessionService.backend(session)
        with BrowserSessionService.lock(session):
            pre = BrowserObservationService.observe(user, session, screenshot=action_type not in cls.READ_ONLY_ACTIONS, reason=f"before:{action_type}")
            blocker = BrowserObservationService.blocker(pre)
            if blocker and action_type not in cls.READ_ONLY_ACTIONS:
                # A command, model plan, or API payload may never override CAPTCHA/login/MFA blockers.
                # The user must resolve the page state themselves; Echo may continue once the blocker disappears.
                raise HumanInterventionRequired(blocker["type"], blocker["detail"])
            approval_detail = BrowserSafetyPolicy.require_confirmation(pre, action_type, arguments)
            if approval_detail:
                raise HumanInterventionRequired("approval", approval_detail)
            record = BrowserAction.objects.create(
                owner=user,
                session=session,
                name=action_type,
                title=action_type.replace("_", " ").title(),
                description="Echo computer-use action.",
                status="running",
                action_type=action_type,
                target=str(arguments.get("target") or arguments.get("url") or "")[:5000],
                arguments=arguments,
                pre_observation=pre,
                started_at=timezone.now(),
            )
            try:
                page = {"elements": (pre.dom or {}).get("elements", []), "headings": (pre.dom or {}).get("headings", []), "visible_text": pre.visible_text, "media": pre.media, "viewport": pre.viewport}
                raw_target = arguments.get("target")
                if action_type in {"click", "double_click", "right_click", "hover", "focus", "drag"} and isinstance(raw_target, str):
                    visual_terms = ("blue", "red", "green", "yellow", "right", "left", "top", "bottom", "thumbnail", "icon", "that", "this")
                    if any(term in raw_target.casefold() for term in visual_terms):
                        visual_target = VisionTargetResolver.resolve(pre, raw_target)
                        if visual_target:
                            arguments["target"] = visual_target
                            record.arguments = arguments
                            record.target = str(visual_target)[:5000]
                approval_detail = BrowserSafetyPolicy.require_confirmation(pre, action_type, arguments)
                if approval_detail:
                    raise HumanInterventionRequired("approval", approval_detail)
                try:
                    result = backend.perform(action_type, arguments, page=page)
                except BrowserTargetNotFound:
                    visual_target = VisionTargetResolver.resolve(pre, arguments.get("target"))
                    if not visual_target:
                        raise
                    arguments["target"] = visual_target
                    record.arguments = arguments
                    record.target = str(visual_target)[:5000]
                    approval_detail = BrowserSafetyPolicy.require_confirmation(pre, action_type, arguments)
                    if approval_detail:
                        raise HumanInterventionRequired("approval", approval_detail)
                    result = backend.perform(action_type, arguments, page=page)
                post = BrowserObservationService.observe(user, session, screenshot=True, reason=f"after:{action_type}")
                if action_type == "get_screenshot":
                    result = {"captured": True, "observation_id": str(post.pk), "screenshot_url": post.screenshot.url if post.screenshot else None}
                verified = cls.verify(action_type, arguments, result, pre, post)
                record.result = result
                record.post_observation = post
                record.verified = verified
                record.status = "completed" if verified or action_type in cls.READ_ONLY_ACTIONS else "unverified"
                record.completed_at = timezone.now()
                record.save()
                if not verified and action_type not in cls.READ_ONLY_ACTIONS:
                    raise ComputerUseError(f"The {action_type.replace('_',' ')} action ran, but Echo could not verify the requested result.")
                return ActionOutcome(str(record.pk), bool(verified or action_type in cls.READ_ONLY_ACTIONS), result, str(post.pk))
            except Exception as exc:
                record.status = "failed"
                record.error_message = str(exc)
                record.completed_at = timezone.now()
                record.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
                raise

    @staticmethod
    def verify(action: str, arguments: dict[str, Any], result: dict[str, Any], pre: BrowserObservation, post: BrowserObservation) -> bool:
        action = action.casefold()
        if action in BrowserActionService.READ_ONLY_ACTIONS: return True
        if action in {"open_url", "navigate"}:
            requested = normalize_url(str(arguments.get("url") or arguments.get("target") or ""))
            requested_host = (urlparse(requested).hostname or "").removeprefix("www.")
            actual_host = (urlparse(post.url).hostname or "").removeprefix("www.")
            return bool(requested_host and actual_host and (actual_host == requested_host or actual_host.endswith("." + requested_host) or requested_host.endswith("." + actual_host)))
        if action in {"play", "resume", "media_action"} and str(arguments.get("media_action") or action) in {"play", "resume"}:
            return bool(result.get("paused") is False)
        if action == "pause" or (action == "media_action" and arguments.get("media_action") == "pause"):
            return bool(result.get("paused") is True)
        if action == "scroll": return pre.viewport.get("scroll_y") != post.viewport.get("scroll_y") or post.viewport.get("document_height") <= post.viewport.get("height")
        if action == "type":
            expected = str(arguments.get("text") or "")
            return bool(expected and (expected.casefold() in post.visible_text.casefold() or pre.content_hash != post.content_hash))
        if action == "download_if_permitted":
            return bool(result.get("downloaded") and result.get("filename"))
        if action in {"back", "forward", "refresh", "click", "double_click", "right_click", "select", "press_key", "drag", "new_tab", "switch_tab", "close_tab", "scroll_to", "hover", "focus", "wait", "volume", "seek"}:
            return bool(result) and (pre.content_hash != post.content_hash or pre.url != post.url or action in {"hover", "focus", "wait", "volume", "seek", "refresh"})
        return bool(result)


class MediaUnderstandingService:
    @classmethod
    def _vision_from_png(cls, png: bytes, prompt: str) -> str:
        if not png or not settings.AI_PROVIDER_BASE_URL or not settings.AI_PROVIDER_API_KEY:
            return ""
        model = getattr(settings, "AI_VISION_MODEL", "") or settings.AI_PROVIDER_MODEL
        if not model:
            return ""
        try:
            image_b64 = base64.b64encode(png).decode("ascii")
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }]
            content, _ = OpenAICompatibleProvider().complete(messages, model=model, temperature=0.0, timeout=60)
            return str(content).strip()
        except Exception as exc:
            logger.info("Vision analysis unavailable: %s", exc)
            return ""

    @classmethod
    def _vision_note(cls, observation: BrowserObservation) -> str:
        if not observation.screenshot:
            return ""
        try:
            with observation.screenshot.open("rb") as handle:
                png = handle.read()
        except Exception:
            return ""
        return cls._vision_from_png(
            png,
            "Describe only what is visibly supported by this browser screenshot, focusing on the current media/page content. Do not infer unseen events. Be concise.",
        )

    @classmethod
    def _sample_visual_timeline(cls, session: BrowserSession, media_index: int, duration: float | None, *, operation: ComputerUseOperation | None = None) -> list[dict[str, Any]]:
        if not settings.AI_PROVIDER_BASE_URL or not settings.AI_PROVIDER_API_KEY:
            return []
        if not duration or not isinstance(duration, (int, float)) or duration <= 2:
            return []
        max_samples = min(max(int(getattr(settings, "ECHO_MEDIA_MAX_VISUAL_SAMPLES", 6)), 1), 10)
        points = sorted({round(duration * fraction, 2) for fraction in [0.08, 0.24, 0.42, 0.60, 0.78, 0.94][:max_samples] if duration * fraction < duration})
        backend = BrowserSessionService.backend(session)
        driver = backend.driver
        media = [item for item in driver.find_elements("css selector", "video,audio") if item.is_displayed()]
        if media_index >= len(media):
            return []
        element = media[media_index]
        original = driver.execute_script("return {time:arguments[0].currentTime,paused:arguments[0].paused,scrollY:window.scrollY}", element)
        samples: list[dict[str, Any]] = []
        try:
            # Keep the sampled media in the rendered viewport so screenshots are
            # evidence of the media itself rather than an unrelated off-screen page.
            driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'nearest'}); arguments[0].pause()", element)
            time.sleep(0.08)
            for seconds in points:
                if operation:
                    operation.refresh_from_db(fields=["cancel_requested"])
                    if operation.cancel_requested:
                        raise ComputerUseCancelled("Computer-use operation was cancelled by the user.")
                try:
                    driver.execute_async_script(
                        "const el=arguments[0], t=arguments[1], done=arguments[arguments.length-1]; "
                        "let finished=false; const complete=()=>{if(finished)return;finished=true;done(true)}; "
                        "el.addEventListener('seeked',complete,{once:true}); el.currentTime=t; setTimeout(complete,1800);",
                        element, seconds,
                    )
                    time.sleep(0.12)
                    note = cls._vision_from_png(
                        backend.screenshot_png(),
                        f"This is a rendered frame sampled at about {seconds:.1f} seconds from media the user asked Echo to understand. Describe only visible content relevant to understanding the media. Do not infer audio or unseen events.",
                    )
                    if note:
                        samples.append({"time": seconds, "note": note[:5000]})
                except Exception as exc:
                    logger.info("Media frame sample failed at %s seconds: %s", seconds, exc)
        finally:
            try:
                driver.execute_script("arguments[0].currentTime=arguments[1]", element, float((original or {}).get("time", 0) or 0))
                if not bool((original or {}).get("paused", True)):
                    driver.execute_async_script("const el=arguments[0],done=arguments[arguments.length-1];Promise.resolve(el.play()).then(()=>done(true)).catch(()=>done(false));", element)
                driver.execute_script("window.scrollTo(0, arguments[0])", float((original or {}).get("scrollY", 0) or 0))
            except Exception:
                pass
        return samples

    @classmethod
    def _sample_audio_timeline(cls, user, session: BrowserSession, media_index: int, duration: float | None, *, operation: ComputerUseOperation | None = None) -> list[dict[str, Any]]:
        provider_name = str(getattr(settings, "ECHO_MEDIA_STT_PROVIDER", "") or "").strip()
        if not provider_name:
            try:
                from echo.apps.voice.services import VoiceProfileService
                selected = VoiceProfileService.default_for(user).speech_to_text_provider
                provider_name = selected if selected != "browser" else ("configured_http" if getattr(settings, "VOICE_PROVIDER_BASE_URL", "") else "")
            except Exception:
                provider_name = "configured_http" if getattr(settings, "VOICE_PROVIDER_BASE_URL", "") else ""
        if not provider_name:
            return []
        try:
            from echo.apps.voice.providers import VoiceProviderRegistry
            provider = VoiceProviderRegistry.stt(provider_name)
        except Exception as exc:
            logger.info("Media speech provider unavailable: %s", exc)
            return []
        backend = BrowserSessionService.backend(session)
        driver = backend.driver
        media = [item for item in driver.find_elements("css selector", "video,audio") if item.is_displayed()]
        if media_index >= len(media):
            return []
        element = media[media_index]
        try:
            encrypted = bool(driver.execute_script("return Boolean(arguments[0].mediaKeys)", element))
        except Exception:
            encrypted = False
        if encrypted:
            return []
        original = driver.execute_script("return {time:arguments[0].currentTime,paused:arguments[0].paused}", element)
        max_samples = min(max(int(getattr(settings, "ECHO_MEDIA_MAX_AUDIO_SAMPLES", 3)), 1), 5)
        sample_seconds = min(max(float(getattr(settings, "ECHO_MEDIA_AUDIO_SAMPLE_SECONDS", 6)), 2), 8)
        if duration and isinstance(duration, (int, float)) and duration > sample_seconds * 1.5:
            fractions = [0.08, 0.50, 0.88][:max_samples]
            points = [max(0.0, min(float(duration) - sample_seconds - 0.25, float(duration) * fraction)) for fraction in fractions]
        else:
            points = [float((original or {}).get("time", 0) or 0)]
        samples: list[dict[str, Any]] = []
        try:
            for point in points:
                if operation:
                    operation.refresh_from_db(fields=["cancel_requested"])
                    if operation.cancel_requested:
                        raise ComputerUseCancelled("Computer-use operation was cancelled by the user.")
                try:
                    if duration and isinstance(duration, (int, float)):
                        driver.execute_async_script(
                            "const el=arguments[0],t=arguments[1],done=arguments[arguments.length-1];let hit=false;const finish=()=>{if(hit)return;hit=true;done(true)};el.addEventListener('seeked',finish,{once:true});el.currentTime=t;setTimeout(finish,1500);",
                            element, float(point),
                        )
                    captured = backend.capture_media_audio(media_index, seconds=sample_seconds)
                    if not captured.get("ok"):
                        logger.info("Media audio capture unavailable at %s: %s", point, captured.get("reason"))
                        continue
                    audio = base64.b64decode(str(captured.get("audio_base64") or ""), validate=True)
                    result = provider.transcribe(audio, mime_type=str(captured.get("mime_type") or "audio/webm"), language=str(getattr(settings, "LANGUAGE_CODE", "en-US")))
                    text = str(result.text or "").strip()
                    if text:
                        samples.append({"time": round(float(point), 2), "text": text[:12000], "confidence": float(result.confidence or 0), "provider": provider_name})
                except Exception as exc:
                    logger.info("Media audio sample failed at %s seconds: %s", point, exc)
        finally:
            try:
                driver.execute_script("arguments[0].currentTime=arguments[1]", element, float((original or {}).get("time", 0) or 0))
                if bool((original or {}).get("paused", True)):
                    driver.execute_script("arguments[0].pause()", element)
                else:
                    driver.execute_async_script("const el=arguments[0],done=arguments[arguments.length-1];Promise.resolve(el.play()).then(()=>done(true)).catch(()=>done(false));", element)
            except Exception:
                pass
        return samples

    @classmethod
    def analyze_current(cls, user, session: BrowserSession, *, operation: ComputerUseOperation | None = None) -> MediaUnderstanding:
        observation = BrowserObservationService.observe(user, session, screenshot=True, reason="media-analysis")
        media = list(observation.media or [])
        if not media:
            record = MediaUnderstanding.objects.create(
                owner=user, session=session, operation=operation, name="media-analysis", title="Media analysis", status="failed",
                source_url=observation.url, media_metadata={}, transcript="", visual_notes="", summary="",
                evidence=[{"observation_id": str(observation.pk), "type": "page"}], confidence=0,
                processed_at=timezone.now(), configuration={"reason": "no_accessible_media"},
            )
            raise ComputerUseError("Echo could not identify accessible audio or video on the current page.")
        primary = media[0]
        cues = primary.get("captions") or []
        transcript_parts = []
        seen = set()
        for cue in cues:
            text = str(cue.get("text") or "").strip()
            if text and text not in seen:
                seen.add(text); transcript_parts.append(text)
        for text in ((observation.dom or {}).get("live_text") or []):
            clean = str(text or "").strip()
            if clean and clean not in seen:
                seen.add(clean); transcript_parts.append(clean)
        caption_transcript = "\n".join(transcript_parts)[: int(getattr(settings, "ECHO_MEDIA_MAX_TRANSCRIPT_CHARS", 120000))]
        duration = primary.get("duration")
        duration_value = float(duration) if isinstance(duration, (int, float)) else None
        audio_samples = []
        if len(caption_transcript) < 500:
            audio_samples = cls._sample_audio_timeline(user, session, int(primary.get("index", 0) or 0), duration_value, operation=operation)
        audio_transcript = "\n".join(f"~{item['time']:.1f}s: {item['text']}" for item in audio_samples)
        transcript = "\n".join(filter(None, [caption_transcript, audio_transcript]))[: int(getattr(settings, "ECHO_MEDIA_MAX_TRANSCRIPT_CHARS", 120000))]
        visual_note = cls._vision_note(observation)
        visual_samples = []
        if len(transcript) < 500:
            visual_samples = cls._sample_visual_timeline(session, int(primary.get("index", 0) or 0), duration_value, operation=operation)
        if visual_samples:
            sampled_notes = "\n".join(f"~{item['time']:.1f}s: {item['note']}" for item in visual_samples)
            visual_note = "\n".join(filter(None, [visual_note, sampled_notes]))[:30000]
        evidence = [{"observation_id": str(observation.pk), "type": "screenshot_and_dom"}]
        if caption_transcript: evidence.append({"type": "captions", "cue_count": len(cues), "characters": len(caption_transcript), "audio_evidence": "caption_or_accessible_text"})
        if audio_samples: evidence.append({"type": "audio_transcription", "sample_count": len(audio_samples), "seconds_per_sample": float(getattr(settings, "ECHO_MEDIA_AUDIO_SAMPLE_SECONDS", 6)), "provider": audio_samples[0].get("provider")})
        if visual_note: evidence.append({"type": "vision", "observation_id": str(observation.pk), "sample_count": len(visual_samples) or 1, "visual_only": not bool(transcript)})
        if len(transcript) < 80 and not visual_note:
            summary = ""
            confidence = 0.15
            status = "insufficient_evidence"
        elif settings.AI_PROVIDER_BASE_URL and settings.AI_PROVIDER_API_KEY:
            messages = [
                {"role": "system", "content": "Summarize only the supplied media evidence. Distinguish caption/accessibility text, directly transcribed rendered-audio samples, and sampled visual-frame evidence. Never claim Echo heard audio unless audio_transcription evidence is present, and never claim full coverage unless the evidence supports it. State material limitations concisely."},
                {"role": "user", "content": f"Media metadata: {json.dumps(primary, default=str)[:12000]}\n\nAccessible transcript/captions:\n{transcript[:90000]}\n\nVisible-frame notes:\n{visual_note[:10000]}"},
            ]
            summary, _ = OpenAICompatibleProvider().complete(messages, model=settings.AI_PROVIDER_MODEL or None, temperature=0.1, timeout=90)
            confidence = 0.85 if len(transcript) > 500 else 0.55
            status = "completed"
        else:
            summary = (transcript[:3500] if transcript else visual_note[:3500]).strip()
            confidence = 0.55 if transcript else 0.35
            status = "completed"
        record = MediaUnderstanding.objects.create(
            owner=user,
            session=session,
            operation=operation,
            name="media-analysis",
            title=f"Media on {observation.page_title or observation.url}"[:255],
            description="Evidence-backed understanding of accessible media content.",
            status=status,
            source_url=observation.url,
            media_metadata=primary,
            transcript=transcript,
            visual_notes=visual_note,
            summary=str(summary or "")[:50000],
            evidence=evidence,
            confidence=confidence,
            processed_at=timezone.now(),
            configuration={
                "coverage": "multi_modal" if (transcript and visual_samples) else "transcript_or_audio" if transcript else "sampled_visual_frames" if visual_samples else "current_visible_frame" if visual_note else "none",
                "visual_samples": len(visual_samples),
                "audio_samples": len(audio_samples),
                "audio_directly_processed": bool(audio_samples),
                "transcript_source": "captions_and_audio_samples" if caption_transcript and audio_samples else "captions_or_accessible_text" if caption_transcript else "rendered_audio_samples" if audio_samples else "none",
            },
        )
        return record

    @classmethod
    def answer_latest(cls, user, question: str, *, session: BrowserSession | None = None) -> dict[str, Any]:
        records = MediaUnderstanding.objects.filter(owner=user).exclude(status="failed")
        if session is not None:
            records = records.filter(session=session)
        record = records.order_by("-processed_at", "-created_at").first()
        if not record or (not record.transcript and not record.visual_notes and not record.summary):
            return {"ok": False, "content": "I couldn't reliably determine that because I have not processed enough accessible media content yet."}
        evidence = f"Evidence metadata: {json.dumps(record.evidence or {}, default=str)[:30000]}\nSummary: {record.summary}\nTranscript: {record.transcript[:90000]}\nVisual notes: {record.visual_notes[:10000]}"
        if settings.AI_PROVIDER_BASE_URL and settings.AI_PROVIDER_API_KEY:
            messages = [
                {"role": "system", "content": "Answer only from the supplied processed media evidence. Treat captions, direct rendered-audio transcriptions, and sampled visual-frame notes as distinct evidence sources. Do not claim Echo heard audio unless the evidence metadata contains direct audio transcription. If the evidence is insufficient, say so plainly. Do not hallucinate."},
                {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{evidence}"},
            ]
            content, _ = OpenAICompatibleProvider().complete(messages, model=settings.AI_PROVIDER_MODEL or None, temperature=0.1, timeout=60)
        else:
            content = record.summary or record.transcript[:2500] or record.visual_notes[:2500]
        return {"ok": True, "content": str(content), "media_understanding_id": str(record.pk), "source_url": record.source_url, "confidence": float(record.confidence)}


class ComputerUsePlanner:
    """Build short evidence-driven plans without site-specific automation."""

    @staticmethod
    def _ordinal(text: str, default: int = 0) -> int:
        lowered = text.casefold()
        for word, index in _ORDINALS.items():
            if re.search(rf"\b{re.escape(word)}\b", lowered): return index
        number = re.search(r"\b(?:number\s+)?(\d{1,2})\b", lowered)
        return max(0, int(number.group(1)) - 1) if number else default

    @classmethod
    def deterministic(cls, request_text: str) -> list[dict[str, Any]]:
        text = re.sub(r"\s+", " ", request_text.strip())
        lowered = text.casefold()
        steps: list[dict[str, Any]] = []
        open_match = re.search(r"\b(?:open|launch|go to|navigate to|take me to)\s+([^,]+?)(?=\s+(?:and|then)\s+|,|$)", text, re.I)
        if open_match:
            target = open_match.group(1).strip()
            if not any(word in target.casefold() for word in ("first", "second", "third", "result", "video", "playlist", "button", "menu")):
                steps.append({"tool": "browser.open_url", "input": {"url": normalize_url(target)}, "description": f"Open {target}"})
        research_match = re.search(r"\b(?:research|investigate|look\s+up)\s+(.+?)(?=\s+(?:and|then)\s+(?:save|store|add|create|prepare)|$)", text, re.I)
        if research_match:
            query = research_match.group(1).strip().rstrip(".,")
            steps.extend([
                {"tool": "browser.search", "input": {"query": query}, "description": f"Search for {query}"},
                {"tool": "browser.click", "input": {"target": {"kind": "result", "index": 1}}, "description": "Open the first relevant search result"},
                {"tool": "browser.answer_page", "input": {"question": f"Summarize the evidence on this page relevant to: {query}"}, "description": "Analyze the opened source from current page evidence"},
            ])
        site_search = re.search(r"\bsearch\s+(?P<site>[a-z0-9.-]+)\s+for\s+(?P<query>.+?)(?=\s+(?:and|then)\s+(?:open|play|watch|summarize|scroll)|$)", text, re.I)
        site_search_matched = False
        if site_search:
            site = site_search.group("site").strip()
            query = site_search.group("query").strip().rstrip(".,")
            try:
                site_url = normalize_url(site)
            except ValidationError:
                site_url = ""
            if site_url:
                steps.append({"tool": "browser.open_url", "input": {"url": site_url}, "description": f"Open {site}"})
                steps.append({"tool": "browser.search", "input": {"query": query, "fallback": "error"}, "description": f"Search {site} for {query}"})
                site_search_matched = True
        if not site_search_matched:
            search_match = re.search(r"\bsearch(?:\s+(?:google|the web|web|this site|here))?\s+(?:for\s+)?(.+?)(?=\s+(?:and|then)\s+(?:open|play|watch|summarize|scroll)|$)", text, re.I)
            if search_match:
                query = search_match.group(1).strip().rstrip(".,")
                steps.append({"tool": "browser.search", "input": {"query": query}, "description": f"Search for {query}"})
        scroll_until = re.search(r"\bscroll(?:\s+down)?\s+until\s+(?:you\s+)?find\s+(.+)$", text, re.I)
        if scroll_until:
            query = scroll_until.group(1).strip().rstrip(".,")
            steps.append({"tool": "browser.scroll_until", "input": {"query": query, "direction": "down"}, "description": f"Scroll until {query} is found"})
        else:
            for match in re.finditer(r"\bscroll(?:\s+(down|up))?\b", text, re.I):
                steps.append({"tool": "browser.scroll", "input": {"direction": (match.group(1) or "down").casefold()}, "description": f"Scroll {(match.group(1) or 'down').lower()}"})
        item_match = re.search(
            r"\b(?:open|click|select|choose)\s+(?:the\s+)?(?P<ordinal>(?:first|second|third|fourth|fifth|\d+(?:st|nd|rd|th)?)\s+)?(?P<demonstrative>that\s+|this\s+|current\s+)?(?:relevant\s+)?(?P<kind>video|result|playlist|link|button|menu)\b",
            text, re.I,
        )
        if item_match:
            index = cls._ordinal(item_match.group(0))
            kind = item_match.group("kind").casefold()
            visual_qualifiers = ("blue", "red", "green", "yellow", "right", "left", "top", "bottom", "thumbnail", "icon")
            target: Any
            if item_match.group("demonstrative") or any(term in lowered for term in visual_qualifiers):
                # Preserve referential/visual language so the current DOM + screenshot
                # resolver identifies the element from fresh evidence instead of
                # assuming a fixed ordinal or coordinate.
                target = item_match.group(0)
            else:
                target = {"kind": "media_link" if kind in {"video", "playlist"} else "result" if kind in {"result", "link"} else kind, "index": index}
            steps.append({"tool": "browser.click", "input": {"target": target}, "description": f"Open the requested {kind}"})
        else:
            ordinal_one = re.search(r"\b(?:open|click|select|choose)\s+(?:the\s+)?(?P<ordinal>first|second|third|fourth|fifth|\d+(?:st|nd|rd|th)?)\s+one\b", text, re.I)
            if ordinal_one:
                steps.append({"tool": "browser.click", "input": {"target": {"kind": "result", "index": cls._ordinal(ordinal_one.group(0))}}, "description": "Open the requested item from current page evidence"})
            else:
                generic_click = re.search(r"\b(?P<action>click|double\s+click|right\s+click)(?:\s+(?:on|the))?\s+(?P<target>.+?)(?:[.!?]|$)", text, re.I)
                if generic_click:
                    action = generic_click.group("action").casefold().replace(" ", "_")
                    target = generic_click.group("target").strip()
                    steps.append({"tool": f"browser.{action}", "input": {"target": target}, "description": f"{action.replace('_', ' ').title()} {target} using current page evidence"})
        if re.search(r"\b(?:play|resume)(?:\s+(?:it|this|the video|the media))?\b", lowered):
            steps.append({"tool": "browser.media_action", "input": {"media_action": "play"}, "description": "Play the current media"})
        if re.search(r"\bpause(?:\s+(?:it|this|the video|the media))?\b", lowered):
            steps.append({"tool": "browser.media_action", "input": {"media_action": "pause"}, "description": "Pause the current media"})
        skip = re.search(r"\b(?:skip|go)\s+(?:ahead|forward)\s+(\d+)\s+seconds?", lowered)
        if skip: steps.append({"tool": "browser.media_action", "input": {"media_action": "seek", "seconds": int(skip.group(1))}, "description": "Seek forward"})
        rewind = re.search(r"\b(?:go back|rewind)\s+(\d+)\s+seconds?", lowered)
        if rewind: steps.append({"tool": "browser.media_action", "input": {"media_action": "seek", "seconds": -int(rewind.group(1))}, "description": "Seek backward"})
        if any(phrase in lowered for phrase in ("watch and listen", "analyze this video", "process this video", "summarize this video", "summarize the video")):
            steps.append({"tool": "media.analyze", "input": {}, "description": "Process accessible media evidence"})
        if any(phrase in lowered for phrase in ("what is this", "what am i looking at", "what does this page say", "summarize this page", "read this", "what does the chart show", "what is the error")):
            steps.append({"tool": "browser.answer_page", "input": {"question": text}, "description": "Answer from current page evidence"})
        if not scroll_until:
            find_match = re.search(r"\bfind\s+(?:the\s+)?(.+?)(?:[.!?]|$)", text, re.I)
            if find_match and not any(phrase in lowered for phrase in ("find in my knowledge", "find my", "find information in my knowledge")):
                query = find_match.group(1).strip()
                steps.append({"tool": "browser.find", "input": {"query": query}, "description": f"Find {query} on the current page"})
        if not steps and re.fullmatch(r"(?:scroll|scroll down|scroll up)[.!]?", lowered):
            steps.append({"tool": "browser.scroll", "input": {"direction": "up" if "up" in lowered else "down"}, "description": "Scroll the current page"})
        return steps

    @classmethod
    def ai_plan(cls, request_text: str, observation: BrowserObservation | None) -> list[dict[str, Any]]:
        if not settings.AI_PROVIDER_BASE_URL or not settings.AI_PROVIDER_API_KEY:
            return []
        allowed = [definition for definition in ToolExecutor.definitions() if definition.get("availability") and (definition["name"].startswith("browser.") or definition["name"] == "media.analyze") and definition["name"] != "browser.execute_allowed_action"]
        recent_actions = []
        if observation and observation.session_id:
            recent_actions = [
                {
                    "action": item.action_type,
                    "target": item.target[:500],
                    "verified": item.verified,
                    "result": item.result,
                    "status": item.status,
                }
                for item in BrowserAction.objects.filter(session_id=observation.session_id).order_by("-created_at")[:8]
            ]
        context = {
            "url": observation.url if observation else "",
            "title": observation.page_title if observation else "",
            "visible_text": (observation.visible_text[:12000] if observation else ""),
            "elements": ((observation.dom or {}).get("elements", [])[:120] if observation else []),
            "recent_verified_actions": list(reversed(recent_actions)),
        }
        system_prompt = "You are Echo's computer-use planner. Return strict JSON only: {\"steps\":[{\"tool\":\"...\",\"input\":{},\"description\":\"...\"}]}. Use only supplied tools. Prefer DOM/accessibility identifiers. Never propose CAPTCHA/MFA/auth bypass, DRM circumvention, credential theft, or policy evasion. Only include consequential, destructive, financial, or externally visible actions when the user explicitly requested them; the executor will pause for approval when required. Plans are verified by the executor after every action; do not fabricate success."
        user_text = f"Request: {request_text}\nCurrent browser evidence: {json.dumps(context, default=str)}\nAvailable tools: {json.dumps(allowed)}"
        user_content: Any = user_text
        if observation and observation.screenshot and (getattr(settings, "AI_VISION_MODEL", "") or settings.AI_PROVIDER_MODEL):
            try:
                with observation.screenshot.open("rb") as handle:
                    image_b64 = base64.b64encode(handle.read()).decode("ascii")
                user_content = [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ]
            except Exception:
                user_content = user_text
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        try:
            content, _ = OpenAICompatibleProvider().complete(messages, model=settings.AI_PROVIDER_MODEL or None, temperature=0.0, timeout=60)
            match = re.search(r"\{.*\}", str(content), re.S)
            payload = json.loads(match.group(0) if match else str(content))
            steps = payload.get("steps") if isinstance(payload, dict) else []
            allowed_names = {item["name"] for item in allowed}
            clean = []
            for item in steps or []:
                if isinstance(item, dict) and item.get("tool") in allowed_names and isinstance(item.get("input", {}), dict):
                    clean.append({"tool": item["tool"], "input": item.get("input", {}), "description": str(item.get("description") or item["tool"])[:255]})
            return clean[:20]
        except Exception as exc:
            logger.info("Computer-use AI planning failed: %s", exc)
            return []

    @classmethod
    def plan(cls, user, request_text: str, session: BrowserSession) -> list[dict[str, Any]]:
        deterministic = cls.deterministic(request_text)
        if deterministic:
            return deterministic
        observation = None
        try: observation = BrowserObservationService.observe(user, session, screenshot=True, reason="planning")
        except Exception: pass
        return cls.ai_plan(request_text, observation)


class ComputerUseOperationService:
    _local_executor = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("ECHO_LOCAL_BACKGROUND_WORKERS", "2"))), thread_name_prefix="echo-computer-use")

    @staticmethod
    def _final_content(operation: ComputerUseOperation, results: list[dict[str, Any]]) -> str:
        if not results:
            return "The computer-use task finished without a usable result."
        last = results[-1]
        tool = str(last.get("tool") or "")
        output = last.get("output") if isinstance(last.get("output"), dict) else {}
        if tool == "media.analyze":
            return str(output.get("summary") or "Processed the accessible media evidence.")[:6000]
        if tool in {"browser.open_url", "browser.navigate"}:
            title = str(output.get("title") or "").strip()
            url = str(output.get("url") or "").strip()
            return f"{title or url or 'The requested page'} is open."[:6000]
        if tool == "browser.search":
            query = str(output.get("query") or "").strip()
            return (f"Search completed for “{query}”." if query else "Search completed.")[:6000]
        if tool == "browser.scroll":
            direction = str(output.get("direction") or "").strip()
            return (f"Scrolled {direction}." if direction else "The page was scrolled.")[:6000]
        if tool == "browser.scroll_until":
            query = str(output.get("query") or "").strip()
            return (f"Found “{query}”." if output.get("found") else f"I could not find “{query}” on the page after scrolling.")[:6000]
        if tool == "browser.find":
            query = str(output.get("query") or "").strip()
            found = bool(output.get("body_match") or output.get("count"))
            return (f"Found “{query}” on the current page." if found else f"I could not find “{query}” on the current page.")[:6000]
        if tool in {"browser.click", "browser.double_click", "browser.right_click"}:
            return "The requested browser action completed and was verified."
        if tool == "browser.media_action":
            return "Playback was updated and verified."
        if tool == "browser.answer_page":
            return str(output.get("content") or "I could not determine a reliable answer from the current page evidence.")[:6000]
        for key in ("summary", "content", "title", "url"):
            value = str(output.get(key) or "").strip()
            if value:
                return value[:6000]
        return f"Completed: {operation.request_text}"[:6000]

    @classmethod
    def _publish_completion(cls, operation: ComputerUseOperation, *, status_value: str, content: str, attention: dict[str, Any] | None = None) -> None:
        try:
            from echo.apps.notifications.models import Notification
            Notification.objects.create(
                owner=operation.owner,
                name=f"computer_use_{status_value}",
                title=("Computer-use task needs you" if status_value == "waiting_user" else "Computer-use task completed" if status_value == "completed" else "Computer-use task cancelled" if status_value == "cancelled" else "Computer-use task failed"),
                description=content[:4000],
                status="pending" if status_value == "waiting_user" else status_value,
                category="computer_use",
                configuration={"operation_id": str(operation.pk), "attention": attention or {}, "browser_session_id": str(operation.session_id) if operation.session_id else None},
            )
        except Exception:
            logger.exception("Could not publish computer-use notification")
        if operation.conversation_id and status_value in {"completed", "failed", "waiting_user", "cancelled"}:
            try:
                from echo.apps.chat.models import Message
                Message.objects.create(
                    owner=operation.owner, conversation=operation.conversation, name="assistant_message", title=content[:80],
                    status="completed" if status_value == "completed" else status_value, sender="assistant", role="assistant",
                    content=content, rendered_content=content, data={"route": "computer_use.result", "operation_id": str(operation.pk), "execution_status": status_value, "attention": attention or {}},
                )
            except Exception:
                logger.exception("Could not append computer-use result to conversation")
        # Synchronize the durable Agent Manager graph when this operation originated
        # from a delegated Browser Agent task. This is deliberately best-effort so a
        # notification failure can never corrupt a successful browser action.
        try:
            from echo.apps.agent_manager.models import AgentCommunication, AgentTask
            task_id = str((operation.configuration or {}).get("agent_task_id") or "")
            if task_id:
                task = AgentTask.objects.filter(pk=task_id, owner=operation.owner).select_related("agent", "parent_task").first()
                if task:
                    mapped = {"waiting_user": "waiting", "completed": "completed", "failed": "failed", "cancelled": "cancelled"}.get(status_value, status_value)
                    task.status = mapped
                    task.progress = 100 if mapped == "completed" else int(operation.progress or task.progress or 0)
                    task.current_tool = operation.current_tool
                    task.current_operation = operation.current_operation or ("Waiting for user" if mapped == "waiting" else mapped.title())
                    task.error_message = operation.error_message or ""
                    task.completed_at = operation.completed_at if mapped in {"completed", "failed", "cancelled"} else None
                    existing = dict(task.output_payload or {})
                    result_payload = dict(existing.get("result") or {})
                    data = dict(result_payload.get("data") or {})
                    data.update({"operation_id": str(operation.pk), "execution_status": status_value, "operation_result": operation.result, "attention": attention or {}})
                    result_payload.update({"content": content, "route": "computer_use.result", "data": data})
                    task.output_payload = {**existing, "status": mapped, "result": result_payload}
                    task.save(update_fields=["status", "progress", "current_tool", "current_operation", "error_message", "completed_at", "output_payload", "updated_at"])
                    AgentCommunication.objects.create(
                        owner=operation.owner, task=task, sender_agent=task.agent, recipient_agent=None,
                        name="browser_operation_result", title=f"{task.agent.identifier if task.agent else 'browser'} → manager",
                        status="completed", category="orchestration", message_type="result", correlation_id=task.correlation_id,
                        payload={"operation_id": str(operation.pk), "status": status_value, "content": content, "attention": attention or {}, "result": operation.result},
                        processed_at=timezone.now(),
                    )
                    parent = task.parent_task
                    post_artifacts = []
                    post_actions = list((operation.configuration or {}).get("agent_post_actions") or [])
                    if mapped == "completed" and "knowledge.ingest" in post_actions:
                        try:
                            from echo.apps.agent_manager.registry import AgentRegistry
                            pieces = []
                            for step in list((operation.result or {}).get("steps") or []):
                                output = step.get("output") if isinstance(step, dict) and isinstance(step.get("output"), dict) else {}
                                for key in ("summary", "content", "text", "title", "url"):
                                    value = str(output.get(key) or "").strip()
                                    if value and value not in pieces:
                                        pieces.append(value)
                            evidence_content = "\n\n".join(pieces).strip() or str((operation.result or {}).get("content") or "").strip()
                            if evidence_content:
                                knowledge_execution = ToolExecutor.execute_named(
                                    "knowledge.ingest",
                                    operation.owner,
                                    {
                                        "title": f"Research: {operation.request_text}"[:255],
                                        "content": evidence_content[:120000],
                                        "source_type": "computer_use",
                                        "source_id": str(operation.pk),
                                        "category": "research",
                                        "metadata": {"request": operation.request_text, "source_url": operation.session.current_url if operation.session else "", "verified_operation": True},
                                    },
                                    agent="browser",
                                    task_id=str(task.pk),
                                    correlation_id=str(task.correlation_id or ""),
                                )
                                knowledge_data = dict(knowledge_execution.output or {})
                                knowledge_id = str(knowledge_data.get("document_id") or "")
                                knowledge_title = str(knowledge_data.get("title") or f"Research: {operation.request_text}")
                                knowledge_agent = AgentRegistry.ensure_record(operation.owner, "knowledge")
                                knowledge_task = AgentTask.objects.create(
                                    owner=operation.owner, agent=knowledge_agent, parent_task=parent, conversation=operation.conversation,
                                    name="knowledge.ingest", title="Store verified research in knowledge", description=operation.request_text,
                                    request_text=operation.request_text, status="completed", category="orchestrated",
                                    input_payload={"source_operation_id": str(operation.pk)},
                                    output_payload={"status": "completed", "result": {"route": "knowledge.ingest", "data": {"knowledge_id": knowledge_id}}},
                                    progress=100, started_at=timezone.now(), completed_at=timezone.now(), current_operation="Completed",
                                )
                                AgentCommunication.objects.create(
                                    owner=operation.owner, task=knowledge_task, sender_agent=task.agent, recipient_agent=knowledge_agent,
                                    name="knowledge_handoff", title="browser → knowledge", status="completed", category="orchestration",
                                    message_type="handoff", correlation_id=task.correlation_id,
                                    payload={"operation_id": str(operation.pk), "knowledge_id": knowledge_id, "evidence_chars": len(evidence_content)},
                                    processed_at=timezone.now(),
                                )
                                post_artifacts.append({"type": "knowledge", "id": knowledge_id, "title": knowledge_title})
                                data["knowledge_id"] = knowledge_id
                                result_payload["data"] = data
                                task.output_payload = {**task.output_payload, "result": result_payload, "artifacts": [*(task.output_payload.get("artifacts") or []), *post_artifacts]}
                                task.save(update_fields=["output_payload", "updated_at"])
                        except Exception:
                            logger.exception("Could not complete Agent Manager knowledge post-action")
                    if mapped == "completed" and "documents.report" in post_actions:
                        try:
                            from echo.apps.agent_manager.registry import AgentRegistry
                            from echo.apps.documents.models import Document, DocumentContent
                            pieces = []
                            for step in list((operation.result or {}).get("steps") or []):
                                output = step.get("output") if isinstance(step, dict) and isinstance(step.get("output"), dict) else {}
                                for key in ("summary", "content", "text", "title", "url"):
                                    value = str(output.get(key) or "").strip()
                                    if value and value not in pieces:
                                        pieces.append(value)
                            evidence_content = "\n\n".join(pieces).strip() or str((operation.result or {}).get("content") or "").strip()
                            if evidence_content:
                                report = Document.objects.create(
                                    owner=operation.owner,
                                    name=f"report:{operation.pk}",
                                    title=f"Research report: {operation.request_text}"[:255],
                                    description="Report generated from verified computer-use evidence.",
                                    status="completed",
                                    category="agent_report",
                                    configuration={
                                        "source_operation_id": str(operation.pk),
                                        "source_url": operation.session.current_url if operation.session else "",
                                        "verified_operation": True,
                                        "request": operation.request_text,
                                    },
                                )
                                DocumentContent.objects.create(
                                    owner=operation.owner,
                                    name=f"content:{report.pk}",
                                    title=report.title,
                                    description=evidence_content[:120000],
                                    status="completed",
                                    category="agent_report",
                                    configuration={"document_id": str(report.pk), "source_operation_id": str(operation.pk)},
                                )
                                document_agent = AgentRegistry.ensure_record(operation.owner, "documents")
                                report_task = AgentTask.objects.create(
                                    owner=operation.owner, agent=document_agent, parent_task=parent, conversation=operation.conversation,
                                    name="documents.report", title="Create report from verified research", description=operation.request_text,
                                    request_text=operation.request_text, status="completed", category="orchestrated",
                                    input_payload={"source_operation_id": str(operation.pk)},
                                    output_payload={"status": "completed", "result": {"route": "documents.report", "data": {"document_id": str(report.pk)}}},
                                    progress=100, started_at=timezone.now(), completed_at=timezone.now(), current_operation="Completed",
                                )
                                AgentCommunication.objects.create(
                                    owner=operation.owner, task=report_task, sender_agent=task.agent, recipient_agent=document_agent,
                                    name="document_handoff", title="browser → documents", status="completed", category="orchestration",
                                    message_type="handoff", correlation_id=task.correlation_id,
                                    payload={"operation_id": str(operation.pk), "document_id": str(report.pk), "evidence_chars": len(evidence_content)},
                                    processed_at=timezone.now(),
                                )
                                post_artifacts.append({"type": "document", "id": str(report.pk), "title": report.title})
                                data["report_document_id"] = str(report.pk)
                                result_payload["data"] = data
                                task.output_payload = {**task.output_payload, "result": result_payload, "artifacts": [*(task.output_payload.get("artifacts") or []), *post_artifacts]}
                                task.save(update_fields=["output_payload", "updated_at"])
                        except Exception:
                            logger.exception("Could not complete Agent Manager report post-action")
                    if parent:
                        parent.status = mapped
                        parent.progress = task.progress
                        parent.current_tool = task.current_tool
                        parent.current_operation = task.current_operation
                        parent.error_message = task.error_message
                        parent.completed_at = task.completed_at
                        parent.output_payload = {"child_task_id": str(task.pk), "agent": task.agent.identifier if task.agent else "browser", **task.output_payload}
                        parent.save(update_fields=["status", "progress", "current_tool", "current_operation", "error_message", "completed_at", "output_payload", "updated_at"])
        except Exception:
            logger.exception("Could not synchronize computer-use completion with Agent Manager")

    @classmethod
    def create(cls, user, request_text: str, *, conversation=None, session: BrowserSession | None = None) -> ComputerUseOperation:
        session = session or BrowserSessionService.current(user, create=True)
        plan = ComputerUsePlanner.plan(user, request_text, session)
        if not plan:
            raise ComputerUseError("Echo could not form a safe executable browser plan for that request. Configure the AI provider for more complex screen-aware planning.")
        return ComputerUseOperation.objects.create(
            owner=user,
            session=session,
            conversation=conversation,
            name=request_text[:255],
            title=request_text[:255],
            description="General computer-use operation.",
            status="queued",
            request_text=request_text,
            plan=plan,
            current_step=0,
            progress=0,
            cancellable=True,
            configuration={"planner": "deterministic_or_ai", "max_replans": int(getattr(settings, "ECHO_COMPUTER_USE_MAX_REPLANS", 2))},
        )

    @classmethod
    def dispatch(cls, operation: ComputerUseOperation) -> str:
        if getattr(settings, "REDIS_URL", "") and not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", True):
            from .tasks import run_computer_use_operation
            async_result = run_computer_use_operation.delay(str(operation.pk))
            operation.configuration = {**(operation.configuration or {}), "queue": "celery", "queue_task_id": str(async_result.id)}
            operation.save(update_fields=["configuration", "updated_at"])
            return str(async_result.id)
        future = cls._local_executor.submit(cls._run_in_thread, str(operation.pk))
        local_id = f"local-{id(future)}"
        operation.configuration = {**(operation.configuration or {}), "queue": "local_thread", "queue_task_id": local_id}
        operation.save(update_fields=["configuration", "updated_at"])
        return local_id

    @staticmethod
    def _run_in_thread(operation_id: str):
        close_old_connections()
        try:
            ComputerUseOperationService.run(operation_id)
        finally:
            close_old_connections()

    @classmethod
    def cancel(cls, user, operation_id) -> ComputerUseOperation:
        query = ComputerUseOperation.objects.all() if user.is_staff else ComputerUseOperation.objects.filter(owner=user)
        operation = query.filter(pk=operation_id).first()
        if not operation: raise BrowserTargetNotFound("Computer-use operation was not found.")
        if operation.status in {"completed", "failed", "cancelled"}: return operation
        if not operation.cancellable: raise ComputerUseError("This operation is not safely cancellable at its current stage.")
        operation.cancel_requested = True
        operation.status = "cancelling"
        operation.save(update_fields=["cancel_requested", "status", "updated_at"])
        return operation

    @classmethod
    def resume(cls, user, operation_id) -> tuple[ComputerUseOperation, str]:
        query = ComputerUseOperation.objects.all() if user.is_staff else ComputerUseOperation.objects.filter(owner=user)
        operation = query.filter(pk=operation_id).first()
        if not operation:
            raise BrowserTargetNotFound("Computer-use operation was not found.")
        if operation.status not in {"waiting_user", "failed", "cancelled"}:
            raise ComputerUseError("Only an interrupted, failed, or cancelled operation can be resumed.")
        previous_attention = (operation.configuration or {}).get("attention") or {}
        operation.cancel_requested = False
        operation.error_message = ""
        operation.status = "queued"
        resumed_config = {**(operation.configuration or {}), "attention": {}, "resumed_at": timezone.now().isoformat()}
        if previous_attention.get("type") == "approval":
            resumed_config["approval_granted_for_step"] = int(operation.current_step)
        operation.configuration = resumed_config
        operation.save(update_fields=["cancel_requested", "error_message", "status", "configuration", "updated_at"])
        return operation, cls.dispatch(operation)

    @classmethod
    def run(cls, operation_id: str) -> ComputerUseOperation:
        operation = ComputerUseOperation.objects.select_related("owner", "session").get(pk=operation_id)
        user = operation.owner
        if not user or not operation.session:
            operation.status = "failed"; operation.error_message = "Operation owner or browser session is unavailable."; operation.completed_at = timezone.now(); operation.save(); return operation
        # A controlled browser session is a single mutable environment. Serialize browser
        # operations for that session while leaving chat, voice, documents, and other
        # independent Echo work free to run concurrently. Nested browser actions reuse
        # the same re-entrant lock.
        with BrowserSessionService.lock(operation.session):
            return cls._run_locked(operation, user)

    @classmethod
    def _run_locked(cls, operation: ComputerUseOperation, user) -> ComputerUseOperation:
        operation.refresh_from_db()
        if operation.cancel_requested:
            operation.status = "cancelled"
            operation.completed_at = timezone.now()
            operation.current_operation = "Cancelled by user"
            operation.save(update_fields=["status", "completed_at", "current_operation", "updated_at"])
            cls._publish_completion(operation, status_value="cancelled", content="Computer-use task cancelled.")
            return operation
        operation.status = "running"; operation.started_at = operation.started_at or timezone.now(); operation.save(update_fields=["status", "started_at", "updated_at"])
        started_clock = time.monotonic()
        results = list((operation.result or {}).get("steps") or []) if operation.current_step else []
        plan = list(operation.plan or [])[: int(getattr(settings, "ECHO_COMPUTER_USE_MAX_STEPS", 30))]
        replan_count = 0
        index = operation.current_step
        while index < len(plan):
            if time.monotonic() - started_clock > int(getattr(settings, "ECHO_COMPUTER_USE_MAX_RUNTIME_SECONDS", 900)):
                operation.status = "failed"; operation.error_message = "Computer-use operation exceeded the configured runtime limit."; operation.completed_at = timezone.now(); operation.result = {"steps": results}; operation.save()
                cls._publish_completion(operation, status_value="failed", content=operation.error_message)
                return operation
            operation.refresh_from_db(fields=["cancel_requested", "status"])
            if operation.cancel_requested:
                operation.status = "cancelled"; operation.completed_at = timezone.now(); operation.current_operation = "Cancelled by user"; operation.result = {"steps": results}; operation.save(); cls._publish_completion(operation, status_value="cancelled", content="Computer-use task cancelled."); return operation
            step = plan[index]
            tool_name = str(step.get("tool") or "")
            payload = dict(step.get("input") or {})
            # Confirmation is execution state, never planner-controlled input.
            # A model-generated plan cannot self-approve a consequential action.
            payload.pop("confirmed", None)
            payload.pop("permission_confirmed", None)
            if int((operation.configuration or {}).get("approval_granted_for_step", -1)) == index:
                payload["confirmed"] = True
                if tool_name == "browser.download_if_permitted":
                    payload["permission_confirmed"] = True
            operation.current_step = index
            operation.current_tool = tool_name
            operation.current_operation = str(step.get("description") or tool_name)[:255]
            operation.progress = min(99, int(index / max(len(plan), 1) * 100))
            operation.save(update_fields=["current_step", "current_tool", "current_operation", "progress", "updated_at"])
            try:
                execution = ToolExecutor.execute_named(tool_name, user, {**payload, "browser_session_id": str(operation.session_id), "operation_id": str(operation.pk)}, agent="browser", task_id=str(operation.pk))
                results.append({"step": index, "tool": tool_name, "execution_id": execution.execution_id, "output": execution.output})
                index += 1
                operation.current_step = index
                operation.progress = min(99, int(index / max(len(plan), 1) * 100))
                operation.result = {"steps": results}
                config = dict(operation.configuration or {})
                config.pop("approval_granted_for_step", None)
                operation.configuration = config
                operation.save(update_fields=["current_step", "progress", "result", "configuration", "updated_at"])
            except ToolExecutionError as exc:
                cause = exc.__cause__
                if isinstance(cause, ComputerUseCancelled):
                    operation.status = "cancelled"
                    operation.cancel_requested = True
                    operation.current_operation = "Cancelled by user"
                    operation.error_message = ""
                    operation.completed_at = timezone.now()
                    operation.result = {"steps": results}
                    operation.save()
                    cls._publish_completion(operation, status_value="cancelled", content="Computer-use task cancelled.")
                    return operation
                if isinstance(cause, HumanInterventionRequired):
                    operation.status = "waiting_user"
                    operation.current_operation = cause.detail[:255]
                    operation.error_message = cause.detail
                    operation.configuration = {**(operation.configuration or {}), "attention": {"type": cause.reason, "detail": cause.detail}}
                    operation.result = {"steps": results}
                    operation.save()
                    cls._publish_completion(operation, status_value="waiting_user", content=cause.detail, attention={"type": cause.reason, "detail": cause.detail})
                    return operation
                if replan_count < int((operation.configuration or {}).get("max_replans", 2)):
                    replan_count += 1
                    try:
                        observation = BrowserObservationService.observe(user, operation.session, screenshot=True, reason="replan")
                        replanned = ComputerUsePlanner.ai_plan(operation.request_text, observation)
                    except Exception:
                        replanned = []
                    if replanned:
                        plan = replanned
                        operation.plan = plan
                        index = 0
                        operation.current_step = 0
                        operation.configuration = {**(operation.configuration or {}), "replan_count": replan_count, "last_error": str(exc)}
                        operation.save(update_fields=["plan", "current_step", "configuration", "updated_at"])
                        continue
                operation.status = "failed"; operation.error_message = str(exc); operation.completed_at = timezone.now(); operation.result = {"steps": results}; operation.save(); cls._publish_completion(operation, status_value="failed", content=operation.error_message); return operation
            except Exception as exc:
                operation.status = "failed"; operation.error_message = str(exc); operation.completed_at = timezone.now(); operation.result = {"steps": results}; operation.save(); cls._publish_completion(operation, status_value="failed", content=operation.error_message); return operation
        operation.status = "completed"; operation.progress = 100; operation.completed_at = timezone.now(); operation.current_operation = "Completed"; operation.result = {"steps": results, "content": cls._final_content(operation, results)}; operation.save(); cls._publish_completion(operation, status_value="completed", content=operation.result["content"]); return operation


class ComputerUseCommandRouter:
    """Shared text/voice command entry point for browser computer use."""

    MEDIA_QUESTION_PHRASES = ("what was this video about", "what was the video about", "what did the speaker say", "what happened near the end", "main points", "summarize this video", "summarize the video")
    MEDIA_REFERENTIAL_PHRASES = ("what examples", "what did they", "what did he", "what did she", "what was the main", "what were the", "near the end", "in the video", "in this video", "the speaker", "the presenter")
    LOCAL_ENVIRONMENT_RE = re.compile(r"\b(?:downloads?|documents?|desktop)\s+folder\b|\b(?:file explorer|finder|terminal|command prompt|powershell|desktop app)\b", re.I)

    @classmethod
    def _is_browser_command(cls, prompt: str) -> bool:
        lowered = prompt.casefold().strip()
        patterns = (
            r"\b(?:open|launch|go to|navigate to|take me to)\b",
            r"\bscroll(?:\s+down|\s+up)?\b",
            r"\b(?:click|double click|right click|select|hover|press|type)\b",
            r"\b(?:play|pause|resume|skip ahead|go back \d+ seconds?)\b",
            r"\bsearch(?: google| the web| this site| here)?\s+(?:for\s+)?",
            r"\b(?:research|investigate|look up)\b",
            r"\b(?:watch and listen|process this video|analyze this video)\b",
            r"\b(?:what is this|what am i looking at|what does this page say|summarize this page|read this|find the .+|what does the chart show|what is the error)\b",
        )
        return any(re.search(pattern, lowered) for pattern in patterns)

    @classmethod
    def handle(cls, user, prompt: str, *, conversation=None, source: str = "text") -> dict[str, Any] | None:
        lowered = prompt.casefold().strip()
        current_session = BrowserSessionService.current(user, create=False)
        explicit_media_question = any(phrase in lowered for phrase in cls.MEDIA_QUESTION_PHRASES) and not any(verb in lowered for verb in ("watch", "process", "analyze"))
        contextual_media_question = bool(
            current_session
            and MediaUnderstanding.objects.filter(owner=user, session=current_session).exclude(status="failed").exists()
            and any(phrase in lowered for phrase in cls.MEDIA_REFERENTIAL_PHRASES)
        )
        if explicit_media_question or contextual_media_question:
            answer = MediaUnderstandingService.answer_latest(user, prompt, session=current_session if contextual_media_question else None)
            return {"content": answer["content"], "route": "media.answer", "status": "completed" if answer.get("ok") else "failed", "data": answer}
        if cls.LOCAL_ENVIRONMENT_RE.search(prompt):
            environments = [item["name"] for item in ComputerEnvironmentRegistry.capabilities()]
            if not any(name.startswith("desktop.") or name.startswith("files.") or name.startswith("terminal.") for name in environments):
                return {
                    "content": "That request needs a local desktop/files environment, and this Echo deployment currently has only the controlled browser environment configured.",
                    "route": "computer.environment_unavailable", "status": "waiting",
                    "data": {"configured_environments": environments},
                }
        if not cls._is_browser_command(prompt): return None
        session = current_session or BrowserSessionService.current(user, create=True)
        try:
            # Browser I/O is always dispatched as a durable operation. This keeps the
            # Django request, Voice loop, and unrelated Echo work responsive even when
            # browser startup, navigation, media processing, or page waits are slow.
            operation = ComputerUseOperationService.create(user, prompt, conversation=conversation, session=session)
            queue_id = ComputerUseOperationService.dispatch(operation)
        except (ToolExecutionError, ComputerUseError, UnsafeURL, ValidationError, PermissionDenied) as exc:
            cause = exc.__cause__ if isinstance(exc, ToolExecutionError) else exc
            if isinstance(cause, HumanInterventionRequired):
                return {"content": cause.detail, "route": "browser.waiting_user", "status": "waiting", "data": {"attention": {"type": cause.reason, "detail": cause.detail}, "browser_session_id": str(session.pk)}}
            return {"content": f"I couldn't start that browser action: {exc}", "route": "browser.error", "status": "failed", "data": {"browser_session_id": str(session.pk), "error": str(exc)}}
        return {"content": "I started that computer-use task.", "route": "computer_use.start", "status": "completed", "data": {"operation_id": str(operation.pk), "browser_session_id": str(session.pk), "queue_task_id": queue_id, "execution_status": operation.status}}


def _session_from_payload(context: ToolContext, payload: dict[str, Any]) -> BrowserSession:
    session_id = payload.get("browser_session_id")
    return BrowserSessionService.get(context.user, session_id) if session_id else BrowserSessionService.current(context.user, create=True)


def _operation_from_context(context: ToolContext, payload: dict[str, Any]) -> ComputerUseOperation | None:
    operation_id = payload.get("operation_id")
    if not operation_id:
        return None
    return ComputerUseOperation.objects.filter(pk=operation_id, owner=context.user).first()


def _raise_if_cancelled(context: ToolContext, payload: dict[str, Any]) -> None:
    operation = _operation_from_context(context, payload)
    if operation and operation.cancel_requested:
        raise ComputerUseCancelled("Computer-use operation was cancelled by the user.")


def _browser_wait(payload: dict[str, Any], context: ToolContext):
    session = _session_from_payload(context, payload)
    seconds = min(max(float(payload.get("seconds", 1) or 1), 0), float(getattr(settings, "ECHO_BROWSER_MAX_WAIT", 20)))
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _raise_if_cancelled(context, payload)
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))
    return {"ok": True, "waited_seconds": seconds, "browser_session_id": str(session.pk)}


def _browser_tool(action: str):
    def handler(payload: dict[str, Any], context: ToolContext):
        session = _session_from_payload(context, payload)
        outcome = BrowserActionService.execute(context.user, session, action, payload)
        return {"ok": outcome.verified, "action_id": outcome.action_id, "observation_id": outcome.observation_id, **outcome.result, "browser_session_id": str(session.pk)}
    return handler


def _browser_search(payload: dict[str, Any], context: ToolContext):
    session = _session_from_payload(context, payload)
    query = str(payload.get("query") or "").strip()
    if not query: raise ValidationError("query is required")
    observation = BrowserObservationService.observe(context.user, session, screenshot=False, reason="search-target")
    backend = BrowserSessionService.backend(session)
    elements = (observation.dom or {}).get("elements", [])
    search_candidates = [item for item in elements if item.get("role") == "searchbox" or item.get("type") == "search" or "search" in f"{item.get('name','')} {item.get('placeholder','')} {item.get('aria_label','')}".casefold()]
    if search_candidates:
        target = {"echo_id": search_candidates[0].get("echo_id")}
        outcome = BrowserActionService.execute(context.user, session, "type", {"target": target, "text": query, "clear": True, "submit": True})
    elif str(payload.get("fallback") or "web").casefold() == "error":
        raise BrowserTargetNotFound("I could not identify a search control on the requested website.")
    else:
        # This fallback is used only by the explicit web-search capability. Unknown
        # OPEN/navigation intents never arrive here.
        outcome = BrowserActionService.execute(context.user, session, "open_url", {"url": f"https://www.google.com/search?q={quote_plus(query)}"})
    return {"ok": outcome.verified, "action_id": outcome.action_id, "observation_id": outcome.observation_id, "query": query, **outcome.result, "browser_session_id": str(session.pk)}


def _browser_scroll_until(payload: dict[str, Any], context: ToolContext):
    session = _session_from_payload(context, payload)
    query = str(payload.get("query") or "").strip()
    if not query:
        raise ValidationError("query is required")
    direction = str(payload.get("direction") or "down").casefold()
    max_scrolls = min(max(int(payload.get("max_scrolls", 12) or 12), 1), 40)
    for index in range(max_scrolls + 1):
        _raise_if_cancelled(context, payload)
        observation = BrowserObservationService.observe(context.user, session, screenshot=index in {0, max_scrolls}, reason="scroll-until")
        backend = BrowserSessionService.backend(session)
        found = backend.perform("find", {"query": query}, page={"elements": (observation.dom or {}).get("elements", []), "visible_text": observation.visible_text})
        if found.get("body_match") or found.get("count"):
            return {"ok": True, "found": True, "query": query, "scrolls": index, "matches": found.get("matches", [])[:10], "observation_id": str(observation.pk), "browser_session_id": str(session.pk)}
        if index >= max_scrolls:
            break
        BrowserActionService.execute(context.user, session, "scroll", {"direction": direction, "amount": int(payload.get("amount", 700) or 700)})
    return {"ok": False, "found": False, "query": query, "scrolls": max_scrolls, "browser_session_id": str(session.pk)}


def _browser_answer_page(payload: dict[str, Any], context: ToolContext):
    session = _session_from_payload(context, payload)
    question = str(payload.get("question") or "What is on this page?").strip()
    return PageUnderstandingService.answer(context.user, session, question)


def _browser_execute_allowed(payload: dict[str, Any], context: ToolContext):
    action = str(payload.get("action") or "").strip().casefold()
    requested_input = payload.get("input") or {}
    if not isinstance(requested_input, dict):
        raise ValidationError("input must be an object")
    tool_name = f"browser.{action}"
    if tool_name in {"browser.execute_allowed_action", "browser.download_if_permitted"}:
        raise ValidationError("That action is not available through browser.execute_allowed_action.")
    try:
        definition = ToolExecutor.definition(tool_name)
    except ValidationError as exc:
        raise ValidationError("That action is not available through browser.execute_allowed_action.") from exc
    if definition.category != "browser":
        raise ValidationError("That action is not a browser capability.")

    session = _session_from_payload(context, payload)
    action_input = dict(requested_input)
    # This meta-tool cannot be used by a planner to smuggle approval flags.
    action_input.pop("confirmed", None)
    action_input.pop("permission_confirmed", None)
    action_input["browser_session_id"] = str(session.pk)
    nested = ToolExecutor.execute_named(
        tool_name,
        context.user,
        action_input,
        agent=context.agent or "browser",
        task_id=context.task_id,
        correlation_id=context.correlation_id,
    )
    result = nested.output if isinstance(nested.output, dict) else {"value": nested.output}
    return {**result, "delegated_tool": tool_name, "delegated_execution_id": nested.execution_id, "browser_session_id": str(session.pk)}


def _media_analyze(payload: dict[str, Any], context: ToolContext):
    session = _session_from_payload(context, payload)
    operation = _operation_from_context(context, payload)
    _raise_if_cancelled(context, payload)
    record = MediaUnderstandingService.analyze_current(context.user, session, operation=operation)
    return {"ok": record.status == "completed", "status": record.status, "media_understanding_id": str(record.pk), "summary": record.summary, "confidence": float(record.confidence), "source_url": record.source_url, "evidence": record.evidence}


def _browser_runtime_available() -> bool:
    """Cheap capability probe used for registry discovery.

    Starting a real browser is intentionally deferred to execution so registry
    discovery has no external side effects. The action handler still performs
    the definitive environment check and returns a structured failure if the
    local/remote browser cannot be started.
    """

    return bool(SeleniumBrowserBackend.capabilities().get("available"))


def register_computer_use_tools() -> None:
    descriptions = {
        "open_url": "Open a public URL in Echo's controlled browser and verify the resulting location.",
        "navigate": "Navigate the current controlled browser tab to a public URL.",
        "back": "Go back in browser history.", "forward": "Go forward in browser history.", "refresh": "Refresh the current page.",
        "click": "Click an element resolved from DOM/accessibility evidence.", "double_click": "Double-click an element resolved from current page evidence.", "right_click": "Open an element context menu.",
        "type": "Type text into a resolved input control.", "press_key": "Press a keyboard key on a resolved element.",
        "scroll": "Scroll the current page generically.", "scroll_to": "Scroll to the top, bottom, or a resolved element.",
        "find": "Find current-page elements or visible text without changing page state.", "select": "Select an option in a resolved select element.",
        "hover": "Hover over a resolved element.", "drag": "Drag one resolved element to another.", "focus": "Focus a resolved element.",
        "switch_tab": "Switch the controlled browser to another open tab.", "close_tab": "Close the active controlled browser tab when another tab remains.", "new_tab": "Open a new controlled browser tab.",
        "get_page": "Return structured current-page evidence.", "get_dom": "Return visible DOM interaction metadata.", "get_accessibility_tree": "Return the browser accessibility tree where supported.", "get_screenshot": "Capture the current viewport screenshot.", "wait": "Wait briefly inside a computer-use plan.",
        "media_action": "Control an accessible HTML audio/video element generically.",
        "download_if_permitted": "Download a user-requested resource only when the browser exposes a permitted download and verify the completed file.",
    }
    target_schema = {}
    schemas = {
        "open_url": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string", "format": "uri"}}, "additionalProperties": True},
        "navigate": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string", "format": "uri"}}, "additionalProperties": True},
        "back": {"type": "object", "additionalProperties": True},
        "forward": {"type": "object", "additionalProperties": True},
        "refresh": {"type": "object", "additionalProperties": True},
        "click": {"type": "object", "required": ["target"], "properties": {"target": target_schema}, "additionalProperties": True},
        "double_click": {"type": "object", "required": ["target"], "properties": {"target": target_schema}, "additionalProperties": True},
        "right_click": {"type": "object", "required": ["target"], "properties": {"target": target_schema, "confirmed": {"type": "boolean"}}, "additionalProperties": True},
        "type": {"type": "object", "required": ["target", "text"], "properties": {"target": target_schema, "text": {"type": "string"}, "clear": {"type": "boolean"}, "submit": {"type": "boolean"}, "confirmed": {"type": "boolean"}}, "additionalProperties": True},
        "press_key": {"type": "object", "required": ["target", "key"], "properties": {"target": target_schema, "key": {"type": "string", "minLength": 1}}, "additionalProperties": True},
        "scroll": {"type": "object", "properties": {"direction": {"enum": ["up", "down"]}, "amount": {"type": "integer", "minimum": 1}}, "additionalProperties": True},
        "scroll_to": {"type": "object", "properties": {"destination": {"type": "string"}, "target": target_schema}, "additionalProperties": True},
        "find": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string", "minLength": 1}}, "additionalProperties": True},
        "select": {"type": "object", "required": ["target"], "properties": {"target": target_schema, "value": {"type": "string"}, "text": {"type": "string"}}, "additionalProperties": True},
        "hover": {"type": "object", "required": ["target"], "properties": {"target": target_schema}, "additionalProperties": True},
        "drag": {"type": "object", "required": ["target", "destination"], "properties": {"target": target_schema, "destination": target_schema, "confirmed": {"type": "boolean"}}, "additionalProperties": True},
        "focus": {"type": "object", "required": ["target"], "properties": {"target": target_schema}, "additionalProperties": True},
        "switch_tab": {"type": "object", "properties": {"handle": {"type": "string"}, "index": {"type": "integer"}}, "additionalProperties": True},
        "close_tab": {"type": "object", "additionalProperties": True},
        "new_tab": {"type": "object", "properties": {"url": {"type": "string"}}, "additionalProperties": True},
        "get_page": {"type": "object", "additionalProperties": True},
        "get_dom": {"type": "object", "additionalProperties": True},
        "get_accessibility_tree": {"type": "object", "additionalProperties": True},
        "get_screenshot": {"type": "object", "additionalProperties": True},
        "download_if_permitted": {"type": "object", "required": ["target"], "properties": {"target": target_schema, "permission_confirmed": {"type": "boolean"}}, "additionalProperties": True},
    }
    actions = ["open_url","navigate","back","forward","refresh","click","double_click","right_click","type","press_key","scroll","scroll_to","find","select","hover","drag","focus","switch_tab","close_tab","new_tab","get_page","get_dom","get_accessibility_tree","get_screenshot","download_if_permitted"]
    for action in actions:
        sensitive = action in {"type", "right_click", "drag", "download_if_permitted"}
        ToolExecutor.register(
            f"browser.{action}", _browser_tool(action), description=descriptions[action], category="browser",
            input_schema=schemas.get(action, {"type": "object", "additionalProperties": True}), output_schema={"type": "object"},
            permissions=("tools.execute",), availability=_browser_runtime_available, execution_mode="interactive", timeout=int(getattr(settings, "ECHO_BROWSER_MAX_WAIT", 20)) + 10,
            risk_level="medium" if sensitive else "low", confirmation="required" if sensitive else "none",
            cancellable=action in {"download_if_permitted"}, agent_access=("browser", "planner", "chat", "workflow"),
        )
    ToolExecutor.register("browser.wait", _browser_wait, description=descriptions["wait"], category="browser", input_schema={"type": "object", "properties": {"seconds": {"type": "number", "minimum": 0}}, "additionalProperties": True}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=_browser_runtime_available, execution_mode="interactive", timeout=30, risk_level="low", cancellable=True, agent_access=("browser", "planner", "chat", "workflow"))
    ToolExecutor.register("browser.search", _browser_search, description="Search using a visible current-page search control when available, otherwise use a public web search.", category="browser", input_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}, "additionalProperties": True}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=_browser_runtime_available, execution_mode="interactive", timeout=45, risk_level="low", agent_access=("browser", "planner", "chat", "workflow"))
    ToolExecutor.register("browser.media_action", _browser_tool("media_action"), description=descriptions["media_action"], category="browser", input_schema={"type": "object", "required": ["media_action"], "properties": {"media_action": {"enum": ["play", "pause", "resume", "seek", "volume"]}}, "additionalProperties": True}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=_browser_runtime_available, execution_mode="interactive", timeout=30, risk_level="low", agent_access=("browser", "planner", "chat", "workflow"))
    ToolExecutor.register("browser.scroll_until", _browser_scroll_until, description="Observe, scroll, observe, and stop when current-page evidence contains the requested target.", category="browser", input_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "direction": {"enum": ["up", "down"]}, "max_scrolls": {"type": "integer"}}, "additionalProperties": True}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=_browser_runtime_available, execution_mode="background", timeout=120, risk_level="low", cancellable=True, agent_access=("browser", "planner", "chat", "workflow"))
    ToolExecutor.register("browser.answer_page", _browser_answer_page, description="Answer a question from the current DOM, accessibility tree, visible text, and screenshot evidence.", category="browser", input_schema={"type": "object", "required": ["question"], "properties": {"question": {"type": "string"}}, "additionalProperties": True}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=_browser_runtime_available, execution_mode="interactive", timeout=60, risk_level="low", agent_access=("browser", "planner", "chat", "workflow"))
    ToolExecutor.register("browser.execute_allowed_action", _browser_execute_allowed, description="Execute one explicitly allowed generic browser action through the same verified action service.", category="browser", input_schema={"type": "object", "required": ["action", "input"], "properties": {"action": {"type": "string"}, "input": {"type": "object"}}, "additionalProperties": True}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=_browser_runtime_available, execution_mode="interactive", timeout=60, risk_level="medium", agent_access=("browser", "planner", "chat", "workflow"))
    ToolExecutor.register("media.analyze", _media_analyze, description="Build evidence-backed understanding from accessible captions/transcripts and current visual browser evidence without bypassing DRM or access controls.", category="media", input_schema={"type": "object", "additionalProperties": True}, output_schema={"type": "object"}, permissions=("tools.execute",), availability=_browser_runtime_available, execution_mode="background", timeout=900, risk_level="low", cancellable=True, agent_access=("browser", "planner", "chat", "workflow"))
