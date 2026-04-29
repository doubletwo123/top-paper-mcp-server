[![PyPI Version](https://img.shields.io/pypi/v/top-paper-mcp-server.svg)](https://pypi.org/project/top-paper-mcp-server/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/top-paper-mcp-server.svg)](https://pypi.org/project/top-paper-mcp-server/)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# Top Paper MCP Server

> 🔍 Enable AI assistants to search and access academic papers from arXiv and top conferences through a simple MCP interface.

The Top Paper MCP Server provides a bridge between AI assistants and academic research repositories (arXiv, CVPR, NeurIPS, ICLR, ICML, etc.) through the Model Context Protocol (MCP). It allows AI models to search for papers and access their content in a programmatic way.

<div align="center">
  
🤝 **[Contribute](CONTRIBUTING.md)** • 
📝 **[Report Bug](https://github.com/doubletwo123/top-paper-mcp-server/issues)**

</div>

## ✨ Core Features

### arXiv Integration
- 🔎 **Paper Search**: Query arXiv papers with filters for date ranges and categories
- 📄 **Paper Access**: Download and read paper content
- 📋 **Paper Listing**: View all downloaded papers
- 🗃️ **Local Storage**: Papers are saved locally for faster access

### Conference Support
- 🔎 **Conference Search**: Search papers from top AI/ML/CV/NLP conferences:
  - **CVF**: CVPR, ICCV, WACV
  - **ECVA**: ECCV
  - **OpenReview**: ICLR, NeurIPS, ICML, AAAI, IJCAI, ACL, EMNLP, NAACL, COLM, CoRL, MLSYS, MICCAI, IWSLT, INTERSPEECH
  - **ML Anthology**: COLT, UAI
  - **ACM**: ACM Digital Library (SIGGRAPH, CHI, KDD, etc.)
- 📄 **Paper Download**: Download papers from conference websites
- 📝 **Prompts**: Research prompts for paper analysis

## Supported Conferences

| Conference | Data Source | Year Range |
|------------|-------------|------------|
| **Computer Vision** |
| CVPR | CVF Open Access | 2000-present |
| ICCV | CVF Open Access | 2000-present |
| WACV | CVF Open Access | 2000-present |
| ECCV | ECVA | 2000-present |
| **Machine Learning / AI** |
| ICLR | OpenReview API | 2000-present |
| NeurIPS | OpenReview API | 2000-present |
| ICML | OpenReview API | 2000-present |
| AAAI | OpenReview API | 2000-present |
| IJCAI | OpenReview API | 2000-present |
| COLM | OpenReview API | 2000-present |
| CoRL | OpenReview API | 2000-present |
| MLSYS | OpenReview API | 2020-present |
| **NLP** |
| ACL | OpenReview API | 2000-present |
| EMNLP | OpenReview API | 2000-present |
| NAACL | OpenReview API | 2000-present |
| **Speech / Multimodal** |
| INTERSPEECH | OpenReview API | 2000-present |
| IWSLT | OpenReview API | 2000-present |
| MICCAI | OpenReview API | 2000-present |
| **Theory** |
| COLT | ML Anthology | 2000-present |
| UAI | ML Anthology | 2000-present |
| **Other** |
| ACM | ACM Digital Library | Varies |

## 🚀 Quick Start

### Installing via Smithery

```bash
npx -y @smithery/cli install top-paper-mcp-server --client claude
```

### Manual Installation

```bash
uv tool install top-paper-mcp-server
```

For PDF support (older papers):

```bash
uv tool install 'top-paper-mcp-server[pdf]'
```

Verify installation:

```bash
top-paper-mcp-server --help
```

### MCP Configuration

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

For development:

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

### HTTP Transport

```bash
TRANSPORT=http HOST=127.0.0.1 PORT=8080 top-paper-mcp-server --storage-path /path/to/papers
```

Then configure your MCP client:

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

## 💡 Available Tools

### arXiv Tools

```python
# Search arXiv papers
result = await call_tool("search_papers", {
    "query": "transformer",
    "max_results": 10,
    "categories": ["cs.LG", "cs.AI"]
})

# Download a paper
result = await call_tool("download_paper", {
    "paper_id": "2401.12345"
})

# List downloaded papers
result = await call_tool("list_papers", {})

# Read paper content
result = await call_tool("read_paper", {
    "paper_id": "2401.12345"
})
```

### Conference Tools

```python
# Search single conference
result = await call_tool("conference_search", {
    "query": "object detection",
    "conference": "CVPR",
    "year": 2024,
    "max_results": 10
})

# Multi-conference concurrent search (NEW!)
result = await call_tool("conference_search", {
    "query": "transformer",
    "conference": "NeurIPS",
    "year": 2024,
    "search_all": True,
    "conferences": ["CVPR", "NeurIPS", "ICLR", "ICML"]
})

# Search by category with concurrent execution
result = await call_tool("conference_search", {
    "query": "attention",
    "conference": "NeurIPS",
    "year": 2024,
    "search_all": True,
    "categories": ["computer_vision", "nlp"]
})

# Unified search across ALL conferences
result = await call_tool("unified_search", {
    "query": "deep learning",
    "year": 2024,
    "max_results_per_conference": 5,
    "total_results": 20
})

# Download conference paper
result = await call_tool("conference_download", {
    "paper_id": "12345",
    "conference": "CVPR",
    "year": 2024
})
```

#### Multi-Threaded Concurrent Search Features

- **Concurrent Execution**: Searches multiple conferences in parallel using asyncio
- **Priority-Based Ordering**: Results sorted by conference priority (CVPR > NeurIPS > ICLR > ICML > ...)
- **Category Filtering**: Filter by domain (computer_vision, machine_learning, nlp, ai, speech, medical, theory)
- **Results Aggregation**: Merges and deduplicates results from multiple sources
- **Rate Limiting**: Built-in semaphore limits concurrent requests (max 10) to prevent API throttling
- **Timeout Protection**: Individual requests timeout after 30 seconds to prevent slow endpoints blocking
- **Automatic Retry**: Failed requests automatically retry up to 2 times with exponential backoff
- **Error Resilience**: Graceful handling of partial failures - successful results still returned

## ⚙️ Configuration

| Setting | Purpose | Default |
|---------|---------|---------|
| `--storage-path` | Paper storage location | `~/.top-paper-mcp-server/papers` |
| `MAX_RESULTS` | Maximum search results | `50` |
| `REQUEST_TIMEOUT` | API timeout in seconds | `60` |
| `TRANSPORT` | Transport type: `stdio`, `http` | `stdio` |
| `HOST` | Host to bind to in HTTP mode | `127.0.0.1` |
| `PORT` | Port to listen on in HTTP mode | `8000` |

## 🔒 Security

**Paper content retrieved from external sources is untrusted input.**

When an AI assistant downloads or reads a paper through this server, the paper's
text is passed directly into the model's context. A maliciously crafted paper
could embed adversarial instructions designed to hijack the AI's behavior.

### Recommended Mitigations

1. Use read-only MCP configurations when possible
2. Review paper content before acting on AI summaries
3. Be cautious in multi-tool setups
4. Treat AI-generated summaries as data, not instructions

## 🧪 Testing

```bash
python -m pytest
```

## 📄 License

Released under the Apache License 2.0. See the LICENSE file for details.

---

## 🙏 Acknowledgments

This project is a fork of **[arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server)** created by **[Joseph Blazick](https://github.com/blazickjp)**, with additional features and conference support added by **doubletwo123**.

We sincerely thank:
- **Joseph Blazick** for creating the original arxiv-mcp-server and making it open source
- The **arXiv** team for providing the open research repository
- **OpenReview** for enabling open access to peer reviews
- **CVF/ECVA** for providing open access to computer vision conference papers
- All the conference organizers who make their papers publicly accessible

This project extends the original work to support additional top academic conferences while maintaining compatibility with the existing arXiv functionality.

---

<div align="center">

Made with ❤️ for academic research

</div>