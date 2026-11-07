# Digital Cement Passport (DCP) – illustrative pilot implementation

This repository accompanies a manuscript on the Digital Cement Passport (DCP) framework by
Hamidkhaniha, Garcia Martinez and Pourhosseini (Universidad de Sevilla), currently under review.
The reference to the published article will be added here after publication.

The manuscript is **conceptual**: it specifies the DCP framework. This package is a **small pilot** that
shows the specified data structure can be expressed in machine-readable form and checked automatically.

> **Scope and limitations — please read**
> * All data are **synthetic**. The batch, the plant, the manufacturer, the coordinates (0, 0) and every
>   numerical value are invented for demonstration. They do not describe any real cement, plant or EPD.
> * The pilot has **not** been deployed as software, connected to a plant, applied to a building
>   project or validated in an industrial setting.
> * Passing the schema means a record is **structurally consistent with the specification**. It is
>   **not** a conformity assessment under EN 197-1 (which relies on statistical autocontrol), **not** an
>   EPD verification under EN 15804 and **not** proof of compliance with REACH.
> * No MQTT broker or passport server is operated. The A3 update is simulated offline, and the design QR
>   points to the reserved domain example.org, so it opens no page; the demonstration QR and the HTML
>   passport page show the batch data instead.
> * The BIM link of the framework (only the batchID and passport URI in the BIM object) is not part
>   of this pilot.
> * The role-dependent views only filter fields; no authentication or authorization is implemented.
> * There is no data transformation engine and no connection to manufacturer, laboratory or LCA
>   databases; records are read from JSON files.
> * The pilot does not generate batch identifiers and cannot enforce their uniqueness or immutability
>   (there is no database).
> * The CAS check confirms the number format and check digit only, not that the number is registered
>   for the named substance or matches the EN 197-1 constituent code. The chromium VI check compares a reported value with the limit; it does not
>   check the test method.

## Contents

| Path | Part of the framework | What it is |
|---|---|---|
| `model/CementPassport.ttl` | Semantic model (TTL) | SAMM 2.1.0 aspect model of the DCP (Turtle) |
| `schema/dcp-batch.schema.json` | Validation schema | Validation rules of the DCP (JSON Schema draft-07) |
| `schema/listing1_excerpt.json` | Validation schema | Abridged excerpt of the schema for print (tested to be an exact subset of the full schema) |
| `examples/batch-valid.json` | – | One synthetic batch record that passes |
| `examples/invalid/*.json` | – | 22 synthetic records, each made by changing one value of the valid record; they must be rejected (one change can break more than one rule) |
| `examples/expected_rejections.json` | – | For each invalid record: the change made and the field at which an error must be reported |
| `api/dcp-asyncapi.yaml` | Proposed MQTT component | AsyncAPI 3.0 description of the A3 update message |
| `src/validate_passport.py` | Validation schema | Validates records against the schema (+ checks JSON Schema cannot express) |
| `src/generate_qr.py` | QR data carrier | Design QR (passport URI only) and a demonstration QR with a readable text summary that any phone shows offline |
| `src/render_passport.py` | Passport view | Phone-friendly HTML passport page of a batch (opens in any browser) |
| `demo_url.txt` | Passport view | Address where the generated passport page is published online (`index.html`, the same page as in `output/`); the QR printed on the page opens it |
| `src/passport_report.py` | Role-dependent views | Role-dependent views (public / engineer / auditor) |
| `src/simulate_a3_update.py` | Proposed MQTT component | Offline simulation: message → validation → record |
| `src/run_pilot.py` | – | Runs all steps and writes `output/pilot_run_log.txt` |
| `src/make_invalid_examples.py` | – | Re-creates the invalid records from the valid one |
| `tests/test_pilot.py` | – | 21 automated tests. Cross-layer tests check that the TTL model and the schema have the same field names, the same required/optional fields and the same allowed values (they do not compare data types or numeric limits), and that the AsyncAPI message equals the message schema used by the simulation |
| `data/platform_comparison_table7.csv` | Platform benchmarking | Comparison of 16 passport data categories across four battery passport platforms, as used in the manuscript |
| `output/` | – | Results of the pilot run included in this release: log, both QR codes, passport page `passport_DCP-EX-2026-000123.html`, updated record |

## Quick start

No installation: open `run_in_colab.ipynb` in Google Colab and run the cells. Windows: double-click
`run_pilot_windows.bat`. macOS/Linux: `sh run_pilot_mac_linux.sh`. Or manually:

Requires Python 3.9 or later.

```bash
pip install -r requirements.txt
python src/run_pilot.py                      # full pilot, writes output/pilot_run_log.txt
python -m unittest discover -s tests -v      # automated tests
python src/validate_passport.py examples/batch-valid.json examples/invalid/*.json
python src/passport_report.py examples/batch-valid.json engineer
```

