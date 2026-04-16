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
signals = []

# VIX评分
if vix_close > 30:
    score += 3
    signals.append("VIX>30 极度恐慌")
elif vix_close > 20:
    score += 1
    signals.append("VIX 20-30 谨慎")
elif vix_close < 15:
    score -= 2
    signals.append("VIX<15 极度贪婪")

# 位置评分
if position_in_range > 90:
    score -= 2
    signals.append("接近52周高点")
elif position_in_range < 20:
    score += 2
    signals.append("接近52周低点")

# 均线评分
if price_vs_ma > 10:
    score -= 1
    signals.append("远高于50日均线")
elif price_vs_ma < -10:
    score += 1
    signals.append("远低于50日均线")

# 生成信号
if score >= 2:
    signal = "买入"
    signal_class = "buy"
elif score <= -2:
    signal = "卖出"
    signal_class = "sell"
else:
    signal = "持有"
    signal_class = "hold"

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
    "signals": signals,
    "advice": advice
}

# 保存JSON
with open('output/data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 生成HTML页面
html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>纳指模型 - {{data['date']}}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 400px; margin: 0 auto; }}
        .header {{ text-align: center; color: white; margin-bottom: 20px; }}
        .header h1 {{ font-size: 24px; margin-bottom: 5px; }}
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
            font-size: 32px; 
            font-weight: bold; 
            padding: 20px; 
            border-radius: 15px; 
            color: white;
            margin-bottom: 15px;
        }}
        .buy {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
        .sell {{ background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); }}
        .hold {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}

        .score-box {{ 
            display: inline-block; 
            padding: 10px 20px; 
            background: #f0f0f0; 
            border-radius: 20px; 
            font-size: 14px;
            color: #666;
        }}

        .data-card {{ 
            background: white; 
            border-radius: 15px; 
            padding: 20px; 
            margin-bottom: 15px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        .data-card h3 {{ 
            font-size: 16px; 
            color: #333; 
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .metric {{ 
            display: flex; 
            justify-content: space-between; 
            padding: 12px 0; 
            border-bottom: 1px solid #f0f0f0;
            font-size: 15px;
        }}
        .metric:last-child {{ border-bottom: none; }}
        .metric-label {{ color: #666; }}
        .metric-value {{ font-weight: 600; color: #333; }}
        .positive {{ color: #11998e; }}
        .negative {{ color: #eb3349; }}

        .advice-card {{ 
            background: white; 
            border-radius: 15px; 
            padding: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        .advice-card h3 {{ font-size: 16px; margin-bottom: 10px; }}
        .advice-text {{ 
            font-size: 15px; 
            line-height: 1.6; 
            color: #555;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
        }}

        .footer {{ 
            text-align: center; 
            color: rgba(255,255,255,0.7); 
            font-size: 12px; 
            margin-top: 20px;
        }}

        @media (max-width: 380px) {{
            body {{ padding: 15px; }}
            .signal-box {{ font-size: 28px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 纳指交易模型</h1>
            <div class="date">{{data['date']}} 更新</div>
        </div>

        <div class="signal-card">
            <div class="signal-box {{signal_class}}">{{data['signal']}}</div>
            <div class="score-box">模型评分: {{data['score']}} / -5~+5</div>
        </div>

        <div class="data-card">
            <h3>📊 市场数据</h3>
            <div class="metric">
                <span class="metric-label">纳指收盘</span>
                <span class="metric-value">{{"{:,.2f}".format(data['nasdaq_close'])}}</span>
            </div>
            <div class="metric">
                <span class="metric-label">涨跌幅</span>
                <span class="metric-value {{ 'positive' if data['change_pct'] > 0 else 'negative' }}">{{"{:+.2f}}%".format(data['change_pct'])}}</span>
            </div>
            <div class="metric">
                <span class="metric-label">VIX恐慌指数</span>
                <span class="metric-value">{{"{:.2f}".format(data['vix'])}}</span>
            </div>
            <div class="metric">
                <span class="metric-label">vs 50日均线</span>
                <span class="metric-value {{ 'positive' if data['price_vs_ma'] > 0 else 'negative' }}">{{"{:+.2f}}%".format(data['price_vs_ma'])}}</span>
            </div>
            <div class="metric">
                <span class="metric-label">52周位置</span>
                <span class="metric-value">{{"{:.1f}}%".format(data['position_in_range'])}}</span>
            </div>
        </div>

        <div class="advice-card">
            <h3>💡 操作建议</h3>
            <div class="advice-text">{{data['advice']}}</div>
        </div>

        <div class="footer">
            数据延迟15分钟 | 仅供参考不构成投资建议
        </div>
    </div>
</body>
</html>"""

with open('output/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"✅ 更新完成：{{data['date']}}")
print(f"📊 纳指：{{data['nasdaq_close']}} ({{data['change_pct']:+.2f}}%)")
print(f"😰 VIX：{{data['vix']:.2f}}")
print(f"🎯 信号：{{data['signal']}} (评分: {{data['score']}})")
