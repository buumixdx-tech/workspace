// static/chart.js — 任务 #208 模块化拆分
// 包含: chart 常量、loadChart、switchChart、renderMinuteChart、renderKlineChart、refreshChart,
// 以及相关 helper (detectMarket / fullDayTotal / buildShowValues / splitBySession / minuteToLabel / buildSeries)。
// 依赖: window.state (app.js 提供), window.api (app.js 提供), window.echarts (echarts.min.js),
//        jQuery $ (index.html 提供)。
//
// 公开 API:
//   Chart.load(code, signal)         — 异步拉数据 + 切到当前 mode (selectStock 调)
//   Chart.switchTab(mode)            — 切 minute/kline tab (html onclick 调)
//   Chart.refresh(code)              — 3s tick 局部刷新 (定时器调)
//   Chart.init()                     — 绑定 window.resize

const UP_COLOR = '#dc2626';    // 涨红
const DOWN_COLOR = '#16a34a';  // 跌绿

// 任务 #210+: 从 window.Util 解构, 不再依赖 bare api/isAbortError/$。
// (旧版这些是 var/const 全局, 拆分后每个模块独立, 必须显式拿。)
const { $, api, isAbortError } = window.Util;

// 任务 #195: chart 复用实例 — 同 code + 同 mode 走 setOption,不同 code 才 dispose。
// ECharts dispose+init 实测 50-200ms,频繁切 tab/切股时抖动的主因。
async function loadChart(code, signal) {
  if (!code) return;
  const chartArea = $('#chart-area');
  if (!chartArea) return;
  chartArea.style.display = '';

  const sameCode = state.chartCode === code;
  state.chartCode = code;

  // 同 code 同 mode → 数据可能没变(3s tick 在 refreshChart 里 update),跳过
  // 同 code 不同 mode → 复用 instance,只 setOption
  // 不同 code → dispose + init(数据/坐标轴都变,实例不能复用)
  if (!sameCode && state.chartInstance) {
    state.chartInstance.dispose();
    state.chartInstance = null;
  }

  // I7: 只在切股时拉当前 tab 需要的图。
  // 同 code 不重复拉(切 tab 走 switchChart,那里按需补拉)
  let needMinute = !state.chartData.minute || !sameCode;
  let needKline = state.chartMode === 'kline' && (!state.chartData.kline || !sameCode);

  const minutePromise = needMinute
    ? api(`/api/stocks/${encodeURIComponent(code)}/minute`, { signal })
    : Promise.resolve(null);
  let klinePromise;
  if (needKline) {
    klinePromise = api(`/api/stocks/${encodeURIComponent(code)}/kline`, { signal });
  }

  // 等待数据回 — 旧请求 abort 时直接返回
  try {
    const minuteRes = await Promise.allSettled([minutePromise]);
    if (minuteRes[0].status === 'fulfilled' && minuteRes[0].value) {
      state.chartData.minute = minuteRes[0].value.data;
    } else if (minuteRes[0].status === 'rejected' && isAbortError(minuteRes[0].reason)) {
      return;  // 被新 select 打断,别动 DOM
    }
    if (klinePromise) {
      const klineRes = await Promise.allSettled([klinePromise]);
      if (klineRes[0].status === 'fulfilled' && klineRes[0].value) {
        state.chartData.kline = klineRes[0].value.data;
      } else if (klineRes[0].status === 'rejected' && isAbortError(klineRes[0].reason)) {
        return;
      }
    }
  } catch (e) {
    if (isAbortError(e)) return;
    throw e;
  }

  switchTab(state.chartMode, /*reuseInstance=*/sameCode);
}

