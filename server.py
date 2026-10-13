import json
import os
import re
import ssl
from collections import defaultdict
from difflib import SequenceMatcher
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


RAJASTHAN_RERA_API = "https://reraapi.rajasthan.gov.in/api/web/Home/GetProjects"
RAJASTHAN_RERA_REFERER = "https://rera.rajasthan.gov.in/"
GUJARAT_RERA_API = "https://gujrera.gujarat.gov.in/project_reg/public/global-search"
SQUARE_YARDS_MCP = "https://sy-mcp.squareyards.com/mcp/external"


def _match_text(value):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper())).strip()


def _locality_match_score(guideline_place, locality, *area_fields):
    """Compare the primary project locality with PDF place/admin labels."""
    primary = re.split(r"[,/|]", str(locality or ""), maxsplit=1)[0]
    wanted = _match_text(primary).split()
    available = _match_text(" ".join(str(value or "") for value in (guideline_place, *area_fields))).split()
    if not wanted or not available:
        return None

    scores = []
    for token in wanted:
        best = max((SequenceMatcher(None, token, candidate).ratio() for candidate in available), default=0)
        threshold = 1.0 if len(token) <= 2 else 0.82
        if best < threshold:
            return None
        scores.append(best)
    return round(sum(scores) / len(scores), 4)


def _square_yards_project(project_id):
    """Fetch canonical project metadata using the same MCP tool as the frontend."""
    request_body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_entity_details",
            "arguments": {"entity": "project", "id": str(project_id)},
        },
    }).encode("utf-8")
    request = Request(
        SQUARE_YARDS_MCP,
        data=request_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
        },
    )
    with urlopen(request, timeout=20) as response:
        body = response.read(2_000_000).decode("utf-8-sig")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        data_line = next((line[5:].strip() for line in body.splitlines() if line.startswith("data:")), None)
        if not data_line:
            raise ValueError("Square Yards returned an unreadable project response.")
        payload = json.loads(data_line)

    result = payload.get("result", payload)
    if result.get("isError"):
        message = " ".join(item.get("text", "") for item in result.get("content", []) if item.get("text"))
        raise ValueError(message or "Square Yards could not retrieve this project.")
    structured = result.get("structuredContent") or payload.get("structuredContent")
    if not isinstance(structured, dict):
        raise ValueError("Square Yards did not return structured project details.")

    detail = structured.get("detail") if isinstance(structured.get("detail"), dict) else {}
    project = structured.get("projectData") or detail.get("projectData") or structured
    if not isinstance(project, dict):
        raise ValueError("Square Yards returned project details in an unexpected format.")
    location = project.get("subLocation") or project.get("locality") or project.get("location")
    city = project.get("city") or structured.get("city")
    # If Square Yards returns only a combined location string, use its final
    # component as city and first component as the locality.
    if isinstance(location, str) and "," in location:
        parts = [part.strip() for part in location.split(",") if part.strip()]
        location = parts[0]
        city = city or parts[-1]
    return {
        "project_id": int(project_id),
        "project_name": project.get("projectName") or project.get("name") or structured.get("name"),
        "city": city,
        "locality": location,
    }


