# Chrysalis

AI Agent 技能自进化引擎。让你的 Claude Code / Codex / 任何 MCP 兼容 Agent 从经验中学习。

```
执行任务 → 录制 → 分析 → 进化技能 → 下次自动注入
   ↑                                      |
   └──────────────────────────────────────┘
```

## 工作原理

Chrysalis 作为 **MCP Server** 运行。宿主 Agent（Claude Code、Codex 等）负责所有推理，Chrysalis 负责记忆。

| 组件 | 角色 |
|------|------|
| **宿主 Agent** | 负责全部推理 —— 分析执行、撰写技能内容 |
| **Chrysalis** | 存储技能、录制执行、追踪版本和质量指标 |

技能是结构化的 Markdown 文件（`SKILL.md`），包含可复用的操作指南。通过两种方式进化：

- **CAPTURE** — 从成功的执行模式中提取全新技能
- **FIX** — 修复/改进表现不佳的已有技能

**不需要额外的本地大模型** —— 谁调用谁就是大脑。

## MCP 工具

| 工具 | 何时使用 |
|------|----------|
| `search_skills` | 任务**之前** —— 查找相关经验 |
| `record_execution` | 任务**之后** —— 保存执行过程 |
| `analyze_executions` | **定期** —— 发现进化机会 |
| `evolve_skills` | **分析之后** —— 应用技能改进 |
| `get_stats` | 查看技能库状态 |

## 安装

```bash
git clone https://github.com/yourusername/chrysalis.git
cd chrysalis
pip install -e .
```

## 配置到 Claude Code

在 `~/.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "chrysalis": {
      "type": "stdio",
      "command": "chrysalis"
    }
  }
}
```

如果使用虚拟环境：

```json
{
  "mcpServers": {
    "chrysalis": {
      "type": "stdio",
      "command": "/path/to/chrysalis/.venv/bin/chrysalis"
    }
  }
}
```

## 数据存储

所有数据存储在 `~/.chrysalis/`：

```
~/.chrysalis/
└── chrysalis.db    # SQLite —— 技能、执行录制、进化历史
```

可通过 `CHRYSALIS_DATA_DIR` 环境变量覆盖路径。

## SKILL.md 格式

```markdown
---
name: deploy nextjs
description: 部署 Next.js 应用到 Vercel
tags: [nextjs, deploy, vercel]
version: 2
origin: fix
parent_id: deploy-nextjs__v1
---

## 步骤
1. 执行 `vercel deploy --prod`
2. 验证部署 URL 返回 200
3. 检查构建日志中的警告
```

## 架构

```
src/chrysalis/
├── core/
│   ├── skill.py        # 技能数据模型 + SKILL.md 解析器
│   └── store.py        # SQLite 持久化 + 版本追踪
├── evolution/
│   ├── analyzer.py     # 为宿主 LLM 构建分析 prompt
│   └── evolver.py      # 执行进化（capture/fix）
└── mcp/
    └── server.py       # MCP Server（5 个工具）
```

5 个文件，一条闭环，零外部 LLM 依赖。

## License

MIT
