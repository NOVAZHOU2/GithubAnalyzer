# config.py
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"

# GitHub API配置
GITHUB_API_URL = "https://api.github.com"
GITHUB_SEARCH_URL = f"{GITHUB_API_URL}/search/repositories"
GITHUB_COMMITS_URL = f"{GITHUB_API_URL}/repos/{{owner}}/{{repo}}/commits"

# 默认配置
DEFAULT_CONFIG = {
    "min_stars": 1000,  # 默认最小star数
    "max_projects": 10,  # 默认最大项目数
    "commits_per_project": 100,  # 每个项目的commit数
    "language": "C",  # 搜索的语言
    "per_page": 100,  # 每页数量
    "sort": "stars",  # 排序方式
    "order": "desc"  # 排序顺序
}

# 确保数据目录存在
DATA_DIR.mkdir(exist_ok=True)