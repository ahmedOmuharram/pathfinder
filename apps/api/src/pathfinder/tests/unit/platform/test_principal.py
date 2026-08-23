"""Principal value objects and service-token matching."""

import pytest
from assistant_core.platform.context import DEFAULT_APPLICATION_ID
from pydantic import ValidationError

from pathfinder.platform.principal import Principal, ServiceTokenRegistry

USER_ID = "11111111-2222-3333-4444-555555555555"
SECRET = "analytics-secret-0123456789abcdefgh"
OTHER_SECRET = "gene-page-secret-0123456789abcdefgh"


class TestPrincipal:
    def test_the_application_defaults_to_pathfinder(self) -> None:
        principal = Principal(user_id=USER_ID, credential="pathfinder-cookie")

        assert principal.application_id == DEFAULT_APPLICATION_ID
        assert principal.application_id == "pathfinder"

    def test_the_principal_is_immutable(self) -> None:
        principal = Principal(user_id=USER_ID, credential="pathfinder-cookie")

        with pytest.raises(ValidationError):
            principal.application_id = "other"

    def test_an_unknown_credential_kind_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Principal(user_id=USER_ID, credential="basic-auth")

    def test_the_json_form_uses_camel_case(self) -> None:
        principal = Principal(
            user_id=USER_ID,
            application_id="analytics",
            credential="veupathdb-bearer",
        )

        assert principal.model_dump(by_alias=True, mode="json") == {
            "userId": USER_ID,
            "applicationId": "analytics",
            "credential": "veupathdb-bearer",
        }


class TestServiceTokenRegistry:
    def test_an_empty_setting_matches_nothing(self) -> None:
        registry = ServiceTokenRegistry.parse("")

        assert registry.tokens == ()
        assert registry.application_for(SECRET) is None

    def test_a_configured_secret_names_its_application(self) -> None:
        registry = ServiceTokenRegistry.parse(f"analytics:{SECRET}")

        assert registry.application_for(SECRET) == "analytics"

    def test_an_unknown_secret_names_no_application(self) -> None:
        registry = ServiceTokenRegistry.parse(f"analytics:{SECRET}")

        assert registry.application_for(OTHER_SECRET) is None

    def test_each_application_keeps_its_own_secret(self) -> None:
        registry = ServiceTokenRegistry.parse(
            f"analytics:{SECRET}, gene-page:{OTHER_SECRET}",
        )

        assert registry.application_for(SECRET) == "analytics"
        assert registry.application_for(OTHER_SECRET) == "gene-page"

    def test_padding_around_an_entry_is_not_part_of_the_secret(self) -> None:
        registry = ServiceTokenRegistry.parse(f"  analytics :  {SECRET}  ")

        assert registry.application_for(SECRET) == "analytics"

    def test_a_trailing_separator_is_ignored(self) -> None:
        registry = ServiceTokenRegistry.parse(f"analytics:{SECRET},")

        assert len(registry.tokens) == 1

    def test_an_entry_without_a_separator_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="application_id:secret"):
            ServiceTokenRegistry.parse(SECRET)

    def test_a_short_secret_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ServiceTokenRegistry.parse("analytics:too-short")

    def test_a_blank_application_id_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ServiceTokenRegistry.parse(f":{SECRET}")

    def test_a_repeated_application_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="analytics"):
            ServiceTokenRegistry.parse(f"analytics:{SECRET},analytics:{OTHER_SECRET}")

    def test_a_non_ascii_secret_matches_nothing_instead_of_raising(self) -> None:
        """Starlette decodes a header as latin-1, so any byte can reach the match."""
        registry = ServiceTokenRegistry.parse(f"analytics:{SECRET}")

        assert registry.application_for("caf\xe9-token-0123456789abcdefghij") is None
        assert registry.application_for("\U0001f512" * 40) is None
        assert registry.application_for(SECRET) == "analytics"

    def test_the_secret_stays_out_of_the_repr(self) -> None:
        registry = ServiceTokenRegistry.parse(f"analytics:{SECRET}")

        assert SECRET not in repr(registry)
        assert "analytics" in repr(registry)
