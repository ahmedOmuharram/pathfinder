"""Seed definitions for AmoebaDB.

Covers Entamoeba histolytica HM-1:IMSS with real gene IDs verified against
AmoebaDB (Mar 2026), biologically meaningful search configurations targeting:
  - Cysteine proteases (CP family): major virulence factors for tissue invasion
  - Gal/GalNAc lectins: host cell adhesion, critical for pathogenesis
  - Amoebapores: pore-forming peptides (saposin-like), cytolysis of host cells
  - Trogocytosis/phagocytosis: actin cytoskeleton, Rho GTPases
  - Encystation: chitin synthase, Jacob lectins, cyst wall glycoproteins
  - Drug targets: thioredoxin/reductase, alcohol dehydrogenases (metronidazole)
  - Signaling: Rho GTPases, kinases, phosphatases
"""

import json

from veupath_chatbot.services.experiment.seed.types import ControlSetDef, SeedDef

# ---------------------------------------------------------------------------
# Organism constants
# ---------------------------------------------------------------------------

EH_ORG = "Entamoeba histolytica HM-1:IMSS"

# ---------------------------------------------------------------------------
# Gene ID lists (all real VEuPathDB IDs, verified Mar 2026)
# ---------------------------------------------------------------------------

# Cysteine proteases — CP family, papain-family, calpain (virulence factors)
EH_CYSTEINE_PROTEASES = [
    "EHI_030720",
    "EHI_062480",
    "EHI_084060",
    "EHI_091450",
    "EHI_097900",
    "EHI_108240",
    "EHI_117650",
    "EHI_121160",
    "EHI_123950",
    "EHI_126170",
    "EHI_140220",
    "EHI_159610",
    "EHI_160330",
    "EHI_179600",
    "EHI_180170",
    "EHI_180650",
    "EHI_181230",
    "EHI_182260",
    "EHI_197490",
    "EHI_200690",
    "EHI_045290",
    "EHI_064430",
    "EHI_006920",
    "EHI_138460",
    "EHI_010850",
    "EHI_033710",
    "EHI_039610",
    "EHI_050570",
    "EHI_096740",
    "EHI_151400",
    "EHI_151440",
    "EHI_168240",
    "EHI_074180",
    # Cysteine protease inhibitors (EhICP1/2)
    "EHI_040460",
    "EHI_159600",
]

# Gal/GalNAc lectins and galactose-binding lectins — adhesion, virulence
EH_LECTINS = [
    "EHI_058330",
    "EHI_006980",
    "EHI_012270",
    "EHI_065330",
    "EHI_148790",
    "EHI_183000",
    "EHI_046650",
    "EHI_159870",
    "EHI_009250",
    "EHI_027800",
    "EHI_035690",
    "EHI_104370",
    "EHI_133900",
    "EHI_152000",
    "EHI_183400",
]

# Amoebapores and pore-forming peptides — saposin-like, cytolysis
EH_AMOEBAPORES = [
    "EHI_118270",  # amoebapore C
    "EHI_159480",  # amoebapore A precursor
    "EHI_169350",  # nonpathogenic pore-forming peptide precursor
    "EHI_194540",  # amoebapore B precursor
    "EHI_118190",  # saposin-domain hypothetical
    "EHI_048580",  # saposin-domain hypothetical
    "EHI_169600",  # saposin-domain hypothetical
    "EHI_184010",  # saposin-domain hypothetical
]

# Kinases — protein/tyrosine/casein kinases (signaling, invasion)
EH_KINASES = [
    "EHI_148280",
    "EHI_002790",
    "EHI_004780",
    "EHI_004790",
    "EHI_006750",
    "EHI_006800",
    "EHI_009580",
    "EHI_011170",
    "EHI_011220",
    "EHI_011510",
    "EHI_011920",
    "EHI_014100",
    "EHI_015960",
    "EHI_017760",
    "EHI_023010",
    "EHI_023610",
    "EHI_025280",
    "EHI_030120",
    "EHI_030420",
    "EHI_035500",
    "EHI_035570",
    "EHI_043140",
    "EHI_044470",
    "EHI_044640",
    "EHI_049390",
    "EHI_050140",
    "EHI_050480",
    "EHI_050650",
    "EHI_050820",
    "EHI_051910",
    "EHI_051920",
    "EHI_053040",
    "EHI_053060",
    "EHI_055710",
    "EHI_057680",
    "EHI_058930",
    "EHI_064490",
    "EHI_065500",
    "EHI_066510",
    "EHI_067070",
    "EHI_068160",
    "EHI_068350",
    "EHI_068600",
    "EHI_070110",
    "EHI_071320",
    "EHI_073490",
    "EHI_073660",
    "EHI_074740",
    "EHI_074780",
    "EHI_075540",
    "EHI_078200",
    "EHI_083440",
    "EHI_086050",
    "EHI_087600",
    "EHI_087800",
    "EHI_088490",
    "EHI_092260",
    "EHI_092300",
    "EHI_092530",
    "EHI_095940",
    "EHI_097640",
    "EHI_098240",
    "EHI_103290",
    "EHI_103610",
    "EHI_103810",
    "EHI_104670",
    "EHI_105130",
    "EHI_105830",
    "EHI_106700",
    "EHI_110490",
    "EHI_110650",
    "EHI_114420",
    "EHI_115050",
    "EHI_117590",
    "EHI_117680",
    "EHI_118080",
    "EHI_118410",
    "EHI_119250",
    "EHI_123720",
    "EHI_123840",
]