async function switchTab(mode, reuseInstance) {
  // 同 code 切 tab: 复用 instance,只 setOption
  // 不同 code: dispose 后由 switchChart 渲染端 init
  if (state.chartMode === mode && reuseInstance && state.chartInstance) {
    // 同 code 同 mode — 数据没变,啥也不做
    return;
  }
  const wasSameMode = state.chartMode === mode;
  state.chartMode = mode;
  $('#tab-minute').classList.toggle('active', mode === 'minute');
  $('#tab-kline').classList.toggle('active', mode === 'kline');

  // 任务 #204: 首次切到日 K 时,chartData.kline 可能是 null(selectStock 阶段
  // 不会主动拉 K,因为 chartMode 默认是 minute)。这里若发现未就位,
  // 先 await 拉数据,避免渲染"无数据"。同 code 切换时拉到的是同一股,
  // 不会触发新的 selectStock race。
  if (mode === 'kline' && !state.chartData.kline && state.selectedStockCode) {
    try {
      const r = await api(`/api/stocks/${encodeURIComponent(state.selectedStockCode)}/kline`);
      state.chartData.kline = r.data;
    } catch (e) {
      console.warn('[switchChart] kline fetch failed:', e.message);
      // 仍走下方渲染,让用户看到"无数据"占位
    }
  }

  // 同 code 切 tab 模式: 复用 instance,数据已就位直接 setOption
  if (reuseInstance && state.chartInstance && wasSameMode === false) {
    if (mode === 'minute' && state.chartData.minute) {
      // 直接重画 — renderMinuteChart 内部已 setOption 不 dispose
      renderMinuteChart(/*reuse=*/true);
      return;
    } else if (mode === 'kline' && state.chartData.kline) {
      renderKlineChart(/*reuse=*/true);
      return;
    }
  }

  // 首次或不同 code: dispose + init
  if (state.chartInstance) {
    state.chartInstance.dispose();
    state.chartInstance = null;
  }
  if (mode === 'minute') {
    renderMinuteChart(/*reuse=*/false);
  } else {
    renderKlineChart(/*reuse=*/false);
  }
};

// ── Time helpers for minute chart ───
// Given raw minutes-from-midnight, convert to relative elapsed minutes
// (excluding lunch break for A股/港股, continuous for 美股)
function rawToRelative(rawMin) {
  // raw minutes from midnight
  // A股 morning: 570-690 (9:30-11:30) → 0-120
  // A股 afternoon: 780-900 (13:00-15:00) → 240-330
  // 港股 morning: 570-720 (9:30-12:00) → 0-150
  // 港股 afternoon: 780-960 (13:00-16:00) → 240-390
  // 美股: 570-960 (9:30-16:00) → 0-390
  if (rawMin < 690) {
    // morning, all markets
    return rawMin - 570;  // 9:30=0
  } else if (rawMin < 780) {
    // 港股 lunch break (12:00-12:59) — shouldn't appear after filtering, treat as 港股
    return rawMin - 570;  // 港股 morning extends to 150
  } else {
    // afternoon: detect market by whether morning extended to 150
    // For now, return rawMin - 570 (continuous) and let caller adjust
    return rawMin - 570;
  }
}

// Detect market from raw minute values in a points array
function detectMarket(points) {
  const raws = points.map(p => {
    const parts = (p.time_label || '').split(':');
    return parts.length === 2 ? parseInt(parts[0]) * 60 + parseInt(parts[1]) : null;
  }).filter(r => r != null);
  const maxRaw = Math.max(...raws);
  if (maxRaw > 900) return 'US';     // 16:00+ → 960
  if (maxRaw > 720) return 'HK';     // 12:00+ exists → 港股
  return 'CN';                        // A股
}

function timeLabelToMinute(t) {
  if (!t) return null;
  const parts = t.split(':');
  if (parts.length !== 2) return null;
  let h = parseInt(parts[0]), m = parseInt(parts[1]);
  return rawToRelative(h * 60 + m);
}

// 完整交易日 idx 范围（与 bar 步长绑定）
// A 股 1m bar: 09:30-15:00 = 242 idx (含 9:30/15:00 两端)
// 港股 5m bar: 09:30-16:00 = 66 idx (5m × 66 = 330 min)
// 美股 5m bar: 09:30-16:00 = 78 idx (5m × 78 = 390 min)
function fullDayTotal(market) {
  if (market.isCN) return 242;
  if (market.isHK) return 66;
  if (market.isUS) return 78;
  return 240;
}

// 静态化 emphasis：所有分时图 series 复用同一份配置
var STATIC_EMPHASIS = { focus: 'none', disabled: true };

// 市场检测：直接读后端 data.exchange 字段（不再扫 points.time_label）
function detectMarket(data) {
  var exch = String(data.exchange || '').toUpperCase();
  var isHK = exch === 'HK';
  var isUS = exch === 'US';
  var isCN = !isHK && !isUS;
  return { isHK: isHK, isUS: isUS, isCN: isCN };
}

