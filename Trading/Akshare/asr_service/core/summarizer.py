import ollama
import os

class Summarizer:
    def __init__(self, model="qwen:1.7b", host="http://127.0.0.1:11434"):
        self.client = ollama.Client(host=host)
        self.model = model

    def chunk_text(self, text, size=1500):
        """
        Split text into overlapping chunks.
        """
        return [text[i:i + size] for i in range(0, len(text), size)]

    def summarize_chunk(self, chunk_text):
        """
        Clean and summarize a single chunk of text.
        """
        prompt = f"""你是一个专业的文档整理专家。请对以下识别出的原始语音转录文本进行处理：
1. 修正明显的错别字。
2. 去除语气助词、冗余重复词。
3. 保持原意的前提下，将其改写为流畅、书面化的表达。

待处理文本：
{chunk_text}

处理后的文本："""
        
        response = self.client.generate(model=self.model, prompt=prompt)
        return response['response']

    def final_summary(self, combined_text):
        """
        Generate a structured final summary from cleaned chunks.
        """
        prompt = f"""基于以下整理后的文本，请输出一份结构化的会议/语音摘要。
要求：
1. 使用 Markdown 格式。
2. 包含核心摘要、主要内容要点、待办事项（如有）。
3. 语言精炼准确。

正文内容：
{combined_text}

结构化摘要："""
        
        response = self.client.generate(model=self.model, prompt=prompt)
        return response['response']