# Transporters — ABC, MFS, cation, amino acid, nucleoside transporters
EH_TRANSPORTERS = [
    "EHI_005050",
    "EHI_008030",
    "EHI_010080",
    "EHI_015330",
    "EHI_017040",
    "EHI_025250",
    "EHI_026390",
    "EHI_069990",
    "EHI_078700",
    "EHI_110700",
    "EHI_110730",
    "EHI_112010",
    "EHI_114390",
    "EHI_124840",
    "EHI_147510",
    "EHI_148880",
    "EHI_153380",
    "EHI_166890",
    "EHI_169580",
    "EHI_175940",
    "EHI_177580",
    "EHI_185600",
    "EHI_197410",
    "EHI_197670",
    "EHI_005130",
    "EHI_008110",
    "EHI_051700",
    "EHI_051720",
    "EHI_067960",
    "EHI_072120",
    "EHI_103540",
    "EHI_110150",
    "EHI_110390",
    "EHI_115320",
    "EHI_117260",
    "EHI_129510",
    "EHI_134010",
    "EHI_134730",
    "EHI_141000",
    "EHI_151940",
    "EHI_153450",
    "EHI_156230",
    "EHI_162180",
    "EHI_165090",
    "EHI_173950",
    "EHI_182490",
    "EHI_182750",
    "EHI_185430",
    "EHI_190460",
    "EHI_193310",
    "EHI_194200",
    "EHI_194310",
    "EHI_020320",
    "EHI_050270",
    "EHI_068400",
    "EHI_100280",
    "EHI_124580",
    "EHI_175440",
    "EHI_011380",
    "EHI_011970",
    "EHI_048980",
    "EHI_111850",
    "EHI_195130",
    "EHI_198990",
    "EHI_199020",
    "EHI_200200",
    "EHI_041050",
    "EHI_050900",
    "EHI_068590",
    "EHI_107010",
    "EHI_122920",
    "EHI_030600",
    "EHI_103680",
    "EHI_152760",
]

# Ribosomal proteins — structural components of ribosomes
EH_RIBOSOMAL = [
    "EHI_003940",
    "EHI_008210",
    "EHI_008620",
    "EHI_009680",
    "EHI_009810",
    "EHI_012360",
    "EHI_015320",
    "EHI_017700",
    "EHI_020370",
    "EHI_023400",
    "EHI_031400",
    "EHI_035600",
    "EHI_037130",
    "EHI_038580",
    "EHI_040660",
    "EHI_044550",
    "EHI_044590",
    "EHI_044810",
    "EHI_044830",
    "EHI_048990",
    "EHI_054740",
    "EHI_069490",
    "EHI_074800",
    "EHI_078300",
    "EHI_079190",
    "EHI_086120",
    "EHI_088600",
    "EHI_090020",
    "EHI_095610",
    "EHI_098470",
    "EHI_098780",
    "EHI_098840",
    "EHI_099730",
    "EHI_114400",
    "EHI_118170",
    "EHI_124300",
    "EHI_125780",
    "EHI_126110",
    "EHI_126250",
    "EHI_127330",
    "EHI_131940",
    "EHI_135060",
    "EHI_137870",
    "EHI_146560",
    "EHI_147710",
    "EHI_148820",
    "EHI_149000",
    "EHI_152080",
    "EHI_152610",
    "EHI_156690",
    "EHI_158270",
    "EHI_163670",
    "EHI_164870",
    "EHI_167050",
    "EHI_169100",
    "EHI_177470",
    "EHI_179000",
    "EHI_182590",
    "EHI_182850",
    "EHI_185010",
    "EHI_187740",
    "EHI_189150",
    "EHI_189940",
    "EHI_192090",
    "EHI_199970",
    "EHI_200090",
    "EHI_200850",
    "EHI_000510",
    "EHI_000590",
    "EHI_004200",
    "EHI_005890",
    "EHI_006860",
    "EHI_008010",
    "EHI_008650",
    "EHI_010650",
    "EHI_012480",
    "EHI_013890",
    "EHI_014110",
    "EHI_015310",
    "EHI_020280",
    "EHI_020300",
    "EHI_020310",
    "EHI_021450",
    "EHI_023840",
    "EHI_025590",
    "EHI_025600",
    "EHI_025830",
    "EHI_026410",
    "EHI_029530",
    "EHI_030710",
    "EHI_030760",
    "EHI_035090",
    "EHI_035440",
    "EHI_035460",
    "EHI_036530",
    "EHI_038620",
    "EHI_038860",
    "EHI_039010",
    "EHI_040800",
    "EHI_040830",
]