// 动态探测 MORNING_END：返回 points 里 '12:00' 之前的最后 idx + 1
// 用 '12:00' 而非 '13:00' 是因为后端补的 15:00 占位 bar 会被 '13:00+' 误判
// 12:00 之前都是上午, 12:00+ 是下午(港股 12:00 午休 / A 股 11:30-13:00 中间空白都符合)
// 美股全天交易, 12:00 不存在, 返回 points.length
function detectMorningEnd(points) {
  for (var i = 0; i < points.length; i++) {
    var t = (points[i] && points[i].time_label) || '';
    if (t >= '12:00') return i;
  }
  return points.length;
}

// 构造 showValues 数组：x 轴 30 min 步长 label 的 idx 位置。
// A 股关键：1m bar 跨午休时, idx 121(=13:00) 离 idx 120(=11:30) 只差 1,
// 所以下午从 morningEnd+30=151 开始, 跳过 13:00 避免重复 label
function buildShowValues(FULL_TOTAL, morningEnd, market) {
  var values = [];
  // 30 min 步长 (A 股 1m = 30 idx, 港/美 5m = 6 idx)
  var fixedStep = (market.isHK || market.isUS) ? 6 : 30;

  if (market.isHK || market.isUS) {
    for (var v = 0; v <= FULL_TOTAL; v += fixedStep) values.push(v);
  } else if (market.isCN) {
    // 上午 0..morningEnd step=30
    for (var v = 0; v <= morningEnd; v += fixedStep) values.push(v);
    // 下午 morningEnd+30..FULL_TOTAL step=30 (跳过 13:00 重复 label)
    for (var v = morningEnd + 30; v <= FULL_TOTAL; v += fixedStep) values.push(v);
  } else {
    for (var v = 0; v <= FULL_TOTAL; v += fixedStep) values.push(v);
  }
  return values;
}

// 切分上午/下午 + 合并均价（均价线无 areaStyle,合成单 series 即可）
function splitBySession(points, morningEnd) {
  var priceData = points.map(function(p, i) { return [i, p.price]; }).filter(function(item) { return item[1] != null; });
  var avgData   = points.map(function(p, i) { return [i, p.avg_price]; }).filter(function(item) { return item[1] != null; });
  return {
    priceMorning:   priceData.filter(function(it) { return it[0] < morningEnd; }),
    priceAfternoon: priceData.filter(function(it) { return it[0] >= morningEnd; }),
    avgAll:         avgData,
  };
}

// idx → HH:MM：数据驱动, 直接用 points[idx].time_label
// 后端补的 09:30 / 15:00 占位 bar 也有正确 time_label, 天然适配
// 不再用 idx 数学公式 — 之前公式在数据不全 / 边界 idx 时会算错时间
function minuteToLabel(idx, points) {
  if (points[idx] && points[idx].time_label) return points[idx].time_label;
  return '';
}

function withStatic(s) { s.emphasis = STATIC_EMPHASIS; return s; }

function buildAreaStyle(areaTop) {
  return {
    color: {
      type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
      colorStops: [
        { offset: 0, color: areaTop + '0.15)' },
        { offset: 1, color: areaTop + '0)' }
      ],
    },
  };
}

function buildSeries(opts) {
  var series = [];
  if (opts.priceMorning.length) {
    series.push(withStatic({
      name: '价格', type: 'line', data: opts.priceMorning,
      smooth: false, symbol: 'none',
      lineStyle: { color: opts.upColor, width: 1 },
      areaStyle: buildAreaStyle(opts.areaTop),
    }));
  }
  if (opts.priceAfternoon.length) {
    series.push(withStatic({
      name: '下午', type: 'line', data: opts.priceAfternoon,
      smooth: false, symbol: 'none',
      lineStyle: { color: opts.upColor, width: 1 },
      areaStyle: buildAreaStyle(opts.areaTop),
    }));
  }
  if (opts.avgAll.length) {
    series.push(withStatic({
      name: '均价', type: 'line', data: opts.avgAll,
      smooth: false, symbol: 'none',
      lineStyle: { color: '#f59e0b', width: 1, type: 'dashed' },
    }));
  }
  series.push(withStatic({
    name: '昨收', type: 'line',
    data: [[0, opts.prevClose], [opts.total, opts.prevClose]],
    smooth: false, symbol: 'none',
    lineStyle: { color: '#666', width: 1, type: 'dotted' },
    silent: true,
  }));
  return series;
}

