# 本轮修改与证据

所有写入位于 D:\BDF2RAD-X。外部安装、输入、旧输出和用户附件只读。

1. `paths.py`：限制输出在项目内；CLI 在创建目录前检查。
2. `audit.py`、`deck.py`：不完整审查输出改为 .rad.draft；不再将 JSON false 描述为对外部 GUI 的实际启动拦截。
3. `solver_log.py`：独立报告 Engine 启动/正常退出及仿真有效性；用户日志被判 FAILED，原因 NO_PART + EMPTY_MODEL_RUN。单循环本身不自动判失败。
4. `solid.py`：受限实体 IR、注册表、引用及正体积检查，输出真实 /MAT/LAW1、/PROP/SOLID、/PART、/TETRA4 及配对 Engine。
5. 实测 reports/elastic_tetra/starter.log：0 errors / 0 warnings。engine.log：正常结束、2 cycles，打印稳定时间步 8.2108e-7。
6. 29 项 unittest 通过，包括高阶和塑性拒绝、草稿隔离、输出边界、真实 Part 输出及日志误判回归。

语法参考：只读查看 OpenRadioss-main.zip 的 ACCELERO、COMPA1B、JETV41B、INTERF/INT_25/tetra4 官方 miniqa，未复制完整官方模型。
本轮未完成各关键字官网文档和材料 formulation 全面交叉验证，故不标记物理 VERIFIED。

尚未完成：Solution 3-1 的 CTETRA10/CHEXA20/CPENTA15、MATS1、胶接接触、RBE、集中质量、SPC/TIC/GRAV 及工况语义。
当前基准不加载这些内容；正式样例仍不可宣称转换成功。下一阶段需分别建立这些映射和物理回归，不能把基准 writer 无条件套到大模型。


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
