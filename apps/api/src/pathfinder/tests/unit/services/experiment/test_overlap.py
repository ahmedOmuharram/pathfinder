from pathfinder.services.experiment.overlap import (
    GeneMembership,
    OverlapResult,
    PairwiseOverlap,
    PerExperimentSummary,
    compute_gene_set_overlap,
)
from pathfinder.services.experiment.types.experiment import (
    Experiment,
    ExperimentConfig,
)
from pathfinder.services.experiment.types.metrics import GeneInfo


def _gene(gene_id: str) -> GeneInfo:
    return GeneInfo(id=gene_id)


def _exp(
    exp_id: str,
    name: str,
    tp: list[str],
    fp: list[str],
) -> Experiment:
    return Experiment(
        id=exp_id,
        config=ExperimentConfig(
            site_id="plasmodb",
            record_type="transcript",
            search_name="S",
            parameters={},
            positive_controls=[],
            negative_controls=[],
            controls_search_name="C",
            controls_param_name="p",
            name=name,
        ),
        true_positive_genes=[_gene(g) for g in tp],
        false_positive_genes=[_gene(g) for g in fp],
    )


def _pair(result: OverlapResult, a_id: str, b_id: str) -> PairwiseOverlap:
    matches = [
        e
        for e in result["pairwise"]
        if e["experimentA"] == a_id and e["experimentB"] == b_id
    ]
    assert len(matches) == 1
    return matches[0]


def _summary(result: OverlapResult, exp_id: str) -> PerExperimentSummary:
    matches = [e for e in result["perExperiment"] if e["experimentId"] == exp_id]
    assert len(matches) == 1
    return matches[0]


def _membership(result: OverlapResult, gene_id: str) -> GeneMembership:
    matches = [e for e in result["geneMembership"] if e["geneId"] == gene_id]
    assert len(matches) == 1
    return matches[0]


def test_two_experiment_pairwise_partial_overlap() -> None:
    a = _exp("A", "Alpha", ["g1", "g2"], ["g3"])
    b = _exp("B", "Beta", ["g2", "g3"], ["g4"])

    result = compute_gene_set_overlap([a, b], ["A", "B"])

    assert len(result["pairwise"]) == 1
    pair = _pair(result, "A", "B")
    assert pair["labelA"] == "Alpha"
    assert pair["labelB"] == "Beta"
    assert pair["sizeA"] == 3
    assert pair["sizeB"] == 3
    assert pair["intersection"] == 2
    assert pair["union"] == 4
    assert pair["jaccard"] == 0.5
    assert pair["sharedGenes"] == ["g2", "g3"]
    assert pair["uniqueA"] == ["g1"]
    assert pair["uniqueB"] == ["g4"]


def _three_experiment_fixture() -> OverlapResult:
    a = _exp("A", "Alpha", ["g1", "g2"], ["g3"])
    b = _exp("B", "Beta", ["g2", "g3"], ["g4"])
    c = _exp("C", "Gamma", ["g2"], [])
    return compute_gene_set_overlap([a, b, c], ["A", "B", "C"])


def test_three_experiment_pairwise() -> None:
    result = _three_experiment_fixture()

    assert len(result["pairwise"]) == 3

    ab = _pair(result, "A", "B")
    assert ab["intersection"] == 2
    assert ab["union"] == 4
    assert ab["jaccard"] == 0.5
    assert ab["sharedGenes"] == ["g2", "g3"]
    assert ab["uniqueA"] == ["g1"]
    assert ab["uniqueB"] == ["g4"]

    ac = _pair(result, "A", "C")
    assert ac["intersection"] == 1
    assert ac["union"] == 3
    assert ac["jaccard"] == 0.3333
    assert ac["sharedGenes"] == ["g2"]
    assert ac["uniqueA"] == ["g1", "g3"]
    assert ac["uniqueB"] == []

    bc = _pair(result, "B", "C")
    assert bc["intersection"] == 1
    assert bc["union"] == 3
    assert bc["jaccard"] == 0.3333
    assert bc["sharedGenes"] == ["g2"]
    assert bc["uniqueA"] == ["g3", "g4"]
    assert bc["uniqueB"] == []


def test_three_experiment_universal_and_totals() -> None:
    result = _three_experiment_fixture()

    assert result["universalGenes"] == ["g2"]
    assert result["totalUniqueGenes"] == 4
    assert result["experimentIds"] == ["A", "B", "C"]
    assert result["experimentLabels"] == {"A": "Alpha", "B": "Beta", "C": "Gamma"}


def test_three_experiment_membership() -> None:
    result = _three_experiment_fixture()

    assert _membership(result, "g1")["foundIn"] == 1
    assert _membership(result, "g1")["experiments"] == ["A"]
    g2 = _membership(result, "g2")
    assert g2["foundIn"] == 3
    assert g2["totalExperiments"] == 3
    assert g2["experiments"] == ["A", "B", "C"]
    assert _membership(result, "g3")["foundIn"] == 2
    assert _membership(result, "g3")["experiments"] == ["A", "B"]
    assert _membership(result, "g4")["foundIn"] == 1
    assert _membership(result, "g4")["experiments"] == ["B"]