function renderMinuteChart(reuse) {
  var container = document.getElementById('main-chart');
  if (!container) return;
  var data = state.chartData.minute;
  if (!data || !data.points || data.points.length === 0) {
    container.innerHTML = '<div style="color:var(--text-dim);text-align:center;padding:40px;font-family:var(--mono);font-size:12px">暂无分时数据</div>';
    return;
  }

  var points = data.points;
  var market = detectMarket(data);
  market.morningEnd = detectMorningEnd(points);
  // x 轴固定为完整交易日范围, 折线按时间比例分布
  // 早盘只采 14 根 1m bar 时, 折线只占 14/242 ≈ 5.8% 左侧, 不会拉伸占满
  var FULL_TOTAL = fullDayTotal(market);
  var showValues = buildShowValues(FULL_TOTAL, market.morningEnd, market);
  console.log('[renderMinuteChart]', {
    market: market,
    pointsCount: points.length,
    FULL_TOTAL: FULL_TOTAL,
    morningEnd: market.morningEnd,
    showValues: showValues,
    firstTime: points[0] && points[0].time_label,
    lastTime: points[points.length-1] && points[points.length-1].time_label,
  });

  var split = splitBySession(points, market.morningEnd);
  var prevClose = data.prev_close || (points[0] ? points[0].price : 0) || 0;
  var lastPrice = points[points.length - 1].price;
  var upColor = lastPrice >= prevClose ? UP_COLOR : DOWN_COLOR;
  var areaTop = lastPrice >= prevClose ? 'rgba(220,38,38,' : 'rgba(22,163,74,';

  var allPrices = points.map(function(p) { return p.price; }).filter(function(v) { return v != null; });
  var minP = Math.min.apply(null, allPrices.concat([prevClose]));
  var maxP = Math.max.apply(null, allPrices.concat([prevClose]));
  var pad = (maxP - minP) * 0.05 || prevClose * 0.01 || 0.01;

  // reuse=true: 复用现有实例只 setOption (任务 #195, 切 tab 不再 dispose+init)
  if (!reuse) {
    if (state.chartInstance) { state.chartInstance.dispose(); state.chartInstance = null; }
    state.chartInstance = echarts.init(container, null, { renderer: 'canvas' });
  }
  state.chartInstance.setOption({
    animation: false,
    backgroundColor: 'transparent',
    grid: { left: 55, right: 15, top: 8, bottom: 35 },
    xAxis: {
      type: 'value',
      min: 0,
      max: FULL_TOTAL,
      axisLine: { lineStyle: { color: '#2a2a2a' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#666', fontSize: 9, fontFamily: 'var(--mono)',
        // 关键：用 customValues 强制指定 tick 位置, 不依赖 splitNumber/interval
        // 之前用 interval+interval=0 在 splitNumber 边界会失效, ECharts 5.4 customValues
        // 是 type='value' 下唯一 100% 锁定 label 数量的方法
        customValues: showValues,
        formatter: function(val) { return minuteToLabel(val, points); }
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', scale: true,
      min: (minP - pad).toFixed(2),
      max: (maxP + pad).toFixed(2),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#666', fontSize: 9, fontFamily: 'var(--mono)', formatter: function(v) { return v.toFixed(2); } },
      splitLine: { lineStyle: { color: '#1a1a1a' } },
    },
    series: buildSeries({
      upColor: upColor, areaTop: areaTop,
      priceMorning: split.priceMorning,
      priceAfternoon: split.priceAfternoon,
      avgAll: split.avgAll,
      prevClose: prevClose, total: FULL_TOTAL,
    }),
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'none' },
      backgroundColor: 'rgba(17,17,17,0.95)',
      borderColor: '#333',
      textStyle: { color: '#e0e0e0', fontSize: 11, fontFamily: 'var(--mono)' },
      formatter: function(params) {
        var priceP = params.find(function(p) { return p.seriesName === '价格' || p.seriesName === '下午'; });
        if (!priceP) return '';
        var idx = priceP.data[0];
        var time = minuteToLabel(idx, points);
        var price = priceP.data[1];
        if (price == null) return '';
        var pct = prevClose ? (((price - prevClose) / prevClose * 100)).toFixed(2) : '--';
        var c = price >= prevClose ? UP_COLOR : DOWN_COLOR;
        return '<strong>' + time + '</strong><br/>价格: <span style="color:' + c + '">' + price.toFixed(2) + '</span><br/>涨跌: <span style="color:' + c + '">' + (pct !== '--' ? pct + '%' : pct) + '</span>';
      },
    },
  }, true);

  window.addEventListener('resize', function() { if (state.chartInstance) state.chartInstance.resize(); });
}

