import csv
import json
import time
import requests
from typing import Dict, List, Optional

# Bug类型分类映射
BUG_CATEGORIES = {
    "内存安全": ["内存泄漏", "缓冲区溢出", "野指针"],
    "并发安全": ["竞态条件", "死锁"],
    "系统错误": ["空指针解引用", "资源泄漏"],
    "逻辑错误": ["条件判断错误", "循环边界错误", "整数溢出"],
    "安全漏洞": ["格式化字符串", "输入验证"],
    "性能问题": ["算法效率"],
    "其他": ["配置错误", "非Bug修复"]
}


class CommitAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def analyze_commit_message(self, commit_message: str) -> Dict:
        """
        使用ChatGPT API分析commit消息，识别bug类型
        """
        prompt = f"""
请分析以下C语言项目的commit消息，识别修复的bug类型：

Commit消息: "{commit_message}"

请从以下bug类型中选择最匹配的一项（如果没有修复bug，请选择"非Bug修复"）：
- 内存泄漏、缓冲区溢出、野指针
- 竞态条件、死锁
- 空指针解引用、资源泄漏
- 条件判断错误、循环边界错误、整数溢出
- 格式化字符串、输入验证
- 算法效率
- 配置错误
- 非Bug修复

请按以下JSON格式回复，不要包含其他内容：
{{
    "has_bug_fix": true/false,
    "bug_category": "大类名称",
    "bug_type": "具体bug类型名称",
    "confidence": 0.0-1.0,
    "reasoning": "简要分析理由"
}}
"""

        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "你是一个专业的软件工程分析专家，擅长识别代码提交中的bug修复类型。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }

        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()

            result_data = response.json()
            result_text = result_data["choices"][0]["message"]["content"].strip()

            # 解析JSON响应
            result = json.loads(result_text)

            # 验证bug类型是否在预定义列表中
            if result["has_bug_fix"] and result["bug_type"] != "非Bug修复":
                valid_type = False
                for category, types in BUG_CATEGORIES.items():
                    if result["bug_type"] in types:
                        valid_type = True
                        break

                if not valid_type:
                    result["bug_type"] = "非Bug修复"
                    result["has_bug_fix"] = False
                    result["confidence"] = 0.0
                    result["reasoning"] = "检测到的bug类型不在预定义列表中"

            return result

        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"原始响应: {result_text}")
            return {
                "has_bug_fix": False,
                "bug_category": "其他",
                "bug_type": "非Bug修复",
                "confidence": 0.0,
                "reasoning": "API响应解析失败"
            }
        except Exception as e:
            print(f"API调用错误: {e}")
            return {
                "has_bug_fix": False,
                "bug_category": "其他",
                "bug_type": "非Bug修复",
                "confidence": 0.0,
                "reasoning": f"API调用失败: {str(e)}"
            }


def read_csv_file(filename: str) -> List[Dict]:
    """读取CSV文件"""
    data = []
    try:
        # 尝试不同的编码方式和分隔符组合
        encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']
        delimiters = [',', ';', '\t']  # 常见分隔符：逗号、分号、制表符

        for encoding in encodings:
            for delimiter in delimiters:
                try:
                    with open(filename, 'r', encoding=encoding) as file:
                        # 读取前几行来检查文件内容
                        lines = file.readlines()
                        if not lines:
                            continue

                        # 检查第一行是否是标题行
                        first_line = lines[0].strip()
                        if delimiter in first_line:
                            # 重置文件指针
                            file.seek(0)
                            reader = csv.DictReader(file, delimiter=delimiter)

                            for row in reader:
                                # 清理键名中的特殊字符
                                cleaned_row = {}
                                for key, value in row.items():
                                    cleaned_key = key.strip().strip('\ufeff')  # 移除BOM和空格
                                    cleaned_row[cleaned_key] = value
                                data.append(cleaned_row)

                            print(f"成功使用编码 {encoding} 和分隔符 '{delimiter}' 读取CSV文件")
                            print(f"共{len(data)}条记录")
                            print(f"列名: {list(data[0].keys()) if data else '无数据'}")
                            return data
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    continue

        # 如果自动检测失败，尝试简单读取
        print("自动检测失败，尝试简单读取...")
        for encoding in encodings:
            try:
                with open(filename, 'r', encoding=encoding) as file:
                    content = file.read()
                    print("文件内容前500字符:")
                    print(content[:500])

                    # 尝试手动解析
                    lines = content.strip().split('\n')
                    if len(lines) > 1:
                        # 假设第一行是标题
                        headers = [h.strip().strip('\ufeff') for h in lines[0].split(',')]
                        for i, line in enumerate(lines[1:]):
                            if line.strip():
                                values = line.split(',')
                                row = {}
                                for j, header in enumerate(headers):
                                    if j < len(values):
                                        row[header] = values[j].strip()
                                    else:
                                        row[header] = ''
                                data.append(row)

                        print(f"手动解析成功，共{len(data)}条记录")
                        return data
            except Exception as e:
                print(f"简单读取失败: {e}")
                continue

        print("所有读取方法都失败")
        return []

    except Exception as e:
        print(f"读取CSV文件错误: {e}")
        return []


