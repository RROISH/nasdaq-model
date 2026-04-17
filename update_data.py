#!/usr/bin/env python3
"""
纳指买卖模型 - v4.3 纳斯达克综合指数版 (^IXIC)
显示点位：24102（纳斯达克综合指数）
估值(40) + 恐慌(35) + 趋势(25) = 100分
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 尝试导入akshare
try:
    import akshare as ak
    print(f"✅ AKShare版本: {ak.__version__}")
except ImportError:
    os.system("pip install akshare --quiet")
    import akshare as ak
    print(f"✅ AKShare已安装，版本: {ak.__version__}")

DATA_FILE = "data/nasdaq_data.json"

def fetch_ixic_sina():
    """从新浪财经获取纳斯达克综合指数历史数据（^IXIC）"""
    print("\n=== 获取纳斯达克综合指数（新浪财经）===")
    
    try:
        # 关键修改：改为 .IXIC（纳斯达克综合指数）
        print("正在调用 ak.index_us_stock_sina('.IXIC') ...")
        df = ak.index_us_stock_sina(symbol=".IXIC")
        
        if df.empty:
            raise ValueError("新浪返回空数据")
        
        print(f"✅ 获取原始数据 {len(df)} 条")
        print(f"📅 原始数据范围: {df['date'].min()} 至 {df['date'].max()}")
        
        # 只取最近10年
        df = df.tail(252 * 10).copy()
        
        # 标准化列名
        df = df.rename(columns={
            'date': 'Date',
            'close': 'Close'
        })
        
        # 确保日期格式正确（移除时区）
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        
        latest_date = df['Date'].max()
        latest_price = df['Close'].iloc[-1]
        print(f"📊 截取后最新日期: {latest_date.strftime('%Y-%m-%d')}")
        print(f"📈 最新收盘点位: {latest_price:.2f}")  # 应该显示24102左右
        
        # 检查数据新鲜度
        today = datetime.now()
        diff_days = (today - latest_date).days
        
        if diff_days > 1:
            print(f"⚠️ 警告: 数据延迟 {diff_days} 天")
            weekday = latest_date.weekday()
            if weekday >= 5:
                print(f"💡 提示: 最新日期是周{'六' if weekday == 5 else '日'}，美股周末休市")
        else:
            print(f"✅ 数据较新（相差{diff_days}天）")
        
        return df[['Date', 'Close']].dropna(), "^IXIC", latest_date.strftime('%Y-%m-%d')
        
    except Exception as e:
        print(f"❌ 新浪数据源失败: {e}")
        import traceback
        traceback.print_exc()
        raise

def fetch_vix_sina():
    """获取VIX数据（新浪财经）"""
    print("\n=== 获取VIX恐慌指数 ===")
    
    try:
        print("正在调用 ak.index_us_stock_sina('.VIX') ...")
        df = ak.index_us_stock_sina(symbol=".VIX")
        
        if df.empty:
            raise ValueError("VIX返回空数据")
        
        # 取最近10年
        df = df.tail(252 * 10).copy()
        
        df = df.rename(columns={
            'date': 'Date',
            'close': 'Close'
        })
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        
        print(f"✅ VIX获取成功，最新日期: {df['Date'].max().strftime('%Y-%m-%d')}")
        return df[['Date', 'Close']].dropna()
        
    except Exception as e:
        print(f"⚠️ VIX获取失败: {e}，将使用默认值20")
        return pd.DataFrame(columns=['Date', 'Close'])

def calculate_signals(ixic_df, vix_df, ticker_used):
    """计算三维度交易信号"""
    print("\n=== 计算三维度评分 ===")
    
    # 合并数据
    merged = pd.merge(ixic_df, vix_df.rename(columns={'Close': 'VIX'}), 
                     on='Date', how='left')
    
    # VIX缺失值用20填充
    merged['VIX'] = merged['VIX'].ffill().fillna(20)
    
    prices = merged['Close'].values.astype(float)
    vix_values = merged['VIX'].values.astype(float)
    dates = merged['Date'].values
    n = len(prices)
    
    print(f"📊 合并后数据量: {n} 天")
    print(f"📅 计算范围: {pd.to_datetime(dates.min()).strftime('%Y-%m-%d')} 至 {pd.to_datetime(dates.max()).strftime('%Y-%m-%d')}")
    
    if n < 252:
        raise ValueError(f"数据不足一年(252日)，仅有{n}条")
    
    # 52周高低点（252个交易日）
    high_52w = np.array([np.max(prices[max(0, i-251):i+1]) for i in range(n)])
    low_52w = np.array([np.min(prices[max(0, i-251):i+1]) for i in range(n)])
    position_52w = (prices - low_52w) / (high_52w - low_52w + 1e-10)
    
    # 200日均线
    print("计算200日均线...")
    ma200 = np.array([np.mean(prices[max(0, i-199):i+1]) for i in range(n)])
    ma_dist = (prices - ma200) / (ma200 + 1e-10) * 100
    
    scores = []
    details = []
    
    print("计算每日评分...")
    for i in range(n):
        # 维度1: 估值(40分)
        pos = position_52w[i]
        if pos > 0.9: val_score = 5
        elif pos > 0.7: val_score = 15
        elif pos > 0.5: val_score = 25
        elif pos > 0.3: val_score = 32
        else: val_score = 40
        
        # 维度2: 恐慌(35分)
        vix = vix_values[i]
        if vix >= 45: fear_score = 35
        elif vix >= 35: fear_score = 30 + (vix - 35) / 10 * 5
        elif vix >= 25: fear_score = 20 + (vix - 25) / 10 * 10
        elif vix >= 15: fear_score = (vix - 15) / 10 * 20
        else: fear_score = max(0, (vix - 10) / 5 * 5)
        
        # 维度3: 趋势(25分)
        dist = ma_dist[i]
        if dist <= -25: trend_score = 25
        elif dist <= -15: trend_score = 20 + (dist + 25) / 10 * 5
        elif dist <= -5: trend_score = 10 + (dist + 15) / 10 * 10
        elif dist < 10: trend_score = 5 + max(0, (5 - dist) / 15 * 5)
        else: trend_score = max(0, 5 - (dist - 10) / 5)
        
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
        if score >= 90: signals.append(('强烈买入', '🔥 历史级买点，建议重仓'))
        elif score >= 75: signals.append(('买入', '📈 较好买入时机'))
        elif score >= 60: signals.append(('定投', '💰 可开始定投或轻仓'))
        elif score >= 40: signals.append(('持有', '⏸️ 持有观望'))
        elif score >= 25: signals.append(('减仓', '⚠️ 考虑部分止盈'))
        elif score >= 10: signals.append(('卖出', '📉 高估区域，建议减仓'))
        else: signals.append(('强烈卖出', '🚨 泡沫区域，清仓避险'))
    
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
        'Index_Type': ticker_used
    })
    
    return result

def main():
    print(f"=== 纳指模型 v4.3 (纳斯达克综合指数 ^IXIC) ===")
    print(f"⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 工作目录: {os.getcwd()}")
    print(f"📈 目标指数: 纳斯达克综合指数 (^IXIC)")
    
    try:
        # 关键修改：获取IXIC数据而非NDX
        ixic_df, ticker_used, sina_latest_date = fetch_ixic_sina()
        vix_df = fetch_vix_sina()
        
        # 计算信号
        result = calculate_signals(ixic_df, vix_df, ticker_used)
        
        # 加载旧数据
        print("\n=== 加载现有JSON数据 ===")
        old_data = {}
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    old_data = json.load(f).get('daily_data', {})
                print(f"✅ 加载现有数据: {len(old_data)} 天")
                if old_data:
                    print(f"📅 现有数据范围: {min(old_data.keys())} 至 {max(old_data.keys())}")
            except Exception as e:
                print(f"⚠️ 无法读取旧数据（将创建新文件）: {e}")
        else:
            print(f"⚠️ 数据文件不存在（将创建新文件）")
        
        # 合并新数据（强制更新）
        print("\n=== 合并数据 ===")
        update_count = 0
        skipped = 0
        
        for _, row in result.iterrows():
            if pd.isna(row['Price']):
                skipped += 1
                continue
                
            date = row['Date'].strftime('%Y-%m-%d')
            
            # 检查是否是新数据或数据有变化
            if date in old_data:
                old_price = old_data[date].get('price', 0)
                new_price = float(row['Price'])
                # 如果价格变化小于0.01，视为相同数据
                if abs(old_price - new_price) < 0.01:
                    pass
            
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
                'index_type': str(row['Index_Type']),
                'data_source': 'sina'
            }
            update_count += 1
        
        print(f"✅ 处理数据: {update_count} 天")
        if skipped > 0:
            print(f"⚠️ 跳过无效数据: {skipped} 条")
        
        # 保存（强制写入）
        print("\n=== 保存数据 ===")
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        
        output = {
            'last_update': datetime.now().isoformat(),
            'data_source': 'sina',
            'index_used': ticker_used,
            'version': '4.3',
            'daily_data': old_data
        }
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        # 验证写入
        file_size = os.path.getsize(DATA_FILE)
        print(f"✅ 已保存到 {DATA_FILE}")
        print(f"📦 文件大小: {file_size} bytes")
        print(f"📊 总记录数: {len(old_data)} 天")
        
        # 显示最近3天
        recent_dates = sorted(old_data.keys())[-3:]
        print(f"\n📈 最近3天数据（保存后）:")
        for d in recent_dates:
            data = old_data[d]
            print(f"   {d}: {data['score']}分 | 点位:{data['price']:.2f} | VIX:{data['vix']:.2f}")
        
        # 检查新浪最新日期是否在文件中
        if sina_latest_date in old_data:
            print(f"\n✅ 确认: 新浪最新日期 {sina_latest_date} 已写入文件")
            latest_price = old_data[sina_latest_date]['price']
            print(f"📈 最新点位: {latest_price:.2f} (预期: 24102.70左右)")
        else:
            print(f"\n⚠️ 警告: 新浪最新日期 {sina_latest_date} 未找到于文件中！")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 致命错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
