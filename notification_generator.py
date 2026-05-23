# -*- coding: utf-8 -*-
"""通知图片生成器"""
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from flask import current_app


class NotificationImageGenerator:
    """通知图片生成器类"""
    
    COLORS = {
        'normal': {
            'header': (52, 152, 219),
            'header_text': (255, 255, 255),
            'body_bg': (255, 255, 255),
            'title': (44, 62, 80),
            'content': (52, 73, 94),
            'footer': (236, 240, 241),
            'border': (52, 152, 219)
        },
        'important': {
            'header': (243, 156, 18),
            'header_text': (255, 255, 255),
            'body_bg': (255, 254, 240),
            'title': (44, 62, 80),
            'content': (52, 73, 94),
            'footer': (254, 249, 231),
            'border': (243, 156, 18)
        },
        'urgent': {
            'header': (231, 76, 60),
            'header_text': (255, 255, 255),
            'body_bg': (255, 245, 245),
            'title': (192, 57, 43),
            'content': (52, 73, 94),
            'footer': (253, 234, 234),
            'border': (231, 76, 60)
        }
    }
    
    def __init__(self, width=600):
        self.width = width
        self.padding = 30
        self.header_height = 60
        self.footer_height = 50
    
    def get_font(self, size, bold=False):
        """获取字体"""
        try:
            if bold:
                return ImageFont.truetype("msyhbd.ttc", size)
            return ImageFont.truetype("msyh.ttc", size)
        except:
            try:
                if bold:
                    return ImageFont.truetype("simhei.ttf", size)
                return ImageFont.truetype("simsun.ttc", size)
            except:
                return ImageFont.load_default()
    
    def wrap_text(self, text, font, max_width):
        """文字换行"""
        lines = []
        words = text.split('\n')
        for word in words:
            if not word:
                lines.append('')
                continue
            words_list = word.split()
            current_line = ''
            for w in words_list:
                test_line = current_line + ' ' + w if current_line else w
                bbox = font.getbbox(test_line)
                if bbox[2] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = w
            if current_line:
                lines.append(current_line)
        return lines
    
    def generate(self, title, content, priority='normal', sender_name='', company_name='公司通知', user_image_path=None):
        """生成通知图片（支持包含用户上传的图片）"""
        colors = self.COLORS.get(priority, self.COLORS['normal'])
        
        title_font = self.get_font(28, bold=True)
        content_font = self.get_font(18, bold=False)
        footer_font = self.get_font(14, bold=False)
        
        content_width = self.width - 2 * self.padding
        title_lines = self.wrap_text(title, title_font, content_width)
        content_lines = self.wrap_text(content, content_font, content_width)
        
        line_height = 30
        title_height = len(title_lines) * 40
        content_height = len(content_lines) * line_height
        
        # 计算用户上传图片的高度
        user_image_height = 0
        has_user_image = False
        if user_image_path and os.path.exists(user_image_path):
            try:
                with Image.open(user_image_path) as user_img:
                    # 计算缩放后的高度（保持宽高比，宽度为content_width）
                    img_width, img_height = user_img.size
                    scale_ratio = content_width / img_width
                    user_image_height = int(img_height * scale_ratio)
                    # 限制最大高度
                    if user_image_height > 300:
                        user_image_height = 300
                    has_user_image = True
            except:
                has_user_image = False
        
        body_padding = 40
        image_padding = 20 if has_user_image else 0
        
        total_height = self.header_height + title_height + body_padding + content_height + image_padding + user_image_height + body_padding + self.footer_height
        
        img = Image.new('RGB', (self.width, total_height), colors['body_bg'])
        draw = ImageDraw.Draw(img)
        
        # 绘制头部
        draw.rectangle([(0, 0), (self.width, self.header_height)], fill=colors['header'])
        
        # 绘制标题
        y = self.header_height + 15
        for line in title_lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_width = bbox[2] - bbox[0]
            x = (self.width - text_width) // 2
            draw.text((x, y), line, font=title_font, fill=colors['title'])
            y += 40
        
        # 绘制分隔线
        y += 10
        draw.line([(self.padding, y), (self.width - self.padding, y)], fill=colors['border'], width=2)
        y += 20
        
        # 绘制内容
        for line in content_lines:
            draw.text((self.padding, y), line, font=content_font, fill=colors['content'])
            y += line_height
        
        # 如果有用户上传的图片，添加到内容下方
        if has_user_image and user_image_path and os.path.exists(user_image_path):
            try:
                with Image.open(user_image_path) as user_img:
                    y += image_padding
                    img_width, img_height = user_img.size
                    scale_ratio = content_width / img_width
                    scaled_height = int(img_height * scale_ratio)
                    if scaled_height > 300:
                        scale_ratio = 300 / img_height
                        scaled_width = int(img_width * scale_ratio)
                        scaled_height = 300
                    else:
                        scaled_width = content_width
                    
                    user_img = user_img.resize((scaled_width, scaled_height), Image.LANCZOS)
                    
                    # 计算居中位置
                    x = (self.width - scaled_width) // 2
                    img.paste(user_img, (x, y))
                    y += scaled_height
            except Exception as e:
                print(f"添加用户图片失败: {e}")
        
        # 绘制底部
        y = total_height - self.footer_height + 15
        footer_text = f"{company_name}"
        if sender_name:
            footer_text += f"  |  发布人：{sender_name}"
        footer_text += f"  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) // 2
        draw.text((x, y), footer_text, font=footer_font, fill=(128, 128, 128))
        
        # 绘制边框
        draw.rectangle([(0, 0), (self.width - 1, total_height - 1)], outline=colors['border'], width=3)
        
        return img
    
    def save(self, img, notification_id):
        """保存图片"""
        save_dir = os.path.join(os.path.dirname(__file__), 'static', 'notifications')
        os.makedirs(save_dir, exist_ok=True)
        
        filename = f"notification_{notification_id}.png"
        filepath = os.path.join(save_dir, filename)
        img.save(filepath, 'PNG', quality=95)
        
        return f"/static/notifications/{filename}"


def create_notification_image(title, content, priority='normal', sender_name='', notification_id=None, user_image_path=None):
    """创建通知图片的便捷函数（支持包含用户上传的图片）"""
    if notification_id is None:
        import time
        notification_id = int(time.time() * 1000)
    
    # 将相对路径转换为绝对路径
    if user_image_path and user_image_path.startswith('/'):
        user_image_path = os.path.join(os.path.dirname(__file__), user_image_path.lstrip('/'))
    
    generator = NotificationImageGenerator()
    img = generator.generate(title, content, priority, sender_name, user_image_path=user_image_path)
    image_path = generator.save(img, notification_id)
    
    return image_path, notification_id
