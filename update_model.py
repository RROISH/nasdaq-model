import yfinance as yf
import pandas as pd
import json
from datetime import datetime
import os

# 创建输出目录
os.makedirs('output', exist_ok=True)

# 获取数据
nasdaq = yf.Ticker("^IXIC")
vix = yf.Ticker("^VIX")

# 历史数据
nasdaq_hist = nasdaq.history(period="3mo")
vix_hist = vix.history(period="3mo")

# 最新数据
latest = nasdaq_hist.index[-1]
nasdaq_close = nasdaq_hist['Close'].iloc[-1]
nasdaq_prev = nasdaq_hist['Close'].iloc[-2]
change_pct = (nasdaq_close - nasdaq_prev) / nasdaq_prev * 100

vix_close = vix_hist['Close'].iloc[-1]

# 计算指标
fifty_ma = nasdaq_hist['Close'].rolling(50).mean().iloc[-1]
price_vs_ma = (nasdaq_close - fifty_ma) / fifty_ma * 100

# 52周高低点
year_high = nasdaq_hist['Close'].max()
year_low = nasdaq_hist['Close'].min()
position_in_range = (nasdaq_close - year_low) / (year_high - year_low) * 100

# 模型评分算法
score = 0

# VIX评分
if vix_close > 30:
    score += 3
elif vix_close > 20:
    score += 1
elif vix_close < 15:
    score -= 2

# 位置评分
if position_in_range > 90:
    score -= 2
elif position_in_range < 20:
    score += 2

# 均线评分
if price_vs_ma > 10:
    score -= 1
elif price_vs_ma < -10:
    score += 1

# 生成信号
if score >= 2:
    signal = "买入"
    signal_color = "green"
elif score <= -2:
    signal = "卖出"
    signal_color = "red"
else:
    signal = "持有"
    signal_color = "orange"

# 生成操作建议
if score >= 3:
    advice = "市场极度恐慌，建议分批买入"
elif score >= 2:
    advice = "市场低位，可考虑轻仓买入"
elif score <= -3:
    advice = "市场极度贪婪，建议减仓止盈"
elif score <= -2:
    advice = "市场高位，建议分批减仓"
else:
    advice = "市场正常，持有观望"

# 数据字典
data = {
    "date": latest.strftime("%Y-%m-%d"),
    "nasdaq_close": round(nasdaq_close, 2),
    "change_pct": round(change_pct, 2),
    "vix": round(vix_close, 2),
    "price_vs_ma": round(price_vs_ma, 2),
    "position_in_range": round(position_in_range, 1),
    "score": score,
    "signal": signal,
    "advice": advice
}

# 保存JSON
with open('output/data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 生成简单HTML（使用字符串拼接，避免任何花括号冲突）
date_str = data['date']
nasdaq_str = str(data['nasdaq_close'])
change_str = str(data['change_pct'])
vix_str = str(data['vix'])
ma_str = str(data['price_vs_ma'])
position_str = str(data['position_in_range'])
score_str = str(data['score'])
signal_str = data['signal']
advice_str = data['advice']

# 涨跌幅颜色
if data['change_pct'] > 0:
    change_color = "green"
else:
    change_color = "red"

# 均线颜色
if data['price_vs_ma'] > 0:
    ma_color = "green"
else:
    ma_color = "red"

html_parts = []
html_parts.append('<!DOCTYPE html>')
html_parts.append('<html lang="zh-CN">')
html_parts.append('<head>')
html_parts.append('    <meta charset="UTF-8">')
html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
html_parts.append('    <title>纳指模型 - ' + date_str + '</title>')
html_parts.append('    <style>')
html_parts.append('        body { font-family: Arial, sans-serif; background: #f0f0f0; padding: 20px; margin: 0; }')
html_parts.append('        .container { max-width: 400px; margin: 0 auto; background: white; border-radius: 10px; padding: 20px; }')
html_parts.append('        h1 { text-align: center; color: #333; font-size: 24px; }')
html_parts.append('        .date { text-align: center; color: #666; font-size: 14px; margin-bottom: 20px; }')
html_parts.append('        .signal { font-size: 36px; font-weight: bold; text-align: center; padding: 20px; border-radius: 10px; margin: 20px 0; }')
html_parts.append('        .signal-green { background: #4CAF50; color: white; }')
html_parts.append('        .signal-red { background: #f44336; color: white; }')
html_parts.append('        .signal-orange { background: #FF9800; color: white; }')
html_parts.append('        .score { text-align: center; font-size: 16px; color: #666; margin-bottom: 20px; }')
html_parts.append('        .data-row { display: flex; justify-content: space-between; padding: 15px 0; border-bottom: 1px solid #eee; }')
html_parts.append('        .data-label { color: #666; }')
html_parts.append('        .data-value { font-weight: bold; color: #333; }')
html_parts.append('        .green { color: #4CAF50; }')
html_parts.append('        .red { color: #f44336; }')
html_parts.append('        .advice { background: #f9f9f9; padding: 15px; border-radius: 8px; margin-top: 20px; }')
html_parts.append('        .advice h3 { margin-top: 0; color: #333; }')
html_parts.append('        .footer { text-align: center; color: #999; font-size: 12px; margin-top: 20px; }')
html_parts.append('    </style>')
html_parts.append('</head>')
html_parts.append('<body>')
html_parts.append('    <div class="container">')
html_parts.append('        <h1>📈 纳指交易模型</h1>')
html_parts.append('        <div class="date">' + date_str + ' 更新</div>')
html_parts.append('        <div class="signal signal-' + signal_color + '">' + signal_str + '</div>')
html_parts.append('        <div class="score">模型评分: ' + score_str + ' / -5~+5</div>')
html_parts.append('        <div class="data-row">')
html_parts.append('            <span class="data-label">纳指收盘</span>')
html_parts.append('            <span class="data-value">' + nasdaq_str + '</span>')
html_parts.append('        </div>')
html_parts.append('        <div class="data-row">')
html_parts.append('            <span class="data-label">涨跌幅</span>')
html_parts.append('            <span class="data-value ' + change_color + '">' + change_str + '%</span>')
html_parts.append('        </div>')
html_parts.append('        <div class="data-row">')
html_parts.append('            <span class="data-label">VIX恐慌指数</span>')
html_parts.append('            <span class="data-value">' + vix_str + '</span>')
html_parts.append('        </div>')
html_parts.append('        <div class="data-row">')
html_parts.append('            <span class="data-label">vs 50日均线</span>')
html_parts.append('            <span class="data-value ' + ma_color + '">' + ma_str + '%</span>')
html_parts.append('        </div>')
html_parts.append('        <div class="data-row">')
html_parts.append('            <span class="data-label">52周位置</span>')
html_parts.append('            <span class="data-value">' + position_str + '%</span>')
html_parts.append('        </div>')
html_parts.append('        <div class="advice">')
html_parts.append('            <h3>💡 操作建议</h3>')
html_parts.append('            <p>' + advice_str + '</p>')
html_parts.append('        </div>')
html_parts.append('        <div class="footer">数据延迟15分钟 | 仅供参考</div>')
html_parts.append('    </div>')
html_parts.append('</body>')
html_parts.append('</html>')

html_content = '\n'.join(html_parts)

with open('output/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("更新完成：" + date_str)
print("纳指：" + nasdaq_str + " (" + change_str + "%)")
print("VIX：" + vix_str)
print("信号：" + signal_str + " (评分: " + score_str + ")")