class PrototypeHandler(SimpleHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # A browser navigation/refresh may close a request while MySQL is
            # still working. Do not turn that normal disconnect into a traceback.
            return

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/api/health":
            self._send_json(200, {"ok": True})
            return
        if parsed.path == "/api/cities":
            self._get_cities()
            return
        if parsed.path == "/api/ensure-project":
            self._ensure_project(parse_qs(parsed.query))
            return
        if parsed.path == "/api/price-trends":
            self._get_price_trends(parse_qs(parsed.query))
            return
        if parsed.path == "/api/financier-projects":
            self._get_financier_projects(parse_qs(parsed.query))
            return
        if parsed.path == "/api/top-properties":
            self._get_top_properties(parse_qs(parsed.query))
            return
        if parsed.path == "/api/infrastructure-projects":
            self._get_infrastructure_projects(parse_qs(parsed.query))
            return
        requested = Path(self.path.split("?", 1)[0].lstrip("/"))
        if not requested.name or not requested.is_file():
            self.path = "/index.html"
        super().do_GET()

    def _get_cities(self):
        """Return cities already represented in the shared project catalog."""
        try:
            import mysql.connector
            from mysql.connector import Error as MySQLError
        except ImportError:
            self._send_json(503, {"ok": False, "error": "MySQL driver is missing. Install mysql-connector-python."})
            return

        db_config = {
            "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", "nriease_guidelines"),
            "connection_timeout": 8,
        }
        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor()
            cursor.execute("SELECT DISTINCT city FROM projects WHERE TRIM(city) <> '' ORDER BY city")
            cities = [row[0] for row in cursor.fetchall() if row[0]]
            cursor.close()
            self._send_json(200, {"ok": True, "cities": cities})
        except MySQLError as error:
            message = "The projects table is missing. Run `py city_onboarding.py setup` first." if getattr(error, "errno", None) == 1146 else "Could not load available cities. Check MySQL and the server's MYSQL_* settings."
            self._send_json(503, {"ok": False, "error": message})
        finally:
            if connection is not None and connection.is_connected():
                connection.close()

    def _ensure_project(self, query):
        """Ensure a Square Yards project exists locally before related lookups."""
        project_id = (query.get("project_id") or [""])[0].strip()
        if not project_id.isdigit():
            self._send_json(400, {"ok": False, "error": "Provide a numeric project_id query parameter."})
            return

        try:
            import mysql.connector
            from mysql.connector import Error as MySQLError
        except ImportError:
            self._send_json(503, {"ok": False, "error": "MySQL driver is missing. Install mysql-connector-python."})
            return

        db_config = {
            "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", "nriease_guidelines"),
            "connection_timeout": 8,
        }
        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT project_id, project_name, city, locality FROM projects WHERE project_id = %s",
                (int(project_id),),
            )
            existing = cursor.fetchone()
            if existing and existing.get("project_name") and existing.get("city") and existing.get("locality"):
                cursor.close()
                self._send_json(200, {"ok": True, "created": False, "project": existing, "source": "database"})
                return
            cursor.close()
            connection.close()
            connection = None

            try:
                project = _square_yards_project(project_id)
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as error:
                self._send_json(502, {"ok": False, "error": "Could not fetch this project from Square Yards.", "detail": str(error)})
                return
            if not project.get("project_name") or not project.get("city"):
                self._send_json(502, {"ok": False, "error": "Square Yards did not return enough project information to save it."})
                return

            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO projects (project_id, project_name, city, locality, property_type)
                VALUES (%s, %s, %s, %s, NULL)
                ON DUPLICATE KEY UPDATE
                  project_name = IF(project_name IS NULL OR project_name = '', VALUES(project_name), project_name),
                  city = IF(city IS NULL OR city = '', VALUES(city), city),
                  locality = IF(locality IS NULL OR locality = '', VALUES(locality), locality)
            """, (int(project_id), project["project_name"], project["city"], project.get("locality")))
            created = existing is None and cursor.rowcount == 1
            connection.commit()
            cursor.close()

            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT project_id, project_name, city, locality FROM projects WHERE project_id = %s",
                (int(project_id),),
            )
            saved = cursor.fetchone()
            cursor.close()
            self._send_json(200, {"ok": True, "created": created, "project": saved, "source": "square_yards"})
        except (MySQLError, ValueError) as error:
            self._send_json(503, {"ok": False, "error": "Could not ensure this project in the MySQL projects table.", "detail": str(error)})
        finally:
            if connection is not None and connection.is_connected():
                connection.close()

    def _get_price_trends(self, query):
        """Aggregate all eligible guideline rates for the project's primary locality."""
        project_id = (query.get("project_id") or [""])[0].strip()
        rate_code = (query.get("rate_code") or ["plot_residential_sqm"])[0].strip()
        allowed_rate_codes = {
            "plot_residential_sqm": "plot_residential_sqm",
            "plot_commercial_sqm": "plot_commercial_sqm",
            "plot_industrial_sqm": "plot_industrial_sqm",
            "building_residential_rcc_sqm": "building_residential_rcc_sqm",
            "building_residential_rbc_sqm": "building_residential_rbc_sqm",
            "building_residential_tin_shade_sqm": "building_residential_tin_shade_sqm",
            "building_residential_kaccha_kabelu_sqm": "building_residential_kaccha_kabelu_sqm",
            "building_commercial_shop_sqm": "building_commercial_shop_sqm",
            "building_commercial_office_sqm": "building_commercial_office_sqm",
            "building_commercial_godown_sqm": "building_commercial_godown_sqm",
            "building_multi_residential_sqm": "building_multi_residential_sqm",
            "building_multi_commercial_sqm": "building_multi_commercial_sqm",
        }
        if not project_id.isdigit():
            self._send_json(400, {"ok": False, "error": "Provide a numeric project_id query parameter."})
            return
        if rate_code not in allowed_rate_codes:
            self._send_json(400, {"ok": False, "error": "Unsupported rate_code."})
            return

        try:
            import mysql.connector
            from mysql.connector import Error as MySQLError
        except ImportError:
            self._send_json(503, {"ok": False, "error": "MySQL driver is missing. Install mysql-connector-python."})
            return

        db_config = {
            "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", "nriease_guidelines"),
            "connection_timeout": 8,
        }
        rate_column = allowed_rate_codes[rate_code]  # selected only from the allow-list above
        square_yards_project = None
        square_yards_error = None
        try:
            square_yards_project = _square_yards_project(project_id)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as error:
            square_yards_error = str(error)

        locality_sql = f"""
            SELECT s.financial_year, e.entry_id, e.guideline_place,
                   e.urban_local_body, e.sub_area, e.ward, e.tehsil,
                   e.{rate_column} AS rate, s.file_name, s.source_url,
                   e.printed_page, e.serial_no
            FROM guideline_sources s
            JOIN guideline_entries e ON e.source_id = s.source_id
            WHERE s.city = %s AND e.extraction_status <> 'rejected'
              AND e.{rate_column} IS NOT NULL
              AND (e.normalized_place LIKE %s OR e.sub_area LIKE %s OR e.ward LIKE %s)
            ORDER BY s.financial_year, e.serial_no
        """
        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT project_name, city, locality FROM projects WHERE project_id = %s",
                (int(project_id),),
            )
            cached_project = cursor.fetchone()
            project = {
                "project_id": int(project_id),
                "project_name": (square_yards_project or {}).get("project_name") or (cached_project or {}).get("project_name"),
                "city": (square_yards_project or {}).get("city") or (cached_project or {}).get("city"),
                "locality": (square_yards_project or {}).get("locality") or (cached_project or {}).get("locality"),
            }
            if not project["city"] or not project["locality"]:
                cursor.close()
                status = 502 if square_yards_error else 404
                self._send_json(status, {
                    "ok": False,
                    "error": "Could not determine the project's city and locality from Square Yards or the local cache.",
                    "project_id": int(project_id),
                    "square_yards_error": square_yards_error,
                })
                return

            # Search by the first four letters of the primary locality only.
            # Python then validates the full locality tokens, allowing variants
            # such as Nipania/Nipaniya and Mangaliya/Mangliya.
            primary_locality = re.split(r"[,/|]", str(project["locality"]), maxsplit=1)[0]
            locality_tokens = _match_text(primary_locality).split()
            if not locality_tokens:
                cursor.close()
                self._send_json(404, {"ok": False, "error": "The project has no usable primary locality.", "project_id": int(project_id)})
                return
            first_token = locality_tokens[0]
            locality_pattern = f"%{first_token[:min(4, len(first_token))]}%"
            # All cities use the shared guideline schema and the same locality
            # matching rules; only the source rows selected by s.city differ.
            cursor.execute(locality_sql, (project["city"], locality_pattern, locality_pattern, locality_pattern))
            candidate_rows = cursor.fetchall()
            cursor.close()
        except (MySQLError, ValueError) as error:
            if getattr(error, "errno", None) == 1146:
                message = ("The shared price-trend tables guideline_sources and guideline_entries are missing "
                           "from the database selected by MYSQL_DATABASE. These same tables store rate history "
                           "for every city.")
            else:
                message = "Could not query the guideline database. Check MySQL and the server's MYSQL_* settings."
            self._send_json(503, {"ok": False, "error": message})
            return
        finally:
            if connection is not None and connection.is_connected():
                connection.close()

        locality_rows_by_year = defaultdict(list)
        for row in candidate_rows:
            score = _locality_match_score(
                row["guideline_place"], project["locality"],
                row["sub_area"], row["ward"], row["tehsil"],
            )
            if score is not None:
                row["locality_match_score"] = score
                locality_rows_by_year[row["financial_year"]].append(row)

        if not locality_rows_by_year:
            no_rate_message = "No guideline rate rows matched the project's primary locality in the shared guideline tables."
            self._send_json(404, {
                "ok": False,
                "error": no_rate_message,
                "project_id": int(project_id),
                "locality": project["locality"],
                "rate_code": rate_code,
                "hint": "Import the city's dated locality rates into guideline_sources and guideline_entries. Locality/project screening rows do not contain rate values.",
            })
            return

        points = []
        for year, rows in sorted(locality_rows_by_year.items()):
            rates = [float(row["rate"]) for row in rows]
            sources = {}
            for row in rows:
                sources[row["file_name"]] = {
                    "name": row["file_name"],
                    "url": row["source_url"],
                }
            samples = sorted(rows, key=lambda item: item["serial_no"])[:8]
            points.append({
                "financial_year": year,
                "average_rate": round(sum(rates) / len(rates), 2),
                "min_rate": min(rates),
                "max_rate": max(rates),
                "unit": "INR/sq_m" if rate_code.endswith("_sqm") else "INR/hectare",
                "rate_code": rate_code,
                "matched_records": len(rates),
                "locality_match_method": "primary_locality_text",
                "average_locality_match_score": round(sum(row["locality_match_score"] for row in rows) / len(rows), 4),
                "sample_guideline_places": [{
                    "name": row["guideline_place"],
                    "rate": float(row["rate"]),
                    "printed_page": row["printed_page"],
                    "serial_no": row["serial_no"],
                } for row in samples],
                "sources": list(sources.values()),
            })
        self._send_json(200, {
            "ok": True,
            "project": project,
            "metric": "locality_collector_guideline_rate_summary",
            "source_label": f"Official valuation schedule for {project['city']}",
            "rate_code": rate_code,
            "unit": points[0]["unit"],
            "aggregation": "Average, minimum, and maximum of all non-rejected matching guideline rows for the primary locality in each financial year.",
            "data_note": "These are official locality valuation benchmarks, not actual sale prices, asking prices, or apartment appreciation values. The maximum is the highest matching guideline rate in that locality and category.",
            "points": points,
        })

    def _get_financier_projects(self, query):
        """Return bank-published project references linked to a project ID."""
        project_id = (query.get("project_id") or [""])[0].strip()
        if not project_id.isdigit():
            self._send_json(400, {"ok": False, "error": "Provide a numeric project_id query parameter."})
            return

        try:
            import mysql.connector
            from mysql.connector import Error as MySQLError
        except ImportError:
            self._send_json(503, {"ok": False, "error": "MySQL driver is missing. Install mysql-connector-python."})
            return

        db_config = {
            "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", "nriease_guidelines"),
            "connection_timeout": 8,
        }
        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT project_id, project_name, city, locality FROM projects WHERE project_id = %s",
                (int(project_id),),
            )
            project = cursor.fetchone()
            if not project:
                cursor.close()
                self._send_json(404, {
                    "ok": False,
                    "error": "Project not found in the projects table. Open its details page first so it can be saved.",
                    "project_id": int(project_id),
                })
                return

            cursor.execute("""
                SELECT r.reference_id, r.listed_project_name, r.builder_name,
                       r.bank_project_code, r.match_status, r.match_note,
                       r.captured_at AS reference_captured_at,
                       s.financier_name, s.source_title, s.source_type,
                       s.source_url, s.source_note,
                       COALESCE(r.captured_at, s.captured_at) AS captured_at
                FROM financier_project_references r
                JOIN financier_reference_sources s ON s.source_id = r.source_id
                WHERE r.project_id = %s
                ORDER BY s.financier_name, r.listed_project_name
            """, (int(project_id),))
            references = cursor.fetchall()
            cursor.close()
            for reference in references:
                for field in ("reference_captured_at", "captured_at"):
                    if reference.get(field) is not None:
                        reference[field] = reference[field].isoformat()
            self._send_json(200, {
                "ok": True,
                "project": project,
                "count": len(references),
                "finance_references": references,
                "data_note": "A bank-published project reference is not a guarantee of loan approval or availability for a specific unit.",
            })
        except MySQLError as error:
            message = "Finance tables are missing. Restart the backend to run first-time schema setup, or run `py city_onboarding.py setup`." if getattr(error, "errno", None) == 1146 else "Could not query the financier database. Check MySQL and the server's MYSQL_* settings."
            self._send_json(503, {"ok": False, "error": message, "detail": str(error)})
        finally:
            if connection is not None and connection.is_connected():
                connection.close()

    def _get_top_properties(self, query):
        """Rank known city projects using the five weighted evidence pillars."""
        city = (query.get("city") or [""])[0].strip()
        try:
            limit = int((query.get("limit") or ["20"])[0])
        except ValueError:
            self._send_json(400, {"ok": False, "error": "limit must be an integer from 1 to 20."})
            return
        if not city or len(city) > 100 or limit < 1 or limit > 20:
            self._send_json(400, {"ok": False, "error": "Provide a city and a limit from 1 to 20."})
            return

        try:
            import mysql.connector
            from mysql.connector import Error as MySQLError
        except ImportError:
            self._send_json(503, {"ok": False, "error": "MySQL driver is missing. Install mysql-connector-python."})
            return

        db_config = {
            "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", "nriease_guidelines"),
            "connection_timeout": 8,
        }
        connection = None
        database_context = {}
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)
            # Expose non-secret connection identity so imported rows can be
            # compared with the MySQL instance and schema this API reads.
            cursor.execute("SELECT DATABASE() AS database_name, @@hostname AS server_host, @@port AS server_port, CURRENT_USER() AS database_user")
            database_context = cursor.fetchone() or {}
            cursor.execute(
                "SELECT project_id, project_name, city, locality FROM projects WHERE LOWER(city) = LOWER(%s)",
                (city,),
            )
            projects = cursor.fetchall()
            cursor.execute("""
                SELECT r.project_id, COUNT(*) AS financier_count,
                       COUNT(DISTINCT s.financier_name) AS financier_institute_count
                FROM financier_project_references r
                JOIN financier_reference_sources s ON s.source_id = r.source_id
                WHERE r.project_id IS NOT NULL AND r.match_status IN ('exact', 'listed')
                GROUP BY r.project_id
            """)
            finance_by_project = {int(row["project_id"]): row for row in cursor.fetchall()}
            cursor.execute("""
                SELECT p.infrastructure_project_id, p.area_name, p.locality_names,
                       p.status_code, p.project_name
                FROM infrastructure_projects p
                WHERE LOWER(p.city) = LOWER(%s) AND p.is_active = 1
                  AND p.status_code <> 'completed_reported'
            """, (city,))
            infrastructure = cursor.fetchall()
            cursor.execute("""
                SELECT s.financial_year, e.guideline_place, e.sub_area, e.ward, e.tehsil,
                       e.plot_residential_sqm
                FROM guideline_sources s
                JOIN guideline_entries e ON e.source_id = s.source_id
                WHERE LOWER(s.city) = LOWER(%s)
                  AND e.extraction_status <> 'rejected'
                  AND e.plot_residential_sqm IS NOT NULL
            """, (city,))
            guideline_rows = cursor.fetchall()
            cursor.close()
        except MySQLError as error:
            message = "Ranking requires the project, financier, infrastructure, and guideline tables. Apply their SQL setup/import files first." if getattr(error, "errno", None) == 1146 else "Could not query the property ranking data. Check MySQL and the server's MYSQL_* settings."
            self._send_json(503, {"ok": False, "error": message, "detail": str(error)})
            return
        finally:
            if connection is not None and connection.is_connected():
                connection.close()

        def locality_names(row):
            names = [row.get("area_name")]
            raw_names = row.get("locality_names")
            if isinstance(raw_names, str):
                try:
                    raw_names = json.loads(raw_names)
                except json.JSONDecodeError:
                    raw_names = []
            if isinstance(raw_names, list):
                names.extend(raw_names)
            return [str(name) for name in names if name]

        ranked = []
        for project in projects:
            project_id = int(project["project_id"])
            locality = project.get("locality") or ""
            primary_locality = re.split(r"[,/|]", locality, maxsplit=1)[0].strip()
            finance_row = finance_by_project.get(project_id, {})
            finance_count = int(finance_row.get("financier_count", 0))
            institute_count = int(finance_row.get("financier_institute_count", 0))
            infrastructure_matches = []
            if primary_locality and _match_text(primary_locality) != _match_text(city):
                wanted_locality = _match_text(primary_locality)
                for item in infrastructure:
                    named_areas = [_match_text(name) for name in locality_names(item)]
                    if any(name and re.search(rf"\b{re.escape(wanted_locality)}\b", name) for name in named_areas):
                        infrastructure_matches.append(item)

            matching_years = set()
            for row in guideline_rows:
                score = _locality_match_score(
                    row["guideline_place"], primary_locality,
                    row.get("sub_area"), row.get("ward"), row.get("tehsil"),
                )
                if score is not None:
                    matching_years.add(str(row["financial_year"]))
            trend_years = sorted(matching_years)[-5:]

            # Pillars award their stated points only when matching evidence is
            # present. Broker and crime data are currently unintegrated, so they
            # are reported unavailable and receive no points.
            scores = {
                "housing_finance": 30 if finance_count else 0,
                "appreciation_trend": 25 if len(trend_years) >= 3 else 0,
                "future_infrastructure": 20 if infrastructure_matches else 0,
                "certified_broker": 0,
                "locality_crime_safety": 0,
            }
            pillars = [
                {"key": "housing_finance", "label": "Housing finance", "weight": 30, "score": scores["housing_finance"], "available": finance_count > 0},
                {"key": "appreciation_trend", "label": "Price trend", "weight": 25, "score": scores["appreciation_trend"], "available": len(trend_years) >= 3},
                {"key": "future_infrastructure", "label": "Infrastructure", "weight": 20, "score": scores["future_infrastructure"], "available": bool(infrastructure_matches)},
                {"key": "certified_broker", "label": "Certified broker", "weight": 15, "score": scores["certified_broker"], "available": False},
                {"key": "locality_crime_safety", "label": "Crime and safety", "weight": 10, "score": scores["locality_crime_safety"], "available": False},
            ]
            total = sum(scores.values())
            ranked.append({
                "project": project,
                "score": total,
                "max_score": 100,
                "pillar_scores": scores,
                "pillars": pillars,
                "evidence": {
                    "financier_count": finance_count,
                    "financier_institute_count": institute_count,
                    "guideline_trend_years": trend_years,
                    "guideline_year_count": len(trend_years),
                    "future_infrastructure_count": len(infrastructure_matches),
                    "future_infrastructure_projects": [item["project_name"] for item in infrastructure_matches[:5]],
                    "certified_broker": {"available": False, "reason": "No certified broker data source is connected yet."},
                    "locality_crime_safety": {"available": False, "reason": "No locality-level crime data source is connected yet."},
                },
            })

        ranked.sort(key=lambda item: (
            -item["score"],
            -item["pillar_scores"]["housing_finance"],
            -item["evidence"]["financier_institute_count"],
            -item["pillar_scores"]["future_infrastructure"],
            -item["evidence"]["guideline_year_count"],
            item["project"]["project_name"].casefold(),
        ))
        top_properties = ranked[:limit]
        for rank, item in enumerate(top_properties, start=1):
            item["rank"] = rank
        self._send_json(200, {
            "ok": True,
            "city": city,
            "algorithm": "Evidence availability points: finance 30, 3+ years of matching locality guideline trend 25, explicit non-completed locality infrastructure match 20, certified broker 15, crime/safety data 10. Missing pillars score 0 and are labeled unavailable.",
            "candidate_projects_in_database": len(projects),
            "database_context": database_context,
            "returned": len(top_properties),
            "limit": limit,
            "properties": top_properties,
            "data_note": f"This ranks {city} projects currently present in the projects table; it does not imply every city listing has been imported. Guideline rates are government benchmarks, not transaction-price appreciation. Finance references are not loan approvals. Broker and crime data are not yet connected.",
        })

    def _get_infrastructure_projects(self, query):
        """Find sourced Smart City infrastructure records for a project's locality."""
        project_id = (query.get("project_id") or [""])[0].strip()
        city = (query.get("city") or [""])[0].strip()
        locality = (query.get("locality") or [""])[0].strip()
        include_completed = (query.get("include_completed") or ["false"])[0].strip().lower() in {"1", "true", "yes"}

        if project_id and not project_id.isdigit():
            self._send_json(400, {"ok": False, "error": "project_id must be numeric."})
            return
        if not project_id and (not city or not locality):
            self._send_json(400, {
                "ok": False,
                "error": "Provide project_id, or both city and locality.",
                "examples": [
                    "/api/infrastructure-projects?project_id=315399",
                    "/api/infrastructure-projects?city=Indore&locality=Nipania",
                ],
            })
            return

        try:
            import mysql.connector
            from mysql.connector import Error as MySQLError
        except ImportError:
            self._send_json(503, {"ok": False, "error": "MySQL driver is missing. Install mysql-connector-python."})
            return

        db_config = {
            "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", "nriease_guidelines"),
            "connection_timeout": 8,
        }
        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)
            if project_id:
                cursor.execute(
                    "SELECT project_name, city, locality FROM projects WHERE project_id = %s",
                    (int(project_id),),
                )
                cached = cursor.fetchone()
                if cached and cached.get("city") and cached.get("locality"):
                    city = cached["city"]
                    locality = cached["locality"]
                    project_context = {
                        "project_id": int(project_id),
                        "project_name": cached.get("project_name"),
                        "city": city,
                        "locality": locality,
                    }
                else:
                    cursor.close()
                    cursor = None
                    try:
                        resolved = _square_yards_project(project_id)
                    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError):
                        resolved = None
                    if not resolved or not resolved.get("city") or not resolved.get("locality"):
                        self._send_json(404, {
                            "ok": False,
                            "error": "Could not resolve this project's city and locality. Add it to projects or pass city and locality directly.",
                            "project_id": int(project_id),
                            "examples": ["/api/infrastructure-projects?city=Indore&locality=Nipania"],
                        })
                        return
                    city = str(resolved["city"])
                    locality = str(resolved["locality"])
                    project_context = resolved
                    cursor = connection.cursor()
                    cursor.execute("""
                        INSERT INTO projects (project_id, project_name, city, locality, property_type)
                        VALUES (%s,%s,%s,%s,NULL)
                        ON DUPLICATE KEY UPDATE project_name=VALUES(project_name),
                          city=VALUES(city), locality=VALUES(locality)
                    """, (int(project_id), resolved.get("project_name") or f"Project {project_id}", city, locality))
                    connection.commit()
                    cursor.close()
                    cursor = connection.cursor(dictionary=True)

            normalized_city = str(city or "").strip()
            normalized_locality = re.split(r"[,/|]", str(locality or ""), maxsplit=1)[0].strip()
            if not normalized_city or not normalized_locality:
                self._send_json(400, {"ok": False, "error": "A usable city and locality are required."})
                return
            project_context = locals().get("project_context") or {
                "city": normalized_city,
                "locality": normalized_locality,
            }

            completion_clause = "" if include_completed else "AND p.status_code <> 'completed_reported'"
            # Restrict the database result set to records whose source explicitly
            # names this locality. Escape SQL LIKE metacharacters from user data.
            locality_pattern = "%" + normalized_locality.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
            cursor.execute(f"""
                SELECT p.infrastructure_project_id, p.project_name, p.city,
                       p.area_name, p.locality_names, p.scope, p.category,
                       p.program_name, p.status_code, p.status_label, p.description,
                       p.capacity_value, p.capacity_unit, p.source_reference,
                       p.imported_at, s.source_title, s.source_type, s.source_url,
                       s.file_name, s.fetched_at AS source_fetched_at, s.import_note
                FROM infrastructure_projects p
                JOIN infrastructure_sources s ON s.source_id = p.source_id
                WHERE LOWER(p.city) = LOWER(%s) AND p.is_active = 1 {completion_clause}
                  AND (
                    LOWER(COALESCE(p.area_name, '')) LIKE LOWER(%s) ESCAPE '!'
                    OR LOWER(COALESCE(CAST(p.locality_names AS CHAR), '')) LIKE LOWER(%s) ESCAPE '!'
                  )
                ORDER BY p.project_name
            """, (normalized_city, locality_pattern, locality_pattern))
            rows = cursor.fetchall()
            cursor.close()
        except MySQLError as error:
            self._send_json(503, {
                "ok": False,
                "error": "Infrastructure tables are missing. Restart the backend to run first-time schema setup, or run `py city_onboarding.py setup`.",
                "database_error": str(error),
            })
            return
        finally:
            if connection is not None and connection.is_connected():
                connection.close()

        def locality_key(value):
            value = _match_text(value)
            value = re.sub(r"\b(SQUARE|CHOWK|ROAD|AREA|LOCALITY)\b", " ", value)
            return re.sub(r"\s+", " ", value).strip()

        requested_locality = locality_key(normalized_locality)
        matched = []
        for row in rows:
            names = row.get("locality_names") or []
            if isinstance(names, str):
                try:
                    names = json.loads(names)
                except json.JSONDecodeError:
                    names = []
            if not isinstance(names, list):
                names = []
            names = [name for name in [row.get("area_name"), *names] if name]
            keys = [locality_key(name) for name in names]
            is_match = bool(requested_locality and any(
                key and (key == requested_locality or key in requested_locality or requested_locality in key)
                for key in keys
            ))
            row["capacity"] = None if row.get("capacity_value") is None else {
                "value": float(row["capacity_value"]), "unit": row.get("capacity_unit")
            }
            row.pop("capacity_value", None)
            row.pop("capacity_unit", None)
            row["source"] = {
                "title": row.pop("source_title"),
                "type": row.pop("source_type"),
                "url": row.pop("source_url"),
                "file_name": row.pop("file_name"),
                "fetched_at": row.pop("source_fetched_at").isoformat(sep=" ") if row.get("source_fetched_at") else None,
                "note": row.pop("import_note"),
                "reference": row.get("source_reference"),
            }
            row.pop("source_reference", None)
            row["imported_at"] = row["imported_at"].isoformat(sep=" ") if row.get("imported_at") else None
            # SQL LIKE has already limited these records to named-area candidates;
            # the normalized check protects against accidental wildcard matches.
            if is_match:
                matched.append(row)

        self._send_json(200, {
            "ok": True,
            "project": project_context,
            "matching_rule": "Only records whose area_name or locality_names explicitly contains the property's locality are returned. Matching uses parameterized SQL LIKE plus a normalized text check; no distance or proximity is inferred.",
            "include_completed": include_completed,
            "counts": {
                "locality_matches": len(matched),
                "area_based_context": 0,
                "citywide_context": 0,
                "unlocated_proposals": 0,
            },
            "locality_matches": matched,
            "area_based_context": [],
            "citywide_context": [],
            "unlocated_proposals": [],
            "data_note": "Projects without a matching area_name or locality_names are omitted, including citywide and unlocated records. A text match establishes that the source names the locality, not the project's physical distance. SCP PDF-only records are historical proposal items; verify current status against the cited live source.",
        })

    def _save_project_record(self, payload):
        project_id = str(payload.get("project_id", "")).strip()
        project_name = str(payload.get("project_name", "")).strip()
        city = str(payload.get("city", "")).strip()
        locality = str(payload.get("locality", "")).strip() or None
        if not project_id.isdigit() or not project_name or not city:
            self._send_json(400, {"ok": False, "error": "project_id, project_name, and city are required."})
            return
        if len(project_name) > 255 or len(city) > 100 or (locality and len(locality) > 255):
            self._send_json(400, {"ok": False, "error": "Project fields exceed the database column sizes."})
            return

        try:
            import mysql.connector
            from mysql.connector import Error as MySQLError
        except ImportError:
            self._send_json(503, {"ok": False, "error": "MySQL driver is missing. Install mysql-connector-python."})
            return

        db_config = {
            "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", "nriease_guidelines"),
            "connection_timeout": 8,
        }
        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT DATABASE() AS database_name, @@hostname AS hostname, @@port AS port, @@datadir AS data_dir, CURRENT_USER() AS db_user")
            db_identity = cursor.fetchone()
            cursor.execute(
                "SELECT project_id, project_name, city, locality FROM projects WHERE project_id = %s",
                (int(project_id),),
            )
            existing = cursor.fetchone()
            if existing and existing.get("project_name") and existing.get("city") and existing.get("locality"):
                cursor.close()
                self._send_json(200, {"ok": True, "created": False, "project": existing, "source": "database"})
                return
            cursor.close()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO projects (project_id, project_name, city, locality, property_type)
                VALUES (%s, %s, %s, %s, NULL)
                ON DUPLICATE KEY UPDATE
                  project_name = IF(project_name IS NULL OR project_name = '', VALUES(project_name), project_name),
                  city = IF(city IS NULL OR city = '', VALUES(city), city),
                  locality = IF(locality IS NULL OR locality = '', VALUES(locality), locality)
            """, (int(project_id), project_name, city, locality))
            connection.commit()
            created = existing is None and cursor.rowcount == 1
            cursor.close()

            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT project_id, project_name, city, locality FROM projects WHERE project_id = %s",
                (int(project_id),),
            )
            saved = cursor.fetchone()
            cursor.close()
            if not saved:
                self._send_json(500, {"ok": False, "error": "The project upsert completed but the row could not be read back."})
                return
            print(
                f"[project-sync] database={db_identity['database_name']} host={db_identity['hostname']} "
                f"port={db_identity['port']} data_dir={db_identity['data_dir']} user={db_identity['db_user']} "
                f"project_id={saved['project_id']} "
                f"project_name={saved['project_name']!r} created={created}",
                flush=True,
            )
            self._send_json(200, {"ok": True, "created": created, "project": saved, "database": db_identity})
        except (MySQLError, ValueError) as error:
            self._send_json(503, {"ok": False, "error": "Could not save this project to MySQL.", "detail": str(error), "database": db_config["database"]})
        finally:
            if connection is not None and connection.is_connected():
                connection.close()

    def do_POST(self):
        if self.path == "/api/ensure-project":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 16384:
                    raise ValueError("Request body must be between 1 and 16384 bytes.")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Expected a project object.")
            except (ValueError, UnicodeDecodeError) as error:
                self._send_json(400, {"ok": False, "error": str(error) or "Expected JSON project data."})
                return
            self._save_project_record(payload)
            return
        if self.path == "/api/gujarat-rera":
            self._proxy_gujarat_rera()
            return
        if self.path != "/api/rajasthan-rera":
            self._send_json(404, {"ok": False, "error": "Not found."})
            return

        api_key = os.environ.get("RAJASTHAN_RERA_API_KEY", "").strip()
        if not api_key:
            self._send_json(503, {"ok": False, "error": "Rajasthan RERA API key is not configured on the local server."})
            return

        try:
            length = min(int(self.headers.get("Content-Length", "0")), 8192)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            registration_number = str(payload.get("RegistrationNo", "")).strip()
        except (ValueError, UnicodeDecodeError, AttributeError):
            self._send_json(400, {"ok": False, "error": "Expected JSON with a RegistrationNo field."})
            return

        if not registration_number or len(registration_number) > 80:
            self._send_json(400, {"ok": False, "error": "A valid RegistrationNo is required."})
            return

        request_body = json.dumps({"RegistrationNo": registration_number}).encode("utf-8")
        request = Request(
            RAJASTHAN_RERA_API,
            data=request_body,
            method="POST",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Referer": RAJASTHAN_RERA_REFERER,
                "x-api-key": api_key,
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                upstream_body = response.read(2_000_000)
                upstream_payload = json.loads(upstream_body.decode("utf-8-sig"))
            self._send_json(200, upstream_payload)
        except HTTPError as error:
            self._send_json(502, {"ok": False, "error": f"Rajasthan RERA returned HTTP {error.code}."})
        except (URLError, TimeoutError, OSError):
            self._send_json(502, {"ok": False, "error": "Could not reach the Rajasthan RERA service."})
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(502, {"ok": False, "error": "Rajasthan RERA returned an unreadable response."})

    def _proxy_gujarat_rera(self):
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 8192)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            registration_number = str(payload.get("RegistrationNo", "")).strip()
        except (ValueError, UnicodeDecodeError, AttributeError):
            self._send_json(400, {"ok": False, "error": "Expected JSON with a RegistrationNo field."})
            return

        if not registration_number or len(registration_number) > 180:
            self._send_json(400, {"ok": False, "error": "A valid RegistrationNo is required."})
            return

        request_body = json.dumps({"query": registration_number, "dataSize": 25, "startWith": 0}).encode("utf-8")
        request = Request(
            GUJARAT_RERA_API,
            data=request_body,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            tls_context = ssl.create_default_context()
            tls_context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0)
            with urlopen(request, timeout=20, context=tls_context) as response:
                upstream_body = response.read(2_000_000)
                upstream_payload = json.loads(upstream_body.decode("utf-8-sig"))
                self._send_json(200, upstream_payload)
        except HTTPError as error:
            self._send_json(502, {"ok": False, "error": f"Gujarat RERA returned HTTP {error.code}."})
        except (URLError, TimeoutError, OSError):
            self._send_json(502, {"ok": False, "error": "Could not reach the Gujarat RERA service."})
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(502, {"ok": False, "error": "Gujarat RERA returned an unreadable response."})


if __name__ == "__main__":
    # Prepare only missing standard tables on first local startup. Existing
    # tables and data are left as-is; credentials come from MYSQL_* or a hidden
    # terminal prompt through the onboarding helper.
    try:
        from city_onboarding import db_connect, ensure_schema

        schema_connection = db_connect()
        try:
            created_tables = ensure_schema(schema_connection)
        finally:
            schema_connection.close()
        if created_tables:
            print("Database schema ready; created missing tables: " + ", ".join(created_tables))
        else:
            print("Database schema ready; all standard tables already exist.")
    except Exception as error:
        raise SystemExit(
            "Database first-run setup failed. Check that MySQL is running, "
            "the configured account can create the database/tables if missing, "
            f"and city_onboarding_schema.sql is present. Details: {error}"
        ) from error

    port = int(os.environ.get("PORT", "4000"))
    print(f"NRI Ease prototype running at http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), PrototypeHandler).serve_forever()
