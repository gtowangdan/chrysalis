# Chrysalis - AI Agent 技能自进化引擎

## 核心设计原则
- **只做闭环**：执行→录制→分析→进化→存储→注入，其他全砍
- **零依赖优先**：能用标准库就不引外部包
- **MCP-first**：通过 MCP 协议接入 Claude Code / Codex / 任意 Agent

## 架构（极简）

```
chrysalis/
├── src/chrysalis/
│   ├── core/
│   │   ├── skill.py        # Skill 数据模型 + SKILL.md 读写
│   │   └── store.py        # SQLite 持久化 + 版本追踪
│   ├── evolution/
│   │   ├── analyzer.py     # 执行录制分析，产出进化建议
│   │   └── evolver.py      # 用 LLM 执行技能进化
│   └── mcp/
│       └── server.py       # MCP Server（4个工具）
├── pyproject.toml
└── README.md
```

共 5 个核心文件 + 项目配置，不多一个。

## 实施计划

### Phase 1: 骨架搭建
- [ ] 1. 项目配置（pyproject.toml, __init__.py）
- [ ] 2. Skill 数据模型 + SKILL.md 格式解析/写入
- [ ] 3. SQLite Store（技能 CRUD + 版本追踪 + 质量指标）
- [ ] 4. Analyzer（分析执行录制，产出进化建议）
- [ ] 5. Evolver（FIX + CAPTURED 两种进化）
- [ ] 6. MCP Server（execute_task / search_skills / evolve_skill）
- [ ] 7. README + 使用说明

### 砍掉的东西（未来按需加）
- ❌ BM25 + Embedding 混合检索（先用简单关键词匹配）
- ❌ 云社区功能
- ❌ 工具退化检测
- ❌ 定期健康检查
- ❌ Prompt injection 安全检查
- ❌ 多格式 Patch（FULL/DIFF/PATCH）
- ❌ 复杂版本 DAG（用简单 parent_id）
