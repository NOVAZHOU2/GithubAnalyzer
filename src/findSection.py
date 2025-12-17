import pandas as pd
import os
import glob


def find_longest_valid_interval(file_path, min_interval_length=50, max_diff_threshold=200):
    """
    为单个项目文件找到最长的连续区间，其中所有commit的diff行数不超过阈值
    每个项目只选取一段最长的区间
    """
    # 读取commit数据
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return [], []

    # 检查是否有必要的列
    required_columns = ['项目名称', '提交ID', '提交时间', '总变化行数']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Missing columns in {file_path}: {missing_columns}")
        return [], []

    # 确保数据按时间顺序排列（最新的在前面）
    if '提交时间' in df.columns:
        # 将提交时间转换为datetime类型用于排序
        df['提交时间'] = pd.to_datetime(df['提交时间'], errors='coerce')
        # 按时间倒序排序（最新的在最前面）
        df = df.sort_values('提交时间', ascending=False).reset_index(drop=True)

    # 从第一行获取项目名称
    project_name = df.iloc[0]['项目名称'] if len(df) > 0 else 'Unknown'

    # 将总变化行数转换为数值类型
    df['总变化行数'] = pd.to_numeric(df['总变化行数'], errors='coerce').fillna(0)

    # 找到所有满足条件的连续区间
    candidate_intervals = []  # 候选区间
    candidate_commits = []  # 候选区间的commits

    start_index = -1
    current_length = 0
    current_commits = []  # 当前区间的commits

    for i in range(len(df)):
        current_change = df.iloc[i]['总变化行数']

        if current_change <= max_diff_threshold:
            if start_index == -1:  # 开始新的区间
                start_index = i

            current_length += 1
            # 保存当前commit信息
            commit_info = {
                'project': project_name,
                'commit': df.iloc[i]['提交ID'],
                'diff_lines': int(current_change)
            }
            current_commits.append(commit_info)
        else:
            if current_length >= min_interval_length:  # 只记录长度≥50的区间
                end_index = start_index + current_length - 1

                # 获取区间起始和终止commit
                start_commit_id = df.iloc[start_index]['提交ID']
                end_commit_id = df.iloc[end_index]['提交ID']

                # 保存区间信息
                interval_info = {
                    'project': project_name,
                    'start_commit_id': start_commit_id,
                    'end_commit_id': end_commit_id,
                    'interval_length': current_length,
                    'start_index': start_index,
                    'end_index': end_index
                }
                candidate_intervals.append(interval_info)
                candidate_commits.append(current_commits.copy())  # 保存副本

            # 重置计数器
            start_index = -1
            current_length = 0
            current_commits = []

    # 处理最后一个区间
    if current_length >= min_interval_length:
        end_index = start_index + current_length - 1
        start_commit_id = df.iloc[start_index]['提交ID']
        end_commit_id = df.iloc[end_index]['提交ID']

        interval_info = {
            'project': project_name,
            'start_commit_id': start_commit_id,
            'end_commit_id': end_commit_id,
            'interval_length': current_length,
            'start_index': start_index,
            'end_index': end_index
        }
        candidate_intervals.append(interval_info)
        candidate_commits.append(current_commits.copy())

    # 如果没有找到任何区间，返回空
    if not candidate_intervals:
        return [], []

    # 选择最长的区间
    longest_interval = max(candidate_intervals, key=lambda x: x['interval_length'])

    # 找到对应的commits
    longest_index = candidate_intervals.index(longest_interval)
    selected_commits = candidate_commits[longest_index]

    return [longest_interval], selected_commits


def process_all_projects_in_directory(directory_path="output_with_time", min_interval_length=50,
                                      max_diff_threshold=200):
    """
    处理目录中的所有项目文件，每个项目只选取最长的一段区间
    """
    # 查找所有CSV文件
    csv_files = glob.glob(os.path.join(directory_path, "*.csv"))

    if not csv_files:
        print(f"No CSV files found in {directory_path}")
        return [], []

    print(f"Found {len(csv_files)} project files to process")
    print(f"Minimum interval length: {min_interval_length} commits")
    print(f"Maximum diff per commit: {max_diff_threshold} lines")

    all_intervals = []  # 所有区间信息（每个项目一段）
    all_commits = []  # 所有选定区间内的commits

    for file_path in csv_files:
        filename = os.path.basename(file_path)
        print(f"\nProcessing {filename}...")

        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            print(f"  ✗ File is empty")
            continue

        # 找到最长的区间
        intervals, commits = find_longest_valid_interval(file_path, min_interval_length, max_diff_threshold)

        if intervals:
            # 每个项目只应该有一段区间
            interval = intervals[0]

            print(f"  ✓ Found longest interval: {interval['interval_length']} commits")
            print(f"    From: {interval['start_commit_id']} to {interval['end_commit_id']}")

            # 添加找到的区间
            all_intervals.append(interval)

            # 添加找到的commits
            all_commits.extend(commits)
        else:
            print(f"  ✗ No interval with ≥{min_interval_length} commits found")

    return all_intervals, all_commits


