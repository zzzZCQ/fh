# -*- coding: utf-8 -*-
"""检查已处理的日期文件"""
import os

BEHAVIOR_DATA_DIR = os.path.join(os.path.dirname(__file__), 'behavior_tracking_data')

for user_folder in os.listdir(BEHAVIOR_DATA_DIR):
    user_dir = os.path.join(BEHAVIOR_DATA_DIR, user_folder)
    if os.path.isdir(user_dir):
        processed_file = os.path.join(user_dir, 'processed_dates.txt')
        if os.path.exists(processed_file):
            with open(processed_file, 'r', encoding='utf-8') as f:
                dates = f.readlines()
            print(f"{user_folder} 的已处理日期：")
            for d in dates:
                print(f"  {d.strip()}")
        else:
            print(f"{user_folder} 没有已处理日期文件")
        
        print(f"\n{user_folder} 目录中的文件：")
        for f in os.listdir(user_dir):
            print(f"  {f}")
        print()
