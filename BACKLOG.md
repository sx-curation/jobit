 P0 — 阻塞核心工作流（必须先做）

 1. Page 3：Add / Edit Search Group 表单
 - 路由：导航栏"+ Add Group" → 新建；Page 4 "Edit" → 预填已有 group
 - 字段：Group ID、Label、CV File 下拉（来自 /api/cvfiles）、Primary Keywords EN/DE（chip input）、Job Family EN/DE（多行 textarea）
 - 折叠区：Search Settings（Location / Date Range Days / Max Jobs / Score Threshold）
 - 底部操作栏：Cancel | Save Draft | Save & Search Now
 - 需新增服务端：POST /api/group-save { group } → upsert config.json
 - 关键 UX 细节：Group ID 实时格式化（转小写 + 连字符）；保存后吐出 Toast；Save & Search Now 复制指令 + 跳 Dashboard + 开始轮询，
 限制group数量，最多6个

 2. 材料生成状态指示器（Generated Badge）
 - 当前痛点：用户不知道哪些职缺已生成 CV/Cover Letter，需去文件夹查
 - 方案：server.py parse_jobs() 扫描 jd_path 对应目录下是否存在 cv_final.pdf / cover_letter_final.pdf，添加 materials_ready: bool 字段
 - 前端：在表格 Title 列后加小图标（📄）或在 Score 旁加徽章，hover 显示"CV + CL generated"

 CV 文件服务（预览 + 下载）
 - 当前：按钮存在但无功能
 - 方案：server.py 新增 GET /api/cvfile?name=my_cv_da.pdf → 返回 MY_CV_DIR / name（路径验证：不允许 ..）
 - 下载：<a href="/api/cvfile?name=..." download>
 - 预览：新 tab 打开，浏览器原生 PDF viewer

 1. Page 3 "Search Settings" 与 config.json 数据模型冲突                                                                                                                                                 
                                                                                                                                                                                                          
  SPEC 中 Page 3 表单的 4 个字段映射如下：

  ┌─────────────────────────┬─────────────────────────────────┐
  │          字段           │            映射路径             │
  ├─────────────────────────┼─────────────────────────────────┤
  │ Location                │ job_search.location             │
  ├─────────────────────────┼─────────────────────────────────┤
  │ Date Range Days         │ job_search.date_range_days      │
  ├─────────────────────────┼─────────────────────────────────┤
  │ Max Jobs Per Keyword    │ job_search.max_jobs_per_keyword │
  ├─────────────────────────┼─────────────────────────────────┤
  │ Score Threshold Warning │ job_search.score_threshold_warn │
  └─────────────────────────┴─────────────────────────────────┘

  问题：这 4 个字段都在 job_search.*（全局配置），不是 per-group 字段。
  如果在"Edit group-da"的表单里修改了 Location，所有 group 的搜索地点都会被改掉。

  有两种解法，需要你选一个：
  - 方案 A：这 4 个字段从 Page 3 form 中移除，改为单独的"Global Search Settings"入口（Page 4 顶部或 navbar）
  - 方案 B：将这 4 个字段下沉到 per-group 配置（keyword_groups[].search_settings），每个 group 独立控制

  ---
  2. /api/group-save upsert key 不明确

  SPEC 说"新增或更新 config.json 中的 group 对象"，但 没有定义 update 的 key。

  在 Edit 模式下，如果用户修改了 Group ID：
  - 旧 group_id 的 output 文件夹名全部失效
  - config.json 里应该删除旧条目还是保留？
  - 还是 Edit 模式下 Group ID 字段应该设为只读？

  建议：Edit 模式下 Group ID 不可修改（置灰），upsert key = group_id。是否认可？

Page 3 Group ID 格式约束缺失

  输出目录命名规则是 output/<group_id>_<company>_<title>_<YYYYMMDD>/。

  如果用户输入 My Group! 或 group DA（含空格/特殊字符）仅用于group label。
  SPEC 未规定 Group ID 的格式约束（如：只允许小写字母、数字、连字符）。


  投递漏斗视图（Application Funnel）
     - Dashboard 统计区增加第 2 行：Pipeline 卡片
     - 数据：JOBS 中各 application_record 状态计数，Sankey/水平条图
     - 帮助用户看清"搜索→标记→投递→面试→offer"转化漏斗                                                           



 9. Search Timeline（Page 4 Footer）
  SPEC 要求卡片 Footer 展示该 group 最近 3 次搜索记录（日期 + （new_total-hidden_low_score-skipped_duplicate）+ fetched_total+fetched_per_source），数据来自 output/search_history.json。sample json
   {
      "batch_id": "20260417_001",
      "date": "2026-04-17",
      "raw_results_file": "output\\temp\\raw_results_20260417_001.json",
      "dedup_done": true,
      "fetched_total": 36,
      "fetched_per_keyword": {
        "Marketing Analytics Specialist; Marketing Performance Analyst; Go-to-Market Data Analyst": 36
      },
      "fetched_per_source": {
        "stepstone": 36
      },
      "new_total": 36,
      "displayed": 2,
      "skipped_duplicate": 0,
      "hidden_low_score": 34,
      "job_ids": [
        "st_07244229",
        "st_6f023fe0"
      ]
    },



独立新增功能，对于Linkedin搜索结果，根据search_search.json，自动检查search date-15，15天前的职缺是否已经过期，不再接收职缺投递（e.g.No longer accepting applications）。如果之前没有application record，则更新为invalid

My CVs，keyword添加编辑按钮，可以删除或添加关键词，并对应更新config