def save_results(all_intervals, all_commits, output_dir="results"):
    """
    保存结果到文件
    """
    if not all_intervals and not all_commits:
        print("No results to save")
        return

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 1. 保存区间信息（格式：project,start_commit_id,end_commit_id,interval_length）
    if all_intervals:
        # 创建DataFrame
        intervals_df = pd.DataFrame(all_intervals)

        # 确保列顺序正确
        intervals_df = intervals_df[['project', 'start_commit_id', 'end_commit_id', 'interval_length']]

        # 按区间长度降序排序
        intervals_df = intervals_df.sort_values('interval_length', ascending=False)

        # 保存到CSV
        intervals_file = os.path.join(output_dir, "project_intervals.csv")
        intervals_df.to_csv(intervals_file, index=False, header=False, encoding='utf-8-sig')
        print(f"\n✓ 区间信息已保存到: {intervals_file}")

        # 打印所有区间
        print(f"\n所有项目的区间 (共{len(intervals_df)}个):")
        print("-" * 80)
        for i, row in intervals_df.iterrows():
            project = row['project']
            if len(project) > 30:
                project = project[:27] + "..."
            print(f"{project:30} {row['start_commit_id']}..{row['end_commit_id']} "
                  f"({row['interval_length']} commits)")

    # 2. 保存commits信息（格式：project,commit,diff_lines）
    if all_commits:
        # 创建DataFrame
        commits_df = pd.DataFrame(all_commits)

        # 确保列顺序正确
        commits_df = commits_df[['project', 'commit', 'diff_lines']]

        # 按项目和commit排序
        commits_df = commits_df.sort_values(['project', 'commit'])

        # 保存到CSV
        commits_file = os.path.join(output_dir, "project_commits.csv")
        commits_df.to_csv(commits_file, index=False, header=False, encoding='utf-8-sig')
        print(f"\n✓ 所有commits详情已保存到: {commits_file}")

        # 统计commits数量
        commits_count = len(commits_df)
        projects_count = commits_df['project'].nunique()
        print(f"  包含 {projects_count} 个项目的 {commits_count} 个commits")

    # 打印汇总信息
    print(f"\n" + "=" * 60)
    print("汇总信息")
    print("=" * 60)
    print(f"符合条件的项目数: {len(all_intervals)}")

    if all_intervals:
        # 统计信息
        total_commits = sum(interval['interval_length'] for interval in all_intervals)
        avg_length = total_commits / len(all_intervals)
        max_length = max(interval['interval_length'] for interval in all_intervals)
        min_length = min(interval['interval_length'] for interval in all_intervals)

        # 计算总变化行数
        if all_commits:
            total_diff_lines = sum(commit['diff_lines'] for commit in all_commits)
            avg_diff = total_diff_lines / total_commits if total_commits > 0 else 0
        else:
            total_diff_lines = 0
            avg_diff = 0

        print(f"总commit数: {total_commits}")
        print(f"总变化行数: {total_diff_lines}")
        print(f"平均区间长度: {avg_length:.1f} commits")
        print(f"平均每commit变化: {avg_diff:.1f} 行")
        print(f"最小区间长度: {min_length} commits")
        print(f"最大区间长度: {max_length} commits")

    print(f"详细commits记录数: {len(all_commits)}")


def main():
    """
    主函数
    """
    # 配置参数
    input_dir = "output_with_time"  # 包含各项目commit文件的目录
    output_dir = "results"  # 输出结果目录
    min_interval_length = 50  # 最小区间长度
    max_diff_threshold = 200  # 每个commit的最大diff行数阈值

    print("=" * 60)
    print("GitHub项目连续小变更区间分析")
    print("每个项目只选取最长的一段区间")
    print("=" * 60)
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print(f"最小区间长度: {min_interval_length} commits")
    print(f"每个commit最大diff行数: {max_diff_threshold} lines")
    print("-" * 60)

    # 处理所有项目文件
    all_intervals, all_commits = process_all_projects_in_directory(
        input_dir,
        min_interval_length,
        max_diff_threshold
    )

    # 保存结果
    save_results(all_intervals, all_commits, output_dir)


if __name__ == "__main__":
    main()