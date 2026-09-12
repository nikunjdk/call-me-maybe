from __future__ import annotations

from twilio.twiml.voice_response import Dial, VoiceResponse

from app.models import Session

# Hour-one invariant: killing a leg must not collapse the conference.
END_CONFERENCE_ON_EXIT = False
BROWSER_LABEL = "browser"


def _booking_bits(session: Session | None) -> tuple[str, str, str, str]:
    if session is None or session.extracted is None:
        return "Alex Chen", "ABC123", "UA 482", "September 18"
    extracted = session.extracted
    return (
        extracted.passenger_name,
        extracted.pnr,
        extracted.flight_number,
        extracted.date,
    )


def rep_twiml(session: Session | None = None) -> str:
    """Audio for the simulated airline PSTN participant.

    This TwiML *is* the other party. Do not Dial a Conference here — Twilio
    already mixed this call into cmm-<session_id> via participants.create.
    """
    passenger, pnr, flight, date = _booking_bits(session)
    response = VoiceResponse()
    response.pause(length=2)
    response.say(
        "Thank you for calling United Reservations. This call may be recorded. "
        "How can I help you today?",
        voice="Polly.Joanna",
    )
    response.pause(length=12)
    response.say(
        f"I found the booking for {passenger}, confirmation {pnr}, "
        f"flight {flight} on {date}. I can cancel that reservation. "
        "Please note there is a two hundred dollar cancellation fee.",
        voice="Polly.Joanna",
    )
    response.pause(length=10)
    response.say(
        "To complete the cancellation I will need the credit card used to "
        "purchase the ticket, or another card for the fee.",
        voice="Polly.Joanna",
    )
    response.pause(length=120)
    return str(response)


def browser_twiml(
    session_id: str,
    status_url: str | None = None,
    muted: bool = True,
) -> str:
    """Place the Voice JS client into the conference muted."""
    response = VoiceResponse()
    dial = Dial()
    kwargs: dict = {
        "muted": muted,
        "beep": False,
        "start_conference_on_enter": True,
        "end_conference_on_exit": END_CONFERENCE_ON_EXIT,
        "participant_label": BROWSER_LABEL,
    }
    if status_url:
        kwargs["status_callback"] = status_url
        kwargs["status_callback_event"] = "start end join leave mute"
        kwargs["status_callback_method"] = "POST"
    dial.conference(f"cmm-{session_id}", **kwargs)
    response.append(dial)
    return str(response)
