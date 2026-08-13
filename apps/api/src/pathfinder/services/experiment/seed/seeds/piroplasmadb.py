"""Seed definitions for PiroplasmaDB, scoped to the Babesia bovis T2Bo
reference genome."""

from pathfinder.services.experiment.seed.helpers import (
    go_search_params,
    signal_peptide_params,
    text_search_params,
    transmembrane_params,
)
from pathfinder.services.experiment.seed.types import ControlSetDef, SeedDef

BB_ORG = "Babesia bovis T2Bo"

# Variant erythrocyte surface antigens, which drive immune evasion.
BB_VESA = [
    "BBOV_I000010",
    "BBOV_I000020",
    "BBOV_I000030",
    "BBOV_I000050",
    "BBOV_I000060",
    "BBOV_I000070",
    "BBOV_I001140",
    "BBOV_I001190",
    "BBOV_I001320",
    "BBOV_I001330",
    "BBOV_I001340",
    "BBOV_I001410",
    "BBOV_I001430",
    "BBOV_I001440",
    "BBOV_I002990",
    "BBOV_I003000",
    "BBOV_I003010",
    "BBOV_I003020",
    "BBOV_I003060",
    "BBOV_I003830",
    "BBOV_I003840",
    "BBOV_I003870",
    "BBOV_I003900",
    "BBOV_I003910",
    "BBOV_I004510",
    "BBOV_I004520",
    "BBOV_I005110",
    "BBOV_I005120",
    "BBOV_I005140",
    "BBOV_I005160",
    "BBOV_I005180",
    "BBOV_I005190",
    "BBOV_I005805",
    "BBOV_I005815",
    "BBOV_I005825",
    "BBOV_I005835",
    "BBOV_I005845",
    "BBOV_I005865",
    "BBOV_I005875",
    "BBOV_I005885",
    "BBOV_I005895",
    "BBOV_I005905",
    "BBOV_I005915",
    "BBOV_I005925",
    "BBOV_I005935",
    "BBOV_I005945",
    "BBOV_I005955",
    "BBOV_II000030",
    "BBOV_II000040",
    "BBOV_II000100",
]

# Kinases, GO:0004672 (protein kinase activity).
BB_KINASES = [
    "BBOV_I000170",
    "BBOV_I000350",
    "BBOV_I001560",
    "BBOV_I001950",
    "BBOV_I004190",
    "BBOV_I004215",
    "BBOV_I004690",
    "BBOV_II000610",
    "BBOV_II000760",
    "BBOV_II004380",
    "BBOV_II005282",
    "BBOV_II006890",
    "BBOV_II007230",
    "BBOV_II007390",
    "BBOV_II007640",
    "BBOV_III001400",
    "BBOV_III002900",
    "BBOV_III003120",
    "BBOV_III003210",
    "BBOV_III003600",
    "BBOV_III004260",
    "BBOV_III004870",
    "BBOV_III005470",
    "BBOV_III005740",
    "BBOV_III006430",
    "BBOV_III007370",
    "BBOV_III007550",
    "BBOV_III007790",
    "BBOV_III008760",
    "BBOV_III008880",
    "BBOV_III009120",
    "BBOV_III009390",
    "BBOV_III009650",
    "BBOV_III010080",
    "BBOV_IV001230",
    "BBOV_IV003210",
    "BBOV_IV004470",
    "BBOV_IV005520",
    "BBOV_IV006150",
    "BBOV_IV007830",
    "BBOV_IV008300",
    "BBOV_IV008960",
    "BBOV_IV009470",
    "BBOV_IV010230",
    "BBOV_IV010480",
    "BBOV_IV010650",
    "BBOV_IV010690",
    "BBOV_IV011370",
    "BBOV_IV012050",
]

