# -*- coding: utf-8 -*-
"""钉钉配置路由"""
import os
import re
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

bp = Blueprint('dingtalk', __name__)


# ============ 钉钉群配置页面 ============
@bp.route('/dingtalk/setup')
def dingtalk_setup():
    """钉钉群配置页面 - 通过JSAPI选择群获取openConversationId"""
    return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>配置钉钉群</title>
    <script src="https://g.alicdn.com/dingding/dingtalk-jsapi/3.0.25/dingtalk.open.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f7fa; padding: 20px; }
        .container { max-width: 500px; margin: 0 auto; }
        h1 { font-size: 20px; color: #333; margin-bottom: 20px; }
        .card { background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .card h3 { font-size: 16px; color: #333; margin-bottom: 12px; }
        .card p { font-size: 14px; color: #666; line-height: 1.6; margin-bottom: 12px; }
        .btn { display: inline-block; padding: 10px 24px; background: #1677ff; color: #fff; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; }
        .btn:hover { background: #4096ff; }
        .btn:disabled { background: #ccc; cursor: not-allowed; }
        .status { padding: 12px; border-radius: 8px; margin-top: 12px; font-size: 14px; }
        .success { background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }
        .error { background: #fff2f0; color: #ff4d4f; border: 1px solid #ffccc7; }
        .info { background: #e6f4ff; color: #1677ff; border: 1px solid #91caff; }
        .result { margin-top: 12px; padding: 12px; background: #f9f9f9; border-radius: 8px; font-size: 13px; word-break: break-all; }
        .step { display: flex; align-items: flex-start; margin-bottom: 12px; }
        .step-num { width: 24px; height: 24px; background: #1677ff; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; margin-right: 10px; flex-shrink: 0; }
        .step-text { font-size: 14px; color: #333; line-height: 24px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>配置钉钉群</h1>
        <div class="card">
            <h3>操作步骤</h3>
            <div class="step">
                <div class="step-num">1</div>
                <div class="step-text">确保你在<strong>钉钉客户端</strong>中打开此页面</div>
            </div>
            <div class="step">
                <div class="step-num">2</div>
                <div class="step-text">确保目标群中已添加<strong>企业内部机器人</strong>（群设置 &gt; 机器人 &gt; 添加机器人 &gt; 企业内部机器人）</div>
            </div>
            <div class="step">
                <div class="step-num">3</div>
                <div class="step-text">点击下方按钮，在弹出的列表中选择目标群</div>
            </div>
        </div>
        <div class="card">
            <h3>选择群会话</h3>
            <button class="btn" id="chooseBtn" onclick="chooseChat()">选择钉钉群</button>
            <div id="status"></div>
            <div id="result"></div>
        </div>
        <div class="card" id="currentConfig" style="display:none;">
            <h3>当前配置</h3>
            <div class="result" id="configInfo"></div>
        </div>
    </div>
    <script>
        fetch('/api/dingtalk/config').then(function(r){return r.json()}).then(function(data){
            if(data.open_conversation_id){
                document.getElementById('currentConfig').style.display='block';
                document.getElementById('configInfo').innerHTML='<strong>openConversationId:</strong> '+data.open_conversation_id;
            }
        });
        function chooseChat(){
            var btn=document.getElementById('chooseBtn');
            var status=document.getElementById('status');
            var result=document.getElementById('result');
            btn.disabled=true;
            status.innerHTML='<div class="status info">正在打开群选择器...</div>';
            result.innerHTML='';
            if(typeof dd==='undefined'){
                status.innerHTML='<div class="status error">未检测到钉钉JSAPI，请在钉钉客户端中打开此页面</div>';
                btn.disabled=false;return;
            }
            dd.ready(function(){
                dd.biz.chat.chooseChat({
                    isConfirm:true,
                    onSuccess:function(chat){
                        console.log('选择的群信息:',chat);
                        var chatId=chat.chatId;
                        var title=chat.title||'未知群名';
                        status.innerHTML='<div class="status info">已选择群: '+title+'，正在保存...</div>';
                        fetch('/api/dingtalk/save_chat',{
                            method:'POST',
                            headers:{'Content-Type':'application/json'},
                            body:JSON.stringify({chat_id:chatId,title:title})
                        }).then(function(r){return r.json()}).then(function(data){
                            if(data.success){
                                status.innerHTML='<div class="status success">保存成功! 群: '+title+'</div>';
                                result.innerHTML='<div class="result"><strong>chatId:</strong> '+chatId+'<br><strong>openConversationId:</strong> '+(data.open_conversation_id||'获取中...')+'</div>';
                                if(data.open_conversation_id){
                                    document.getElementById('currentConfig').style.display='block';
                                    document.getElementById('configInfo').innerHTML='<strong>openConversationId:</strong> '+data.open_conversation_id;
                                }
                            }else{
                                status.innerHTML='<div class="status error">保存失败: '+(data.error||'未知错误')+'</div>';
                            }
                        }).catch(function(err){
                            status.innerHTML='<div class="status error">网络错误: '+err.message+'</div>';
                        });
                    },
                    onFail:function(err){
                        status.innerHTML='<div class="status error">选择群失败: '+JSON.stringify(err)+'</div>';
                    }
                });
            });
            dd.error(function(err){
                status.innerHTML='<div class="status error">JSAPI错误: '+JSON.stringify(err)+'</div>';
            });
            btn.disabled=false;
        }
    </script>
</body>
</html>"""


@bp.route('/api/dingtalk/config')
def api_dingtalk_config():
    """获取当前钉钉群配置"""
    from config import DINGTALK_OPEN_CONVERSATION_ID, DINGTALK_CHAT_ID
    return jsonify({
        'chat_id': DINGTALK_CHAT_ID,
        'open_conversation_id': DINGTALK_OPEN_CONVERSATION_ID
    })


@bp.route('/api/dingtalk/save_chat', methods=['POST'])
def api_dingtalk_save_chat():
    """保存群chatId并转换为openConversationId"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id', '')
        title = data.get('title', '')

        if not chat_id:
            return jsonify({'success': False, 'error': 'chatId为空'})

        print(f"[DEBUG] 保存群配置: chatId={chat_id}, title={title}")

        # 1. 转换 chatId -> openConversationId
        from services import _get_dingtalk_token
        token = _get_dingtalk_token()

        import requests as req
        url = f'https://api.dingtalk.com/v1.0/im/chat/{chat_id}/convertToOpenConversationId'
        headers = {
            'x-acs-dingtalk-access-token': token,
            'Content-Type': 'application/json'
        }
        resp = req.post(url, headers=headers, timeout=10)
        result = resp.json()

        print(f"[DEBUG] 转换结果: {result}")

        if 'openConversationId' not in result:
            error_msg = result.get('message', '转换失败')
            return jsonify({'success': False, 'error': f'chatId转换失败: {error_msg}'})

        open_conversation_id = result['openConversationId']
        print(f"[DEBUG] openConversationId: {open_conversation_id}")

        # 2. 保存到配置文件
        config_path = os.path.join(os.path.dirname(__file__), 'config.py')
        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        # 更新 DINGTALK_OPEN_CONVERSATION_ID
        config_content = re.sub(
            r"DINGTALK_OPEN_CONVERSATION_ID\s*=\s*os\.environ\.get\('DINGTALK_OPEN_CONVERSATION_ID',\s*'[^']*'\)",
            f"DINGTALK_OPEN_CONVERSATION_ID = os.environ.get('DINGTALK_OPEN_CONVERSATION_ID', '{open_conversation_id}')",
            config_content
        )

        # 更新 DINGTALK_CHAT_ID
        config_content = re.sub(
            r"DINGTALK_CHAT_ID\s*=\s*os\.environ\.get\('DINGTALK_CHAT_ID',\s*'[^']*'\)",
            f"DINGTALK_CHAT_ID = os.environ.get('DINGTALK_CHAT_ID', '{chat_id}')",
            config_content
        )

        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)

        # 3. 更新运行时配置
        import config
        config.DINGTALK_OPEN_CONVERSATION_ID = open_conversation_id
        config.DINGTALK_CHAT_ID = chat_id

        print(f"[DEBUG] 配置已保存: chatId={chat_id}, openConversationId={open_conversation_id}")

        return jsonify({
            'success': True,
            'chat_id': chat_id,
            'open_conversation_id': open_conversation_id,
            'title': title
        })

    except Exception as e:
        import traceback
        print(f"[ERROR] 保存群配置失败: {e}")
        print(f"[ERROR] {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)})
