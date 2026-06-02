# Graph Report - F:/Claude code project/jobit/1_generate_linkedin_cv  (2026-05-31)

## Corpus Check
- 248 files · ~120,000 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 711 nodes · 1023 edges · 26 communities detected
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 62 edges (avg confidence: 0.81)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Leon Job Application Materials|Leon Job Application Materials]]
- [[_COMMUNITY_Candidate Profile & Skills|Candidate Profile & Skills]]
- [[_COMMUNITY_Web UI & Project Spec|Web UI & Project Spec]]
- [[_COMMUNITY_PMO Group Job Listings|PMO Group Job Listings]]
- [[_COMMUNITY_MCP Common Utilities|MCP Common Utilities]]
- [[_COMMUNITY_HTTP Server & API Backend|HTTP Server & API Backend]]
- [[_COMMUNITY_Product Marketing Job Listings|Product Marketing Job Listings]]
- [[_COMMUNITY_Stepstone Search & State|Stepstone Search & State]]
- [[_COMMUNITY_Digital Marketing Job Listings|Digital Marketing Job Listings]]
- [[_COMMUNITY_LinkedIn Search Pipeline|LinkedIn Search Pipeline]]
- [[_COMMUNITY_Kelebogie Applications|Kelebogie Applications]]
- [[_COMMUNITY_Sanity Check System|Sanity Check System]]
- [[_COMMUNITY_Specialist Role Listings|Specialist Role Listings]]
- [[_COMMUNITY_Leon User Profile & Groups|Leon User Profile & Groups]]
- [[_COMMUNITY_Job Summary Generator|Job Summary Generator]]
- [[_COMMUNITY_Multi-user Migration Tools|Multi-user Migration Tools]]
- [[_COMMUNITY_PDF Generation Engine|PDF Generation Engine]]
- [[_COMMUNITY_Analytics Group Job Listings|Analytics Group Job Listings]]
- [[_COMMUNITY_Skills Translation Utility|Skills Translation Utility]]
- [[_COMMUNITY_Brand Marketing Listings|Brand Marketing Listings]]
- [[_COMMUNITY_JD Analysis & Scoring|JD Analysis & Scoring]]
- [[_COMMUNITY_UI HTML Templates|UI HTML Templates]]
- [[_COMMUNITY_CV Parser Agent|CV Parser Agent]]
- [[_COMMUNITY_Config & Keyword Groups|Config & Keyword Groups]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]

