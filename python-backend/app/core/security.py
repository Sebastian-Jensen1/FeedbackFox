"""Sikkerhed omkring hele appen.

To ting sker for ALLE requests:
  1. Der tilføjes sikkerhedsheaders til svaret (SecurityHeadersMiddleware).
  2. Requests med for stor body afvises (BodySizeLimitMiddleware).

En "middleware" er kode der sidder mellem browseren og vores routes og ser alle
requests og svar igennem.
"""

import base64
import hashlib
import re
from pathlib import Path

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Største tilladte request: 256 KB. En normal request er et par hundrede bytes.
MAX_BODY_BYTES = 256 * 1024

# Finder <script>...</script> uden src= (altså JavaScript skrevet direkte i HTML-filen).
_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)


def inline_script_hashes(index_html: Path) -> list[str]:
    """Regner hash (et fingeraftryk) ud for scriptet i index.html.

    Browseren må kun køre scripts hvis fingeraftryk står på listen. Får en
    angriber sneget et script ind i en anmeldelse, har det et andet fingeraftryk
    og bliver blokeret.
    """
    if not index_html.is_file():
        return []
    # Browseren regner på tekst med \n som linjeskift, så vi gør det samme.
    html = index_html.read_text(encoding="utf-8").replace("\r\n", "\n")
    return [
        "'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode("utf-8")).digest()).decode() + "'"
        for m in _INLINE_SCRIPT.finditer(html)
    ]


def build_csp(script_hashes: list[str]) -> str:
    """Bygger Content-Security-Policy: en liste over hvad siden må indlæse og køre.

    Alt er forbudt som udgangspunkt, og så åbnes der kun for det siden har brug for.
    """
    return "; ".join(
        [
            "default-src 'none'",  # som udgangspunkt: intet må indlæses
            "script-src 'self' " + " ".join(script_hashes),  # kun vores eget script
            "style-src 'self' 'unsafe-inline'",  # siden bruger style-attributter
            "img-src 'self' data:",
            "connect-src 'self'",  # fetch() må kun kalde vores egen server
            "base-uri 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",  # siden må ikke vises i en iframe (clickjacking)
        ]
    )


class SecurityHeadersMiddleware:
    """Tilføjer sikkerhedsheaders til hvert eneste svar."""

    def __init__(self, app: ASGIApp, csp: str):
        self.app = app
        self.csp = csp

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Kører for hver request. Sender den videre og retter svarets headers på vejen tilbage."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_api = scope["path"].startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            """Tilføjer headers når svaret begynder at blive sendt."""
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = self.csp
                headers["X-Content-Type-Options"] = "nosniff"  # browseren må ikke gætte filtype
                headers["Referrer-Policy"] = "no-referrer"
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                headers["Cross-Origin-Resource-Policy"] = "same-origin"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if is_api:
                    # API-svar er forretningsdata og skal ikke gemmes i browserens cache.
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _BodyTooLarge(Exception):
    """Bruges internt når en request viser sig at være for stor."""


class BodySizeLimitMiddleware:
    """Afviser requests der er større end grænsen (svarer 413)."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Kører for hver request. Tjekker størrelsen både på forhånd og mens data læses."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Tjek 1: klienten oplyser selv en størrelse i headeren Content-Length.
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(send)
            return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            """Tæller bytes efterhånden som de læses. Tjek 2, fordi Content-Length kan være løgn."""
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            """Husker om vi er begyndt at svare (så vi ikke svarer to gange)."""
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        """Sender svaret 413 "Forespørgslen er for stor"."""
        body = '{"error":"Forespørgslen er for stor."}'.encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
