"""
零食商城 - 数据导入脚本
========================
作用：把旧库 huacai-snack 的分类/商品/轮播图 导入到当前 Django 数据库
运行：python import_data.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '零食商城.settings')
django.setup()

import pymysql
from product.models import Category, Product, Banner

# 1. 连接旧数据库（只读 huacai-snack）
old = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='123456',   # 你的 MySQL 密码
    database='huacai-snack',
    charset='utf8mb4'
)
cur = old.cursor()

# 2. 清空现有业务表（重新导入用）
Category.objects.all().delete()
Product.objects.all().delete()
Banner.objects.all().delete()

# 3. 导入分类：记录 旧category_id → 新id 的映射
cat_map = {}  # {旧id: 新id}
cur.execute("SELECT category_id, name, image, description FROM category")
for old_id, name, image, desc in cur.fetchall():
    c = Category.objects.create(name=name, image=image, description=desc)
    cat_map[old_id] = c.id
print(f"✅ 导入分类 {len(cat_map)} 条")

# 4. 导入商品：旧category_id 通过映射换成新id
cur.execute("SELECT product_id, category_id, name, description, price, image FROM product")
count = 0
for pid, cid, name, desc, price, image in cur.fetchall():
    Product.objects.create(
        category_id=cat_map[cid],   # 换成新库的category id
        name=name,
        description=desc,
        price=price,
        image=image,
    )
    count += 1
print(f"✅ 导入商品 {count} 条")

# 5. 导入轮播图
cur.execute("SELECT image, sort FROM banner")
count = 0
for image, sort in cur.fetchall():
    Banner.objects.create(image=image, sort=sort)
    count += 1
print(f"✅ 导入轮播图 {count} 条")

print("\n🎉 全部导入完成！")
