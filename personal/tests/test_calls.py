"""Provider requests are mocked: these tests never contact recipients."""

import json

import httpx
import pytest
from personal.calls import CallError, credential_status, main, place_call, plan_call

SETTINGS = {
    "JARVIS_TWILIO_ACCOUNT_SID": "AC" + "1" * 32,
    "JARVIS_TWILIO_AUTH_TOKEN": "test-secret-do-not-log",
    "JARVIS_TWILIO_FROM_NUMBER": "+14155552671",
}


def test_offline_plan_escapes_message_and_reports_presence_only():
    preview = plan_call("+442079460018", 'A < B & "C"', environ=SETTINGS)
    assert preview["network_request_sent"] is False
    assert '<Say>A &lt; B &amp; "C"</Say>' in preview["twiml"]
    assert all(preview["credential_status"].values())
    assert SETTINGS["JARVIS_TWILIO_AUTH_TOKEN"] not in json.dumps(preview)
    assert not any(credential_status({}).values())


@pytest.mark.parametrize(
    "phone", ["4155552671", "+1", "+0123456789", "+12345678/Calls"]
)
def test_reject_invalid_recipient(phone):
    with pytest.raises(CallError, match="E.164"):
        plan_call(phone, "Hello", environ={})


@pytest.mark.parametrize("message", ["", "  ", "x" * 4001, "Hello\x00"])
def test_reject_invalid_message(message):
    with pytest.raises(CallError):
        plan_call("+442079460018", message, environ={})


def test_confirmation_required_before_request():
    def no_request(request):
        pytest.fail("No network request may occur without confirmation")

    with httpx.Client(transport=httpx.MockTransport(no_request)) as client:
        with pytest.raises(CallError, match="--confirm"):
            place_call("+442079460018", "Hello", environ=SETTINGS, client=client)


def test_missing_credentials_no_request():
    with pytest.raises(CallError, match="Missing environment settings"):
        place_call("+442079460018", "Hello", confirmed=True, environ={})


def test_exact_provider_request_and_safe_result():
    requests = []

    def handle(request):
        requests.append(request)
        assert str(request.url) == (
            "https://api.twilio.com/2010-04-01/Accounts/"
            + SETTINGS["JARVIS_TWILIO_ACCOUNT_SID"]
            + "/Calls.json"
        )
        from urllib.parse import parse_qs

        payload = parse_qs(request.content.decode())
        assert payload == {
            "To": ["+442079460018"],
            "From": ["+14155552671"],
            "Twiml": ["<Response><Say>Hello &amp; welcome</Say></Response>"],
        }
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(201, json={"sid": "CA" + "2" * 32, "status": "queued"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = place_call(
            "+442079460018",
            "Hello & welcome",
            confirmed=True,
            environ=SETTINGS,
            client=client,
        )
    assert result == {"call_sid": "CA" + "2" * 32, "status": "queued"}
    assert len(requests) == 1


def test_provider_error_does_not_expose_response_or_retry():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(401, text=SETTINGS["JARVIS_TWILIO_AUTH_TOKEN"])

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(CallError, match="HTTP 401") as error:
            place_call(
                "+442079460018",
                "Hello",
                confirmed=True,
                environ=SETTINGS,
                client=client,
            )
    assert SETTINGS["JARVIS_TWILIO_AUTH_TOKEN"] not in str(error.value)
    assert len(requests) == 1


def test_timeout_is_uncertain_and_not_retried():
    requests = []

    def handle(request):
        requests.append(request)
        raise httpx.ReadTimeout("sensitive detail", request=request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(CallError, match="acceptance is unknown") as error:
            place_call(
                "+442079460018",
                "Hello",
                confirmed=True,
                environ=SETTINGS,
                client=client,
            )
    assert "sensitive detail" not in str(error.value)
    assert len(requests) == 1


def test_cli_plan_and_unconfirmed_place(capsys):
    assert main(["plan", "--to", "+442079460018", "--message", "Hello"]) == 0
    assert json.loads(capsys.readouterr().out)["network_request_sent"] is False
    with pytest.raises(SystemExit) as error:
        main(["place", "--to", "+442079460018", "--message", "Hello"])
    assert error.value.code == 1
    assert "--confirm" in capsys.readouterr().err
