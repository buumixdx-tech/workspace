"""
Dify API 调用模块
封装与 Dify 工作流的通信逻辑
"""
import requests
import json
from config import DIFY_API_URL, DIFY_API_KEY

def call_dify_workflow(news_json):
    """
    调用 Dify 工作流处理新闻
    
    Args:
        news_json: 新闻数据字典，包含 标题、内容、信息发布方、发布时间 等字段
    
    Returns:
        tuple: (success: bool, result: dict or str)
               成功时返回 (True, 结果字典)
               失败时返回 (False, 错误信息)
    """
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 构造请求 payload
    # Dify 工作流的输入参数为单个 "json" 字段，值为 JSON 字符串
    payload = {
        "inputs": {
            "json": json.dumps(news_json, ensure_ascii=False)
        },
        "response_mode": "blocking",
        "user": "rss-engine"
    }
    
    try:
        # 设置超长超时：连接 10 秒，读取 300 秒（5 分钟）
        response = requests.post(
            DIFY_API_URL,
            headers=headers,
            json=payload,
            timeout=(10, 300)
        )
        response.raise_for_status()
        
        result = response.json()
        
        # 解析 Dify 返回结构
        # Dify 返回格式: { "data": { "outputs": { "text": "{...JSON字符串...}" } } }
        if result.get("data") and result["data"].get("outputs"):
            outputs = result["data"]["outputs"]
            text_output = outputs.get("text", "")
            
            # 解析 text 字段中的 JSON 字符串
            try:
                parsed_output = json.loads(text_output)
            except json.JSONDecodeError:
                # 如果解析失败，尝试清理常见问题
                cleaned = text_output.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                try:
                    parsed_output = json.loads(cleaned.strip())
                except:
                    return False, f"无法解析 LLM 输出: {text_output[:200]}"
            
            # 将数组字段转换为 JSON 字符串存储
            def array_to_json_str(val):
                if isinstance(val, list):
                    return json.dumps(val, ensure_ascii=False)
                return val or ""
            
            # 提取重要度，兼容“重要度”和“重要程度”两种命名方式
            try:
                # 优先获取“重要度”，其次“重要程度”，最后默认为 3
                val = parsed_output.get("重要度") or parsed_output.get("重要程度", 3)
                importance = int(val)
                importance = max(1, min(5, importance))
            except:
                importance = 3

            return True, {
                "标题": parsed_output.get("标题", ""),
                "发布来源": parsed_output.get("发布来源", ""),
                "转载来源": parsed_output.get("转载来源", ""),
                "消息类型": parsed_output.get("消息类型", ""),
                "发布时间": parsed_output.get("发布时间", ""),
                "综述": parsed_output.get("综述", ""),
                "影响板块": array_to_json_str(parsed_output.get("影响板块", [])),
                "直接提到的个股": array_to_json_str(parsed_output.get("直接提到的个股", [])),
                "可能影响的个股": array_to_json_str(parsed_output.get("可能影响的个股", [])),
                "原文链接": parsed_output.get("原文链接", ""),
                "重要度": importance,
                "_raw_text": text_output # 新增：原始文本
            }
        else:
            return False, f"Dify 返回格式异常: {result}"
            
    except requests.exceptions.Timeout:
        return False, "请求超时（超过 5 分钟）"
    except requests.exceptions.ConnectionError:
        return False, "无法连接到 Dify 服务"
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP 错误: {e.response.status_code} - {e.response.text}"
    except json.JSONDecodeError:
        return False, "Dify 返回非 JSON 格式"
    except Exception as e:
        return False, f"未知错误: {str(e)}"

def test_connection():
    """测试 Dify 连接是否正常"""
    test_news = {
        "标题": "测试标题",
        "内容": "这是一条测试新闻内容",
        "信息发布方": "测试源",
        "发布时间": "2026-01-14 12:00:00"
    }
    success, result = call_dify_workflow(test_news)
    if success:
        print("Dify 连接测试成功!")
        print(f"返回结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    else:
        print(f"Dify 连接测试失败: {result}")
    return success

if __name__ == "__main__":
    test_connection()
