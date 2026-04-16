#!/usr/bin/env python3
"""
纳指模型数据更新脚本
纯净Python代码，自动获取数据并生成JSON和HTML
"""

import yfinance as yf
import json
import os
import shutil
from datetime import datetime

def get_market_data():
    """获取纳指和VIX数据"""
    print("正在获取纳指数据...")
    
    try:
        # 获取纳指数据
        ndx = yf.Ticker("^IXIC")
        hist = ndx.history(period="1year")
        
        if hist.empty:
            raise ValueError("无法获取纳指数据")
        
        latest = hist.iloc[-1]
        prev = hist.iloc[-2]
        close = float(latest['Close'])
        
        # 计算涨跌幅
        change_1d = ((close - float(prev['Close'])) / float(prev['Close'])) * 100
        change_5d = ((close - float(hist.iloc[-6]['Close'])) / float(hist.iloc[-6]['Close'])) * 100 if len(hist) >= 6 else 0
        
        # 52周高低点
        high_52w = float(hist['High'].max())
        low_52w = float(hist['Low'].min())
        position_52w = ((close - low_52w) / (high_52w - low_52w)) * 100
        
        # 50日均线
        ma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
        ma50_deviation = ((close - float(ma_50)) / float(ma_50)) * 100
        
        # 获取VIX
        try:
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="5d")
            vix_value = float(vix_hist.iloc[-1]['Close']) if not vix_hist.empty else 18.0
        except Exception as e:
            print(f"VIX获取失败，使用默认值: {e}")
            vix_value = 18.0
        
        data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "close": round(close, 2),
            "change_1d": round(change_1d, 2),
            "change_5d": round(change_5d, 2),
            "position_52w": round(position_52w, 2),
            "ma50_deviation": round(ma50_deviation, 2),
            "vix": round(vix_value, 2)
        }
        
        return data
        
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None

def main():
    # 创建output目录
    os.makedirs('output', exist_ok=True)
    
    # 获取数据
    data = get_market_data()
    if not data:
        print("错误：无法获取市场数据")
        exit(1)
    
    # 保存JSON数据
    json_path = 'output/latest.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ 数据已保存: {json_path}")
    
    # 复制index.html到output目录（如果存在）
    if os.path.exists('index.html'):
        shutil.copy('index.html', 'output/index.html')
        print("✓ HTML已复制到output目录")
    else:
        print("⚠ 警告：未找到index.html文件")
    
    print(f"\n数据摘要: 纳指 {data['close']}, VIX {data['vix']}, 位置 {data['position_52w']}%")

if __name__ == "__main__":
    main()
