from veupath_chatbot.integrations.vectorstore.qdrant_store import point_uuid


def test_point_uuid_is_deterministic() -> None:
    a = point_uuid("plasmodb:transcript:GenesByText")
    b = point_uuid("plasmodb:transcript:GenesByText")
    c = point_uuid("plasmodb:transcript:GenesByPhenotypeText")
    assert a == b
    assert a != c
