# src/github_analyzer_fast.py
import pandas as pd
import requests
import time
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import os
from dotenv import load_dotenv
import logging
import csv
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

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
    commits_per_project: int = 300
    language: str = "C"
    per_page: int = 100
    sort: str = "stars"
    order: str = "desc"


class GitHubAPIFast:
    """改进版GitHub API客户端，保持时间顺序"""

    def __init__(self, token: Optional[str] = None, max_workers: int = 5):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.user_agent = os.getenv("GITHUB_USER_AGENT", "GitHub-Commit-Analyzer")
        self.timeout = 20
        self.max_workers = max_workers

        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": self.user_agent
        }

        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def search_c_projects_fast(self, min_stars: int, max_projects: int = 5) -> List[Dict]:
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

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    for item in items:
                        if len(projects) >= max_projects:
                            break

                        projects.append({
                            "name": item["name"],
                            "full_name": item["full_name"],
                            "owner": item["owner"]["login"],
                            "html_url": item["html_url"],
                            "stars": item["stargazers_count"]
                        })

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
            time.sleep(0.3)

        logger.info(f"✅ 共找到 {len(projects)} 个项目")
        return projects

    def get_commits_with_times_batch(self, owner: str, repo: str, max_commits: int = 300) -> List[Dict]:
        """批量获取commits，包含时间信息"""
        commits = []
        page = 1
        per_page = 100

        logger.info(f"📄 获取 {owner}/{repo} 的提交记录（带时间信息）...")

        while len(commits) < max_commits:
            url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            params = {
                "per_page": min(per_page, max_commits - len(commits)),
                "page": page
            }

            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)

                if response.status_code == 200:
                    batch_commits = response.json()
                    if not batch_commits:
                        break

                    for commit_item in batch_commits:
                        if len(commits) >= max_commits:
                            break

                        commit_info = {
                            "sha": commit_item["sha"],
                            "sha_short": commit_item["sha"][:7],
                            "author_date": commit_item["commit"]["author"]["date"],
                            "html_url": commit_item["html_url"]
                        }
                        commits.append(commit_info)

                    logger.info(f"  获取到 {len(commits)}/{max_commits} 个commit（带时间）")

                    if len(batch_commits) < per_page:
                        break
                else:
                    logger.warning(f"获取commit失败: {response.status_code}")
                    break

            except Exception as e:
                logger.error(f"获取commit异常: {e}")
                break

            page += 1
            time.sleep(0.2)

        logger.info(f"✅ 获取到 {len(commits)} 条提交记录（带时间）")
        return commits

    def get_commit_diff_parallel(self, commits_with_time: List[Dict]) -> List[Dict]:
        """并行获取commits的diff行数"""
        results = []

        def get_single_commit_diff(commit_info: Dict) -> Dict:
            """获取单个commit的diff行数"""
            try:
                # 解析owner和repo
                html_url = commit_info.get("html_url", "")
                if html_url and "/commit/" in html_url:
                    # 从URL中提取owner和repo
                    parts = html_url.replace("https://github.com/", "").split("/")
                    if len(parts) >= 3:
                        owner = parts[0]
                        repo = parts[1]
                        sha = commit_info["sha"]

                        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
                        response = requests.get(url, headers=self.headers, timeout=8)

                        if response.status_code == 200:
                            commit_data = response.json()

                            # 计算总变化行数
                            total_changes = 0
                            for file_data in commit_data.get('files', []):
                                total_changes += file_data.get('additions', 0) + file_data.get('deletions', 0)

                            return {
                                "sha": commit_info["sha"],
                                "sha_short": commit_info["sha_short"],
                                "author_date": commit_info["author_date"],
                                "total_changes": total_changes
                            }
            except Exception:
                pass

            # 失败时返回默认值
            return {
                "sha": commit_info.get("sha", ""),
                "sha_short": commit_info.get("sha_short", ""),
                "author_date": commit_info.get("author_date", ""),
                "total_changes": 0
            }

        # 使用线程池并行处理
        logger.info(f"🚀 开始并行获取 {len(commits_with_time)} 个commit的diff行数...")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_commit = {executor.submit(get_single_commit_diff, commit): commit for commit in commits_with_time}

            # 收集结果
            completed = 0
            for future in as_completed(future_to_commit):
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1

                    # 显示进度
                    if completed % 50 == 0 or completed == len(commits_with_time):
                        elapsed = time.time() - start_time
                        speed = completed / elapsed if elapsed > 0 else 0
                        logger.info(f"  ✅ 已处理 {completed}/{len(commits_with_time)} 个commit "
                                    f"(速度: {speed:.1f} 个/秒)")

                except Exception:
                    pass

        total_time = time.time() - start_time
        logger.info(f"✅ 并行获取完成，耗时 {total_time:.1f} 秒，平均 {len(commits_with_time) / total_time:.1f} 个/秒")

        return results

    def get_commits_with_time_and_diff(self, owner: str, repo: str, max_commits: int = 300) -> List[Dict]:
        """获取commits，包含时间和diff行数，并按时间排序"""
        logger.info(f"🕐 获取 {owner}/{repo} 的提交记录（带时间和diff）...")

        # 1. 获取commits和时间信息
        commits_with_time = self.get_commits_with_times_batch(owner, repo, max_commits)

        if not commits_with_time:
            logger.warning(f"无法获取到任何commit")
            return []

        # 2. 并行获取每个commit的diff行数
        commits_with_diff = self.get_commit_diff_parallel(commits_with_time)

        # 3. 按时间倒序排序（最新的在最前面）
        commits_with_diff.sort(key=lambda x: x["author_date"], reverse=True)

        logger.info(f"✅ 最终获取到 {len(commits_with_diff)} 条提交记录（已按时间排序）")

        # 验证排序
        if len(commits_with_diff) >= 2:
            latest = commits_with_diff[0]["author_date"]
            oldest = commits_with_diff[-1]["author_date"]
            logger.info(f"📅 时间范围: {oldest} 到 {latest}")

        return commits_with_diff


