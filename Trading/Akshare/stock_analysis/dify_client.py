import requests
import json
import time
import os
import toml

def _get_dify_config():
    """从根目录 config.toml 加载 Dify 配置"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.toml")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = toml.load(f).get("dify", {})
        return (
            config.get("hotspot_api_key"), 
            config.get("base_url"), 
            config.get("sector_hook_api_key"),
            config.get("max_workers", 8),
            config.get("hotspot_2_api_key"),
            config.get("gemini_analysis_api_key")
        )

HOTSPOT_API_KEY, DIFY_BASE_URL, SECTOR_HOOK_API_KEY, MAX_WORKERS, HOTSPOT_2_API_KEY, GEMINI_ANALYSIS_API_KEY = _get_dify_config()

def call_stock_analysis_workflow(stock_code, stock_name=None):
    api_url = f"{DIFY_BASE_URL}/v1/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {HOTSPOT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": {
            "code": stock_code,
            "stock": stock_name
        },
        "response_mode": "blocking",
        "user": "analysis-module"
    }
    return _execute_dify_request(api_url, headers, payload)

def call_sector_hook_workflow(description):
    api_url = f"{DIFY_BASE_URL}/v1/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {SECTOR_HOOK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": {
            "stock_info": description
        },
        "response_mode": "blocking",
        "user": "sector-hook-module"
    }
    return _execute_dify_request(api_url, headers, payload)

def call_hotspot_2_workflow(description):
    """
    Call the new workflow for Processor 3 using HOTSPOT_2_API_KEY.
    """
    api_url = f"{DIFY_BASE_URL}/v1/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {HOTSPOT_2_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": {
            "stock_info": description
        },
        "response_mode": "blocking",
        "user": "hotspot-2-module"
    }
    return _execute_dify_request(api_url, headers, payload)

def call_gemini_analysis_workflow(stock_code):
    """
    Call the Gemini stock analysis workflow using GEMINI_ANALYSIS_API_KEY.
    Input requires 'stock_code'. Returns raw markdown text instead of forcing JSON.
    """
    api_url = f"{DIFY_BASE_URL}/v1/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {GEMINI_ANALYSIS_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": {
            "stock_code": stock_code
        },
        "response_mode": "blocking",
        "user": "gemini-analysis-module"
    }
    # For long workflows, use a custom request wrapper with prolonged timeout and no JSON enforcement
    return _execute_dify_markdown_request(api_url, headers, payload)

def _execute_dify_markdown_request(api_url, headers, payload, max_retries=3):
    last_error = ""
    for attempt in range(max_retries):
        try:
            # 20 minutes (1200s) read timeout for Gemini long workflow
            response = requests.post(api_url, headers=headers, json=payload, timeout=(10, 1200))
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("status") == "failed":
                return False, f"Dify Error: {result.get('error', 'Unknown Error')} (Tokens: {result.get('total_tokens')})"
                
            if result.get("data") and result["data"].get("outputs"):
                outputs = result["data"]["outputs"]
                
                candidate_keys = ["text", "result", "output", "markdown", "report"]
                raw_output = ""
                for key in candidate_keys:
                    if key in outputs:
                        raw_output = outputs[key]
                        break
                
                if not raw_output and outputs:
                    raw_output = list(outputs.values())[0]

                if isinstance(raw_output, str):
                    return True, raw_output
                else:
                    try:
                        return True, json.dumps(raw_output, ensure_ascii=False)
                    except:
                        return True, str(raw_output)
            else:
                return False, f"Invalid Dify response format: {result}"
                
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = str(e)
            print(f"  [Dify-Gemini] Attempt {attempt+1}/{max_retries} failed (Network/Timeout). Retrying in 10s...")
            time.sleep(10)
            continue
        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 500:
                last_error = f"HTTP {e.response.status_code}"
                print(f"  [Dify-Gemini] Attempt {attempt+1}/{max_retries} failed with {last_error}. Retrying in 10s...")
                time.sleep(10)
                continue
            return False, f"HTTP Error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return False, f"Request failed: {str(e)}"
            
    return False, f"Failed after {max_retries} attempts. Last error: {last_error}"

def _execute_dify_request(api_url, headers, payload, max_retries=3):
    last_error = ""
    for attempt in range(max_retries):
        try:
            # Timeout: connect 10s, read 120s
            response = requests.post(api_url, headers=headers, json=payload, timeout=(10, 120))
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("data") and result["data"].get("outputs"):
                outputs = result["data"]["outputs"]
                
                # Common keys in Dify workflows
                candidate_keys = ["text", "result", "output", "json", "json_output", "answer"]
                raw_output = ""
                for key in candidate_keys:
                    if key in outputs:
                        raw_output = outputs[key]
                        break
                
                if not raw_output and outputs:
                    raw_output = list(outputs.values())[0]

                if not isinstance(raw_output, str):
                    return True, raw_output

                # Clean up markdown code blocks
                cleaned = raw_output.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                    
                try:
                    parsed_json = json.loads(cleaned.strip())
                    return True, parsed_json
                except json.JSONDecodeError:
                    return False, f"Output is not valid JSON: {raw_output[:200]}..."
            else:
                return False, f"Invalid Dify response format: {result}"
                
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = str(e)
            print(f"  [Dify] Attempt {attempt+1}/{max_retries} failed (Network/Timeout). Retrying in 2s...")
            time.sleep(2)
            continue
        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 500:
                last_error = f"HTTP {e.response.status_code}"
                print(f"  [Dify] Attempt {attempt+1}/{max_retries} failed with {last_error}. Retrying in 2s...")
                time.sleep(2)
                continue
            return False, f"HTTP Error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return False, f"Request failed: {str(e)}"
            
    return False, f"Failed after {max_retries} attempts. Last error: {last_error}"
