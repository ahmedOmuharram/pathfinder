"""Who a request acts as: the user, the calling application, and the credential."""

import hmac
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pathfinder.platform.pydantic_base import CamelModel

CredentialKind = Literal[
    "pathfinder-cookie",
    "pathfinder-bearer",
    "veupathdb-bearer",
]

DEFAULT_APPLICATION_ID = "pathfinder"
SERVICE_AUTH_HEADER = "X-PathFinder-Service-Token"

_MIN_SERVICE_SECRET_LENGTH = 32
_ENTRY_SEPARATOR = ","
_FIELD_SEPARATOR = ":"


class Principal(CamelModel):
    """The identity a request is served under."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    application_id: str = DEFAULT_APPLICATION_ID
    credential: CredentialKind


class ServiceToken(BaseModel):
    """One application identity and the shared secret that proves it."""

    model_config = ConfigDict(frozen=True)

    application_id: str = Field(min_length=1)
    secret: str = Field(min_length=_MIN_SERVICE_SECRET_LENGTH, repr=False)


class ServiceTokenRegistry(BaseModel):
    """The configured application identities."""

    model_config = ConfigDict(frozen=True)

    tokens: tuple[ServiceToken, ...] = ()

    @model_validator(mode="after")
    def _reject_repeated_application_ids(self) -> Self:
        seen: set[str] = set()
        for token in self.tokens:
            if token.application_id in seen:
                msg = (
                    f"Service token application id is repeated: {token.application_id}"
                )
                raise ValueError(msg)
            seen.add(token.application_id)
        return self

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Read the ``app_id:secret[,app_id:secret...]`` setting form."""
        entries = [
            entry.strip() for entry in raw.split(_ENTRY_SEPARATOR) if entry.strip()
        ]
        tokens: list[ServiceToken] = []
        for entry in entries:
            application_id, separator, secret = entry.partition(_FIELD_SEPARATOR)
            if not separator:
                msg = f"Service token entry must read application_id:secret: {entry!r}"
                raise ValueError(msg)
            tokens.append(
                ServiceToken(
                    application_id=application_id.strip(),
                    secret=secret.strip(),
                ),
            )
        return cls(tokens=tuple(tokens))

    def application_for(self, presented: str) -> str | None:
        """Return the application the presented secret proves, or None.

        The comparison is over encoded bytes, because a header carries any byte
        and a non-ASCII string cannot be compared. Every configured secret is
        compared, so the answer takes the same work whichever one matches.
        """
        candidate = presented.encode("utf-8")
        matched: str | None = None
        for token in self.tokens:
            if hmac.compare_digest(token.secret.encode("utf-8"), candidate):
                matched = token.application_id
        return matched
