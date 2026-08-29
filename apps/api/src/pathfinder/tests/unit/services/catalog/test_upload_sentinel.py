"""A one-term vocabulary whose display starts with 'Upload a' is an empty state."""

from __future__ import annotations

from pathfinder.domain.parameters.wdk_vocab import (
    WDKTreeBoxVocabNode,
    WDKVocabNodeData,
    WDKVocabTerm,
)
from pathfinder.integrations.veupathdb.wdk_parameters import WDKEnumParam
from pathfinder.services.catalog.eda_backed import is_upload_sentinel_vocabulary
from pathfinder.services.catalog.param_formatting import format_param_info_typed
from pathfinder.services.catalog.param_sheet import SheetEntry, build_sheet


def _terms(*pairs: tuple[str, str]) -> list[WDKVocabTerm]:
    return [WDKVocabTerm((t, d, None)) for t, d in pairs]


def test_the_live_sentinel_is_recognised() -> None:
    vocabulary = _terms(
        (
            "EDAUD_slI5M0RwIg0Zw",
            "Upload a Phenotype User Dataset in My Workspace",
        )
    )
    assert is_upload_sentinel_vocabulary(vocabulary) is True


def test_a_real_single_dataset_vocabulary_is_not_a_sentinel() -> None:
    vocabulary = _terms(("EDAUD_realid", "My RNA-Seq counts"))
    assert is_upload_sentinel_vocabulary(vocabulary) is False


def test_two_terms_are_never_a_sentinel() -> None:
    vocabulary = _terms(
        ("EDAUD_a", "Upload a Phenotype User Dataset in My Workspace"),
        ("EDAUD_b", "My dataset"),
    )
    assert is_upload_sentinel_vocabulary(vocabulary) is False


def test_an_empty_vocabulary_is_not_a_sentinel() -> None:
    assert is_upload_sentinel_vocabulary([]) is False


def test_none_is_not_a_sentinel() -> None:
    assert is_upload_sentinel_vocabulary(None) is False


def test_the_raw_counts_sentinel_is_recognised_too() -> None:
    vocabulary = _terms(
        ("EDAUD_slI5M0RwIg0Zw", "Upload an RNA-Seq Raw Counts Dataset in My Workspace")
    )
    assert is_upload_sentinel_vocabulary(vocabulary) is True


def test_a_word_that_only_starts_with_upload_is_not_a_sentinel() -> None:
    """The article is a whole word, so 'Uploaded' is a dataset name."""
    assert (
        is_upload_sentinel_vocabulary(_terms(("EDAUD_x", "Uploaded counts"))) is False
    )


def test_a_dataset_named_upload_all_is_not_a_sentinel() -> None:
    """The article ends the word, so 'Upload All' names a dataset the user owns."""
    vocabulary = _terms(("EDAUD_x", "Upload All Samples"))
    assert is_upload_sentinel_vocabulary(vocabulary) is False


def test_a_dataset_named_upload_and_is_not_a_sentinel() -> None:
    vocabulary = _terms(("EDAUD_x", "Upload and merge"))
    assert is_upload_sentinel_vocabulary(vocabulary) is False


def test_a_tree_vocabulary_is_never_a_sentinel() -> None:
    tree = WDKTreeBoxVocabNode(
        data=WDKVocabNodeData(term="EDAUD_x", display="Upload a Dataset")
    )
    assert is_upload_sentinel_vocabulary(tree) is False


def _entry(vocabulary: list[WDKVocabTerm]) -> SheetEntry:
    param = WDKEnumParam(
        name="eda_dataset_id",
        display_name="User dataset",
        type="single-pick-vocabulary",
        vocabulary=vocabulary,
    )
    entries = build_sheet(format_param_info_typed([param]), query="my phenotype data")
    assert len(entries) == 1
    return entries[0]


def test_the_sheet_offers_no_value_when_the_vocabulary_is_the_sentinel() -> None:
    entry = _entry(
        _terms(
            (
                "EDAUD_slI5M0RwIg0Zw",
                "Upload a Phenotype User Dataset in My Workspace",
            )
        )
    )

    assert entry.vocabulary == []
    assert entry.vocabulary_total == 0
    assert entry.vocabulary_note is not None
    assert "no installed dataset" in entry.vocabulary_note


def test_the_sheet_keeps_a_real_one_dataset_vocabulary() -> None:
    entry = _entry(_terms(("EDAUD_realid", "My RNA-Seq counts")))

    assert [option.value for option in entry.vocabulary] == ["EDAUD_realid"]
    assert entry.vocabulary_note is None
