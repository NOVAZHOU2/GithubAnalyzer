# src/github_analyzer.py
import requests
import time
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import csv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ProjectConfig:
    """项目配置类"""
    min_stars: int = 1000
    max_projects: int = 5
    commits_per_project: int = 20
    language: str = "C"
    per_page: int = 100
    sort: str = "stars"
    order: str = "desc"


class GitHubAPI:
    """GitHub API客户端"""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.user_agent = os.getenv("GITHUB_USER_AGENT", "GitHub-Commit-Analyzer")
        self.timeout = int(os.getenv("REQUEST_TIMEOUT", 30))
        self.max_retries = int(os.getenv("MAX_RETRIES", 3))

        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": self.user_agent
        }

        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

        # API 状态跟踪
        self.remaining_requests = 60
        self.reset_time = 0

    def _check_rate_limit(self, response_headers):
        """检查并处理API速率限制"""
        if 'X-RateLimit-Remaining' in response_headers:
            self.remaining_requests = int(response_headers['X-RateLimit-Remaining'])

        if 'X-RateLimit-Reset' in response_headers:
            self.reset_time = int(response_headers['X-RateLimit-Reset'])

        if self.remaining_requests < 10:
            wait_time = max(self.reset_time - int(time.time()), 0) + 5
            if wait_time > 0:
                logger.warning(f"API请求剩余 {self.remaining_requests} 次，等待 {wait_time} 秒")
                time.sleep(wait_time)

    def search_c_projects(self, min_stars: int, max_projects: int = 5) -> List[Dict]:
        """搜索C语言项目"""
        projects = []
        page = 1

        logger.info(f"🔍 搜索C语言项目，最小star数: {min_stars}")

        while len(projects) < max_projects:
            query = f"language:C stars:>={min_stars}"
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": min(100, max_projects - len(projects)),
                "page": page
            }

            try:
                response = requests.get(
                    "https://api.github.com/search/repositories",
                    headers=self.headers,
                    params=params,
                    timeout=self.timeout
                )

                self._check_rate_limit(response.headers)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    for item in items:
                        if len(projects) >= max_projects:
                            break

                        project_info = {
                            "name": item["name"],
                            "full_name": item["full_name"],
                            "owner": item["owner"]["login"],
                            "html_url": item["html_url"],
                            "description": item["description"] or "No description",
                            "stars": item["stargazers_count"],
                            "language": item["language"],
                            "created_at": item["created_at"],
                            "updated_at": item["updated_at"]
                        }
                        projects.append(project_info)

                        logger.info(f"📦 找到项目: {item['full_name']} (⭐ {item['stargazers_count']})")

                elif response.status_code == 403:
                    logger.error("API请求被限制，请稍后重试或添加GitHub Token")
                    break
                else:
                    logger.error(f"搜索失败: {response.status_code}")
                    break

            except Exception as e:
                logger.error(f"请求异常: {e}")
                break

            page += 1
            time.sleep(1)  # 避免过快请求

        logger.info(f"✅ 共找到 {len(projects)} 个项目")
        return projects

    def get_commits(self, owner: str, repo: str, max_commits: int = 20) -> List[Dict]:
        """获取项目的commits - 类似图片中的格式"""
        commits = []
        page = 1

        logger.info(f"📄 获取 {owner}/{repo} 的提交记录...")

        while len(commits) < max_commits:
            url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            params = {
                "per_page": min(100, max_commits - len(commits)),
                "page": page
            }

            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=self.timeout
                )

                self._check_rate_limit(response.headers)

                if response.status_code == 200:
                    commit_data = response.json()

                    for commit_item in commit_data:
                        if len(commits) >= max_commits:
                            break

                        # 只获取需要的字段，类似图片中的格式
                        commit_info = {
                            "sha_short": commit_item["sha"][:7],
                            "message": commit_item["commit"]["message"],
                            "author_name": commit_item["commit"]["author"]["name"],
                            "author_date": commit_item["commit"]["author"]["date"],
                            "html_url": commit_item["html_url"]
                        }
                        commits.append(commit_info)

                        # 显示进度
                        if len(commits) % 10 == 0:
                            logger.info(f"  已获取 {len(commits)} 条提交记录")

                elif response.status_code == 404:
                    logger.warning(f"仓库不存在或无法访问: {owner}/{repo}")
                    break
                elif response.status_code == 409:  # 空仓库
                    logger.warning(f"仓库 {owner}/{repo} 为空")
                    break
                else:
                    logger.error(f"获取提交失败: {response.status_code}")
                    break

            except Exception as e:
                logger.error(f"请求异常: {e}")
                break

            page += 1
            time.sleep(0.5)  # 避免过快请求

        logger.info(f"✅ 获取到 {len(commits)} 条提交记录")
        return commits

    def get_commit_details(self, owner: str, repo: str, sha: str) -> Optional[Dict]:
        """获取单个commit的详细信息"""
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"

        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"获取commit详情失败: {e}")

        return None


