# Graph Report - .  (2026-04-22)

## Corpus Check
- 78 files · ~83,686 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 348 nodes · 545 edges · 22 communities detected
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 38 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Project Architecture & Pipeline|Project Architecture & Pipeline]]
- [[_COMMUNITY_Target Companies & Job Descriptions|Target Companies & Job Descriptions]]
- [[_COMMUNITY_UI Design & API Layer|UI Design & API Layer]]
- [[_COMMUNITY_Application Outputs & Candidate|Application Outputs & Candidate]]
- [[_COMMUNITY_HTTP Server Module|HTTP Server Module]]
- [[_COMMUNITY_Search State Engine|Search State Engine]]
- [[_COMMUNITY_Candidate Work History|Candidate Work History]]
- [[_COMMUNITY_Sanity Check Module|Sanity Check Module]]
- [[_COMMUNITY_LinkedIn Phase 2 Search|LinkedIn Phase 2 Search]]
- [[_COMMUNITY_Group Search Runner|Group Search Runner]]
- [[_COMMUNITY_Marketing CV Applications|Marketing CV Applications]]
- [[_COMMUNITY_Summary Generator|Summary Generator]]
- [[_COMMUNITY_PDF Generator|PDF Generator]]
- [[_COMMUNITY_Job Detail Refetcher|Job Detail Refetcher]]
- [[_COMMUNITY_Stepstone Search|Stepstone Search]]
- [[_COMMUNITY_LinkedIn MCP Client|LinkedIn MCP Client]]
- [[_COMMUNITY_Review Gate|Review Gate]]
- [[_COMMUNITY_Phase 4 Summary|Phase 4 Summary]]
- [[_COMMUNITY_IMG CV Group|IMG CV Group]]
- [[_COMMUNITY_EM CV Group|EM CV Group]]
- [[_COMMUNITY_EM Source CV|EM Source CV]]
- [[_COMMUNITY_IMG Source CV|IMG Source CV]]

## God Nodes (most connected - your core abstractions)
1. `Project Spec — LinkedIn CV Agent` - 25 edges
2. `CV Draft — Zenith Deutschland Media Performance Analyst` - 16 edges
3. `record()` - 12 edges
4. `Boru Lai (Candidate)` - 11 edges
5. `CV Group: group-pdm (Product/Digital Marketing)` - 11 edges
6. `main()` - 10 edges
7. `get_job_details_batch()` - 9 edges
8. `dedup_and_sort()` - 9 edges
9. `get_job_details_batch()` - 9 edges
10. `Job Analysis Summary (All Groups)` - 9 edges

## Surprising Connections (you probably didn't know these)
- `CV Draft — Zenith Deutschland Media Performance Analyst` --references--> `Source CV — Data Analytics (my_cv_da.pdf)`  [INFERRED]
  output/Zenith-Deutschland_Media-Performance-Analyst/cv_draft.md → my_cv/my_cv_da.pdf
- `Skills Analysis Panel (Matched / Missing)` --semantically_similar_to--> `CV Changes Summary — Zenith Deutschland Media Performance Analyst`  [INFERRED] [semantically similar]
  UI/job_detail_page/code.html → output/Zenith-Deutschland_Media-Performance-Analyst/cv_changes.md
- `Match Score Gauge (SVG Ring)` --semantically_similar_to--> `Attribution Analytics & Performance Measurement`  [INFERRED] [semantically similar]
  UI/job_detail_page/code.html → output/Zenith-Deutschland_Media-Performance-Analyst/cv_draft.md
- `Backlog: Application Funnel View (Sankey/Horizontal Bar)` --semantically_similar_to--> `Application Record 4-State Tracking`  [INFERRED] [semantically similar]
  BACKLOG.md → SPEC.md
- `CV Group: DA (Data Analytics)` --references--> `Source CV — Data Analytics (my_cv_da.pdf)`  [INFERRED]
  UI/My_CVs/code.html → my_cv/my_cv_da.pdf

