"""When the portal retry also fails, report the site's error, not the portal's.

Component-site searches do not all exist on veupathdb.org. Retrying there
after a site failure turns a real PlasmoDB error into a portal 500, and the
500 is what the researcher sees - so the actual cause is invisible and the
step editor just says "Failed to load parameters for this search."

The retry is worth keeping: some searches genuinely only resolve on the
portal. What must not happen is the fallback's own failure replacing the
diagnosis.
"""

from __future__ import annotations

from pathfinder.platform.errors import WDKError
from pathfinder.services.catalog.param_resolution import prefer_original_wdk_error


class TestPreferOriginalWdkError:
    def test_the_portal_message_does_not_replace_the_site_one(self) -> None:
        original = WDKError("GenesByOrthologPattern rejected phyletic_indent_map", 422)
        fallback = WDKError("Internal Server Error", 500)

        chosen = prefer_original_wdk_error(original, fallback)

        detail = str(chosen.detail)
        assert detail.startswith("GenesByOrthologPattern rejected")

    def test_the_original_message_survives(self) -> None:
        original = WDKError("phyletic_indent_map does not accept '[]'", 422)
        fallback = WDKError("Internal Server Error", 500)

        chosen = prefer_original_wdk_error(original, fallback)

        assert "phyletic_indent_map" in str(chosen.detail)

    def test_the_fallback_failure_is_still_recorded(self) -> None:
        """Dropping it entirely would hide that a second call was even made."""
        original = WDKError("original failure", 422)
        fallback = WDKError("portal exploded", 500)

        chosen = prefer_original_wdk_error(original, fallback)

        assert "portal exploded" in str(chosen.detail)

    def test_the_original_status_is_kept(self) -> None:
        """A 422 from the site is a different problem from a portal 500 and
        must not be reported as one."""
        original = WDKError("bad parameter", 422)
        fallback = WDKError("Internal Server Error", 500)

        chosen = prefer_original_wdk_error(original, fallback)

        assert chosen.status == 422

    def test_it_stays_a_wdk_error(self) -> None:
        chosen = prefer_original_wdk_error(
            WDKError("a", 422),
            WDKError("b", 500),
        )

        assert isinstance(chosen, WDKError)