`rdflib` and `PyYAML` are only needed for three optional consistency tests; the tests are skipped
without them.

## Validation rules and their sources

Every rule in the schema is traceable to a source. Values marked "this pilot" are design choices of the
pilot, not requirements of any standard.

| Rule | Source |
|---|---|
| `cementType` restricted to the 27 common cements | EN 197-1:2011, Table 1 |
| `clinkerRatio` within the clinker range of the declared cement type | EN 197-1:2011, Table 1 |
| `strengthClass` restricted to 32.5L … 52.5R; L classes only for CEM III | EN 197-1:2011, Table 3 |
| Early and 28-day strength both required; 28-day strength within the limits of the class; early strength given at the age specified for the class and above its minimum | EN 197-1:2011, Table 3 |
| Each clinker, main or minor additional constituent carries its EN 197-1 code (K, S, D, P, Q, V, W, T, L, LL); main constituents must match the cement type (e.g. V for CEM II/B-V; S and P/Q/V for CEM V) | EN 197-1:2011, Table 1 |
| Share of each group of main constituents within the range of the cement type (e.g. V 21–35 % in CEM II/B-V; S and P/Q/V each 18–30 % in CEM V/A); at least two different main constituents in CEM II/A-M and CEM II/B-M; silica fume at most 10 %; minor additional constituents at most 5 % (all in % of main + minor constituents) | EN 197-1:2011, Table 1 and its footnotes |
| `solubleChromiumVI` ≤ 2 mg/kg (0.0002 % of total dry weight of cement) | REACH, Regulation (EC) No 1907/2006, Annex XVII, entry 47 |
| Indicators per module A1, A2, A3 (or A1-A3), C1–C4; GWP-total, PERT, PENRT | EN 15804:2012+A2:2019 |
| All three indicators required for every module listed | this pilot |
| `declaredUnit` fixed to 1 t cement | this pilot (comparability between batches) |
| `passportURI` ends with the `batchID` | this pilot (the QR must point to the same batch) |
| `casNumber` format and check digit (registration of the number is not checked) | CAS Registry Number format (Chemical Abstracts Service) |
| Latitude −90…90, longitude −180…180 | Definition of geographic coordinates (WGS 84) |
| `energySourceType` vocabulary (Fossil, Alternative, Renewable, Mixed) | this pilot |
| `dataSource` vocabulary (EPD, supplyChainReport, plantSensor, siteInspection); the transport protocol (MQTT) is not a data source | this pilot |
| A3 messages must carry `dataSource` and `lastUpdated`; a message not later than the stored A3 value is not recorded | this pilot |
| Role-to-field assignment of the views | this pilot |
| Constituent shares sum to 100 %; `clinkerRatio` consistent with the constituents (±0.5 percentage points) | this pilot (arithmetic consistency) |

The numerical limits of EN 197-1 were entered by hand; users should check them against their own copy of
EN 197-1. In particular check: the early-strength age used for class 52.5L (2 days) and the S and P/Q/V ranges used
for CEM V/B (31–49 %).

## Verification performed for this release

* `model/CementPassport.ttl` conforms to the official SAMM 2.1.0 SHACL shapes
  (eclipse-esmf/esmf-semantic-aspect-meta-model), checked with pySHACL. Because pySHACL misreads SPARQL
  variables named `?values` in three of those shapes, the variable was renamed before checking; the
  rules themselves were not changed.
* `api/dcp-asyncapi.yaml` parses without errors with the official AsyncAPI parser (@asyncapi/parser 3).
* `schema/dcp-batch.schema.json` is valid against the JSON Schema draft-07 meta-schema.
* All 21 tests pass (3 of them need `rdflib` and `PyYAML` and are skipped without them); both QR codes
  were decoded back to their content with OpenCV.

## Attribution

The modelling approach follows the **Battery Pass data model** (Battery Pass consortium,
<https://github.com/batterypass/BatteryPassDataModel>, releases 1.0.0 and 1.2.0; the repository README
states CC BY 4.0), in particular the SAMM aspect-model structure, the generated JSON Schema per aspect,
the AsyncAPI (MQTT) description per aspect (release 1.0.0),
and the "carbon footprint per lifecycle stage" list pattern, which is reused here for the EN 15804
modules. The cement model was written anew; no files or text were copied from that repository.
See `NOTICE.md`.

Generative AI tools (Google Gemini and Anthropic Claude) assisted in drafting and restructuring the code.
The author reviewed and tested all files and takes responsibility for them.

## Status

This is an open, unverified proof of concept shared in the spirit of open science. Comments and
corrections are welcome: Shayesteh Hamidkhaniha, Shaham@alum.us.es.

## How to cite

See `CITATION.cff` (repository identifier to be added after deposit in idUS, the institutional
repository of the Universidad de Sevilla). Please cite this package together with the accompanying publication.

## License

Creative Commons Attribution 4.0 International (CC BY 4.0). See `LICENSE`.
