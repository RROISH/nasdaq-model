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

# 历史数据（获取更长时间用于计算历史分位）
nasdaq_hist = nasdaq.history(period="1y")
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

# 52周高低点和分位点
year_high = nasdaq_hist['Close'].max()
year_low = nasdaq_hist['Close'].min()
position_in_range = (nasdaq_close - year_low) / (year_high - year_low) * 100

# 计算近期趋势
change_5d = (nasdaq_close - nasdaq_hist['Close'].iloc[-5]) / nasdaq_hist['Close'].iloc[-5] * 100
change_20d = (nasdaq_close - nasdaq_hist['Close'].iloc[-20]) / nasdaq_hist['Close'].iloc[-20] * 100

# 模型评分算法（详细版）
score = 0
score_details = []

# 1. VIX评分（-2到+3分）
if vix_close > 40:
    vix_score = 3
    vix_desc = "极度恐慌(>40) +3"
elif vix_close > 30:
    vix_score = 2
    vix_desc = "恐慌(30-40) +2"
elif vix_close > 20:
    vix_score = 1
    vix_desc = "谨慎(20-30) +1"
elif vix_close > 15:
    vix_score = 0
    vix_desc = "正常(15-20) 0"
elif vix_close > 10:
    vix_score = -1
    vix_desc = "贪婪(10-15) -1"
else:
    vix_score = -2
    vix_desc = "极度贪婪(<10) -2"
score += vix_score
score_details.append(("VIX恐慌指数", vix_close, vix_score, vix_desc))

# 2. 位置评分（-2到+2分）
if position_in_range > 95:
    pos_score = -2
    pos_desc = "历史高位(>95%) -2"
elif position_in_range > 80:
    pos_score = -1
    pos_desc = "偏高(80-95%) -1"
elif position_in_range < 5:
    pos_score = 2
    pos_desc = "历史低位(<5%) +2"
elif position_in_range < 20:
    pos_score = 1
    pos_desc = "偏低(5-20%) +1"
else:
    pos_score = 0
    pos_desc = "中位(20-80%) 0"
score += pos_score
score_details.append(("52周位置", position_in_range, pos_score, pos_desc))

# 3. 均线偏离评分（-1到+1分）
if price_vs_ma > 15:
    ma_score = -1
    ma_desc = "严重超买(>15%) -1"
elif price_vs_ma < -15:
    ma_score = 1
    ma_desc = "严重超卖(<-15%) +1"
else:
    ma_score = 0
    ma_desc = "正常(-15%~15%) 0"
score += ma_score
score_details.append(("vs 50日均线", price_vs_ma, ma_score, ma_desc))

# 4. 短期趋势评分（-1到+1分）
if change_5d > 8:
    trend_score = -1
    trend_desc = "短期过热(5日>8%) -1"
elif change_5d < -8:
    trend_score = 1
    trend_desc = "短期超跌(5日<-8%) +1"
else:
    trend_score = 0
    trend_desc = "趋势正常 0"
score += trend_score
score_details.append(("5日涨跌幅", change_5d, trend_score, trend_desc))

# 生成信号
if score >= 3:
    signal = "强烈买入"
    signal_color = "green"
    signal_level = 3
elif score >= 1:
    signal = "买入"
    signal_color = "green"
    signal_level = 2
elif score <= -3:
    signal = "强烈卖出"
    signal_color = "red"
    signal_level = 3
elif score <= -1:
    signal = "卖出"
    signal_color = "red"
    signal_level = 2
else:
    signal = "持有观望"
    signal_color = "orange"
    signal_level = 1

# 生成操作建议
if score >= 3:
    advice = "市场极度恐慌，建议分批买入"
elif score >= 1:
    advice = "市场低位，可考虑轻仓买入"
elif score <= -3:
    advice = "市场极度贪婪，建议减仓止盈"
elif score <= -1:
    advice = "市场高位，建议分批减仓"
else:
    advice = "市场正常，持有观望"

# 生成仓位建议
if score >= 3:
    position_advice = "建议仓位：80-100%"
elif score >= 1:
    position_advice = "建议仓位：60-80%"
