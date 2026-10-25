"""Explicitly confirmed outbound Twilio Voice calls; planning is offline.

Examples::
    python -m personal.calls plan --to +14155552671 --message "Hello"
    python -m personal.calls place --to +14155552671 --message "Hello" --confirm

The second command contacts the recipient and can incur Twilio charges.
It plays a message; interactive conversation requires a separate voice service.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Mapping
from xml.sax.saxutils import escape

import httpx

ENV_NAMES = (
    "JARVIS_TWILIO_ACCOUNT_SID",
    "JARVIS_TWILIO_AUTH_TOKEN",
    "JARVIS_TWILIO_FROM_NUMBER",
)
_PHONE = re.compile(r"\+[1-9][0-9]{7,14}\Z")
_SID = re.compile(r"AC[0-9a-fA-F]{32}\Z")


class CallError(RuntimeError):
    """A safe, user-facing call setup or provider failure."""


def credential_status(environ: Mapping[str, str] | None = None) -> dict[str, bool]:
    """Report presence only, never credential values."""
    env = os.environ if environ is None else environ
    return {name: bool(env.get(name, "").strip()) for name in ENV_NAMES}


def _validate_phone(value: str, label: str) -> str:
    if not _PHONE.fullmatch(value):
        raise CallError(f"{label} must be an E.164 number, for example +14155552671.")
    return value


def _twiml(message: str) -> str:
    if not message.strip() or len(message) > 4000:
        raise CallError("Message must contain 1 to 4000 characters.")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in message):
        raise CallError("Message contains unsupported control characters.")
    return f"<Response><Say>{escape(message)}</Say></Response>"


def plan_call(
    to: str, message: str, *, environ: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Create a local preview. Does not use the network or require credentials."""
    return {
        "action": "outbound_voice_message",
        "to": _validate_phone(to, "Recipient"),
        "message": message,
        "twiml": _twiml(message),
        "credential_status": credential_status(environ),
        "network_request_sent": False,
        "next_step": (
            "Review recipient and message; place with --confirm to make a paid call."
        ),
    }


def place_call(
    to: str,
    message: str,
    *,
    confirmed: bool = False,
    environ: Mapping[str, str] | None = None,
    client: httpx.Client | None = None,
) -> dict[str, str]:
    """Submit exactly one voice call after explicit confirmation.

    No automatic retries: a timeout may occur after Twilio accepted a call.
    Check the Twilio console before trying again after any uncertain failure.
    """
    if confirmed is not True:
        raise CallError(
            "Explicit --confirm is required to contact the recipient and incur charges."
        )
    env = os.environ if environ is None else environ
    recipient = _validate_phone(to, "Recipient")
    twiml = _twiml(message)
    missing = [name for name, present in credential_status(env).items() if not present]
    if missing:
        raise CallError("Missing environment settings: " + ", ".join(missing))
    sid = env[ENV_NAMES[0]].strip()
    if not _SID.fullmatch(sid):
        raise CallError("JARVIS_TWILIO_ACCOUNT_SID must be a valid Twilio account SID.")
    sender = _validate_phone(env[ENV_NAMES[2]].strip(), "Configured sender")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
    own_client = client is None
    connection = client if client is not None else httpx.Client()
    try:
        try:
            response = connection.post(
                url,
                data={"To": recipient, "From": sender, "Twiml": twiml},
                auth=httpx.BasicAuth(sid, env[ENV_NAMES[1]]),
                timeout=30.0,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise CallError(
                "Twilio request failed; call acceptance is unknown. "
                "Check the Twilio console before retrying."
            ) from None
        if response.status_code != 201:
            raise CallError(
                f"Twilio did not confirm call creation (HTTP {response.status_code}). "
                "Check the Twilio console; no automatic retry was attempted."
            )
        try:
            data = response.json()
        except ValueError:
            data = None
        if not isinstance(data, dict) or not isinstance(data.get("sid"), str):
            raise CallError(
                "Twilio returned an unexpected response; call acceptance is unknown. "
                "Check the Twilio console before retrying."
            )
        call_sid = data["sid"]
        status = data.get("status", "queued")
        if not re.fullmatch(r"CA[0-9a-fA-F]{32}", call_sid):
            raise CallError(
                "Twilio response lacks a valid call SID; check the Twilio console."
            )
        allowed_statuses = {
            "queued",
            "ringing",
            "in-progress",
            "completed",
            "busy",
            "failed",
            "no-answer",
            "canceled",
        }
        if not isinstance(status, str) or status not in allowed_statuses:
            status = "unknown"
        return {"call_sid": call_sid, "status": status}
    finally:
        if own_client:
            connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "place"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("--to", required=True)
        command_parser.add_argument("--message", required=True)
        if command == "place":
            command_parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = (
            plan_call(args.to, args.message)
            if args.command == "plan"
            else place_call(args.to, args.message, confirmed=args.confirm)
        )
    except CallError as exc:
        parser.exit(1, f"Call error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
