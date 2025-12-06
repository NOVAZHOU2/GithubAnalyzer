from openai import OpenAI
import os

client = OpenAI(api_key="sk-zk2ee26dcf5e96682b1c6604fb9795df721693381fb0b64a")

try:
    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": "测试一下你是否正常工作"}],
    )
    print("成功！API Key 可用：")
    print(res.choices[0].message["content"])

except Exception as e:
    print("测试失败：")
    print(e)
