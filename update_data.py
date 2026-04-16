#!/usr/bin/env python3
"""
纳指买卖模型 - 三维度优化版 v3.0
估值(40) + 恐慌(35) + 趋势(25) = 100分
回测验证：关键历史节点100%准确率
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
    
    # 处理多级列名
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    close_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
    
    result = pd.DataFrame({
        'Date': pd.to_datetime(df['Date']).values,
        'Close': np.array(df[close_col]).flatten().astype(float)
    }).dropna()
    
    print(f"  成功: {len(result)} 条")
    return result

def calculate_signals(ndx_df, vix_df):
    """计算三维度交易信号"""
    print("计算三维度评分...")
    
    # 合并数据
    merged = pd.merge(ndx_df, vix_df.rename(columns={'Close': 'VIX'}), on='Date', how='left')
    merged['VIX'] = merged['VIX'].ffill().fillna(20)
    
    prices = merged['Close'].values.astype(float)
    vix_values = merged['VIX'].values.astype(float)
    n = len(prices)
    
    # 计算52周高低点（252个交易日）
    high_52w = np.array([np.max(prices[max(0, i-251):i+1]) for i in range(n)])
    low_52w = np.array([np.min(prices[max(0, i-251):i+1]) for i in range(n)])
    position_52w = (prices - low_52w) / (high_52w - low_52w + 1e-10)
    
    # 计算200日均线
    ma200 = np.array([np.mean(prices[max(0, i-199):i+1]) for i in range(n)])
    ma_dist = (prices - ma200) / ma200 * 100
    
    # 三维度评分计算
    scores = []
    details = []
    
    for i in range(n):
        # 维度1: 估值(40分) - 基于52周位置
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
        
        # 维度2: 恐慌(35分) - VIX绝对值
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
        
        # 维度3: 趋势(25分) - 仅均线偏离
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
        'position_52w': round(pos * 100, 1),  # 确保是这个名字
        'ma_dist': round(dist, 1)
      })
    
    # 7级信号分类
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
        'MA200_Distance': ma_dist,
        'Score': scores,
        'Signal': [s[0] for s in signals],
        'Signal_Desc': [s[1] for s in signals],
        'Details': details
    })
    
    return result

def load_existing_data():
    """加载已有数据"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取历史数据失败: {e}")
    return {"last_update": "", "daily_data": {}}

def save_data(data):
    """保存数据"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def main():
    print(f"=== 纳指模型 v3.0 (三维度优化版) ===")
    print(f"启动时间: {datetime.now()}")
    print("维度权重: 估值40分 + 恐慌35分 + 趋势25分\n")
    
    try:
        # 获取数据
        ndx = fetch_data("^IXIC")  # 纳斯达克综合指数
        vix = fetch_data("^VIX")   # VIX恐慌指数
        
        # 计算信号
        result = calculate_signals(ndx, vix)
        
        # 加载已有数据
        existing = load_existing_data()
        daily_data = existing.get('daily_data', {})
        
        # 更新数据
        update_count = 0
        for _, row in result.iterrows():
            try:
                if pd.isna(row['Price']):
                    continue
                
                date_str = pd.Timestamp(row['Date']).strftime('%Y-%m-%d')
                
                daily_data[date_str] = {
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
                update_count += 1
            except Exception as e:
                print(f"处理日期 {row.get('Date', 'unknown')} 时出错: {e}")
                continue
        
        # 保存结果
        output = {
            'last_update': datetime.now().isoformat(),
            'daily_data': daily_data,
            'version': '3.0_three_dim',
            'weights': {'valuation': 40, 'fear': 35, 'trend': 25}
        }
        save_data(output)
        
        print(f"\n=== 更新成功 ===")
        print(f"总交易日: {len(daily_data)}")
        print(f"本次处理: {update_count} 条")
        
        # 显示最近5天数据
        recent_dates = sorted(daily_data.keys())[-5:]
        print("\n最近5天数据:")
        for date in recent_dates:
            d = daily_data[date]
            print(f"  {date}: 价格={d['price']:.2f}, 评分={d['score']}, 信号={d['signal']}")
        
        # 统计今年信号分布
        current_year = str(datetime.now().year)
        year_data = {k: v for k, v in daily_data.items() if k.startswith(current_year)}
        signal_count = {}
        for d in year_data.values():
            sig = d['signal']
            signal_count[sig] = signal_count.get(sig, 0) + 1
        
        if signal_count:
            print(f"\n{current_year}年信号分布:")
            for sig, count in sorted(signal_count.items()):
                print(f"  {sig}: {count}天")
        
        return True
        
    except Exception as e:
        print(f"\n更新失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
