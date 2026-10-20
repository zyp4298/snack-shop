import requests

# ① 先登录拿 token（密码换成你的）
r = requests.post('http://127.0.0.1:8000/login',
                  json={'username': 'admin', 'password': '123456'})
token = r.json()['access']
print('token 拿到 ✔')

# ② 调 AI 接口
r2 = requests.post('http://127.0.0.1:8000/snack/product/aiDescription',
                   headers={'Authorization': f'Bearer {token}'},
                   json={'name': '乐事薯片', 'category': '膨化食品', 'price': '9.9'},
                   timeout=60)
print(r2.status_code)
print(r2.json())
