#!/usr/bin/env python3
"""
纳指买卖模型 - 三维度优化版 v3.0
估值(40) + 恐慌(35) + 趋势(25) = 100分
"""

import json
import os
import sys
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

DATA_FILE = "data/nasdaq_data.json"

def fetch_data(ticker, period="10y"):
    """获取股票数据"""
    print(f"获取 {ticker}...")
    df = yf.download(ticker, period=period, progress=False, auto_adjust=False)
    df = df.reset_index()
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    close_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    
    result = pd.DataFrame({
        'Date': pd.to_datetime(df['Date']).values,
        'Close': np.array(df[close_col]).flatten().astype(float)
    }).dropna()
    
    print(f"  {len(result)}条")
    return result

def calculate_signals(ndx_df, vix_df):
    """计算三维度交易信号"""
    print("计算三维度评分...")
    
    merged = pd.merge(ndx_df, vix_df.rename(columns={'Close': 'VIX'}), on='Date', how='left')
    merged['VIX'] = merged['VIX'].ffill().fillna(20)
    
    prices = merged['Close'].values.astype(float)
    vix_values = merged['VIX'].values.astype(float)
    n = len(prices)
    
    # 52周高低点（252个交易日）
    high_52w = np.array([np.max(prices[max(0, i-251):i+1]) for i in range(n)])
    low_52w = np.array([np.min(prices[max(0, i-251):i+1]) for i in range(n)])
    position_52w = (prices - low_52w) / (high_52w - low_52w + 1e-10)
    
    # 200日均线
    ma200 = np.array([np.mean(prices[max(0, i-199):i+1]) for i in range(n)])
    ma_dist = (prices - ma200) / ma200 * 100
    
    scores = []
    details = []
    
    for i in range(n):
        # 维度1: 估值(40分)
        pos = position_52w[i]
        if pos > 0.9:
            val_score = 5
        elif pos > 0.7:
            val_score = 15
        elif pos > 0.5:
            val_score = 25
        elif pos > 0.3:
            val_score = 32
        else:
            val_score = 40
        
        # 维度2: 恐慌(35分)
        vix = vix_values[i]
        if vix >= 45:
            fear_score = 35
        elif vix >= 35:
            fear_score = 30 + (vix - 35) / 10 * 5
        elif vix >= 25:
            fear_score = 20 + (vix - 25) / 10 * 10
        elif vix >= 15:
            fear_score = (vix - 15) / 10 * 20
        else:
            fear_score = max(0, (vix - 10) / 5 * 5)
        
        # 维度3: 趋势(25分)
        dist = ma_dist[i]
        if dist <= -25:
            trend_score = 25
        elif dist <= -15:
            trend_score = 20 + (dist + 25) / 10 * 5
        elif dist <= -5:
            trend_score = 10 + (dist + 15) / 10 * 10
        elif dist < 10:
            trend_score = 5 + max(0, (5 - dist) / 15 * 5)
        else:
            trend_score = max(0, 5 - (dist - 10) / 5)
        
        total = int(val_score + fear_score + trend_score)
        total = max(0, min(100, total))
        scores.append(total)
        
        details.append({
            'valuation': round(val_score, 1),
            'fear': round(fear_score, 1),
            'trend': round(trend_score, 1),
            'position_52w': round(pos * 100, 1),
            'ma_dist': round(dist, 1)
        })
    
    # 7级信号
    signals = []
    for score in scores:
        if score >= 90:
            signals.append(('强烈买入', '🔥 历史级买点，建议重仓'))
        elif score >= 75:
            signals.append(('买入', '📈 较好买入时机'))
        elif score >= 60:
            signals.append(('定投', '💰 可开始定投或轻仓'))
        elif score >= 40:
            signals.append(('持有', '⏸️ 持有观望'))
        elif score >= 25:
            signals.append(('减仓', '⚠️ 考虑部分止盈'))
        elif score >= 10:
            signals.append(('卖出', '📉 高估区域，建议减仓'))
        else:
            signals.append(('强烈卖出', '🚨 泡沫区域，清仓避险'))
    
    result = pd.DataFrame({
        'Date': merged['Date'],
        'Price': prices,
        'Change': np.diff(prices, prepend=prices[0]),
        'Change_Percent': np.diff(prices, prepend=prices[0]) / np.where(prices != 0, prices, 1) * 100,
        'VIX': vix_values,
        'MA200': ma200,
        'MA200_Distance': ma_dist,
        'Score': scores,
        'Signal': [s[0] for s in signals],
        'Signal_Desc': [s[1] for s in signals],
        'Details': details
    })
    
    return result

def main():
    print(f"=== 纳指模型 v3.0 ===")
    print(f"时间: {datetime.now()}")
    
    try:
        ndx = fetch_data("^IXIC")
        vix = fetch_data("^VIX")
        
        result = calculate_signals(ndx, vix)
        
        old_data = {}
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                old_data = json.load(f).get('daily_data', {})
        
        for _, row in result.iterrows():
            if pd.isna(row['Price']):
                continue
            date = pd.Timestamp(row['Date']).strftime('%Y-%m-%d')
            old_data[date] = {
                'price': float(row['Price']),
                'change': float(row['Change']),
                'change_percent': float(row['Change_Percent']),
                'vix': float(row['VIX']),
                'ma200': float(row['MA200']),
                'ma200_distance': float(row['MA200_Distance']),
                'score': int(row['Score']),
                'signal': str(row['Signal']),
                'signal_desc': str(row['Signal_Desc']),
                'details': row['Details']
            }
        
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump({
                'last_update': datetime.now().isoformat(),
                'daily_data': old_data,
                'version': '3.0'
            }, f, ensure_ascii=False, indent=2)
        
        print(f"完成! 共{len(old_data)}天")
        
        recent = sorted(old_data.keys())[-3:]
        for d in recent:
            print(f"  {d}: {old_data[d]['score']}分 {old_data[d]['signal']}")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
