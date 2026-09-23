# Capability matrix

当前测试证据：17 个 unittest 回归测试；没有求解器模型运行证据。

| 能力 | 状态 | 边界 |
| --- | --- | --- |
| Environment discovery | IMPLEMENTED | 有搜索范围说明；Engine help 异常已记录 |
| BDF small / large / free lexer | PARTIAL | 已测常见格式；未覆盖全部方言 |
| INCLUDE / provenance | PARTIAL | 支持递归与循环拒绝；跨文件续行未支持 |
| Unknown card preservation | IMPLEMENTED | AST JSONL 全量保留，尚无语义分类 |
| Intermediate model | PARTIAL | 容器与 metadata 基础 |
| ID manager | PARTIAL | 确定性分配与引用检查；尚未接入 writer |
| Node / element / property / material mapping | UNSUPPORTED | 尚未实现 |
| Contact / failure / composite / loads / rigid mapping | UNSUPPORTED | 尚未实现 |
| Native RAD writer / validation | UNSUPPORTED | 尚未实现 |
| Starter / Engine model execution | UNSUPPORTED | 仅完成环境探测 |
| Physics / energy validation | UNSUPPORTED | 尚未实现 |
| GUI | UNSUPPORTED | CLI 转换完成后开发 |


## Explicit pipeline development — 2026-09-21

Added separate Nastran IR, Radioss IR schema, full semantic scan, basic reference validation, and convert-explicit CLI. bridge.py uses the new entry point. Outputs are restricted to D:\BDF2RAD-X. Native writer publication is blocked; no runnable full-model deck has been produced.

Real input scan: 551461 nodes, 257641 solid elements, 12 materials, 5 plastic definitions, 1401 SPC records, 548571 TIC records. The requested illustrative 257646 element total differs from the actual solid-card sum (248363 + 9139 + 139 = 257641). Concentrated source mass is 0.167 kg; target/structural mass remains unverified.

Phase 1 is PARTIAL: entity provenance, repeated SPC/TIC records, duplicate mesh IDs and unknown records retained; set selection resolution, comprehensive field validation and mapping remain incomplete. Phases 2–13 remain unverified/unimplemented. High-order topology, material serialization, formulation, rigid constraints, active contact/glue, loads, solver runs and mass comparison block publication. CPENTA fallback is proposed, not applied.

33 legacy tests and 3 new explicit pipeline regressions pass. No Starter or Engine run was performed for the new pipeline.


## External-output and active-case execution update

OutputPolicy now grants directory-scoped external writes, propagated from bridge/CLI to converter report output. Old commands retain workspace-only behavior. The authorized E:/openradioss/output directory receives the report directly. Native writer remains unimplemented; policy propagation into an actual native writer is still pending.

Added active_case.py: single effective subcase selection, BCTADD/BGADD expansion with cycle detection, selected TIC velocity clustering, selected gravity and TSTEP1 end time. SPCADD and general LOAD combinations remain unsupported.

Real direct-run and module CLI were executed: INCOMPLETE. Active source counts: SPC 1401, TIC 548571, sliding sets 1, glue sets 313. Velocity [0,0,-4430] mm/s on 548571 nodes; gravity [0,0,-9810] mm/s^2; selected end time 0.003 s. Mesh order counts match the supplied baseline. These are source checks, not target equivalence checks.

pytest installed into workspace .test-deps only. With PYTHONPATH set to .test-deps and src, python -m pytest -q passed 38 tests and 3 subtests. Initial system-Python pytest command failed because pytest was absent.

Changed: bridge.py, bdf2rad/__init__.py (source-checkout launcher), src/bdf2rad/paths.py, cli.py, converter.py, new active_case.py, tests/test_explicit.py, capability/progress documents. Full native conversion, high-order Starter regressions, contact surface reconstruction, material/constraint/load serialization, Starter execution and Engine smoke remain incomplete. No full-model RAD files emitted. Report: E:/openradioss/output/conversion_report.json.
