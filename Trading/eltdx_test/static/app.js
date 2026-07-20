// eltdx_test 前端主逻辑
// 轮询 /api/all 或 /api/kline，每 3 秒刷新一次；ECharts 渲染分时图或 K 线

(function () {
  'use strict';

  // —— 状态 ——
  let currentCode = '';
  let isPaused = false;
  let pollTimer = null;
  let lastFetchTime = null;
  let chart = null;
  let volumeChart = null;
  let mode = 'minute';            // 'minute' | 'kline'
  let period = 'day';             // K 线周期
  let adjust = 'qfq';             // 复权方式
  const REFRESH_MS = window.APP_CONFIG?.refresh_seconds
    ? window.APP_CONFIG.refresh_seconds * 1000
    : 3000;

  // —— DOM ——
  const $codeInput = document.getElementById('code-input');
  const $btnToggle = document.getElementById('btn-toggle');
  const $status    = document.getElementById('status');
  const $errBar    = document.getElementById('error-bar');

  // —— 工具：格式化 ——
  function fmtNum(v, d = 2) {
    if (v === null || v === undefined) return '--';
    return Number(v).toFixed(d);
  }
  function fmtInt(v) {
    if (v === null || v === undefined) return '--';
    return Math.round(Number(v)).toLocaleString();
  }
  function fmtAmount(v) {
    // 成交额是元，显示为「万」更友好
    if (v === null || v === undefined) return '--';
    const n = Number(v);
    if (n >= 1e8) return (n / 1e8).toFixed(2) + ' 亿';
    if (n >= 1e4) return (n / 1e4).toFixed(2) + ' 万';
    return n.toFixed(0);
  }
  function fmtTime(raw) {
    if (!raw || raw < 10000) return '--';
    // raw 形如 HHMMSS*100 或 HHMMSS —— 取决于字段
    // 实际 eltdx QuoteSnapshot.time_raw 接近 9263980 ≈ 09:26:39.80
    const total = Math.floor(raw / 1000);
    const hh = Math.floor(total / 10000);
    const mm = Math.floor((total % 10000) / 100);
    const ss = total % 100;
    const ms = raw % 1000;
    return `${String(hh).padStart(2,'0')}:${String(mm).padStart(2,'0')}:${String(ss).padStart(2,'0')}.${String(ms).padStart(3,'0')}`;
  }
  function changeClass(change) {
    if (change === null || change === undefined || change === 0) return 'flat';
    return change > 0 ? 'up' : 'down';
  }

  // —— 错误条 ——
  function showError(msg) {
    if (!msg) { $errBar.classList.add('hidden'); return; }
    $errBar.classList.remove('hidden');
    $errBar.textContent = msg;
  }

  // —— ECharts 初始化 ——
  // X 轴：剔除午休，只显示 4 小时交易时间
  //   - 数据用「距离开盘分钟数」(0=9:30, 120=11:30/13:00, 240=15:00)
  //   - 11:30 ↔ 13:00 在 X 轴上对应同一个位置（120），午休自然「刨去」
  // Y 轴：默认 ±(涨跌停/2)，若数据超出则拓展到 ±涨跌停
  const MORNING_MIN = 0;    // 09:30 → 0
  const NOON_MIN = 120;     // 11:30 / 13:00 → 120（午休前后接续）
  const CLOSE_MIN = 240;    // 15:00 → 240

  // 9 个时间锚点（开盘后每 30 分钟一个，最后两个跨午休）
  // 0 → 09:30, 30 → 10:00, 60 → 10:30, 90 → 11:00, 120 → 11:30|13:00,
  // 150 → 13:30, 180 → 14:00, 210 → 14:30, 240 → 15:00
  const TIME_TICKS = [0, 30, 60, 90, 120, 150, 180, 210, 240];

  function minuteToTimeLabel(min) {
    // 把「距开盘分钟数」还原成真实时间（用于 X 轴刻度 + 鼠标提示）
    if (min < 120) {
      const total = 9 * 60 + 30 + min;  // 09:30 + min
      const h = Math.floor(total / 60), m = total % 60;
      return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
    } else {
      const total = 13 * 60 + (min - 120);  // 13:00 + (min-120)
      const h = Math.floor(total / 60), m = total % 60;
      return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
    }
  }

  function timeLabelToMinute(label) {
    // "HH:MM" → 距开盘分钟数（剔除午休）
    if (!label || typeof label !== 'string') return null;
    const m = label.match(/^(\d{1,2}):(\d{2})$/);
    if (!m) return null;
    const h = parseInt(m[1]), mm = parseInt(m[2]);
    if (h < 12) return (h - 9) * 60 + mm - 30;       // 09:30=0 ... 11:30=120
    if (h >= 13) return 120 + (h - 13) * 60 + mm;    // 13:00=120 ... 15:00=240
    return null;  // 12:xx 午休期间不会有点
  }

  // 当前代码 + 昨收价 → Y 轴 bounds
  function computeYBounds(quote, limitPct) {
    const preClose = quote && quote.pre_close_price;
    if (!preClose || !limitPct) return null;
    const half = limitPct / 2;
    // 第一档：昨收 ± (limitPct/2)
    let lo = preClose * (1 - half);
    let hi = preClose * (1 + half);
    return { low: lo, high: hi, preClose, fullLow: preClose * (1 - limitPct), fullHigh: preClose * (1 + limitPct) };
  }

  function initChart() {
    chart = echarts.init(document.getElementById('chart'), null, { renderer: 'canvas' });
    chart.setOption({
      animation: false,
      grid: { left: 55, right: 20, top: 40, bottom: 40 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', label: { backgroundColor: '#374151' } },
        formatter: null,  // 分时/K线各自覆盖
      },
      legend: {
        data: ['价格', '均价', 'MA5', 'MA10', 'MA20', 'MA60'],
        top: 5,
        textStyle: { fontSize: 12 },
        selected: { 'MA5': true, 'MA10': true, 'MA20': true, 'MA60': false },
      },
      xAxis: {
        type: 'value',
        min: MORNING_MIN,
        max: CLOSE_MIN,
        interval: 30,
        axisLabel: {
          fontSize: 11,
          color: '#6b7280',
          formatter: (val) => minuteToTimeLabel(val),
        },
        axisLine: { lineStyle: { color: '#d1d5db' } },
        splitLine: { show: true, lineStyle: { type: 'dashed', color: '#f3f4f6' } },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { fontSize: 11, color: '#6b7280' },
        splitLine: { lineStyle: { type: 'dashed', color: '#e5e7eb' } },
      },
      series: [
        {
          name: '价格', type: 'line', data: [],
          smooth: false, symbol: 'none',
          lineStyle: { width: 1.5, color: '#dc2626' },
          itemStyle: { color: '#dc2626' },
        },
        {
          name: '均价', type: 'line', data: [],
          smooth: false, symbol: 'none',
          lineStyle: { width: 1, color: '#f59e0b', type: 'dashed' },
          itemStyle: { color: '#f59e0b' },
        },
        { name: 'MA5',  type: 'line', data: [] },
        { name: 'MA10', type: 'line', data: [] },
        { name: 'MA20', type: 'line', data: [] },
        { name: 'MA60', type: 'line', data: [] },
      ],
    });
    window.addEventListener('resize', () => chart.resize());
  }

  // 初始化成交量图
  function initVolumeChart() {
    volumeChart = echarts.init(document.getElementById('volume-chart'), null, { renderer: 'canvas' });
    // xAxis 根据当前 mode 决定类型
    const isMinute = (mode === 'minute');
    volumeChart.setOption({
      animation: false,
      grid: { left: 55, right: 20, top: 10, bottom: 25 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params) => {
          if (!params || !params.length) return '';
          const v = Array.isArray(params[0].data) ? params[0].data[1] : params[0].data;
          let label = params[0].axisValue;
          if (isMinute) label = minuteToTimeLabel(Math.round(label));
          return `<b>${label}</b><br>${params[0].marker} 成交量: <b>${fmtInt(v)}</b> 手`;
        },
      },
      xAxis: isMinute
        ? {
            type: 'value', min: MORNING_MIN, max: CLOSE_MIN, interval: 30,
            axisLabel: { fontSize: 10, color: '#6b7280', formatter: (v) => minuteToTimeLabel(v) },
            axisLine: { lineStyle: { color: '#d1d5db' } }, splitLine: { show: false },
          }
        : {
            type: 'category', data: [],
            axisLabel: { fontSize: 10, color: '#6b7280' },
            axisLine: { lineStyle: { color: '#d1d5db' } }, splitLine: { show: false },
          },
      yAxis: {
        type: 'value',
        axisLabel: {
          fontSize: 10, color: '#6b7280',
          formatter: (v) => v >= 1e8 ? (v/1e8).toFixed(1)+'亿' : v >= 1e4 ? (v/1e4).toFixed(0)+'万' : v,
        },
        splitLine: { lineStyle: { type: 'dashed', color: '#e5e7eb' } },
      },
      series: [
        {
          name: '成交量', type: 'bar', data: [],
          barWidth: isMinute ? '70%' : '60%',
          itemStyle: { color: '#dc2626' },
        },
      ],
    });
    window.addEventListener('resize', () => volumeChart.resize());
  }

  function renderMinute(minute, quote, limitPct) {
    if (!minute) return;
    const points = minute.points || [];

    // 数据点 → [距开盘分钟数, 价格]
    const prices = points
      .map(p => [timeLabelToMinute(p.time_label), p.price])
      .filter(([x, v]) => x != null && v != null);
    const avgs = points
      .map(p => [timeLabelToMinute(p.time_label), p.avg_price])
      .filter(([x, v]) => x != null && v != null);

    // 计算 Y 轴 bounds
    const bounds = computeYBounds(quote, limitPct);
    let yMin, yMax;
    if (bounds) {
      // 检查数据是否超出 ±half 范围
      let dataLo = Infinity, dataHi = -Infinity;
      points.forEach(p => {
        if (p.price != null) { dataLo = Math.min(dataLo, p.price); dataHi = Math.max(dataHi, p.price); }
        if (p.avg_price != null) { dataLo = Math.min(dataLo, p.avg_price); dataHi = Math.max(dataHi, p.avg_price); }
      });
      if (dataLo < bounds.low || dataHi > bounds.high) {
        // 超出 half → 拓展到 ±limit
        yMin = bounds.fullLow;
        yMax = bounds.fullHigh;
      } else {
        yMin = bounds.low;
        yMax = bounds.high;
      }
      // 至少留 0.5% 余量，避免曲线贴边
      const pad = (yMax - yMin) * 0.05;
      yMin -= pad; yMax += pad;
    }

    // 昨收线（markLine）
    const markLines = [];
    if (bounds && bounds.preClose) {
      markLines.push({
        yAxis: bounds.preClose,
        label: { formatter: `昨收 ${bounds.preClose.toFixed(2)}`, position: 'insideEndTop', fontSize: 10, color: '#6b7280' },
        lineStyle: { color: '#9ca3af', type: 'dotted', width: 1 },
      });
    }

    chart.setOption({
      yAxis: { min: yMin, max: yMax },
      series: [
        { name: '价格', data: prices, markLine: { silent: true, symbol: 'none', data: markLines } },
        { name: '均价', data: avgs },
      ],
    });

    // 元信息
    let meta = `日期 ${minute.trading_date || '--'} · ${minute.count || points.length} 个点`;
    if (points.length > 0) {
      const first = points[0].time_label;
      const last = points[points.length - 1].time_label;
      meta += ` · ${first} → ${last}`;
    } else {
      meta += ' · 等待开盘';
    }
    if (limitPct) {
      meta += ` · 涨跌停 ±${(limitPct * 100).toFixed(0)}%`;
    }
    document.getElementById('minute-meta').textContent = meta;
  }

  // 渲染成交量图（红涨绿跌）
  function renderVolume(minute) {
    if (!minute) return;
    const points = minute.points || [];
    if (points.length === 0) {
      volumeChart.setOption({ series: [{ name: '成交量', data: [] }] });
      document.getElementById('volume-meta').textContent = '等待开盘';
      return;
    }

    // 每分钟一根柱：颜色按本分钟价格相对前一分钟涨跌（首根对照今开/昨收）
    const ref0 = minute.open_price ?? minute.prev_close ?? points[0].price;
    const data = points.map((p, i) => {
      const min = timeLabelToMinute(p.time_label);
      if (min == null) return null;
      const refPrice = (i === 0) ? ref0 : points[i - 1].price;
      const color = (p.price != null && refPrice != null && p.price >= refPrice)
        ? '#dc2626'  // 涨 → 红
        : '#16a34a'; // 跌 → 绿
      return {
        value: [min, p.volume || 0],
        itemStyle: { color },
      };
    }).filter(Boolean);

    volumeChart.setOption({
      series: [{ name: '成交量', data }],
    });

    const total = points.reduce((s, p) => s + (p.volume || 0), 0);
    document.getElementById('volume-meta').textContent = `累计 ${fmtInt(total)} 手`;
  }

  // —— 渲染报价卡 ——
  function renderQuote(quote) {
    if (!quote) return;

    document.getElementById('quote-name').textContent =
      `${quote.exchange?.toUpperCase() || ''} ${quote.code || ''}`;
    document.getElementById('quote-code').textContent =
      `market_id=${quote.market_id ?? '-'} active=${quote.active1 ?? '-'}`;

    const last = quote.last_price;
    const pre  = quote.pre_close_price;
    const change = (last != null && pre != null) ? (last - pre) : null;
    const pct = (change != null && pre) ? (change / pre * 100) : null;
    const cls = changeClass(change);

    const $last = document.getElementById('last-price');
    $last.textContent = fmtNum(last, 2);
    $last.className = 'last-price ' + cls;

    const $change = document.getElementById('change');
    $change.textContent = change != null ? (change >= 0 ? '+' : '') + change.toFixed(2) : '--';
    $change.className = 'change ' + cls;

    const $pct = document.getElementById('change-pct');
    $pct.textContent = pct != null ? (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%' : '--';
    $pct.className = 'change-pct ' + cls;

    document.getElementById('quote-time').textContent = fmtTime(quote.time_raw);
    document.getElementById('open-price').textContent  = fmtNum(quote.open_price);
    document.getElementById('pre-close').textContent  = fmtNum(quote.pre_close_price);
    document.getElementById('high-price').textContent  = fmtNum(quote.high_price);
    document.getElementById('low-price').textContent   = fmtNum(quote.low_price);
    document.getElementById('volume-hand').textContent = fmtInt(quote.total_hand);
    document.getElementById('current-hand').textContent = fmtInt(quote.current_hand);
    document.getElementById('amount').textContent      = fmtAmount(quote.amount);

    const inout = `内 ${fmtInt(quote.inside_dish)} / 外 ${fmtInt(quote.outer_disc)}`;
    document.getElementById('inout').textContent = inout;
  }

  // —— 渲染五档盘口 ——
  function renderDepth(depth) {
    const records = depth?.records?.[0];
    if (!records) {
      document.getElementById('sell-rows').innerHTML = '';
      document.getElementById('buy-rows').innerHTML = '';
      document.getElementById('depth-meta').textContent = '无数据';
      return;
    }
    document.getElementById('depth-meta').textContent =
      `${records.code || ''} · ${records.exchange?.toUpperCase() || ''}`;

    // sell_levels: 卖1~卖5（价格从高到低）
    const sells = records.sell_levels || [];
    const buys  = records.buy_levels  || [];

    const sellRows = sells.slice().reverse().map((lv, i) => {
      const n = sells.length - i;
      return `<tr class="sell-row">
        <td>卖${n}</td>
        <td class="price">${fmtNum(lv.price, 2)}</td>
        <td>${fmtInt(lv.volume)}</td>
      </tr>`;
    }).join('');
    document.getElementById('sell-rows').innerHTML = sellRows;

    const lastPrice = records.last_price;
    const buyRows = buys.map((lv, i) => {
      const isCurrent = (lastPrice != null && lv.price === lastPrice);
      return `<tr class="buy-row ${isCurrent ? 'current' : ''}">
        <td>买${i+1}</td>
        <td class="price">${fmtNum(lv.price, 2)}</td>
        <td>${fmtInt(lv.volume)}</td>
      </tr>`;
    }).join('');
    document.getElementById('buy-rows').innerHTML = buyRows;
  }

  // —— 字段详情卡：把所有 QuoteSnapshot 字段平铺展示 ——
  function renderFields(quote) {
    if (!quote) return;
    const grid = document.getElementById('fields-grid');
    grid.innerHTML = '';

    // 简单字段
    const simpleKeys = [
      'exchange', 'market_id', 'code', 'active1',
      'last_price', 'pre_close_price', 'open_price', 'high_price', 'low_price',
      'time_raw', 'total_hand', 'current_hand', 'amount',
      'inside_dish', 'outer_disc',
    ];
    simpleKeys.forEach(k => {
      if (quote[k] !== undefined) {
        const item = document.createElement('div');
        item.className = 'field-item';
        item.innerHTML = `<span class="key">${k}</span>
          <span class="val">${formatFieldVal(quote[k])}</span>`;
        grid.appendChild(item);
      }
    });

    // 嵌套字段：买/卖五档
    ['buy_levels', 'sell_levels'].forEach(name => {
      const arr = quote[name];
      if (!Array.isArray(arr) || arr.length === 0) return;
      const item = document.createElement('div');
      item.className = 'field-item nested';
      const rows = arr.map((lv, i) =>
        `<div>[${i+1}] price=${fmtNum(lv.price)} vol=${fmtInt(lv.volume)}</div>`
      ).join('');
      item.innerHTML = `<span class="key">${name} (${arr.length} 档)</span>
        <div class="nested-list val">${rows}</div>`;
      grid.appendChild(item);
    });
  }

  function formatFieldVal(v) {
    if (v === null || v === undefined) return 'null';
    if (typeof v === 'number') {
      if (Number.isInteger(v)) return v.toLocaleString();
      return v.toFixed(4).replace(/\.?0+$/, '');
    }
    return v;
  }

  // —— K 线渲染 ——
  function renderKline(kline) {
    if (!kline || !kline.bars || kline.bars.length === 0) {
      chart.clear();
      showError('K线数据为空');
      return;
    }

    // eltdx 返回的就是升序（旧→新），直接用
    const barsAsc = kline.bars;

    // X 轴类目
    const xData = barsAsc.map(b => b.time ? b.time.slice(0, 10) : '');

    // 蜡烛图：ECharts 需要 [open, close, low, high]
    const candleData = barsAsc.map(b => [b.open, b.close, b.low, b.high]);

    // MA 计算（基于收盘价）
    function ma(n) {
      return xData.map((_, i) => {
        if (i < n - 1) return null;
        let sum = 0;
        for (let j = i - n + 1; j <= i; j++) sum += barsAsc[j].close;
        return +(sum / n).toFixed(3);
      });
    }
    const ma5  = ma(5);
    const ma10 = ma(10);
    const ma20 = ma(20);
    const ma60 = ma(60);

    // 成交量（供下方图用）
    renderKlineVolume(barsAsc, kline.adjust_mode);

    chart.setOption({
      xAxis: { type: 'category', data: xData, boundaryGap: true },
      yAxis: { scale: true },
      series: [
        {
          name: 'K线', type: 'candlestick', data: candleData,
          itemStyle: {
            color: '#dc2626',       // 阳线（涨）
            color0: '#16a34a',      // 阴线（跌）
            borderColor: '#dc2626',
            borderColor0: '#16a34a',
          },
        },
        { name: 'MA5',  type: 'line', data: ma5,  smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#fbbf24' } },
        { name: 'MA10', type: 'line', data: ma10, smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#3b82f6' } },
        { name: 'MA20', type: 'line', data: ma20, smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#a855f7' } },
        { name: 'MA60', type: 'line', data: ma60, smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#ec4899' } },
      ],
    });

    // 元信息
    const adjLabel = { qfq: '前复权', hfq: '后复权', none: '不复权' }[kline.adjust_mode] || kline.adjust_mode;
    const first = barsAsc[0].time.slice(0, 10);
    const last = barsAsc[barsAsc.length - 1].time.slice(0, 10);
    document.getElementById('minute-meta').textContent =
      `${adjLabel} · ${kline.count} 根 · ${first} → ${last}`;
  }

  function renderKlineVolume(barsAsc, adjustMode) {
    document.getElementById('volume-title').textContent = '成交量（K线）';
    // 红涨绿跌：颜色按 close vs open
    const data = barsAsc.map((b, i) => {
      const color = b.close >= b.open ? '#dc2626' : '#16a34a';
      return { value: b.volume || 0, itemStyle: { color } };
    });
    volumeChart.setOption({
      xAxis: { type: 'category', data: barsAsc.map(b => b.time ? b.time.slice(0, 10) : '') },
      yAxis: { type: 'value', axisLabel: { fontSize: 10, color: '#6b7280', formatter: v => v >= 1e4 ? (v/1e4).toFixed(0)+'万' : v } },
      series: [{ name: '成交量', type: 'bar', data, barWidth: '60%' }],
    });
    const total = barsAsc.reduce((s, b) => s + (b.volume || 0), 0);
    document.getElementById('volume-meta').textContent =
      `${adjustMode || 'none'} · 累计 ${fmtInt(total)} 手`;
  }

  // —— 主拉取 ——
  async function refresh() {
    if (isPaused) return;
    $status.textContent = '拉取中...';
    try {
      if (mode === 'minute') {
        const r = await fetch(`/api/all?code=${encodeURIComponent(currentCode)}`);
        const data = await r.json();

        if (data.errors && data.errors.length) {
          showError('部分接口失败：' + data.errors.join('；'));
        } else {
          showError(null);
        }

        if (data.quote)  renderQuote(data.quote);
        if (data.minute) {
          renderMinute(data.minute, data.quote, data.limit_pct);
          renderVolume(data.minute);
          document.getElementById('volume-title').textContent = '成交量';
        }
        if (data.depth)  renderDepth(data.depth);
        if (data.quote)  renderFields(data.quote);
      } else if (mode === 'kline') {
        // K 线刷新频率较低（每 30 秒），但保留兼容
        const r = await fetch(`/api/kline?code=${encodeURIComponent(currentCode)}&period=${period}&count=500&adjust=${adjust}`);
        const data = await r.json();
        if (data.ok) {
          showError(null);
          renderKline(data.data);
        } else {
          showError('K线失败：' + (data.error || '未知'));
        }
      }

      lastFetchTime = new Date();
      $status.textContent = `更新于 ${lastFetchTime.toLocaleTimeString()}`;
    } catch (e) {
      showError('拉取失败：' + e.message);
      $status.textContent = '错误';
    }
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    refresh();
    pollTimer = setInterval(refresh, REFRESH_MS);
  }

  // —— 切换代码 ——
  function switchCode(code) {
    currentCode = code.trim().toLowerCase();
    $codeInput.value = currentCode;
    $status.textContent = `切换到 ${currentCode}`;
    showError(null);
    startPolling();
  }

  // —— 事件绑定 ——
  $btnToggle.addEventListener('click', () => {
    isPaused = !isPaused;
    $btnToggle.textContent = isPaused ? '继续' : '暂停';
    $btnToggle.classList.toggle('paused', isPaused);
    $status.textContent = isPaused ? '已暂停' : '继续拉取';
  });

  $codeInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') switchCode($codeInput.value);
  });

  // —— 模式切换：分时 / K线 ——
  document.querySelectorAll('.mode-tabs .tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const newMode = btn.dataset.mode;
      if (newMode === mode) return;
      mode = newMode;
      document.querySelectorAll('.mode-tabs .tab').forEach(b => b.classList.toggle('active', b === btn));
      document.getElementById('kline-controls').classList.toggle('hidden', mode !== 'kline');
      // 重建图表实例（避免 ECharts 多次 init 同 DOM 警告）
      if (chart) { chart.dispose(); chart = null; }
      if (volumeChart) { volumeChart.dispose(); volumeChart = null; }
      initChart();
      initVolumeChart();
      startPolling();
    });
  });

  // K 线控件
  document.getElementById('period-select').addEventListener('change', (e) => {
    period = e.target.value;
    startPolling();
  });
  document.getElementById('adjust-select').addEventListener('change', (e) => {
    adjust = e.target.value;
    startPolling();
  });

  // —— 启动 ——
  initChart();
  initVolumeChart();
  switchCode(window.APP_DEFAULT_CODE || 'sz000001');

  // 加载代码表元信息
  loadStocksMeta();

  // 绑定搜索自动补全
  bindAutocomplete();

  async function loadStocksMeta() {
    try {
      const r = await fetch('/api/stocks/meta');
      const data = await r.json();
      if (data.ok) {
        const d = data.data;
        const dt = new Date(d.updated_at);
        const ago = humanizeAge(dt);
        document.getElementById('stocks-meta').textContent =
          `代码表 ${d.count} 只 · 更新于 ${dt.toLocaleString('zh-CN')} (${ago})`;
      }
    } catch (e) {
      document.getElementById('stocks-meta').textContent = '代码表加载失败';
    }
  }

  function humanizeAge(dt) {
    const ms = Date.now() - dt.getTime();
    const min = Math.floor(ms / 60000);
    if (min < 1) return '刚刚';
    if (min < 60) return `${min} 分钟前`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h} 小时前`;
    const d = Math.floor(h / 24);
    return `${d} 天前`;
  }

  // —— 自动补全 ——
  let searchTimer = null;
  let searchSeq = 0;          // 防过期响应
  let suggestItems = [];
  let suggestIdx = -1;

  function bindAutocomplete() {
    const $input = $codeInput;
    const $box = document.getElementById('suggestions');

    $input.addEventListener('input', () => {
      const q = $input.value.trim();
      clearTimeout(searchTimer);
      if (!q) { hideSuggestions(); return; }
      searchTimer = setTimeout(() => doSearch(q), 200);
    });

    $input.addEventListener('keydown', (e) => {
      if ($box.classList.contains('hidden')) {
        if (e.key === 'Enter') switchCode($input.value);
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        moveSuggest(1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        moveSuggest(-1);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (suggestIdx >= 0 && suggestItems[suggestIdx]) {
          pickSuggest(suggestItems[suggestIdx]);
        } else {
          switchCode($input.value);
          hideSuggestions();
        }
      } else if (e.key === 'Escape') {
        hideSuggestions();
      }
    });

    // 点外部关闭
    document.addEventListener('click', (e) => {
      if (!$box.contains(e.target) && e.target !== $input) {
        hideSuggestions();
      }
    });
  }

  async function doSearch(q) {
    const seq = ++searchSeq;
    try {
      const r = await fetch(`/api/stocks/search?q=${encodeURIComponent(q)}&limit=15`);
      const data = await r.json();
      if (seq !== searchSeq) return;  // 过期响应
      if (!data.ok || !data.data || data.data.length === 0) {
        renderSuggestionsEmpty(q);
      } else {
        renderSuggestions(data.data, q);
      }
    } catch (e) {
      hideSuggestions();
    }
  }

  function renderSuggestions(items, q) {
    suggestItems = items;
    suggestIdx = items.length > 0 ? 0 : -1;
    const $box = document.getElementById('suggestions');
    const ql = q.toLowerCase();

    const rows = items.map((it, i) => {
      // 高亮匹配片段
      const hlName = hl(it.name, q);
      const hlPy = it.name_pinyin ? hl(it.name_pinyin, ql, true) : '';
      const boardLabel = boardShort(it.board);
      return `
        <div class="item ${i === suggestIdx ? 'active' : ''}" data-i="${i}">
          <div>
            <span class="name">${hlName}</span>
            <span class="code">${it.code}${hlPy ? ' · ' + hlPy : ''}</span>
          </div>
          <span class="board">${boardLabel}</span>
        </div>`;
    }).join('');

    $box.innerHTML = `<div class="header">${items.length} 个匹配 · ↑↓ 选择 Enter 确认 Esc 取消</div>${rows}`;
    $box.classList.remove('hidden');

    // 点击选择
    $box.querySelectorAll('.item').forEach(el => {
      el.addEventListener('click', () => {
        const i = parseInt(el.dataset.i);
        pickSuggest(suggestItems[i]);
      });
      el.addEventListener('mouseenter', () => {
        suggestIdx = parseInt(el.dataset.i);
        $box.querySelectorAll('.item').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
      });
    });
  }

  function renderSuggestionsEmpty(q) {
    suggestItems = [];
    suggestIdx = -1;
    const $box = document.getElementById('suggestions');
    $box.innerHTML = `<div class="empty">无匹配：${escapeHtml(q)}</div>`;
    $box.classList.remove('hidden');
  }

  function hideSuggestions() {
    document.getElementById('suggestions').classList.add('hidden');
    suggestItems = [];
    suggestIdx = -1;
  }

  function moveSuggest(delta) {
    if (suggestItems.length === 0) return;
    suggestIdx = (suggestIdx + delta + suggestItems.length) % suggestItems.length;
    const $box = document.getElementById('suggestions');
    $box.querySelectorAll('.item').forEach((el, i) => {
      el.classList.toggle('active', i === suggestIdx);
    });
    // 滚动到可见
    const active = $box.querySelector('.item.active');
    if (active) active.scrollIntoView({ block: 'nearest' });
  }

  function pickSuggest(item) {
    currentCode = item.code;
    $codeInput.value = item.code;
    hideSuggestions();
    startPolling();
  }

  function hl(text, q, ci = false) {
    if (!q) return escapeHtml(text);
    const idx = ci ? text.toLowerCase().indexOf(q.toLowerCase()) : text.indexOf(q);
    if (idx < 0) return escapeHtml(text);
    return escapeHtml(text.slice(0, idx)) +
           '<b style="color:#dc2626">' + escapeHtml(text.slice(idx, idx + q.length)) + '</b>' +
           escapeHtml(text.slice(idx + q.length));
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function boardShort(b) {
    const m = {
      'sse_main_board': '沪主板',
      'sse_star_market': '科创板',
      'szse_main_board': '深主板',
      'szse_chinext': '创业板',
    };
    return m[b] || (b || '-');
  }
})();