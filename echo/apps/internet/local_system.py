from __future__ import annotations

import configparser
import os
import platform
import re
import shlex
import shutil
import subprocess
import time
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError


class LocalSystemError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApplicationDescriptor:
    identifier: str
    name: str
    executable: str
    arguments: tuple[str, ...] = ()
    source: str = ""
    desktop_file: str = ""
    categories: tuple[str, ...] = ()

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["arguments"] = list(self.arguments)
        data["categories"] = list(self.categories)
        return data


@dataclass(frozen=True)
class SystemLocation:
    identifier: str
    name: str
    target: str
    kind: str = "path"  # path | uri | shell

    def public(self) -> dict[str, Any]:
        return asdict(self)


class DesktopWindowService:
    """Cross-platform window discovery/focus without arbitrary shell execution."""

    @staticmethod
    def _run(args: list[str], *, timeout: float = 3.0) -> subprocess.CompletedProcess:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)

    @classmethod
    def list_windows(cls) -> list[dict[str, Any]]:
        system = platform.system()
        if system == "Linux" and shutil.which("wmctrl"):
            result = cls._run(["wmctrl", "-lx"])
            rows = []
            for line in result.stdout.splitlines():
                parts = line.split(None, 4)
                if len(parts) < 5:
                    continue
                rows.append({"id": parts[0], "desktop": parts[1], "host": parts[2], "class": parts[3], "title": parts[4]})
            return rows
        if system == "Darwin" and shutil.which("osascript"):
            script = 'tell application "System Events" to get name of every application process whose background only is false'
            result = cls._run(["osascript", "-e", script])
            return [{"id": name.strip(), "title": name.strip(), "class": name.strip()} for name in result.stdout.split(",") if name.strip()]
        try:
            import pygetwindow as gw
            rows = []
            for index, window in enumerate(gw.getAllWindows()):
                title = str(getattr(window, "title", "") or "").strip()
                if not title:
                    continue
                rows.append({
                    "id": str(index), "title": title,
                    "left": int(getattr(window, "left", 0) or 0), "top": int(getattr(window, "top", 0) or 0),
                    "width": int(getattr(window, "width", 0) or 0), "height": int(getattr(window, "height", 0) or 0),
                })
            return rows
        except Exception:
            return []

    @classmethod
    def active_window(cls) -> dict[str, Any]:
        system = platform.system()
        if system == "Linux" and shutil.which("xdotool"):
            identifier = cls._run(["xdotool", "getactivewindow"]).stdout.strip()
            if identifier:
                title = cls._run(["xdotool", "getwindowname", identifier]).stdout.strip()
                return {"available": True, "id": identifier, "title": title}
        if system == "Darwin" and shutil.which("osascript"):
            script = 'tell application "System Events" to get name of first application process whose frontmost is true'
            name = cls._run(["osascript", "-e", script]).stdout.strip()
            if name:
                return {"available": True, "id": name, "title": name, "class": name}
        try:
            import pygetwindow as gw
            window = gw.getActiveWindow()
            if window:
                return {
                    "available": True, "title": str(getattr(window, "title", "") or "")[:500],
                    "left": int(getattr(window, "left", 0) or 0), "top": int(getattr(window, "top", 0) or 0),
                    "width": int(getattr(window, "width", 0) or 0), "height": int(getattr(window, "height", 0) or 0),
                }
        except Exception as exc:
            return {"available": False, "reason": str(exc)[:300]}
        return {"available": False, "reason": "No supported active-window provider is available."}

    @classmethod
    def focus(cls, target: str) -> dict[str, Any]:
        needle = str(target or "").strip().casefold()
        if not needle:
            raise ValidationError("A window name is required.")
        candidates = [item for item in cls.list_windows() if needle in f"{item.get('title','')} {item.get('class','')}".casefold()]
        if not candidates:
            raise LocalSystemError(f"No open window matched {target!r}.")
        window = candidates[0]
        system = platform.system()
        if system == "Linux" and shutil.which("wmctrl") and window.get("id"):
            result = cls._run(["wmctrl", "-ia", str(window["id"])])
            if result.returncode != 0:
                raise LocalSystemError(result.stderr.strip() or "The window manager could not focus that window.")
        elif system == "Darwin" and shutil.which("osascript"):
            app = re.sub(r'[^A-Za-z0-9 ._\-]', '', str(window.get("class") or window.get("title") or ""))[:120]
            result = cls._run(["osascript", "-e", f'tell application "{app}" to activate'])
            if result.returncode != 0:
                raise LocalSystemError(result.stderr.strip() or "macOS could not activate that application.")
        else:
            try:
                import pygetwindow as gw
                matches = gw.getWindowsWithTitle(str(window.get("title") or ""))
                if not matches:
                    raise LocalSystemError("The selected window disappeared before it could be focused.")
                matches[0].activate()
            except LocalSystemError:
                raise
            except Exception as exc:
                raise LocalSystemError(f"Window focus is unavailable: {exc}") from exc
        time.sleep(0.2)
        active = cls.active_window()
        verified = needle in str(active.get("title") or active.get("class") or "").casefold()
        return {"success": verified, "verified": verified, "window": window, "active_window": active}

    @classmethod
    def control(cls, action: str, target: str = "") -> dict[str, Any]:
        """Apply a window-manager action to an existing visible window and verify it.

        Closing a window can lose unsaved work and is therefore exposed as a
        confirmation-required Tool Manager capability. This service only receives
        an already-authorized request and never kills arbitrary processes.
        """
        action = str(action or "").strip().casefold()
        if action not in {"close", "minimize", "maximize", "restore"}:
            raise ValidationError("Unsupported window action.")
        if target:
            needle = str(target).strip().casefold()
            windows = [row for row in cls.list_windows() if needle in f"{row.get('title','')} {row.get('class','')}".casefold()]
            if not windows:
                raise LocalSystemError(f"No open window matched {target!r}.")
            window = windows[0]
        else:
            active = cls.active_window()
            if not active.get("available"):
                raise LocalSystemError("No active window could be identified.")
            window = active
        system = platform.system()
        identifier = str(window.get("id") or "")
        title = str(window.get("title") or "")
        if system == "Linux" and shutil.which("wmctrl") and identifier:
            if action == "close":
                result = cls._run(["wmctrl", "-ic", identifier])
            elif action == "maximize":
                result = cls._run(["wmctrl", "-ir", identifier, "-b", "add,maximized_vert,maximized_horz"])
            elif action == "restore":
                result = cls._run(["wmctrl", "-ir", identifier, "-b", "remove,maximized_vert,maximized_horz"])
            elif shutil.which("xdotool"):
                result = cls._run(["xdotool", "windowminimize", identifier])
            else:
                raise LocalSystemError("Minimize requires xdotool on this Linux host.")
            if result.returncode != 0:
                raise LocalSystemError(result.stderr.strip() or f"The window manager could not {action} that window.")
        elif system == "Darwin" and shutil.which("osascript"):
            app = re.sub(r'[^A-Za-z0-9 ._\-]', '', str(window.get("class") or title))[:120]
            if action == "close":
                script = f'tell application "System Events" to tell process "{app}" to click button 1 of front window'
            elif action == "minimize":
                script = f'tell application "System Events" to tell process "{app}" to set value of attribute "AXMinimized" of front window to true'
            elif action == "restore":
                script = f'tell application "System Events" to tell process "{app}" to set value of attribute "AXMinimized" of front window to false'
            else:
                script = f'tell application "System Events" to tell process "{app}" to perform action "AXZoom" of front window'
            result = cls._run(["osascript", "-e", script])
            if result.returncode != 0:
                raise LocalSystemError(result.stderr.strip() or f"macOS could not {action} that window.")
        else:
            try:
                import pygetwindow as gw
                candidates = gw.getWindowsWithTitle(title) if title else []
                if not candidates:
                    raise LocalSystemError("The selected window disappeared before it could be controlled.")
                selected = candidates[0]
                {"close": selected.close, "minimize": selected.minimize, "maximize": selected.maximize, "restore": selected.restore}[action]()
            except LocalSystemError:
                raise
            except Exception as exc:
                raise LocalSystemError(f"Window {action} is unavailable: {exc}") from exc
        time.sleep(0.25)
        windows_after = cls.list_windows()
        active_after = cls.active_window()
        if action == "close":
            signature = f"{title} {window.get('class','')}".casefold().strip()
            verified = not any(signature and signature in f"{row.get('title','')} {row.get('class','')}".casefold() for row in windows_after)
        elif action == "minimize":
            verified = not (title and title.casefold() in str(active_after.get("title") or "").casefold())
        else:
            verified = bool(active_after.get("available"))
        return {"success": verified, "verified": verified, "action": action, "window": window, "active_window": active_after}

    @classmethod
    def capabilities(cls) -> dict[str, Any]:
        windows = cls.list_windows()
        active = cls.active_window()
        return {"available": bool(windows or active.get("available")), "active_window": active, "window_count": len(windows)}


