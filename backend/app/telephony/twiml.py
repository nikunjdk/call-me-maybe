from __future__ import annotations

from twilio.twiml.voice_response import Dial, Start, Stream, VoiceResponse

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


def rep_lines(session: Session | None = None) -> tuple[str, str, str]:
    """The three scripted-rep utterances — shared by TwiML and the transcript clock."""
    passenger, pnr, flight, date = _booking_bits(session)
    greeting = (
        "Hello, this is an AI assistant calling on behalf of Kohav Dey. "
        "I have their booking reference 8H2FED for Japan Airlines JL 030 "
        "on 2026-08-17. They would like to cancel this reservation."
    )
    fee = (
        f"I found the booking for {passenger}, confirmation {pnr}, "
        f"flight {flight} on {date}. I can cancel that reservation. "
        "Please note there is a two hundred dollar cancellation fee."
    )
    payment = (
        "To complete the cancellation I will need the credit card used to "
        "purchase the ticket, or another card for the fee."
    )
    return greeting, fee, payment


def attach_media_stream(
    response: VoiceResponse,
    stream_url: str | None,
    *,
    session_id: str | None = None,
    track: str = "both_tracks",
) -> None:
    """Fork call audio to ElevenLabs Scribe via Twilio Media Streams."""
    if not stream_url:
        return
    start = Start()
    kwargs: dict = {"url": stream_url, "name": "scribe"}
    if track:
        kwargs["track"] = track
    stream = Stream(**kwargs)
    if session_id:
        stream.parameter(name="session_id", value=session_id)
    start.append(stream)
    response.append(start)


def rep_twiml(
    session: Session | None = None,
    *,
    stream_url: str | None = None,
    session_id: str | None = None,
    stream_track: str = "both_tracks",
) -> str:
    """Audio for the simulated airline PSTN participant.

    This TwiML *is* the other party. Do not Dial a Conference here — Twilio
    already mixed this call into cmm-<session_id> via participants.create.
    """
    greeting, fee, payment = rep_lines(session)
    response = VoiceResponse()
    attach_media_stream(
        response, stream_url, session_id=session_id, track=stream_track
    )
    response.pause(length=2)
    response.say(greeting, voice="alice")
    response.pause(length=12)
    response.say(fee, voice="alice")
    response.pause(length=10)
    response.say(payment, voice="alice")
    response.pause(length=120)
    return str(response)


def conference_join_twiml(
    session_id: str,
    *,
    label: str = BROWSER_LABEL,
    muted: bool = True,
    status_url: str | None = None,
) -> str:
    """TwiML <Dial><Conference> — trial accounts cannot use Participants REST."""
    response = VoiceResponse()
    dial = Dial()
    kwargs: dict = {
        "muted": muted,
        "beep": False,
        "start_conference_on_enter": True,
        "end_conference_on_exit": END_CONFERENCE_ON_EXIT,
        "participant_label": label,
    }
    if status_url:
        kwargs["status_callback"] = status_url
        kwargs["status_callback_event"] = "start end join leave mute"
        kwargs["status_callback_method"] = "POST"
    dial.conference(f"cmm-{session_id}", **kwargs)
    response.append(dial)
    return str(response)


def browser_twiml(
    session_id: str,
    status_url: str | None = None,
    muted: bool = True,
) -> str:
    """Place the Voice JS client into the conference muted."""
    return conference_join_twiml(
        session_id, label=BROWSER_LABEL, muted=muted, status_url=status_url
    )