def write_csv_file(filename: str, data: List[Dict], fieldnames: List[str]):
    """写入CSV文件"""
    try:
        with open(filename, 'w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"成功写入CSV文件: {filename}")
    except Exception as e:
        print(f"写入CSV文件错误: {e}")


def process_commits(input_file: str, output_file: str, commit_column: str = "提交信息"):
    """处理commit分析"""

    # 初始化分析器
    analyzer = CommitAnalyzer("sk-zk2ee26dcf5e96682b1c6604fb9795df721693381fb0b64a")

    # 读取原始数据
    original_data = read_csv_file(input_file)
    if not original_data:
        print("无法读取CSV文件，请检查文件路径和格式")
        print("请确认文件是否存在: commits.csv")
        return

    # 显示所有列名供确认
    print("检测到的列名:", list(original_data[0].keys()))

    # 检查commit列是否存在
    if commit_column not in original_data[0]:
        print(f"错误: 列 '{commit_column}' 不存在")
        print(f"可用列: {list(original_data[0].keys())}")

        # 尝试自动找到commit消息列
        possible_columns = ['提交信息', 'commit_message', 'message', 'commit', 'desc', 'description', '提交消息']
        for col in possible_columns:
            if col in original_data[0]:
                commit_column = col
                print(f"自动选择列: {commit_column}")
                break
        else:
            # 让用户选择列
            print("请从以上列名中选择commit消息列，输入列名:")
            user_choice = input().strip()
            if user_choice in original_data[0]:
                commit_column = user_choice
                print(f"使用列: {commit_column}")
            else:
                print("无效的列名，退出程序")
                return

    # 处理每条记录
    processed_data = []
    total_count = len(original_data)

    # 限制处理数量，避免API费用过高（可以调整）
    max_commits = min(10, total_count)  # 先处理10条测试

    print(f"将处理前{max_commits}条commit记录...")

    for i, row in enumerate(original_data[:max_commits]):
        commit_msg = row.get(commit_column, '')

        if not commit_msg or commit_msg.strip() == '':
            print(f"跳过空消息的行 {i + 1}")
            # 添加空的分析结果
            row.update({
                'has_bug_fix': 'False',
                'bug_category': '',
                'bug_type': '',
                'confidence': '0.0',
                'analysis_reasoning': '空消息'
            })
            processed_data.append(row)
            continue

        print(f"分析第 {i + 1}/{max_commits} 条commit: {commit_msg[:80]}...")

        # 调用API分析
        analysis_result = analyzer.analyze_commit_message(commit_msg)

        # 更新结果
        row.update({
            'has_bug_fix': str(analysis_result['has_bug_fix']),
            'bug_category': analysis_result['bug_category'],
            'bug_type': analysis_result['bug_type'],
            'confidence': str(analysis_result['confidence']),
            'analysis_reasoning': analysis_result['reasoning']
        })

        processed_data.append(row)

        # 添加延迟避免API限制
        time.sleep(2)  # 增加延迟避免速率限制

        # 每2条保存一次进度
        if (i + 1) % 2 == 0:
            # 确定所有字段名
            all_fieldnames = list(original_data[0].keys()) + [
                'has_bug_fix', 'bug_category', 'bug_type', 'confidence', 'analysis_reasoning'
            ]
            write_csv_file(output_file, processed_data, all_fieldnames)
            print(f"已保存进度到 {output_file}")

    # 最终保存
    all_fieldnames = list(original_data[0].keys()) + [
        'has_bug_fix', 'bug_category', 'bug_type', 'confidence', 'analysis_reasoning'
    ]
    write_csv_file(output_file, processed_data, all_fieldnames)

    # 生成统计报告
    generate_statistics_report(processed_data, output_file.replace('.csv', '_report.txt'))


def generate_statistics_report(data: List[Dict], report_file: str):
    """生成统计报告"""

    total_commits = len(data)
    bug_fixes = sum(1 for row in data if row.get('has_bug_fix', 'False').lower() == 'true')
    bug_rate = (bug_fixes / total_commits * 100) if total_commits > 0 else 0

    # 统计bug类型
    bug_type_counts = {}
    for row in data:
        if row.get('has_bug_fix', 'False').lower() == 'true':
            bug_type = row.get('bug_type', '')
            bug_type_counts[bug_type] = bug_type_counts.get(bug_type, 0) + 1

    # 生成报告内容
    report = f"""Commit Bug类型分析报告
====================

总体统计:
- 总commit数: {total_commits}
- 修复bug的commit数: {bug_fixes}
- bug修复比例: {bug_rate:.2f}%

Bug类型分布:
"""

    for bug_type, count in bug_type_counts.items():
        percentage = (count / bug_fixes * 100) if bug_fixes > 0 else 0
        report += f"- {bug_type}: {count} 次 ({percentage:.2f}%)\n"

    # 保存报告
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"统计报告已生成: {report_file}")
        print(report)
    except Exception as e:
        print(f"生成报告错误: {e}")


def main():
    """主函数"""
    # 配置参数
    input_csv = "commits.csv"  # 输入的CSV文件路径
    output_csv = "commits_analyzed.csv"  # 输出文件路径
    commit_column = "提交信息"  # commit消息列名

    print("开始分析commit消息...")
    print(f"输入文件: {input_csv}")
    print(f"输出文件: {output_csv}")
    print(f"commit消息列: {commit_column}")
    print("-" * 50)

    # 检查文件是否存在
    import os
    if not os.path.exists(input_csv):
        print(f"错误: 文件 {input_csv} 不存在")
        print("请确保CSV文件在当前目录下")
        return

    # 处理commit分析
    process_commits(input_csv, output_csv, commit_column)


if __name__ == "__main__":
    main()