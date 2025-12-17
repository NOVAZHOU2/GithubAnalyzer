import pandas as pd
import os
import glob


def load_intervals_from_file(intervals_file_path):
    """
    从区间文件中加载区间信息
    格式：project,start_commit_id,end_commit_id,interval_length
    """
    intervals = []

    try:
        # 首先尝试读取文件，看看是否有表头
        with open(intervals_file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()

        # 检查第一行是否包含表头
        has_header = 'project' in first_line.lower() or 'interval' in first_line.lower()

        if has_header:
            print(f"检测到文件有表头，跳过第一行")
            # 有表头，从第二行开始读取
            df = pd.read_csv(intervals_file_path)
        else:
            # 无表头
            df = pd.read_csv(intervals_file_path, header=None,
                             names=['project', 'start_commit_id', 'end_commit_id', 'interval_length'])

        print(f"读取到 {len(df)} 行数据")

        for _, row in df.iterrows():
            # 跳过表头行
            if str(row.get('project', '')).lower() in ['project', 'project_name']:
                continue

            try:
                interval_info = {
                    'project': str(row['project']).strip(),
                    'start_commit_id': str(row['start_commit_id']).strip(),
                    'end_commit_id': str(row['end_commit_id']).strip(),
                    'interval_length': int(row['interval_length'])
                }
                intervals.append(interval_info)
            except (ValueError, TypeError) as e:
                print(f"跳过无效行: {row.to_dict()} - 错误: {e}")
                continue

        print(f"✓ 从 {intervals_file_path} 成功加载了 {len(intervals)} 个有效区间")
        return intervals

    except Exception as e:
        print(f"Error loading intervals from {intervals_file_path}: {e}")
        return []


def get_project_file_path(project_name, data_dir="output_with_time"):
    """
    根据项目名找到对应的数据文件路径
    """
    # 将项目名转换为可能的文件名格式
    safe_names = [
        project_name.replace('/', '_') + '_commits_with_time.csv',
        project_name.replace('/', '_') + '_commits.csv',
        project_name.replace('/', '_') + '.csv'
    ]

    for filename in safe_names:
        file_path = os.path.join(data_dir, filename)
        if os.path.exists(file_path):
            return file_path

    return None


def extract_commits_in_order(project_name, start_commit_id, end_commit_id, expected_length,
                             data_dir="output_with_time"):
    """
    从项目数据文件中按顺序提取指定区间的所有commits
    保持源文件中的原始顺序
    """
    # 1. 找到项目数据文件
    data_file = get_project_file_path(project_name, data_dir)
    if not data_file:
        print(f"  ✗ 找不到项目 {project_name} 的数据文件")
        return []

    # 2. 读取整个项目数据文件
    try:
        df = pd.read_csv(data_file)
    except Exception as e:
        print(f"  ✗ 读取 {data_file} 失败: {e}")
        return []

    # 检查必要的列
    required_columns = ['项目名称', '提交ID', '提交时间', '总变化行数']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"  ✗ 缺少必要的列: {missing_columns}")
        return []

    # 3. 找到起始和终止commit的索引
    start_index = None
    end_index = None

    for i, commit_id in enumerate(df['提交ID']):
        commit_str = str(commit_id).strip()

        # 检查是否匹配起始commit
        if start_index is None and commit_str.startswith(start_commit_id):
            start_index = i

        # 检查是否匹配终止commit
        if end_index is None and commit_str.startswith(end_commit_id):
            end_index = i

    # 4. 验证找到的索引
    if start_index is None:
        print(f"  ✗ 找不到起始commit: {start_commit_id}")
        return []

    if end_index is None:
        print(f"  ✗ 找不到终止commit: {end_commit_id}")
        return []

    # 5. 确保起始索引小于终止索引
    if start_index > end_index:
        print(f"  ⚠️  起始commit索引 {start_index} 在终止commit索引 {end_index} 之后")
        return []

    # 6. 验证区间长度
    actual_length = end_index - start_index + 1
    if actual_length != expected_length:
        print(f"  ⚠️  实际区间长度 {actual_length} 与预期 {expected_length} 不一致")
        return []

    # 7. 提取区间内的所有commits，保持原始顺序
    interval_commits = []

    for i in range(start_index, end_index + 1):
        row = df.iloc[i]
        commit_info = {
            'project': project_name,
            'commit': str(row['提交ID']).strip(),
            'diff_lines': int(float(row['总变化行数']))
        }
        interval_commits.append(commit_info)

    print(f"  ✓ 提取了 {actual_length} 个commits (从索引 {start_index} 到 {end_index})")

    # 8. 验证顺序
    if actual_length >= 2:
        first_commit = interval_commits[0]['commit']
        last_commit = interval_commits[-1]['commit']

        if first_commit.startswith(start_commit_id) and last_commit.startswith(end_commit_id):
            print(f"  ✓ 顺序验证通过: {first_commit[:7]}..{last_commit[:7]}")
        else:
            print(f"  ⚠️  顺序验证失败")

    return interval_commits


