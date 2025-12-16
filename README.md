# GitHub C项目提交分析工具

![GitHub](https://img.shields.io/badge/Language-Python-blue)
![GitHub](https://img.shields.io/badge/API-GitHub-violet)

## 🚀 功能描述

1. 通过GitHub API搜索指定star数的C语言大型项目
2. 分析项目的commit历史记录
3. 提取关键提交信息（功能更新/缺陷修复/性能优化等）

## ⚙️ 安装与配置

### 前置要求
- Python 3.8+
- GitHub账号（需准备[Personal Access Token](https://github.com/settings/tokens) , 请在.env中输入自己的 Token,否则会触发401错误）
- ChatGPT API KEY 用于进行 bug 类型的分析

### 安装依赖

- pip install -r requirements.txt5

### 使用教程

- 可以修改 main.py 中的参数，调整项目筛选的 star 和 commit 的数量
- 运行 main.py 后，可在 results 文件夹中获取爬取的 csv 文件，包括每个项目的数据以及合并之后的数据

# 项目常见Bug类型分类表

| 大类 | 子类 | 具体类型 | 关键词示例 |
|------|------|----------|------------|
| **内存安全** | 内存泄漏 | Memory Leak | `memory leak`, `free`, `malloc`, `alloc` |
| | 缓冲区溢出 | Buffer Overflow | `buffer overflow`, `out of bounds`, `OOB` |
| | 野指针 | Dangling Pointer | `dangling pointer`, `use after free` |
| **并发安全** | 竞态条件 | Race Condition | `race condition`, `data race` |
| | 死锁 | Deadlock | `deadlock`, `lock order` |
| **系统错误** | 空指针解引用 | Null Pointer Dereference | `null pointer`, `NULL`, `segfault` |
| | 资源泄漏 | Resource Leak | `fd leak`, `resource leak`, `handle leak` |
| **逻辑错误** | 条件判断错误 | Condition Error | `if condition`, `logic error` |
| | 循环边界错误 | Loop Boundary | `off-by-one`, `loop boundary` |
| | 整数溢出 | Integer Overflow | `integer overflow`, `wrap` |
| **安全漏洞** | 格式化字符串 | Format String | `format string`, `printf` |
| | 输入验证 | Input Validation | `input validation`, `sanitize` |
| **性能问题** | 算法效率 | Algorithm Efficiency | `performance`, `optimize`, `O(n^2)` |
| **其他** | 配置错误 | Configuration Error | `config`, `setting`, `parameter` |
| | 非Bug修复 | Non-Bug Fix | `refactor`, `cleanup`, `style`, `doc` |

## 使用说明

此表格用于GPT API分析C语言项目commit消息中的bug类型。每个commit消息将被分类到上述类型之一，如果没有修复bug则标记为"非Bug修复"。