## Hyperedges (group relationships)
- **CV Tailoring Pipeline: Parsed CV + JD Analysis → Tailored CV + Cover Letter** — cv_parsed_boru_lai, concept_jd_analysis_json, concept_phase3a_cv_cl_gen, concept_cv_rewrite_rules [EXTRACTED 0.95]
- **Web UI Data Flow: server.py + config.json + jd_analysis.json → Dashboard Pages** — concept_server_py, concept_config_json, concept_jd_analysis_json, concept_web_ui_page1_dashboard [EXTRACTED 0.90]
- **Job Search Pipeline: LinkedIn MCP + Stepstone MCP → search_history.json** — concept_linkedin_scraper_mcp, concept_stepstone_mcp, concept_phase2_job_search, concept_search_history_json [EXTRACTED 0.90]
- **group-pdm Job Descriptions Cluster** — jd_datasite_product_marketing_specialist, jd_wack_junior_online_marketing_seo, jd_eao_marketing_content_specialist, jd_emnify_digital_marketing_specialist, jd_franke_ecommerce_growth_specialist, jd_haystack_marketing_graduate, jd_jobgether_marketing_operations_specialist, jd_mintos_junior_lifecycle_retention, jd_renesas_product_marketing_specialist, jd_reonic_digital_marketing_specialist, jd_rose_bikes_sales_marketing_analyst [EXTRACTED 1.00]
- **Tailored CV + Cover Letter + Changes per Application** — messe_cv_draft, messe_cover_letter, messe_cv_changes [EXTRACTED 1.00]
- **Candidate Core Differentiating Skills (PL-300, Customer Journey, Cohort Analysis)** — skill_powerbi_pl300, skill_customer_journey_mapping, skill_cohort_analysis [INFERRED 0.80]
- **Kinetic Archive Design System Applied Across All UI Pages** — ui_velocity_talent_design, ui_job_detail_html, ui_dashboard_html, ui_my_cvs_html [EXTRACTED 0.95]
- **Zenith Deutschland Application Bundle (CV Draft + Changes + Cover Letter)** — zenith_cv_draft, zenith_cv_changes, zenith_cover_letter [EXTRACTED 1.00]
- **CV Groups Mapped to Source PDF Files** — cv_group_da, cv_group_pm, cv_group_pdm [INFERRED 0.85]

## Communities

### Community 0 - "Project Architecture & Pipeline"
Cohesion: 0.08
Nodes (47): All for One I Analytics Senior Consultant JD Text, Project Backlog, LinkedIn CV Agent CLAUDE.md, POST /api/group-save Endpoint (Pending), POST /api/search + SSE Log Streaming, Backlog: Application Funnel View (Sankey/Horizontal Bar), Application Record 4-State Tracking, classifySkill() — 6-Category Skill Classifier (+39 more)

### Community 1 - "Target Companies & Job Descriptions"
Cohesion: 0.08
Nodes (30): Datasite / Sherpany, EAO, emnify, Franke Group, Haystack (recruiting for FMCG brand), Intersnack Group, Jobgether (partner company), Renesas Electronics (+22 more)