def process_all_intervals(intervals_file_path, data_dir="output_with_time"):
    """
    处理所有区间，提取每个区间的commits
    """
    # 1. 加载区间信息
    all_intervals = load_intervals_from_file(intervals_file_path)
    if not all_intervals:
        return [], []

    # 2. 为每个区间提取commits
    all_commits = []
    processed_intervals = []

    print(f"\n开始处理 {len(all_intervals)} 个区间...")
    print("-" * 80)

    for i, interval in enumerate(all_intervals, 1):
        project = interval['project']
        start_commit = interval['start_commit_id']
        end_commit = interval['end_commit_id']
        expected_length = interval['interval_length']

        print(f"\n[{i}/{len(all_intervals)}] 处理: {project}")
        print(f"  区间: {start_commit}..{end_commit} (预期 {expected_length} commits)")

        # 提取该区间的commits
        commits = extract_commits_in_order(project, start_commit, end_commit, expected_length, data_dir)

        if commits:
            actual_length = len(commits)

            # 添加到总列表
            all_commits.extend(commits)
            processed_intervals.append(interval)

            # 显示提取的commits数量
            print(f"  ✓ 成功提取 {actual_length} 个commits")
        else:
            print(f"  ✗ 提取失败")

    return processed_intervals, all_commits


def save_results(processed_intervals, all_commits, output_dir="results"):
    """
    保存结果到文件
    """
    if not processed_intervals and not all_commits:
        print("No results to save")
        return

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 1. 保存区间信息（格式：project,start_commit_id,end_commit_id,interval_length）
    if processed_intervals:
        # 创建DataFrame
        intervals_df = pd.DataFrame(processed_intervals)

        # 确保列顺序正确
        intervals_df = intervals_df[['project', 'start_commit_id', 'end_commit_id', 'interval_length']]

        # 按区间长度降序排序
        intervals_df = intervals_df.sort_values('interval_length', ascending=False)

        # 保存到CSV
        intervals_file = os.path.join(output_dir, "project_intervals.csv")
        intervals_df.to_csv(intervals_file, index=False, header=False, encoding='utf-8-sig')
        print(f"\n✓ 区间信息已保存到: {intervals_file}")

        # 打印所有区间
        print(f"\n处理成功的区间 (共{len(intervals_df)}个):")
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

        # 按项目分组，保持每个项目内的时间顺序
        # 由于我们已经按原始文件顺序提取，所以直接保存即可
        commits_file = os.path.join(output_dir, "project_commits.csv")
        commits_df.to_csv(commits_file, index=False, header=False, encoding='utf-8-sig')
        print(f"\n✓ 所有commits详情已保存到: {commits_file}")

        # 统计commits数量
        commits_count = len(commits_df)
        projects_count = commits_df['project'].nunique()
        print(f"  包含 {projects_count} 个项目的 {commits_count} 个commits")

        # 显示每个项目的commits数量
        project_stats = commits_df.groupby('project').size().reset_index(name='count')
        project_stats = project_stats.sort_values('count', ascending=False)

        print(f"\n各项目commits数量:")
        for i, row in project_stats.head(10).iterrows():
            project = row['project']
            if len(project) > 25:
                project = project[:22] + "..."
            print(f"  {project:25} {row['count']:4d} commits")

        # 验证文件中的顺序
        print(f"\n验证文件顺序:")
        with open(commits_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) >= 3:
                first_line = lines[0].strip()
                last_line = lines[-1].strip() if lines[-1].strip() else lines[-2].strip()
                print(f"  第一个commit: {first_line}")
                print(f"  最后一个commit: {last_line}")

    # 打印汇总信息
    print(f"\n" + "=" * 60)
    print("汇总信息")
    print("=" * 60)
    print(f"成功处理的区间数: {len(processed_intervals)}")

    if processed_intervals:
        # 统计信息
        total_commits = sum(interval['interval_length'] for interval in processed_intervals)
        total_extracted_commits = len(all_commits)
        avg_length = total_commits / len(processed_intervals) if processed_intervals else 0
        max_length = max(interval['interval_length'] for interval in processed_intervals) if processed_intervals else 0
        min_length = min(interval['interval_length'] for interval in processed_intervals) if processed_intervals else 0

        # 计算总变化行数
        if all_commits:
            total_diff_lines = sum(commit['diff_lines'] for commit in all_commits)
            avg_diff = total_diff_lines / total_extracted_commits if total_extracted_commits > 0 else 0
        else:
            total_diff_lines = 0
            avg_diff = 0

        print(f"预期总commit数: {total_commits}")
        print(f"实际提取commit数: {total_extracted_commits}")
        print(f"总变化行数: {total_diff_lines}")
        print(f"平均区间长度: {avg_length:.1f} commits")
        print(f"平均每commit变化: {avg_diff:.1f} 行")
        print(f"最小区间长度: {min_length} commits")
        print(f"最大区间长度: {max_length} commits")

        if total_commits != total_extracted_commits:
            print(f"⚠️  注意: 预期和实际提取的commit数量不一致")

    print(f"详细commits记录数: {len(all_commits)}")


def main():
    """
    主函数
    """
    # 配置参数
    intervals_file = "project_intervals_results.csv"  # 区间文件路径
    data_dir = "output_with_time"  # 包含各项目commit文件的目录
    output_dir = "results"  # 输出结果目录

    print("=" * 60)
    print("GitHub项目区间commits提取工具")
    print("从已确定的区间中提取所有commits")
    print("=" * 60)
    print(f"区间文件: {intervals_file}")
    print(f"数据目录: {data_dir}")
    print(f"输出目录: {output_dir}")
    print("-" * 60)

    # 处理所有区间
    processed_intervals, all_commits = process_all_intervals(intervals_file, data_dir)

    # 保存结果
    save_results(processed_intervals, all_commits, output_dir)


if __name__ == "__main__":
    main()