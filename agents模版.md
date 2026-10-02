# 项目主控启用 dispatch-log

> **已退役（2026-10-02）**：用户已批准由 [Saddle](https://github.com/firegnu/saddle) 核心遥测接管新链路，路由由其可选 dispatch 插件提供。本仓库停止新开发与新采集，不再复制旧启用模板或以旧 dlog 包装新派发。以下内容仅作历史说明；本地程序和 `~/.local/share/dispatch-log/` 旧数据保留，不导入、不删除，`ls/show/cat` 可离线查看历史。不要自行恢复服务、委派任务或修改上游。

将下面这段复制到需要启用记录的项目根目录 `AGENTS.md` 中：

> 本项目主控在进行任务路由、派发及审查收尾前，先阅读 `/Users/firegnu/Developer/personal_projs/dispatch-log/USAGE.md`，按其说明使用 dispatch-log 保存记录。被委派的实现者和审查者无需采集。此要求不改变原有任务授权及队列放行流程。

以上路径用于当前本机；换机器时改为该机器上 dispatch-log 的实际路径。已有主控会话需重新读取更新后的 `AGENTS.md`，后续新会话读取该文件后即可沿用。
