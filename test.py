import os, django, time
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '零食商城.settings')
django.setup()

from product.views import AiSearchView

v = AiSearchView()
msgs = [{'role': 'user', 'content': '用三句话介绍一下零食'}]

t0 = time.time()
first = None
for piece in v._ask_stream(msgs):
    if first is None:
        first = time.time() - t0
    print(piece, end='', flush=True)

print()
print(f'首字 {first:.2f}s，总 {time.time()-t0:.2f}s')