class CommitAnalyzer:
    """Commit分析器"""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.github = GitHubAPI()
        self.projects = []
        self.project_commits = {}  # 项目名 -> commits列表

    def run(self):
        """运行分析"""
        print("=" * 60)
        print("GitHub C项目提交分析工具")
        print("=" * 60)

        # 1. 搜索项目
        self.projects = self.github.search_c_projects(
            min_stars=self.config.min_stars,
            max_projects=self.config.max_projects
        )

        if not self.projects:
            logger.error("未找到符合条件的项目")
            return

        # 保存项目信息
        self.save_projects_csv()

        # 2. 获取每个项目的commits
        for i, project in enumerate(self.projects, 1):
            print(f"\n[{i}/{len(self.projects)}] 分析项目: {project['full_name']}")

            commits = self.github.get_commits(
                owner=project["owner"],
                repo=project["name"],
                max_commits=self.config.commits_per_project
            )

            if commits:
                self.project_commits[project["full_name"]] = {
                    "project": project,
                    "commits": commits
                }

                # 保存每个项目的数据
                self.save_project_commits_csv(project, commits)

        # 3. 保存合并的表格
        if self.project_commits:
            self.save_combined_table()

        self.print_summary()

    def save_projects_csv(self, filename: str = "projects.csv"):
        """保存项目信息到CSV"""
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["序号", "项目名称", "项目URL", "Star数", "描述", "创建时间", "更新时间"])

            for i, project in enumerate(self.projects, 1):
                writer.writerow([
                    i,
                    project["full_name"],
                    project["html_url"],
                    project["stars"],
                    project["description"],
                    project["created_at"],
                    project["updated_at"]
                ])

        logger.info(f"✅ 项目列表已保存到 {filename}")

    def save_project_commits_csv(self, project: Dict, commits: List[Dict], filename: str = None):
        """保存单个项目的commits到CSV"""
        if not filename:
            safe_name = project["full_name"].replace("/", "_")
            filename = f"{safe_name}_commits.csv"

        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["项目名称", "项目URL", "提交ID", "提交者", "提交时间", "提交信息", "提交链接"])

            for commit in commits:
                writer.writerow([
                    project["full_name"],
                    project["html_url"],
                    commit["sha_short"],
                    commit["author_name"],
                    commit["author_date"],
                    commit["message"].replace('\n', ' '),  # 移除换行符
                    commit["html_url"]
                ])

        logger.info(f"📁 提交记录已保存到 {filename}")

    def save_combined_table(self, filename: str = "all_commits.csv"):
        """保存合并表格 - 按照图片格式"""
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["项目名称+URL", "提交时间", "Commit标题", "Commit URL"])

            for project_full_name, data in self.project_commits.items():
                project = data["project"]
                commits = data["commits"]

                for commit in commits:
                    # 格式化时间（类似图片中的"2 hours ago"格式）
                    time_str = self.format_relative_time(commit["author_date"])

                    # 获取commit标题（第一行）
                    message_lines = commit["message"].split('\n')
                    commit_title = message_lines[0] if message_lines else ""

                    writer.writerow([
                        f"{project['full_name']} ({project['html_url']})",
                        f"{commit['author_name']} committed {time_str}",
                        commit_title,
                        commit["html_url"]
                    ])

        logger.info(f"✅ 合并表格已保存到 {filename}")

        # 同时保存为Markdown格式，更易读
        self.save_markdown_table("all_commits.md")

    def save_markdown_table(self, filename: str = "all_commits.md"):
        """保存为Markdown表格格式"""
        with open(filename, 'w', encoding='utf-8-sig') as f:
            f.write("# GitHub C项目提交记录\n\n")
            f.write("> 生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n")

            for project_full_name, data in self.project_commits.items():
                project = data["project"]
                commits = data["commits"]

                f.write(f"## {project['full_name']}\n")
                f.write(f"- **URL**: {project['html_url']}\n")
                f.write(f"- **Star数**: {project['stars']}\n")
                f.write(f"- **提交记录数**: {len(commits)}\n\n")

                f.write("| 提交时间 | 提交者 | Commit标题 | 链接 |\n")
                f.write("|----------|--------|------------|------|\n")

                for commit in commits:
                    time_str = self.format_relative_time(commit["author_date"])
                    message_lines = commit["message"].split('\n')
                    commit_title = message_lines[0] if message_lines else ""

                    # 缩短过长的标题
                    if len(commit_title) > 80:
                        commit_title = commit_title[:77] + "..."

                    f.write(
                        f"| {time_str} | {commit['author_name']} | {commit_title} | [查看]({commit['html_url']}) |\n")

                f.write("\n---\n\n")

        logger.info(f"📄 Markdown格式已保存到 {filename}")

    def format_relative_time(self, iso_time: str) -> str:
        """格式化时间为相对时间（如'2 hours ago'）"""
        try:
            # 解析ISO时间
            commit_dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
            now_dt = datetime.now(commit_dt.tzinfo)

            # 计算时间差
            delta = now_dt - commit_dt

            # 转换为相对时间
            if delta.days > 365:
                years = delta.days // 365
                return f"{years} year{'s' if years > 1 else ''} ago"
            elif delta.days > 30:
                months = delta.days // 30
                return f"{months} month{'s' if months > 1 else ''} ago"
            elif delta.days > 0:
                if delta.days == 1:
                    return "1 day ago"
                else:
                    return f"{delta.days} days ago"
            elif delta.seconds >= 3600:
                hours = delta.seconds // 3600
                if hours == 1:
                    return "1 hour ago"
                else:
                    return f"{hours} hours ago"
            elif delta.seconds >= 60:
                minutes = delta.seconds // 60
                if minutes == 1:
                    return "1 minute ago"
                else:
                    return f"{minutes} minutes ago"
            else:
                return "just now"
        except:
            return iso_time

    def print_summary(self):
        """打印摘要信息"""
        print("\n" + "=" * 60)
        print("分析摘要")
        print("=" * 60)
        print(f"📊 分析完成！")
        print(f"   项目数量: {len(self.projects)}")

        total_commits = sum(len(data["commits"]) for data in self.project_commits.values())
        print(f"   提交记录总数: {total_commits}")

        print(f"\n📁 生成的文件:")
        print(f"   - projects.csv (项目列表)")
        print(f"   - all_commits.csv (合并表格)")
        print(f"   - all_commits.md (Markdown格式)")

        for project_full_name, data in self.project_commits.items():
            safe_name = project_full_name.replace("/", "_")
            print(f"   - {safe_name}_commits.csv")

        print(f"\n📈 项目详情:")
        for i, project in enumerate(self.projects[:5], 1):
            commits = self.project_commits.get(project["full_name"], {}).get("commits", [])
            print(f"{i:2d}. {project['full_name']:<40} ⭐ {project['stars']:<6} 📝 {len(commits)} commits")

        if self.project_commits:
            print(f"\n📋 最近提交示例:")
            for project_full_name, data in list(self.project_commits.items())[:2]:
                project = data["project"]
                commits = data["commits"][:2] if len(data["commits"]) >= 2 else data["commits"]

                print(f"\n项目: {project['full_name']}")
                print("-" * 80)
                for commit in commits:
                    time_str = self.format_relative_time(commit["author_date"])
                    message_lines = commit["message"].split('\n')
                    title = message_lines[0] if message_lines else ""

                    if len(title) > 80:
                        title = title[:77] + "..."

                    print(f"  [{time_str}] {commit['author_name']}: {title}")