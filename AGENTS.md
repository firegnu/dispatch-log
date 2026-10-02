# dispatch-log 开发约定

> **已退役（2026-10-02）**：用户已批准由 [Saddle](https://github.com/firegnu/saddle) 核心遥测接管新链路，路由由其可选 dispatch 插件提供。本仓库停止新开发与新采集，不再复制旧启用模板或以旧 dlog 包装新派发。以下内容仅作历史说明；本地程序和 `~/.local/share/dispatch-log/` 旧数据保留，不导入、不删除，`ls/show/cat` 可离线查看历史。不要自行恢复服务、委派任务或修改上游。

先读 `README.md`、`docs/DESIGN.md`、`HANDOFF.md`。本项目由 saddle T38 讨论拆出，用户已选择独立 repo 和 JEV 方案 B。

- 只维护本仓库的个人记录器；未经用户明确授权，不改 corral、drover、共享 corral-dispatch-skill 或客户端全局指令，不推进真实队列。
- 不启动常驻服务，不注入工作 agent，不读私人会话日志/终端历史，不读 corral/drover 内部文件。外部集成只走公开 CLI。
- 方案 B 只加载经过哈希核验的 route.py 字节，调用既有函数；不修改该文件，不复制路由题目、规则或阈值。
- 适配器不得额外请求 JEV；失败不得自动重放 start/send。兼容降级只能发生在请求之前。记录结果与操作结果分离。
- 不把主控声明、文件快照或时间接近当成已证明的回复归属/agent 实际读取。字段未知时保持未知。
- 不给 agent 名字推断项目/任务，不把工作目录当任务项目，不建立新的队列状态机。
- 保持标准库实现，先做最小改动。行为变更先有针对性失败检查，再实现并回归；文档不造 RED。
- 标准检查：`python3 -m unittest discover -s tests -v`。修改 JEV 适配时增加 `DLOG_TEST_ROUTE` 的离线契约检查。
- 测试只用临时目录、合成材料和假 corral；JEV 网络必须 mock，不调用真实平台，不读取或保存真实队列正文/回复。
- 采集数据不提交。新增字段遵循白名单，不存通用 argv、环境、认证头或任意 stderr。
- 不自行委派、启用全局采集、安装服务或发布远端；用户会用 corral 开新 agent 专门接手。
- 完成后更新中文 `HANDOFF.md`，写清代码、验证、未接入项与未提交状态；设计理由放 `docs/DESIGN.md`。
