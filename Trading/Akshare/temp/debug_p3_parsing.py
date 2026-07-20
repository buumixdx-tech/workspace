
raw_response_str = """
{'text': '{"info_content": "公司已公告其电子级含氟冷却液产品可用于大数据中心浸没式冷却。", "linked_hotspots": [{"hotspot": "电子氟化液", "pattern": "直接产品", "analysis": "公司的电子级含氟冷却液属于电子氟化液类别，直接作为产品应用于数据中心冷却。"}]}'}
"""
# Note: The above string uses single quotes for the outer dict, and the inner JSON string is valid double-quoted JSON.

import json
import ast

def parse(result):
    print("--- Parsing Start ---")
    
    # 1. Fallback: Unwrap 'text'
    if "linked_hotspots" not in result and "text" in result:
        print("Found 'text' key, attempting to extract JSON...")
        raw_text = result["text"]
        # Basic cleanup
        if raw_text.startswith("```json"): raw_text = raw_text[7:]
        if raw_text.startswith("```"): raw_text = raw_text[3:]
        if raw_text.endswith("```"): raw_text = raw_text[:-3]
        
        parsed_inner = None
        try:
            parsed_inner = json.loads(raw_text.strip())
            print("Successfully parsed with json.loads")
        except:
            try:
                parsed_inner = ast.literal_eval(raw_text.strip())
                print("Successfully parsed with ast.literal_eval")
            except Exception as e:
                print(f"Failed to parse inner text: {e}")
        
        if isinstance(parsed_inner, dict):
            # MERGE or REPLACE?
            # If we replace, we lose original keys? It's fine.
            result = parsed_inner
            print(f"Result keys after unwrapping: {result.keys()}")

    # 2. Extract linked_hotspots
    linked = result.get("linked_hotspots")
    print(f"linked_hotspots raw value: {linked}")
    print(f"Type: {type(linked)}")
    
    # 3. Handle stringified list
    if isinstance(linked, str):
        print("linked_hotspots is string, parsing...")
        try:
            linked = json.loads(linked)
        except:
            try:
                linked = ast.literal_eval(linked)
            except Exception as e:
                print(f"Failed string parse: {e}")
                
    if not linked:
        print("linked_hotspots is empty or None.")
        return

    # 4. Check item structure
    for i, item in enumerate(linked):
        print(f"Item {i} keys: {item.keys()}")
        print(f"  Hotspot: {item.get('hotspot')}")
        print(f"  Pattern: {item.get('pattern')}")
        print(f"  Analysis: {item.get('analysis')}")

# Test Case 1: Python dict with inner JSON string (Simulating Dify output)
test_1 = ast.literal_eval(raw_response_str.strip())
parse(test_1)