### Community 2 - "UI Design & API Layer"
Cohesion: 0.11
Nodes (28): API Endpoint /api/search (localhost:8080), API SSE Endpoint /api/search-log, CV Group: DA (Data Analytics), CV Group: PDM (Product Marketing), CV Group: PMO (Project Management Office), Glass Navigation (backdrop-filter blur), Kinetic Archive Design Philosophy, Kinetic Gradient (Primary #005D8F → #0077B5 135deg) (+20 more)

### Community 3 - "Application Outputs & Candidate"
Cohesion: 0.14
Nodes (24): Boru Lai (Candidate), Messe Düsseldorf, Mintos, PUMA Group, SOFTGAMES, Mintos Junior Lifecycle & Retention Marketing Specialist JD, Messe Düsseldorf Cover Letter Draft, Messe Düsseldorf CV Changes Summary (+16 more)

### Community 4 - "HTTP Server Module"
Cohesion: 0.15
Nodes (15): BaseHTTPRequestHandler, HTTPServer, compute_group_stats(), get_keyword_groups(), Handler, _load_search_batches(), parse_jobs(), Return keyword_groups list from config regardless of nesting. (+7 more)

### Community 5 - "Search State Engine"
Cohesion: 0.15
Nodes (21): build_group_meta(), compute_offsets(), dedup_and_sort(), flatten_keywords(), get_batch(), load_cv_skills(), load_history(), new_batch_id() (+13 more)

### Community 6 - "Candidate Work History"
Cohesion: 0.12
Nodes (22): Boru Lai — Job Applicant, ECE Group Hamburg — Working Student Business Development (2024), GRG Banking Corporation Limited — Product Marketing Manager (2019), Hapag-Lloyd AG — Working Student Project Coordination (2024–2025), HSBC — Strategy PMO (2021–2022), Intelligent Power Corporation Limited — Marketing Manager (2020), Moli Media Corporation Limited — Marketing & Project Coordinator (2019), Glow25 Senior Marketing Analyst — Cover Letter Final PDF (+14 more)

### Community 7 - "Sanity Check Module"
Cohesion: 0.22
Nodes (20): check_config(), check_cv_files(), check_cv_parsed_cache(), check_linkedin_mcp(), check_output_dir(), check_progress_files(), _check_schema(), check_search_history() (+12 more)

### Community 8 - "LinkedIn Phase 2 Search"
Cohesion: 0.19
Nodes (19): call_tool(), extract_job_ids_from_result(), get_job_details_batch(), initialize_proc(), _is_ui_noise(), is_valid_job(), kill_proc(), main() (+11 more)

### Community 9 - "Group Search Runner"
Cohesion: 0.19
Nodes (19): call_tool(), extract_job_ids_from_result(), get_job_details_batch(), initialize_proc(), _is_ui_noise(), is_valid_job(), kill_proc(), main() (+11 more)

### Community 10 - "Marketing CV Applications"
Cohesion: 0.12
Nodes (20): ADAC Marketing Analyst Cover Letter Draft, ADAC CV Changes Summary, ADAC CV Draft, Bionorica SE Cover Letter, Bionorica SE CV Changes, Bionorica SE Tailored CV, CV Rewrite Rules (Rewording Only, No Fabrication), CV Group: group-pmo (Project Management Office) (+12 more)

### Community 11 - "Summary Generator"
Cohesion: 0.23
Nodes (12): build_markdown(), cross_source_dedup(), extract_group_id(), fmt_list(), load_all_analyses(), main(), 根据记录列表生成 Markdown 汇总表（列顺序按 Orchestrator.md 规范）。, 扫描 output/*/jd_analysis.json，返回所有成功解析的记录列表。 (+4 more)

### Community 12 - "PDF Generator"
Cohesion: 0.27
Nodes (11): build_css_from_theme(), generate_pdf(), get_all_themes(), list_themes(), load_theme_factory_themes(), 合并 theme-factory 主题和内建主题（theme-factory 优先）。, 解析主题名称，返回 (css_string, theme_dict)。     优先级：theme-factory CSS 文件 > theme-factory, Strip <script>/<style> tags and on* event attributes to prevent injection. (+3 more)

### Community 13 - "Job Detail Refetcher"
Cohesion: 0.3
Nodes (11): get_details_batch(), initialize(), _is_ui_noise(), main(), make_proc(), parse_job_details(), parse_job_posting(), Fetch details for a batch of job_ids. Returns {job_id: parsed_dict}. (+3 more)

### Community 14 - "Stepstone Search"
Cohesion: 0.24
Nodes (11): main(), make_stepstone_job_id(), parse_job_details_response(), parse_search_response(), Parse get_job_details text response into structured fields.     Handles new emoj, Open one SSE session, search all keywords for a group at one zip_code,     then, Run searches for all groups × zip_codes sequentially., Generate stable ID: st_ + first 16 hex chars of SHA256(url).     16 hex = 64-bit (+3 more)

### Community 16 - "LinkedIn MCP Client"
Cohesion: 0.5
Nodes (4): Send a JSON-RPC message and read a matching response., Launch linkedin-scraper-mcp, perform initialize handshake,     call search_jobs, search_jobs(), send_recv()

### Community 21 - "Review Gate"
Cohesion: 1.0
Nodes (1): Phase 3B: Human Review

### Community 22 - "Phase 4 Summary"
Cohesion: 1.0
Nodes (1): Phase 4: Summary

### Community 23 - "IMG CV Group"
Cohesion: 1.0
Nodes (1): CV Group: group-internal-marketing

### Community 24 - "EM CV Group"
Cohesion: 1.0
Nodes (1): CV Group: group-event-management

### Community 25 - "EM Source CV"
Cohesion: 1.0
Nodes (1): Source CV — Event Management (my_cv_em.pdf)

### Community 26 - "IMG Source CV"
Cohesion: 1.0
Nodes (1): Source CV — Internal Marketing (my_cv_img.pdf)

## Knowledge Gaps
- **97 isolated node(s):** `检查 theme-factory skill 是否已安装。`, `Launch uvx linkedin-scraper-mcp as a subprocess, send an MCP initialize     mess`, `Spawn uvx linkedin-scraper-mcp briefly to trigger package download/cache,     th`, `Verify that uvx linkedin-scraper-mcp is reachable via MCP initialize.     On fir`, `HTTP GET to Stepstone MCP server to verify it is running.     Uses stepstone.ser` (+92 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Review Gate`** (1 nodes): `Phase 3B: Human Review`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Phase 4 Summary`** (1 nodes): `Phase 4: Summary`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `IMG CV Group`** (1 nodes): `CV Group: group-internal-marketing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `EM CV Group`** (1 nodes): `CV Group: group-event-management`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `EM Source CV`** (1 nodes): `Source CV — Event Management (my_cv_em.pdf)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `IMG Source CV`** (1 nodes): `Source CV — Internal Marketing (my_cv_img.pdf)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Project Spec — LinkedIn CV Agent` connect `Project Architecture & Pipeline` to `Marketing CV Applications`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `search_group_zip()` connect `Stepstone Search` to `Group Search Runner`, `Job Detail Refetcher`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Why does `call_tool()` connect `Group Search Runner` to `Stepstone Search`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **What connects `检查 theme-factory skill 是否已安装。`, `Launch uvx linkedin-scraper-mcp as a subprocess, send an MCP initialize     mess`, `Spawn uvx linkedin-scraper-mcp briefly to trigger package download/cache,     th` to the rest of the system?**
  _97 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Project Architecture & Pipeline` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Target Companies & Job Descriptions` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `UI Design & API Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._