## God Nodes (most connected - your core abstractions)
1. `Boru Lai (Candidate)` - 29 edges
2. `record()` - 12 edges
3. `A/B Testing & Experimentation` - 12 edges
4. `CV Group: group-pdm (Product Marketing Management)` - 11 edges
5. `main()` - 10 edges
6. `search_keyword()` - 10 edges
7. `get_job_details_batch()` - 9 edges
8. `dedup_and_sort()` - 9 edges
9. `send_recv()` - 9 edges
10. `get_job_details_batch()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `UI Component: Skills Analysis Panel (Matched / Missing)` --semantically_similar_to--> `Zenith Deutschland CV Changes Summary`  [INFERRED] [semantically similar]
  UI/job_detail_page/code.html → ARCHIVE_pre_multiuser/output/Zenith-Deutschland_Media-Performance-Analyst/cv_changes.md
- `UI Component: Match Score Gauge (SVG Ring)` --semantically_similar_to--> `Attribution Analytics & Performance Measurement`  [INFERRED] [semantically similar]
  UI/job_detail_page/code.html → ARCHIVE_pre_multiuser/output/Zenith-Deutschland_Media-Performance-Analyst/cv_draft.md
- `Role: Franke E-Commerce Growth Specialist` --conceptually_related_to--> `E-Commerce & Multi-channel Analytics`  [INFERRED]
  users/leon/output/group-pdm_Franke-Group_E-Commerce-Growth-Specialist-fmd/jd_text.txt → ARCHIVE_pre_multiuser/output/group-pdm_ROSE-Bikes_Sales-and-Marketing-Analyst-Commerce-mwd/jd_text.txt
- `_mcp_handshake_ok()` --calls--> `make_mcp_proc()`  [INFERRED]
  F:\Claude code project\jobit\1_generate_linkedin_cv\scripts\check.py → F:\Claude code project\jobit\1_generate_linkedin_cv\scripts\common.py
- `_mcp_handshake_ok()` --calls--> `send_recv()`  [INFERRED]
  F:\Claude code project\jobit\1_generate_linkedin_cv\scripts\check.py → F:\Claude code project\jobit\1_generate_linkedin_cv\scripts\_run_group_search.py

## Hyperedges (group relationships)
- **Startup Sequence** —  [INFERRED 1.00]
- **CV Generation Pipeline** —  [INFERRED 1.00]
- **Dual Source Search** —  [INFERRED 1.00]
- **Candidate Strength Profile** —  [INFERRED 0.90]
- **Group-CV Mapping** —  [INFERRED 1.00]
- **Product & Digital Marketing Job Group (group-pdm)** — appinio_role_csm, datasite_role_pms, drwack_role_joms, eao_role_mcs, emnify_role_dms, franke_role_egs, haystack_role_mg, innonature_role_crm, jobgether_role_mos, lekkerland_role_uxram, mintos_role_jlrm, rebuy_role_apro, renesas_role_pms, reonic_role_dms, rosebikes_role_sma, trivago_role_da, hela_role_pmm [EXTRACTED 1.00]
- **PMO / Project Management Job Group (group-pmo)** — aldi_role_pmo, climatepartner_role_spmo, digooh_role_pm, koenigneumath_role_spmo [EXTRACTED 1.00]
- **Digital Advertising Job Group (group-da)** — zweidigital_role_pmm [EXTRACTED 1.00]
- **A/B Testing required across multiple roles** — innonature_role_crm, lekkerland_role_uxram, mintos_role_jlrm, rebuy_role_apro, trivago_role_da [EXTRACTED 1.00]
- **PMO Group JD Cluster (LA Lernallianz + MEAG)** —  [EXTRACTED 1.00]
- **Messe Düsseldorf Application Bundle (CV Draft + Changes + Cover Letter)** —  [EXTRACTED 1.00]
- **PUMA Group Application Bundle (CV Tailored + Changes + Cover Letter)** —  [EXTRACTED 1.00]
- **SOFTGAMES Application Bundle (CV Draft + Changes + Cover Letter)** —  [EXTRACTED 1.00]
- **Zenith Deutschland Application Bundle (CV Draft + Changes + Cover Letter)** —  [EXTRACTED 1.00]
- **Kinetic Archive Design System Applied Across All UI Pages** —  [EXTRACTED 0.95]
- **Candidate Core Differentiating Skills (PL-300, Customer Journey, Cohort Analysis, A/B Testing)** —  [INFERRED 0.80]
- **Kelebogie Batch 20260531: 3 Job Applications (CV + CL + Changes)** — kelebogie_batch_20260531, kelebogie_crossing_hurdles_cv, kelebogie_crossing_hurdles_cl, kelebogie_crossing_hurdles_changes, kelebogie_alignerr_cv, kelebogie_alignerr_cl, kelebogie_alignerr_changes, kelebogie_fti_cv, kelebogie_fti_cl, kelebogie_fti_changes [EXTRACTED 1.00]
- **Kelebogie group-econ-research: 54 jobs analyzed** — kelebogie_group_econ_research, job_crossing_hurdles_policy, job_alignerr_ai_policy, job_fti_consulting [EXTRACTED 1.00]
- **Kelebogile Riet Work History (4 internships)** — kelebogie_candidate_profile, kelebogie_nc_treasury, kelebogie_dedat, kelebogie_dept_education, kelebogie_salga [EXTRACTED 1.00]
- **Leon Three Active Search Groups (da, pmo, pdm)** — leon_candidate_profile, leon_group_da, leon_group_pmo, leon_group_pdm [EXTRACTED 1.00]
- **LinkedIn CV Agent Complete Workflow** — agent_workflow_phases, kelebogie_spec, leon_spec, pdf_generation_fpdf2 [INFERRED 0.85]

## Communities

### Community 0 - "Leon Job Application Materials"
Cohesion: 0.05
Nodes (69): Boru Lai, Microsoft Certified: Power BI Data Analyst Associate PL-300, SOFTGAMES: GRG bullets reordered to lead with performance analytics over product/market work, SOFTGAMES: HSBC bullet label changed to Dashboard Development, added 'in Power BI' factually, SOFTGAMES: Moli Media bullet 1 reframed to foreground cohort analytics without adding new content, SOFTGAMES: Moli Media KOL bullet reframed as performance measurement / UA analogue, SOFTGAMES: Skills reordered to lead with cohort analysis and A/B testing per JD requirements, SOFTGAMES: Summary rewritten to foreground cohort analysis, A/B testing, PL-300 certification (+61 more)

### Community 1 - "Candidate Profile & Skills"
Cohesion: 0.05
Nodes (62): GET /api/group-stats, GET /api/jobs, POST /api/search, Application Record (4-state), Boru Lai (Candidate), CLAUDE.md, Color System, config.json (+54 more)

### Community 2 - "Web UI & Project Spec"
Cohesion: 0.04
Nodes (57): Cover Letter: ADAC Marketinganalyst, CV Changes: ADAC Marketinganalyst, CV Draft: ADAC Marketinganalyst, Cover Letter: Bionorica SE Marketing Analyst, CV Changes: Bionorica SE Marketing Analyst, CV Tailored: Bionorica SE Marketing Analyst, Company: ADAC, Company: All for One (+49 more)

### Community 3 - "PMO Group Job Listings"
Cohesion: 0.04
Nodes (52): ALDI Einkauf SE & Co. oHG, PMO ERP Transformation (ALDI), ClimatePartner GmbH, Senior PMO Manager (ClimatePartner), ALDI Einkauf SE & Co. oHG, ClimatePartner GmbH, DIGOOH Media GmbH, König + Neurath AG (+44 more)

### Community 4 - "MCP Common Utilities"
Cohesion: 0.05
Nodes (48): Lekkerland SE (REWE Group), Rebuy Recommerce GmbH, trivago NV, Zenith Deutschland (Publicis Groupe), Franke Group, E-Commerce Growth Specialist (Franke), InnoNature GmbH, Senior CRM Manager (InnoNature) (+40 more)

### Community 5 - "HTTP Server & API Backend"
Cohesion: 0.07
Nodes (46): Boru Lai (Candidate), Company: Glow25, Messe Düsseldorf, Messe Düsseldorf, PUMA Group, PUMA Group, ROSE Bikes, SOFTGAMES (+38 more)

### Community 6 - "Product Marketing Job Listings"
Cohesion: 0.08
Nodes (37): make_mcp_proc(), Background thread: drain stdout into queue; put None sentinel on EOF., Spawn linkedin-scraper-mcp with a background reader thread.      Fixes two bug, Send a JSON-RPC message and return the matching response within *timeout* second, send_recv(), _stdout_reader_loop(), Launch linkedin-scraper-mcp, perform initialize handshake,     call search_jobs, search_jobs() (+29 more)

### Community 7 - "Stepstone Search & State"
Cohesion: 0.1
Nodes (34): BaseHTTPRequestHandler, HTTPServer, _build_job_family_prompt(), compute_group_stats(), compute_search_analysis(), _cur_uid(), get_config_path(), get_cv_dir() (+26 more)

### Community 8 - "Digital Marketing Job Listings"
Cohesion: 0.08
Nodes (36): _extract_posted_days_ago(), main(), make_stepstone_job_id(), parse_job_details_response(), parse_search_response(), Parse get_job_details text response into structured fields.     Handles new emo, Open one SSE session, search all keywords for a group at one zip_code,     then, Run searches for all groups × zip_codes sequentially. (+28 more)

### Community 9 - "LinkedIn Search Pipeline"
Cohesion: 0.06
Nodes (32): APPINIO GmbH, Senior Customer Success Manager DACH (APPINIO), InnoNature GmbH, Mintos, Reonic, emnify, Digital Marketing Specialist (emnify), Senior CRM Manager — InnoNature GmbH (+24 more)

### Community 10 - "Kelebogie Applications"
Cohesion: 0.13
Nodes (26): call_tool(), extract_job_ids_from_result(), get_job_details_batch(), initialize_proc(), _is_jp_noise(), _is_ui_noise(), is_valid_job(), kill_proc() (+18 more)

### Community 11 - "Sanity Check System"
Cohesion: 0.1
Nodes (26): Job: Alignerr — AI Policy Ethics & Compliance Analyst (Score 52), Job: Crossing Hurdles — Policy Analyst $25/hour Remote (Score 88), Job: FTI Consulting — Consultant German Markets Economic Financial (Score 52), CV Changes — Alignerr AI Policy Analyst, Cover Letter — Alignerr AI Policy Analyst, CV Draft — Alignerr AI Policy Analyst, Kelebogie Batch 20260531_001, Kelebogile Riet — Candidate Profile (+18 more)

### Community 12 - "Specialist Role Listings"
Cohesion: 0.1
Nodes (23): Project Spec — LinkedIn CV Agent (Amy user), Design Component: Glass Navigation (backdrop-filter blur), Design Token: Kinetic Gradient (#005D8F → #0077B5 135deg), Design Principle: No-Line Rule (tonal separation), Design Typography Triad: Manrope / Inter / Space Grotesk, Feature: CV Tailoring Pipeline (Phase 3A), Feature: Dual-Source Job Search (LinkedIn + Stepstone), Feature: Multi-User Support (users/ directory) (+15 more)

### Community 13 - "Leon User Profile & Groups"
Cohesion: 0.22
Nodes (20): check_config(), check_cv_files(), check_cv_parsed_cache(), check_linkedin_mcp(), check_output_dir(), check_progress_files(), _check_schema(), check_search_history() (+12 more)

### Community 14 - "Job Summary Generator"
Cohesion: 0.11
Nodes (18): Jobgether, Dr. O.K. Wack Chemie GmbH, Junior Online Marketing Specialist SEO (Dr. Wack), EAO, Marketing Content Specialist (EAO), Marketing Operations Specialist — Jobgether, Jobgether (partner), Marketing Operations Specialist (Jobgether) (+10 more)

### Community 15 - "Multi-user Migration Tools"
Cohesion: 0.15
Nodes (16): Leon — Candidate Profile (Data-driven marketing analytics), Leon CV Parsed, ECE Group Hamburg — Working Student Business Development (Leon), Leon Group: Marketing Analytics (group-da), Leon Group: Product Marketing Management (group-pdm), Leon Group: Project Management Office (group-pmo), HSBC — Strategy PMO (Leon Work Experience), Job: CROWDCONSULTANTS — PMO Product Portfolio Lead (Score 95) (+8 more)

### Community 16 - "PDF Generation Engine"
Cohesion: 0.2
Nodes (14): build_markdown(), cross_source_dedup(), extract_group_id(), fmt_list(), load_all_analyses(), load_last_seen(), main(), 从文件夹名称动态提取 group-id（取首个下划线前的 group- 前缀）。 (+6 more)

### Community 17 - "Analytics Group Job Listings"
Cohesion: 0.21
Nodes (9): _copy_tree(), _create_hardlink(), _create_junction(), _create_user_workspace(), migrate_leon(), Create Windows junction point (no admin required)., Create hard link (same filesystem, no admin required)., Copy directory tree, skip existing files. (+1 more)

### Community 18 - "Skills Translation Utility"
Cohesion: 0.27
Nodes (11): build_css_from_theme(), generate_pdf(), get_all_themes(), list_themes(), load_theme_factory_themes(), 合并 theme-factory 主题和内建主题（theme-factory 优先）。, 解析主题名称，返回 (css_string, theme_dict)。     优先级：theme-factory CSS 文件 > theme-factor, Strip <script>/<style> tags and on* event attributes to prevent injection. (+3 more)

### Community 19 - "Brand Marketing Listings"
Cohesion: 0.2
Nodes (11): LA Lernallianz GmbH, MEAG MUNICH ERGO AssetManagement GmbH, LA Lernallianz GmbH — PMO / Transformation Manager JD, MEAG MUNICH ERGO — Project Manager Organization Transformation & Strategy JD, PMO / Transformation Manager (m/w/d), Project Manager Organization — Transformation & Strategy, Asset Management / Financial Services Domain, Change Management & Transformation (+3 more)

### Community 20 - "JD Analysis & Scoring"
Cohesion: 0.43
Nodes (6): collect_german_entries(), is_german(), main(), Return list of (jd_file, field_name, index, original_text) for German entries., Translate all texts in batches via claude -p (file-based I/O)., translate_batch()

### Community 21 - "UI HTML Templates"
Cohesion: 0.33
Nodes (7): Haystack, Haystack (recruiter), Marketing Graduate / Brand Manager (Haystack), Brand Manager (Marketing Graduate) — Haystack, Hesse, Germany, Brand Management, Consumer & Shopper Insights

### Community 23 - "CV Parser Agent"
Cohesion: 0.5
Nodes (4): DIGOOH Media GmbH, Projektmanager Portfoliomanagement (DIGOOH), Advanced Excel (SVERWEIS, Pivot), Portfolio & Partner Management (DOOH)

### Community 24 - "Config & Keyword Groups"
Cohesion: 0.67
Nodes (4): LinkedIn CV Agent Workflow Phases (Phase 1-4), Kelebogie User SPEC, Leon User SPEC, Web UI Specification (job_tracker server)

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Multi-Channel Data Activation & Personalisation

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): MS Excel

## Knowledge Gaps
- **227 isolated node(s):** `检查 theme-factory skill 是否已安装。`, `Launch uvx linkedin-scraper-mcp and verify it responds to MCP initialize.`, `Spawn uvx linkedin-scraper-mcp briefly to trigger package download/cache,     t`, `Verify that uvx linkedin-scraper-mcp is reachable via MCP initialize.     On fi`, `HTTP GET to Stepstone MCP server to verify it is running.     Uses stepstone.se` (+222 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 36`** (1 nodes): `Multi-Channel Data Activation & Personalisation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `MS Excel`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Boru Lai (Candidate)` connect `HTTP Server & API Backend` to `Web UI & Project Spec`, `MCP Common Utilities`, `Specialist Role Listings`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **What connects `检查 theme-factory skill 是否已安装。`, `Launch uvx linkedin-scraper-mcp and verify it responds to MCP initialize.`, `Spawn uvx linkedin-scraper-mcp briefly to trigger package download/cache,     t` to the rest of the system?**
  _227 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Leon Job Application Materials` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
- **Should `Candidate Profile & Skills` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
- **Should `Web UI & Project Spec` be split into smaller, more focused modules?**
  _Cohesion score 0.04 - nodes in this community are weakly interconnected._
- **Should `PMO Group Job Listings` be split into smaller, more focused modules?**
  _Cohesion score 0.04 - nodes in this community are weakly interconnected._
- **Should `MCP Common Utilities` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._