"""Builders for the WDK search parameter dicts that the seed definitions share."""

import json
from dataclasses import dataclass


def org(names: list[str]) -> str:
    """Encode an organism name list as a WDK JSON-array string."""
    return json.dumps(names)


def go_search_params(
    organism: str,
    go_id: str,
    *,
    evidence: list[str] | None = None,
    go_term_value: str | None = None,
) -> dict[str, str]:
    """Build GenesByGoTerm search parameters. Some sites need a separate term value."""
    if evidence is None:
        evidence = ["Curated", "Computed"]
    return {
        "organism": org([organism]),
        "go_term_evidence": json.dumps(evidence),
        "go_term_slim": "No",
        "go_typeahead": json.dumps([go_id]),
        "go_term": go_term_value if go_term_value is not None else go_id,
    }


def text_search_params(
    organism: str,
    expression: str,
    *,
    fields: list[str] | None = None,
) -> dict[str, str]:
    """Build GenesByText search parameters."""
    if fields is None:
        fields = ["product"]
    return {
        "text_search_organism": org([organism]),
        "text_expression": expression,
        "document_type": "gene",
        "text_fields": json.dumps(fields),
    }


def signal_peptide_params(organism: str) -> dict[str, str]:
    """Build GenesWithSignalPeptide search parameters."""
    return {"organism": org([organism])}


def transmembrane_params(
    organism: str,
    min_tm: str,
    max_tm: str,
) -> dict[str, str]:
    """Build GenesByTransmembraneDomains search parameters."""
    return {
        "organism": org([organism]),
        "min_tm": min_tm,
        "max_tm": max_tm,
    }


def mol_weight_params(
    organism: str,
    min_mw: str,
    max_mw: str,
) -> dict[str, str]:
    """Build GenesByMolecularWeight search parameters."""
    return {
        "organism": org([organism]),
        "min_molecular_weight": min_mw,
        "max_molecular_weight": max_mw,
    }


def ec_search_params(
    organism: str,
    *,
    ec_number: str,
    ec_sources: list[str],
    ec_wildcard: str = "No",
) -> dict[str, str]:
    """Build GenesByEcNumber search parameters."""
    return {
        "organism": org([organism]),
        "ec_source": json.dumps(ec_sources),
        "ec_number_pattern": ec_number,
        "ec_wildcard": ec_wildcard,
    }


def gene_type_params(
    organism: str,
    gene_type: str = "protein coding",
) -> dict[str, str]:
    """Build GenesByGeneType search parameters."""
    return {
        "organism": org([organism]),
        "geneType": json.dumps([gene_type]),
        "includePseudogenes": "No",
    }


def location_params(
    organism: str,
    chromosome: str,
    start: str,
    end: str,
) -> dict[str, str]:
    """Build GenesByLocation search parameters."""
    return {
        "organismSinglePick": org([organism]),
        "chromosomeOptional": chromosome,
        "sequenceId": "",
        "start_point": start,
        "end_point": end,
    }


def exon_count_params(
    organism: str,
    min_exons: str,
    max_exons: str,
) -> dict[str, str]:
    """Build GenesByExonCount search parameters."""
    return {
        "organism": org([organism]),
        "scope": "Gene",
        "num_exons_gte": min_exons,
        "num_exons_lte": max_exons,
    }


@dataclass
class RNASeqOptions:
    """Optional parameters for an RNA-Seq fold-change search."""

    hard_floor: str = "0"
    fold_change: str = "2"
    protein_coding: str = "yes"
    ref_op: str = "average1"
    comp_op: str = "average1"


def rnaseq_fc_params(
    dataset_url: str,
    profileset: str,
    direction: str,
    ref_samples: list[str],
    comp_samples: list[str],
    options: RNASeqOptions | None = None,
) -> dict[str, str]:
    """Build RNA-Seq fold-change search parameters."""
    opts = options or RNASeqOptions()
    return {
        "dataset_url": dataset_url,
        "profileset_generic": profileset,
        "regulated_dir": direction,
        "samples_fc_ref_generic": json.dumps(ref_samples),
        "min_max_avg_ref": opts.ref_op,
        "samples_fc_comp_generic": json.dumps(comp_samples),
        "min_max_avg_comp": opts.comp_op,
        "fold_change": opts.fold_change,
        "hard_floor": opts.hard_floor,
        "protein_coding_only": opts.protein_coding,
    }


def paralog_count_params(
    organism: str,
    min_p: str,
    max_p: str,
) -> dict[str, str]:
    """Build GenesByParalogCount search parameters."""
    return {
        "organism": org([organism]),
        "num_paralogs": json.dumps({"min": min_p, "max": max_p}),
    }