# Heat shock proteins — stress response, chaperones
EH_HEAT_SHOCK = [
    "EHI_017350",
    "EHI_022620",
    "EHI_028920",
    "EHI_034710",
    "EHI_042860",
    "EHI_072140",
    "EHI_135750",
    "EHI_156560",
    "EHI_001950",
    "EHI_002560",
    "EHI_008600",
    "EHI_013550",
    "EHI_015390",
    "EHI_021780",
    "EHI_026590",
    "EHI_034960",
    "EHI_043000",
    "EHI_052860",
    "EHI_059700",
    "EHI_061640",
    "EHI_064470",
    "EHI_065320",
    "EHI_065770",
    "EHI_070450",
    "EHI_071800",
    "EHI_073540",
    "EHI_076480",
    "EHI_082200",
    "EHI_086390",
    "EHI_091570",
    "EHI_092830",
    "EHI_094470",
    "EHI_102270",
    "EHI_104330",
    "EHI_108130",
    "EHI_111810",
    "EHI_112590",
    "EHI_113410",
    "EHI_123490",
    "EHI_125830",
    "EHI_126180",
    "EHI_130160",
    "EHI_132530",
    "EHI_132540",
    "EHI_133950",
    "EHI_137670",
    "EHI_148990",
    "EHI_150770",
    "EHI_155370",
    "EHI_155490",
    "EHI_159140",
    "EHI_178230",
    "EHI_180380",
    "EHI_183680",
    "EHI_185120",
    "EHI_185420",
    "EHI_188610",
    "EHI_192440",
    "EHI_196940",
    "EHI_197860",
    "EHI_198320",
    "EHI_201260",
    "EHI_007150",
    "EHI_013760",
    "EHI_055680",
    "EHI_100810",
    "EHI_101120",
    "EHI_127700",
    "EHI_163480",
    "EHI_175600",
    "EHI_193390",
    "EHI_199590",
]

# Surface antigens — ariel1, SREHP, variant surface proteins
EH_SURFACE = [
    "EHI_005260",
    "EHI_028430",
    "EHI_030860",
    "EHI_036490",
    "EHI_041270",
    "EHI_057430",
    "EHI_080200",
    "EHI_091840",
    "EHI_098180",
    "EHI_101730",
    "EHI_116260",
    "EHI_123850",
    "EHI_128600",
    "EHI_131360",
    "EHI_160750",
    "EHI_169800",
    "EHI_172850",
    "EHI_186470",
    "EHI_015380",
    "EHI_042870",
    "EHI_069390",
    "EHI_197360",
    "EHI_200230",
]

# Rho family GTPases — signaling for invasion, motility, trogocytosis
EH_RHO_GTPASES = [
    "EHI_012240",
    "EHI_013260",
    "EHI_015440",
    "EHI_029020",
    "EHI_046630",
    "EHI_052150",
    "EHI_067220",
    "EHI_067390",
    "EHI_068240",
    "EHI_070730",
    "EHI_087390",
    "EHI_126310",
    "EHI_129750",
    "EHI_135450",
    "EHI_140190",
    "EHI_144600",
    "EHI_146180",
    "EHI_153460",
    "EHI_178680",
    "EHI_180430",
    "EHI_181250",
    "EHI_190440",
    "EHI_192450",
    "EHI_194390",
    "EHI_197840",
    "EHI_018960",
    "EHI_053210",
    "EHI_035940",
    "EHI_056450",
    "EHI_069180",
    "EHI_092650",
    "EHI_131930",
    "EHI_146500",
    "EHI_187110",
]

# Rab family GTPases — vesicular trafficking, phagocytosis
EH_RAB_GTPASES = [
    "EHI_001870",
    "EHI_003020",
    "EHI_004380",
    "EHI_005010",
    "EHI_005460",
    "EHI_008350",
    "EHI_008640",
    "EHI_010660",
    "EHI_012030",
    "EHI_012380",
    "EHI_014060",
    "EHI_017740",
    "EHI_021480",
    "EHI_024680",
    "EHI_026420",
    "EHI_038680",
    "EHI_040310",
    "EHI_040450",
    "EHI_042250",
    "EHI_045550",
    "EHI_046390",
    "EHI_048250",
    "EHI_053150",
    "EHI_053420",
    "EHI_056100",
    "EHI_059670",
    "EHI_065790",
    "EHI_067850",
    "EHI_068230",
]

