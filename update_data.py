#!/usr/bin/env python3
"""
纳指买卖模型 - 三维度优化版 v3.1
修复：数据源优化 + 稳定性提升
估值(40) + 恐慌(35) + 趋势(25) = 100分
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
import requests
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 尝试导入yfinance，如失败则安装
try:
    import yfinance as yf
except ImportError:
    os.system("pip install yfinance --quiet")
    import yfinance as yf

DATA_FILE = "data/nasdaq_data.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def fetch_with_retry(ticker, period="10y", max_retries=3):
    """带重试机制的数据获取"""
    for attempt in range(max_retries):
        try:
            print(f"  尝试 {attempt+1}/{max_retries}: {ticker}")
            # 使用session避免被拦截
            session = requests.Session()
            session.headers.update({'User-Agent': USER_AGENT})
            
            # 创建Ticker对象
            t = yf.Ticker(ticker, session=session)
            # 获取历史数据，自动调整股息
            df = t.history(period=period, auto_adjust=True)
            
            if df.empty:
                raise ValueError(f"返回空数据: {ticker}")
            
            # 重置索引，确保Date是列
            df = df.reset_index()
            
            # 统一列名（处理多级索引情况）
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # 标准化列名
            df = df.rename(columns={
                'Date': 'Date',
                'Open': 'Open',
                'High': 'High', 
                'Low': 'Low',
                'Close': 'Close',
                'Adj Close': 'Close',
                'Volume': 'Volume'
            })
            
            # 确保Date是datetime类型
            df['Date'] = pd.to_datetime(df['Date'])
            
            print(f"  ✓ 获取 {len(df)} 条记录，最新日期: {df['Date'].max().strftime('%Y-%m-%d')}")
            
            # 数据新鲜度检查（如果最新数据超过3天，警告）
            latest_date = df['Date'].max()
            days_diff = (datetime.now() - latest_date).days
            if days_diff > 3:
                print(f"  ⚠️ 警告: 数据可能延迟 {days_diff} 天")
            
            return df[['Date', 'Close']].dropna()
            
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                print(f"  等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                raise

def fetch_data(primary_ticker="^NDX", backup_ticker="^IXIC", period="10y"):
    """获取纳指数据，优先NDX，失败时回退到IXIC"""
    print(f"获取纳指数据（首选: {primary_ticker}）...")
    
    try:
        df = fetch_with_retry(primary_ticker, period)
        print(f"✅ 使用 {primary_ticker} (纳指100) - 更准确的投资标的")
        return df, primary_ticker
    except Exception as e:
        print(f"⚠️ {primary_ticker} 失败: {e}")
        print(f"回退到 {backup_ticker} (纳指综合)...")
        df = fetch_with_retry(backup_ticker, period)
        return df, backup_ticker

def fetch_vix():
    """获取VIX恐慌指数"""
    print("获取 VIX 恐慌指数...")
    try:
        df = fetch_with_retry("^VIX", period="10y")
        print("✅ VIX 数据获取成功")
        return df
    except Exception as e:
        print(f"⚠️ VIX获取失败: {e}")
        # 返回空DataFrame，后续会用默认值20
        return pd.DataFrame(columns=['Date', 'Close'])

def calculate_signals(ndx_df, vix_df, ticker_used):
    """计算三维度交易信号"""
    print("\n计算三维度评分...")
    
    # 合并数据（左连接保持纳指日期）
    merged = pd.merge(ndx_df, vix_df.rename(columns={'Close': 'VIX'}), 
                     on='Date', how='left')
    
    # VIX缺失值处理：使用前值填充，如果没有则用20（长期均值）
    merged['VIX'] = merged['VIX'].ffill().fillna(20)
    
    # 确保数值类型正确
    prices = merged['Close'].values.astype(float)
    vix_values = merged['VIX'].values.astype(float)
    dates = merged['Date'].values
    n = len(prices)
    
    if n < 252:
        raise ValueError(f"数据不足一年(252日)，仅有{n}条")
    
    # 计算52周高低点（252个交易日）
    high_52w = np.array([np.max(prices[max(0, i-251):i+1]) for i in range(n)])
    low_52w = np.array([np.min(prices[max(0, i-251):i+1]) for i in range(n)])
    position_52w = (prices - low_52w) / (high_52w - low_52w + 1e-10)
    
    # 200日均线
    ma200 = np.array([np.mean(prices[max(0, i-199):i+1]) for i in range(n)])
    ma_dist = (prices - ma200) / (ma200 + 1e-10) * 100
    
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
        
        # 维度2: 恐慌(35分) - 基于VIX
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
        
        # 维度3: 趋势(25分) - 基于200日均线偏离
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
    
    # 7级信号判断
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
    
    # 计算涨跌
    changes = np.diff(prices, prepend=prices[0])
    change_pcts = np.where(prices != 0, changes / prices * 100, 0)
    
    result = pd.DataFrame({
        'Date': pd.to_datetime(dates),
        'Price': prices,
        'Change': changes,
        'Change_Percent': change_pcts,
        'VIX': vix_values,
        'MA200': ma200,
        'MA200_Distance': ma_dist,
        'Score': scores,
        'Signal': [s[0] for s in signals],
        'Signal_Desc': [s[1] for s in signals],
        'Details': details,
        'Index_Type': ticker_used  # 记录使用的指数类型
    })
    
    return result

def main():
    print(f"=== 纳指模型 v3.1 (数据源优化版) ===")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"工作目录: {os.getcwd()}")
    
    try:
        # 获取数据（优先NDX，失败回退IXIC）
        ndx_df, ticker_used = fetch_data("^NDX", "^IXIC", period="10y")
        vix_df = fetch_vix()
        
        # 计算信号
        result = calculate_signals(ndx_df, vix_df, ticker_used)
        
        # 加载旧数据（用于增量更新）
        old_data = {}
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    old_data = json.load(f).get('daily_data', {})
                print(f"\n加载现有数据: {len(old_data)} 天")
            except Exception as e:
                print(f"\n警告: 无法读取旧数据: {e}")
        
        # 合并新数据
        update_count = 0
        for _, row in result.iterrows():
            if pd.isna(row['Price']):
                continue
            date = row['Date'].strftime('%Y-%m-%d')
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
                'details': row['Details'],
                'index_type': str(row['Index_Type'])
            }
            update_count += 1
        
        # 保存
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        output = {
            'last_update': datetime.now().isoformat(),
            'data_source': 'yahoo_finance',
            'index_used': ticker_used,
            'version': '3.1',
            'daily_data': old_data
        }
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 成功更新 {update_count} 天数据")
        print(f"总数据量: {len(old_data)} 天")
        print(f"使用指数: {ticker_used} ({'纳指100' if ticker_used == '^NDX' else '纳指综合'})")
        
        # 显示最近3天
        recent_dates = sorted(old_data.keys())[-3:]
        print(f"\n最近3天:")
        for d in recent_dates:
            data = old_data[d]
            print(f"  {d}: {data['score']}分 {data['signal']} | 价格:{data['price']:.2f} VIX:{data['vix']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 致命错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
