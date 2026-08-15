from django.db import models
from django.contrib.auth.models import User
# Create your models here.


# ============ 表1: category 零食分类（无外键，最先建） ============
class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="分类名称")
    image = models.CharField(max_length=255, verbose_name="分类图片")
    description = models.CharField(max_length=255, verbose_name="描述")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "category"  # 指定表名
        ordering = ["id"]  # 默认排序

    def __str__(self):
        return self.name

# ============ 表2: product 商品（外键 → category） ============
class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",    # 反向查询：category.products.all()
        verbose_name="所属分类",
    )
    name = models.CharField(max_length=255, verbose_name="商品名称")
    description = models.CharField(max_length=500, verbose_name="描述")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="价格")
    image = models.CharField(max_length=255, verbose_name="图片")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "product"
        ordering = ["id"]   # ORDER BY id ASC

# ============ 表3: banner 轮播图（无外键） ============
class Banner(models.Model):
    image = models.CharField(max_length=255,verbose_name='图片')
    sort = models.IntegerField(max_length=11,verbose_name='排序')

    class Meta:
        db_table = 'banner'
        ordering = ['sort']

# ============ 表4: cart 购物车（外键 → user + product） ============
class Cart(models.Model):
    # 外键 1:用户
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="carts", verbose_name="用户")
    # 外键 2:商品
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="carts", verbose_name="商品")
    quantity = models.IntegerField(verbose_name="数量")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "cart"

# ============ 表5: order 订单（外键 → user，保留字符串订单号） ============
class Order(models.Model):
    order_id = models.CharField(max_length=32, primary_key=True, verbose_name="订单号")  # 如 OR20251016235855104
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders", verbose_name="用户")
    name = models.CharField(max_length=255, verbose_name="收货人")
    phone = models.CharField(max_length=255, verbose_name="手机号码")
    address = models.CharField(max_length=255, verbose_name="收货地址")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="合计价格")
    product_count = models.IntegerField(verbose_name="商品件数")
    status = models.CharField(max_length=200, default="待收货", verbose_name="订单状态")
    remark = models.TextField(blank=True, null=True, verbose_name="备注")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="下单时间")

    class Meta:
        db_table = "order"
        ordering = ["-create_time"]   # 最新订单在前

# ============ 表6: order_products 订单商品明细（外键 → order） ============
class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="products", verbose_name="所属订单")
    name = models.CharField(max_length=255, verbose_name="商品名称")
    image = models.CharField(max_length=255, null=True, blank=True, verbose_name="图片")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="价格")
    quantity = models.IntegerField(verbose_name="数量")

    class Meta:
        db_table = "order_products"

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses", verbose_name="用户")
    name = models.CharField(max_length=100,null=False,verbose_name='收货人')
    phone = models.CharField(max_length=200,null=False,verbose_name='手机号码')
    detail = models.TextField(null=False,verbose_name='详细地址')
    is_default = models.BooleanField(null=False,default=1,verbose_name='是否默认地址')
    create_time = models.DateTimeField(null=False,auto_now_add=True,verbose_name='创建时间')

    class Meta:
        db_table = 'address'
        verbose_name = '收货地址'