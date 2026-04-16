#!/usr/bin/env python3
"""
纳指买卖模型 - 专业优化版 v2.0
五维评分体系 + 智能分级信号
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
    """获取数据"""
    print(f"获取 {ticker} ...")
    df = yf.download(ticker, period=period, progress=False, auto_adjust=False)
    df = df.reset_index()
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    close_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    
    result = pd.DataFrame({
        'Date': pd.to_datetime(df['Date']).values,
        'Close': np.array(df[close_col]).flatten().astype(float)
    }).dropna()
    
    print(f"  成功: {len(result)} 条")
    return result

def calculate_advanced_signals(ndx_df, vix_df):
    """计算五维评分信号"""
    print("计算五维指标...")
    
    # 合并数据
    merged = pd.merge(ndx_df, vix_df.rename(columns={'Close': 'VIX'}), on='Date', how='left')
    merged['VIX'] = merged['VIX'].ffill().fillna(20)
    
    prices = merged['Close'].values.astype(float)
    vix_values = merged['VIX'].values.astype(float)
    n = len(prices)
    
    # 计算基础指标
    ma200 = np.array([np.mean(prices[max(0, i-199):i+1]) for i in range(n)])
    ma50 = np.array([np.mean(prices[max(0, i-49):i+1]) for i in range(n)])
    ma20 = np.array([np.mean(prices[max(0, i-19):i+1]) for i in range(n)])
    
    # 52周高低点
    high_52w = np.array([np.max(prices[max(0, i-251):i+1]) for i in range(n)])
    low_52w = np.array([np.min(prices[max(0, i-251):i+1]) for i in range(n)])
    position_52w = (prices - low_52w) / (high_52w - low_52w + 1e-10)
    
    # VIX 20日均值（趋势）
    vix_ma20 = np.array([np.mean(vix_values[max(0, i-19):i+1]) for i in range(n)])
    vix_trend = vix_values - vix_ma20
    
    # 波动率 (20日)
    volatility = np.array([np.std(prices[max(0, i-19):i+1]) for i in range(n)])
    vol_ma = np.mean(volatility[-20:]) if len(volatility) >= 20 else np.mean(volatility)
    
    # 估值百分位（252日）
    pe_pct = np.zeros(n)
    for i in range(n):
        start = max(0, i - 251)
        if i - start >= 50:
            window = prices[start:i+1] / ma200[start:i+1]
            current = prices[i] / ma200[i]
            pe_pct[i] = np.mean(window <= current)
        else:
            pe_pct[i] = 0.5
    
    # 五维评分计算
    scores = np.zeros(n, dtype=int)
    details = []
    
    for i in range(n):
        # 1. 估值维度 (30分) - PE百分位(20) + 52周位置(10)
        pe_score = (1 - pe_pct[i]) * 20
        position_score = (1 - position_52w[i]) * 10
        valuation_score = pe_score + position_score
        
        # 2. 恐慌维度 (25分) - VIX绝对值(15) + VIX趋势(10)
        vix = vix_values[i]
        if vix > 35:
            vix_level_score = 15
        elif vix > 25:
            vix_level_score = 10 + (vix - 25) / 10 * 5
        elif vix > 15:
            vix_level_score = (vix - 15) / 10 * 10
        else:
            vix_level_score = max(0, (vix - 10) / 5 * 5)
        
        # VIX趋势：VIX上升表示恐慌加剧（加分）
        vix_trend_score = min(10, max(0, vix_trend[i] / 5 * 5 + 5))
        fear_score = vix_level_score + vix_trend_score
        
        # 3. 趋势维度 (20分) - 均线排列(10) + 偏离度(10)
        # 均线多头排列：MA20 > MA50 > MA200
        ma_bull = 1 if (ma20[i] > ma50[i] > ma200[i]) else 0
        ma_bear = 1 if (ma20[i] < ma50[i] < ma200[i]) else 0
        ma_score = 10 if ma_bear else (5 if not ma_bull else 0)
        
        # 偏离度：超跌加分，超买减分
        dist = (prices[i] - ma200[i]) / ma200[i] * 100
        if dist < -15:
            dist_score = 10
        elif dist < -5:
            dist_score = 5 + (dist + 15) / 10 * 5
        elif dist < 5:
            dist_score = 5
        else:
            dist_score = max(0, 5 - (dist - 5) / 2)
        trend_score = ma_score + dist_score
        
        # 4. 动量维度 (15分) - 反向指标，超跌反弹
        if i >= 20:
            mom20 = (prices[i] - prices[i-20]) / prices[i-20] * 100
        else:
            mom20 = 0
        
        if mom20 < -15:
            momentum_score = 15
        elif mom20 < -5:
            momentum_score = 10 + (mom20 + 15) / 10 * 5
        elif mom20 < 5:
            momentum_score = 5
        else:
            momentum_score = max(0, 5 - mom20 / 4)
        
        # 5. 波动维度 (10分) - 高波动时更谨慎
        if volatility[i] > vol_ma * 1.5:
            vol_score = 10  # 高波动有机会
        elif volatility[i] > vol_ma:
            vol_score = 7
        else:
            vol_score = 5
        
        # 总分（动态权重：高VIX时估值权重提升）
        if vix > 25:
            total = int(valuation_score * 1.2 + fear_score * 1.1 + trend_score * 0.9 + momentum_score + vol_score * 0.8)
        else:
            total = int(valuation_score + fear_score + trend_score + momentum_score + vol_score)
        
        total = max(0, min(100, total))
        scores[i] = total
        
        # 保存详情
        details.append({
            'valuation': round(valuation_score, 1),
            'fear': round(fear_score, 1),
            'trend': round(trend_score, 1),
            'momentum': round(momentum_score, 1),
            'volatility': round(vol_score, 1),
            'ma_dist': round(dist, 2),
            'vix': round(vix, 2),
            'pe_pct': round(pe_pct[i], 3)
        })
    
    # 智能分级信号
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
    
    # 组装结果
    result = pd.DataFrame({
        'Date': merged['Date'],
        'Price': prices,
        'Change': np.diff(prices, prepend=prices[0]),
        'Change_Percent': np.diff(prices, prepend=prices[0]) / np.where(prices != 0, prices, 1) * 100,
        'VIX': vix_values,
        'MA200': ma200,
        'MA200_Distance': ((prices - ma200) / ma200 * 100),
        'Score': scores,
        'Signal': [s[0] for s in signals],
        'Signal_Desc': [s[1] for s in signals],
        'Details': details
    })
    
    return result

def main():
    print(f"=== 纳指模型 v2.0 启动: {datetime.now()} ===")
    
    try:
        ndx = fetch_data("^IXIC")
        vix = fetch_data("^VIX")
        
        result = calculate_advanced_signals(ndx, vix)
        
        # 加载旧数据
        old_data = {}
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                old_data = json.load(f).get('daily_data', {})
        
        # 更新
        for _, row in result.iterrows():
            date = pd.Timestamp(row['Date']).strftime('%Y-%m-%d')
            old_data[date] = {
                'price': round(float(row['Price']), 2),
                'change': round(float(row['Change']), 2),
                'change_percent': round(float(row['Change_Percent']), 2),
                'vix': round(float(row['VIX']), 2),
                'ma200': round(float(row['MA200']), 2),
                'ma200_distance': round(float(row['MA200_Distance']), 2),
                'score': int(row['Score']),
                'signal': str(row['Signal']),
                'signal_desc': str(row['Signal_Desc']),
                'details': row['Details']
            }
        
        # 保存
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump({
                'last_update': datetime.now().isoformat(),
                'daily_data': old_data,
                'version': '2.0'
            }, f, ensure_ascii=False, indent=2)
        
        print(f"完成! 共 {len(old_data)} 天数据")
        
        # 显示最近5天及信号分布
        recent = sorted(old_data.keys())[-5:]
        print("\n最近5天:")
        for date in recent:
            d = old_data[date]
            print(f"  {date}: {d['score']}分 {d['signal']} (VIX:{d['vix']:.1f})")
        
        # 统计近一年信号分布
        year_data = {k: v for k, v in old_data.items() if k >= recent[-1][:4] + '-01-01'}
        signals_count = {}
        for d in year_data.values():
            s = d['signal']
            signals_count[s] = signals_count.get(s, 0) + 1
        print(f"\n今年信号分布: {signals_count}")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
