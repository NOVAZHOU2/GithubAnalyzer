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

### 安装依赖

- pip install -r requirements.txt

### 使用教程

- 可以修改 main.py 中的参数，调整项目筛选的 star 和 commit 的数量
- 运行 main.py 后，可在 results 文件夹中获取爬取的 csv 文件，包括每个项目的数据以及合并之后的数据