class ApplicationDiscoveryService:
    """Discover installed GUI applications from OS metadata, with PATH fallback.

    The registry is generated from the host machine rather than being a fixed list.
    A small cross-platform alias map only resolves common product naming differences
    (for example, "VS Code" -> ``code``) when native metadata is incomplete.
    """

    _cache: tuple[float, list[ApplicationDescriptor]] | None = None
    CACHE_SECONDS = 60
    COMMON_EXECUTABLE_ALIASES = {
        "firefox": ("firefox",),
        "google chrome": ("google-chrome", "google-chrome-stable", "chrome"),
        "chrome": ("google-chrome", "google-chrome-stable", "chrome", "chromium", "chromium-browser"),
        "chromium": ("chromium", "chromium-browser"),
        "visual studio code": ("code", "code-insiders"),
        "vs code": ("code", "code-insiders"),
        "vscode": ("code", "code-insiders"),
        "terminal": ("x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "kitty", "alacritty"),
        "file manager": ("nautilus", "dolphin", "thunar", "nemo", "pcmanfm", "explorer"),
    }

    @staticmethod
    def normalize(value: str) -> str:
        value = re.sub(r"\b(?:the|app|application)\b", " ", str(value or "").casefold())
        return re.sub(r"[^a-z0-9]+", " ", value).strip()

    @classmethod
    def _linux_desktop_entries(cls) -> list[ApplicationDescriptor]:
        locations = [Path.home() / ".local/share/applications", Path("/usr/local/share/applications"), Path("/usr/share/applications")]
        rows: dict[str, ApplicationDescriptor] = {}
        field_code = re.compile(r"%[fFuUdDnNickvm]")
        for directory in locations:
            if not directory.is_dir():
                continue
            for path in directory.glob("*.desktop"):
                try:
                    parser = configparser.ConfigParser(interpolation=None, strict=False)
                    parser.read(path, encoding="utf-8")
                    section = parser["Desktop Entry"]
                    if section.get("Type", "Application") != "Application" or section.getboolean("Hidden", fallback=False) or section.getboolean("NoDisplay", fallback=False):
                        continue
                    name = section.get("Name", "").strip()
                    exec_line = field_code.sub("", section.get("Exec", "")).strip()
                    if not name or not exec_line:
                        continue
                    args = shlex.split(exec_line)
                    if not args:
                        continue
                    executable = shutil.which(args[0]) or args[0]
                    identifier = cls.normalize(name) or path.stem.casefold()
                    rows.setdefault(identifier, ApplicationDescriptor(
                        identifier=identifier, name=name, executable=executable, arguments=tuple(args[1:]),
                        source="desktop_file", desktop_file=str(path),
                        categories=tuple(item for item in section.get("Categories", "").split(";") if item),
                    ))
                except Exception:
                    continue
        return list(rows.values())

    @classmethod
    def _mac_apps(cls) -> list[ApplicationDescriptor]:
        rows = []
        for root in (Path("/Applications"), Path.home() / "Applications"):
            if not root.is_dir():
                continue
            for path in root.glob("*.app"):
                name = path.stem
                rows.append(ApplicationDescriptor(cls.normalize(name), name, "/usr/bin/open", ("-a", name), "application_bundle", str(path)))
        return rows

    @classmethod
    def _windows_apps(cls) -> list[ApplicationDescriptor]:
        rows = []
        roots = [
            Path(os.getenv("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.getenv("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        ]
        for root in roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*.lnk"):
                name = path.stem
                rows.append(ApplicationDescriptor(cls.normalize(name), name, str(path), (), "start_menu", str(path)))
        return rows

    @classmethod
    def discover(cls, *, force: bool = False) -> list[ApplicationDescriptor]:
        now = time.monotonic()
        if cls._cache and not force and now - cls._cache[0] < cls.CACHE_SECONDS:
            return list(cls._cache[1])
        system = platform.system()
        if system == "Linux":
            rows = cls._linux_desktop_entries()
        elif system == "Darwin":
            rows = cls._mac_apps()
        elif system == "Windows":
            rows = cls._windows_apps()
        else:
            rows = []
        cls._cache = (now, rows)
        return list(rows)

    @classmethod
    def _default_browser_descriptor(cls) -> ApplicationDescriptor | None:
        system = platform.system()
        if system == "Linux" and shutil.which("xdg-settings"):
            try:
                result = subprocess.run(["xdg-settings", "get", "default-web-browser"], capture_output=True, text=True, timeout=2, check=False)
                desktop_id = result.stdout.strip()
                if desktop_id:
                    for item in cls.discover():
                        if Path(item.desktop_file).name == desktop_id:
                            return ApplicationDescriptor("default-browser", item.name, item.executable, item.arguments, item.source, item.desktop_file, item.categories)
            except Exception:
                pass
        # Fall back to the platform browser resolver when the concrete executable is
        # not safely discoverable from application metadata. Availability checks keep
        # this from being advertised on headless Linux servers.
        if system in {"Linux", "Darwin", "Windows"}:
            return ApplicationDescriptor("default-browser", "Default Browser", "", (), "default_browser")
        return None

    @classmethod
    def _alias_descriptor(cls, query: str) -> ApplicationDescriptor | None:
        normalized = cls.normalize(query)
        names = cls.COMMON_EXECUTABLE_ALIASES.get(normalized, ())
        for executable_name in names:
            executable = shutil.which(executable_name)
            if executable:
                return ApplicationDescriptor(normalized, query.strip().title(), executable, (), "path_alias")
        return None

    @classmethod
    def find(cls, query: str) -> ApplicationDescriptor | None:
        needle = cls.normalize(query)
        if not needle:
            return None
        if needle in {"browser", "web browser", "default browser"}:
            return cls._default_browser_descriptor()
        rows = cls.discover()
        exact = [row for row in rows if cls.normalize(row.name) == needle or row.identifier == needle]
        if exact:
            return exact[0]
        starts = [row for row in rows if cls.normalize(row.name).startswith(needle) or needle.startswith(cls.normalize(row.name))]
        if len(starts) == 1:
            return starts[0]
        contains = [row for row in rows if needle in cls.normalize(row.name)]
        if len(contains) == 1:
            return contains[0]
        direct = shutil.which(query.strip()) or shutil.which(needle.replace(" ", "-"))
        if direct:
            return ApplicationDescriptor(needle, query.strip(), direct, (), "path")
        return cls._alias_descriptor(query)

    @classmethod
    def recognizes_application_name(cls, query: str) -> bool:
        normalized = cls.normalize(query)
        return cls.find(query) is not None or normalized in cls.COMMON_EXECUTABLE_ALIASES or normalized in {"browser", "web browser", "default browser"}

    @classmethod
    def list_public(cls, *, limit: int = 250) -> list[dict[str, Any]]:
        return [item.public() for item in sorted(cls.discover(), key=lambda row: row.name.casefold())[: max(1, min(limit, 500))]]


class ProcessInspector:
    @staticmethod
    def executable_running(executable: str) -> bool:
        name = Path(executable).name.casefold()
        if platform.system() == "Linux" and Path("/proc").is_dir():
            for child in Path("/proc").iterdir():
                if not child.name.isdigit():
                    continue
                try:
                    raw = (child / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", errors="ignore").casefold()
                    if name and name in raw:
                        return True
                except Exception:
                    continue
        return False


class ApplicationLauncherService:
    @classmethod
    def launch(cls, requested: str) -> dict[str, Any]:
        app = ApplicationDiscoveryService.find(requested)
        if not app:
            raise LocalSystemError(f"No installed application matched {requested!r}.")
        before = DesktopWindowService.active_window()
        system = platform.system()
        try:
            if app.source == "default_browser":
                opened = bool(webbrowser.open_new("about:blank"))
                if not opened:
                    raise LocalSystemError("The operating system did not accept the default-browser launch request.")
                process = None
            elif system == "Windows" and app.source == "start_menu":
                os.startfile(app.executable)  # type: ignore[attr-defined]
                process = None
            else:
                process = subprocess.Popen([app.executable, *app.arguments], close_fds=(system != "Windows"), start_new_session=(system != "Windows"))
        except OSError as exc:
            raise LocalSystemError(f"Could not launch {app.name}: {exc}") from exc
        time.sleep(float(getattr(settings, "ECHO_APPLICATION_VERIFY_DELAY", 0.8)))
        after = DesktopWindowService.active_window()
        process_alive = bool(process and process.poll() is None)
        process_found = ProcessInspector.executable_running(app.executable)
        name_tokens = [token for token in ApplicationDiscoveryService.normalize(app.name).split() if len(token) >= 3]
        active_text = f"{after.get('title','')} {after.get('class','')}".casefold()
        window_match = bool(name_tokens and any(token in active_text for token in name_tokens))
        browser_tokens = ("firefox", "chrome", "chromium", "safari", "edge", "browser")
        default_browser_match = bool(
            app.source == "default_browser" and after.get("available") and before != after
            and any(token in active_text for token in browser_tokens)
        )
        verified = bool(process_alive or process_found or window_match or default_browser_match)
        return {
            "success": verified, "verified": verified, "application": app.public(),
            "pid": int(process.pid) if process else None, "running": bool(process_alive or process_found),
            "active_window": after, "verification": "verified" if verified else "launch_sent_but_not_verified",
        }

    @classmethod
    def status(cls, requested: str) -> dict[str, Any]:
        app = ApplicationDiscoveryService.find(requested)
        if not app:
            raise LocalSystemError(f"No installed application matched {requested!r}.")
        running = ProcessInspector.executable_running(app.executable) if app.executable else False
        needle = ApplicationDiscoveryService.normalize(app.name)
        windows = [row for row in DesktopWindowService.list_windows() if any(token in f"{row.get('title','')} {row.get('class','')}".casefold() for token in needle.split() if len(token) >= 3)]
        return {"success": True, "application": app.public(), "running": bool(running or windows), "windows": windows[:20]}

    @classmethod
    def is_available(cls) -> bool:
        system = platform.system()
        if system == "Linux" and not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
            return False
        return system in {"Linux", "Darwin", "Windows"}


class SystemLocationResolver:
    ALIASES = {
        "downloads": "downloads", "download": "downloads", "downloads folder": "downloads",
        "documents": "documents", "document": "documents", "documents folder": "documents",
        "desktop": "desktop", "desktop folder": "desktop",
        "home": "home", "home folder": "home", "home directory": "home", "file manager": "home", "files": "home",
        "pictures": "pictures", "photos": "pictures", "pictures folder": "pictures",
        "videos": "videos", "movies": "videos", "videos folder": "videos",
        "music": "music", "music folder": "music",
        "trash": "trash", "trash bin": "trash", "recycle bin": "trash", "recycling bin": "trash",
        "file system": "filesystem", "filesystem": "filesystem", "computer": "filesystem",
        "echo project": "echo_project", "echo project folder": "echo_project", "project folder": "echo_project", "project directory": "echo_project",
    }

    @classmethod
    def normalize(cls, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9/_.~ -]+", " ", str(value or "").casefold())).strip()

    @classmethod
    def recognizes(cls, requested: str) -> bool:
        value = cls.normalize(requested)
        return value in cls.ALIASES or value.startswith(("~/", "/")) or bool(re.match(r"^[a-z]:[\\/]", value, re.I))

    @classmethod
    def resolve(cls, requested: str) -> SystemLocation:
        raw = str(requested or "").strip()
        value = cls.normalize(raw)
        alias = cls.ALIASES.get(value)
        home = Path.home().resolve()
        if alias == "trash":
            system = platform.system()
            if system == "Windows":
                return SystemLocation("trash", "Trash Bin", "shell:RecycleBinFolder", "shell")
            if system == "Linux" and shutil.which("gio"):
                return SystemLocation("trash", "Trash", "trash:///", "uri")
            path = (home / (".Trash" if system == "Darwin" else ".local/share/Trash/files")).resolve()
            return SystemLocation("trash", "Trash", str(path))
        named = {
            "downloads": home / "Downloads", "documents": home / "Documents", "desktop": home / "Desktop",
            "home": home, "pictures": home / "Pictures", "videos": home / "Videos", "music": home / "Music",
            "filesystem": Path(home.anchor or "/"), "echo_project": Path(settings.BASE_DIR).resolve(),
        }
        if alias in named:
            path = Path(named[alias]).resolve()
            if not path.exists():
                raise LocalSystemError(f"{path.name or path} was not found on this computer.")
            return SystemLocation(alias, "File System" if alias == "filesystem" else ("Echo Project" if alias == "echo_project" else path.name or "Home"), str(path))
        # Explicit paths are owner-safe by default: home and the Echo installation are
        # the only roots accepted without a stronger file-system permission layer.
        candidate = Path(os.path.expanduser(raw)).resolve()
        allowed_roots = [home, Path(settings.BASE_DIR).resolve()]
        if not any(candidate == root or root in candidate.parents for root in allowed_roots):
            raise ValidationError("That path is outside Echo's allowed local roots.")
        if not candidate.exists():
            raise LocalSystemError("The requested local path does not exist.")
        return SystemLocation("path", candidate.name or str(candidate), str(candidate))

    @staticmethod
    def _launch(location: SystemLocation):
        system = platform.system()
        if system == "Windows":
            if location.kind == "shell":
                return subprocess.Popen(["explorer.exe", location.target])
            os.startfile(location.target)  # type: ignore[attr-defined]
            return None
        if system == "Darwin":
            return subprocess.Popen(["open", location.target], close_fds=True)
        if location.kind == "uri" and shutil.which("gio"):
            return subprocess.Popen(["gio", "open", location.target], close_fds=True)
        opener = shutil.which("xdg-open") or shutil.which("gio")
        if not opener:
            raise LocalSystemError("No desktop file opener is available on this Linux host.")
        args = [opener, location.target] if Path(opener).name == "xdg-open" else [opener, "open", location.target]
        return subprocess.Popen(args, close_fds=True)

    @classmethod
    def open(cls, requested: str) -> dict[str, Any]:
        location = cls.resolve(requested)
        before = DesktopWindowService.active_window()
        try:
            process = cls._launch(location)
        except OSError as exc:
            raise LocalSystemError(f"Could not open {location.name}: {exc}") from exc
        time.sleep(float(getattr(settings, "ECHO_APPLICATION_VERIFY_DELAY", 0.8)))
        after = DesktopWindowService.active_window()
        process_alive = bool(process and process.poll() is None)
        changed = bool(after.get("available") and before != after)
        active_text = f"{after.get('title','')} {after.get('class','')}".casefold()
        visible_name = location.name.casefold() in active_text
        file_manager_tokens = ("files", "file manager", "nautilus", "dolphin", "thunar", "nemo", "pcmanfm", "explorer", "finder")
        file_manager_evidence = bool(changed and any(token in active_text for token in file_manager_tokens))
        verified = bool(process_alive or visible_name or file_manager_evidence)
        return {
            "success": verified, "verified": verified, "location": location.public(),
            "pid": int(process.pid) if process else None, "active_window": after,
            "verification": "verified" if verified else "open_sent_but_not_verified",
        }

    @classmethod
    def is_available(cls) -> bool:
        system = platform.system()
        if system == "Linux":
            return bool((os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")) and (shutil.which("xdg-open") or shutil.which("gio")))
        return system in {"Darwin", "Windows"}
