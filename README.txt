Digital Cement Passport (DCP) – illustrative pilot implementation

This repository accompanies the article *Digital Material Passports for the Construction Sector:
Batch-Level Traceability of Energy and Carbon Data with Building Information Modeling*
(Hamidkhaniha, Garcia Martinez, Pourhosseini; under review).

The article is conceptual: it specifies the DCP framework. This package is a small pilot that
shows the specified data structure can be expressed in machine-readable form and checked automatically.

Scope and limitations — please read
* All data are synthetic. The batch, the plant, the manufacturer, the coordinates (0, 0) and every
  numerical value are invented for demonstration. They do not describe any real cement, plant or EPD.
* The pilot has not been deployed as software, connected to a plant, applied to a building
  project or validated in an industrial setting.
* Passing the schema means a record is structurally consistent with the specification. It is
  not a conformity assessment under EN 197-1 (which relies on statistical autocontrol), not an
  EPD verification under EN 15804 and not proof of compliance with REACH.
* No MQTT broker or passport server is operated. The A3 update is simulated offline, and the design QR
  points to the reserved domain example.org, so it opens no page; the demonstration QR and the HTML
  passport page show the batch data instead.
* The BIM link described in the article (only the batchID and passport URI in the BIM object) is
  not part of this pilot.

Contents

| Path | Layer in the article | What it is |
|---|---|---|
| model/CementPassport.ttl | Layer 1 – semantic model | SAMM 2.1.0 aspect model of the DCP (Turtle) |
| schema/dcp-batch.schema.json | Layer 2 – JSON Schema | Validation rules of the DCP (JSON Schema draft-07) |
| schema/listing1_excerpt.json | Layer 2 | Abridged excerpt printed as Listing 1 in the article (tested to be an exact subset of the full schema) |
| examples/batch-valid.json | – | One synthetic batch record that passes |
| examples/invalid/*.json | – | 14 synthetic records, each with one defect, that must be rejected |
| examples/expected_rejections.json | – | Expected reason and error location for each invalid record |
| api/dcp-asyncapi.yaml | Proposed MQTT component | AsyncAPI 3.0 description of the A3 update message |
| src/validate_passport.py | Layer 2 | Validates records against the schema (+ checks JSON Schema cannot express) |
| src/generate_qr.py | Layer 1 – data carrier | Design QR (passport URI only) and a demonstration QR with a readable text summary that any phone shows offline |
| src/render_passport.py | Layer 1 – what a stakeholder sees | Phone-friendly HTML passport page of a batch (opens in any browser) |
| demo_url.txt | – | Address of an online copy of the passport page; the QR printed on the page opens it |
| src/passport_report.py | Layer 1 – access control | Role-dependent views (public / engineer / auditor) |
| src/simulate_a3_update.py | Proposed MQTT component | Offline simulation: message → validation → record |
| src/run_pilot.py | – | Runs all steps and writes output/pilot_run_log.txt |
| src/make_invalid_examples.py | – | Re-creates the invalid records from the valid one |
| tests/test_pilot.py | – | 15 automated tests, including cross-layer consistency (TTL ↔ schema ↔ AsyncAPI) |
| data/platform_comparison_table7.csv | Section 3.6, Table 7 | Platform comparison matrix behind the 69 % and "six essential categories" results |
| output/ | – | Results of the pilot run included in this release: log, both QR codes, passport page passport_DCP-EX-2026-000123.html, updated record |

Quick start

No installation: open run_in_colab.ipynb in Google Colab and run the cells. Windows: double-click
run_pilot_windows.bat. macOS/Linux: sh run_pilot_mac_linux.sh. Or manually:

Requires Python 3.9 or later.

bash
pip install -r requirements.txt
python src/run_pilot.py                      # full pilot, writes output/pilot_run_log.txt
python -m unittest discover -s tests -v      # automated tests
python src/validate_passport.py examples/batch-valid.json examples/invalid/*.json
python src/passport_report.py examples/batch-valid.json engineer


rdflib and PyYAML are only needed for two optional consistency tests; the tests are skipped
without them.

Validation rules and their sources

Every rule in the schema is traceable to a source. Values marked "this pilot" are design choices of the
pilot, not requirements of any standard.

| Rule | Source |
|---|---|
| cementType restricted to the 27 common cements | EN 197-1:2011, Table 1 |
| clinkerRatio within the clinker range of the declared cement type | EN 197-1:2011, Table 1 |
| strengthClass restricted to 32.5L … 52.5R; L classes only for CEM III | EN 197-1:2011, Table 3 and clause on low early strength |
| 28-day strength within the limits of the class; early strength minimum at the age of the class | EN 197-1:2011, Table 3 |
| solubleChromiumVI ≤ 2 mg/kg (0.0002 % of total dry weight of cement) | REACH, Regulation (EC) No 1907/2006, Annex XVII, entry 47 |
| Indicators per module A1, A2, A3 (or A1-A3), C1–C4; GWP-total, PERT, PENRT | EN 15804:2012+A2:2019 |
| casNumber format and check digit | CAS Registry Number format (Chemical Abstracts Service) |
| Latitude −90…90, longitude −180…180 | Definition of geographic coordinates (WGS 84) |
| energySourceType vocabulary (Fossil, Alternative, Renewable, Mixed) | this pilot |
| Role-to-field assignment of the views | this pilot |
| Constituent shares sum to 100 %; clinkerRatio consistent with the constituents (±0.5 percentage points) | this pilot (arithmetic consistency) |

The numerical limits of EN 197-1 were entered by hand; users should check them against their own copy of
EN 197-1. (The early-strength age used for class 52.5L is 2 days.)

Verification performed for this release

* model/CementPassport.ttl conforms to the official SAMM 2.1.0 SHACL shapes
  (eclipse-esmf/esmf-semantic-aspect-meta-model), checked with pySHACL.
* api/dcp-asyncapi.yaml parses without errors with the official AsyncAPI parser (@asyncapi/parser 3).
* schema/dcp-batch.schema.json is valid against the JSON Schema draft-07 meta-schema.
* All 15 tests pass; the QR code was decoded back to the passport URI with OpenCV.

Attribution

The modelling approach follows the Battery Pass data model (Battery Pass consortium,
<https://github.com/batterypass/BatteryPassDataModel>, release 1.2.0, licensed under CC BY 4.0), in
particular the SAMM aspect-model structure, the generated JSON Schema / AsyncAPI artefacts per aspect,
and the "carbon footprint per lifecycle stage" list pattern, which is reused here for the EN 15804
modules. The cement model was written anew; no files or text were copied from that repository.
See NOTICE.md.

Generative AI tools (Google Gemini and Anthropic Claude) assisted in drafting and restructuring the code.
The author reviewed and tested all files and takes responsibility for them.

Status

This is an open, unverified proof of concept shared in the spirit of open science. Comments and
corrections are welcome: Shayesteh Hamidkhaniha, Shaham@alum.us.es.

How to cite

See CITATION.cff (repository identifier to be added after deposit in idUS, the institutional
repository of the Universidad de Sevilla). Please cite this package together with the article.

License

Creative Commons Attribution 4.0 International (CC BY 4.0). See LICENSE.