# Encystation genes — chitin synthase, chitinase, Jacob lectins, cyst wall
EH_ENCYSTATION = [
    "EHI_028930",  # cyst wall-specific glycoprotein Jacob
    "EHI_067190",  # cyst wall-specific glycoprotein Jacob
    "EHI_044500",  # cyst wall-specific glycoprotein Jacob, putative
    "EHI_136360",  # cyst wall-specific glyco protein Jacob, putative
    "EHI_092100",  # chitinase, putative
    "EHI_109890",  # chitinase, putative
    "EHI_180790",  # chitinase, putative
    "EHI_015750",  # chitinase Jessie3, putative
    "EHI_024660",  # chitinase Jessie, putative
    "EHI_170480",  # chitin synthase, putative
    "EHI_152170",  # chitinase Jessie 3, putative
    "EHI_044840",  # chitin synthase 2, putative
]

# Thioredoxin family — redox defense, drug targets (metronidazole)
EH_THIOREDOXIN = [
    "EHI_004490",
    "EHI_006700",
    "EHI_021560",
    "EHI_023060",
    "EHI_026340",
    "EHI_027550",
    "EHI_029380",
    "EHI_042900",
    "EHI_045250",
    "EHI_053840",
    "EHI_062790",
    "EHI_068390",
    "EHI_096200",
    "EHI_105860",
    "EHI_107670",
    "EHI_110350",
    "EHI_124400",
    "EHI_133970",
    "EHI_149850",
    "EHI_152600",
    "EHI_169240",
    "EHI_170420",
    "EHI_155440",  # thioredoxin reductase — key metronidazole target
    "EHI_190880",  # thioredoxin domain-containing protein 2
]

# Peroxiredoxin/lysozyme/SOD — antimicrobial defense, redox
EH_REDOX_DEFENSE = [
    "EHI_001420",
    "EHI_061980",
    "EHI_114010",
    "EHI_122310",
    "EHI_123390",
    "EHI_145840",
    "EHI_201250",  # peroxiredoxins
    "EHI_015250",
    "EHI_081740",
    "EHI_089990",
    "EHI_096570",
    "EHI_199110",  # lysozymes
    "EHI_018740",
    "EHI_183180",
    "EHI_084260",  # more peroxiredoxins
    "EHI_159160",  # iron-containing superoxide dismutase
]

# Alcohol/aldehyde dehydrogenases — anaerobic metabolism, drug targets
EH_DEHYDROGENASES = [
    "EHI_000410",
    "EHI_088020",
    "EHI_107560",
    "EHI_125950",
    "EHI_157010",
    "EHI_166490",
    "EHI_192470",
    "EHI_023110",
    "EHI_030180",
    "EHI_160670",
    "EHI_198760",
    "EHI_024240",
    "EHI_042260",
    "EHI_107210",
    "EHI_150490",
    "EHI_160940",
    "EHI_042140",  # aldehyde dehydrogenase 1
    "EHI_008200",
    "EHI_167320",
    "EHI_187020",  # GAPDH
    "EHI_014410",
    "EHI_067860",
    "EHI_092450",
    "EHI_152670",
    "EHI_165350",  # malate DH
    "EHI_030810",  # malate DH, cytoplasmic
]

# Ferredoxin / iron-sulfur cluster — mitosomal function, electron transfer
EH_FERREDOXIN = [
    "EHI_025710",
    "EHI_138480",
    "EHI_189480",
    "EHI_198670",
    "EHI_099860",
    "EHI_194430",  # iron-sulfur cluster binding
    "EHI_051060",  # pyruvate:ferredoxin oxidoreductase
    "EHI_159640",  # iron hydrogenase
    "EHI_159160",  # iron-containing SOD
]

# Actin / cytoskeleton — trogocytosis, phagocytosis, motility
EH_ACTIN = [
    "EHI_182900",
    "EHI_008780",
    "EHI_022240",
    "EHI_039070",
    "EHI_043640",
    "EHI_048630",
    "EHI_107290",
    "EHI_126190",
    "EHI_131230",
    "EHI_140120",
    "EHI_140710",
    "EHI_142730",
    "EHI_148100",
    "EHI_159150",
    "EHI_163580",
    "EHI_163750",
    "EHI_197810",
    "EHI_198930",
    "EHI_038800",
    "EHI_094030",
    "EHI_094060",
    "EHI_103450",
    "EHI_104390",
    "EHI_111050",
    "EHI_122800",
    "EHI_161200",  # actin-binding proteins
    "EHI_152990",
    "EHI_168340",
    "EHI_186770",
    "EHI_186840",  # cofilin/tropomyosin
    "EHI_005020",
    "EHI_033740",
    "EHI_134490",
    "EHI_140640",  # F-actin capping
    "EHI_045000",  # Arp2/3 complex subunit
]

