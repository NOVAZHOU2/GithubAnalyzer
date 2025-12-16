import pandas as pd
import os
import glob


def find_largest_valid_interval(file_path, min_interval_length=50, max_diff_threshold=200):
    """
    为单个项目文件找到最大的连续区间，其中所有commit的diff行数不超过阈值
    """
    # 读取commit数据
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

    # 检查是否有必要的列
    required_columns = ['提交ID', '总变化行数']
    for col in required_columns:
        if col not in df.columns:
            print(f"Column '{col}' not found in {file_path}")
            return None

    # 确保数据按时间顺序排列（最新的在前面）
    if '提交时间' in df.columns:
        # 将提交时间转换为datetime类型用于排序
        df['提交时间'] = pd.to_datetime(df['提交时间'], errors='coerce')
        # 按时间倒序排序（最新的在最前面）
        df = df.sort_values('提交时间', ascending=False).reset_index(drop=True)
    else:
        print(f"⚠️  '提交时间' column not found, using original order")

    # 将总变化行数转换为数值类型
    df['总变化行数'] = pd.to_numeric(df['总变化行数'], errors='coerce').fillna(0)

    # 找到所有满足条件的连续区间
    intervals = []
    start_index = -1
    current_length = 0

    for i in range(len(df)):
        if df.iloc[i]['总变化行数'] <= max_diff_threshold:
            if start_index == -1:  # 开始新的区间
                start_index = i
            current_length += 1
        else:
            if current_length >= min_interval_length:  # 只记录长度≥50的区间
                intervals.append((start_index, current_length))
            start_index = -1
            current_length = 0

    # 处理最后一个区间
    if current_length >= min_interval_length:
        intervals.append((start_index, current_length))

    if not intervals:
        print(f"No valid interval (length ≥ {min_interval_length}) found in {file_path}")
        return None

    # 找到最长的区间
    longest_interval = max(intervals, key=lambda x: x[1])
    start_index, interval_length = longest_interval

    # 获取区间信息
    start_commit_row = df.iloc[start_index]
    end_commit_row = df.iloc[start_index + interval_length - 1]

    # 提取commit信息
    start_commit_id = start_commit_row['提交ID']
    end_commit_id = end_commit_row['提交ID']

    # 从文件名获取项目名并修剪
    filename = os.path.basename(file_path)
    project_name = clean_project_name(filename)

    return {
        'project': project_name,
        'start_commit_id': start_commit_id,
        'end_commit_id': end_commit_id,
        'interval_length': interval_length
    }


def clean_project_name(filename):
    """
    修剪项目名，去掉不必要的后缀
    """
    # 去掉各种可能的后缀
    suffixes = [
        '_commits_with_time.csv',
        '_commits_with_diff.csv',
        '_commits.csv',
        '_commits_fast.csv',
        '_commits_minimal.csv',
        '.csv'
    ]

    name = filename
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    # 将下划线恢复为斜杠（对于GitHub项目）
    if '_' in name and '/' not in name:
        # 尝试最多分割3次
        parts = name.split('_', 3)
        if len(parts) >= 2:
            # 取前两部分作为组织名/项目名
            name = f"{parts[0]}/{parts[1]}"
            # 如果有第三部分，可能是子项目，也加上
            if len(parts) >= 3 and parts[2]:
                name += f"_{parts[2]}"
                if len(parts) >= 4 and parts[3]:
                    name += f"_{parts[3]}"

    return name


def process_all_projects_in_directory(directory_path="../results/output_with_diff", min_interval_length=50,
                                      max_diff_threshold=200):
    """
    处理目录中的所有项目文件
    """
    # 查找所有CSV文件
    csv_files = glob.glob(os.path.join(directory_path, "*.csv"))

    if not csv_files:
        print(f"No CSV files found in {directory_path}")
        return []

    print(f"Found {len(csv_files)} project files to process")
    print(f"Minimum interval length: {min_interval_length} commits")
    print(f"Maximum diff per commit: {max_diff_threshold} lines")

    project_intervals = []

    for file_path in csv_files:
        filename = os.path.basename(file_path)
        print(f"\nProcessing {filename}...")

        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            print(f"  ✗ File is empty")
            continue

        interval = find_largest_valid_interval(file_path, min_interval_length, max_diff_threshold)

        if interval:
            project_intervals.append(interval)
            print(f"  ✓ Found interval: {interval['interval_length']} commits")
            print(f"    From: {interval['start_commit_id']}")
            print(f"    To:   {interval['end_commit_id']}")
        else:
            print(f"  ✗ No interval with ≥{min_interval_length} commits found")

    return project_intervals


def save_results(project_intervals, output_file="project_intervals_results.csv"):
    """
    保存结果到CSV文件
    """
    if not project_intervals:
        print("No valid intervals found")
        return

    # 转换为DataFrame
    results_df = pd.DataFrame(project_intervals)

    # 只保留四个属性
    columns_order = ['project', 'start_commit_id', 'end_commit_id', 'interval_length']
    results_df = results_df[columns_order]

    # 按区间长度降序排序
    results_df = results_df.sort_values('interval_length', ascending=False)

    # 保存到CSV
    results_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✓ Results saved to {output_file}")

    # 打印汇总信息
    print(f"\n=== Summary ===")
    print(f"Total projects with valid intervals (length ≥ 50): {len(project_intervals)}")


def main():
    """
    主函数
    """
    # 配置参数
    output_dir = "output_with_time"  # 包含各项目commit文件的目录
    output_file = "project_intervals_results.csv"  # 结果输出文件
    min_interval_length = 50  # 最小区间长度
    max_diff_threshold = 200  # 每个commit的最大diff行数阈值

    print("=" * 60)
    print("GitHub项目连续小变更区间分析")
    print("=" * 60)
    print(f"分析目录: {output_dir}")
    print(f"最小区间长度: {min_interval_length} commits")
    print(f"每个commit最大diff行数: {max_diff_threshold} lines")
    print("-" * 60)

    # 处理所有项目文件
    project_intervals = process_all_projects_in_directory(
        output_dir,
        min_interval_length,
        max_diff_threshold
    )

    # 保存结果
    save_results(project_intervals, output_file)

    # 显示详细结果
    if project_intervals:
        # 按区间长度排序
        sorted_intervals = sorted(project_intervals, key=lambda x: x['interval_length'], reverse=True)

        print(f"\n=== 详细结果（按区间长度排序）===")
        for i, interval in enumerate(sorted_intervals, 1):
            project_display = interval['project']
            if len(project_display) > 30:
                project_display = project_display[:27] + "..."

            print(f"{i:2d}. {project_display:30} "
                  f"长度: {interval['interval_length']:3d} commits "
                  f"[{interval['start_commit_id']}..{interval['end_commit_id']}]")

        # 统计信息
        total_commits = sum(interval['interval_length'] for interval in project_intervals)
        avg_length = total_commits / len(project_intervals) if project_intervals else 0
        max_length = max(interval['interval_length'] for interval in project_intervals) if project_intervals else 0
        min_length = min(interval['interval_length'] for interval in project_intervals) if project_intervals else 0

        print(f"\n=== 统计信息 ===")
        print(f"平均区间长度: {avg_length:.1f} commits")
        print(f"最小区间长度: {min_length} commits")
        print(f"最大区间长度: {max_length} commits")
        print(f"所有区间总commit数: {total_commits}")
        print(f"符合条件的项目数: {len(project_intervals)}")


if __name__ == "__main__":
    main()