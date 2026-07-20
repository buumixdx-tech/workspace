import requests
import toml
import os

class TelegramBot:
    def __init__(self):
        self.token = ""
        self.chat_id = ""
        self._load_config()

    def _load_config(self):
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.toml")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = toml.load(f)
                    if "telegram" in config:
                        self.token = config["telegram"].get("bot_token", "")
                        self.chat_id = config["telegram"].get("chat_id", "")
        except Exception as e:
            print(f"Error loading telegram config: {e}")

    def send_message(self, text: str, disable_web_page_preview: bool = False, parse_mode: str = "Markdown"):
        if not self.token or not self.chat_id:
            print("Telegram config missing (token or chat_id).")
            return
            
        # Support multiple chat_ids separated by comma
        chat_ids = [cid.strip() for cid in str(self.chat_id).split(',') if cid.strip()]
        
        for cid in chat_ids:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                "chat_id": cid,
                "text": text,
                "disable_web_page_preview": disable_web_page_preview
            }
            if parse_mode:
                data["parse_mode"] = parse_mode
            
            try:
                resp = requests.post(url, data=data, timeout=10)
                if resp.status_code != 200:
                    print(f"Failed to send telegram message to {cid}: {resp.text}")
            except Exception as e:
                print(f"Telegram connection error for {cid}: {e}")

    def send_compressed_market_data(self, data: dict):
        """
        使用 V6 极致压缩协议发送行情数据
        """
        try:
            from .compressor_utils import MarketDataPackerV6
            
            # 确保字典路径正确 (同级目录)
            dict_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "concept_dict.json")
            packer = MarketDataPackerV6(concept_dict_path=dict_path)
            
            # 执行压缩
            b64_str = packer.pack(data)
            
            # 1. 发送人类可读的详细文本报告
            report_text = self.format_report(data)
            self.send_message(report_text, disable_web_page_preview=True)

            # 2. 构造压缩数据包消息
            # 2. 构造压缩数据包消息
            # DEBUG: 使用可见的 Payload，纯文本发送
            visible_payload = f"Payload: http://p/{b64_str}\n" 
            
            msg = (
                f"{visible_payload}"
                f"Market Pulse\n"
                f"[{data.get('timestamp')}]\n"
                f"P3(>5%): {len(data.get('pool_3') or [])} | P2(>3.5%): {len(data.get('pool_2') or [])} | P1(LU>=3): {len(data.get('pool_1') or [])}\n"
                f"Lottery: {len(data.get('lottery_pool') or [])} | SmallCap: {len(data.get('small_cap_pool') or [])}\n"
                f"(Payload: {packer.stats['original_bytes']}B -> {packer.stats['compressed_bytes']}B)"
            )
            
            # 使用 parse_mode=None 发送纯文本，确保 Base64 不会报错
            return self.send_message(msg, disable_web_page_preview=True, parse_mode=None)
            
        except Exception as e:
            print(f"Failed to compress and send market data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def format_report(self, data: dict) -> str:
        """
        格式化 diff 报告
        """
        timestamp = data.get('timestamp')
        pool_1 = data.get('pool_1', [])
        pool_2 = data.get('pool_2', [])
        pool_3 = data.get('pool_3', [])
        lottery_pool = data.get('lottery_pool', [])
        knowledge_pool = data.get('small_cap_pool', [])
        
        time_str = str(timestamp).split(' ')[-1] if timestamp else "实时"
        msg = f"🔔 **板块异动监控** [{time_str}]\n"
        msg += "========================\n\n"
        
        # Helper to format concept list
        def fmt_c(c_list, label):
            if not c_list: return ""
            txt = f"{label} ({len(c_list)}个)\n"
            for c in c_list:
                name = c.get('concept_name')
                pct = c.get('pct_chg', 0)
                lu = c.get('limit_up_count', 0)
                txt += f"• **{name}** (+{pct:.2f}%) [🔥:{lu}]\n"
            txt += "\n"
            return txt

        # Display Pools (Only New items are passed here)
        # Deduplication Strategy: Show sector only in its highest pool
        
        # 1. Get names for filtering
        p3_names = {c['concept_name'] for c in pool_3}
        p2_names = {c['concept_name'] for c in pool_2}
        
        # 2. Filter Lists
        # P3: Show all
        display_p3 = pool_3
        # P2: Show if not in P3
        display_p2 = [c for c in pool_2 if c['concept_name'] not in p3_names]
        # P1: Show if not in P3 AND not in P2
        # Note: p2_names includes those in P3 if they qualified for P2, so just checking not in p2_names covers it? 
        # But wait, if a sector jumps to P3 directly, it is in P1, P2, P3.
        # So excluding p2_names removes it from P1. Correct.
        display_p1 = [c for c in pool_1 if c['concept_name'] not in p2_names and c['concept_name'] not in p3_names]

        if display_p3:
            msg += fmt_c(display_p3, "🚀 **[新] 爆发板块 (涨幅>5%)**")
        if display_p2:
            msg += fmt_c(display_p2, "⚡ **[新] 强势板块 (涨幅>3.5%)**")
        if display_p1:
            msg += fmt_c(display_p1, "🔥 **[新] 活跃板块 (涨停>=3)**")
            
        # Display Stocks
        if lottery_pool:
            msg += "🎯 **相关冲板个股**\n"
            for s in lottery_pool[:15]:
                code_short = s.get('code', '').split('.')[-1]
                name = s.get('name', '')
                pct = s.get('pct_chg', 0)
                msg += f"• `{code_short}` **{name}** (+{pct:.2f}%)\n"
            if len(lottery_pool) > 15:
                msg += f"  *(...共{len(lottery_pool)}只)*\n"
            msg += "\n"

        if knowledge_pool:
            msg += "💡 **相关 AI 知识库个股**\n"
            for s in knowledge_pool[:8]:
                name = s.get('name')
                code = s.get('code', '').split('.')[-1]
                pct = s.get('pct_chg', 0)
                topic = s.get('matched_topic', '') or s.get('concept_name', '')
                msg += f"- `{code}` **{name}** (+{pct:.2f}%) [{topic}]\n"
            msg += "\n"

        if not (pool_1 or pool_2 or pool_3 or lottery_pool or knowledge_pool):
             msg += "无新增异动。\n"
             
        return msg
