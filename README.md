# Codex Windows Shared Home

**实验性工具，两个可信 Windows 用户轮流使用。禁止并发。**
Experimental toolkit for sequential use of one Codex home by trusted Windows users.

目标是一份历史、项目列表和普通配置，并能在另一个 Windows 用户中续接开发。
认证、浏览器和部分运行状态按用户保存。这不是 OpenAI 官方工具，也不是适用于
任意 Codex 版本的一键迁移程序。

## 提供的工具

- 只读审计：核心文件数量、已知数据库中的历史数量、失效 rollout 路径。
- 停机核心快照：筛选复制、SHA-256 校验、SQLite 及 WAL/SHM 保留；
  只对副本 quick_check，不 checkpoint 原库。
- 按字段生成路径计划；最长目录前缀匹配、目录边界与联接别名处理。
- 候选副本的精确事务更新原语；旧值不符和身份键冲突会停止。
- Windows 启动器：跨用户独占租约、身份校验、已知私有目录联接切换、
  普通配置准备、子进程专用环境和可选代理。

没有通用的第二用户数据库合并器、自动 Git worktree 修复器或生产迁移器。
完整迁移需要按 [迁移说明](docs/MIGRATION.md) 逐项审阅；
只运行启动器不会把两份旧历史自动合成一份。

## 边界

1. 一个用户完全退出共享版后，另一个才能启动。保持启动器运行，
   不要删除锁文件或绕过守卫。普通 Codex 也必须先退出。
2. 共享目录参与者必须相互信任；共享内容包含对话和代码引用。
   目录联接不是参与者之间的安全隔离。工具不修改 ACL。
3. 启动器要求 OS 凭据存储，拒绝共享 auth.json，只绑定已登记私有目录。
   不读取、导出、复制或迁移凭据文件；每个用户手动登录。
   keyring 不代表所有认证状态都在 home 外，应用还可能使用加密 secrets。
4. 内部变量 CODEX_ELECTRON_USER_DATA_PATH 只表示请求私有 Electron profile，
   不能证明所有浏览器及原生辅助进程都使用这个目录。
5. 不关闭沙盒、不更改权限模式、不放宽权限。**尚未证明完整 Windows 沙盒状态隔离**；
   已有任务权限可能与全局配置不同。系统设置或权限提示需另行审查。
6. 文件名筛选无法识别配置、Skills、插件或对话内嵌的秘密，也可能遗漏正常资产。
   快照、审计报告和本地设置只留本机，不能作为公开附件。

## 快速开始：只读审计

需要 Windows、Python 3.11+；启动器还需 PowerShell 7、已注册的 Codex 桌面应用、
当前 Windows 用户可用的 Codex Python runtime。两用户须已拥有所需访问权；
工具不会替你取得访问权。

~~~powershell
Copy-Item examples/settings.example.json local.settings.json
# 编辑本地设置，填写实际 SID、profile、source_home；不要提交这个文件。
$env:PYTHONPATH = "$PWD/src"
python -B -m codex_shared_home.cli --settings local.settings.json audit --home 'C:\Users\UserA\.codex'
python -B -m codex_shared_home.cli --settings local.settings.json plan-paths --home 'C:\Users\UserA\.codex'
~~~

以上命令不修改核心数据。示例中的用户、SID 和路径均为虚构。
审计只支持代码列出的已知 schema；新版本可能停止或需要适配。

## 停机快照与启动

关闭两个 Windows 会话内的桌面端、CLI、app-server、MCP、自动化及其他写入者。
仅锁屏或切换用户不等于退出。

~~~powershell
python -B -m codex_shared_home.cli --settings local.settings.json snapshot --home 'C:\Users\UserA\.codex' --output 'D:\CodexShared\snapshots\UserA-first'
# 默认 dry run；确认全部停止后，同一命令增加 --apply 才创建新快照。
~~~

该快照排除已知私有状态，**不是完整灾难恢复备份**。另用受限的本地备份方法
保全 AppData、私有状态和启动设置，勿展开凭据内容。

完成独立候选验证、路径审阅和停机迁移后，操作人员才能在 shared_root/home 下
创建 SHARED-HOME-READY.json，并将 allow_private_state_binding 改为 true。
此标记代表人工验收，工具不验证其内容。然后运行：

~~~powershell
.\windows\Start-Shared.cmd
~~~

自动 MSIX 查询不可用时，在本地设置填写已核对的 app_executable。
启动器只对子进程设置 CODEX_HOME，不改持久环境、系统代理或默认快捷方式。
关闭启动器会失去租约保护；切换前须确认应用和后台写入者退出。

## 测试与验证

参见 [验证记录](docs/VALIDATION.md)。测试仅使用虚构数据。
本地原型交替续接成功，不等于这个通用版本或任意 Codex 更新已通过验收。
更换应用版本后重新做 A → B → A 验证。

~~~powershell
$env:PYTHONPATH = "$PWD/src"
python -B -m unittest discover -s tests -v
~~~

## English summary

This MIT-licensed experimental reference toolkit targets one shared history,
project list and ordinary configuration, used sequentially by trusted Windows
users. It offers filtered cold snapshots, typed path planning and a guarded
launcher. It does not merge SQLite databases, migrate credentials, change ACLs,
disable sandboxing or automatically promote a production migration. Authentication
and selected runtime directories are routed per user; complete browser and Windows
sandbox isolation is not established. Read the migration and validation documents
before attempting a disposable trial.

References: [environment variables](https://learn.chatgpt.com/docs/config-file/environment-variables),
[app-server](https://learn.chatgpt.com/docs/app-server),
[Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox).

License: [MIT](LICENSE).
