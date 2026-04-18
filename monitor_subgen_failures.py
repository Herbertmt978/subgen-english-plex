#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import smtplib
import ssl
import subprocess
import sys
import time
from email.message import EmailMessage
from pathlib import Path


TRANSCRIBE_START_RE = re.compile(r"WORKER START : \[TRANSCRIBE\s*\] (?P<name>.+?) \| Jobs:")
PROCESSING_ERROR_RE = re.compile(r"Error processing file (?P<path>/media/.+)$")
ENGLISH_MISMATCH_RE = re.compile(
    r"ENGLISH_AUDIO_MISMATCH \| (?P<path>.+?) \| detected=(?P<detected>[^|]+) \| audio=(?P<audio>.+)$"
)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def env_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def utc_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Monitor:
    def __init__(self, args):
        self.container = args.container
        self.media_root = Path(args.media_root).resolve()
        self.state_dir = Path(args.state_dir).resolve()
        self.auto_delete = args.auto_delete_failed_files
        self.smtp_host = args.smtp_host
        self.smtp_port = args.smtp_port
        self.smtp_username = args.smtp_username
        self.smtp_password = args.smtp_password
        self.smtp_from = args.smtp_from
        self.smtp_to = [item.strip() for item in args.smtp_to.split(",") if item.strip()]
        self.smtp_use_tls = args.smtp_use_tls
        self.reconnect_delay_seconds = args.reconnect_delay_seconds
        self.summary_path = self.state_dir / "subgen_failed_files.txt"
        self.events_path = self.state_dir / "subgen_failed_events.log"
        self.state_path = self.state_dir / "subgen_failed_state.json"
        self.heartbeat_path = self.state_dir / "subgen_failure_monitor_heartbeat.txt"
        self.processing_errors = {}
        self.crash_candidates = {}
        self.notifications = {}
        self.last_transcribe_start = None

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.load_state()

    def load_state(self) -> None:
        if not self.state_path.exists():
            return

        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return

        self.processing_errors = {
            item["host_path"].lower(): item
            for item in state.get("processing_errors", [])
            if item.get("host_path")
        }
        self.crash_candidates = {
            item["display_name"].lower(): item
            for item in state.get("crash_candidates", [])
            if item.get("display_name")
        }
        self.notifications = {
            item["host_path"].lower(): item
            for item in state.get("notifications", [])
            if item.get("host_path")
        }

    def save_state(self) -> None:
        state = {
            "updated_utc": utc_stamp(),
            "container_name": self.container,
            "media_root": str(self.media_root),
            "processing_errors": sorted(self.processing_errors.values(), key=lambda item: item["host_path"]),
            "crash_candidates": sorted(self.crash_candidates.values(), key=lambda item: item["display_name"]),
            "notifications": sorted(self.notifications.values(), key=lambda item: item["host_path"]),
        }
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def append_event(self, kind: str, message: str) -> None:
        line = f"{utc_stamp()} [{kind}] {message}\n"
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        self.heartbeat_path.write_text(f"{utc_stamp()} {kind}\n", encoding="utf-8")

    def write_summary(self) -> None:
        lines = [
            f"Updated UTC: {utc_stamp()}",
            f"Container: {self.container}",
            f"Media root: {self.media_root}",
            "",
            f"Auto delete failed files: {self.auto_delete}",
            "",
            "Processing errors:",
        ]

        if not self.processing_errors:
            lines.append("  none")
        else:
            for item in sorted(self.processing_errors.values(), key=lambda value: value["host_path"]):
                lines.append(f"  {item['host_path']}")
                lines.append(f"    container: {item['container_path']}")
                lines.append(f"    first_seen_utc: {item['first_seen_utc']}")
                lines.append(f"    last_seen_utc: {item['last_seen_utc']}")
                lines.append(f"    count: {item['count']}")
                if item.get("delete_status"):
                    lines.append(f"    delete_status: {item['delete_status']}")
                    lines.append(f"    deleted_utc: {item.get('deleted_utc', '')}")
                    lines.append(f"    delete_message: {item.get('delete_message', '')}")

        lines.extend(["", "Crash candidates before SIGSEGV:"])
        if not self.crash_candidates:
            lines.append("  none")
        else:
            for item in sorted(self.crash_candidates.values(), key=lambda value: value["display_name"]):
                lines.append(f"  {item['display_name']}")
                if item.get("host_path"):
                    lines.append(f"    host_path: {item['host_path']}")
                lines.append(f"    first_seen_utc: {item['first_seen_utc']}")
                lines.append(f"    last_seen_utc: {item['last_seen_utc']}")
                lines.append(f"    count: {item['count']}")
                if item.get("delete_status"):
                    lines.append(f"    delete_status: {item['delete_status']}")
                    lines.append(f"    deleted_utc: {item.get('deleted_utc', '')}")
                    lines.append(f"    delete_message: {item.get('delete_message', '')}")

        lines.extend(["", "English mismatch notifications:"])
        if not self.notifications:
            lines.append("  none")
        else:
            for item in sorted(self.notifications.values(), key=lambda value: value["host_path"]):
                lines.append(f"  {item['host_path']}")
                lines.append(f"    detected_language: {item['detected_language']}")
                lines.append(f"    english_audio: {item['english_audio']}")
                lines.append(f"    first_seen_utc: {item['first_seen_utc']}")
                lines.append(f"    last_seen_utc: {item['last_seen_utc']}")
                lines.append(f"    email_status: {item.get('email_status', 'not_sent')}")
                if item.get("email_message"):
                    lines.append(f"    email_message: {item['email_message']}")

        lines.extend(
            [
                "",
                "Notes:",
                "  Processing errors are exact file paths reported by Subgen logs.",
                "  Crash candidates are the last TRANSCRIBE jobs seen before a SIGSEGV.",
                "  English mismatch notifications are emitted when Whisper detects non-English audio but file metadata still shows an English audio track.",
            ]
        )
        self.summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.save_state()

    def convert_container_path_to_host_path(self, container_path: str) -> str:
        if not container_path or not container_path.startswith("/media/"):
            return container_path

        relative_path = container_path[len("/media/") :]
        host_path = (self.media_root / relative_path).resolve()
        media_root_text = str(self.media_root)
        host_text = str(host_path)
        if host_text != media_root_text and not host_text.startswith(media_root_text + os.sep):
            raise ValueError(f"Refusing path outside media root: {host_path}")
        return host_text

    def try_delete_path(self, host_path: str, target: dict, missing_kind: str, deleted_kind: str, failed_kind: str) -> None:
        if not self.auto_delete:
            return

        now = utc_stamp()
        path_obj = Path(host_path)
        try:
            if not path_obj.exists():
                target["delete_status"] = "missing"
                target["delete_message"] = "Path not found at delete time."
                target["deleted_utc"] = now
                self.append_event(missing_kind, f"{host_path} | missing")
                return

            if path_obj.is_dir():
                shutil.rmtree(path_obj)
            else:
                path_obj.unlink()

            target["delete_status"] = "deleted"
            target["delete_message"] = "Removed by monitor."
            target["deleted_utc"] = now
            self.append_event(deleted_kind, host_path)
        except Exception as exc:
            target["delete_status"] = "failed"
            target["delete_message"] = str(exc)
            target["deleted_utc"] = now
            self.append_event(failed_kind, f"{host_path} | {exc}")

    def resolve_crash_candidate_host_path(self, display_name: str):
        for root, _, files in os.walk(self.media_root):
            if display_name in files:
                return str((Path(root) / display_name).resolve())
        return None

    def record_processing_error(self, container_path: str) -> None:
        host_path = self.convert_container_path_to_host_path(container_path)
        key = host_path.lower()
        now = utc_stamp()

        if key not in self.processing_errors:
            self.processing_errors[key] = {
                "host_path": host_path,
                "container_path": container_path,
                "first_seen_utc": now,
                "last_seen_utc": now,
                "count": 1,
                "delete_status": None,
                "deleted_utc": None,
                "delete_message": None,
            }
        else:
            self.processing_errors[key]["last_seen_utc"] = now
            self.processing_errors[key]["count"] += 1

        self.append_event("PROCESSING_ERROR", host_path)
        self.try_delete_path(
            host_path,
            self.processing_errors[key],
            missing_kind="FILE_DELETE_SKIPPED",
            deleted_kind="FILE_DELETED",
            failed_kind="FILE_DELETE_FAILED",
        )
        self.write_summary()

    def record_crash_candidate(self, display_name: str) -> None:
        key = display_name.lower()
        now = utc_stamp()

        if key not in self.crash_candidates:
            self.crash_candidates[key] = {
                "display_name": display_name,
                "host_path": None,
                "first_seen_utc": now,
                "last_seen_utc": now,
                "count": 1,
                "delete_status": None,
                "deleted_utc": None,
                "delete_message": None,
            }
        else:
            self.crash_candidates[key]["last_seen_utc"] = now
            self.crash_candidates[key]["count"] += 1

        self.append_event("CRASH_CANDIDATE", display_name)
        if not self.crash_candidates[key]["host_path"]:
            self.crash_candidates[key]["host_path"] = self.resolve_crash_candidate_host_path(display_name)

        if self.crash_candidates[key]["host_path"]:
            self.try_delete_path(
                self.crash_candidates[key]["host_path"],
                self.crash_candidates[key],
                missing_kind="CRASH_FILE_DELETE_SKIPPED",
                deleted_kind="CRASH_FILE_DELETED",
                failed_kind="CRASH_FILE_DELETE_FAILED",
            )
        self.write_summary()

    def send_email_notification(self, host_path: str, detected_language: str, english_audio: str):
        if not self.smtp_host or not self.smtp_to:
            return "skipped", "SMTP not configured"

        message = EmailMessage()
        message["Subject"] = f"Subgen English mismatch on {os.uname().nodename}"
        message["From"] = self.smtp_from or self.smtp_username or "subgen@localhost"
        message["To"] = ", ".join(self.smtp_to)
        message.set_content(
            "\n".join(
                [
                    "Subgen detected a non-English language on a file that still looks English based on its audio metadata.",
                    "",
                    f"File: {host_path}",
                    f"Detected language: {detected_language}",
                    f"English audio tracks: {english_audio}",
                    f"Timestamp (UTC): {utc_stamp()}",
                ]
            )
        )

        try:
            if self.smtp_use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.starttls(context=context)
                    if self.smtp_username:
                        server.login(self.smtp_username, self.smtp_password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    if self.smtp_username:
                        server.login(self.smtp_username, self.smtp_password)
                    server.send_message(message)
            return "sent", "Delivered successfully"
        except Exception as exc:
            return "failed", str(exc)

    def record_english_mismatch(self, container_path: str, detected_language: str, english_audio: str) -> None:
        host_path = self.convert_container_path_to_host_path(container_path)
        key = host_path.lower()
        now = utc_stamp()

        if key not in self.notifications:
            self.notifications[key] = {
                "host_path": host_path,
                "detected_language": detected_language,
                "english_audio": english_audio,
                "first_seen_utc": now,
                "last_seen_utc": now,
                "email_status": None,
                "email_message": None,
            }
        else:
            self.notifications[key]["last_seen_utc"] = now
            self.notifications[key]["detected_language"] = detected_language
            self.notifications[key]["english_audio"] = english_audio

        if self.notifications[key].get("email_status") != "sent":
            email_status, email_message = self.send_email_notification(host_path, detected_language, english_audio)
            self.notifications[key]["email_status"] = email_status
            self.notifications[key]["email_message"] = email_message
            self.append_event("ENGLISH_MISMATCH", f"{host_path} | detected={detected_language} | email={email_status}")

        self.write_summary()

    def process_log_line(self, line: str) -> None:
        if not line:
            return

        match = TRANSCRIBE_START_RE.search(line)
        if match:
            display_name = match.group("name").strip()
            self.last_transcribe_start = {"display_name": display_name, "seen_utc": utc_stamp()}
            self.append_event("TRANSCRIBE_START", display_name)
            return

        match = PROCESSING_ERROR_RE.search(line)
        if match:
            self.record_processing_error(match.group("path").strip())
            return

        match = ENGLISH_MISMATCH_RE.search(line)
        if match:
            self.record_english_mismatch(
                match.group("path").strip(),
                match.group("detected").strip(),
                match.group("audio").strip(),
            )
            return

        if "SIGSEGV" in line:
            if self.last_transcribe_start:
                self.record_crash_candidate(self.last_transcribe_start["display_name"])
            else:
                self.append_event("SIGSEGV", "Crash seen without a tracked TRANSCRIBE start")

    def follow_logs(self, since: str) -> None:
        command = [
            "docker",
            "logs",
            "--follow",
            "--since",
            since,
            self.container,
        ]
        self.append_event("FOLLOW", " ".join(command))
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        assert process.stdout is not None
        for line in process.stdout:
            self.process_log_line(line.rstrip("\n"))

        return_code = process.wait()
        if return_code != 0:
            self.append_event("FOLLOW_EXIT", f"docker logs exited with status {return_code}")

    def run(self, since: str) -> None:
        self.write_summary()
        self.append_event("MONITOR_START", f"Watching container '{self.container}' (auto_delete_failed_files={self.auto_delete})")
        cursor = since

        while True:
            try:
                self.follow_logs(cursor)
            except Exception as exc:
                self.append_event("MONITOR_ERROR", str(exc))

            time.sleep(self.reconnect_delay_seconds)
            cursor = utc_stamp()
            self.heartbeat_path.write_text(f"{utc_stamp()} reconnect after follow exit\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Monitor Subgen logs and clean up failed media.")
    parser.add_argument("--container", default=os.getenv("SUBGEN_CONTAINER", "subgen"))
    parser.add_argument("--media-root", default=os.getenv("MEDIA_ROOT", "/srv/media"))
    parser.add_argument(
        "--state-dir",
        default=os.getenv("SUBGEN_STATE_DIR", "/opt/subgen/monitor"),
    )
    parser.add_argument(
        "--since",
        default=env_default("SUBGEN_LOG_SINCE", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 10))),
    )
    parser.add_argument(
        "--reconnect-delay-seconds",
        type=int,
        default=int(os.getenv("SUBGEN_RECONNECT_DELAY_SECONDS", "5")),
    )
    parser.add_argument(
        "--auto-delete-failed-files",
        action="store_true",
        default=env_bool("AUTO_DELETE_FAILED_FILES", True),
    )
    parser.add_argument("--smtp-host", default=os.getenv("SMTP_HOST", ""))
    parser.add_argument("--smtp-port", type=int, default=int(os.getenv("SMTP_PORT", "587")))
    parser.add_argument("--smtp-username", default=os.getenv("SMTP_USERNAME", ""))
    parser.add_argument("--smtp-password", default=os.getenv("SMTP_PASSWORD", ""))
    parser.add_argument("--smtp-from", default=os.getenv("SMTP_FROM", ""))
    parser.add_argument("--smtp-to", default=os.getenv("SMTP_TO", "alerts@example.com"))
    parser.add_argument("--smtp-use-tls", action="store_true", default=env_bool("SMTP_USE_TLS", True))
    return parser.parse_args()


def main():
    args = parse_args()
    monitor = Monitor(args)
    monitor.run(args.since)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