# Phosphatases — signaling, dephosphorylation
EH_PHOSPHATASES = [
    "EHI_019610",
    "EHI_048570",
    "EHI_056420",
    "EHI_086040",
    "EHI_092510",
    "EHI_107260",
    "EHI_110320",
    "EHI_114170",
    "EHI_140690",
    "EHI_141860",
    "EHI_162200",
    "EHI_197000",
    "EHI_197120",
    "EHI_024410",
    "EHI_024450",
    "EHI_044560",
    "EHI_049430",
    "EHI_056630",
    "EHI_073370",
    "EHI_087900",
    "EHI_103800",
    "EHI_110570",
    "EHI_119910",
    "EHI_124450",
    "EHI_131070",
    "EHI_136980",
    "EHI_153650",
    "EHI_165320",
    "EHI_169660",
    "EHI_176830",
    "EHI_179330",
    "EHI_000480",
    "EHI_006050",
    "EHI_010290",
    "EHI_017600",
    "EHI_020260",
    "EHI_023140",
    "EHI_031240",
    "EHI_048550",
    "EHI_056650",
    "EHI_059820",
    "EHI_064720",
    "EHI_079260",
    "EHI_088080",
    "EHI_098850",
    "EHI_100420",
    "EHI_103250",
    "EHI_110140",
    "EHI_117570",
    "EHI_119520",
]

# ---------------------------------------------------------------------------
# Parameter helpers
# ---------------------------------------------------------------------------


def _org(names: list[str]) -> str:
    return json.dumps(names)


def _text_search_params(
    organism: str,
    term: str,
    fields: list[str] | None = None,
) -> dict[str, str]:
    if fields is None:
        fields = ["product"]
    return {
        "text_search_organism": _org([organism]),
        "text_expression": term,
        "document_type": "gene",
        "text_fields": json.dumps(fields),
    }


def _ec_search_params(
    organism: str,
    ec_number: str,
    ec_sources: list[str] | None = None,
) -> dict[str, str]:
    if ec_sources is None:
        ec_sources = [
            "KEGG_Enzyme",
            "GenBank",
            "computationally inferred from Orthology",
            "Uniprot",
        ]
    return {
        "organism": _org([organism]),
        "ec_source": json.dumps(ec_sources),
        "ec_number_pattern": ec_number,
        "ec_wildcard": "No",
    }


def _signal_peptide_params(organism: str) -> dict[str, str]:
    return {"organism": _org([organism])}


def _tm_domain_params(
    organism: str,
    min_tm: int = 1,
    max_tm: int = 30,
) -> dict[str, str]:
    return {
        "organism": _org([organism]),
        "min_tm": str(min_tm),
        "max_tm": str(max_tm),
    }


# ---------------------------------------------------------------------------
# Seed definitions
# ---------------------------------------------------------------------------

