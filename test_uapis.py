
import requests

UAPIS_API_KEY = "uapi--5ndmrhw66hOT4V0WfAF96QPEZh_ruE2BtgHPLlF"
UAPIS_API_URL = "https://uapis.cn/api/v1/misc/tracking/query"

# 测试单号
test_tracking_number = "78992610154327"
test_phone_last4 = None

params = {
    'tracking_number': test_tracking_number
}
if test_phone_last4:
    params['phone'] = test_phone_last4

headers = {
    'Authorization': f'Bearer {UAPIS_API_KEY}',
    'Accept': 'application/json'
}

print(f"Testing uapis.cn API...")
print(f"URL: {UAPIS_API_URL}")
print(f"Params: {params}")

try:
    response = requests.get(UAPIS_API_URL, params=params, headers=headers, timeout=10)
    print(f"Status code: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    print(f"Response text: {response.text}")
    print(f"Response JSON: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
