# Add a city to NRI Ease

This guide explains the repeatable city onboarding process for the three evidence sections already used by the app: price trends, home-finance references, and infrastructure. The helper prepares four SQL files in the order the API expects: city projects first, then each evidence pillar.

## What this pipeline does

`city_onboarding.py` can fetch the Square Yards residential catalog and run cited AI web research to stage candidate records for the three evidence pillars. Review the CSV contents directly: correct or remove unsupported rows, then `build` converts every remaining valid row into the four SQL files without requiring review-marker edits. Review the generated SQL before applying it. `apply` writes all four files in one MySQL transaction. On first local `server.py` startup (or the pipeline's `setup` command), it creates the database if absent and creates only missing standard tables from `city_onboarding_schema.sql`. It never alters or drops existing tables. It does not bypass CAPTCHA or sign-in controls, and no command can promise all three pillars will have data if official sources do not publish usable records or require human access.

The existing tables used are:

| SQL file | Existing tables | What goes in it |
| --- | --- | --- |
| `projects.sql` | `projects` | Every project in the Square Yards city catalog, with its listing ID and locality |
| `price_trends.sql` | `guideline_sources`, `guideline_entries` | Source and dated, locality-level values that fit the existing guideline schema |
| `financier.sql` | `financier_reference_sources`, `financier_project_references` | Bank source records and matched project references |
| `infrastructure.sql` | `infrastructure_sources`, `infrastructure_projects` | Source records and named infrastructure projects/areas/statuses |

The API uses the same tables for every city. The website's city filters load distinct city names from the existing `projects` table through `/api/cities`, so importing a city's project catalog makes that city selectable without editing a city list in code. The price API compares a project's primary locality with `guideline_entries` using its existing locality matching logic. Finance references need a project ID to appear on a project page. Infrastructure locality matches should use only localities explicitly named by the source; broad ward or city coverage must not be presented as a specific colony match.

## One-time setup on a computer

1. Copy the project folder, including `server.py`, `city_onboarding.py`, and `city_onboarding_schema.sql`, to the computer. Keep these files together and use the same application version so the schema and API assumptions match.
2. Install Python 3.10 or newer and the MySQL connector: `py -m pip install mysql-connector-python`.
3. Install Codex CLI and sign in on that computer with `codex login`. The pipeline uses Codex CLI's live web search and the signed-in user's Codex access; it does not ask for a Gemini/OpenAI API key. The signed-in account must have access to Codex and remaining usage. A friend's computer needs its own CLI installation and sign-in.
4. Install/start MySQL. The account used by the program must be able to create the database/tables on first setup and insert/update records. If the database already exists with all standard tables, it only needs the required data permissions.
5. Do not put database passwords in the script, CSV files, or SQL files. If `MYSQL_PASSWORD` is not configured, `server.py` and the pipeline prompt for it with hidden input. Optional `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, and `MYSQL_DATABASE` settings select the connection; the database must remain `nriease_guidelines`.

### First command for a teammate

From PowerShell in the project folder, the usual first run is:

```powershell
py -m pip install mysql-connector-python
py server.py
```

When the server starts, it checks the database and creates the database/tables only if missing. If no password environment variable is set, it asks for the MySQL password in the terminal without displaying it. Keep MySQL running. The standalone setup command is also available:

```powershell
py city_onboarding.py setup
```

The app startup and `setup` use the same schema file. If a table already exists with an older or incompatible structure, the pipeline will not silently alter it; that needs an intentional schema migration.

## Repeat these steps for each city

### Collect, review, build, and import

Install `mysql-connector-python`, make sure MySQL is running, and run this from the project folder:

```powershell
py city_onboarding.py collect-city --city "Mumbai"
```

This fetches Mumbai's Square Yards catalog and runs cited source research through the locally signed-in Codex CLI with live web search. PowerShell displays the current bank/civic research pass and Codex search progress. Review `sources.csv` and the evidence CSVs directly: correct or delete inaccurate rows. No review-marker column needs to be changed. Then run `build` to convert all remaining valid rows. The `onboard-city` convenience command also collects and builds, but pauses before database import so you can review the CSVs and SQL. Project CSV rows merge by `project_id`, and the database uses a primary-key upsert to avoid duplicate project IDs.

### 1. Create the city worksheets

From the project folder in PowerShell, run:

```powershell
py city_onboarding.py init-city --city "Bhopal"
```

Replace Bhopal with the target city. This creates `city_onboarding\cities\bhopal\` with `projects.csv`, `price_trends.csv`, `finance.csv`, `infrastructure.csv`, and an audit-only `sources.csv`. It does not access MySQL.

### 2. Collect projects and evidence candidates

The project folder already exists, so collect into it without re-running `init-city`:

```powershell
py city_onboarding.py collect-city --city "Bhopal"
```

This fetches the Square Yards residential catalog, then runs 17 focused research tasks: one for official valuation schedules, one per bank (11 banks), and five for development, municipal, transport, utilities, and procurement sources. Codex CLI is invoked in read-only mode with live web search enabled; the pipeline receives its final cited response and stores the findings/progress in CSV files. The terminal shows each research task and Codex activity. No JSON checkpoint files are created. Each completed search is saved to the evidence CSVs and tracked in `research_tasks.csv`. The next run skips completed Codex searches and retries failed ones. Add `--refresh-research` to deliberately rerun completed searches. Each run uses your signed-in Codex access and available usage; it is not unlimited. No AI API key is requested or saved. The `gemini`, `groq`, and `openai` API providers remain available only when deliberately selected. Project rows merge by ID; the database upsert and primary key prevent duplicate project IDs.

Codex CLI is the default; to select it explicitly, use `py city_onboarding.py collect-city --city "Bhopal" --ai-provider codex`. Other supported providers can be selected explicitly with `--ai-provider gemini`, `--ai-provider groq`, or `--ai-provider openai` and require their respective API keys.

For projects only, no OpenAI key is needed:

```powershell
py city_onboarding.py collect-projects --city "Bhopal"
```

Review `research_tasks.csv` to see what was completed, skipped, or blocked by quota, then review `sources.csv` and the evidence CSVs. Only cited URLs are retained as sources. Correct or delete inaccurate rows directly in the CSVs; no marker edits are needed to include valid rows in SQL. Finance matches remain `possible` where identity/phase is uncertain, and infrastructure candidates start inactive (`is_active=0`) so they are not shown until explicitly activated. Price records must have real values and correct source, unit, year, page, and locality. The collector cannot obtain CAPTCHA-protected records. Use a permitted bulk/download source or collect a smaller sample manually. It does not import to MySQL.

### 3. Research and enter the price-trend source

Start with the relevant state registration/valuation authority or another authoritative public source. Existing examples are [MP IGRS guideline view](https://www.mpigr.gov.in/#/guidline-view) and [Rajasthan ePanjiyan DLC lookup](https://mobileepanjiyan.rajasthan.gov.in/ePanjiyandlc/FindDlcRate.aspx). For each new state, find its official equivalent and record the exact source URL, title, retrieval date, district, schedule year, page, row/serial, original locality label, and rate unit.

The current shared schema has specific rate columns for residential/commercial/industrial plots, building types, and agricultural rates. A source value may be imported only when its meaning and unit fit one of those columns exactly. Do not map a Rajasthan interior/exterior or road-width rate to a plot rate merely because the units look similar. If the source's categories cannot be represented faithfully, leave the trend import empty and flag the schema gap for a separate product/schema decision; do not create a city-only table. Review each rate row in the CSV against its source before building. The build command includes valid rows without requiring a review-marker edit.

If a website presents CAPTCHA, stop automated access and use a permitted official bulk download/API, ask the authority for access, or collect a smaller reviewed sample manually. Do not try to defeat or bypass CAPTCHA. Save enough source/page context to trace every number.

### 4. Research bank references

Check official bank approved-project pages, PDFs, or search tools. Record each bank as a separate source and retain the bank-listed project name, builder, phase, code, capture date, and URL. Match only to the project IDs in that city's `projects.csv`. Mark uncertain identity/phase matches `possible`; only strong verified matches should be `exact` or `listed`. A bank list is evidence of a listed project, not a loan guarantee. Projects with no bank listing still remain in the catalog with no finance row.

### 5. Research infrastructure

Prefer the city's development/master plan and progress reports, plus official procurement, municipal, metro/transport, water, and utility sources. A plan can establish that something is proposed; a tender establishes procurement activity; neither proves construction or completion. Use the project's actual source status and keep the source wording in `status_label`/`description`. Set `locality_names` to a JSON array of names expressly stated in the source. Do not infer nearby localities from a map or constituency. Use `citywide` or `unlocated` when a project is not tied to a project locality.

### 6. Review AI candidates against the source

The default collector calls Codex CLI, using the local user's Codex sign-in and live web search, and asks for structured candidate data. Gemini, Groq, or OpenAI API can still be chosen explicitly. Candidate URLs must appear in the research response and pass a government-domain or approved-bank-domain check. Project links are assigned only for a unique exact normalized project-name match in the complete Square Yards catalog; every finance match remains `possible` for human review. AI can still omit details or misunderstand a source. Compare names, dates, units, status, and exact geographic wording against the official source. Do not treat model search as proof that a schedule was exhaustively extracted; large state valuation schedules may need a state-specific parser after locating the official download. Codex CLI availability and usage depend on the user's local Codex installation, sign-in, account, and remaining plan allowance.

### 7. Generate and review the four SQL files

From the project folder, run:

```powershell
py city_onboarding.py build --city "Bhopal"
```

Open `city_onboarding\cities\bhopal\` and review the CSVs and four generated SQL files. `build` converts every remaining valid row from `projects.csv`, `price_trends.csv`, `finance.csv`, and `infrastructure.csv`; it does not require changing a review-marker value. Correct or delete unsupported rows in the CSV before building. The generated SQL is repeatable (upsert-based), limited to the existing tables, and contains no `CREATE`, `ALTER`, or `DROP` statements. An empty pillar CSV produces an empty import for that pillar; it does not invent evidence. The review-only `sources.csv` is an audit worksheet, while source details needed by the API are stored in the pillar source tables.

### 8. Dry-run, then apply

First validate without connecting to MySQL:

```powershell
py city_onboarding.py apply --city "Bhopal" --dry-run
```

If the SQL is correct, apply explicitly:

```powershell
py city_onboarding.py apply --city "Bhopal" --execute
```

The helper asks you to type the city name and then prompts for the MySQL password with hidden input. It ensures the database and missing standard tables exist, checks that project IDs do not belong to another city, and applies projects → price trends → finance → infrastructure as one transaction. If any data statement fails, the transaction is rolled back. Do not run the import on production until the generated SQL and matches have been reviewed.

## Verify the imported data

Use MySQL Workbench to check project and pillar counts for the city. Then open a property page and check its three evidence sections. The existing endpoints can be queried locally, for example:

```text
GET http://localhost:4000/api/price-trends?project_id=PROJECT_ID&rate_code=plot_residential_sqm
GET http://localhost:4000/api/financier-projects?project_id=PROJECT_ID
GET http://localhost:4000/api/infrastructure-projects?city=CITY&locality=LOCALITY
```

Replace `PROJECT_ID`, `CITY`, and `LOCALITY` with exact values from the imported catalog. A no-match response can mean no source data was imported, a locality label does not meet the API's current match rules, the rate category does not fit the requested rate code, or the project page is using a different locality spelling. Review the source and API response before changing any mapping.

## Files to share with a teammate

Share the application folder, including `server.py`, `city_onboarding.py`, `city_onboarding_schema.sql`, and this guide, through the team's normal version control or file-sharing process. Do not share a database password in a source file or SQL export. Each teammate needs Python, the MySQL connector, a running MySQL instance, and a database account with the required permissions. On startup the program creates missing standard tables; each teammate still needs the reviewed city source data to populate them. They can then repeat the city worksheet, review, dry-run, and apply steps on their machine.
