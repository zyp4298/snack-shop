from rest_framework import serializers
from product.models import Category,Product,Banner,Cart,Order,Address,OrderProduct

class CategorySerializer(serializers.ModelSerializer):
    categoryId = serializers.CharField(source='id',read_only=True)
    class Meta:
        model = Category    # 翻译哪个模型
        fields:str = ['categoryId', 'name', 'image', 'description', 'create_time']  # 翻译所有的字段,可以是字符串,列表或元组

class ProductSerializer(serializers.ModelSerializer):
    '''
    因为前端带有Id,模型没有,所以额外增加一个叫做 categoryId 的字段，并且这个字段的值是对应分类的 ID
    source='category.id'：数据从哪来？
    read_only=True：只读
    '''
    productId = serializers.CharField(source='id',read_only=True)
    categoryId = serializers.CharField(source='category.id',read_only=True)
    categoryName = serializers.CharField(source='category.name',read_only=True)     # 加分
    productImage = serializers.CharField(source='image', read_only=True)  # 管理后台
    class Meta:
        model = Product
        fields:list = ['productId','categoryId','categoryName','name','description','price','image','create_time','productImage']

class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = '__all__'

class CartSerializer(serializers.ModelSerializer):
    productId = serializers.CharField(source='product.id',read_only=True)
    productName = serializers.CharField(source='product.name',read_only=True)
    name = serializers.CharField(source='product.name', read_only=True)  # ← 加：别名
    productImage = serializers.CharField(source='product.image',read_only=True)     # 管理后台
    image = serializers.CharField(source='product.image', read_only=True)  # 小程序（加这行）
    productPrice = serializers.DecimalField(source='product.price',max_digits=10,decimal_places=2,read_only=True)
    price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)  # ← 加：别名
    description = serializers.CharField(source='product.description', read_only=True)  # ← 加：别名
    userName = serializers.CharField(source='user.username',read_only=True)
    class Meta:
        model = Cart
        fields = ['id', 'productId', 'productName', 'name', 'productImage', 'image',
                  'productPrice', 'price', 'description', 'quantity', 'userName']

class AddressSerializer(serializers.ModelSerializer):
    userName = serializers.CharField(source='user.username',read_only=True)
    isDefault = serializers.BooleanField(source='is_default',read_only=True)
    class Meta:
        model = Address
        fields = ['id', 'userName', 'name', 'phone', 'detail', 'isDefault', 'create_time']

'''
力度 1：只要 ID（最省事）
class Meta:
    fields = '__all__'
输出：{"product_id": 5}  ← 只有 ID，前端还要自己再查一次

力度 2：要几个指定字段（常用）
productName = serializers.CharField(source='product.name', read_only=True)
productPrice = serializers.DecimalField(source='product.price', ...)
输出：{"productName": "进口饼干", "productPrice": "22.90"}

力度 3：整个关联对象全要（嵌套）
class ProductBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'image']

class CartSerializer(serializers.ModelSerializer):
    product = ProductBriefSerializer(read_only=True)   # 整个商品对象嵌进来
    class Meta:
        model = Cart
        fields = ['id', 'product', 'quantity']
输出：{"product": {"id": 5, "name": "进口饼干", "price": "22.90", "image": "..."}, "quantity": 3}
力度 3 是"全提取"的正确姿势——把整个商品对象嵌进购物车 JSON。这个叫嵌套序列化（Nested Serializer），是很常用的技巧。
'''


class OrderProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderProduct
        fields = ['name', 'image', 'price', 'quantity']

# Order和 OrderProduct是一对多
class OrderSerializer(serializers.ModelSerializer):
    products = OrderProductSerializer(many=True,read_only=True)
    orderId = serializers.CharField(source='order_id',read_only=True)
    totalAmount = serializers.DecimalField(source='total_amount',max_digits=10,decimal_places=2,read_only=True)
    productCount = serializers.IntegerField(source='product_count', read_only=True)
    userName = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Order
        fields = ['orderId', 'userName', 'name', 'phone', 'address', 'totalAmount', 'productCount', 'status', 'remark',
                  'create_time', 'products']

