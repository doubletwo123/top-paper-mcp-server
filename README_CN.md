[English](README.md) | **中文**

# Top Paper MCP Server

![Top Paper MCP Server](./figs/logo.png)

> 🔍 通过简单的 MCP 接口帮助 AI 助手搜索和获取来自 arXiv 及 18+ 顶级学术会议的论文。

Top Paper MCP Server 搭建了 AI 助手与学术研究资源之间的桥梁，通过模型上下文协议（MCP）实现论文搜索和内容获取的编程方式访问。

**这是 [arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server) 的分支，保留了完整的 arXiv 功能，并新增了扩展的会议搜索功能。**

<div align="center">

🤝 **[贡献指南](CONTRIBUTING.md)** •
📝 **[报告问题](https://github.com/doubletwo123/top-paper-mcp-server/issues)**

</div>

## ✨ 核心功能

### arXiv 集成
- 🔎 **论文搜索**：按日期范围和类别筛选搜索 arXiv 论文
- 📄 **论文获取**：下载并阅读论文内容
- 📋 **论文列表**：查看已下载的论文
- 🗃️ **本地存储**：论文本地保存以便快速访问

### 会议支持
- 🔎 **双路并行会议搜索**：同时搜索 arXiv 和 OpenReview，然后合并结果——arXiv 提供完整论文内容（摘要、PDF），OpenReview 提供会议元数据
- 📄 **会议论文下载**：通过 OpenReview API 获取元数据，arXiv 管道获取全文
- 📝 **提示词**：论文分析研究提示

### HuggingFace 集成
- 📊 **每日论文**：获取 HuggingFace 社区每日精选的热门论文
- 🪞 **元数据镜像**：当 arXiv API 拥塞时的备选元数据来源（提供标题、摘要、作者、点赞数、AI 摘要、GitHub 链接）

### 智能搜索与学习
- 🧠 **查询扩展**：自动将查询扩展为多个变体并行执行
- 🔗 **RRF 融合**：使用倒数排名融合（Reciprocal Rank Fusion）合并多查询结果
- 📈 **偏好学习**：轻量级强化学习（上下文赌博机），从用户交互中学习哪些扩展词有效
- 🎯 **个性化重排**：随着系统学习您的研究偏好，搜索结果逐步改善

### 相关论文发现
- 🔍 **推荐**：通过 Semantic Scholar 查找与一篇或多篇种子论文相似的论文
- 📚 **引用与参考文献**：发现谁引用了该论文以及它引用了哪些论文
- 🆓 **免费开放**：基础使用无需 API Key

## 支持的会议

所有会议均通过**双路并行**搜索：arXiv（内容）+ OpenReview（会议元数据）同时查询。

| 会议 | arXiv 分类 | 年份范围 |
|------------|---------------|------------|
| **计算机视觉** |
| CVPR | cs.CV | 2000-至今 |
| ICCV | cs.CV | 2000-至今 |
| WACV | cs.CV | 2000-至今 |
| ECCV | cs.CV | 2000-至今 |
| **机器学习 / 人工智能** |
| ICLR | cs.LG, cs.AI, cs.CL | 2000-至今 |
| NeurIPS | cs.LG, cs.AI, cs.CL, stat.ML | 2000-至今 |
| ICML | cs.LG, stat.ML | 2000-至今 |
| AAAI | cs.AI | 2000-至今 |
| IJCAI | cs.AI | 2000-至今 |
| COLM | cs.CL, cs.LG | 2000-至今 |
| CoRL | cs.RO, cs.LG, cs.AI | 2000-至今 |
| MLSYS | cs.LG, cs.DC | 2020-至今 |
| **自然语言处理** |
| ACL | cs.CL | 2000-至今 |
| EMNLP | cs.CL | 2000-至今 |
| NAACL | cs.CL | 2000-至今 |
| **语音 / 多模态** |
| INTERSPEECH | eess.AS, cs.CL | 2000-至今 |
| IWSLT | cs.CL | 2000-至今 |
| MICCAI | cs.CV, eess.IV | 2000-至今 |

## 🚀 快速开始

### 通过 Smithery 安装

```bash
npx -y @smithery/cli install top-paper-mcp-server --client claude
```

### 手动安装

```bash
uv tool install top-paper-mcp-server
```

如需 PDF 支持（较老的论文）：

```bash
uv tool install 'top-paper-mcp-server[pdf]'
```

验证安装：

```bash
top-paper-mcp-server --help
```

### MCP 配置

```json
{
    "mcpServers": {
        "top-paper": {
            "command": "uv",
            "args": [
                "tool",
                "run",
                "top-paper-mcp-server",
                "--storage-path", "/path/to/paper/storage"
            ]
        }
    }
}
```

开发环境配置：

```json
{
    "mcpServers": {
        "top-paper": {
            "command": "uv",
            "args": [
                "--directory",
                "path/to/cloned/top-paper-mcp-server",
                "run",
                "top-paper-mcp-server",
                "--storage-path", "/path/to/paper/storage"
            ]
        }
    }
}
```

### HTTP 传输

```bash
TRANSPORT=http HOST=127.0.0.1 PORT=8080 top-paper-mcp-server --storage-path /path/to/papers
```

然后配置您的 MCP 客户端：

```json
{
    "mcpServers": {
        "top-paper": {
            "type": "http",
            "url": "http://127.0.0.1:8080/mcp"
        }
    }
}
```

## 💡 可用工具

### arXiv 工具

```python
# 搜索 arXiv 论文
result = await call_tool("search_papers", {
    "query": "transformer",
    "max_results": 10,
    "categories": ["cs.LG", "cs.AI"]
})

# 下载论文
result = await call_tool("download_paper", {
    "paper_id": "2401.12345"
})

# 列出已下载论文
result = await call_tool("list_papers", {})

# 读取论文内容
result = await call_tool("read_paper", {
    "paper_id": "2401.12345"
})
```

### 会议工具

```python
# 搜索单个会议（双路并行：arXiv + OpenReview 同时搜索）
result = await call_tool("conference_search", {
    "query": "object detection",
    "conference": "CVPR",
    "year": 2024,
    "max_results": 10
})

# 多会议并发搜索
result = await call_tool("conference_search", {
    "query": "transformer",
    "conference": "NeurIPS",
    "year": 2024,
    "search_all": True,
    "conferences": ["CVPR", "NeurIPS", "ICLR", "ICML"]
})

# 按领域并发搜索
result = await call_tool("conference_search", {
    "query": "attention",
    "conference": "NeurIPS",
    "year": 2024,
    "search_all": True,
    "categories": ["computer_vision", "nlp"]
})

# 跨所有会议统一搜索
result = await call_tool("unified_search", {
    "query": "deep learning",
    "year": 2024,
    "max_results_per_conference": 5,
    "total_results": 20
})

# 下载会议论文（OpenReview API + arXiv 回退）
result = await call_tool("conference_download", {
    "paper_id": "12345",
    "conference": "CVPR"
})
```

#### 双路并行搜索架构

- **双路并行**：每个会议查询同时运行 arXiv 搜索和 OpenReview 搜索
- **结果合并**：按标题匹配合并——OpenReview 论文（带会议元数据）为主，arXiv 独有论文为补充
- **数据增强**：当论文同时存在于两个来源时，结果包含 arXiv 内容（摘要、PDF）加 OpenReview 会议元数据
- **优先级排序**：按会议优先级排序 (CVPR > NeurIPS > ICLR > ICML > ...)
- **领域筛选**：按领域筛选 (computer_vision, machine_learning, nlp, ai, speech, medical, theory)
- **并发执行**：使用 asyncio 信号量（最多10个）并行搜索多个会议
- **超时保护**：单个请求30秒超时
- **自动重试**：失败请求自动重试最多2次，指数退避

### HuggingFace 工具

```python
# 获取 HuggingFace 每日论文（HF 社区精选的热门论文）
result = await call_tool("hf_daily_papers", {
    "date": "2024-01-15",    # 可选，默认为今天
    "max_results": 20        # 可选，默认 20，最大 100
})
```

HuggingFace 集成还提供了 arXiv 论文的元数据镜像——当 arXiv API 拥塞时，可以从 HuggingFace 的论文 API 获取论文元数据（标题、摘要、作者、点赞数、AI 摘要、GitHub 链接）作为备选方案。

### 智能搜索工具

```python
# 智能搜索：自动查询扩展
result = await call_tool("smart_search", {
    "query": "register",
    "conference": "CVPR",     # 可选
    "year": 2025,             # 可选
    "max_results": 10,
    "expand": true            # 启用/禁用扩展（默认：true）
})

# LLM 预扩展查询（让 LLM 生成扩展词）
result = await call_tool("smart_search", {
    "query": "register",
    "queries": [
        "register tokens vision transformer",
        "learnable register tokens",
        "registration point cloud"
    ],
    "conference": "CVPR",
    "year": 2025
})

# 记录反馈以改善未来搜索
await call_tool("record_feedback", {
    "paper_id": "2506.08010",
    "action": "download"      # 或 "read"
})
```

#### 智能搜索架构

- **查询扩展**：生成多个查询变体（原始 + 二元组 + 学术后缀），或接受 LLM 预扩展查询
- **并行执行**：所有扩展查询通过 `asyncio.gather` 并发运行
- **RRF 融合**：使用倒数排名融合合并结果（`score = Σ 1/(k+rank)`, k=20）
- **模糊去重**：通过 Jaccard 词重叠（>0.7）匹配论文，处理标题变体
- **偏好记忆**：在 `~/.top-paper-mcp-server/preferences.json` 中存储词权重
- **奖励信号**：download=1.0, read=2.0 — 通过指数移动平均更新词权重
- **冷启动**：<5 次交互时不重排；20+ 次交互后完整偏好加权
- **探索机制**：10% 随机词选择（ε-贪心）防止信息茧房

### 相关论文工具

```python
# 通过 Semantic Scholar 推荐相似论文
result = await call_tool("related_papers", {
    "paper_id": "2506.08010",     # arXiv ID 或 Semantic Scholar ID
    "mode": "recommendations",    # 默认
    "limit": 10
})

# 查找引用了该论文的论文
result = await call_tool("related_papers", {
    "paper_id": "2506.08010",
    "mode": "citations",
    "limit": 10
})

# 查找该论文引用的论文
result = await call_tool("related_papers", {
    "paper_id": "2506.08010",
    "mode": "references",
    "limit": 10
})

# 多论文推荐（您觉得有用的论文）
result = await call_tool("related_papers", {
    "paper_ids": ["2506.08010", "2505.05892"],
    "negative_paper_ids": ["2501.99999"],  # 您不感兴趣的论文
    "mode": "recommendations"
})
```

使用 **Semantic Scholar API** — 免费，基础使用无需 API Key。

## ⚙️ 配置

| 设置 | 用途 | 默认值 |
|---------|---------|---------|
| `--storage-path` | 论文存储位置 | `~/.top-paper-mcp-server/papers` |
| `MAX_RESULTS` | 最大搜索结果数 | `50` |
| `REQUEST_TIMEOUT` | API 超时时间（秒） | `60` |
| `TRANSPORT` | 传输类型：`stdio`、`http` | `stdio` |
| `HOST` | HTTP 模式绑定地址 | `127.0.0.1` |
| `PORT` | HTTP 模式监听端口 | `8000` |

## 🔒 安全

**从外部来源获取的论文内容是不可信的输入。**

当 AI 助手通过此服务器下载或阅读论文时，论文文本直接传入模型上下文。恶意构造的论文可能嵌入对抗性指令，企图劫持 AI 行为。

### 建议的防护措施

1. 尽可能使用只读 MCP 配置
2. 在根据 AI 摘要采取行动前审查论文内容
3. 在多工具设置中保持谨慎
4. 将 AI 生成的摘要视为数据而非指令

## 🧪 测试

```bash
python -m pytest
```

## 🗺️ 路线图

### ✅ 已完成
- arXiv 论文搜索、下载与阅读
- 双路并行会议搜索（arXiv + OpenReview）支持 18+ 顶级会议
- HuggingFace 每日论文与元数据镜像
- 智能搜索：查询扩展与 RRF 融合
- 轻量级强化学习偏好学习（上下文赌博机）
- 通过 Semantic Scholar 发现相关论文（推荐、引用、参考文献）

### 🔬 计划中
- **查询缓存**：基于 SQLite 的搜索结果缓存（24-72 小时 TTL），加速重复查询
- **反馈循环增强**：基于会话行为的被动奖励信号（阅读时长、引用模式）
- **Connected Papers 集成**：基于图的论文关系可视化（需要 API Key）

### 💡 强化学习设计原则
- 不引入大模型——仅使用轻量级向量运算
- 不需要 GPU——所有计算均可在 CPU 上完成
- 不需要训练数据——从用户实时交互中学习
- 存储：单个 JSON 文件（~KB 级别）
- 学术搜索的维度较低（~100 个关键词特征）——加权平均已足够
- 用户的研究偏好具有稳定性（CV 研究者始终关注 CV）——指数衰减自然处理兴趣漂移

## 📄 许可证

根据 Apache License 2.0 发布。详见 LICENSE 文件。

---

## 🙏 致谢

本项目是 **[arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server)** (由 **[Joseph Blazick](https://github.com/blazickjp)** 创建) 的分支，由 **doubletwo123** 添加了额外的功能和对更多会议的支持。

衷心感谢：
- **Joseph Blazick** 创建了原始的 arxiv-mcp-server 并使其开源
- **arXiv** 团队提供开放的学术研究资源库
- **OpenReview** 提供开放的同行评审访问
- **CVF/ECVA** 提供计算机视觉会议的开放获取论文
- 所有使论文公开可访问的会议组织者

本项目在保持与现有 arXiv 功能兼容的同时，扩展支持更多顶级学术会议。

---

<div align="center">

用 ❤️ 为学术研究打造

</div>
