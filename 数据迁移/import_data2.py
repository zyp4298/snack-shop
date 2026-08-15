"""
零食商城 - 完整数据导入脚本（第2部分：用户/购物车/地址/订单）
============================================================
运行前：先运行过第1部分（import_data.py）导入了分类/商品/轮播图
运行：python import_data2.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '零食商城.settings')
django.setup()

import pymysql
from django.contrib.auth.models import User
from product.models import Product, Cart, Address, Order, OrderProduct

# 1. 连接旧数据库
old = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='123456',
    database='huacai-snack',
    charset='utf8mb4'
)
cur = old.cursor()

# 2. 建立 旧商品id → 新商品id 的映射（product 表导入后 id 变了）
print("正在建立商品映射...")
old_products = {}  # {旧product_id: 新Product对象}
for p in Product.objects.all():
    pass  # 这里需要从旧库读对应关系
# 注意：上次导入商品时没有保存 旧id→新id 映射，这里通过名称匹配
cur.execute("SELECT product_id, name FROM product")
name_to_oldid = {name: pid for pid, name in cur.fetchall()}

# 新商品：用名称找对象
new_products_by_name = {p.name: p for p in Product.objects.all()}

def map_product(old_id):
    """旧商品id → 新Product对象（通过名称匹配）"""
    cur2 = old.cursor()
    cur2.execute("SELECT name FROM product WHERE product_id=%s", (old_id,))
    row = cur2.fetchone()
    if row and row[0] in new_products_by_name:
        return new_products_by_name[row[0]]
    print(f"  ⚠️ 找不到商品映射: {old_id}")
    return None

# 3. 导入用户（sys_user → auth_user）
print("导入用户...")
old_users = {}  # {旧user_id: 新User对象}
cur.execute("SELECT user_id, user_name, nick_name FROM sys_user WHERE user_id IN (1, 104)")
for user_id, user_name, nick_name in cur.fetchall():
    if not User.objects.filter(username=user_name).exists():
        u = User.objects.create_user(username=user_name, password='123456')
        if user_id == 1:
            u.is_staff = True
            u.is_superuser = True
            u.save()
        old_users[user_id] = u
        print(f"  ✅ 用户: {user_name} (原id={user_id} → 新id={u.id})")
    else:
        old_users[user_id] = User.objects.get(username=user_name)

# 4. 导入购物车
print("导入购物车...")
cur.execute("SELECT product_id, quantity, user_id FROM cart")
count = 0
for old_pid, quantity, old_uid in cur.fetchall():
    p = map_product(old_pid)
    if p is None or old_uid not in old_users:
        continue
    Cart.objects.create(user=old_users[old_uid], product=p, quantity=quantity)
    count += 1
print(f"  ✅ 购物车 {count} 条")

# 5. 导入地址
print("导入地址...")
cur.execute("SELECT name, phone, detail, is_default, user_id FROM address")
count = 0
for name, phone, detail, is_default, old_uid in cur.fetchall():
    if old_uid not in old_users:
        continue
    Address.objects.create(
        user=old_users[old_uid],
        name=name, phone=phone, detail=detail,
        is_default=bool(is_default),
    )
    count += 1
print(f"  ✅ 地址 {count} 条")

# 6. 导入订单 + 订单商品
print("导入订单...")
cur.execute("SELECT order_id, user_id, name, phone, address, total_amount, product_count, status, remark, create_time FROM `order`")
count = 0
for order_id, old_uid, name, phone, addr, total, pcount, status, remark, ctime in cur.fetchall():
    if old_uid not in old_users:
        continue
    order = Order.objects.create(
        order_id=order_id,
        user=old_users[old_uid],
        name=name, phone=phone, address=addr,
        total_amount=total, product_count=pcount,
        status=status, remark=remark or '',
    )
    # 订单商品（快照，直接复制）
    cur2 = old.cursor()
    cur2.execute("SELECT name, image, price, quantity FROM order_products WHERE order_id=%s", (order_id,))
    for pname, pimage, pprice, pqty in cur2.fetchall():
        OrderProduct.objects.create(
            order=order, name=pname, image=pimage,
            price=pprice, quantity=pqty,
        )
    count += 1
print(f"  ✅ 订单 {count} 个（含明细）")

print("\n🎉 全部导入完成！")
