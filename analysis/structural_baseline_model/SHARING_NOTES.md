# M1–M9 regression bundle

This directory contains the code, methodology, figures, and compact result tables for the M1–M9 structural baseline regression analysis.

## Included

- preprocessing, modeling, reporting, and validation code
- the full Korean analysis report and data-quality notes
- M1–M9 aggregate and industry-level performance tables
- sequential and leave-one-block-out contribution tables
- repeat-level metrics used to assess stability
- generated figures and validation summaries

## Not included

The competition source data, reconstructed analysis inputs, row-level out-of-fold predictions, protected-file hashes, and other large reproducible intermediate artifacts are intentionally excluded. They are either source-data derivatives or unnecessary for reviewing the regression results.

The omitted files can be regenerated in the original authorized data environment with the commands documented in `README.md`.

## Main files

- `report.md`: interpretation and limitations
- `tables/model_performance.csv`: M1–M9 aggregate performance
- `tables/industry_model_performance.csv`: industry-level performance
- `tables/model_block_contribution.csv`: sequential and leave-one-block-out contributions
- `tables/industry_count_ticket_block_pathways.csv`: amount, count, and ticket-size pathways
- `tables/validation_checks.csv`: reproducibility checks

