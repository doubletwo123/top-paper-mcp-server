[English](README.md) | **中文**

# Top Paper MCP Server

![Top Paper MCP Server](./figs/logo.png)

> 🔍 通过简单的 MCP 接口帮助 AI 助手搜索和获取来自 arXiv 及顶级学术会议的论文。

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