def test_three_experiment_per_experiment_counts() -> None:
    result = _three_experiment_fixture()

    sa = _summary(result, "A")
    assert sa["totalGenes"] == 3
    assert sa["sharedGenes"] == 2
    assert sa["uniqueGenes"] == 1

    sb = _summary(result, "B")
    assert sb["totalGenes"] == 3
    assert sb["sharedGenes"] == 2
    assert sb["uniqueGenes"] == 1

    sc = _summary(result, "C")
    assert sc["totalGenes"] == 1
    assert sc["sharedGenes"] == 1
    assert sc["uniqueGenes"] == 0


def test_disjoint_sets_jaccard_zero() -> None:
    a = _exp("A", "Alpha", ["g1"], ["g2"])
    b = _exp("B", "Beta", ["g3"], ["g4"])

    result = compute_gene_set_overlap([a, b], ["A", "B"])

    pair = _pair(result, "A", "B")
    assert pair["intersection"] == 0
    assert pair["union"] == 4
    assert pair["jaccard"] == 0.0
    assert pair["sharedGenes"] == []
    assert pair["uniqueA"] == ["g1", "g2"]
    assert pair["uniqueB"] == ["g3", "g4"]
    assert result["universalGenes"] == []
    assert result["totalUniqueGenes"] == 4
    assert _summary(result, "A")["sharedGenes"] == 0
    assert _summary(result, "A")["uniqueGenes"] == 2


def test_identical_sets_jaccard_one() -> None:
    a = _exp("A", "Alpha", ["g1", "g2"], ["g3"])
    b = _exp("B", "Beta", ["g1", "g2"], ["g3"])

    result = compute_gene_set_overlap([a, b], ["A", "B"])

    pair = _pair(result, "A", "B")
    assert pair["intersection"] == 3
    assert pair["union"] == 3
    assert pair["jaccard"] == 1.0
    assert pair["sharedGenes"] == ["g1", "g2", "g3"]
    assert pair["uniqueA"] == []
    assert pair["uniqueB"] == []
    assert result["universalGenes"] == ["g1", "g2", "g3"]
    assert result["totalUniqueGenes"] == 3
    assert _summary(result, "A")["sharedGenes"] == 3
    assert _summary(result, "A")["uniqueGenes"] == 0


def test_empty_result_set() -> None:
    a = _exp("A", "Alpha", [], [])
    b = _exp("B", "Beta", ["g1"], [])

    result = compute_gene_set_overlap([a, b], ["A", "B"])

    pair = _pair(result, "A", "B")
    assert pair["sizeA"] == 0
    assert pair["sizeB"] == 1
    assert pair["intersection"] == 0
    assert pair["union"] == 1
    assert pair["jaccard"] == 0.0
    assert pair["sharedGenes"] == []
    assert pair["uniqueA"] == []
    assert pair["uniqueB"] == ["g1"]
    assert result["universalGenes"] == []
    assert result["totalUniqueGenes"] == 1
    sa = _summary(result, "A")
    assert sa["totalGenes"] == 0
    assert sa["sharedGenes"] == 0
    assert sa["uniqueGenes"] == 0


def test_both_empty_result_sets_jaccard_zero() -> None:
    a = _exp("A", "Alpha", [], [])
    b = _exp("B", "Beta", [], [])

    result = compute_gene_set_overlap([a, b], ["A", "B"])

    pair = _pair(result, "A", "B")
    assert pair["union"] == 0
    assert pair["jaccard"] == 0.0
    assert result["universalGenes"] == []
    assert result["totalUniqueGenes"] == 0
    assert result["geneMembership"] == []


def test_single_experiment_no_pairwise() -> None:
    a = _exp("A", "Alpha", ["g1", "g2"], ["g3"])

    result = compute_gene_set_overlap([a], ["A"])

    assert result["pairwise"] == []
    assert result["universalGenes"] == ["g1", "g2", "g3"]
    assert result["totalUniqueGenes"] == 3
    g1 = _membership(result, "g1")
    assert g1["foundIn"] == 1
    assert g1["totalExperiments"] == 1
    sa = _summary(result, "A")
    assert sa["totalGenes"] == 3
    assert sa["sharedGenes"] == 0
    assert sa["uniqueGenes"] == 3


def test_default_label_falls_back_to_id() -> None:
    a = _exp("A", "", ["g1"], [])
    b = _exp("B", "", ["g1"], [])

    result = compute_gene_set_overlap([a, b], ["A", "B"])

    assert result["experimentLabels"] == {"A": "A", "B": "B"}
    pair = _pair(result, "A", "B")
    assert pair["labelA"] == "A"
    assert pair["labelB"] == "B"
