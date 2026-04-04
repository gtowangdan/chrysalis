# Chrysalis 排障指南

## MCP Server 配置后不生效（Claude Code 无法连接）

### 症状

手动在 `~/.claude/settings.json` 的 `mcpServers` 中添加了 chrysalis 配置，但：
- `claude mcp list` 看不到 chrysalis
- Claude Code 会话中没有 chrysalis 的工具
- MCP handshake 手动测试正常（直接执行 binary 是通的）

### 原因

Claude Code 的 MCP 配置分两层：

| 文件 | 作用 | 写入方式 |
|------|------|----------|
| `~/.claude/settings.json` | 全局设置（权限、插件、环境变量等） | 手动编辑 |
| `~/.claude.json` 或项目根目录 `.claude.json` | MCP server 注册 | `claude mcp add` 命令 |

**关键发现**：`settings.json` 中的 `mcpServers` 字段虽然可以写入，但 `claude mcp list` 并不读取它。只有通过 `claude mcp add` 写入 `.claude.json` 的配置才会被 Claude Code 正确加载。

### 解决办法

**正确方式**：使用 `claude mcp add` 命令注册：

```bash
# 从源码安装（指定 venv 中的 binary）
claude mcp add chrysalis -- /path/to/chrysalis/.venv/bin/chrysalis

# 使用 uvx（推荐，无需管理虚拟环境）
claude mcp add chrysalis -- uvx chrysalis
```

**验证**：

```bash
# 查看是否连接成功
claude mcp list | grep chrysalis
# 应显示: chrysalis: ... - ✓ Connected
```

**功能测试**：

```bash
# 在新会话中测试工具调用
claude -p "调用 get_stats 工具" --allowedTools "mcp__chrysalis__*"
```

### 清理

如果之前在 `settings.json` 中手动添加了 `mcpServers.chrysalis`，可以删除该条目，避免混淆。实际生效的是 `.claude.json` 中的配置。

### 配置作用域

`claude mcp add` 默认写入项目级配置（当前目录的 `.claude.json`）。如需全局可用：

```bash
claude mcp add --scope user chrysalis -- /path/to/chrysalis/.venv/bin/chrysalis
```

| scope | 配置文件 | 适用范围 |
|-------|----------|----------|
| `local` (默认) | 项目根 `.claude.json` | 仅当前项目 |
| `user` | `~/.claude.json` | 所有项目 |

---

*记录日期：2026-04-04*
*环境：Claude Code CLI, macOS, Python 3.14, MCP SDK 1.27.0*
