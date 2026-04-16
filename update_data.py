#!/usr/bin/env python3
"""
纳指买卖模型数据更新脚本
每日自动获取纳指数据并计算交易信号
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
import yfinance as yf
import pandas as pd
import numpy as np

# 数据文件路径
DATA_FILE = "data/nasdaq_data.json"

def fetch_nasdaq_data() -> pd.DataFrame:
    """获取纳指历史数据（近10年）"""
    print("正在获取纳指数据...")
    ticker = "^IXIC"  # 纳斯达克综合指数
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3650)  # 近10年
    
    df = yf.download(ticker, start=start_date, end=end_date, progress=False)
    df.reset_index(inplace=True)
    df['Date'] = pd.to_datetime(df['Date'])
    
    return df

def fetch_vix_data() -> pd.DataFrame:
    """获取VIX恐慌指数数据"""
    print("正在获取VIX数据...")
    ticker = "^VIX"
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3650)
    
    df = yf.download(ticker, start=start_date, end=end_date, progress=False)
    df.reset_index(inplace=True)
    df['Date'] = pd.to_datetime(df['Date'])
    
    return df

def calculate_pe_percentile(df: pd.DataFrame, window: int = 500) -> pd.Series:
    """
    计算估值百分位（使用价格/200日均线作为代理指标）
    实际应用中可替换为真实PE数据
    """
    ma200 = df['Close'].rolling(window=200).mean()
    price_to_ma = df['Close'] / ma200
    
    # 计算滚动百分位
    percentile = price_to_ma.rolling(window=window).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=True
    )
    return percentile

def calculate_signals(df: pd.DataFrame, vix_df: pd.DataFrame) -> pd.DataFrame:
    """计算交易信号"""
    # 合并数据
    df['Date'] = pd.to_datetime(df['Date'])
    vix_df['Date'] = pd.to_datetime(vix_df['Date'])
    merged = df.merge(vix_df[['Date', 'Close']], on='Date', how='left', suffixes=('', '_vix'))
    merged.rename(columns={'Close_vix': 'VIX'}, inplace=True)
    merged['VIX'].fillna(method='ffill', inplace=True)
    
    # 计算技术指标
    merged['MA200'] = merged['Close'].rolling(window=200).mean()
    merged['MA50'] = merged['Close'].rolling(window=50).mean()
    merged['MA200_Distance'] = (merged['Close'] - merged['MA200']) / merged['MA200'] * 100
    
    # 估值百分位（使用价格相对200日均线的位置）
    merged['PE_Percentile'] = calculate_pe_percentile(merged)
    
    # 计算涨跌幅
    merged['Change'] = merged['Close'].diff()
    merged['Change_Percent'] = merged['Close'].pct_change() * 100
    
    # 综合评分系统 (0-100)
    # 考虑因素：估值(40%)、趋势(30%)、VIX(30%)
    def calculate_score(row):
        if pd.isna(row['PE_Percentile']) or pd.isna(row['MA200_Distance']) or pd.isna(row['VIX']):
            return 50
        
        score = 0
        
        # 估值评分 (越低越适合买入，最高40分)
        pe_score = (1 - row['PE_Percentile']) * 40
        
        # 趋势评分 (超跌反弹，最高30分)
        if row['MA200_Distance'] < -20:
            trend_score = 30
        elif row['MA200_Distance'] < -10:
            trend_score = 20 + (row['MA200_Distance'] + 20) / 10 * 10
        elif row['MA200_Distance'] < 0:
            trend_score = 10 + (row['MA200_Distance'] + 10) / 10 * 10
        else:
            trend_score = max(0, 10 - row['MA200_Distance'])
        
        # VIX评分 (越高越恐慌越适合买入，最高30分)
        if row['VIX'] > 30:
            vix_score = 30
        elif row['VIX'] > 20:
            vix_score = 15 + (row['VIX'] - 20) / 10 * 15
        else:
            vix_score = row['VIX'] / 20 * 15
        
        return round(pe_score + trend_score + vix_score)
    
    merged['Score'] = merged.apply(calculate_score, axis=1)
    
    # 生成交易信号
    def get_signal(row):
        score = row['Score']
        vix = row['VIX']
        ma_dist = row['MA200_Distance']
        
        if score >= 75 and vix > 20:
            return '买入', '强烈建议买入（高恐慌+低估值）'
        elif score >= 65:
            return '买入', '建议买入（估值合理或超跌）'
        elif score <= 25 and ma_dist > 15:
            return '卖出', '建议卖出（高估+超买）'
        elif score <= 35 and ma_dist > 10:
            return '卖出', '考虑减仓（相对高估）'
        else:
            return '持有', '继续持有观望'
    
    signals = merged.apply(get_signal, axis=1, result_type='expand')
    merged['Signal'] = signals[0]
    merged['Signal_Desc'] = signals[1]
    
    return merged

def load_existing_data() -> Dict:
    """加载已有数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"last_update": "", "daily_data": {}}

def save_data(data: Dict):
    """保存数据到文件"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_data():
    """主更新函数"""
    print(f"开始更新数据: {datetime.now()}")
    
    try:
        # 获取数据
        ndx_df = fetch_nasdaq_data()
        vix_df = fetch_vix_data()
        
        # 计算信号
        result_df = calculate_signals(ndx_df, vix_df)
        
        # 加载已有数据
        existing = load_existing_data()
        daily_data = existing.get('daily_data', {})
        
        # 更新数据
        for _, row in result_df.iterrows():
            if pd.isna(row['Close']):
                continue
            
            date_str = row['Date'].strftime('%Y-%m-%d')
            
            daily_data[date_str] = {
                'price': float(row['Close']),
                'change': float(row['Change']) if not pd.isna(row['Change']) else 0,
                'change_percent': float(row['Change_Percent']) if not pd.isna(row['Change_Percent']) else 0,
                'vix': float(row['VIX']) if not pd.isna(row['VIX']) else 20,
                'pe_percentile': float(row['PE_Percentile']) if not pd.isna(row['PE_Percentile']) else 0.5,
                'ma200_distance': float(row['MA200_Distance']) if not pd.isna(row['MA200_Distance']) else 0,
                'score': int(row['Score']) if not pd.isna(row['Score']) else 50,
                'signal': str(row['Signal']),
                'signal_desc': str(row['Signal_Desc'])
            }
        
        # 保存
        output = {
            'last_update': datetime.now().isoformat(),
            'daily_data': daily_data
        }
        save_data(output)
        
        print(f"数据更新完成，共 {len(daily_data)} 个交易日")
        
        # 显示最近5天数据
        recent_dates = sorted(daily_data.keys())[-5:]
        print("\n最近5天数据预览:")
        for date in recent_dates:
            d = daily_data[date]
            print(f"{date}: 价格={d['price']:.2f}, 信号={d['signal']}, 评分={d['score']}")
        
    except Exception as e:
        print(f"更新失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    update_data()
