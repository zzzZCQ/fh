# -*- coding: utf-8 -*-
"""
企业微信 SCRM 三方托管 - API 封装层
===============================
基于企业微信开发者文档：
  - access_token:           https://developer.work.weixin.qq.com/document/path/91039
  - 外部联系人列表:          https://developer.work.weixin.qq.com/document/path/92113
  - 外部联系人详情:          https://developer.work.weixin.qq.com/document/path/91336
  - 客户联系"企业"管理:      https://developer.work.weixin.qq.com/document/path/91335
  - 获取客户群列表:          https://developer.work.weixin.qq.com/document/path/92122
  - 扫码登录(企业内部):       https://developer.work.weixin.qq.com/document/path/98176
  - 扫码登录(第三方应用):     https://developer.work.weixin.qq.com/document/path/99247
"""

import json
import time
import requests
from typing import Optional, Dict, List, Tuple


class WecomScrmService:
    """企业微信 SCRM 服务 - 封装所有 API 调用"""

    BASE_URL = 'https://qyapi.weixin.qq.com'

    def __init__(self, corp_id: str, contact_secret: str):
        """
        Args:
            corp_id: 企业ID
            contact_secret: 客户联系Secret (外部联系人专用)
        """
        self.corp_id = corp_id
        self.contact_secret = contact_secret
        self._access_token_cache: Optional[str] = None
        self._access_token_expire_at: float = 0

    # ---------- access_token ----------

    def get_access_token(self) -> str:
        """获取 access_token（带本地缓存）

        接口: GET /cgi-bin/gettoken?corpid=CORPID&corpsecret=SECRET
        返回: {"errcode": 0, "errmsg": "ok", "access_token": "xxx", "expires_in": 7200}
        """
        # 未过期直接返回
        if self._access_token_cache and time.time() < self._access_token_expire_at - 60:
            return self._access_token_cache

        # 重新获取
        url = f'{self.BASE_URL}/cgi-bin/gettoken'
        params = {'corpid': self.corp_id, 'corpsecret': self.contact_secret}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if data.get('errcode') != 0:
            raise RuntimeError(f'获取 access_token 失败: {data.get("errmsg")}')

        self._access_token_cache = data['access_token']
        expires_in = data.get('expires_in', 7200)
        self._access_token_expire_at = time.time() + expires_in
        return self._access_token_cache

    # ---------- 外部联系人：获取配置了客户联系功能的成员 ----------

    def get_follow_user_list(self) -> List[Dict]:
        """获取配置了客户联系功能的成员列表

        接口: POST /cgi-bin/externalcontact/get_follow_user_list
        Body: {}
        返回: {"errcode": 0, "follow_user": [{"userid": "xxx", "remark": "xxx"}, ...]}
        """
        token = self.get_access_token()
        url = f'{self.BASE_URL}/cgi-bin/externalcontact/get_follow_user_list?access_token={token}'
        resp = requests.post(url, json={}, timeout=10)
        data = resp.json()

        if data.get('errcode') != 0:
            raise RuntimeError(f'获取客户联系成员失败: {data.get("errmsg")}')

        return data.get('follow_user', [])

    # ---------- 外部联系人：批量获取外部联系人 ----------

    def get_external_contacts(self, userid: str, cursor: str = '', limit: int = 100) -> Dict:
        """获取指定成员的外部联系人（分页）

        接口: GET /cgi-bin/externalcontact/list?access_token=TOKEN&userid=USERID&cursor=CURSOR&limit=LIMIT
        返回: {
            "errcode": 0, "errmsg": "ok",
            "external_userid": ["xxx", "yyy", ...],
            "next_cursor": "xxx"  // 为空表示已取完
        }
        """
        token = self.get_access_token()
        url = f'{self.BASE_URL}/cgi-bin/externalcontact/list'
        params = {
            'access_token': token,
            'userid': userid,
            'cursor': cursor,
            'limit': limit,
        }
        resp = requests.get(url, params=params, timeout=10)
        return resp.json()

    def get_all_external_contacts(self, userid: str) -> List[str]:
        """分页获取某成员的全部外部联系人ID"""
        all_ids = []
        cursor = ''
        while True:
            data = self.get_external_contacts(userid, cursor=cursor, limit=100)
            if data.get('errcode') != 0:
                raise RuntimeError(f'获取外部联系人失败: {data.get("errmsg")}')
            all_ids.extend(data.get('external_userid', []))
            cursor = data.get('next_cursor', '')
            if not cursor:
                break
        return all_ids

    # ---------- 外部联系人：获取联系人详情 ----------

    def get_contact_detail(self, external_userid: str, cursor: str = '') -> Dict:
        """获取外部联系人详情

        接口: GET /cgi-bin/externalcontact/get?access_token=TOKEN&external_userid=EXT_USERID&cursor=CURSOR
        返回: {
            "errcode": 0,
            "external_contact": {
                "external_userid": "xxx",
                "name": "客户名称",
                "position": "职位",
                "avatar": "https://xxx",
                "corp_name": "企业名",
                "gender": 1,  // 0-未定义 1-男 2-女
                "unionid": "xxx",
            },
            "follow_user": [
                {"userid": "成员ID", "remark": "备注", "description": "描述",
                 "createtime": 123456789, "tags": ["标签1", "标签2"]}
            ],
            "next_cursor": "xxx"
        }
        """
        token = self.get_access_token()
        url = f'{self.BASE_URL}/cgi-bin/externalcontact/get'
        params = {
            'access_token': token,
            'external_userid': external_userid,
            'cursor': cursor,
        }
        resp = requests.get(url, params=params, timeout=10)
        return resp.json()

    # ---------- 外部联系人：批量获取外部联系人详情 ----------

    def batch_get_contact_detail(self, external_userid_list: List[str], userid: str = '') -> List[Dict]:
        """批量获取外部联系人详情

        接口: POST /cgi-bin/externalcontact/batch/get_by_user
        Body: {"userid": "xxx", "cursor": "", "limit": 100}
        返回: {
            "errcode": 0,
            "external_contact_list": [
                {
                    "external_contact": { ... },
                    "follow_info": { ... }
                }
            ],
            "next_cursor": "xxx"
        }
        """
        token = self.get_access_token()
        url = f'{self.BASE_URL}/cgi-bin/externalcontact/batch/get_by_user?access_token={token}'
        all_contacts = []

        # 按成员分页拉取（batch接口按用户维度拉取，而非按 external_userid 列表）
        cursor = ''
        while True:
            payload = {'userid': userid, 'cursor': cursor, 'limit': 100}
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()

            if data.get('errcode') != 0:
                # 若是权限问题（errcode=86012 表示当前未配置客户联系功能）
                if data.get('errcode') == 86012:
                    raise RuntimeError(f'成员 {userid} 未配置客户联系功能: {data.get("errmsg")}')
                raise RuntimeError(f'批量获取外部联系人失败: {data.get("errmsg")}')

            all_contacts.extend(data.get('external_contact_list', []))
            cursor = data.get('next_cursor', '')
            if not cursor:
                break

        return all_contacts

    # ---------- 企业成员：获取企业成员列表（用于账号托管识别） ----------

    def get_user_list(self, department_id: int = 1, fetch_child: bool = True) -> List[Dict]:
        """读取部门成员（简单信息）

        接口: GET /cgi-bin/user/simplelist?access_token=TOKEN&department_id=1&fetch_child=1
        返回: {"errcode": 0, "userlist": [{"userid": "xxx", "name": "xxx", "department": [1,2]}, ...]}
        """
        token = self.get_access_token()
        url = f'{self.BASE_URL}/cgi-bin/user/simplelist'
        params = {
            'access_token': token,
            'department_id': department_id,
            'fetch_child': 1 if fetch_child else 0,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if data.get('errcode') != 0:
            raise RuntimeError(f'获取成员列表失败: {data.get("errmsg")}')

        return data.get('userlist', [])

    def get_user_detail(self, userid: str) -> Dict:
        """读取成员详细信息

        接口: GET /cgi-bin/user/get?access_token=TOKEN&userid=USERID
        返回: {
            "errcode": 0, "errmsg": "ok",
            "userid": "xxx", "name": "xxx", "department": [1,2],
            "position": "xxx", "mobile": "xxx", "gender": "1",
            "email": "xxx", "avatar": "xxx", "status": 1,
            "enable": 1, "isleader": 1, ...
        }
        """
        token = self.get_access_token()
        url = f'{self.BASE_URL}/cgi-bin/user/get'
        params = {'access_token': token, 'userid': userid}
        resp = requests.get(url, params=params, timeout=10)
        return resp.json()

    def get_department_list(self) -> List[Dict]:
        """获取部门列表

        接口: GET /cgi-bin/department/list?access_token=TOKEN
        返回: {"errcode": 0, "department": [{"id": 1, "name": "xxx", "parentid": 0}, ...]}
        """
        token = self.get_access_token()
        url = f'{self.BASE_URL}/cgi-bin/department/list'
        params = {'access_token': token}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if data.get('errcode') != 0:
            raise RuntimeError(f'获取部门列表失败: {data.get("errmsg")}')

        return data.get('department', [])

    # ---------- 扫码登录（企业内部应用扫码授权） ----------

    def get_qr_connect_url(self, redirect_uri: str, agentid: str = '', state: str = 'wecom-scrm') -> Dict:
        """生成企业微信扫码托管二维码 URL

        参考: https://developer.work.weixin.qq.com/document/path/98176
        URL: https://open.work.weixin.qq.com/wwopen/sso/qrConnect
             ?appid=CORPID&agentid=AGENTID&redirect_uri=URI&state=STATE

        说明: agentid 为企业内自建应用的 agentid（扫码应用），
             扫码后企业微信会将 code 和 state 回传到 redirect_uri。
        """
        from urllib.parse import quote
        encoded_uri = quote(redirect_uri, safe='')
        agentid_param = f'&agentid={agentid}' if agentid else ''
        qr_url = (
            f'https://open.work.weixin.qq.com/wwopen/sso/qrConnect'
            f'?appid={self.corp_id}'
            f'{agentid_param}'
            f'&redirect_uri={encoded_uri}'
            f'&state={state}'
        )
        return {
            'qr_url': qr_url,
            'redirect_uri': redirect_uri,
            'agentid': agentid,
            'state': state,
        }

    def get_userinfo_by_code(self, code: str, qr_secret: str = '') -> Dict:
        """通过扫码回调的 code 获取成员 userid

        流程: 扫码 -> 企微回调 redirect_uri?code=CODE&state=STATE
              -> 后端用 code 调 /cgi-bin/user/getuserinfo3rd?access_token=TOKEN&code=CODE
              或 /cgi-bin/auth/getuserinfo?access_token=TOKEN&code=CODE

        注意: 获取 userinfo 需要用扫码应用自身的 secret 取 access_token，
              若传入 qr_secret 则使用它重新获取 token。
        返回: {
            "errcode": 0,
            "UserId": "xxx"  // 成员在企业的userid
        }
        """
        token = self.get_access_token()
        # 优先尝试新版 auth/getuserinfo
        url = f'{self.BASE_URL}/cgi-bin/auth/getuserinfo'
        params = {'access_token': token, 'code': code}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        # 如果新版接口返回错误，尝试旧版
        if data.get('errcode') != 0:
            url2 = f'{self.BASE_URL}/cgi-bin/user/getuserinfo'
            resp2 = requests.get(url2, params=params, timeout=10)
            data = resp2.json()

        if data.get('errcode') != 0:
            raise RuntimeError(f'通过 code 获取成员信息失败: {data.get("errmsg")}')

        return data

    # ---------- 快捷：同步一个成员的全部客户 ----------

    def sync_all_customers_for_user(self, userid: str) -> List[Dict]:
        """同步某成员的全部外部联系人（详情）

        返回标准化后的客户列表:
        [{
            'external_userid': 'xxx',
            'name': '客户名',
            'avatar': 'https://xxx',
            'gender': '男/女/未知',
            'position': '职位',
            'corp_name': '公司名',
            'remark': '备注',
            'tags': ['标签1', '标签2'],
            'first_contact_time': datetime,
            'creator_userid': userid,
        }, ...]
        """
        try:
            raw_contacts = self.batch_get_contact_detail([], userid=userid)
        except RuntimeError as e:
            # 若该成员未配置客户联系功能，返回空
            return []

        normalized = []
        for item in raw_contacts:
            ext = item.get('external_contact', {})
            follow = item.get('follow_info', {})

            # 从 follow_user 中找到当前 userid 的备注信息
            follow_user_list = item.get('follow_user', [])
            my_follow = {}
            for fu in follow_user_list:
                if fu.get('userid') == userid:
                    my_follow = fu
                    break

            # 若没找到，用 batch 接口返回的 follow_info
            if not my_follow and follow:
                my_follow = follow

            gender_map = {0: '未知', 1: '男', 2: '女'}
            tags = my_follow.get('tags', []) or []
            tag_names = [t.get('tag_name', '') for t in tags if t.get('tag_name')]

            first_contact_ts = my_follow.get('createtime', 0)

            normalized.append({
                'external_userid': ext.get('external_userid', ''),
                'name': ext.get('name', ''),
                'avatar': ext.get('avatar', ''),
                'gender': gender_map.get(ext.get('gender', 0), '未知'),
                'position': ext.get('position', ''),
                'corp_name': ext.get('corp_name', ''),
                'remark': my_follow.get('remark', ''),
                'description': my_follow.get('description', ''),
                'tags': json.dumps(tag_names, ensure_ascii=False),
                'first_contact_time': time.strftime(
                    '%Y-%m-%d %H:%M:%S', time.localtime(first_contact_ts)
                ) if first_contact_ts else None,
                'creator_userid': userid,
            })

        return normalized


# ============================================================
# 工具函数
# ============================================================

def create_wecom_service(corp_id: str, contact_secret: str) -> WecomScrmService:
    """创建 WecomScrmService 实例"""
    if not corp_id or not contact_secret:
        raise ValueError('corp_id 和 contact_secret 不能为空')
    return WecomScrmService(corp_id, contact_secret)


def test_connection(corp_id: str, contact_secret: str) -> Tuple[bool, str]:
    """测试企业微信连接

    返回 (是否成功, 消息)
    """
    try:
        svc = create_wecom_service(corp_id, contact_secret)
        token = svc.get_access_token()
        if token:
            return True, f'连接成功，access_token={token[:20]}...'
        return False, '获取 access_token 失败'
    except Exception as e:
        return False, str(e)
