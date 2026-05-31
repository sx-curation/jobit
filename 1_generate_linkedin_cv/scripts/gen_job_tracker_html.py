#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate C:/Users/Leon/Desktop/job_tracker/index.html
Lean template — all job data is loaded at runtime from server.py (/api/jobs).
Run: python scripts/gen_job_tracker_html.py
Then: python scripts/server.py
"""
import sys, io, os, json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DEST = Path("C:/Users/Leon/Desktop/job_tracker/index.html")

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@700;800&family=Space+Grotesk:wght@400;500;600&family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<style>
* { box-sizing: border-box; }
body { font-family: 'Inter', sans-serif; background: #F8F9FA; color: #191c1d; margin: 0; }
.material-symbols-outlined { font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24; vertical-align:middle; line-height:1; user-select:none; }
.kinetic-gradient { background: linear-gradient(135deg,#005d8f 0%,#0077b5 100%); }
.glass-nav { backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); background:rgba(248,249,250,.92); }

/* Pages */
.page { display:none; }
.page.active { display:block; }

/* Score badge */
.score-badge { display:inline-flex; align-items:center; justify-content:center;
  min-width:42px; padding:3px 10px; border-radius:9999px;
  font-family:'Space Grotesk',monospace; font-size:12px; font-weight:700;
  cursor:pointer; transition:box-shadow .15s, transform .15s; }
.score-badge:hover { box-shadow:0 4px 12px rgba(0,0,0,.18); transform:translateY(-1px); }

/* Segmented control */
.seg-track { background:#e1e3e4; padding:4px; border-radius:9999px; display:inline-flex; gap:2px; flex-wrap:wrap; }
.seg-btn { padding:5px 14px; border-radius:9999px; font-family:'Space Grotesk',sans-serif;
  font-size:12px; font-weight:500; border:none; cursor:pointer; background:transparent;
  color:#404850; transition:.15s; white-space:nowrap; }
.seg-btn.active { background:#fff; color:#005d8f; box-shadow:0 1px 3px rgba(0,0,0,.1); }

/* Table scroll wrapper — overflow:auto makes sticky thead top:0 work */
.table-scroll-wrapper { max-height: calc(100vh - 310px); overflow:auto; border-radius:.75rem .75rem 0 0; }
.jobs-table { width:100%; border-collapse:collapse; min-width:1050px; }
.jobs-table thead th {
  padding:11px 14px; font-family:'Space Grotesk',sans-serif; font-size:10px; font-weight:600;
  text-transform:uppercase; letter-spacing:.07em; color:#707881; text-align:left;
  position:sticky; top:0; z-index:20; background:#e7e8e9;
  box-shadow:0 1px 0 #d1d5db; white-space:nowrap; }
.jobs-table tbody tr { border-bottom:1px solid #f3f4f5; transition:background .1s; cursor:pointer; }
.jobs-table tbody tr:nth-child(even) { background:#f8f9fa; }
.jobs-table tbody tr:hover { background:#EFF6FF; }
.jobs-table td { padding:9px 14px; font-size:13px; vertical-align:middle; }

/* 3-line clamp with tooltip */
.line-clamp-3 { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }

/* Group tag */
.group-tag { background:#edeeef; color:#404850; border-radius:4px; padding:2px 7px;
  font-family:'Space Grotesk',monospace; font-size:11px; }

/* Source */
.src-li { color:#0077b5; font-weight:600; font-size:12px; }
.src-ss { color:#f97316; font-weight:600; font-size:12px; }

/* Application record buttons */
.rec-wrap { display:flex; gap:4px; align-items:center; }
.rec-btn { width:26px; height:26px; border-radius:50%; border:1.5px solid #d1d5db;
  font-size:13px; cursor:pointer; background:#fff; display:flex; align-items:center;
  justify-content:center; transition:.15s; padding:0; }
.rec-btn:hover { border-color:#9ca3af; transform:scale(1.1); }
.rec-btn.active-success { background:#DCFCE7; border-color:#22C55E; }
.rec-btn.active-invalid  { background:#FEE2E2; border-color:#EF4444; }

/* Remark badge */
.remark-badge { background:#FEF9C3; color:#854d0e; border-radius:4px; padding:2px 6px;
  font-size:10px; font-family:'Space Grotesk',monospace; font-weight:600; white-space:nowrap; }

/* Pagination */
.page-btn { width:30px; height:30px; border-radius:9999px; border:none; cursor:pointer;
  font-family:'Space Grotesk',sans-serif; font-size:12px; font-weight:600;
  background:#fff; color:#707881; transition:.15s; box-shadow:0 1px 3px rgba(0,0,0,.08); }
.page-btn.current { background:#005d8f; color:#fff; }
.page-btn:hover:not(.current) { color:#005d8f; }
.page-btn:disabled { opacity:.4; cursor:default; }

/* Loading button */
#loading-btn { font-family:'Space Grotesk',sans-serif; font-size:12px; font-weight:700;
  padding:7px 18px; border-radius:9999px; border:none; cursor:pointer;
  background:linear-gradient(135deg,#005d8f,#0077b5); color:#fff;
  transition:.15s; white-space:nowrap; display:flex; align-items:center; gap:6px; }
#loading-btn:disabled { opacity:.7; cursor:not-allowed; }

/* Stats cards */
.stat-card { background:#fff; border-radius:1rem; padding:20px 24px; box-shadow:0 1px 3px rgba(0,0,0,.07); }
.stat-card .stat-val { font-family:Manrope; font-size:28px; font-weight:800; color:#191c1d; }
.stat-card .stat-label { font-family:'Space Grotesk'; font-size:10px; font-weight:600;
  text-transform:uppercase; letter-spacing:.07em; color:#707881; }
.stat-card .stat-sub { font-size:11px; color:#9ca3af; margin-top:2px; }

/* Detail page */
.detail-card { background:#fff; border-radius:1rem; padding:28px; box-shadow:0 1px 3px rgba(0,0,0,.07); }
.matched-row { display:flex; align-items:center; gap:10px; padding:6px 0; font-size:13px; border-bottom:1px solid #f3f4f5; }
.emphasis-item { display:flex; gap:10px; margin-bottom:14px; align-items:flex-start; }
.emphasis-num { width:22px; height:22px; border-radius:50%; background:#fed7aa; color:#c2410c;
  display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:700;
  flex-shrink:0; font-family:'Space Grotesk',monospace; margin-top:1px; }
.detail-footer { position:fixed; bottom:0; left:0; width:100%; z-index:50;
  background:#fff; box-shadow:0 -4px 20px rgba(0,0,0,.07); border-radius:1rem 1rem 0 0;
  padding:14px 24px; display:flex; gap:12px; }

/* Error banner */
#error-banner { display:none; background:#FEE2E2; border:1px solid #fca5a5; border-radius:.75rem;
  padding:14px 20px; color:#991b1b; font-size:13px; margin-bottom:16px; }

/* ── Page 4 — My CVs ── */
.group-card { background:#fff; border-radius:12px; padding:24px;
  box-shadow:0 1px 3px rgba(0,0,0,.07); border:1px solid #E5E7EB;
  transition:border-color .2s, box-shadow .2s; position:relative; }
.group-card:hover { border-color:#3B82F6; box-shadow:0 4px 16px rgba(0,0,0,.10); }
.group-icon { width:42px; height:42px; border-radius:10px; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  font-family:'Space Grotesk',monospace; font-size:11px; font-weight:700; color:#fff; }
.kw-chip-en { background:#EFF6FF; color:#1D4ED8; border:1px solid #BFDBFE;
  border-radius:9999px; padding:2px 9px; font-size:11px; font-weight:600; white-space:nowrap; }
.kw-chip-de { background:#EDE9FE; color:#5B21B6; border:1px solid #DDD6FE;
  border-radius:9999px; padding:2px 9px; font-size:11px; font-weight:600; white-space:nowrap; }
.kw-chip-more { background:#F3F4F6; color:#6B7280; border-radius:9999px;
  padding:2px 9px; font-size:11px; font-weight:600; }
.miss-tag { background:#FEF9C3; color:#854D0E; border-radius:4px;
  padding:1px 7px; font-size:11px; font-family:'Space Grotesk',monospace; font-weight:600;
  position:relative; }
.card-section-label { font-family:'Space Grotesk',sans-serif; font-size:10px; font-weight:600;
  text-transform:uppercase; letter-spacing:.07em; color:#9CA3AF; margin-bottom:6px; }
.dropdown-wrap { position:relative; display:inline-block; }
.dropdown-menu { display:none; position:absolute; right:0; top:calc(100% + 4px); z-index:40;
  min-width:140px; background:#fff; border-radius:10px;
  box-shadow:0 8px 24px rgba(0,0,0,.13); overflow:hidden; }
.dropdown-menu.open { display:block; }
.dropdown-item { padding:10px 16px; font-size:13px; cursor:pointer; display:block;
  font-family:'Inter',sans-serif; transition:background .1s; }
.dropdown-item:hover { background:#F3F4F6; }
.dropdown-item.danger { color:#EF4444; }
.dropdown-item.danger:hover { background:#FEE2E2; }
.cv-action-btn { width:28px; height:28px; border-radius:8px; border:none; cursor:pointer;
  background:#F3F4F6; color:#6B7280; font-size:16px; display:flex; align-items:center;
  justify-content:center; transition:.15s; }
.cv-action-btn:hover { background:#E5E7EB; color:#191c1d; }

/* Sortable column headers */
.th-sort { cursor:pointer; user-select:none; }
.th-sort:hover { background:#dde0e2; }
.sort-icon { font-size:9px; opacity:.45; margin-left:3px; }
.th-sort.sort-active .sort-icon { opacity:1; color:#005d8f; }

/* Application record select */
.rec-select { border-radius:9999px; border:1.5px solid #d1d5db; background:#fff;
  font-family:'Space Grotesk',sans-serif; font-size:11px; font-weight:600;
  padding:2px 8px 2px 10px; cursor:pointer; color:#9CA3AF; outline:none;
  transition:.15s; max-width:96px; }
.rec-select[data-state="applied"]   { background:#EFF6FF; color:#1D4ED8; border-color:#1D4ED8; }
.rec-select[data-state="interview"] { background:#EDE9FE; color:#5B21B6; border-color:#5B21B6; }
.rec-select[data-state="invalid"]   { background:#F3F4F6; color:#6B7280; border-color:#9CA3AF; }

/* Materials ready badge */
.mat-badge { display:inline-flex; align-items:center; gap:2px; font-size:10px;
  color:#16A34A; background:#DCFCE7; border-radius:3px; padding:1px 5px;
  font-family:'Space Grotesk',monospace; font-weight:600; white-space:nowrap; margin-bottom:2px; }

/* Notes icon */
.note-icon { color:#D1D5DB; font-size:16px !important; cursor:default; }
.note-icon.has-note { color:#F59E0B; }

/* Matched skills tag (Page 4) */
.match-tag { background:#DCFCE7; color:#166534; border-radius:4px;
  padding:1px 7px; font-size:11px; font-family:'Space Grotesk',monospace; font-weight:600; position:relative; }

/* Notes textarea in detail */
.note-textarea { width:100%; min-height:80px; border:1.5px solid #E5E7EB; border-radius:8px;
  padding:10px 14px; font-size:13px; font-family:'Inter',sans-serif; resize:vertical;
  outline:none; transition:border-color .15s; color:#191c1d; }
.note-textarea:focus { border-color:#005d8f; }
</style>
</head>
<body>

<!-- ═══ NAVBAR ═══ -->
<header class="glass-nav fixed top-0 left-0 w-full z-50 flex items-center justify-between px-8"
  style="height:68px;">
  <div class="flex items-center gap-8">
    <span class="text-xl font-black text-[#0077B5] cursor-pointer select-none"
      style="font-family:Manrope;" onclick="showPage('dashboard')">Job Tracker</span>
    <nav class="hidden md:flex gap-3">
      <a id="nav-dashboard"
        class="text-[#0077B5] border-b-2 border-[#0077B5] pb-0.5 font-bold text-sm"
        href="#" onclick="showPage('dashboard');return false;">Dashboard</a>
      <a id="nav-cvs" class="text-slate-500 font-medium text-sm px-3 py-1 rounded-full hover:bg-gray-100"
        href="#" onclick="navTo('cvs');return false;">My CVs</a>
      <a id="nav-analysis" class="text-slate-500 font-medium text-sm px-3 py-1 rounded-full hover:bg-gray-100"
        href="#" onclick="navTo('analysis');return false;">Analysis</a>
    </nav>
  </div>
  <div class="flex items-center gap-3 flex-1 max-w-xs mx-6">
    <div class="relative w-full">
      <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
        style="font-size:18px;">search</span>
      <input id="search-input"
        class="w-full bg-gray-100 rounded-full py-1.5 pl-9 pr-8 text-sm border-none focus:outline-none focus:ring-2 focus:ring-blue-200"
        placeholder="Company, title…" oninput="onSearch(); toggleSearchClear()">
      <button id="search-clear" onclick="clearSearch()"
        class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 text-base leading-none"
        style="display:none;" title="Clear search">✕</button>
    </div>
  </div>
  <span id="result-count" class="text-xs text-slate-400 font-mono hidden lg:block"></span>
</header>

<!-- ═══ PAGE 1 — DASHBOARD ═══ -->
<div id="page-dashboard" class="page active" style="padding-top:84px;">
<div class="px-6 pb-16 max-w-[1700px] mx-auto">

  <div id="error-banner"></div>

  <!-- Stats row -->
  <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6" id="stats-row">
    <div class="stat-card" style="border-left:4px solid #005d8f; cursor:pointer;"
      id="card-total" onclick="setScoreTier('all')" title="Show all (score ≥30)">
      <div class="stat-label mb-2">Total Jobs</div>
      <div class="stat-val" id="stat-total">—</div>
      <div class="stat-sub text-[10px] text-slate-400">score ≥ 30</div>
    </div>
    <div class="stat-card" style="cursor:pointer;" id="card-high"
      onclick="setScoreTier('high')" title="Filter: High Match ≥70">
      <div class="flex items-center gap-2 mb-2">
        <div class="w-2.5 h-2.5 rounded-full bg-[#22C55E]"></div>
        <span class="stat-label">High Match ≥70</span>
      </div>
      <div class="stat-val" id="stat-green">—</div>
      <div class="stat-sub" id="stat-green-sub"></div>
    </div>
    <div class="stat-card" style="cursor:pointer;" id="card-mid"
      onclick="setScoreTier('mid')" title="Filter: Good Match 45–69">
      <div class="flex items-center gap-2 mb-2">
        <div class="w-2.5 h-2.5 rounded-full bg-[#EAB308]"></div>
        <span class="stat-label">Good Match 45–69</span>
      </div>
      <div class="stat-val" id="stat-yellow">—</div>
      <div class="stat-sub" id="stat-yellow-sub"></div>
    </div>
    <div class="stat-card" style="cursor:pointer;" id="card-low"
      onclick="setScoreTier('low')" title="Filter: Moderate 30–44">
      <div class="flex items-center gap-2 mb-2">
        <div class="w-2.5 h-2.5 rounded-full bg-[#F97316]"></div>
        <span class="stat-label">Moderate 30–44</span>
      </div>
      <div class="stat-val" id="stat-orange">—</div>
      <div class="stat-sub" id="stat-orange-sub"></div>
    </div>
  </div>

  <!-- Filter bar -->
  <div class="bg-white rounded-xl p-4 mb-5 shadow-sm flex flex-wrap gap-4 items-end">
    <!-- Group tabs (built dynamically) -->
    <div class="flex flex-col gap-1.5">
      <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
        style="font-family:'Space Grotesk'">Group</label>
      <div class="seg-track" id="group-tabs"></div>
    </div>
    <!-- Source tabs -->
    <div class="flex flex-col gap-1.5">
      <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
        style="font-family:'Space Grotesk'">Source</label>
      <div class="seg-track" id="source-tabs">
        <button class="seg-btn active" data-source="all">All</button>
        <button class="seg-btn" data-source="LinkedIn">LinkedIn</button>
        <button class="seg-btn" data-source="Stepstone">Stepstone</button>
      </div>
    </div>
    <!-- Score range inputs -->
    <div class="flex flex-col gap-1.5">
      <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
        style="font-family:'Space Grotesk'">Score</label>
      <div class="flex gap-1 items-center">
        <input id="score-min" type="number" min="0" max="100" placeholder="Min"
          class="w-14 border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-600 outline-none focus:border-[#005d8f]"
          oninput="onScoreInput(); debounceFilters()">
        <span class="text-gray-400 text-xs">–</span>
        <input id="score-max" type="number" min="0" max="100" placeholder="Max"
          class="w-14 border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-600 outline-none focus:border-[#005d8f]"
          oninput="onScoreInput(); debounceFilters()">
      </div>
    </div>
    <!-- Date range pickers -->
    <div class="flex flex-col gap-1.5">
      <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
        style="font-family:'Space Grotesk'">1st Fetch Date</label>
      <div class="flex gap-1 items-center">
        <input id="date-from" type="date"
          class="border border-gray-200 rounded-lg px-2 py-1.5 text-xs text-slate-600 outline-none focus:border-[#005d8f]"
          oninput="debounceFilters()">
        <span class="text-gray-400 text-xs">–</span>
        <input id="date-to" type="date"
          class="border border-gray-200 rounded-lg px-2 py-1.5 text-xs text-slate-600 outline-none focus:border-[#005d8f]"
          oninput="debounceFilters()">
      </div>
    </div>
    <!-- Application record filter -->
    <div class="flex flex-col gap-1.5">
      <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
        style="font-family:'Space Grotesk'">Status</label>
      <select id="record-filter" onchange="onRecordFilter()"
        class="text-xs font-semibold px-3 py-1.5 rounded-full outline-none cursor-pointer border-2"
        style="border-color:rgba(0,93,143,.2);color:#005d8f;font-family:'Space Grotesk';background:#fff;min-width:110px;">
        <option value="">All Status</option>
        <option value="__none__">— Track</option>
        <option value="applied">Applied</option>
        <option value="interview">Interview</option>
        <option value="invalid">Invalid</option>
      </select>
    </div>
    <!-- Location filter -->
    <div class="flex flex-col gap-1.5">
      <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
        style="font-family:'Space Grotesk'">Location</label>
      <select id="location-filter" onchange="applyFilters(); saveFilterState();"
        class="text-xs font-semibold px-3 py-1.5 rounded-full outline-none cursor-pointer border-2"
        style="border-color:rgba(0,93,143,.2);color:#005d8f;font-family:'Space Grotesk';background:#fff;min-width:110px;">
        <option value="">All Locations</option>
      </select>
    </div>
    <!-- Reset all filters -->
    <div class="flex flex-col gap-1.5">
      <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
        style="font-family:'Space Grotesk'">&nbsp;</label>
      <button id="btn-reset" onclick="resetFilters()"
        class="text-xs font-semibold px-3 py-1.5 rounded-full border-2 transition hover:bg-gray-50"
        style="border-color:rgba(0,93,143,.2);color:#005d8f;font-family:'Space Grotesk';">↺ Reset</button>
    </div>
    <!-- Right-side actions -->
    <div class="ml-auto flex items-end gap-3">
      <!-- Skill Gap toggle -->
      <div class="flex flex-col gap-1.5">
        <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
          style="font-family:'Space Grotesk'">Analyze</label>
        <button onclick="toggleSkillGap()"
          class="flex items-center gap-1.5 text-xs font-bold px-4 py-1.5 rounded-full border-2"
          style="border-color:rgba(0,93,143,.2);color:#005d8f;font-family:'Space Grotesk';background:#fff;">
          <span class="material-symbols-outlined" style="font-size:14px;">analytics</span> Skill Gap
        </button>
      </div>
      <!-- Export CSV -->
      <div class="flex flex-col gap-1.5">
        <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
          style="font-family:'Space Grotesk'">Export</label>
        <button onclick="exportCSV()"
          class="flex items-center gap-1.5 text-xs font-bold px-4 py-1.5 rounded-full border-2"
          style="border-color:rgba(0,93,143,.2);color:#005d8f;font-family:'Space Grotesk';background:#fff;">
          <span class="material-symbols-outlined" style="font-size:14px;">download</span> CSV
        </button>
      </div>
      <!-- Search -->
      <div class="flex flex-col gap-1.5">
        <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
          style="font-family:'Space Grotesk'">Action</label>
        <button id="loading-btn" onclick="onLoadingClick()">
          <span class="material-symbols-outlined" style="font-size:15px;">refresh</span>
          <span id="loading-btn-text">搜索职缺</span>
        </button>
        <div id="search-log-panel" style="display:none; margin-top:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;
                      font-size:11px;color:#64748b;margin-bottom:4px;">
            <span>Claude Code Output</span>
            <button onclick="document.getElementById('search-log-panel').style.display='none'"
                    style="background:none;border:none;cursor:pointer;font-size:14px;color:#94a3b8;">✕</button>
          </div>
          <pre id="search-log-pre"
               style="background:#0f172a;color:#94a3b8;font-size:11px;font-family:monospace;
                      padding:10px;border-radius:6px;max-height:200px;overflow-y:auto;
                      white-space:pre-wrap;word-break:break-all;margin:0;"></pre>
        </div>
      </div>
    </div>
  </div>

  <!-- Skill Gap Panel (hidden by default) -->
  <div id="skill-gap-wrap" class="bg-white rounded-xl shadow-sm mb-5" style="display:none;">
    <div class="px-5 pt-4 pb-4">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-[#F97316]" style="font-size:18px;">analytics</span>
          <span class="font-bold text-sm text-[#191c1d]" style="font-family:Manrope;">Top Missing Skills</span>
          <span id="skill-gap-subtitle" class="text-xs text-slate-400"></span>
        </div>
        <button onclick="toggleSkillGap()" class="text-xs text-slate-400 hover:text-slate-600"
          style="font-family:'Space Grotesk';">Hide</button>
      </div>
      <div id="skill-gap-bars" class="flex flex-wrap gap-2 pt-1"></div>
    </div>
  </div>

  <!-- Table -->
  <div class="bg-white rounded-xl shadow-sm">
    <!-- Table toolbar: column toggle -->
    <div class="px-4 pt-3 pb-1 flex justify-end">
      <div class="relative" id="col-toggle-wrap">
        <button id="col-toggle-btn" onclick="toggleColPanel()"
          class="text-xs font-semibold px-3 py-1 rounded-full border-2 hover:bg-gray-50 transition"
          style="border-color:rgba(0,93,143,.2);color:#005d8f;font-family:'Space Grotesk';">
          ⚙ Columns
        </button>
        <div id="col-toggle-panel" class="hidden absolute right-0 top-9 bg-white border border-gray-200 rounded-xl shadow-lg z-20 p-3 min-w-[170px] text-xs space-y-1.5"
          style="font-family:'Space Grotesk';">
          <div class="font-bold text-slate-500 pb-1 border-b border-gray-100 mb-1">Toggle Columns</div>
          <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" data-col="group" checked onchange="toggleCol(this)"> Group</label>
          <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" data-col="source" checked onchange="toggleCol(this)"> Source</label>
          <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" data-col="size" checked onchange="toggleCol(this)"> Size</label>
          <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" data-col="location" checked onchange="toggleCol(this)"> Location</label>
          <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" data-col="emphasis" checked onchange="toggleCol(this)"> Emphasis</label>
          <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" data-col="missing" checked onchange="toggleCol(this)"> Missing Skills</label>
          <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" data-col="search_date" checked onchange="toggleCol(this)"> 1st Fetch Date</label>
          <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" data-col="last_seen" checked onchange="toggleCol(this)"> Last Seen</label>
        </div>
      </div>
    </div>
    <div class="table-scroll-wrapper">
      <table class="jobs-table">
        <thead>
          <tr>
            <th>#</th>
            <th class="th-sort" id="th-score" onclick="setSortCol('score')">Score <span class="sort-icon" id="si-score">↓</span></th>
            <th data-col="group">Group</th>
            <th data-col="source">Source</th>
            <th class="th-sort" id="th-company" onclick="setSortCol('company')">Company <span class="sort-icon" id="si-company">⇅</span></th>
            <th class="th-sort" id="th-title" style="min-width:160px" onclick="setSortCol('title')">Title <span class="sort-icon" id="si-title">⇅</span></th>
            <th data-col="size">Size</th>
            <th data-col="location" style="min-width:100px">Location</th>
            <th data-col="emphasis" style="min-width:190px">Recommended Emphasis</th>
            <th data-col="missing" style="min-width:170px">Missing Skills</th>
            <th data-col="search_date" class="th-sort" id="th-analyzed" style="white-space:nowrap" onclick="setSortCol('analyzed')">1st Fetch Date <span class="sort-icon" id="si-analyzed">⇅</span></th>
            <th data-col="last_seen" class="th-sort" id="th-last-seen" style="white-space:nowrap" onclick="setSortCol('last_seen')">Last Seen <span class="sort-icon" id="si-last-seen">⇅</span></th>
            <th>Record</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody id="jobs-tbody"></tbody>
      </table>
    </div>
    <!-- Pagination footer -->
    <div class="px-5 py-3 flex items-center justify-between bg-gray-50 rounded-b-xl border-t border-gray-100">
      <p id="page-info" class="text-xs text-slate-400 font-semibold"
        style="font-family:'Space Grotesk'"></p>
      <div id="pagination" class="flex gap-1.5 items-center"></div>
    </div>
  </div>

</div>
</div><!-- /page-dashboard -->

<!-- ═══ PAGE 2 — JOB DETAIL ═══ -->
<div id="page-detail" class="page" style="padding-top:84px; padding-bottom:100px;">
<div class="px-6 max-w-[1200px] mx-auto">
  <div class="flex items-center gap-3 mb-6">
    <button onclick="showPage('dashboard')"
      class="flex items-center gap-1 text-sm text-slate-500 hover:text-[#005d8f] transition-colors">
      <span class="material-symbols-outlined text-lg">arrow_back</span> Back to list
    </button>
  </div>
  <div id="detail-content"></div>
</div>
</div>

<!-- Detail sticky footer -->
<div id="detail-footer" style="display:none;" class="detail-footer">
  <a id="apply-btn" href="#" target="_blank"
    class="flex-1 flex items-center justify-center gap-2 kinetic-gradient text-white rounded-full px-6 py-3 font-bold text-sm no-underline"
    style="font-family:Manrope;">
    Apply Now <span class="material-symbols-outlined text-sm">arrow_forward</span>
  </a>
  <button onclick="showPage('dashboard'); document.getElementById('detail-footer').style.display='none';"
    class="flex-1 flex items-center justify-center gap-2 text-[#005d8f] border-2 border-[#005d8f]/20
           bg-white rounded-full px-6 py-3 font-bold text-sm"
    style="font-family:Manrope;">
    <span class="material-symbols-outlined text-sm">list</span> Back to List
  </button>
</div>

<!-- ═══ PAGE 4 — MY CVs ═══ -->
<div id="page-cvs" class="page" style="padding-top:84px; padding-bottom:48px;">
<div class="px-6 max-w-[1400px] mx-auto">

  <!-- Title row -->
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-2xl font-black text-[#191c1d]" style="font-family:Manrope;">My CVs</h1>
      <p class="text-sm text-slate-500 mt-1">Manage your CV-to-job-group mappings. Each group uses a dedicated CV tailored for a specific career track.</p>
    </div>
    <button disabled title="Coming soon — Page 3 not yet implemented"
      class="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold opacity-40 cursor-not-allowed"
      style="font-family:'Space Grotesk'; background:linear-gradient(135deg,#005d8f,#0077b5); color:#fff;">
      <span class="material-symbols-outlined" style="font-size:16px;">add</span> Add Group
    </button>
  </div>

  <!-- Summary bar -->
  <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6" id="cvs-stats-row">
    <div class="stat-card" style="border-left:4px solid #005d8f;">
      <div class="stat-label mb-2">Total Groups</div>
      <div class="stat-val" id="cvs-stat-groups">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label mb-2">Assigned CVs</div>
      <div class="stat-val" id="cvs-stat-cvs">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label mb-2">Active Searches</div>
      <div class="stat-val" id="cvs-stat-active">—</div>
      <div class="stat-sub">last 7 days</div>
    </div>
    <div class="stat-card">
      <div class="stat-label mb-2">Last Updated</div>
      <div class="stat-val text-lg" id="cvs-stat-updated">—</div>
    </div>
  </div>

  <!-- Card grid -->
  <div class="grid grid-cols-1 xl:grid-cols-2 gap-4" id="cvs-card-grid">
    <div class="stat-card text-center text-slate-400 text-sm">Loading groups…</div>
  </div>

  <!-- Callout banner -->
  <div class="mt-6 px-6 py-4 rounded-xl text-sm text-[#1D4ED8]" style="background:#EFF6FF;">
    <span class="font-bold">Tip:</span> Each group's CV is automatically selected when generating tailored applications. Keep CVs updated to improve match scores.
  </div>

</div>
</div><!-- /page-cvs -->

<!-- ═══ PAGE — SEARCH ANALYSIS ═══ -->
<div id="page-analysis" class="page" style="padding-top:84px;padding-bottom:48px;">
<div class="px-6 max-w-[1400px] mx-auto">

  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-2xl font-black text-[#191c1d]" style="font-family:Manrope;">Search Analysis</h1>
      <p class="text-sm text-slate-500 mt-1">Per-keyword result counts and average match scores — all-time aggregated across all batches.</p>
    </div>
  </div>

  <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
    <div class="stat-card" style="border-left:4px solid #005d8f;">
      <div class="stat-label mb-2">Total Fetched</div>
      <div class="stat-val" id="an-stat-total">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label mb-2">Groups Searched</div>
      <div class="stat-val" id="an-stat-groups">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label mb-2">Fallback Triggered</div>
      <div class="stat-val" id="an-stat-fallback">—</div>
      <div class="text-[10px] text-slate-400 mt-1" id="an-stat-fallback-sub"></div>
    </div>
    <div class="stat-card">
      <div class="stat-label mb-2">Last Search</div>
      <div class="stat-val text-lg" id="an-stat-date">—</div>
    </div>
  </div>

  <div class="bg-white rounded-xl p-4 mb-5 shadow-sm">
    <div class="flex flex-col gap-1.5">
      <label class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold"
        style="font-family:'Space Grotesk'">Group</label>
      <div class="seg-track" id="analysis-group-tabs"></div>
    </div>
  </div>

  <div class="bg-white rounded-xl shadow-sm p-6" id="analysis-chart-wrap">
    <div class="text-slate-400 text-sm text-center py-8">Loading analysis…</div>
  </div>

</div>
</div><!-- /page-analysis -->

<!-- ═══ SCRIPT ═══ -->
<script>
'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
let JOBS = [];
let filteredJobs = [];
let currentPage = 1;
const ROWS_PER_PAGE = 25;
let activeGroup    = 'all';
let activeSource   = 'all';
let filterRecord   = '';
let activeScoreTier = null;  // 'high' | 'mid' | 'low' | null
let pollingTimer   = null;
let lastMtime      = null;
let sortCol        = 'score';
let sortDir        = 'desc';
let detailJob      = null;
let _filterTimer   = null;
let _skillGapVisible = false;

// ── Skill classification — taxonomy injected from config.json at build time ───
const SKILL_TAXONOMY = __SKILL_TAXONOMY_JSON__;
// Priority: tools → cert → langs → academic → domain → soft
// (cert before academic: avoids "certified engineer" landing in academic;
//  academic before domain: avoids "economics degree" landing in domain)
function classifySkill(s) {
  const sl = s.toLowerCase();
  if ((SKILL_TAXONOMY.tools   ||[]).some(t => sl.includes(t))) return 'tools';
  if ((SKILL_TAXONOMY.cert    ||[]).some(t => sl.includes(t))) return 'cert';
  if ((SKILL_TAXONOMY.langs   ||[]).some(l => sl.includes(l))) return 'langs';
  if ((SKILL_TAXONOMY.academic||[]).some(t => sl.includes(t))) return 'academic';
  if ((SKILL_TAXONOMY.domain  ||[]).some(d => sl.includes(d))) return 'domain';
  return 'soft';
}
function categorizeMissingSkills(skills) {
  const groups = {tools:[], academic:[], domain:[], langs:[], cert:[], soft:[]};
  (skills||[]).forEach(s => { groups[classifySkill(s)].push(s); });
  return groups;
}
// Variant for [{skill, count}] format — groups objects, sorts by count desc within category
function categorizeSkillObjs(skillObjs) {
  const groups = {tools:[], academic:[], domain:[], langs:[], cert:[], soft:[]};
  (skillObjs||[]).forEach(obj => {
    const s = obj.skill || obj;
    groups[classifySkill(s)].push(obj);
  });
  Object.values(groups).forEach(arr => arr.sort((a,b) => (b.count||0)-(a.count||0)));
  return groups;
}
const SKILL_CATS = [
  {key:'tools',    label:'Tools & Technical'},
  {key:'academic', label:'Academic Background'},
  {key:'cert',     label:'Certificates'},
  {key:'langs',    label:'Languages'},
  {key:'domain',   label:'Domain Knowledge'},
  {key:'soft',     label:'Soft & Other'},
];
function renderSkillCategories(skills, icon, iconColor) {
  if (!(skills||[]).length) return '';
  const groups = categorizeMissingSkills(skills);
  const catLabel = t => `<div class="text-[9px] uppercase tracking-wider text-slate-400 font-bold mb-1 mt-2" style="font-family:'Space Grotesk'">${t}</div>`;
  const mkRow = s => `<div class="matched-row"><span class="material-symbols-outlined" style="font-size:16px;color:${iconColor};">${icon}</span><span>${esc(s)}</span></div>`;
  return SKILL_CATS.map(({key, label}) =>
    groups[key].length ? catLabel(label) + groups[key].map(mkRow).join('') : ''
  ).join('');
}
function parseAnalyzedDate(s) {
  if (!s || s === '—') return null;
  // "Apr 17" → assume current year
  const m = s.match(/^([A-Za-z]{3})\s+(\d{1,2})$/);
  if (m) { const d = new Date(`${m[1]} ${m[2]} ${new Date().getFullYear()}`); return isNaN(d) ? null : d; }
  const d = new Date(s);
  return isNaN(d) ? null : d;
}

// ── Score helpers ─────────────────────────────────────────────────────────────
function scoreColor(s) {
  if (s == null) return '#9CA3AF';
  if (s >= 70) return '#22C55E';
  if (s >= 45) return '#EAB308';
  if (s >= 30) return '#F97316';
  return '#EF4444';
}
function scoreBg(s) {
  if (s == null) return '#F3F4F6';
  if (s >= 70) return '#DCFCE7';
  if (s >= 45) return '#FEF9C3';
  if (s >= 30) return '#FFEDD5';
  return '#FEE2E2';
}

function esc(s) {
  return String(s||'')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// ── Load jobs from server ─────────────────────────────────────────────────────
async function loadJobs() {
  try {
    const resp = await fetch('/api/jobs');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    JOBS = await resp.json();
    hideError();
    populateLocationDropdown();
    restoreFilterState();
    buildGroupTabs();
    applyFilters();
    updateStats();
    updateSortUI();
    restoreColVisibility();
  } catch(e) {
    showError('⚠ Cannot reach server. Run: <code>python scripts/server.py</code> &nbsp;(' + e.message + ')');
  }
}

function showError(msg) {
  const el = document.getElementById('error-banner');
  el.innerHTML = msg;
  el.style.display = 'block';
}
function hideError() {
  document.getElementById('error-banner').style.display = 'none';
}

// ── Build dynamic group tabs ───────────────────────────────────────────────────
function buildGroupTabs() {
  // Build group_id → group_label map from JOBS, preserve insertion order then sort by id
  const groupMap = {};
  JOBS.forEach(j => {
    if (j.group && j.group !== '—') groupMap[j.group] = j.group_label || j.group;
  });
  const groupIds = Object.keys(groupMap).sort();
  const el = document.getElementById('group-tabs');
  el.innerHTML = '<button class="seg-btn' + (activeGroup==='all'?' active':'') +
    '" data-group="all">All</button>';
  groupIds.forEach(gid => {
    // Strip "group-" prefix from label for compact display
    const label = (groupMap[gid] || gid).replace(/^group-/i, '');
    const active = activeGroup === gid ? ' active' : '';
    el.innerHTML += `<button class="seg-btn${active}" data-group="${esc(gid)}">${esc(label)}</button>`;
  });
}

// ── Segmented control events ──────────────────────────────────────────────────
document.getElementById('group-tabs').addEventListener('click', e => {
  const btn = e.target.closest('.seg-btn');
  if (!btn) return;
  document.querySelectorAll('#group-tabs .seg-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeGroup = btn.dataset.group;
  applyFilters();
  updateLoadingBtnText();
});

document.getElementById('source-tabs').addEventListener('click', e => {
  const btn = e.target.closest('.seg-btn');
  if (!btn) return;
  document.querySelectorAll('#source-tabs .seg-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeSource = btn.dataset.source;
  applyFilters();
  updateLoadingBtnText();
});

function onSearch() {
  applyFilters();
}
function onRecordFilter() {
  filterRecord = document.getElementById('record-filter').value;
  applyFilters();
}

// ── Filters ───────────────────────────────────────────────────────────────────
function applyFilters() {
  const query    = (document.getElementById('search-input').value || '').toLowerCase();
  const scoreMin = parseInt(document.getElementById('score-min').value);
  const scoreMax = parseInt(document.getElementById('score-max').value);
  const hasScoreMin = !isNaN(scoreMin);
  const hasScoreMax = !isNaN(scoreMax);

  const dateFromVal = document.getElementById('date-from').value;
  const dateToVal   = document.getElementById('date-to').value;
  const dateFrom = dateFromVal ? new Date(dateFromVal) : null;
  const dateTo   = dateToVal   ? new Date(dateToVal + 'T23:59:59') : null;

  const locVal = document.getElementById('location-filter').value;

  filteredJobs = JOBS.filter(j => {
    if (activeGroup !== 'all' && j.group !== activeGroup) return false;
    if (activeSource !== 'all') {
      if (!(j.source||'').toLowerCase().includes(activeSource.toLowerCase())) return false;
    }
    if (hasScoreMin && j.score !== null && j.score < scoreMin) return false;
    if (hasScoreMax && j.score !== null && j.score > scoreMax) return false;
    if (query) {
      const hay = ((j.company||'')+' '+(j.title||'')+' '+(j.group_label||j.group||'')+' '+(j.source||'')).toLowerCase();
      if (!hay.includes(query)) return false;
    }
    if (dateFrom || dateTo) {
      if (!j.analyzed || j.analyzed === '—') return false;
      const d = parseAnalyzedDate(j.analyzed);
      if (!d || (dateFrom && d < dateFrom) || (dateTo && d > dateTo)) return false;
    }
    if (filterRecord === '__none__') {
      if (j.application_record) return false;
    } else if (filterRecord) {
      const normAr = (j.application_record === 'success') ? 'applied' : j.application_record;
      if (normAr !== filterRecord) return false;
    }
    if (locVal && (j.inferred_location || '') !== locVal) return false;
    return true;
  });

  filteredJobs = sortJobs(filteredJobs);
  currentPage = 1;
  renderTable();
  document.getElementById('result-count').textContent = filteredJobs.length + ' results';
  updateSkillGap();
  updateStats();
  saveFilterState();
}

// ── Stats row (dynamic: reflects current filteredJobs) ────────────────────────
function updateStats() {
  const TRACKING = new Set(['applied','interview','success']);
  const src = filteredJobs;
  const tier = (minS, maxS) => {
    const all      = src.filter(j => j.score != null && j.score >= minS && (maxS == null || j.score < maxS));
    const tracking = all.filter(j => TRACKING.has(j.application_record)).length;
    return { total: all.length, tracking };
  };
  const g = tier(70, null), y = tier(45, 70), o = tier(30, 45);
  const total = src.filter(j => j.score != null && j.score >= 30).length;

  document.getElementById('stat-total').textContent  = total;
  document.getElementById('stat-green').textContent  = g.total;
  document.getElementById('stat-yellow').textContent = y.total;
  document.getElementById('stat-orange').textContent = o.total;
  document.getElementById('stat-green-sub').textContent  = g.tracking + ' applied';
  document.getElementById('stat-yellow-sub').textContent = y.tracking + ' applied';
  document.getElementById('stat-orange-sub').textContent = o.tracking + ' applied';
  updateStatCardHighlight();
}

// ── Loading button ────────────────────────────────────────────────────────────
function getCommand() {
  // Returns {display, clipboard}
  // display: uses group_label for human readability
  // clipboard: uses group_id for CLI command
  const g = activeGroup, s = activeSource;
  const groupLabel = (() => {
    if (g === 'all') return null;
    const btn = document.querySelector(`#group-tabs .seg-btn[data-group="${g}"]`);
    return btn ? btn.textContent.trim() : g;
  })();
  if (g === 'all') {
    if (s === 'all')       return {display: '搜索职缺',            clipboard: '搜索职缺'};
    if (s === 'LinkedIn')  return {display: '搜索LinkedIn职缺',    clipboard: '搜索LinkedIn职缺'};
    if (s === 'Stepstone') return {display: '搜索Stepstone职缺',   clipboard: '搜索Stepstone职缺'};
  } else {
    if (s === 'all')       return {display: '搜索职缺 ' + groupLabel,          clipboard: '搜索职缺 ' + g};
    if (s === 'LinkedIn')  return {display: '搜索LinkedIn职缺 ' + groupLabel,  clipboard: '搜索LinkedIn职缺 ' + g};
    if (s === 'Stepstone') return {display: '搜索Stepstone职缺 ' + groupLabel, clipboard: '搜索Stepstone职缺 ' + g};
  }
  return {display: '搜索职缺', clipboard: '搜索职缺'};
}

function updateLoadingBtnText() {
  document.getElementById('loading-btn-text').textContent = getCommand().display;
}

async function startPolling() {
  if (pollingTimer) clearInterval(pollingTimer);
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    lastMtime = d.mtime;
  } catch(e) { lastMtime = null; }
  let ticks = 0;
  pollingTimer = setInterval(async () => {
    try {
      const r = await fetch('/api/status');
      const d = await r.json();
      if (lastMtime !== null && d.mtime !== lastMtime) {
        clearInterval(pollingTimer); pollingTimer = null;
        await loadJobs(); resetLoadingBtn();
        return;
      }
    } catch(e) {}
    if (++ticks >= 150) { clearInterval(pollingTimer); pollingTimer = null; resetLoadingBtn(); }
  }, 2000);
}

async function onLoadingClick() {
  const {clipboard: cmd} = getCommand();
  const btn  = document.getElementById('loading-btn');
  const span = document.getElementById('loading-btn-text');
  const gid  = filterGroup || 'all';

  // Immediately show feedback so user knows the click registered
  btn.disabled = true;
  span.textContent = '⏳ 连接中…';

  let started = false;
  try {
    const resp = await fetch('/api/search', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({group_id: gid})
    });
    if (resp.ok) {
      started = true;
      console.log('[search] API started:', gid);
    } else if (resp.status === 409) {
      btn.disabled = false;
      span.textContent = getCommand().display;
      alert('A search is already running.');
      return;
    } else {
      console.warn('[search] API returned', resp.status, '— falling back to clipboard');
    }
  } catch(e) {
    console.warn('[search] Server unreachable — falling back to clipboard:', e.message);
  }

  if (!started) {
    try { await navigator.clipboard.writeText(cmd); }
    catch(e) { prompt('Copy this command and paste it into Claude Code:', cmd); }
    span.textContent = '⏳ Loading…';
    await startPolling();
    return;
  }

  span.textContent = '⏳ Running…';
  openSearchLog();
  subscribeSearchLog();
}

function openSearchLog() {
  const panel = document.getElementById('search-log-panel');
  const pre   = document.getElementById('search-log-pre');
  if (panel) panel.style.display = 'block';
  if (pre)   pre.textContent = '';
}

function subscribeSearchLog() {
  const pre = document.getElementById('search-log-pre');
  const es  = new EventSource('/api/search-log');
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.done) {
      es.close();
      resetLoadingBtn();
      setTimeout(() => loadJobs(), 2000);
      return;
    }
    if (pre && d.text) {
      pre.textContent += d.text + '\n';
      pre.scrollTop = pre.scrollHeight;
    }
  };
  es.onerror = () => { es.close(); resetLoadingBtn(); };
}

function resetLoadingBtn() {
  const btn = document.getElementById('loading-btn');
  btn.disabled = false;
  document.getElementById('loading-btn-text').textContent = getCommand().display;
}

// ── Render table ──────────────────────────────────────────────────────────────
function renderTable() {
  const tbody  = document.getElementById('jobs-tbody');
  const total  = filteredJobs.length;
  const pages  = Math.ceil(total / ROWS_PER_PAGE) || 1;
  if (currentPage > pages) currentPage = pages;

  const start = (currentPage - 1) * ROWS_PER_PAGE;
  const slice = filteredJobs.slice(start, start + ROWS_PER_PAGE);
  tbody._slice = slice;   // stored for event delegation

  document.getElementById('page-info').textContent =
    `Showing ${start+1}–${Math.min(start+ROWS_PER_PAGE, total)} of ${total} jobs`;

  if (!slice.length) {
    tbody.innerHTML = `<tr><td colspan="14" class="text-center py-12">
      <div class="text-slate-400">
        <span class="material-symbols-outlined text-4xl block mb-2">search_off</span>
        <p class="font-semibold mb-1 text-sm">No jobs match your filters</p>
        <p class="text-xs mb-4">Try lowering the score threshold or clearing the search</p>
        <button onclick="resetFilters()"
          class="text-xs font-bold px-4 py-2 rounded-full kinetic-gradient text-white"
          style="font-family:'Space Grotesk'">Reset Filters</button>
      </div></td></tr>`;
    renderPagination(1);
    return;
  }

  tbody.innerHTML = slice.map((j, idx) => {
    const sc  = scoreColor(j.score);
    const sbg = scoreBg(j.score);
    const sd  = j.score != null ? Math.round(j.score) : '—';

    const grpLabel = (j.group_label || j.group || '').replace(/^group-/i, '');
    const grp = j.group && j.group !== '—'
      ? `<span class="group-tag">${esc(grpLabel)}</span>`
      : '<span class="text-slate-300 text-xs">—</span>';

    const srcCls  = (j.source||'').toLowerCase().includes('linkedin') ? 'src-li' : 'src-ss';
    const srcIcon = (j.source||'').toLowerCase().includes('linkedin') ? '🔗' : '📄';


    // Application record select (5-state)
    const ar = j.application_record;
    const displayState = (ar === 'success') ? 'applied' : (ar || '');
    const recHtml = j.jd_path
      ? `<div onclick="event.stopPropagation()">
           <select class="rec-select" data-state="${esc(displayState)}"
             onchange="setRecord(${idx}, this.value)">
             <option value=""${!ar?'selected':''}>— Track</option>
             <option value="applied"${(ar==='applied'||ar==='success')?'selected':''}>Applied</option>
             <option value="interview"${ar==='interview'?'selected':''}>Interview</option>
             <option value="invalid"${ar==='invalid'?'selected':''}>Invalid</option>
               </select>
         </div>`
      : '';

    // Remark
    const remarkHtml = j.remark
      ? `<span class="remark-badge">${esc(j.remark)}</span>` : '';

    // Materials badge
    const matBadge = j.materials_ready
      ? `<span class="mat-badge" title="CV + CL generated">📄 Ready</span><br>` : '';

    // Notes cell: icon + first 20 chars when has note
    const noteCell = j.user_note
      ? `<div class="flex flex-col items-center gap-0.5">
           <span class="material-symbols-outlined note-icon has-note"
             title="${esc(j.user_note.slice(0,80))}" style="font-size:16px;">edit_note</span>
           <span class="text-[10px] text-amber-600 font-mono max-w-[72px] truncate leading-tight">${esc(j.user_note.slice(0,20))}</span>
         </div>`
      : `<span class="material-symbols-outlined note-icon" title="No notes" style="font-size:16px;">edit_note</span>`;

    return `<tr data-row-idx="${idx}" class="job-row">
      <td class="text-slate-400 text-xs font-mono">${String(start+idx+1).padStart(3,'0')}</td>
      <td><span class="score-badge" style="color:${sc};background:${sbg};"
        title="View detail">${sd}</span></td>
      <td data-col="group">${grp}</td>
      <td data-col="source">${j.url
        ? `<a href="${esc(j.url)}" target="_blank" onclick="event.stopPropagation()"
             class="${srcCls}" style="text-decoration:none;" title="${esc(j.url)}">${srcIcon} ${esc(j.source||'—')}</a>`
        : `<span class="${srcCls}">${srcIcon} ${esc(j.source||'—')}</span>`}</td>
      <td class="font-bold text-sm max-w-[140px]">
        <span class="block truncate" title="${esc(j.company)}">${esc(j.company)}</span></td>
      <td style="max-width:170px;">
        ${matBadge}<span class="block text-sm text-slate-600 line-clamp-3"
          title="${esc(j.title)}">${esc(j.title)}</span></td>
      <td data-col="size" class="text-center text-xs text-slate-400 whitespace-nowrap">${esc(j.size||'—')}</td>
      <td data-col="location" class="text-xs text-slate-500 whitespace-nowrap">${esc(j.inferred_location||j.location||'—')}</td>
      <td data-col="emphasis" style="max-width:200px;">
        <span class="block text-xs text-slate-500 line-clamp-3"
          title="${esc(j.recommended_emphasis_raw)}">${esc(j.recommended_emphasis_raw)}</span></td>
      <td data-col="missing" style="max-width:180px;">${(() => {
        const skills = (j.missing_skills&&j.missing_skills.length)
          ? j.missing_skills
          : (j.missing_skills_raw ? j.missing_skills_raw.split(/[;,]/).map(s=>s.trim()).filter(Boolean) : []);
        if (!skills.length) return '<span class="text-slate-300 text-xs">—</span>';
        const {tools, academic, domain, langs, cert, soft} = categorizeMissingSkills(skills);
        const catLbl = t => `<div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#9CA3AF;font-family:'Space Grotesk',sans-serif;line-height:1.8;">${t}</div>`;
        const mkPills = arr => `<div style="display:flex;flex-wrap:wrap;gap:2px;">${arr.map(s=>`<span class="miss-tag">${esc(s)}</span>`).join('')}</div>`;
        const parts = [];
        if (tools.length)    parts.push(catLbl('Tools') + mkPills(tools));
        if (academic.length) parts.push(catLbl('Academic') + mkPills(academic));
        if (cert.length)     parts.push(catLbl('Certs') + mkPills(cert));
        if (langs.length)    parts.push(catLbl('Languages') + mkPills(langs));
        if (domain.length)   parts.push(catLbl('Domain') + mkPills(domain));
        if (soft.length)     parts.push(catLbl('Other') + mkPills(soft));
        return `<div title="${esc(skills.join(', '))}">${parts.join('')}</div>`;
      })()}</td>
      <td data-col="search_date" class="text-xs text-slate-400 whitespace-nowrap font-mono">${esc(j.analyzed)}</td>
      <td data-col="last_seen" class="text-xs text-slate-400 whitespace-nowrap font-mono">${esc(j.last_seen||'—')}</td>
      <td>${recHtml}</td>
      <td class="text-center">${noteCell}</td>
    </tr>`;
  }).join('');

  renderPagination(pages);
}

// ── Application record (5-state select) ──────────────────────────────────────
async function setRecord(idx, val) {
  const tbody = document.getElementById('jobs-tbody');
  const job   = tbody._slice[idx];
  if (!job || !job.jd_path) return;

  const newVal = val || null;
  try {
    const r = await fetch('/api/record', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({jd_path: job.jd_path, record: newVal})
    });
    const d = await r.json();
    if (d.ok) {
      job.application_record = newVal;
      const orig = JOBS.find(j => j.jd_path === job.jd_path);
      if (orig) orig.application_record = newVal;
      updateStats();
      const row = tbody.querySelector(`tr[data-row-idx="${idx}"]`);
      if (row) {
        const sel = row.querySelector('.rec-select');
        if (sel) sel.dataset.state = (newVal === 'success' ? 'applied' : newVal) || '';
      }
    }
  } catch(e) { showToast('Save failed: ' + e.message); }
}

// ── Row click → Page 2 (event delegation) ────────────────────────────────────
document.getElementById('jobs-tbody').addEventListener('click', e => {
  if (e.target.closest('a[href]') || e.target.closest('.rec-wrap')) return;
  const row = e.target.closest('tr.job-row');
  if (!row) return;
  const tbody = document.getElementById('jobs-tbody');
  const job   = tbody._slice[parseInt(row.dataset.rowIdx, 10)];
  if (job) showDetail(job);
});

// ── Pagination ─────────────────────────────────────────────────────────────────
function renderPagination(totalPages) {
  const el = document.getElementById('pagination');
  if (totalPages <= 1) { el.innerHTML = ''; return; }

  const win = 5;
  let s = Math.max(1, currentPage - Math.floor(win/2));
  let e = Math.min(totalPages, s + win - 1);
  if (e - s < win - 1) s = Math.max(1, e - win + 1);

  let html = `<button class="page-btn" onclick="goPage(${currentPage-1})"
    ${currentPage===1?'disabled':''}>
    <span class="material-symbols-outlined" style="font-size:16px;">chevron_left</span></button>`;
  if (s > 1) html += `<button class="page-btn" onclick="goPage(1)">1</button>`;
  if (s > 2) html += `<span class="text-slate-300 text-sm px-1">…</span>`;
  for (let p = s; p <= e; p++)
    html += `<button class="page-btn${p===currentPage?' current':''}" onclick="goPage(${p})">${p}</button>`;
  if (e < totalPages-1) html += `<span class="text-slate-300 text-sm px-1">…</span>`;
  if (e < totalPages) html += `<button class="page-btn" onclick="goPage(${totalPages})">${totalPages}</button>`;
  html += `<button class="page-btn" onclick="goPage(${currentPage+1})"
    ${currentPage===totalPages?'disabled':''}>
    <span class="material-symbols-outlined" style="font-size:16px;">chevron_right</span></button>`;

  el.innerHTML = html;
}
function goPage(p) {
  const pages = Math.ceil(filteredJobs.length / ROWS_PER_PAGE) || 1;
  if (p < 1 || p > pages) return;
  currentPage = p;
  renderTable();
  window.scrollTo({top:0, behavior:'smooth'});
}

// ── Page navigation ───────────────────────────────────────────────────────────
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (name === 'dashboard') {
    document.getElementById('detail-footer').style.display = 'none';
  }
  // Update nav active state
  document.querySelectorAll('nav a[id^="nav-"]').forEach(a => {
    a.className = 'text-slate-500 font-medium text-sm px-3 py-1 rounded-full hover:bg-gray-100';
  });
  const activeNav = document.getElementById('nav-' + name);
  if (activeNav) activeNav.className = 'text-[#0077B5] border-b-2 border-[#0077B5] pb-0.5 font-bold text-sm';
}

function navTo(name) {
  showPage(name);
  if (name === 'cvs') loadGroupStats();
  if (name === 'analysis') loadSearchAnalysis();
}

// ── Page 2 — Job Detail ───────────────────────────────────────────────────────
function showDetail(job) {
  const sc  = scoreColor(job.score);
  const sd  = job.score != null ? Math.round(job.score) : '—';
  const sbg = scoreBg(job.score);

  // Score label
  const slabel = job.score >= 70 ? 'Excellent Alignment'
    : job.score >= 45 ? 'Good Alignment'
    : job.score >= 30 ? 'Moderate Fit' : 'Low Fit';

  // Source/size badges
  const srcBg  = (job.source||'').toLowerCase().includes('linkedin') ? '#E0F0FB' : '#FFEDD5';
  const srcTxt = (job.source||'').toLowerCase().includes('linkedin') ? '#0077B5' : '#C2410C';
  const srcBadge = job.source
    ? `<span class="text-xs px-2 py-1 rounded-full font-semibold"
        style="background:${srcBg};color:${srcTxt};">${esc(job.source)}</span>` : '';
  const szBadge = job.size
    ? `<span class="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-500 font-mono">${esc(job.size)}</span>` : '';

  // Core responsibilities
  const coreHtml = (job.core_responsibilities||[]).map((r,i) =>
    `<li class="flex gap-3 items-start">
      <span class="font-bold text-[#005d8f] font-mono text-sm flex-shrink-0"
        style="font-family:'Space Grotesk'">${String(i+1).padStart(2,'0')}</span>
      <p class="text-sm leading-relaxed text-slate-600">${esc(r)}</p></li>`).join('');

  // Culture keywords
  const cultHtml = (job.culture_keywords||[]).map(k =>
    `<span class="bg-blue-50 text-blue-700 border border-blue-100 px-3 py-1.5 rounded-full text-xs font-semibold">${esc(k)}</span>`
  ).join('');

  // Matched / Missing skills
  const matchHtml = renderSkillCategories(job.matched_skills, 'check_circle', '#22C55E');
  const missHtml  = renderSkillCategories(job.missing_skills, 'cancel',       '#EF4444');

  // Bonus skills
  const bonusHtml = (job.bonus_skills||[]).map(s =>
    `<span class="border-2 border-dashed border-orange-300 text-orange-700 bg-orange-50
      px-3 py-1.5 rounded-full text-xs font-semibold">${esc(s)}</span>`).join('');

  // Recommended emphasis
  const emphArr = Array.isArray(job.recommended_emphasis) ? job.recommended_emphasis
    : (job.recommended_emphasis_raw||'').split(';').map(s=>s.trim()).filter(Boolean);
  const emphHtml = emphArr.map((e,i) =>
    `<div class="emphasis-item">
      <div class="emphasis-num">${i+1}</div>
      <p class="text-sm text-orange-900 leading-relaxed">${esc(e)}</p></div>`).join('');

  // Required skills
  const reqHtml = (job.required_skills||[]).map(r =>
    `<li class="flex items-center gap-2 text-xs text-slate-500">
      <div class="w-1.5 h-1.5 rounded-full bg-slate-400 flex-shrink-0"></div>${esc(r)}</li>`).join('');

  // Gauge ring offset (circumference 503)
  const offset = job.score != null ? (503 * (1 - job.score/100)).toFixed(1) : 503;

  document.getElementById('detail-content').innerHTML = `
    <!-- Title card -->
    <div class="detail-card mb-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 class="text-2xl font-black text-[#191c1d] mb-2" style="font-family:Manrope;">${esc(job.title)}</h1>
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-semibold text-slate-700">${esc(job.company)}</span>
            ${szBadge} ${srcBadge}
          </div>
        </div>
        <span class="score-badge text-base px-5 py-2" style="color:${sc};background:${sbg};font-size:16px;">${sd}</span>
      </div>
    </div>

    <!-- Score gauge -->
    <div class="flex justify-center mb-6">
      <div class="detail-card flex flex-col items-center text-center max-w-xs w-full">
        <div class="relative flex items-center justify-center" style="width:160px;height:160px;">
          <svg width="160" height="160" viewBox="0 0 200 200">
            <circle cx="100" cy="100" r="80" fill="none" stroke="#e7e8e9" stroke-width="18"/>
            <circle cx="100" cy="100" r="80" fill="none" stroke="${sc}" stroke-width="18"
              stroke-linecap="round"
              style="stroke-dasharray:503;stroke-dashoffset:${offset};
                     transform:rotate(-90deg);transform-origin:50% 50%;
                     transition:stroke-dashoffset .6s ease;"/>
          </svg>
          <div class="absolute flex flex-col items-center">
            <span class="font-extrabold" style="font-family:Manrope;font-size:44px;color:${sc};line-height:1;">${sd}</span>
            <span class="text-[9px] tracking-widest text-slate-400 font-mono mt-1">MATCH SCORE</span>
          </div>
        </div>
        <p class="mt-3 text-sm font-semibold text-slate-600">${slabel}</p>
      </div>
    </div>

    <!-- 3-col grid: 40% / 35% / 25% -->
    <div class="gap-5" style="display:grid; grid-template-columns: 2fr 1.75fr 1.25fr;">

      <!-- Left: Core Responsibilities + Culture -->
      <div class="flex flex-col gap-5">
        ${coreHtml ? `<div class="detail-card">
          <div class="flex items-center gap-2 mb-4">
            <span class="material-symbols-outlined text-[#005d8f]">assignment</span>
            <h3 class="font-bold text-base" style="font-family:Manrope;">Core Responsibilities</h3>
          </div>
          <ol class="space-y-4">${coreHtml}</ol></div>` : ''}
        ${cultHtml ? `<div class="detail-card">
          <div class="flex items-center gap-2 mb-4">
            <span class="material-symbols-outlined text-[#005d8f]">diversity_3</span>
            <h3 class="font-bold text-base" style="font-family:Manrope;">Culture Keywords</h3>
          </div>
          <div class="flex flex-wrap gap-2">${cultHtml}</div></div>` : ''}
      </div>

      <!-- Center: Skills + Bonus -->
      <div class="flex flex-col gap-5">
        <div class="detail-card">
          <div class="flex items-center gap-2 mb-4">
            <span class="material-symbols-outlined text-[#005d8f]">psychology</span>
            <h3 class="font-bold text-base" style="font-family:Manrope;">Skills Analysis</h3>
          </div>
          ${matchHtml ? `<div class="mb-4">
            <div class="flex justify-between mb-2 pb-1 border-b border-gray-100">
              <span class="text-xs font-bold uppercase tracking-wider text-[#22C55E]">Matched ✓</span>
              <span class="text-xs text-slate-400">${(job.matched_skills||[]).length} found</span>
            </div>${matchHtml}</div>` : ''}
          ${missHtml ? `<div>
            <div class="flex justify-between mb-2 pb-1 border-b border-gray-100">
              <span class="text-xs font-bold uppercase tracking-wider text-[#EF4444]">Missing ✗</span>
              <span class="text-xs text-slate-400">${(job.missing_skills||[]).length} gaps</span>
            </div>${missHtml}</div>` : ''}
        </div>
        ${bonusHtml ? `<div class="detail-card">
          <div class="flex items-center gap-2 mb-4">
            <span class="material-symbols-outlined text-orange-500">auto_awesome</span>
            <h3 class="font-bold text-base" style="font-family:Manrope;">Bonus Skills</h3>
          </div>
          <div class="flex flex-wrap gap-2">${bonusHtml}</div></div>` : ''}
      </div>

      <!-- Right: Emphasis + Required -->
      <div class="flex flex-col gap-5">
        ${emphHtml ? `<div class="detail-card" style="background:#FFF7ED;border:1px solid #fed7aa;">
          <div class="flex items-center gap-2 mb-4">
            <span class="material-symbols-outlined text-orange-600">tips_and_updates</span>
            <h3 class="font-bold text-base text-orange-950" style="font-family:Manrope;">Recommended Emphasis</h3>
          </div>${emphHtml}</div>` : ''}
        ${reqHtml ? `<div class="detail-card">
          <div class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
            Baseline Requirements</div>
          <ul class="space-y-2">${reqHtml}</ul></div>` : ''}
      </div>
    </div><!-- /grid -->
  `;

  // Notes section
  const notesSection = job.jd_path ? `
    <div class="detail-card mt-5">
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined text-[#F59E0B]">edit_note</span>
        <h3 class="font-bold text-base" style="font-family:Manrope;">Notes</h3>
        <span class="text-xs text-slate-400 ml-auto">Auto-saved on blur</span>
      </div>
      <textarea class="note-textarea" id="detail-note"
        placeholder="Interview feedback, contact info, salary range…"
        onblur="saveNote()">${esc(job.user_note||'')}</textarea>
    </div>` : '';

  document.getElementById('detail-content').innerHTML += notesSection;

  detailJob = job;
  document.getElementById('apply-btn').href = job.url || '#';
  document.getElementById('detail-footer').style.display = 'flex';
  showPage('detail');
  window.scrollTo({top:0, behavior:'smooth'});
}

// ── Debounce for score slider ─────────────────────────────────────────────────
function debounceFilters() {
  clearTimeout(_filterTimer);
  _filterTimer = setTimeout(applyFilters, 150);
}

// ── Filter persistence (localStorage) ────────────────────────────────────────
function saveFilterState() {
  try {
    localStorage.setItem('jt_filter', JSON.stringify({
      activeGroup, activeSource, filterRecord,
      scoreMin: document.getElementById('score-min').value,
      scoreMax: document.getElementById('score-max').value,
      dateFrom: document.getElementById('date-from').value,
      dateTo:   document.getElementById('date-to').value,
      location: document.getElementById('location-filter').value,
      searchQuery: document.getElementById('search-input').value
    }));
  } catch(e) {}
}

function restoreFilterState() {
  try {
    const s = JSON.parse(localStorage.getItem('jt_filter') || 'null');
    if (!s) return;
    activeGroup  = s.activeGroup  || 'all';
    activeSource = s.activeSource || 'all';
    filterRecord = s.filterRecord || '';
    document.getElementById('score-min').value = s.scoreMin || '';
    document.getElementById('score-max').value = s.scoreMax || '';
    document.getElementById('date-from').value = s.dateFrom || '';
    document.getElementById('date-to').value   = s.dateTo   || '';
    document.getElementById('search-input').value = s.searchQuery || '';
    const lf = document.getElementById('location-filter');
    if (lf && s.location) lf.value = s.location;
    document.querySelectorAll('#source-tabs .seg-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.source === activeSource));
    const rf = document.getElementById('record-filter');
    if (rf) rf.value = filterRecord;
    toggleSearchClear();
  } catch(e) {}
}

function resetFilters() {
  activeGroup = 'all'; activeSource = 'all'; filterRecord = ''; activeScoreTier = null;
  document.getElementById('score-min').value = '';
  document.getElementById('score-max').value = '';
  document.getElementById('date-from').value = '';
  document.getElementById('date-to').value   = '';
  document.getElementById('search-input').value = '';
  const lf = document.getElementById('location-filter');
  if (lf) lf.value = '';
  const rf = document.getElementById('record-filter');
  if (rf) rf.value = '';
  document.querySelectorAll('#source-tabs .seg-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.source === 'all'));
  document.querySelectorAll('#group-tabs .seg-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.group === 'all'));
  toggleSearchClear();
  applyFilters();
}

// ── Column sorting ────────────────────────────────────────────────────────────
function sortJobs(jobs) {
  return [...jobs].sort((a, b) => {
    let va, vb;
    if (sortCol === 'score') {
      va = a.score ?? -1; vb = b.score ?? -1;
    } else if (sortCol === 'company') {
      va = (a.company||'').toLowerCase(); vb = (b.company||'').toLowerCase();
    } else if (sortCol === 'title') {
      va = (a.title||'').toLowerCase(); vb = (b.title||'').toLowerCase();
    } else if (sortCol === 'analyzed') {
      va = parseAnalyzedDate(a.analyzed||'')?.getTime() ?? 0;
      vb = parseAnalyzedDate(b.analyzed||'')?.getTime() ?? 0;
      return sortDir === 'asc' ? va - vb : vb - va;
    } else if (sortCol === 'last_seen') {
      va = parseAnalyzedDate(a.last_seen||'')?.getTime() ?? 0;
      vb = parseAnalyzedDate(b.last_seen||'')?.getTime() ?? 0;
      return sortDir === 'asc' ? va - vb : vb - va;
    } else { return 0; }
    if (va < vb) return sortDir === 'asc' ? -1 : 1;
    if (va > vb) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });
}

function setSortCol(col) {
  if (sortCol === col) {
    sortDir = sortDir === 'desc' ? 'asc' : 'desc';
  } else {
    sortCol = col;
    sortDir = col === 'score' ? 'desc' : 'asc';
  }
  filteredJobs = sortJobs(filteredJobs);
  updateSortUI();
  currentPage = 1;
  renderTable();
}

function updateSortUI() {
  ['score','company','title','analyzed'].forEach(col => {
    const th = document.getElementById('th-' + col);
    const si = document.getElementById('si-' + col);
    if (!th || !si) return;
    if (col === sortCol) {
      th.classList.add('sort-active');
      si.textContent = sortDir === 'desc' ? '↓' : '↑';
    } else {
      th.classList.remove('sort-active');
      si.textContent = '⇅';
    }
  });
}

// ── Skill gap panel ───────────────────────────────────────────────────────────
function toggleSkillGap() {
  _skillGapVisible = !_skillGapVisible;
  document.getElementById('skill-gap-wrap').style.display = _skillGapVisible ? 'block' : 'none';
  if (_skillGapVisible) updateSkillGap();
}

function updateSkillGap() {
  if (!_skillGapVisible) return;
  const freq = {};
  filteredJobs.forEach(j => (j.missing_skills||[]).forEach(s => {
    const k = s.trim().toLowerCase();
    if (!k) return;
    if (!freq[k]) freq[k] = {label: s, count: 0, cat: classifySkill(s)};
    freq[k].count++;
  }));
  const all = Object.values(freq).sort((a,b)=>b.count-a.count).slice(0,20);
  const maxCount = all[0]?.count || 1;
  document.getElementById('skill-gap-subtitle').textContent =
    `— ${filteredJobs.length} jobs · ${Object.keys(freq).length} unique gaps`;
  const filtered = all.filter(x => x.count > 1);
  let html = '';
  SKILL_CATS.forEach(({key, label}) => {
    const items = filtered.filter(x => x.cat === key);
    if (!items.length) return;
    html += `<div class="w-full">
      <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#9CA3AF;font-family:'Space Grotesk',sans-serif;margin-bottom:6px;margin-top:4px;">${label}</div>
      <div class="flex flex-wrap gap-2">`;
    items.forEach(({label: lbl, count}) => {
      const sz = Math.round(11 + (count / maxCount) * 14);
      const pad = Math.round(1 + (count / maxCount) * 3);
      html += `<span class="miss-tag" title="${count} jobs" style="font-size:${sz}px;padding:${pad}px ${pad+6}px;line-height:1.4;">${esc(lbl)}<sup style="position:absolute;top:-5px;right:-5px;font-size:9px;background:#6B7280;color:#fff;border-radius:999px;padding:0 3px;line-height:14px;min-width:14px;text-align:center;">${count}</sup></span>`;
    });
    html += `</div></div>`;
  });
  document.getElementById('skill-gap-bars').innerHTML = html || '<span class="text-slate-400 text-xs">No missing skills data</span>';
}

// ── Export CSV ────────────────────────────────────────────────────────────────
function exportCSV() {
  const fields = ['company','title','score','source','group','inferred_location','url','analyzed','application_record'];
  const rows = filteredJobs.map(j =>
    fields.map(f => '"' + String(j[f] ?? '').replace(/"/g, '""') + '"').join(',')
  );
  const csv = [fields.join(','), ...rows].join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], {type:'text/csv;charset=utf-8;'}));
  a.download = 'jobs_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
}

// ── Score card click — set tier filter ────────────────────────────────────────
function setScoreTier(tier) {
  if (activeScoreTier === tier) {
    // Toggle off: clear score inputs
    activeScoreTier = null;
    document.getElementById('score-min').value = '';
    document.getElementById('score-max').value = '';
  } else {
    activeScoreTier = tier;
    const ranges = { high: [70, 100], mid: [45, 69], low: [30, 44], all: ['', ''] };
    const [lo, hi] = ranges[tier] || ['', ''];
    document.getElementById('score-min').value = lo;
    document.getElementById('score-max').value = hi;
  }
  applyFilters();
}

function updateStatCardHighlight() {
  const map = { all: 'card-total', high: 'card-high', mid: 'card-mid', low: 'card-low' };
  Object.entries(map).forEach(([tier, id]) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (tier === activeScoreTier) {
      el.style.outline = '2px solid #005d8f';
      el.style.outlineOffset = '-2px';
    } else {
      el.style.outline = '';
    }
  });
}

function onScoreInput() {
  // If user manually edits score inputs, clear the active tier highlight
  activeScoreTier = null;
}

// ── Search clear button ───────────────────────────────────────────────────────
function toggleSearchClear() {
  const val = document.getElementById('search-input').value;
  document.getElementById('search-clear').style.display = val ? 'block' : 'none';
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  toggleSearchClear();
  applyFilters();
}

// ── Location dropdown population ──────────────────────────────────────────────
function populateLocationDropdown() {
  const sel = document.getElementById('location-filter');
  if (!sel) return;
  const locs = [...new Set(JOBS.map(j => j.inferred_location).filter(Boolean))].sort();
  // Clear all except "All Locations" (first option)
  while (sel.options.length > 1) sel.remove(1);
  locs.forEach(l => sel.add(new Option(l, l)));
}

// ── Column visibility toggle ──────────────────────────────────────────────────
function toggleColPanel() {
  const panel = document.getElementById('col-toggle-panel');
  panel.classList.toggle('hidden');
  // Close on outside click
  if (!panel.classList.contains('hidden')) {
    setTimeout(() => {
      document.addEventListener('click', closeColPanel, {once: true, capture: true});
    }, 0);
  }
}

function closeColPanel(e) {
  const wrap = document.getElementById('col-toggle-wrap');
  if (wrap && wrap.contains(e.target)) return;
  const panel = document.getElementById('col-toggle-panel');
  if (panel) panel.classList.add('hidden');
}

function toggleCol(cb) {
  const col = cb.dataset.col;
  const show = cb.checked;
  // Toggle header
  document.querySelectorAll(`th[data-col="${col}"]`).forEach(el => {
    el.style.display = show ? '' : 'none';
  });
  // Toggle all body cells — use a live render approach via re-render or direct DOM
  document.querySelectorAll(`td[data-col="${col}"]`).forEach(el => {
    el.style.display = show ? '' : 'none';
  });
  // Persist to localStorage
  try {
    const vis = JSON.parse(localStorage.getItem('jt_col_vis') || '{}');
    vis[col] = show;
    localStorage.setItem('jt_col_vis', JSON.stringify(vis));
  } catch(e) {}
}

function restoreColVisibility() {
  try {
    const vis = JSON.parse(localStorage.getItem('jt_col_vis') || '{}');
    document.querySelectorAll('#col-toggle-panel input[data-col]').forEach(cb => {
      const col = cb.dataset.col;
      if (col in vis && !vis[col]) {
        cb.checked = false;
        toggleCol(cb);
      }
    });
  } catch(e) {}
}

// ── Page 4 helpers ────────────────────────────────────────────────────────────
function mkCollapsedChips(items, cls, uid, max) {
  if (!items.length) return '<span class="text-slate-300 text-xs">—</span>';
  const visible = items.slice(0, max);
  const hidden  = items.slice(max);
  let html = visible.map(k=>`<span class="${cls}">${esc(k)}</span>`).join(' ');
  if (hidden.length) {
    html += ` <span id="${uid}" style="display:none;">${hidden.map(k=>`<span class="${cls}">${esc(k)}</span>`).join(' ')}</span>`;
    html += ` <button class="kw-chip-more" onclick="event.stopPropagation();toggleChips('${uid}',this,${hidden.length})">+${hidden.length}</button>`;
  }
  return html;
}
function toggleChips(id, btn, n) {
  const el = document.getElementById(id);
  if (!el) return;
  const shown = el.style.display !== 'none';
  el.style.display = shown ? 'none' : 'inline';
  btn.textContent = shown ? '+' + n : 'Less';
}

// ── Page 4 — My CVs ──────────────────────────────────────────────────────────
const GROUP_HUES = ['#3B82F6','#8B5CF6','#14B8A6','#F59E0B','#EC4899','#EF4444','#10B981'];
function groupColor(gid) {
  let h = 0;
  for (const c of gid) h = (h * 31 + c.charCodeAt(0)) & 0xffff;
  return GROUP_HUES[h % GROUP_HUES.length];
}
function groupInitials(gid) {
  const parts = gid.replace('group-','').split('-');
  return parts.map(p => p[0] ? p[0].toUpperCase() : '').join('').slice(0,3) || gid.slice(0,2).toUpperCase();
}

async function loadGroupStats() {
  try {
    const resp = await fetch('/api/group-stats');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const groups = await resp.json();
    renderCVStats(groups);
    renderCVCards(groups);
  } catch(e) {
    document.getElementById('cvs-card-grid').innerHTML =
      `<div class="stat-card text-red-600 text-sm col-span-2">Failed to load group stats: ${esc(e.message)}</div>`;
  }
}

function renderCVStats(groups) {
  document.getElementById('cvs-stat-groups').textContent  = groups.length;
  document.getElementById('cvs-stat-cvs').textContent     = new Set(groups.map(g=>g.cv_file)).size;
  document.getElementById('cvs-stat-active').textContent  = groups.filter(g=>g.is_active).length;
  const dates = groups.map(g=>g.last_search).filter(Boolean);
  document.getElementById('cvs-stat-updated').textContent = dates.length ? dates[dates.length-1] : '—';
}

function renderCVCards(groups) {
  if (!groups.length) {
    document.getElementById('cvs-card-grid').innerHTML =
      '<div class="stat-card text-center text-slate-400 text-sm col-span-2">No groups found in config.json</div>';
    return;
  }
  const sorted = [...groups].sort((a,b) => (b.avg_score??-1) - (a.avg_score??-1));
  document.getElementById('cvs-card-grid').innerHTML = sorted.map((g,idx) => {
    const color    = groupColor(g.group_id);
    const initials = groupInitials(g.group_id);
    const sc = g.avg_score;
    const scColor = scoreColor(sc);
    const scBg    = scoreBg(sc);
    const gid = g.group_id;

    // Section B: EN keywords + EN job family (left column, first 6 + collapse)
    const enKws    = (g.primary_keywords&&g.primary_keywords.en)||[];
    const enTitles = (g.job_family&&g.job_family.en)||[];
    const enKwHtml    = mkCollapsedChips(enKws,    'kw-chip-en', `cx-${gid}-enkw`,    6);
    const enTitleHtml = mkCollapsedChips(enTitles, 'kw-chip-en', `cx-${gid}-entitle`, 6);

    // Section C: DE keywords + DE job family (right column, first 6 + collapse)
    const deKws    = (g.primary_keywords&&g.primary_keywords.de)||[];
    const deTitles = (g.job_family&&g.job_family.de)||[];
    const deKwHtml    = mkCollapsedChips(deKws,    'kw-chip-de', `cx-${gid}-dekw`,    6);
    const deTitleHtml = mkCollapsedChips(deTitles, 'kw-chip-de', `cx-${gid}-detitle`, 6);

    // Missing skills (Section D) with 6-category labels
    const topMiss = g.top_missing_skills||[];
    const {tools: mTools, academic: mAcademic, domain: mDomain, langs: mLangs, cert: mCert, soft: mSoft} = categorizeSkillObjs(topMiss);
    const catLblD = t => `<div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#9CA3AF;font-family:'Space Grotesk',sans-serif;line-height:1.8;">${t}</div>`;
    const mkMissPills = arr => arr.map(obj => {
      const s = obj.skill||obj; const c = obj.count||0;
      return `<span class="miss-tag" style="position:relative;">${esc(s)}${c>1?`<sup style="position:absolute;top:-5px;right:-6px;font-size:8px;background:#EF4444;color:#fff;border-radius:9999px;padding:0 3px;line-height:14px;font-weight:700;">${c}</sup>`:''}</span>`;
    }).join(' ');
    let missHtml = '';
    if (mTools.length)    missHtml += catLblD('Tools')    + mkMissPills(mTools);
    if (mAcademic.length) missHtml += catLblD('Academic') + mkMissPills(mAcademic);
    if (mCert.length)     missHtml += catLblD('Certs')    + mkMissPills(mCert);
    if (mLangs.length)    missHtml += catLblD('Languages')+ mkMissPills(mLangs);
    if (mDomain.length)   missHtml += catLblD('Domain')   + mkMissPills(mDomain);
    if (mSoft.length)     missHtml += catLblD('Other')    + mkMissPills(mSoft);

    // Matched skills (Section E) with 6-category labels
    const topMatched = g.top_matched_skills||[];
    const {tools: tTools, academic: tAcademic, domain: tDomain, langs: tLangs, cert: tCert, soft: tSoft} = categorizeSkillObjs(topMatched);
    const mkMatchPills = arr => arr.map(obj => `<span class="match-tag">${esc(obj.skill||obj)}</span>`).join(' ');
    let matchedHtml = '';
    if (tTools.length)    matchedHtml += catLblD('Tools')    + mkMatchPills(tTools);
    if (tAcademic.length) matchedHtml += catLblD('Academic') + mkMatchPills(tAcademic);
    if (tCert.length)     matchedHtml += catLblD('Certs')    + mkMatchPills(tCert);
    if (tLangs.length)    matchedHtml += catLblD('Languages')+ mkMatchPills(tLangs);
    if (tDomain.length)   matchedHtml += catLblD('Domain')   + mkMatchPills(tDomain);
    if (tSoft.length)     matchedHtml += catLblD('Other')    + mkMatchPills(tSoft);

    // Search timeline rows
    const timelineHtml = (g.search_timeline||[]).map(t =>
      `<div class="text-[10px] text-slate-400 font-mono"
        style="font-family:'Space Grotesk';">
        ${esc(t.date)} · <span class="text-slate-600 font-semibold">${t.new_net}</span> new
        · ${t.fetched_total} fetched
        ${t.sources ? `<span class="text-slate-300"> (${esc(t.sources)})</span>` : ''}
      </div>`
    ).join('');

    const statusBg  = g.is_active ? '#DCFCE7' : '#F3F4F6';
    const statusClr = g.is_active ? '#16A34A' : '#6B7280';
    const statusTxt = g.is_active ? 'Active'  : 'Draft';

    return `<div class="group-card" id="gcard-${esc(g.group_id)}">

      <!-- Header -->
      <div class="flex items-start gap-3 mb-4">
        <div class="group-icon" style="background:${color};">${initials}</div>
        <div class="flex-1 min-w-0">
          <div class="font-bold text-base text-[#191c1d] leading-tight" style="font-family:Manrope;">${esc(g.group_label)}</div>
          <div class="text-xs text-slate-400 font-mono mt-0.5">${esc(g.group_id)}</div>
        </div>
        <div class="flex items-center gap-2 flex-shrink-0">
          <span class="text-xs px-2 py-1 rounded-full font-semibold" style="background:${statusBg};color:${statusClr};">${statusTxt}</span>
          ${sc!=null ? `<span class="score-badge text-sm" style="color:${scColor};background:${scBg};">${Math.round(sc)}</span>` : ''}
        </div>
      </div>

      <!-- Section A: CV File -->
      <div class="mb-3">
        <div class="card-section-label">CV File</div>
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-slate-400" style="font-size:18px;">description</span>
          <span class="text-sm text-slate-600 font-medium flex-1">${esc(g.cv_file||'—')}</span>
          <a href="/api/cvfile?name=${esc(g.cv_file)}" target="_blank"
            class="cv-action-btn" title="Preview CV in new tab" style="text-decoration:none;">
            <span class="material-symbols-outlined" style="font-size:16px;">visibility</span></a>
          <button class="cv-action-btn" title="File is in my_cv/ folder">
            <span class="material-symbols-outlined" style="font-size:16px;">download</span></button>
        </div>
      </div>

      <!-- Section B (left) + C (right): two-column keyword layout -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;" class="mb-3">
        <div>
          <div class="card-section-label">Keywords EN</div>
          <div class="flex flex-wrap gap-1.5 mb-1">${enKwHtml}</div>
          ${enTitles.length ? `<div class="flex flex-wrap gap-1">${enTitleHtml}</div>` : ''}
        </div>
        <div>
          <div class="card-section-label">Keywords DE</div>
          <div class="flex flex-wrap gap-1.5 mb-1">${deKwHtml}</div>
          ${deTitles.length ? `<div class="flex flex-wrap gap-1">${deTitleHtml}</div>` : ''}
        </div>
      </div>

      <!-- Section D: Top Missing Skills -->
      ${missHtml ? `<div class="mb-3">
        <div class="card-section-label">Top Missing Skills</div>
        <div>${missHtml}</div>
      </div>` : ''}

      <!-- Section E: Top Matched Skills -->
      ${matchedHtml ? `<div class="mb-3">
        <div class="card-section-label">Top Matched Skills</div>
        <div>${matchedHtml}</div>
      </div>` : ''}

      <!-- Footer: Search Timeline + Actions -->
      <div class="pt-3 border-t border-gray-100">
        ${timelineHtml ? `<div class="space-y-0.5 mb-2">${timelineHtml}</div>` : ''}
        <div class="flex items-center justify-between">
        <span class="text-xs text-slate-400" style="font-family:'Space Grotesk';">
          ${!timelineHtml && g.last_search ? `Last: ${esc(g.last_search)}` : ''}
          ${g.job_count ? `${esc(String(g.job_count))} jobs` : ''}
        </span>
        <div class="flex items-center gap-2">
          <button onclick="searchGroup('${esc(g.group_id)}')"
            class="text-xs font-bold px-3 py-1.5 rounded-full text-white"
            style="font-family:'Space Grotesk';background:linear-gradient(135deg,#005d8f,#0077b5);">
            Search Jobs</button>
          <button disabled title="Coming soon"
            class="text-xs font-bold px-3 py-1.5 rounded-full border border-slate-200 text-slate-300 cursor-not-allowed"
            style="font-family:'Space Grotesk';">Edit</button>
          <div class="dropdown-wrap">
            <button onclick="toggleDropdown('ddrop-${esc(g.group_id)}')"
              class="cv-action-btn text-base font-bold text-slate-500" title="More actions">···</button>
            <div class="dropdown-menu" id="ddrop-${esc(g.group_id)}">
              <span class="dropdown-item" onclick="duplicateGroup('${esc(g.group_id)}')">
                <span class="material-symbols-outlined" style="font-size:14px;vertical-align:-2px;">content_copy</span>
                Duplicate</span>
              <span class="dropdown-item danger" onclick="deleteGroup('${esc(g.group_id)}')">
                <span class="material-symbols-outlined" style="font-size:14px;vertical-align:-2px;">delete</span>
                Delete</span>
            </div>
          </div>
        </div>
        </div><!-- end flex justify-between -->
      </div><!-- end footer -->
    </div>`;
  }).join('');
}

function toggleDropdown(id) {
  const menu = document.getElementById(id);
  if (!menu) return;
  const wasOpen = menu.classList.contains('open');
  document.querySelectorAll('.dropdown-menu.open').forEach(m => m.classList.remove('open'));
  if (!wasOpen) menu.classList.add('open');
}
// Close dropdown on outside click
document.addEventListener('click', e => {
  if (!e.target.closest('.dropdown-wrap')) {
    document.querySelectorAll('.dropdown-menu.open').forEach(m => m.classList.remove('open'));
  }
});

function searchGroup(group_id) {
  const cmd = '搜索职缺 ' + group_id;
  navigator.clipboard.writeText(cmd).catch(() => prompt('Copy this command:', cmd));
  activeGroup = group_id;
  showPage('dashboard');
  applyFilters();
  updateLoadingBtnText();
  // Sync segmented control UI (built dynamically, may not exist yet)
  document.querySelectorAll('#group-tabs .seg-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.group === group_id));
  const btn  = document.getElementById('loading-btn');
  const span = document.getElementById('loading-btn-text');
  btn.disabled = true;
  span.textContent = '⏳ Loading…';
  startPolling();
}

async function deleteGroup(group_id) {
  document.querySelectorAll('.dropdown-menu.open').forEach(m => m.classList.remove('open'));
  if (!confirm('Delete group "' + group_id + '"?\nThis cannot be undone.')) return;
  try {
    const r = await fetch('/api/group-delete', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({group_id})
    });
    const d = await r.json();
    if (d.ok) { loadGroupStats(); showToast('Group deleted'); }
    else showToast('Error: ' + d.error);
  } catch(e) { showToast('Server error: ' + e.message); }
}

async function duplicateGroup(group_id) {
  document.querySelectorAll('.dropdown-menu.open').forEach(m => m.classList.remove('open'));
  try {
    const r = await fetch('/api/group-dup', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({group_id})
    });
    const d = await r.json();
    if (d.ok) { loadGroupStats(); showToast('Duplicated as ' + d.new_group_id); }
    else showToast('Error: ' + d.error);
  } catch(e) { showToast('Server error: ' + e.message); }
}

async function saveNote() {
  const ta = document.getElementById('detail-note');
  if (!ta || !detailJob || !detailJob.jd_path) return;
  const note = ta.value;
  try {
    await fetch('/api/note', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({jd_path: detailJob.jd_path, note})
    });
    detailJob.user_note = note;
    const orig = JOBS.find(j => j.jd_path === detailJob.jd_path);
    if (orig) orig.user_note = note;
  } catch(e) { /* silently fail */ }
}

function showToast(msg) {
  const t = document.createElement('div');
  t.style.cssText = 'position:fixed;bottom:96px;left:50%;transform:translateX(-50%);' +
    'background:#1f2937;color:#fff;padding:10px 20px;border-radius:9999px;font-size:13px;' +
    'font-weight:600;box-shadow:0 4px 16px rgba(0,0,0,.2);z-index:999;white-space:nowrap;' +
    'font-family:Inter,sans-serif;';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2500);
}

// ── Search Analysis ───────────────────────────────────────────────────────────
let _analysisData = null;
let _analysisGroup = 'all';

async function loadSearchAnalysis() {
  document.getElementById('analysis-chart-wrap').innerHTML =
    '<div class="text-slate-400 text-sm text-center py-8">Loading analysis…</div>';
  try {
    const resp = await fetch('/api/search-analysis');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    _analysisData = await resp.json();
    if (_analysisData.error) throw new Error(_analysisData.error);
    _renderAnalysisStats();
    _renderAnalysisGroupTabs();
    _renderAnalysisChart();
  } catch(e) {
    document.getElementById('analysis-chart-wrap').innerHTML =
      `<div class="text-red-500 text-sm text-center py-8">Failed to load: ${esc(e.message)}</div>`;
  }
}

function _renderAnalysisStats() {
  if (!_analysisData) return;
  const groups = _analysisData.groups || [];
  const total  = groups.reduce((s, g) => s + (g.total_fetched || 0), 0);
  const nFall  = groups.filter(g => g.fallback_triggered).length;
  const fallIds = groups.filter(g => g.fallback_triggered)
    .map(g => g.group_id.replace('group-', '')).join(', ');
  document.getElementById('an-stat-total').textContent    = total;
  document.getElementById('an-stat-groups').textContent   = groups.length;
  document.getElementById('an-stat-fallback').textContent = nFall || '0';
  document.getElementById('an-stat-fallback-sub').textContent = nFall ? fallIds : 'none triggered';
  document.getElementById('an-stat-date').textContent     = _analysisData.last_search_date || '—';
}

function _renderAnalysisGroupTabs() {
  if (!_analysisData) return;
  const groups = _analysisData.groups || [];
  const el = document.getElementById('analysis-group-tabs');
  let html = `<button class="seg-btn${_analysisGroup === 'all' ? ' active' : ''}" data-grp="all">All</button>`;
  groups.forEach(g => {
    const label  = (g.group_label || g.group_id).replace(/^group-/i, '');
    const active = _analysisGroup === g.group_id ? ' active' : '';
    const fb     = g.fallback_triggered
      ? ` <span style="background:#FEF3C7;color:#B45309;border-radius:9999px;padding:0 5px;font-size:9px;font-weight:700;">FB</span>`
      : '';
    html += `<button class="seg-btn${active}" data-grp="${esc(g.group_id)}">${esc(label)}${fb}</button>`;
  });
  el.innerHTML = html;
  el.querySelectorAll('.seg-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _analysisGroup = btn.dataset.grp;
      el.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _renderAnalysisChart();
    });
  });
}

function _renderAnalysisChart() {
  if (!_analysisData) return;
  const groups = _analysisData.groups || [];
  const toShow = _analysisGroup === 'all' ? groups : groups.filter(g => g.group_id === _analysisGroup);
  const wrap   = document.getElementById('analysis-chart-wrap');
  if (!toShow.length) {
    wrap.innerHTML = '<div class="text-slate-400 text-sm text-center py-8">No data for this group.</div>';
    return;
  }
  const maxCount = Math.max(1, ...toShow.flatMap(g => (g.keywords || []).map(k => k.count)));
  wrap.innerHTML = toShow.map((g, gi) => {
    const fbBadge = g.fallback_triggered
      ? `<span style="background:#FEF3C7;color:#B45309;border-radius:9999px;padding:2px 8px;font-size:10px;font-weight:700;margin-left:8px;">Fallback triggered</span>`
      : '';
    const kwRows = (g.keywords || []).map(k => {
      if (k.type === 'batch') return '';  // skip Stepstone batch entries
      const isPrimary  = k.type === 'primary';
      const barColor   = isPrimary ? '#3B82F6' : '#F59E0B';
      const typeLabel  = isPrimary ? 'Primary KW' : 'Job Family';
      const typeBg     = isPrimary ? '#EFF6FF' : '#FFFBEB';
      const typeClr    = isPrimary ? '#1D4ED8' : '#B45309';
      const pct        = Math.round((k.count / maxCount) * 100);

      // Source icons — show all sources this keyword was searched on
      const srcs = k.sources && k.sources.length ? k.sources : [(k.source || 'linkedin')];
      const srcHtml = srcs.map(s => {
        const icon = s.includes('stepstone') ? 'S' : 'Li';
        const clr  = s.includes('stepstone') ? '#f97316' : '#0077b5';
        return '<span style="color:' + clr + ';font-weight:700;font-size:10px;">' + icon + '</span>';
      }).join('<span style="color:#cbd5e1;font-size:9px;">+</span>');

      // H/G/M proportions for stacked bar
      const hVal = k.high     || 0;
      const gVal = k.good     || 0;
      const mVal = k.moderate || 0;
      const total = k.count || 1;
      const hPct = Math.round((hVal / total) * 100);
      const gPct = Math.round((gVal / total) * 100);
      const mPct = Math.round((mVal / total) * 100);

      // Stacked bar when analysis data exists; solid light-grey bar otherwise
      let stackedBar;
      if (k.analyzed > 0 && (hPct + gPct + mPct) > 0) {
        stackedBar =
          '<div style="flex:1;background:#E5E7EB;border-radius:9999px;height:8px;min-width:80px;overflow:hidden;">' +
          '<div style="width:' + pct + '%;height:8px;display:flex;">' +
          (hPct > 0 ? '<div style="width:' + hPct + '%;background:#4ADE80;height:8px;flex-shrink:0;"></div>' : '') +
          (gPct > 0 ? '<div style="width:' + gPct + '%;background:#FDE047;height:8px;flex-shrink:0;"></div>' : '') +
          (mPct > 0 ? '<div style="width:' + mPct + '%;background:#FB923C;height:8px;flex-shrink:0;"></div>' : '') +
          '<div style="flex:1;background:#D1D5DB;height:8px;"></div>' +
          '</div>' +
          '</div>';
      } else {
        stackedBar =
          '<div style="flex:1;background:#E5E7EB;border-radius:9999px;height:8px;min-width:80px;">' +
          '<div style="width:' + pct + '%;background:#D1D5DB;border-radius:9999px;height:8px;"></div>' +
          '</div>';
      }

      // H/G/M badges to the right of count
      const hasAny = hVal + gVal + mVal > 0;
      let badgeHtml = '';
      if (hVal > 0) badgeHtml += '<span style="background:#DCFCE7;color:#15803D;border-radius:4px;padding:1px 5px;font-size:9px;font-weight:700;font-family:monospace">H:' + hVal + '</span>';
      if (gVal > 0) badgeHtml += '<span style="background:#FEF9C3;color:#A16207;border-radius:4px;padding:1px 5px;font-size:9px;font-weight:700;font-family:monospace">G:' + gVal + '</span>';
      if (mVal > 0) badgeHtml += '<span style="background:#FFEDD5;color:#EA580C;border-radius:4px;padding:1px 5px;font-size:9px;font-weight:700;font-family:monospace">M:' + mVal + '</span>';
      const matchBadges = hasAny
        ? '<span style="display:inline-flex;gap:3px;flex-shrink:0;">' + badgeHtml + '</span>'
        : '<span style="color:#e2e8f0;font-size:9px;flex-shrink:0;">—</span>';

      return `<div class="flex items-center gap-3 py-1.5" style="border-bottom:1px solid #f3f4f5;">
        <span style="background:${typeBg};color:${typeClr};border-radius:9999px;padding:1px 7px;
          font-size:9px;font-weight:700;font-family:'Space Grotesk',monospace;width:70px;
          text-align:center;flex-shrink:0;">${typeLabel}</span>
        <span style="display:inline-flex;align-items:center;gap:1px;width:32px;flex-shrink:0;">${srcHtml}</span>
        <span class="text-xs text-slate-700 flex-shrink-0"
          style="width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
          title="${esc(k.keyword)}">${esc(k.keyword)}</span>
        ${stackedBar}
        <span style="font-family:'Space Grotesk',monospace;font-size:12px;font-weight:700;
          color:#404850;width:28px;text-align:right;flex-shrink:0;">${k.count}</span>
        ${matchBadges}
      </div>`;
    }).join('');
    const divider = gi > 0 ? '<hr style="border:none;border-top:1px solid #e5e7eb;margin:0 0 24px;">' : '';
    return `${divider}<div class="mb-8">
      <div class="flex items-center gap-2 mb-2">
        <div class="group-icon" style="background:${groupColor(g.group_id)};width:32px;height:32px;font-size:10px;">
          ${groupInitials(g.group_id)}</div>
        <span class="font-bold text-sm text-[#191c1d]" style="font-family:Manrope;">${esc(g.group_label)}</span>
        ${fbBadge}
        <span class="text-xs text-slate-400 ml-2">${g.total_fetched} fetched</span>
      </div>
      <div class="flex items-center gap-4 mb-3" style="font-size:10px;font-family:'Space Grotesk',monospace;flex-wrap:wrap;">
        <span style="display:flex;align-items:center;gap:4px;">
          <span style="width:10px;height:10px;border-radius:2px;background:#3B82F6;display:inline-block;"></span>Primary KW</span>
        <span style="display:flex;align-items:center;gap:4px;">
          <span style="width:10px;height:10px;border-radius:2px;background:#F59E0B;display:inline-block;"></span>Job Family</span>
        <span style="color:#94a3b8;">|</span>
        <span style="background:#DCFCE7;color:#15803D;border-radius:4px;padding:1px 5px;font-size:9px;font-weight:700;">H</span> High ≥70
        <span style="background:#FEF9C3;color:#A16207;border-radius:4px;padding:1px 5px;font-size:9px;font-weight:700;">G</span> Good 50–69
        <span style="background:#FFEDD5;color:#EA580C;border-radius:4px;padding:1px 5px;font-size:9px;font-weight:700;">M</span> Moderate 30–49
        <span style="color:#94a3b8;">| Count = all found · H/G/M = precise score (analyzed jobs only)</span>
      </div>
      <div>${kwRows || '<span class="text-slate-400 text-xs">No keyword data for this batch.</span>'}</div>
    </div>`;
  }).join('');
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadJobs();
</script>
</body>
</html>"""


if __name__ == '__main__':
    config_path = Path("config.json")
    taxonomy = {}
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            taxonomy = cfg.get("skill_taxonomy", {})
        except Exception as e:
            print(f"WARN: could not read skill_taxonomy from config.json: {e}", file=sys.stderr)
    html = HTML.replace("__SKILL_TAXONOMY_JSON__", json.dumps(taxonomy, ensure_ascii=False))
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(html, encoding='utf-8')
    size_kb = os.path.getsize(DEST) // 1024
    print(f"Generated: {DEST}  ({size_kb} KB)")
    print("Next: python scripts/server.py")
