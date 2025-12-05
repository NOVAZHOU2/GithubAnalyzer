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

    def get_project_total_commits(self, owner: str, repo: str) -> int:
        """获取项目的总commit数"""
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                return data.get("size", 0)  # 仓库大小可以作为参考
        except Exception as e:
            logger.warning(f"获取项目{owner}/{repo}信息失败: {e}")

        return 0  # 如果无法获取，返回0

    def get_commits(self, owner: str, repo: str, max_commits: int = 20) -> List[Dict]:
        """获取项目的commits - 类似图片中的格式"""
        commits = []
        page = 1
        total_commits_obtained = 0
        max_attempts = 10  # 最大尝试页数，防止无限循环

        logger.info(f"📄 获取 {owner}/{repo} 的提交记录，期望获取 {max_commits} 条...")

        # 先获取项目的总commit数（估算）
        total_commits_estimate = self.get_project_total_commits(owner, repo)
        if total_commits_estimate > 0:
            logger.info(f"📊 项目 {owner}/{repo} 预计有 {total_commits_estimate} 条commit")
            # 如果总commit数小于请求数，则调整max_commits
            if total_commits_estimate < max_commits:
                max_commits = total_commits_estimate
                logger.info(f"🔧 调整获取数量为: {max_commits} 条")

        attempts = 0
        while len(commits) < max_commits and attempts < max_attempts:
            per_page = min(100, max_commits - len(commits))
            url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            params = {
                "per_page": per_page,
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

                    # 如果没有数据了，说明已经获取了所有commit
                    if not commit_data:
                        logger.info(f"📭 已获取所有可用commit，共 {len(commits)} 条")
                        break

                    current_batch_count = 0
                    for commit_item in commit_data:
                        if len(commits) >= max_commits:
                            break

                        # 只获取需要的字段，类似图片中的格式
                        commit_info = {
                            "sha_short": commit_item["sha"][:7],
                            "message": commit_item["commit"]["message"],
                            "title": self._extract_commit_title(commit_item["commit"]["message"]),
                            "author_name": commit_item["commit"]["author"]["name"],
                            "author_date": commit_item["commit"]["author"]["date"],
                            "html_url": commit_item["html_url"]
                        }
                        commits.append(commit_info)
                        current_batch_count += 1

                    total_commits_obtained += current_batch_count

                    # 显示进度
                    if len(commits) % 10 == 0 or current_batch_count < per_page:
                        logger.info(f"  已获取 {len(commits)} 条提交记录")

                    # 如果这一批数据量小于请求的per_page，说明没有更多数据了
                    if current_batch_count < per_page:
                        logger.info(f"📭 已获取所有可用commit，共 {len(commits)} 条")
                        break

                elif response.status_code == 404:
                    logger.warning(f"仓库不存在或无法访问: {owner}/{repo}")
                    break
                elif response.status_code == 409:  # 空仓库
                    logger.warning(f"仓库 {owner}/{repo} 为空")
                    break
                elif response.status_code == 422:  # 分页超出范围
                    logger.info(f"📭 已获取所有commit，共 {len(commits)} 条")
                    break
                else:
                    logger.error(f"获取提交失败: {response.status_code}")
                    break

            except Exception as e:
                logger.error(f"请求异常: {e}")
                break

            page += 1
            attempts += 1
            time.sleep(0.5)  # 避免过快请求

        # 最终检查：如果实际获取的commit数小于请求数，给出提示
        if len(commits) < max_commits:
            logger.info(f"📊 实际获取 {len(commits)} 条commit（小于请求的 {max_commits} 条）")

        logger.info(f"✅ 最终获取到 {len(commits)} 条提交记录")
        return commits

    def _extract_commit_title(self, message: str) -> str:
        """提取commit标题（第一行）"""
        lines = message.split('\n')
        if lines:
            return lines[0].strip()
        return message

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

    def __init__(self, config: ProjectConfig, output_dir: str = "output"):
        """初始化分析器，指定输出目录"""
        self.config = config
        self.github = GitHubAPI()
        self.projects = []
        self.project_commits = {}  # 项目名 -> commits列表
        self.output_dir = output_dir

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"📁 输出目录设置为: {os.path.abspath(self.output_dir)}")

    def _get_output_path(self, filename: str) -> str:
        """获取输出文件的完整路径"""
        return os.path.join(self.output_dir, filename)

    def run(self):
        """运行分析"""
        print("=" * 60)
        print("GitHub C项目提交分析工具")
        print("=" * 60)
        print(f"输出目录: {os.path.abspath(self.output_dir)}")
        print()

        # 1. 搜索项目
        self.projects = self.github.search_c_projects(
            min_stars=self.config.min_stars,
            max_projects=self.config.max_projects
        )

        if not self.projects:
            logger.error("未找到符合条件的项目")
            return

        # 保存项目信息到output目录
        self.save_projects_csv()

        # 2. 获取每个项目的commits
        total_expected_commits = 0
        total_actual_commits = 0

        for i, project in enumerate(self.projects, 1):
            print(f"\n[{i}/{len(self.projects)}] 分析项目: {project['full_name']}")

            # 获取commits
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

                # 统计commit数量
                expected = self.config.commits_per_project
                actual = len(commits)
                total_expected_commits += expected
                total_actual_commits += actual

                # 显示获取情况
                if actual < expected:
                    print(f"   📊 获取情况: {actual}/{expected} 条commit")
                else:
                    print(f"   ✅ 成功获取: {actual} 条commit")

                # 保存每个项目的数据到output目录
                self.save_project_commits_csv(project, commits)

        # 3. 保存合并的表格到output目录
        if self.project_commits:
            # 保存为类似图片的格式
            self.save_picture_format_csv()
            # 保存为合并表格
            self.save_combined_table()
            # 保存为Markdown格式
            self.save_markdown_table()

        # 显示最终统计
        self.print_summary(total_expected_commits, total_actual_commits)

    def save_projects_csv(self, filename: str = "projects.csv"):
        """保存项目信息到CSV（在output目录下）"""
        filepath = self._get_output_path(filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
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

        logger.info(f"✅ 项目列表已保存到 {filepath}")

    def save_project_commits_csv(self, project: Dict, commits: List[Dict], filename: str = None):
        """保存单个项目的commits到CSV（在output目录下）"""
        if not filename:
            safe_name = project["full_name"].replace("/", "_").replace("\\", "_")
            filename = f"{safe_name}_commits.csv"

        filepath = self._get_output_path(filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
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

        logger.info(f"📁 提交记录已保存到 {filepath}")
        return filepath

    def save_picture_format_csv(self, filename: str = "commits_picture_format.csv"):
        """保存为图片中的格式（在output目录下）"""
        filepath = self._get_output_path(filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # 图片中的表格格式
            writer.writerow(["Commit标题", "作者和时间", "Commit链接"])

            all_commits = []
            for project_full_name, data in self.project_commits.items():
                project = data["project"]
                commits = data["commits"]

                for commit in commits:
                    # 格式化时间（类似图片中的"2 hours ago"格式）
                    time_str = self.format_relative_time(commit["author_date"])
                    author_time = f"{commit['author_name']} committed {time_str}"

                    all_commits.append({
                        "title": commit["title"],
                        "author_time": author_time,
                        "url": commit["html_url"]
                    })

            # 按照时间倒序排序（最新的在前面）
            all_commits.sort(key=lambda x: x["author_time"], reverse=True)

            for commit in all_commits:
                writer.writerow([
                    commit["title"],
                    commit["author_time"],
                    commit["url"]
                ])

        logger.info(f"🖼️ 图片格式表格已保存到 {filepath}")
        return filepath

    def save_combined_table(self, filename: str = "all_commits.csv"):
        """保存合并表格（在output目录下）"""
        filepath = self._get_output_path(filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["项目名称+URL", "提交时间", "Commit标题", "Commit URL"])

            for project_full_name, data in self.project_commits.items():
                project = data["project"]
                commits = data["commits"]

                for commit in commits:
                    # 格式化时间（类似图片中的"2 hours ago"格式）
                    time_str = self.format_relative_time(commit["author_date"])

                    writer.writerow([
                        f"{project['full_name']} ({project['html_url']})",
                        f"{commit['author_name']} committed {time_str}",
                        commit["title"],
                        commit["html_url"]
                    ])

        logger.info(f"✅ 合并表格已保存到 {filepath}")
        return filepath

    def save_markdown_table(self, filename: str = "all_commits.md"):
        """保存为Markdown表格格式（在output目录下）"""
        filepath = self._get_output_path(filename)

        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write("# GitHub C项目提交记录\n\n")
            f.write("> 生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n")
            f.write("> 输出目录: " + os.path.abspath(self.output_dir) + "\n\n")

            for project_full_name, data in self.project_commits.items():
                project = data["project"]
                commits = data["commits"]

                f.write(f"## {project['full_name']}\n")
                f.write(f"- **项目URL**: {project['html_url']}\n")
                f.write(f"- **Star数**: {project['stars']}\n")
                f.write(f"- **提交记录数**: {len(commits)}\n\n")

                f.write("| Commit标题 | 提交者 | 提交时间 | 链接 |\n")
                f.write("|------------|--------|----------|------|\n")

                for commit in commits:
                    time_str = self.format_relative_time(commit["author_date"])
                    commit_title = commit["title"]

                    # 缩短过长的标题
                    if len(commit_title) > 100:
                        commit_title = commit_title[:97] + "..."

                    f.write(
                        f"| {commit_title} | {commit['author_name']} | {time_str} | [查看]({commit['html_url']}) |\n")

                f.write("\n---\n\n")

        logger.info(f"📄 Markdown格式已保存到 {filepath}")
        return filepath

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

    def print_summary(self, total_expected: int, total_actual: int):
        """打印摘要信息"""
        print("\n" + "=" * 60)
        print("分析摘要")
        print("=" * 60)
        print(f"📊 分析完成！")
        print(f"  项目数量: {len(self.projects)}")

        print(f"   📈 Commit获取统计:")
        print(f"     期望获取: {total_expected} 条")
        print(f"     实际获取: {total_actual} 条")

        if total_actual < total_expected:
            print(f"     ⚠️  实际获取少于期望值")
        else:
            print(f"     ✅ 成功获取所有期望的commit")

        print(f"\n📁 输出目录: {os.path.abspath(self.output_dir)}")
        print(f"\n📁 生成的文件:")

        # 列出output目录下的文件
        for filename in os.listdir(self.output_dir):
            if filename.endswith(('.csv', '.md')):
                filepath = os.path.join(self.output_dir, filename)
                size = os.path.getsize(filepath)
                print(f"   - {filename} ({size} bytes)")

        print(f"\n📈 项目详情:")
        for i, project in enumerate(self.projects[:5], 1):
            commits = self.project_commits.get(project["full_name"], {}).get("commits", [])
            expected = self.config.commits_per_project
            actual = len(commits)
            status = "✅" if actual >= expected else "⚠️"
            print(f"{i:2d}. {project['full_name']:<30} ⭐ {project['stars']:<6} {status} {actual}/{expected} commits")

        if self.project_commits:
            print(f"\n📋 最近提交示例（图片格式）:")
            for project_full_name, data in list(self.project_commits.items())[:1]:
                commits = data["commits"][:2] if len(data["commits"]) >= 2 else data["commits"]

                for commit in commits:
                    time_str = self.format_relative_time(commit["author_date"])
                    author_time = f"{commit['author_name']} committed {time_str}"
                    title = commit["title"]

                    if len(title) > 80:
                        title = title[:77] + "..."

                    print(f"\n{title}")
                    print(f"{author_time}")
                    print(f"{commit['html_url']}")