# 阶段状态（2026-09-20）

## PHASE 0

STATUS: COMPLETE_WITH_FINDINGS

Implemented: 可重复运行的环境侦察，显式搜索根目录、PATH 与 OpenRadioss 环境变量；在线可达性检查、只读 ZIP 源码清点及帮助命令探测。

Verified: Python 3.11.9；Git 2.53.0.windows.3；6 个求解器可执行文件；hm_cfg_files 含 radioss2026/radioss2612；源码 ZIP 内 2160 个 Starter 源文件、166 个 RAD 文件；四个指定官方网站 HTTP 200；Starter -help 返回 0。

Not verified: Engine 模型运行、MPI、源代码 ZIP 与二进制是否来自相同提交；网页可访问不代表每个 keyword 已验证。

Known limitations: py 启动器指向失效 Python315；Engine -help 输出后返回 157 / access violation；没有修改安装或尝试掩盖问题。侦察明确限定指定目录和环境路径，不声称扫描所有磁盘。

Tests: `python bridge.py doctor --search-root D:\OpenRadioss --online --solver-help`。

Files changed: 新增 src/bdf2rad/runtime.py、reports/environment/environment.json；外部原文件未修改。

Next phase: PHASE 1。

## PHASE 1

STATUS: INITIAL_IMPLEMENTATION_TESTED

Implemented: 8/16 字符固定格式、逗号自由格式、显式/空白续行、INCLUDE 递归、循环/深度检查、数字简写、源位置、原文、控制段保留、流式 AST 输出。

Verified: 13 个词法回归测试通过；小型板示例可 inspect。

Not verified: 真实 NX 大模型、GB 级性能、所有 Nastran 方言。

Known limitations: 混合字段格式续行明确拒绝；自由格式最多 8 个数据字段加续行字段；控制段仅保留，尚不解析 SUBCASE/LOAD/SPC 选择语义；不实现跨 INCLUDE 边界续行；不支持所有高级 INCLUDE 表达式；注释单独行未作为实体保存。INCLUDE tree 与控制段当前保存在内存中。

Tests: tests/test_parser.py。

Files changed: src/bdf2rad/parser.py、diagnostics.py、cli.py、tests/test_parser.py、examples/parser_sample.bdf、bridge.py、pyproject.toml。

Next phase: PHASE 2。

## PHASE 2

STATUS: FOUNDATION_ONLY

Implemented: 要求中的全部 Model 容器、Confidence、MappingResult、MappingRegistry、稳定 ID 命名空间分配和悬空引用拒绝。

Verified: ID 保留、重编号稳定性、重复 ID 拒绝、命名空间隔离、未知 mapper 不宣称成功。

Not verified: 类型化实体、完整 BDF→IR 构建、坐标变换、物理语义和目标引用同步。

Known limitations: Model 暂为容器基础，不是已实现完整语义模型；注册表目前没有已验证的转换规则。

Tests: tests/test_model.py（4 项）。

Files changed: src/bdf2rad/model.py、tests/test_model.py。

Next phase: 完成 PHASE 2 类型化实体和语义构建，再进入 PHASE 3；PHASE 3–21 尚未实施。

## 原 NX 脚本评估

实际位置是 D:\OpenRadioss\nx2rad_rev_000，用户给出的 nx2rad\_rev\_000 目录不存在。
只读查看 ZIP 内 nx2rad_rev_000.py，未执行。其依赖 NXOpen 活跃 FEM 会话，导出网格及分组，不读取 BDF。
分组 ID 用 abs(hash(group_name))，跨 Python 进程不保证稳定且可能碰撞；未知单元直接 continue；Quad8 与 Quad4 使用同一 SHELL 分支。
脚本未构成材料/属性/接触/边界条件完备的转换链，不可作为本项目语义映射或物理验证依据。
