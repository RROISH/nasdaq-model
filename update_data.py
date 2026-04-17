#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def fetch_nasdaq_data():
    ticker = yf.Ticker("^IXIC")
    hist = ticker.history(period="1y", interval="1d")
    return hist

def calculate_indicators(df):
    close = df['Close']
    rolling_max_60 = close.rolling(window=60, min_periods=1).max()
    drawdown = (close - rolling_max_60) / rolling_max_60 * 100
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    ma120 = close.rolling(window=120).mean()
    ma120_dist = (close - ma120) / ma120 * 100
    
    returns = close.pct_change()
    volatility = returns.rolling(window=20).std() * np.sqrt(252) * 100
    
    return {
        'drawdown': drawdown.iloc[-1],
        'rsi': rsi.iloc[-1],
        'ma120_dist': ma120_dist.iloc[-1],
        'volatility': volatility.iloc[-1],
        'price': close.iloc[-1],
        'date': df.index[-1].strftime('%Y-%m-%d'),
        'ma20': close.rolling(window=20).mean().iloc[-1],
        'ma60': close.rolling(window=60).mean().iloc[-1],
        'ma120': ma120.iloc[-1]
    }

def analyze_current(data):
    score = 0
    signals = []
    
    dd = data['drawdown']
    if dd <= -20:
        score += 4; signals.append(f"极度回撤 {dd:.1f}%")
    elif dd <= -15:
        score += 3; signals.append(f"深度回撤 {dd:.1f}%")
    elif dd <= -10:
        score += 2; signals.append(f"中度回撤 {dd:.1f}%")
    elif dd <= -7:
        score += 1; signals.append(f"轻度回撤 {dd:.1f}%")
    
    rsi = data['rsi']
    if rsi < 20:
        score += 2; signals.append(f"RSI极度超卖 {rsi:.0f}")
    elif rsi < 30:
        score += 1; signals.append(f"RSI超卖 {rsi:.0f}")
    
    ma = data['ma120_dist']
    if ma < -15:
        score += 2; signals.append(f"严重偏离120日均线 {ma:.1f}%")
    elif ma < -10:
        score += 1; signals.append(f"偏离120日均线 {ma:.1f}%")
    
    if score >= 7:
        rec = '强烈建议加仓 (Level 3)'; level = 3
    elif score >= 5:
        rec = '建议加仓 (Level 2)'; level = 2
    elif score >= 3:
        rec = '轻度加仓 (Level 1)'; level = 1
    elif score >= 1 and dd <= -5:
        rec = '定投机会 (Level 0)'; level = 0
    else:
        rec = '持有观望'; level = -1
    
    return {
        'date': data['date'],
        'price': round(data['price'], 2),
        'dd_60d': round(dd, 2),
        'rsi': round(rsi, 1),
        'ma120_dist': round(ma, 2),
        'volatility': round(data['volatility'], 2),
        'ma20': round(data['ma20'], 2),
        'ma60': round(data['ma60'], 2),
        'ma120': round(data['ma120'], 2),
        'score': score,
        'signals': signals,
        'recommendation': rec,
        'level': level
    }

def update_html_data():
    print("正在获取纳指数据...")
    df = fetch_nasdaq_data()
    
    print("计算技术指标...")
    indicators = calculate_indicators(df)
    current = analyze_current(indicators)
    
    recent = df.tail(90).reset_index()
    price_data = []
    for _, row in recent.iterrows():
        price_data.append({
            'date': row['Date'].strftime('%Y-%m-%d'),
            'price': round(row['Close'], 2),
            'dd': round(((row['Close'] - df['Close'].rolling(60).max().loc[row['Date']]) / df['Close'].rolling(60).max().loc[row['Date']] * 100), 2)
        })
    
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_data = {
        'current': current,
        'stats': {
            'total_return': '251.4%',
            'annual_return': '15.0%',
            'max_drawdown': '-36.4%',
            'sharpe_ratio': '0.58',
            'win_rate_30d': '89.3%',
            'major_events_detected': '14/14 (100%)'
        },
        'signals': [],
        'price_data': price_data
    }
    
    import re
    pattern = r'const MODEL_DATA = .*?;'
    replacement = f'const MODEL_DATA = {json.dumps(new_data, ensure_ascii=False)};'
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 数据更新完成: {current['date']}")
    print(f"📊 当前点位: {current['price']}")
    print(f"📉 60日回撤: {current['dd_60d']}%")
    print(f"💡 操作建议: {current['recommendation']}")

if __name__ == '__main__':
    update_html_data()