# Peptidases, GO:0008233 (peptidase activity).
BB_PEPTIDASES = [
    "BBOV_I000200",
    "BBOV_I000540",
    "BBOV_I002820",
    "BBOV_I003700",
    "BBOV_I004260",
    "BBOV_II000170",
    "BBOV_II000870",
    "BBOV_II001460",
    "BBOV_II001800",
    "BBOV_II002340",
    "BBOV_II003480",
    "BBOV_II004070",
    "BBOV_II004090",
    "BBOV_II004450",
    "BBOV_II005180",
    "BBOV_II005380",
    "BBOV_II005540",
    "BBOV_II005930",
    "BBOV_II005940",
    "BBOV_II005950",
    "BBOV_II005970",
    "BBOV_II006070",
    "BBOV_II006080",
    "BBOV_II006100",
    "BBOV_II007480",
    "BBOV_III000270",
    "BBOV_III000530",
    "BBOV_III000740",
    "BBOV_III001640",
    "BBOV_III001650",
    "BBOV_III002280",
    "BBOV_III002610",
    "BBOV_III005230",
    "BBOV_III006020",
    "BBOV_III006180",
    "BBOV_III006660",
    "BBOV_III007670",
    "BBOV_III008630",
    "BBOV_III008650",
    "BBOV_III010070",
    "BBOV_III010190",
    "BBOV_III010365",
    "BBOV_III010630",
    "BBOV_IV000290",
    "BBOV_IV000310",
    "BBOV_IV001260",
    "BBOV_IV001730",
    "BBOV_IV001950",
    "BBOV_IV003800",
    "BBOV_IV003850",
]

# Ribosomal proteins, GO:0003735 (structural constituent of ribosome).
BB_RIBOSOMAL = [
    "BBOV_I000230",
    "BBOV_I000700",
    "BBOV_I001510",
    "BBOV_I002240",
    "BBOV_I002850",
    "BBOV_I003160",
    "BBOV_I003410",
    "BBOV_I003470",
    "BBOV_I004110",
    "BBOV_I004730",
    "BBOV_II000880",
    "BBOV_II001050",
    "BBOV_II001060",
    "BBOV_II001650",
    "BBOV_II001860",
    "BBOV_II001920",
    "BBOV_II002030",
    "BBOV_II002670",
    "BBOV_II002750",
    "BBOV_II002800",
    "BBOV_II003110",
    "BBOV_II003160",
    "BBOV_II003270",
    "BBOV_II003460",
    "BBOV_II003660",
    "BBOV_II004020",
    "BBOV_II004570",
    "BBOV_II004580",
    "BBOV_II004750",
    "BBOV_II005040",
    "BBOV_II005090",
    "BBOV_II005740",
    "BBOV_II006110",
    "BBOV_II006670",
    "BBOV_II007060",
    "BBOV_II007110",
    "BBOV_II007320",
    "BBOV_III000550",
    "BBOV_III000770",
    "BBOV_III000970",
    "BBOV_III000980",
    "BBOV_III001110",
    "BBOV_III001140",
    "BBOV_III001170",
    "BBOV_III001250",
    "BBOV_III001350",
    "BBOV_III001480",
    "BBOV_III001580",
    "BBOV_III001790",
    "BBOV_III001970",
]

# Heat shock proteins.
BB_HEAT_SHOCK = [
    "BBOV_II003640",
    "BBOV_II003920",
    "BBOV_III004230",
    "BBOV_III010010",
    "BBOV_IV003490",
    "BBOV_IV009880",
    "BBOV_IV010060",
    "BBOV_IV010880",
]

# Spherical body proteins.
BB_SPHERICAL_BODY = [
    "BBOV_I004210",
    "BBOV_II000680",
    "BBOV_II000740",
    "BBOV_III005600",
    "BBOV_III005630",
    "BBOV_III005790",
    "BBOV_III005830",
    "BBOV_III005840",
    "BBOV_III005860",
    "BBOV_III006460",
    "BBOV_III006480",
    "BBOV_III006500",
    "BBOV_III006520",
    "BBOV_III006540",
    "BBOV_IV005390",
]

# Merozoite surface proteins.
BB_MEROZOITE = [
    "BBOV_I002990",
    "BBOV_I003000",
    "BBOV_I003010",
    "BBOV_I003020",
    "BBOV_I003060",
]

# Rhoptry proteins.
BB_RHOPTRY = [
    "BBOV_I001630",
    "BBOV_IV009860",
    "BBOV_IV009870",
    "BBOV_IV011430",
]


