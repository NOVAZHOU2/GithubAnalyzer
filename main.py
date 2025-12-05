# main.py
import argparse
from src.github_analyzer import ProjectConfig, CommitAnalyzer
import os


def main():
    parser = argparse.ArgumentParser(description="GitHub C项目提交分析工具 - 简洁表格版")

    parser.add_argument("--stars", type=int, default=1000,
                        help="项目最小star数 (默认: 1000)")
    parser.add_argument("--projects", type=int, default=100,
                        help="最大项目数 (默认: 5)")
    parser.add_argument("--commits", type=int, default=200,
                        help="每个项目的commit数 (默认: 20)")
    parser.add_argument("--output", type=str, default="results",
                        help="输出目录 (默认: results)")

    args = parser.parse_args()

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    # 切换到输出目录
    original_dir = os.getcwd()
    os.chdir(args.output)

    print("🎯 GitHub C项目提交分析工具")
    print("=" * 50)
    print("配置信息:")
    print(f"  - 最小star数: {args.stars}")
    print(f"  - 最大项目数: {args.projects}")
    print(f"  - 每个项目commit数: {args.commits}")
    print()

    # 配置
    config = ProjectConfig(
        min_stars=args.stars,
        max_projects=args.projects,
        commits_per_project=args.commits
    )

    # 运行分析
    try:
        analyzer = CommitAnalyzer(config)
        analyzer.run()

    except KeyboardInterrupt:
        print("\n\n⏹️ 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 切回原目录
        os.chdir(original_dir)
        print(f"\n📁 结果文件保存在: {args.output}/")


if __name__ == "__main__":
    main()