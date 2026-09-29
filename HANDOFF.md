# dispatch-log 交接

更新：2026-09-29。仓库：`/Users/firegnu/Developer/personal_projs/dispatch-log`，分支 `main`。

## 会话摘要

用户从 saddle T38 讨论中选择“独立旁路采集器 + 主控显式使用指令”，采用 JEV 方案 B，并要求新建 repo、写好首版代码与交接；之后由用户自己用 corral 开新 agent 专门接手。

本次完成独立 Python CLI 及离线验证，没有委派新的实现 agent，没有修改 corral/drover/共享技能或 saddle，没有启用全局采集或操作真实队列。

## 已完成

- 本地 Git repo、`main`、标准 Python 包配置、可执行 `./dlog`、开发约定与中文使用说明。
- 显式 project/task/dispatch/parent 关联；本地原子事件和原文快照；`new/ls/show/cat` 查询。
- JEV B：加载核验过的 route.py，保存请求、整理前完整解析响应、整理建议；版本变化在请求前降级 A。失败不额外调用平台。
- corral start/send/reply 包装、派发/返工前任务书快照、模型参数与标签分开、主控决定与审查原文。未关联、实例冲突、草稿合并与 pending 不伪造为成功或确定归属。
- 20 项检查通过（含 3 项已安装 route.py 的离线契约检查）；使用临时目录/假 corral/合成 JEV 响应，无真实平台请求。检查命令和 RED→GREEN 证据见 `docs/VALIDATION.md`。
- 功能提交：`7c0a749 实现独立任务过程记录器与 JEV 版本适配`；随后单独提交本交接文档。

## 当前状态与未完成项

- 本地提交已完成；没有配置 remote、没有创建远端仓库或推送。交接文档随本轮提交，收尾目标为工作树干净；接手请用 `git status --short` 核实。
- 未安装到全局 PATH；直接运行 `./dlog` 或 `python3 -m dispatch_log`。未修改任何客户端个人全局指令，也没有安装个人技能。
- 尚未在真实任务中启用；默认真实数据目录本轮未创建。测试数据均在已清理的临时目录里。
- saddle Dispatch 的读取/展示尚未接入。这是另一仓库的后续工作，不要顺手修改 saddle 或推进 T38 队列。
- 尚无后台服务、自动采全、历史补录、统计打分或自动卸载/停用开关，这些不属于首版。
- 版本化 JEV 适配有维护成本：当前 SHA 在 `dispatch_log/route.py` 和设计文档中。上游更新后先核验、离线比对，再更新许可 SHA，不能盲目放行新版本。
- 没有发现现有覆盖范围内未修复的失败；已知能力边界包括绕过入口漏记、reply 归属是主控声明、HTTP 原始字节未采集、极端中断后仅 intent 不代表未执行。详见设计。

## 关键决定与优先阅读

1. `AGENTS.md`：开发范围、隐私与操作边界。
2. `README.md` / `USAGE.md`：运行方式与主控完整操作模板。
3. `docs/DESIGN.md`：原始事实/主控陈述/缺失的含义、B 的耦合边界、格式 v1。
4. `dispatch_log/route.py`：版本固定的 JEV 适配；`corral.py`：只执行一次、白名单字段。
5. `store.py` / `record.py`：本地持久保存、记录失败与真实命令结果分离。
6. `docs/VALIDATION.md` / `tests/`：可重复验证，不需要真实 agent 或 API key。

## 接手建议

先读以上文档，运行标准离线检查并检查 Git 状态。当前用户授权的是准备可接手的首版，不代表已经批准全局安装、后台采集、真实任务试跑或 saddle 接入；按用户新会话的具体指示继续，不自行扩展。

可直接交给新 agent 的首句：

> 你现在专门接手 dispatch-log。先读 AGENTS.md、HANDOFF.md、README.md、USAGE.md 和 docs/DESIGN.md，核对当前代码与验证记录，向我报告已实现能力、已知边界和建议的下一步；先不要安装全局指令，不要操作真实 agent/队列，不要修改上游或 saddle。