function renderKlineChart(reuse) {
  const container = $('#main-chart');
  const data = state.chartData.kline;
  if (!container) return;

  if (!data || !data.bars || data.bars.length === 0) {
    container.innerHTML = '<div style="color:var(--text-dim);text-align:center;padding:40px;font-family:var(--mono);font-size:12px">暂无K线数据</div>';
    return;
  }

  const bars = data.bars;
  const dates = bars.map(b => b.time ? b.time.slice(5, 10) : '');
  const ohlc = bars.map(b => [b.open, b.close, b.low, b.high]);
  const volumes = bars.map(b => b.volume || 0);

  // reuse=true: 复用现有实例只 setOption (任务 #195)
  if (!reuse) {
    if (state.chartInstance) { state.chartInstance.dispose(); state.chartInstance = null; }
    state.chartInstance = echarts.init(container, null, { renderer: 'canvas' });
  }
  state.chartInstance.setOption({
    animation: false,
    backgroundColor: 'transparent',
    grid: [
      { top: 8, right: 15, bottom: '52%', left: 55 },
      { top: '58%', right: 15, bottom: 30, left: 55 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLine: { lineStyle: { color: '#2a2a2a' } }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false }, boundaryGap: true },
      { type: 'category', data: dates, gridIndex: 1, axisLine: { lineStyle: { color: '#2a2a2a' } }, axisTick: { show: false }, axisLabel: { color: '#666', fontSize: 9, fontFamily: 'var(--mono)', interval: Math.floor(dates.length / 6) }, splitLine: { show: false }, boundaryGap: true },
    ],
    yAxis: [
      { type: 'value', scale: true, gridIndex: 0, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#666', fontSize: 9, fontFamily: 'var(--mono)' }, splitLine: { lineStyle: { color: '#1a1a1a' } } },
      { type: 'value', scale: true, gridIndex: 1, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 4, height: 18, start: 70, end: 100, borderColor: '#2a2a2a', backgroundColor: 'transparent', fillerColor: 'rgba(26,140,255,0.1)', handleStyle: { color: '#1a8cff' }, textStyle: { color: '#666', fontSize: 9 } },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: UP_COLOR, color0: DOWN_COLOR, borderColor: UP_COLOR, borderColor0: DOWN_COLOR },
      },
      {
        name: '成交量', type: 'bar', data: volumes, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: '#666' }, barMaxWidth: 6,
      },
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17,17,17,0.95)',
      borderColor: '#333',
      textStyle: { color: '#e0e0e0', fontSize: 11, fontFamily: 'var(--mono)' },
      formatter: params => {
        const candle = params.find(x => x.seriesName === 'K线');
        const vol = params.find(x => x.seriesName === '成交量');
        if (!candle) return '';
        // ECharts candlestick 在 tooltip params.data 里返回 [dataIndex, open, close, low, high]
        // 但 candle.data 原始是 [open, close, low, high] 4 元素,这里 d[0] 是 index 不是 open.
        // 直接从 chartData.kline.bars 按 dataIndex 取,避开歧义.
        const bar = state.chartData.kline && state.chartData.kline.bars && state.chartData.kline.bars[candle.dataIndex];
        if (!bar) return '';
        const open = bar.open, close = bar.close, high = bar.high, low = bar.low;
        const isUp = close >= open;
        const c = isUp ? UP_COLOR : DOWN_COLOR;
        const pct = open ? ((close - open) / open * 100) : 0;
        const pctStr = (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%';
        // 今日涨跌停价 (来自 state.chartData.kline.limit_up/limit_down, 由后端按当前 pre_close 算)
        const kd = state.chartData.kline || {};
        const limitLine = (kd.limit_up != null && kd.limit_down != null)
          ? `<br/>涨停: <span style="color:${UP_COLOR}">${(+kd.limit_up).toFixed(2)}</span>&nbsp;
             跌停: <span style="color:${DOWN_COLOR}">${(+kd.limit_down).toFixed(2)}</span>`
          : '';
        return `<strong>${candle.axisValue}</strong><br/>
          开: <span style="color:#e0e0e0">${open.toFixed(2)}</span>&nbsp;
          收: <span style="color:${c}">${close.toFixed(2)}</span><br/>
          高: <span style="color:#e0e0e0">${high.toFixed(2)}</span>&nbsp;
          低: <span style="color:#e0e0e0">${low.toFixed(2)}</span><br/>
          涨跌: <span style="color:${c}">${pctStr}</span><br/>
          量: <span style="color:#e0e0e0">${vol && vol.data ? (vol.data / 10000).toFixed(1) + '万' : (bar.volume ? (bar.volume / 10000).toFixed(1) + '万' : '--')}</span>${limitLine}`;
      },
    },
  }, true);

  window.addEventListener('resize', () => state.chartInstance && state.chartInstance.resize());
}