SEEDS: list[SeedDef] = [
    # 1) EhHMIMSS Virulence Factors (12 nodes)
    SeedDef(
        name="EhHMIMSS Virulence Factors",
        description=(
            "Comprehensive virulence factor identification in E. histolytica HM-1:IMSS. "
            "Combines cysteine proteases (CP family), Gal/GalNAc lectins, and amoebapores "
            "with signal peptide prediction. Unions with surface-anchored TM proteins. "
            "Excludes ribosomal housekeeping genes. Key pathogenesis factors for tissue "
            "invasion, host cell killing, and immune evasion."
        ),
        site_id="amoebadb",
        step_tree={
            "id": "root_minus",
            "displayName": "Virulence Factors (no ribosomal)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "union_all_virulence",
                "displayName": "All Virulence Candidates",
                "operator": "UNION",
                "primaryInput": {
                    "id": "secreted_virulence",
                    "displayName": "Secreted Virulence Factors",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "union_cp_lectin_ap",
                        "displayName": "CP + Lectin + Amoebapore",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "union_cp_lectin",
                            "displayName": "CP + Lectin",
                            "operator": "UNION",
                            "primaryInput": {
                                "id": "leaf_cp",
                                "displayName": "Cysteine Proteases",
                                "searchName": "GenesByText",
                                "parameters": _text_search_params(
                                    EH_ORG, "cysteine protease OR cysteine proteinase"
                                ),
                            },
                            "secondaryInput": {
                                "id": "leaf_lectin",
                                "displayName": "Lectins",
                                "searchName": "GenesByText",
                                "parameters": _text_search_params(EH_ORG, "lectin"),
                            },
                        },
                        "secondaryInput": {
                            "id": "leaf_amoebapore",
                            "displayName": "Amoebapores",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EH_ORG, "amoebapore OR saposin", ["product", "InterPro"]
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "leaf_signal_pep",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": _signal_peptide_params(EH_ORG),
                    },
                },
                "secondaryInput": {
                    "id": "surface_tm",
                    "displayName": "Surface + TM",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_surface",
                        "displayName": "Surface Antigens",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(EH_ORG, "surface"),
                    },
                    "secondaryInput": {
                        "id": "leaf_tm",
                        "displayName": "Transmembrane Domains",
                        "searchName": "GenesByTransmembraneDomains",
                        "parameters": _tm_domain_params(EH_ORG),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal",
                "displayName": "Ribosomal (exclude)",
                "searchName": "GenesByText",
                "parameters": _text_search_params(EH_ORG, '"ribosomal protein"'),
            },
        },
        control_set=ControlSetDef(
            name="E. histolytica Virulence Factors (curated)",
            positive_ids=(
                EH_CYSTEINE_PROTEASES[:15] + EH_LECTINS[:8] + EH_AMOEBAPORES[:4]
            ),
            negative_ids=EH_RIBOSOMAL[:25],
            provenance_notes=(
                "Positives: cysteine proteases (CP family), Gal/GalNAc lectins, "
                "and amoebapores — major virulence factors for tissue invasion. "
                "Negatives: ribosomal structural proteins — housekeeping genes."
            ),
            tags=["virulence", "amoeba", "seed"],
        ),
    ),
    # 2) EhHMIMSS Tissue Invasion Machinery (10 nodes)
    SeedDef(
        name="EhHMIMSS Tissue Invasion",
        description=(
            "Tissue invasion machinery of E. histolytica HM-1:IMSS. "
            "Combines proteases, surface molecules, actin/cytoskeleton genes, "
            "and Rho GTPases (motility/trogocytosis signaling) intersected with "
            "membrane-associated features (signal peptide or transmembrane domains). "
            "Excludes ribosomal genes."
        ),
        site_id="amoebadb",
        step_tree={
            "id": "root_minus",
            "displayName": "Invasion Genes (no ribosomal)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "invasion_membrane",
                "displayName": "Invasion intersect Membrane",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "union_invasion",
                    "displayName": "Invasion Components",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "union_protease_surface",
                        "displayName": "Protease + Surface",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_protease",
                            "displayName": "Proteases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EH_ORG, "protease OR proteinase OR peptidase"
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_surface_inv",
                            "displayName": "Surface Molecules",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EH_ORG, "surface OR lectin"
                            ),
                        },
                    },
                    "secondaryInput": {
                        "id": "union_actin_rho",
                        "displayName": "Cytoskeleton + GTPase",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_actin",
                            "displayName": "Actin Cytoskeleton",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(EH_ORG, "actin"),
                        },
                        "secondaryInput": {
                            "id": "leaf_rho",
                            "displayName": "Rho GTPases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EH_ORG, '"Rho family GTPase"'
                            ),
                        },
                    },
                },
                "secondaryInput": {
                    "id": "union_sp_tm",
                    "displayName": "Signal Peptide U TM",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_sp_inv",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": _signal_peptide_params(EH_ORG),
                    },
                    "secondaryInput": {
                        "id": "leaf_tm_inv",
                        "displayName": "Transmembrane",
                        "searchName": "GenesByTransmembraneDomains",
                        "parameters": _tm_domain_params(EH_ORG),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_ribosomal_inv",
                "displayName": "Ribosomal (exclude)",
                "searchName": "GenesByText",
                "parameters": _text_search_params(EH_ORG, '"ribosomal protein"'),
            },
        },
        control_set=ControlSetDef(
            name="E. histolytica Tissue Invasion (curated)",
            positive_ids=(
                EH_CYSTEINE_PROTEASES[:10]
                + EH_SURFACE[:8]
                + EH_ACTIN[:5]
                + EH_RHO_GTPASES[:5]
            ),
            negative_ids=EH_RIBOSOMAL[:25],
            provenance_notes=(
                "Positives: cysteine proteases, surface molecules, actin, "
                "and Rho GTPases — tissue invasion machinery. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["invasion", "amoeba", "seed"],
        ),
    ),
    # 3) EhHMIMSS Drug Targets (10 nodes)
    SeedDef(
        name="EhHMIMSS Drug Targets",
        description=(
            "Potential drug targets in E. histolytica HM-1:IMSS focusing on "
            "anaerobic metabolism. Thioredoxin/reductase (central metronidazole target), "
            "alcohol dehydrogenases, ferredoxin/iron-sulfur proteins (mitosomal), "
            "and peroxiredoxins. E. histolytica lacks mitochondria -- these "
            "essential anaerobic enzymes are prime therapeutic targets. "
            "Excludes ribosomal and heat shock housekeeping genes."
        ),
        site_id="amoebadb",
        step_tree={
            "id": "root_minus",
            "displayName": "Drug Targets (no housekeeping)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "minus_hsp",
                "displayName": "Metabolic - HSP",
                "operator": "MINUS",
                "primaryInput": {
                    "id": "union_all_metabolic",
                    "displayName": "All Metabolic Targets",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "union_trx_adh",
                        "displayName": "Thioredoxin + ADH",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_thioredoxin",
                            "displayName": "Thioredoxin Family",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(EH_ORG, "thioredoxin"),
                        },
                        "secondaryInput": {
                            "id": "leaf_adh",
                            "displayName": "Dehydrogenases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(EH_ORG, "dehydrogenase"),
                        },
                    },
                    "secondaryInput": {
                        "id": "union_fd_prx",
                        "displayName": "Ferredoxin + Redox",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_ferredoxin",
                            "displayName": "Iron-Sulfur / Ferredoxin",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EH_ORG, "ferredoxin OR iron-sulfur"
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_redox",
                            "displayName": "Peroxiredoxin / SOD",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EH_ORG, "peroxiredoxin OR superoxide OR lysozyme"
                            ),
                        },
                    },
                },
                "secondaryInput": {
                    "id": "leaf_hsp",
                    "displayName": "Heat Shock (exclude)",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(EH_ORG, '"heat shock"'),
                },
            },
            "secondaryInput": {
                "id": "leaf_ribo_drug",
                "displayName": "Ribosomal (exclude)",
                "searchName": "GenesByText",
                "parameters": _text_search_params(EH_ORG, '"ribosomal protein"'),
            },
        },
        control_set=ControlSetDef(
            name="E. histolytica Drug Targets (curated)",
            positive_ids=(
                EH_THIOREDOXIN[:12]
                + EH_DEHYDROGENASES[:8]
                + EH_FERREDOXIN[:5]
                + EH_REDOX_DEFENSE[:5]
            ),
            negative_ids=EH_RIBOSOMAL[:15] + EH_HEAT_SHOCK[:10],
            provenance_notes=(
                "Positives: thioredoxins, dehydrogenases, ferredoxins, and "
                "redox defense enzymes — anaerobic metabolism drug targets. "
                "Negatives: ribosomal proteins and heat shock chaperones."
            ),
            tags=["drug-target", "amoeba", "seed"],
        ),
    ),
    # 4) EhHMIMSS Encystation (8 nodes)
    SeedDef(
        name="EhHMIMSS Encystation",
        description=(
            "Encystation pathway genes in E. histolytica HM-1:IMSS. "
            "Chitin synthases and chitinases build the cyst wall; Jacob "
            "lectins are cyst-wall glycoproteins. Signaling kinases with "
            "signal peptides may regulate encystation. Understanding "
            "encystation is key to blocking fecal-oral transmission."
        ),
        site_id="amoebadb",
        step_tree={
            "id": "root_minus",
            "displayName": "Encystation (no ribosomal)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "union_cyst_signaling",
                "displayName": "Cyst Wall + Signaling",
                "operator": "UNION",
                "primaryInput": {
                    "id": "union_chitin_jacob",
                    "displayName": "Chitin + Jacob",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "leaf_chitin",
                        "displayName": "Chitin Synthase/Chitinase",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            EH_ORG, "chitin OR chitinase"
                        ),
                    },
                    "secondaryInput": {
                        "id": "leaf_jacob",
                        "displayName": "Jacob / Cyst Wall",
                        "searchName": "GenesByText",
                        "parameters": _text_search_params(
                            EH_ORG, '"cyst wall" OR jacob'
                        ),
                    },
                },
                "secondaryInput": {
                    "id": "kinase_secreted",
                    "displayName": "Secreted Kinases",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "id": "leaf_kinase_ec",
                        "displayName": "Ser/Thr Kinases",
                        "searchName": "GenesByEcNumber",
                        "parameters": _ec_search_params(EH_ORG, "2.7.11.1"),
                    },
                    "secondaryInput": {
                        "id": "leaf_sp_encyst",
                        "displayName": "Signal Peptide",
                        "searchName": "GenesWithSignalPeptide",
                        "parameters": _signal_peptide_params(EH_ORG),
                    },
                },
            },
            "secondaryInput": {
                "id": "leaf_ribo_encyst",
                "displayName": "Ribosomal (exclude)",
                "searchName": "GenesByText",
                "parameters": _text_search_params(EH_ORG, '"ribosomal protein"'),
            },
        },
        control_set=ControlSetDef(
            name="E. histolytica Encystation (curated)",
            positive_ids=EH_ENCYSTATION + EH_KINASES[:8],
            negative_ids=EH_RIBOSOMAL[:20],
            provenance_notes=(
                "Positives: encystation genes (chitin synthases, chitinases, "
                "Jacob lectins) and signaling kinases. "
                "Negatives: ribosomal structural proteins."
            ),
            tags=["encystation", "amoeba", "seed"],
        ),
    ),
    # 5) EhHMIMSS Signaling Network (10 nodes)
    SeedDef(
        name="EhHMIMSS Signaling Network",
        description=(
            "Complete signaling network in E. histolytica HM-1:IMSS. "
            "Kinases (EC 2.7.11.1), phosphatases, Rho GTPases (invasion/motility), "
            "and Rab GTPases (vesicular trafficking/phagocytosis). "
            "Excludes ribosomal and transporter housekeeping. Critical for "
            "understanding how the parasite coordinates tissue invasion, "
            "trogocytosis, and immune evasion."
        ),
        site_id="amoebadb",
        step_tree={
            "id": "root_minus",
            "displayName": "Signaling (no housekeeping)",
            "operator": "MINUS",
            "primaryInput": {
                "id": "minus_transporter",
                "displayName": "Signaling - Transporters",
                "operator": "MINUS",
                "primaryInput": {
                    "id": "union_all_signaling",
                    "displayName": "All Signaling",
                    "operator": "UNION",
                    "primaryInput": {
                        "id": "kinase_phosphatase",
                        "displayName": "Kinases U Phosphatases",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_kinase",
                            "displayName": "Ser/Thr Kinases (EC)",
                            "searchName": "GenesByEcNumber",
                            "parameters": _ec_search_params(EH_ORG, "2.7.11.1"),
                        },
                        "secondaryInput": {
                            "id": "leaf_phosphatase",
                            "displayName": "Phosphatases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(EH_ORG, "phosphatase"),
                        },
                    },
                    "secondaryInput": {
                        "id": "union_gtpases",
                        "displayName": "GTPases",
                        "operator": "UNION",
                        "primaryInput": {
                            "id": "leaf_rho_sig",
                            "displayName": "Rho GTPases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EH_ORG, '"Rho family GTPase"'
                            ),
                        },
                        "secondaryInput": {
                            "id": "leaf_rab_sig",
                            "displayName": "Rab GTPases",
                            "searchName": "GenesByText",
                            "parameters": _text_search_params(
                                EH_ORG, '"Rab family GTPase"'
                            ),
                        },
                    },
                },
                "secondaryInput": {
                    "id": "leaf_transporter",
                    "displayName": "Transporters (exclude)",
                    "searchName": "GenesByText",
                    "parameters": _text_search_params(EH_ORG, "transporter"),
                },
            },
            "secondaryInput": {
                "id": "leaf_ribo_sig",
                "displayName": "Ribosomal (exclude)",
                "searchName": "GenesByText",
                "parameters": _text_search_params(EH_ORG, '"ribosomal protein"'),
            },
        },
        control_set=ControlSetDef(
            name="E. histolytica Signaling Network (curated)",
            positive_ids=(
                EH_KINASES[:20]
                + EH_PHOSPHATASES[:10]
                + EH_RHO_GTPASES[:8]
                + EH_RAB_GTPASES[:8]
            ),
            negative_ids=EH_RIBOSOMAL[:15] + EH_TRANSPORTERS[:10],
            provenance_notes=(
                "Positives: kinases, phosphatases, Rho and Rab GTPases — "
                "complete signaling apparatus for invasion and trafficking. "
                "Negatives: ribosomal proteins and transporters."
            ),
            tags=["signaling", "amoeba", "seed"],
        ),
    ),
    # 6) EhHMIMSS Exported Kinases (simple 2-node baseline)
    SeedDef(
        name="EhHMIMSS Exported Kinases",
        description=(
            "Simple 2-node baseline: EC 2.7.11.1 Ser/Thr kinases intersected "
            "with signal peptide prediction in E. histolytica HM-1:IMSS. "
            "Identifies potentially exported/secreted kinases."
        ),
        site_id="amoebadb",
        step_tree={
            "id": "combine_kinase_sp",
            "displayName": "Exported Kinases",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "leaf_ec_kinase",
                "displayName": "EC Kinases (2.7.11.1)",
                "searchName": "GenesByEcNumber",
                "parameters": _ec_search_params(EH_ORG, "2.7.11.1"),
            },
            "secondaryInput": {
                "id": "leaf_sp_base",
                "displayName": "Signal Peptide",
                "searchName": "GenesWithSignalPeptide",
                "parameters": _signal_peptide_params(EH_ORG),
            },
        },
        control_set=ControlSetDef(
            name="E. histolytica Exported Kinases (curated)",
            positive_ids=EH_KINASES[:15],
            negative_ids=EH_RIBOSOMAL[:15],
            provenance_notes=(
                "Positives: annotated Ser/Thr protein kinases (EC 2.7.11.1). "
                "Negatives: ribosomal structural proteins — housekeeping."
            ),
            tags=["kinase", "amoeba", "seed"],
        ),
    ),
]
