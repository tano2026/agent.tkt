"""
AGT API HTTP Client.

Handles all communication with the external AGT cấp 1 API (https://api.abtrip.vn).
Injects authentication (RequestInfo) into every request automatically.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from app.services.config import get_settings

logger = logging.getLogger(__name__)


class ABTripClient:
    """
    HTTP client for the ABTrip (AGT cấp 1) API.

    All requests are POST to /Flight/* endpoints.
    Auth fields (PrivateKey, ApiAccount, ApiPassword) are injected
    automatically from environment variables into the RequestInfo payload.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.agt_api_host.rstrip("/")
        self._private_key = settings.agt_private_key
        self._api_account = settings.agt_api_account
        self._api_password = settings.agt_api_password

        if not all([self._private_key, self._api_account, self._api_password]):
            logger.warning(
                "AGT API credentials not fully configured. "
                "Set AGT_PRIVATE_KEY, AGT_API_ACCOUNT, AGT_API_PASSWORD env vars."
            )

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(60.0, connect=30.0),
            follow_redirects=True,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_request_info(self) -> dict[str, str]:
        """Build the RequestInfo dict with authentication credentials."""
        return {
            "PrivateKey": self._private_key,
            "ApiAccount": self._api_account,
            "ApiPassword": self._api_password,
        }

    def _inject_auth(self, body: dict[str, Any]) -> dict[str, Any]:
        """
        Ensure RequestInfo is present in the request body.
        If the caller provided a partial RequestInfo, merge credentials.
        """
        body = dict(body)
        existing = body.get("RequestInfo", {}) or {}
        body["RequestInfo"] = {**existing, **self._build_request_info()}
        return body

    async def _post(
        self, endpoint: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Send a POST request to the AGT API and return the JSON response.
        Handles authentication injection, errors, and logging.
        """
        url = f"/Flight/{endpoint.lstrip('/')}"
        payload = self._inject_auth(body)

        logger.debug("AGT POST %s", url)

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            logger.debug("AGT %s -> %s", url, data.get("Message", "OK"))
            return data
        except httpx.TimeoutException as exc:
            logger.error("AGT %s timeout: %s", url, exc)
            return {
                "StatusCode": "TIMEOUT",
                "Success": False,
                "Message": f"Request to AGT API timed out: {exc}",
            }
        except httpx.HTTPStatusError as exc:
            logger.error("AGT %s HTTP error: %s", url, exc)
            return {
                "StatusCode": str(exc.response.status_code),
                "Success": False,
                "Message": f"AGT API HTTP error: {exc.response.text}",
            }
        except httpx.RequestError as exc:
            logger.error("AGT %s request failed: %s", url, exc)
            return {
                "StatusCode": "ERROR",
                "Success": False,
                "Message": f"AGT API request failed: {exc}",
            }
        except Exception as exc:
            logger.exception("AGT %s unexpected error: %s", url, exc)
            return {
                "StatusCode": "ERROR",
                "Success": False,
                "Message": f"Unexpected AGT API error: {exc}",
            }

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def search_flight(
        self,
        system: str,
        adt: int = 1,
        chd: int = 0,
        inf: int = 0,
        routes: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Search for flights.

        POST /Flight/SearchFlight
        """
        body = {
            "System": system,
            "Adt": adt,
            "Chd": chd,
            "Inf": inf,
            "ListRoute": routes or [],
        }
        return await self._post("SearchFlight", body)

    async def book_flight(
        self,
        forced: bool = False,
        system: str = "",
        guest_contact: Optional[dict[str, Any]] = None,
        agent_contact: Optional[dict[str, Any]] = None,
        passengers: Optional[list[dict[str, Any]]] = None,
        air_options: Optional[list[dict[str, Any]]] = None,
        option: str = "",
        payment: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Book a flight.

        POST /Flight/BookFlight
        """
        body = {
            "Forced": forced,
            "System": system,
            "GuestContact": guest_contact or {},
            "AgentContact": agent_contact or {},
            "ListPassenger": passengers or [],
            "ListAirOption": air_options or [],
            "Option": option,
            "Payment": payment or {},
        }
        return await self._post("BookFlight", body)

    async def issue_ticket(self, booking_code: str) -> dict[str, Any]:
        """
        Issue a ticket for a booked flight.

        POST /Flight/IssueTicket
        """
        body = {"BookingCode": booking_code}
        return await self._post("IssueTicket", body)

    async def retrieve_booking(self, booking_code: str) -> dict[str, Any]:
        """
        Retrieve booking details.

        POST /Flight/RetrieveBooking
        """
        body = {"BookingCode": booking_code}
        return await self._post("RetrieveBooking", body)

    async def get_ancillary(
        self, sessions: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """
        Get ancillary services (bags, meals, etc.) for search results.

        POST /Flight/GetAncillary
        """
        body = {"ListSession": sessions or []}
        return await self._post("GetAncillary", body)

    async def get_fare_rule(
        self, sessions: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """
        Get fare rules for search results.

        POST /Flight/GetFareRule
        """
        body = {"ListSession": sessions or []}
        return await self._post("GetFareRule", body)

    async def get_seat_map(
        self, sessions: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """
        Get seat map for search results.

        POST /Flight/GetSeatMap
        """
        body = {"ListSession": sessions or []}
        return await self._post("GetSeatMap", body)

    async def get_airports(self) -> dict[str, Any]:
        """
        Get list of airports.

        POST /Flight/GetAirports
        """
        body: dict[str, Any] = {}
        return await self._post("GetAirports", body)

    async def get_airlines(self) -> dict[str, Any]:
        """
        Get list of airlines.

        POST /Flight/GetAirlines
        """
        body: dict[str, Any] = {}
        return await self._post("GetAirlines", body)

    async def get_aircrafts(self) -> dict[str, Any]:
        """
        Get list of aircraft types.

        POST /Flight/GetAircrafts
        """
        body: dict[str, Any] = {}
        return await self._post("GetAircrafts", body)

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        await self._client.aclose()


# Module-level singleton for convenience
_client_instance: Optional[ABTripClient] = None


def get_client() -> ABTripClient:
    """Get or create the ABTripClient singleton."""
    global _client_instance
    if _client_instance is None:
        _client_instance = ABTripClient()
    return _client_instance


async def close_client() -> None:
    """Close the client singleton."""
    global _client_instance
    if _client_instance is not None:
        await _client_instance.close()
        _client_instance = None