SEEDS: list[SeedDef] = [
    SeedDef(
        name="BB VESA Immune Evasion Surface Proteins",
        description=(
            "5-node strategy for B. bovis VESA immune evasion analysis. "
            "INTERSECT of variant erythrocyte surface antigen text hits with "
            "transmembrane-domain proteins to confirm surface exposure; "
            "MINUS ribosomal genes (housekeeping exclusion). "
            "Models research into antigenic variation and immune evasion "
            "in bovine babesiosis."
        ),
        site_id="piroplasmadb",
        step_tree={
            "id": "root_minus_ribo",
            "displayName": "VESA Surface (no ribosomal)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "vesa_tm_intersect",
                "displayName": "VESA with TM domains",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "leaf_vesa_text",
                    "displayName": "VESA (text search)",
                    "searchName": "GenesByText",
                    "parameters": text_search_params(
                        BB_ORG, "variant erythrocyte surface antigen"
                    ),
                },
                "secondaryInput": {
                    "id": "leaf_tm",
                    "displayName": "Transmembrane (1-20 TM)",
                    "searchName": "GenesByTransmembraneDomains",
                    "parameters": transmembrane_params(BB_ORG, "1", "20"),
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal",
                "displayName": "Ribosomal (GO:0003735)",
                "searchName": "GenesByGoTerm",
                "parameters": go_search_params(BB_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="B. bovis VESA Immune Evasion (curated)",
            positive_ids=BB_VESA[:40],
            negative_ids=BB_RIBOSOMAL[:40],
            provenance_notes=(
                "Positives: variant erythrocyte surface antigen (VESA) genes — "
                "the primary immune evasion surface proteins of B. bovis. "
                "Negatives: ribosomal proteins — ubiquitous housekeeping genes "
                "not involved in immune evasion."
            ),
            tags=["babesia", "vesa", "immune-evasion", "seed"],
        ),
    ),
    SeedDef(
        name="BB Drug Target Discovery",
        description=(
            "9-node strategy for B. bovis drug target identification. "
            "UNION of kinases and peptidases; INTERSECT with secreted or "
            "transmembrane proteins for accessible targets. "
            "MINUS ribosomal genes (housekeeping exclusion). "
            "Models anti-babesial drug discovery pipelines targeting "
            "enzymes accessible to therapeutic compounds."
        ),
        site_id="piroplasmadb",
        step_tree={
            "id": "root_minus_ribo",
            "displayName": "Drug Targets (no ribosomal)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "accessible_enzymes",
                "displayName": "Accessible Enzymes",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "enzyme_union",
                    "displayName": "Kinases + Peptidases",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_kinases",
                        "displayName": "Protein Kinases (GO:0004672)",
                        "searchName": "GenesByGoTerm",
                        "parameters": go_search_params(BB_ORG, "GO:0004672"),
                    },
                    "secondaryInput": {
                        "id": "leaf_peptidases",
                        "displayName": "Peptidases (GO:0008233)",
                        "searchName": "GenesByGoTerm",
                        "parameters": go_search_params(BB_ORG, "GO:0008233"),
                    },
                },
                "secondaryInput": {
                    "id": "accessible_union",
                    "displayName": "Secreted or Membrane",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_signal_peptide",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": signal_peptide_params(BB_ORG),
                    },
                    "secondaryInput": {
                        "id": "leaf_tm",
                        "displayName": "Transmembrane (1-20 TM)",
                        "searchName": "GenesByTransmembraneDomains",
                        "parameters": transmembrane_params(BB_ORG, "1", "20"),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal",
                "displayName": "Ribosomal (GO:0003735)",
                "searchName": "GenesByGoTerm",
                "parameters": go_search_params(BB_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="B. bovis Drug Targets (curated)",
            positive_ids=BB_KINASES[:25] + BB_PEPTIDASES[:25],
            negative_ids=BB_RIBOSOMAL[:50],
            provenance_notes=(
                "Positives: protein kinases and peptidases — validated enzyme "
                "families used as anti-parasitic drug targets. "
                "Negatives: ribosomal proteins — essential housekeeping genes "
                "conserved across all eukaryotes, poor drug targets."
            ),
            tags=["babesia", "drug-target", "seed"],
        ),
    ),
    SeedDef(
        name="BB Secreted Virulence Factors",
        description=(
            "7-node strategy for B. bovis secreted virulence factor discovery. "
            "UNION of VESA, spherical body, and rhoptry text hits; "
            "INTERSECT with signal peptide for confirmed secretory pathway. "
            "Models research into the parasite's pathogenic arsenal "
            "for vaccine and diagnostic target identification."
        ),
        site_id="piroplasmadb",
        step_tree={
            "id": "root_sp_intersect",
            "displayName": "Secreted Virulence Factors",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "virulence_union_outer",
                "displayName": "All Virulence Families",
                "operator": "UNION",
                "primaryInput": {
                    "id": "vesa_sbc_union",
                    "displayName": "VESA + Spherical Body",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_vesa",
                        "displayName": "VESA (text search)",
                        "searchName": "GenesByText",
                        "parameters": text_search_params(
                            BB_ORG, "variant erythrocyte surface antigen"
                        ),
                    },
                    "secondaryInput": {
                        "id": "leaf_sbc",
                        "displayName": "Spherical Body (text search)",
                        "searchName": "GenesByText",
                        "parameters": text_search_params(BB_ORG, "spherical body"),
                    },
                },
                "secondaryInput": {
                    "id": "leaf_rhoptry",
                    "displayName": "Rhoptry (text search)",
                    "searchName": "GenesByText",
                    "parameters": text_search_params(BB_ORG, "rhoptry"),
                },
            },
            "secondaryInput": {
                "id": "leaf_signal_peptide",
                "displayName": "Signal Peptide",
                "searchName": "GenesWithSignalPeptide",
                "parameters": signal_peptide_params(BB_ORG),
            },
        },
        control_set=ControlSetDef(
            name="B. bovis Secreted Virulence (curated)",
            positive_ids=BB_VESA[:25] + BB_SPHERICAL_BODY,
            negative_ids=BB_RIBOSOMAL[:40],
            provenance_notes=(
                "Positives: VESA surface antigens and spherical body proteins — "
                "secreted virulence factors involved in host-parasite interaction. "
                "Negatives: ribosomal proteins — housekeeping genes not secreted."
            ),
            tags=["babesia", "virulence", "secreted", "seed"],
        ),
    ),
    SeedDef(
        name="BB Membrane Transport Network",
        description=(
            "7-node strategy for B. bovis membrane transport and stress response. "
            "INTERSECT of transport process (GO:0006810) with transmembrane "
            "domain proteins; UNION with heat shock text hits for stress "
            "response transporters. MINUS translation (GO:0006412) to exclude "
            "ribosomal machinery. Models nutrient uptake and stress adaptation."
        ),
        site_id="piroplasmadb",
        step_tree={
            "id": "root_minus_translation",
            "displayName": "Transport Network (no translation)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "transport_hsp_union",
                "displayName": "Transporters + Heat Shock",
                "operator": "UNION",
                "primaryInput": {
                    "id": "transport_tm_intersect",
                    "displayName": "Membrane Transporters",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_transport",
                        "displayName": "Transport (GO:0006810)",
                        "searchName": "GenesByGoTerm",
                        "parameters": go_search_params(BB_ORG, "GO:0006810"),
                    },
                    "secondaryInput": {
                        "id": "leaf_tm",
                        "displayName": "Transmembrane (1-20 TM)",
                        "searchName": "GenesByTransmembraneDomains",
                        "parameters": transmembrane_params(BB_ORG, "1", "20"),
                    },
                },
                "secondaryInput": {
                    "id": "leaf_heat_shock",
                    "displayName": "Heat Shock (text search)",
                    "searchName": "GenesByText",
                    "parameters": text_search_params(BB_ORG, "heat shock"),
                },
            },
            "secondaryInput": {
                "id": "leaf_translation",
                "displayName": "Translation (GO:0006412)",
                "searchName": "GenesByGoTerm",
                "parameters": go_search_params(BB_ORG, "GO:0006412"),
            },
        },
        control_set=ControlSetDef(
            name="B. bovis Membrane Transport (curated)",
            positive_ids=BB_HEAT_SHOCK + BB_KINASES[:30],
            negative_ids=BB_RIBOSOMAL[:40],
            provenance_notes=(
                "Positives: heat shock proteins and kinases — stress-responsive "
                "membrane-associated proteins in B. bovis. "
                "Negatives: ribosomal proteins — translation machinery excluded "
                "as housekeeping."
            ),
            tags=["babesia", "transport", "stress", "seed"],
        ),
    ),
    SeedDef(
        name="BB Surface Antigen Repertoire",
        description=(
            "9-node strategy for B. bovis surface antigen repertoire analysis. "
            "UNION of VESA text hits with signal-peptide + transmembrane "
            "intersect (MINUS kinases to remove signaling enzymes). "
            "MINUS ribosomal genes. Models comprehensive surface proteome "
            "characterization for vaccine candidate discovery."
        ),
        site_id="piroplasmadb",
        step_tree={
            "id": "root_minus_ribo",
            "displayName": "Surface Antigens (no ribosomal)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "surface_union",
                "displayName": "VESA + Non-Kinase Surface",
                "operator": "UNION",
                "primaryInput": {
                    "id": "leaf_vesa",
                    "displayName": "VESA (text search)",
                    "searchName": "GenesByText",
                    "parameters": text_search_params(
                        BB_ORG, "variant erythrocyte surface antigen"
                    ),
                },
                "secondaryInput": {
                    "id": "surface_minus_kinase",
                    "displayName": "Surface (no kinases)",
                    "operator": "MINUS",
                    "primaryInput": {
                        "id": "sp_tm_intersect",
                        "displayName": "Signal Peptide + TM",
                        "operator": "INTERSECT",
                        "primaryInput": {
                            "id": "leaf_signal_peptide",
                            "displayName": "Signal Peptide",
                            "searchName": "GenesWithSignalPeptide",
                            "parameters": signal_peptide_params(BB_ORG),
                        },
                        "secondaryInput": {
                            "id": "leaf_tm",
                            "displayName": "Transmembrane (1-20 TM)",
                            "searchName": "GenesByTransmembraneDomains",
                            "parameters": transmembrane_params(BB_ORG, "1", "20"),
                        },
                    },
                    "secondaryInput": {
                        "id": "leaf_kinases",
                        "displayName": "Kinases (GO:0004672)",
                        "searchName": "GenesByGoTerm",
                        "parameters": go_search_params(BB_ORG, "GO:0004672"),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal",
                "displayName": "Ribosomal (GO:0003735)",
                "searchName": "GenesByGoTerm",
                "parameters": go_search_params(BB_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="B. bovis Surface Antigens (curated)",
            positive_ids=BB_VESA[:50],
            negative_ids=BB_KINASES[:25] + BB_RIBOSOMAL[:25],
            provenance_notes=(
                "Positives: VESA family — the dominant surface antigen repertoire "
                "of B. bovis responsible for antigenic variation. "
                "Negatives: kinases and ribosomal proteins — intracellular "
                "signaling and housekeeping, not surface-exposed."
            ),
            tags=["babesia", "surface-antigen", "seed"],
        ),
    ),
    SeedDef(
        name="BB Erythrocyte Invasion Machinery",
        description=(
            "9-node strategy for B. bovis erythrocyte invasion machinery. "
            "UNION of merozoite, rhoptry, and spherical body text hits "
            "with kinase + signal peptide intersect for secreted signaling. "
            "MINUS ribosomal genes. Models the molecular machinery "
            "driving red blood cell invasion in bovine babesiosis."
        ),
        site_id="piroplasmadb",
        step_tree={
            "id": "root_minus_ribo",
            "displayName": "Invasion Machinery (no ribosomal)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "invasion_union",
                "displayName": "Invasion Components",
                "operator": "UNION",
                "primaryInput": {
                    "id": "organelle_union",
                    "displayName": "Merozoite + Secretory Organelles",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_merozoite",
                        "displayName": "Merozoite (text search)",
                        "searchName": "GenesByText",
                        "parameters": text_search_params(BB_ORG, "merozoite"),
                    },
                    "secondaryInput": {
                        "id": "rhoptry_sbc_union",
                        "displayName": "Rhoptry + Spherical Body",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_rhoptry",
                            "displayName": "Rhoptry (text search)",
                            "searchName": "GenesByText",
                            "parameters": text_search_params(BB_ORG, "rhoptry"),
                        },
                        "secondaryInput": {
                            "id": "leaf_sbc",
                            "displayName": "Spherical Body (text search)",
                            "searchName": "GenesByText",
                            "parameters": text_search_params(BB_ORG, "spherical body"),
                        },
                    },
                },
                "secondaryInput": {
                    "id": "kinase_sp_intersect",
                    "displayName": "Secreted Kinases",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_kinases",
                        "displayName": "Kinases (GO:0004672)",
                        "searchName": "GenesByGoTerm",
                        "parameters": go_search_params(BB_ORG, "GO:0004672"),
                    },
                    "secondaryInput": {
                        "id": "leaf_signal_peptide",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": signal_peptide_params(BB_ORG),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal",
                "displayName": "Ribosomal (GO:0003735)",
                "searchName": "GenesByGoTerm",
                "parameters": go_search_params(BB_ORG, "GO:0003735"),
            },
        },
        control_set=ControlSetDef(
            name="B. bovis Erythrocyte Invasion (curated)",
            positive_ids=(
                BB_MEROZOITE + BB_RHOPTRY + BB_SPHERICAL_BODY + BB_KINASES[:20]
            ),
            negative_ids=BB_RIBOSOMAL[:40],
            provenance_notes=(
                "Positives: merozoite surface, rhoptry, spherical body, and "
                "secreted kinase proteins — the core invasion machinery of "
                "B. bovis for red blood cell entry. "
                "Negatives: ribosomal proteins — housekeeping translation "
                "machinery not involved in invasion."
            ),
            tags=["babesia", "invasion", "seed"],
        ),
    ),
]