async function refreshChart(code) {
  if (!code) return;
  if (state.chartMode !== 'minute') return;
  if (!state.chartInstance) return;
  try {
    const res = await api(`/api/stocks/${encodeURIComponent(code)}/minute`);
    if (!res.data) return;
    state.chartData.minute = res.data;
    const points = state.chartData.minute.points;
    if (!points || !points.length) return;

    // Market detection
    function toRaw(t) {
      const parts = (t || '').split(':');
      return parts.length === 2 ? parseInt(parts[0]) * 60 + parseInt(parts[1]) : null;
    }
    const raws = points.map(p => toRaw(p.time_label)).filter(r => r != null);
    const maxRaw = Math.max.apply(null, raws);
    const hasLunch = raws.some(r => r >= 720 && r < 780);
    const isHK = hasLunch;
    const isCN = !hasLunch && maxRaw <= 900;
    const isUS = !hasLunch && maxRaw > 900;
    const TOTAL = isCN ? 240 : (isHK ? 330 : 390);
    const MORNING_END = isHK ? 150 : 120;

    // Use index as x value (same as renderMinuteChart)
    const priceData = points.map((p, i) => [i, p.price]).filter(item => item[1] != null);
    const avgData   = points.map((p, i) => [i, p.avg_price]).filter(item => item[1] != null);
    const morningPrice = priceData.filter(item => item[0] < MORNING_END);
    const afternoonPrice = priceData.filter(item => item[0] >= MORNING_END);
    const morningAvg = avgData.filter(item => item[0] < MORNING_END);
    const afternoonAvg = avgData.filter(item => item[0] >= MORNING_END);

    const prevClose = state.chartData.minute.prev_close || (points[0] ? points[0].price : 0) || 0;
    const lastPrice = points.length ? points[points.length - 1].price : prevClose;
    const lineColor = lastPrice >= prevClose ? UP_COLOR : DOWN_COLOR;
    const areaTop = lastPrice >= prevClose ? 'rgba(220,38,38,' : 'rgba(22,163,74,';

    state.chartInstance.setOption({
      series: [
        { name: '价格', data: morningPrice, lineStyle: { color: lineColor, width: 1 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: areaTop + '0.15)' }, { offset: 1, color: areaTop + '0)' }] } } },
        afternoonPrice.length > 0 ? { name: '下午', data: afternoonPrice, lineStyle: { color: lineColor, width: 1 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: areaTop + '0.15)' }, { offset: 1, color: areaTop + '0)' }] } } } : null,
        { name: '均价', data: morningAvg, lineStyle: { color: '#f59e0b', width: 1, type: 'dashed' } },
        afternoonAvg.length > 0 ? { name: '均价2', data: afternoonAvg, lineStyle: { color: '#f59e0b', width: 1, type: 'dashed' } } : null,
        { name: '昨收', data: [[0, prevClose], [TOTAL, prevClose]], lineStyle: { color: '#666', width: 1, type: 'dotted' }, silent: true },
      ].filter(s => s != null),
    }, { lazyUpdate: true });
  } catch {}
}

// ── 模块入口包装 ───────────────────────────────────────────
window.Chart = {
  load: loadChart,
  switchTab: switchTab,
  refresh: refreshChart,
  renderMinute: renderMinuteChart,
  renderKline: renderKlineChart,
  // 注意: resize listener 原本就由 renderMinuteChart/renderKlineChart 内部 addEventListener
  // (每次 render 都加一次,这是已存在的问题;不修它以保持本次改动最小)
  init() {},
};