elif score == 0:
    position_advice = "建议仓位：40-60%"
elif score >= -2:
    position_advice = "建议仓位：20-40%"
else:
    position_advice = "建议仓位：0-20%"

# 数据字典
data = {
    "date": latest.strftime("%Y-%m-%d"),
    "nasdaq_close": round(nasdaq_close, 2),
    "change_pct": round(change_pct, 2),
    "change_5d": round(change_5d, 2),
    "change_20d": round(change_20d, 2),
    "vix": round(vix_close, 2),
    "price_vs_ma": round(price_vs_ma, 2),
    "position_in_range": round(position_in_range, 1),
    "score": score,
    "score_details": score_details,
    "signal": signal,
    "signal_level": signal_level,
    "advice": advice,
    "position_advice": position_advice,
    "fifty_ma": round(fifty_ma, 2),
    "year_high": round(year_high, 2),
    "year_low": round(year_low, 2)
}

# 保存JSON
with open('output/data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 生成增强版HTML
def generate_html(data):
    date_str = data['date']
    signal = data['signal']
    signal_color = "green" if "买入" in signal else ("red" if "卖出" in signal else "orange")
    
    # 生成评分明细HTML
    score_details_html = ""
    for name, value, point, desc in data['score_details']:
        point_class = "point-positive" if point > 0 else ("point-negative" if point < 0 else "point-zero")
        point_str = "+" + str(point) if point > 0 else str(point)
        score_details_html += f"""
            <div class="score-item">
                <div class="score-info">
                    <div class="score-name">{name} ({value:.2f})</div>
                    <div class="score-value">{desc}</div>
                </div>
                <div class="score-point {point_class}">{point_str}</div>
            </div>"""
    
    point_class_total = "point-positive" if data['score'] > 0 else ("point-negative" if data['score'] < 0 else "point-zero")
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>纳指模型 - {date_str}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 420px; margin: 0 auto; }}
        .header {{ text-align: center; color: white; margin-bottom: 20px; }}
        .header h1 {{ font-size: 26px; margin-bottom: 5px; }}
        .header .date {{ font-size: 14px; opacity: 0.9; }}
        
        .signal-card {{ 
            background: white; 
            border-radius: 20px; 
            padding: 30px; 
            text-align: center; 
            margin-bottom: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        .signal-box {{ 
            font-size: 36px; 
            font-weight: bold; 
            padding: 25px; 
            border-radius: 15px; 
            color: white;
            margin-bottom: 15px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        .signal-green {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
        .signal-red {{ background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); }}
        .signal-orange {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        
        .score-box {{ 
            display: inline-block; 
            padding: 12px 25px; 
            background: #f0f0f0; 
            border-radius: 25px; 
            font-size: 16px;
            color: #666;
            font-weight: 600;
        }}
        
        .data-card {{ 
            background: white; 
            border-radius: 15px; 
            padding: 20px; 
            margin-bottom: 15px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        .data-card h3 {{ 
            font-size: 17px; 
            color: #333; 
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
        }}
        .metric {{ 
            display: flex; 
            justify-content: space-between; 
            padding: 14px 0; 
            border-bottom: 1px solid #f0f0f0;
            font-size: 15px;
        }}
        .metric:last-child {{ border-bottom: none; }}
        .metric-label {{ color: #666; }}
        .metric-value {{ font-weight: 600; color: #333; }}
        .positive {{ color: #11998e; }}
        .negative {{ color: #eb3349; }}
        
        .score-detail-card {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        .score-detail-card h3 {{
            font-size: 17px;
            color: #333;
            margin-bottom: 15px;
            font-weight: 600;
        }}
        .score-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #f5f5f5;
        }}
        .score-item:last-child {{ border-bottom: none; }}
        .score-info {{ flex: 1; }}
        .score-name {{ font-size: 14px; color: #666; margin-bottom: 2px; }}
        .score-value {{ font-size: 15px; font-weight: 600; color: #333; }}
        .score-point {{
            font-size: 18px;
            font-weight: bold;
            padding: 5px 12px;
            border-radius: 15px;
            min-width: 50px;
            text-align: center;
        }}
        .point-positive {{ background: #e8f5e9; color: #2e7d32; }}
        .point-negative {{ background: #ffebee; color: #c62828; }}
        .point-zero {{ background: #f5f5f5; color: #666; }}
        
        .advice-card {{ 
            background: white; 
            border-radius: 15px; 
            padding: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            margin-bottom: 15px;
        }}
        .advice-card h3 {{ 
            font-size: 17px; 
            margin-bottom: 12px; 
            color: #333;
            font-weight: 600;
        }}
        .advice-text {{ 
            font-size: 16px; 
            line-height: 1.6; 
            color: #555;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            font-weight: 500;
        }}
        .position-advice {{
            margin-top: 12px;
            padding: 12px 15px;
            background: #e3f2fd;
            border-radius: 10px;
            font-size: 15px;
            color: #1565c0;
            font-weight: 600;
            text-align: center;
        }}
        
        .footer {{ 
            text-align: center; 
            color: rgba(255,255,255,0.8); 
            font-size: 12px; 
            margin-top: 20px;
            line-height: 1.5;
        }}
        
        @media (max-width: 380px) {{
            body {{ padding: 15px; }}
            .signal-box {{ font-size: 32px; padding: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 纳指交易模型</h1>
            <div class="date">{date_str} 更新</div>
        </div>
        
        <div class="signal-card">
            <div class="signal-box signal-{signal_color}">{signal}</div>
            <div class="score-box">模型评分: {data['score']} / -5~+5</div>
        </div>
        
        <div class="data-card">
            <h3>📊 市场数据</h3>
            <div class="metric">
                <span class="metric-label">纳指收盘</span>
                <span class="metric-value">{data['nasdaq_close']:,.2f}</span>
            </div>
            <div class="metric">
                <span class="metric-label">涨跌幅(1日)</span>
                <span class="metric-value {'positive' if data['change_pct'] > 0 else 'negative'}">{data['change_pct']:+.2f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">涨跌幅(5日)</span>
                <span class="metric-value {'positive' if data['change_5d'] > 0 else 'negative'}">{data['change_5d']:+.2f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">涨跌幅(20日)</span>
                <span class="metric-value {'positive' if data['change_20d'] > 0 else 'negative'}">{data['change_20d']:+.2f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">VIX恐慌指数</span>
                <span class="metric-value">{data['vix']:.2f}</span>
            </div>
            <div class="metric">
                <span class="metric-label">vs 50日均线</span>
                <span class="metric-value {'positive' if data['price_vs_ma'] > 0 else 'negative'}">{data['price_vs_ma']:+.2f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">52周位置</span>
                <span class="metric-value">{data['position_in_range']:.1f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">52周高点</span>
                <span class="metric-value">{data['year_high']:,.2f}</span>
            </div>
            <div class="metric">
                <span class="metric-label">52周低点</span>
                <span class="metric-value">{data['year_low']:,.2f}</span>
            </div>
        </div>
        
        <div class="score-detail-card">
            <h3>📋 评分明细</h3>
            {score_details_html}
            <div class="score-item" style="border-top: 2px solid #eee; margin-top: 10px; padding-top: 15px;">
                <div class="score-info">
                    <div class="score-value" style="font-size: 17px; color: #333;">综合评分</div>
                </div>
                <div class="score-point {point_class_total}" style="font-size: 20px;">{data['score']}</div>
            </div>
        </div>
        
        <div class="advice-card">
            <h3>💡 操作建议</h3>
            <div class="advice-text">{data['advice']}</div>
            <div class="position-advice">{data['position_advice']}</div>
        </div>
        
        <div class="footer">
            数据延迟15分钟 | 仅供参考不构成投资建议<br>
            模型基于VIX、均线、位置等多因子评分
        </div>
    </div>
</body>
</html>"""
    
    return html

html_content = generate_html(data)

with open('output/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("更新完成：" + data['date'])
print("纳指：" + str(data['nasdaq_close']) + " (" + str(data['change_pct']) + "%)")
print("VIX：" + str(data['vix']))
print("信号：" + data['signal'] + " (评分: " + str(data['score']) + ")")
print("建议：" + data['advice'])