class CommitAnalyzerFast:
    """改进版Commit分析器，确保时间顺序"""

    def __init__(self, config: ProjectConfig, output_dir: str = "output_fast", max_workers: int = 8):
        self.config = config
        self.github = GitHubAPIFast(max_workers=max_workers)
        self.projects = []
        self.project_commits = {}
        self.output_dir = output_dir

        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"📁 输出目录设置为: {os.path.abspath(self.output_dir)}")
        logger.info(f"🚀 使用 {max_workers} 个并行工作线程")

    def _get_output_path(self, filename: str) -> str:
        """获取输出文件的完整路径"""
        return os.path.join(self.output_dir, filename)

    def _project_file_exists(self, project: Dict) -> bool:
        """检查项目是否已经存在数据文件"""
        safe_name = project["full_name"].replace("/", "_").replace("\\", "_")
        possible_filenames = [
            f"{safe_name}_commits_with_time.csv",
            f"{safe_name}_commits_with_diff.csv",
            f"{safe_name}_commits.csv",
            f"{safe_name}_commits_fast.csv",
            f"{safe_name}_commits_minimal.csv"
        ]

        for filename in possible_filenames:
            filepath = self._get_output_path(filename)
            if os.path.exists(filepath):
                # 检查文件是否为空
                if os.path.getsize(filepath) > 100:  # 文件大小大于100字节
                    logger.info(f"📁 项目 {project['full_name']} 已有数据文件: {filename}")
                    return True
        return False

    def _get_existing_commits_count(self, project: Dict) -> int:
        """获取已存在数据文件中的commit数量"""
        safe_name = project["full_name"].replace("/", "_").replace("\\", "_")
        possible_filenames = [
            f"{safe_name}_commits_with_time.csv",
            f"{safe_name}_commits_with_diff.csv",
            f"{safe_name}_commits.csv"
        ]

        for filename in possible_filenames:
            filepath = self._get_output_path(filename)
            if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                try:
                    df = pd.read_csv(filepath)
                    return len(df)
                except:
                    continue
        return 0

    def run(self):
        """运行分析，确保时间顺序正确，跳过已存在的项目"""
        print("=" * 60)
        print("GitHub C项目提交分析工具（带时间排序）- 增量爬取")
        print("=" * 60)
        print(f"输出目录: {os.path.abspath(self.output_dir)}")
        print(f"目标项目数: {self.config.max_projects}")
        print(f"每个项目获取commits: {self.config.commits_per_project}")
        print(f"并行工作线程: {self.github.max_workers}")
        print(f"✓ 自动跳过已存在的项目")
        print()

        # 1. 搜索项目
        start_time = time.time()
        self.projects = self.github.search_c_projects_fast(
            min_stars=self.config.min_stars,
            max_projects=self.config.max_projects
        )

        if not self.projects:
            logger.error("未找到符合条件的项目")
            return

        # 2. 过滤已存在的项目
        projects_to_process = []
        existing_projects = []

        for project in self.projects:
            if self._project_file_exists(project):
                existing_projects.append(project)
            else:
                projects_to_process.append(project)

        print(f"\n📊 项目统计:")
        print(f"  找到项目总数: {len(self.projects)}")
        print(f"  已存在项目数: {len(existing_projects)}")
        print(f"  待处理项目数: {len(projects_to_process)}")

        if existing_projects:
            print(f"\n📁 已跳过的项目:")
            for i, project in enumerate(existing_projects[:10], 1):  # 只显示前10个
                commit_count = self._get_existing_commits_count(project)
                print(f"  {i:2d}. {project['full_name']} ({commit_count} commits)")
            if len(existing_projects) > 10:
                print(f"  ... 还有 {len(existing_projects) - 10} 个项目")

        # 3. 获取每个项目的commits（带时间和diff行数）
        total_expected_commits = 0
        total_actual_commits = 0
        processed_count = 0

        for i, project in enumerate(projects_to_process, 1):
            processed_count += 1
            project_individual_start = time.time()
            print(f"\n[{i}/{len(projects_to_process)}] 分析项目: {project['full_name']}")

            # 获取commits（带时间和diff行数，已排序）
            commits = self.github.get_commits_with_time_and_diff(
                owner=project["owner"],
                repo=project["name"],
                max_commits=self.config.commits_per_project
            )

            if commits:
                self.project_commits[project["full_name"]] = {
                    "project": project,
                    "commits": commits
                }

                # 统计信息
                expected = self.config.commits_per_project
                actual = len(commits)

                total_expected_commits += expected
                total_actual_commits += actual

                project_time = time.time() - project_individual_start
                avg_time_per_commit = project_time / actual if actual > 0 else 0

                print(f"   ✅ 获取: {actual}/{expected} 条commit")
                print(f"   ⏱️  耗时: {project_time:.1f} 秒 (平均 {avg_time_per_commit:.3f} 秒/commit)")

                # 显示时间顺序验证
                if actual >= 2:
                    print(f"   📅 最新commit: {commits[0]['author_date']}")
                    print(f"   📅 最老commit: {commits[-1]['author_date']}")

                # 保存每个项目的数据
                self.save_project_commits_with_time_csv(project, commits)

                # 每处理5个项目显示一次总进度
                if processed_count % 5 == 0:
                    elapsed = time.time() - start_time
                    print(f"\n📈 进度: 已处理 {processed_count}/{len(projects_to_process)} 个项目")
                    print(f"📈 用时: {elapsed:.1f} 秒")

        # 4. 显示最终统计
        total_time = time.time() - start_time
        self.print_summary(len(projects_to_process), total_expected_commits, total_actual_commits, total_time)

    def save_project_commits_with_time_csv(self, project: Dict, commits: List[Dict], filename: str = None):
        """保存单个项目的commits到CSV，包含时间"""
        if not filename:
            safe_name = project["full_name"].replace("/", "_").replace("\\", "_")
            filename = f"{safe_name}_commits_with_time.csv"

        filepath = self._get_output_path(filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # 保存4个字段
            writer.writerow(["项目名称", "提交ID", "提交时间", "总变化行数"])

            for commit in commits:
                writer.writerow([
                    project["full_name"],
                    commit["sha_short"],
                    commit["author_date"],
                    commit["total_changes"]
                ])

        logger.info(f"📁 提交记录（带时间）已保存到 {filepath}")

        # 验证CSV中的时间顺序
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) > 3:  # 至少有标题行和2个数据行
                # 读取前3个commit的时间
                import csv as csv_module
                reader = csv_module.reader(lines[1:4])  # 跳过标题行
                times = []
                for row in reader:
                    if len(row) >= 3:
                        times.append(row[2])  # 提交时间列

                if len(times) >= 2:
                    print(f"   ✅ CSV验证: 第1个commit时间 {times[0]}")
                    print(f"   ✅ CSV验证: 第2个commit时间 {times[1]}")

        return filepath

    def print_summary(self, processed_count, total_expected: int, total_actual: int, total_time: float):
        """打印摘要信息"""
        print("\n" + "=" * 60)
        print("分析摘要（带时间排序）")
        print("=" * 60)
        print(f"✅ 分析完成！")
        print(f"  总用时: {total_time:.1f} 秒 ({total_time / 60:.1f} 分钟)")
        print(f"  处理项目数: {processed_count}")
        print(f"  Commit总数: {total_actual}/{total_expected}")

        if total_actual > 0:
            avg_time_per_commit = total_time / total_actual
            print(f"  平均每个Commit处理时间: {avg_time_per_commit:.3f} 秒")
            print(f"  平均速度: {total_actual / total_time:.1f} commits/秒")

        print(f"\n📁 输出目录: {os.path.abspath(self.output_dir)}")
        print(f"\n📁 生成的文件 (包含4个字段):")
        print(f"  项目名称, 提交ID, 提交时间, 总变化行数")

        # 显示生成的文件列表
        import glob
        csv_files = glob.glob(os.path.join(self.output_dir, "*.csv"))
        if csv_files:
            print(f"\n📁 目录中的文件 ({len(csv_files)} 个):")
            for csv_file in csv_files[:10]:  # 只显示前10个
                filename = os.path.basename(csv_file)
                size = os.path.getsize(csv_file)
                print(f"  - {filename} ({size:,} bytes)")
            if len(csv_files) > 10:
                print(f"  ... 还有 {len(csv_files) - 10} 个文件")


def main_with_time():
    """主函数（带时间排序）- 增量爬取"""
    config = ProjectConfig(
        min_stars=1000,
        max_projects=50,  # 目标项目数
        commits_per_project=500,  # 每个项目获取500个commits
        language="C"
    )

    # 使用8个并行工作线程
    analyzer = CommitAnalyzerFast(config, output_dir="output_with_time", max_workers=8)
    analyzer.run()


if __name__ == "__main__":
    main_with_time()