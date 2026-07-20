
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from storage.ck_client import ck_client

new_tables = [
    'analysis_hot_topic_mapping',
    'concept_snapshot_intraday',
    'dict_concept_mapping',
    'finance_concept_components',
    'finance_concept_main',
    'view_concept_components_filtered',
    'view_selected_concept_list'
]

for t in new_tables:
    print(f"--- {t} ---")
    cols = ck_client.query_df(f"SELECT name, type, comment FROM system.columns WHERE database = 'stock_data' AND table = '{t}' ORDER BY position")
    print(cols)
    print()
