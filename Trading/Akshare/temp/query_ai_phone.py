from market.ck_client import ClickHouseClient

def list_ai_phone_stocks():
    ck = ClickHouseClient()
    sql = """
    SELECT 
        c.stock_code, 
        s.symbol as name
    FROM finance_concept_components c 
    LEFT JOIN securities_info s ON c.stock_code = s.code 
    WHERE c.concept_name = 'AI手机'
    """
    df = ck.query_df(sql)
    print(df.to_string(index=False))
    ck.close()

if __name__ == "__main__":
    list_ai_phone_stocks()
