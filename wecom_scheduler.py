# -*- coding: utf-8 -*-
"""
企业微信营销消息定时调度器
"""
import os
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from wecom_auto_bot import WeComAutoBot


class WeComScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.bot = None
        self.data_dir = os.path.join(os.path.dirname(__file__), 'wecom_data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.scheduled_tasks_file = os.path.join(self.data_dir, 'scheduled_tasks.json')
        self._init_tasks_file()
    
    def _init_tasks_file(self):
        """初始化任务文件"""
        if not os.path.exists(self.scheduled_tasks_file):
            with open(self.scheduled_tasks_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def get_scheduled_tasks(self):
        """获取所有定时任务"""
        with open(self.scheduled_tasks_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def add_scheduled_task(self, task_name: str, customer_names: list, 
                           template_id: int, send_time: str, cron_expr: str = None) -> bool:
        """添加定时任务
        
        Args:
            task_name: 任务名称
            customer_names: 客户名称列表
            template_id: 消息模板ID
            send_time: 发送时间 (YYYY-MM-DD HH:MM)
            cron_expr: Cron表达式（可选，用于周期性任务）
            
        Returns:
            是否添加成功
        """
        tasks = self.get_scheduled_tasks()
        new_id = max([t['id'] for t in tasks], default=0) + 1
        
        task = {
            'id': new_id,
            'name': task_name,
            'customer_names': customer_names,
            'template_id': template_id,
            'send_time': send_time,
            'cron_expr': cron_expr,
            'status': 'pending',  # pending, running, done, cancelled
            'created_time': datetime.now().isoformat()
        }
        
        tasks.append(task)
        with open(self.scheduled_tasks_file, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        
        # 添加到调度器
        self._schedule_task(task)
        print(f"[Scheduler] 已添加定时任务: {task_name}")
        return True
    
    def _schedule_task(self, task: dict):
        """将任务添加到调度器"""
        send_datetime = datetime.fromisoformat(task['send_time'])
        
        if task['cron_expr']:
            # Cron表达式任务
            cron_parts = task['cron_expr'].split()
            if len(cron_parts) >= 5:
                self.scheduler.add_job(
                    self._execute_task,
                    'cron',
                    args=[task['id']],
                    id=str(task['id']),
                    minute=cron_parts[0],
                    hour=cron_parts[1],
                    day=cron_parts[2],
                    month=cron_parts[3],
                    day_of_week=cron_parts[4]
                )
        else:
            # 单次定时任务
            self.scheduler.add_job(
                self._execute_task,
                'date',
                args=[task['id']],
                id=str(task['id']),
                run_date=send_datetime
            )
    
    def _execute_task(self, task_id: int):
        """执行任务"""
        print(f"[Scheduler] 开始执行任务: {task_id}")
        
        tasks = self.get_scheduled_tasks()
        task = next((t for t in tasks if t['id'] == task_id), None)
        if not task:
            print(f"[Scheduler] 任务不存在: {task_id}")
            return
        
        # 更新任务状态
        task['status'] = 'running'
        with open(self.scheduled_tasks_file, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        
        try:
            # 启动机器人并发送消息
            if not self.bot:
                self.bot = WeComAutoBot(headless=True)
                self.bot.launch()
                self.bot.login(wait_scan=False)  # 需要先登录
            
            # 获取消息模板
            templates = self.bot.get_message_templates()
            template = next((t for t in templates if t['id'] == task['template_id']), None)
            
            if template:
                # 批量发送
                success_count = self.bot.send_messages_to_multiple(
                    task['customer_names'],
                    template['content'],
                    interval=3
                )
                print(f"[Scheduler] 任务完成: 成功发送 {success_count}/{len(task['customer_names'])} 条消息")
            
            # 更新任务状态
            task['status'] = 'done'
            task['done_time'] = datetime.now().isoformat()
            
        except Exception as e:
            print(f"[Scheduler] 任务执行失败: {e}")
            task['status'] = 'error'
            task['error_msg'] = str(e)
        
        with open(self.scheduled_tasks_file, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    
    def start(self):
        """启动调度器"""
        # 加载已有的任务
        tasks = self.get_scheduled_tasks()
        for task in tasks:
            if task['status'] == 'pending':
                send_datetime = datetime.fromisoformat(task['send_time'])
                if send_datetime > datetime.now():
                    self._schedule_task(task)
        
        self.scheduler.start()
        print("[Scheduler] 定时任务调度器已启动")
    
    def shutdown(self):
        """关闭调度器"""
        self.scheduler.shutdown()
        if self.bot:
            self.bot.close()
        print("[Scheduler] 定时任务调度器已关闭")


# 单例
_scheduler_instance = None

def get_wecom_scheduler() -> WeComScheduler:
    global _scheduler_instance
    if not _scheduler_instance:
        _scheduler_instance = WeComScheduler()
    return _scheduler_instance
