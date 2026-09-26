from typing import Any
from urllib.request import Request, urlopen
import json

from app.integrations.google_oauth.service import google_oauth_service


GOOGLE_CALENDAR_EVENTS_URL = (
    "https://www.googleapis.com/calendar/v3/"
    "calendars/primary/events"
)


class GoogleCalendarClient:
    async def create_event(
        self,
        user_id: str,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        access_token = (
            await google_oauth_service.get_valid_access_token(
                user_id
            )
        )

        payload = json.dumps(event).encode("utf-8")

        request = Request(
            GOOGLE_CALENDAR_EVENTS_URL,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )

        with urlopen(request, timeout=20.0) as response:
            body = response.read()

        if not body:
            return {}

        return json.loads(body)


google_calendar_client = GoogleCalendarClient()