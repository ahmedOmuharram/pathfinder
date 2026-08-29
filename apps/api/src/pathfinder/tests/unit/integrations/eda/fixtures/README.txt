Recorded responses of the genomics EDA deployment, base https://veupathdb.org/eda.
The genomics deployment is one EDA service behind every genomics site host; do not
re-record from clinepidb.org, which is a different deployment with different ids.

studies_list.json
  GET /studies. Trim: the first 40 studies entries plus every entry whose sha1hash
  is the empty string (the user_submitted rows).

study_detail_de.json
  GET /studies/STUDY_e973eadd57. No trim.

study_detail_phenotype.json
  GET /studies/STUDY_53f554ec6a. No trim.

permissions.json
  GET /permissions. Trim: the first 40 perDataset entries, plus every entry that
  omits shortDisplayName or description, plus DS_53f554ec6a.

count_unfiltered.json
  POST /studies/STUDY_53f554ec6a/entities/GENE_PHENOTYPE_DATA_ENTITY/count
  body {"filters":[]}. No trim.

count_filtered.json
  Same endpoint, body with one stringSet filter on VAR_035294d0 for "P. berghei".
  No trim.

distribution_categorical.json
  POST /studies/STUDY_53f554ec6a/entities/GENE_PHENOTYPE_DATA_ENTITY/variables/
  VAR_035294d0/distribution body {"filters":[],"valueSpec":"count"}. No trim.

tabular_json.json
  POST /studies/STUDY_53f554ec6a/entities/GENE_PHENOTYPE_DATA_ENTITY/tabular with
  Accept: application/json, five rows of VEUPATHDB_GENE_ID. No trim.

apps.json
  GET /apps. No trim.

compute_job_lookup.json
  POST /computes/differentialexpression?autostart=false for STUDY_e973eadd57,
  DESeq, normal against febrile. No trim.

volcano_statistics.json
  POST /computes/differentialexpression/statistics with the same body. Trim: the
  first 200 statistics rows plus the one row that omits pValue.
