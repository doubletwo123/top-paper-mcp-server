# Top Paper MCP Server

[![PyPI Version](https://img.shields.io/pypi/v/top-paper-mcp-server.svg)](https://pypi.org/project/top-paper-mcp-server/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/top-paper-mcp-server.svg)](https://pypi.org/project/top-paper-mcp-server/)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

> 🔍 通过简单的 MCP 接口帮助 AI 助手搜索和获取来自 arXiv 及顶级学术会议的论文。

Top Paper MCP Server 搭建了 AI 助手与学术研究资源（arXiv、CVPR、NeurIPS、ICLR、ICML 等）之间的桥梁，通过模型上下文协议（MCP）实现论文搜索和内容获取的编程方式访问。

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
- 🔎 **会议搜索**：搜索顶级 AI/ML/CV/NLP 会议的论文：
  - **CVF**：CVPR、ICCV、WACV
  - **ECVA**：ECCV
  - **OpenReview**：ICLR、NeurIPS、ICML、AAAI、IJCAI、ACL、EMNLP、NAACL、COLM、CoRL、MLSYS、MICCAI、IWSLT、INTERSPEECH
  - **ML Anthology**：COLT、UAI
  - **ACM**：ACM 数字图书馆（SIGGRAPH、CHI、KDD 等）
- 📄 **论文下载**：从会议网站下载论文
- 📝 **提示词**：论文分析研究提示

## 支持的会议

| 会议 | 数据来源 | 年份范围 |
|------------|-------------|------------|
| **计算机视觉** |
| CVPR | CVF Open Access | 2000-至今 |
| ICCV | CVF Open Access | 2000-至今 |
| WACV | CVF Open Access | 2000-至今 |
| ECCV | ECVA | 2000-至今 |
| **机器学习 / 人工智能** |
| ICLR | OpenReview API | 2000-至今 |
| NeurIPS | OpenReview API | 2000-至今 |
| ICML | OpenReview API | 2000-至今 |
| AAAI | OpenReview API | 2000-至今 |
| IJCAI | OpenReview API | 2000-至今 |
| COLM | OpenReview API | 2000-至今 |
| CoRL | OpenReview API | 2000-至今 |
| MLSYS | OpenReview API | 2020-至今 |
| **自然语言处理** |
| ACL | OpenReview API | 2000-至今 |
| EMNLP | OpenReview API | 2000-至今 |
| NAACL | OpenReview API | 2000-至今 |
| **语音 / 多模态** |
| INTERSPEECH | OpenReview API | 2000-至今 |
| IWSLT | OpenReview API | 2000-至今 |
| MICCAI | OpenReview API | 2000-至今 |
| **理论** |
| COLT | ML Anthology | 2000-至今 |
| UAI | ML Anthology | 2000-至今 |
| **其他** |
| ACM | ACM Digital Library | 不等 |

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
# 搜索单个会议
result = await call_tool("conference_search", {
    "query": "object detection",
    "conference": "CVPR",
    "year": 2024,
    "max_results": 10
})

# 多会议并发搜索 (新增！)
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

# 下载会议论文
result = await call_tool("conference_download", {
    "paper_id": "12345",
    "conference": "CVPR",
    "year": 2024
})
```

#### 多线程并发搜索功能

- **并发执行**：使用 asyncio 并行搜索多个会议
- **优先级排序**：按会议优先级排序结果 (CVPR > NeurIPS > ICLR > ICML > ...)
- **领域筛选**：按领域筛选 (computer_vision, machine_learning, nlp, ai, speech, medical, theory)
- **结果聚合**：合并和去重来自多个数据源的结果
- **流量限制**：内置信号量限制并发请求数（最多10个），防止API限流
- **超时保护**：单个请求30秒超时，防止慢速端点阻塞整体
- **自动重试**：失败请求自动重试最多2次，指数退避
- **错误恢复**：部分失败时仍返回成功的搜索结果

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