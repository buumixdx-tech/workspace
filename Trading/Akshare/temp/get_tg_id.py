import requests
import toml
import os

def get_telegram_chat_id():
    # 1. 读取 Token
    config_path = r"d:\WorkSpace\Trading\Akshare\config.toml"
    token = ""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = toml.load(f)
            token = config["telegram"].get("bot_token", "")
    except Exception:
        pass

    if not token:
        print("错误: config.toml 中未找到 bot_token")
        return

    # 2. 调用 getUpdates 接口
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    print(f"正在查询: {url} ...")
    
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if not data.get("ok"):
            print(f"API请求失败: {data}")
            return
            
        updates = data.get("result", [])
        if not updates:
            print("\n❌ 未收到任何消息。")
            print("请先在 Telegram 中找到你的机器人，点击 Start 或发送一条消息，然后再次运行此脚本。")
            return
            
        # 3. 解析最新的 Chat ID
        last_update = updates[-1]
        chat = last_update.get("message", {}).get("chat", {})
        chat_id = chat.get("id")
        username = chat.get("username") or chat.get("first_name")
        
        print("\n✅ 成功获取！")
        print(f"发送人: {username}")
        print(f"Chat ID: {chat_id}")
        print(f"\n请将 {chat_id} 填入 config.toml 的 chat_id 字段。")
        
    except Exception as e:
        print(f"连接失败: {e}")
        print("请检查网络（是否需要全局代理才能访问 Telegram API）。")

if __name__ == "__main__":
    get_telegram_chat_id()
