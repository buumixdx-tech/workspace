CREATE OR REPLACE VIEW stock_data.view_strategy_flu_pool AS
WITH
    -- 1. 从参数表读取动态参数
    params AS (
        SELECT 
            end_date AS dt,
            upper_limit AS up_lim,
            lower_limit AS low_lim
        FROM stock_data.strategy_flu_params
        LIMIT 1
    ),

    -- 2. 确定 T 日：end_date 之前最后一个交易日
    T_date AS (
        SELECT max(date) AS t_date
        FROM stock_data.index_k
        WHERE date <= (SELECT dt FROM params)
    ),
    T_date_scalar AS (
        SELECT (SELECT t_date FROM T_date) AS t_dt
    ),

    -- 3. 获取 T-5 到 T 日的 6 个最近交易日
    relevant_trading_days AS (
        SELECT
            date AS trade_date,
            row_number() OVER (ORDER BY date DESC) AS days_ago_rank
        FROM (
            SELECT DISTINCT date
            FROM stock_data.daily_k
            WHERE date <= (SELECT t_dt FROM T_date_scalar)
        ) AS unique_dates
        ORDER BY date DESC
        LIMIT 6
    ),

    -- 4. T-5 到 T 日的交易日列表
    trading_days_T_5_to_T AS (
        SELECT trade_date
        FROM relevant_trading_days
        WHERE days_ago_rank BETWEEN 1 AND 6
    ),

    -- 5. 步骤2：T-5 到 T 日连续交易的股票，且在股票池中
    valid_stocks_step2 AS (
        SELECT 
            k.code AS stock_code  -- ✅ 显式命名，避免 vs.code 无法解析
        FROM stock_data.daily_k AS k
        INNER JOIN trading_days_T_5_to_T AS td ON k.date = td.trade_date
        INNER JOIN stock_data.strategy_flu_stock_pool AS pool ON k.code = pool.code
        WHERE k.tradestatus = 1
        GROUP BY k.code
        HAVING count(*) = 6
    ),

    -- 6. 步骤3：T-5 到 T-2 日（rank 3~6）有且仅有一次涨停
    trading_days_T_5_to_T_2 AS (
        SELECT trade_date
        FROM relevant_trading_days
        WHERE days_ago_rank BETWEEN 3 AND 6
    ),
    stocks_with_one_limit_up AS (
        SELECT
            dk.code AS stock_code,
            any(dk.date) AS limit_up_date
        FROM stock_data.daily_k AS dk  -- ✅ 使用 dk 避免与 k 冲突
        INNER JOIN trading_days_T_5_to_T_2 AS td ON dk.date = td.trade_date
        INNER JOIN valid_stocks_step2 AS vs ON dk.code = vs.stock_code  -- ✅ 使用 vs.stock_code
        WHERE dk.price_status = 1
        GROUP BY dk.code
        HAVING count(*) = 1
    ),

    -- 7. 步骤4：获取 L+1 到 T 日的 open 和 close 价格
    trading_days_L_plus_1_to_T AS (
        SELECT 
            k.code AS stock_code, 
            k.open, 
            k.close
        FROM stock_data.daily_k AS k
        INNER JOIN stocks_with_one_limit_up AS lu 
            ON k.code = lu.stock_code 
            AND k.date > lu.limit_up_date 
            AND k.date <= (SELECT t_dt FROM T_date_scalar)
        WHERE k.tradestatus = 1
    ),
    price_ranges_after_limit AS (
        SELECT
            stock_code,
            greatest(max(open), max(close)) AS high_after_limit,
            least(min(open), min(close)) AS low_after_limit
        FROM trading_days_L_plus_1_to_T
        GROUP BY stock_code
    ),

    -- 8. 获取涨停日（L日）的封板价和前一日收盘价
    limit_up_info AS (
        SELECT
            k.code AS stock_code,
            k.close AS limit_up_close_price,
            k.preclose AS pre_limit_up_preclose
        FROM stock_data.daily_k AS k
        INNER JOIN stocks_with_one_limit_up AS lu 
            ON k.code = lu.stock_code AND k.date = lu.limit_up_date
    )

-- 9. 最终结果：计算回撤并过滤
SELECT
    pr.stock_code AS code,
    lu.limit_up_close_price,
    pr.high_after_limit,
    pr.low_after_limit,
    lu.pre_limit_up_preclose,
    -- 板后最高价回撤幅度
    (lu.limit_up_close_price - pr.high_after_limit) / (lu.limit_up_close_price - lu.pre_limit_up_preclose) AS high_drawdown,
    -- 板后最低价回撤幅度
    (lu.limit_up_close_price - pr.low_after_limit) / (lu.limit_up_close_price - lu.pre_limit_up_preclose) AS low_drawdown
FROM price_ranges_after_limit AS pr
INNER JOIN limit_up_info AS lu 
    ON pr.stock_code = lu.stock_code
WHERE
    -- 防止除以零
    (lu.limit_up_close_price != lu.pre_limit_up_preclose)
    AND
    -- 回撤幅度 >= 下限
    ((lu.limit_up_close_price - pr.high_after_limit) / (lu.limit_up_close_price - lu.pre_limit_up_preclose)) >= (SELECT low_lim FROM params)
    AND
    -- 回撤幅度 <= 上限
    ((lu.limit_up_close_price - pr.low_after_limit) / (lu.limit_up_close_price - lu.pre_limit_up_preclose)) <= (SELECT up_lim FROM params)
ORDER BY code;