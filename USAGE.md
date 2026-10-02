# 给主控的使用说明

> **已退役（2026-10-02）**：用户已批准由 [Saddle](https://github.com/firegnu/saddle) 核心遥测接管新链路，路由由其可选 dispatch 插件提供。本仓库停止新开发与新采集，不再复制旧启用模板或以旧 dlog 包装新派发。以下内容仅作历史说明；本地程序和 `~/.local/share/dispatch-log/` 旧数据保留，不导入、不删除，`ls/show/cat` 可离线查看历史。不要自行恢复服务、委派任务或修改上游。

用户可以对主控说：“先读 dispatch-log/USAGE.md，本会话通过记录器进行路由、派发和收尾记录。”

这是一条改变后续命令入口的指令，不授权你立即派发、推进队列或修改上游。必须继续遵守用户、当前项目与 corral 的既有约束。本仓库没有安装全局技能；每个会话显式启用一次。

## 准备

下面是命令模板，不是自动执行脚本。先设置本机真实路径：

```sh
dlog_bin=/absolute/path/to/dispatch-log/dlog
project_dir=/absolute/path/to/project
worktree_dir=/absolute/path/to/project-worktrees/task-branch
task_file=docs/任务/T41-example.md
```

`project_dir` 必须是 drover 使用的项目根，不是实现者 worktree。实际工作目录单独记录。未参与 drover 的任务也可使用显式的个人任务号；记录器不验证或写入队列。

## 一次派发

1. 建立派发 ID。任务号只在这个项目内有意义：

```sh
dispatch_id=$("$dlog_bin" new --project "$project_dir" --task T41)
```

若该命令失败，不要把空 ID 当成已建立记录。ID 已持久化，压缩上下文后可用 `ls --project "$project_dir" --task T41` 查询，不需要写进实现 agent 的提示词。

2. 调用 JEV。用文件重定向传入实际摘要，避免 shell 引号改变正文：

```sh
"$dlog_bin" route --dispatch "$dispatch_id" < /path/to/summary.txt
```

默认读取 `~/.agents/skills/corral-dispatch/route.py`，可通过 `--route-file` 显式指定。支持的版本走 B；其他版本在请求前降级 A，并在 stderr 提示。stdout/退出码仍是路由结果。不要为了补采再调用 JEV。

3. 显式写下实际决定，不把 JEV 建议当主控决定：

```sh
"$dlog_bin" decide --dispatch "$dispatch_id" \
  --model 'opus[1m]' --effort high --budget '目标检查与相关回归' \
  --reason '采纳常规档建议；本轮只做已授权范围'
```

4. 通过记录器执行你原本已获授权的 corral start。模型、强度、角色依实际派发填写，以下只是示例：

```sh
"$dlog_bin" start --dispatch "$dispatch_id" --task-file "$task_file" -- \
  corral start project/dev-example --unique --cwd "$worktree_dir" \
  --label role=implementer --label 'model=opus[1m]' --label effort=high \
  --prompt '先读 AGENTS.md 和 docs/任务/T41-example.md，按任务书完成。' \
  -- claude --model 'opus[1m]' --effort high
```

`--` 后是原命令，记录器不会补参数、添加采集提示词或重试。后续使用 corral 返回的实际 `name`，不能猜 `--unique` 后缀。

start 的相对 `--task-file` 按 corral `--cwd` 解析；派发前保存全文。没有提供文件时明确没有快照。快照不能证明 agent 实际读取版本。

5. 等待和提醒仍按原 corral 流程。记录器不提供新的等待服务。轮次完成后，通过记录器读取一次回复：

```sh
"$dlog_bin" reply --dispatch "$dispatch_id" -- corral reply <实际名字>
```

保留公开接口的 name/instance/text/at。`--dispatch` 是你的归属声明；instance 相符只证明实例一致，不证明回复回应了哪次 send。必须检查内容，不把旧回复当新回复。

6. 提交审查原文，或发出已获授权的返工要求：

```sh
"$dlog_bin" note --dispatch "$dispatch_id" --kind review --file /path/to/review.md
"$dlog_bin" send --dispatch "$dispatch_id" --kind rework \
  --task-file /absolute/path/to/revised-task.md -- \
  corral send <实际名字> '具体返工要求'
```

send 的相对 `--task-file` 按调用者当前目录解析，建议使用绝对路径；它没有 corral start 的 `--cwd`。同 agent 的本次返工可以追加事件；换 agent、升档重派或独立审查，重新 `new --parent "$dispatch_id" --kind redispatch|review` 并使用新 ID。

## 查询和停用

```sh
"$dlog_bin" ls --project "$project_dir" --task T41
"$dlog_bin" show "$dispatch_id"
"$dlog_bin" cat <内容的sha256>
```

stdout 的 JSON 和原文可以直接供后续分析或 saddle 读取。当前 saddle 还没有读取这些文件。

停用时告诉当前主控恢复直接调用 route.py/corral，不再提交 note/decide。没有后台进程要停止；确认旧会话不再调用 dlog 后再卸载。当前没有自动停用开关或全局配置。卸载程序不会删除记录，保留目录仍可日后分析。

## 失败必须分开看

- **真实命令失败**：原样传出结果；由现有流程判断，不自动重发。
- **记录失败**：stderr 明确提示，但真实操作仍只执行一次；以 corral 的 stdout/退出码判断操作，不因记录失败重发。
- **只有 intent，没有 result**：完成情况未知。可能程序被打断，也可能结果未落盘；先查公开状态，不能认定没执行。
- **send pending**：只表示排队，不表示送达。`merged_with_draft=true` 时仅保存我们发送的片段，完整拼接输入未知。
- **默认数据目录不可写**：可能连“记录缺口”也无法持久保存，stderr 是唯一提示。
- `new/decide/note` 是纯记录命令，保存失败会非零退出；不涉及 agent 操作。

不要把缺失解释成未发生。不要补造历史，不读取私人会话来填洞，不为了记录给运行中的 agent 额外送话。
