import baostock as bs
import logging

class BaostockConnector:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BaostockConnector, cls).__new__(cls)
            cls._instance.is_logged_in = False
        return cls._instance

    def login(self):
        if not self.is_logged_in:
            lg = bs.login()
            if lg.error_code == '0':
                self.is_logged_in = True
                logging.info("Baostock login success.")
            else:
                logging.error(f"Baostock login failed: {lg.error_msg}")
                raise Exception(f"Baostock login failed: {lg.error_msg}")
        return self

    def logout(self):
        if self.is_logged_in:
            bs.logout()
            self.is_logged_in = False
            logging.info("Baostock logout success.")

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    @staticmethod
    def query_all_stock(date=None):
        """Helper to get all stock codes for a given date."""
        rs = bs.query_all_stock(day=date)
        data_list = []
        if rs.error_code == '0':
            while rs.next():
                data_list.append(rs.get_row_data())
        return data_list

    def get_price(self, code, start_date, end_date, frequency="d", adjust="3"):
        """
        Fetch historical K-line data for a single stock.
        """
        self.login()
        
        # adjust: "3"=no adjust? Baostock adjustflag: 1:hfq, 2:qfq, 3:default?
        # Actually in Baostock: adjustflag: 1：后复权， 2：前复权， 3：不复权
        # My map: 'qfq'->2, 'hfq'->1, 'none'->3
        adj_map = {'qfq': '2', 'hfq': '1', 'none': '3'}
        adj_flag = adj_map.get(adjust, '3') # Default to no adjust if unknown
        
        fields = "date,open,high,low,close,volume,amount,adjustflag,turn,pctChg"
        rs = bs.query_history_k_data_plus(
            code, fields,
            start_date=start_date, end_date=end_date,
            frequency=frequency, adjustflag=adj_flag
        )
        
        data_list = []
        import pandas as pd
        if rs.error_code == '0':
            while rs.next():
                data_list.append(rs.get_row_data())
                
        if not data_list:
            return pd.DataFrame()
            
        df = pd.DataFrame(data_list, columns=fields.split(','))
        
        # Convert numeric columns
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Filter out empty stocks (volume=0 or price='')
        # df = df[df['volume'] > 0]
        
        return df
