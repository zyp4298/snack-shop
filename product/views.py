from pickle import FALSE
from xmlrpc.client import Fault
from rest_framework.decorators import action
from django.shortcuts import render, HttpResponse
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from product.models import Category, Product, Banner, Cart, Order, Address, OrderProduct
from product.serializers import (CategorySerializer, ProductSerializer, CartSerializer,
                                 BannerSerializer, OrderSerializer, AddressSerializer, OrderProductSerializer)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .pagination import CustomPagination
from django.core.cache import cache # Django 内置缓存工具（背后就是 Redis）
import time
import uuid

'''
将DRF接入Django项目,总结起来就是以下几步:
1. pip install djangorestframework  # 装包
2. 在 settings.py 的 INSTALLED_APPS 里添加 'rest_framework'  # 注册
3. 在 app 目录下新建 serializers.py,定义 Serializer 继承 serializers.ModelSerializer  # 翻译官
4. 在 app 目录下新建 views_api.py,定义 ViewSet 继承 viewsets.ModelViewSet  # 视图集
5. 在 urls.py 里用 DefaultRouter().register() 把 ViewSet 注册进去  # 路由
'''


# Serializer:对象 <-> JSON 翻译官
# ViewSet:一个类打包 增/删/改/查 5 个接口
# Router:URL 自动分发,一个 register 自动生成 5 个 URL

# ModelViewSet 默认生成的 5 个接口:
# GET    /api/xxx/         查所有
# GET    /api/xxx/1/       查单个
# POST   /api/xxx/         新增
# PUT    /api/xxx/1/       修改
# DELETE /api/xxx/1/       删除

# Create your views here.

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    '''给 CategoryViewSet 加分页 + 对齐 list'''
    pagination_class = CustomPagination  # 列表自动变成 {code, rows, total}


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = CustomPagination

    def list(self, request, *args, **kwargs):
        '''商品列表带缓存：先查 Redis → 没有就查 MySQL → 写回 Redis'''
        page = request.query_params.get('page','1')      # 当前第几页（第1页/第2页缓存分开）
        cache_key = f'product_list_{page}'              # 便签名：product_list_1 / product_list_2
        data = cache.get(cache_key)     # ① 先看便签板：有没有？
        if data is not None:              # ② 有！直接返回（秒回 ⚡）
            return Response(data)
        response = super().list(request,*args,**kwargs) # ③ 没有 → 查 MySQL（几十毫秒）
        cache.set(cache_key,response.data,300)  # ④ 写回便签板，300秒(5分钟)后自动过期
        return response


class BannerViewSet(viewsets.ModelViewSet):
    queryset = Banner.objects.all()
    serializer_class = BannerSerializer

'''要看数据 → 用 Serializer      只是做动作 → 不用'''
class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.all()  # 会返回所有的数据,张三也能看到别人
    serializer_class = CartSerializer
    '''permission_classes = [IsAuthenticated]   必须登录（有 token）才能访问，否则 401'''
    permission_classes = [IsAuthenticated]  #必须登录才能访问
    pagination_class = CustomPagination

    '''get_queryset(self)   	重写数据来源方法，用 self.request.user 过滤'''

    def get_queryset(self):
        # 只返回当前用户(request.user)的购物车
        return Cart.objects.filter(user=self.request.user)
    @action(detail=False, methods=['get'])  # 如果设为 detail=True，URL 就会变成 /carts/1/selectMyCartList/
    def selectMyCartList(self, request):
        carts = Cart.objects.filter(user=request.user)
        serializer = CartSerializer(carts, many=True)  # many=True,代表是一堆数据而不是一个,需要一一转化
        return Response({'code': 200, 'data': serializer.data})
    @action(detail=False,methods=['put'])       # 加购    前端调用 PUT /snack/cart/addProductToCart/101/   ← productId=101 加进购物车
    def addProductToCart(self,request,product_id):      # product_id: URL 里的 <int:product_id> 自动传给方法
        # 1. 找到商品
        product = Product.objects.get(id=product_id)
        # 2. 查购物车有没有这条（当前用户的 + 这个商品的）
        cart_item = Cart.objects.filter(user=request.user,product=product).first()  # 查第一条（有返回对象，没有返回 None）
        if cart_item:
            # 3a. 有了 → 数量 +1
            cart_item.quantity += 1
            cart_item.save()
        else:
            # 3b. 没有 → 新建一条
            Cart.objects.create(user=request.user,product=product,quantity=1)
        return Response({'code': 200,'msg':'加入购物车成功'})
    @action(detail=False,methods=['put'])
    def increaseQuantity(self,request,cart_id):     # 购物车数量加一
        # 只允许操作自己的购物车
        cart_item = Cart.objects.filter(id=cart_id,user=request.user).first()
        if not cart_item:
            return Response({'code':200,'msg':'购物车记录不存在'})
        cart_item.quantity += 1
        cart_item.save()
        return Response({'code':200,'msg':'数量+1'})
    @action(detail=False,methods=['put'])
    def reduceQuantity(self,request,cart_id):
        cart_item = Cart.objects.filter(id=cart_id,user=request.user).first()
        if not cart_item:
            return Response({'code':200,'msg':'购物车记录不存在'})
        cart_item.quantity -= 1
        if cart_item.quantity <= 0:
            cart_item.delete()
        else:
            cart_item.save()
        return Response({'code':200,'msg':'数量-1'})

class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)  # ← 新增：注入登录用户

    @action(detail=False, methods=['get'])
    def selectMyAddressList(self, request):
        addresses = Address.objects.filter(user=request.user)
        serializer = AddressSerializer(addresses, many=True)
        return Response({'code': 200, 'data': serializer.data})


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    lookup_field = 'order_id'        # Order 主键是 order_id，不是默认的 id

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
    @action(detail=False, methods=['get'])
    def selectMyOrderList(self, request):
        orders = Order.objects.filter(user=request.user)
        serializer = OrderSerializer(orders, many=True)
        return Response({'code': 200, 'data': serializer.data})

    def perform_create(self, serializer):
        # 生成订单号：OR + 时间戳（主键不能为空，后端生成）
        order_id = 'OR' + time.strftime('%Y%m%d%H%M%S') + str(uuid.uuid4().int % 10000).zfill(4)
        # 绑定当前登录用户 + 订单号
        serializer.save(order_id=order_id, user=self.request.user)

    # 虎鲸 2026-08-29：让 PUT 接受部分字段（前端只发改的 status）
    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


# class OrderProductViewSet(viewsets.ModelViewSet):
#     queryset = OrderProduct.objects.all()
#     serializer_class = OrderProductSerializer

# 猜你喜欢（推荐商品）
class RecommendationView(APIView):
    def get(self,request):
        # 简化版：随机返回 10 个商品
        products = Product.objects.order_by('?')[:10]   # order_by('?') = 随机排序,[:10]是列表的 0到 10号元素
        serializer = ProductSerializer(products,many=True)
        return Response({
            'code':200,
            'msg':'查询成功',
            'rows':serializer.data,     # ← 前端要 rows
            'total':len(serializer.data)
        })

# 注册接口
class RegisterView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        # 校验：用户名不能为空
        if not username or not password:
            return Response({'error': '用户名和密码不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 校验：用户名不能重复
        if User.objects.filter(username=username).exists():
            return Response({'error': '用户名已存在'}, status=status.HTTP_400_BAD_REQUEST)

        #创建用户
        user = User.objects.create_user(username=username, password=password)

        # 自动发 token（注册即登录）
        refresh = RefreshToken.for_user(user)
        return Response({
            'code':200,
            'msg': '注册成功',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)


# 首页统计接口（合同清单 B 组）
class HomePageView(APIView):
    def get(self, request):
        action = request.path.split('/')[-1]  # 取最后一段：selectDataInfo 等

        if action == 'selectDataInfo':
            # 统计三个总数
            return Response({
                'code': 200,
                'data': {
                    'productCount': Product.objects.count(),
                    'orderCount': Order.objects.count(),
                    'categoryCount': Category.objects.count(),
                }
            })
        # 每个分类下有多少商品（饼图用）
        if action == 'selectCategoryChart':
            data = []
            for c in Category.objects.annotate(num=Count('products')):
                data.append({'name': c.name, 'value': c.num})
            return Response({'code': 200, 'data': data})
        # 订单状态统计（柱状图用）
        if action == 'selectOrderStatusCount':
            data = []
            for s in Order.objects.values('status').annotate(num=Count('order_id')):
                data.append({'name': s['status'], 'value': s['num']})
            return Response({'code': 200, 'data': data})

        return Response({'code': 500, 'msg': '未知操作'})


# 分类下拉（前端 selectAllCategoryNameList 用）
class CategoryNameListView(APIView):
    def get(self, request):
        data = [{'categoryId': c.id, 'categoryName': c.name} for c in Category.objects.all()]
        return Response({'code': 200, 'data': data})


# ============================================================
# 以下为 2026-08-09 前端联调适配代码（已注释，暂停使用）
# 以后要继续联调时，取消注释即可
# ============================================================

# 验证码接口（返回 captchaEnabled=false 表示不需要验证码）
class CaptchaView(APIView):
    def get(self, request):
        return Response({
            'captchaEnabled': False,  # 前端看到 false → 不显示验证码
            'uuid': '',  # 留空
            'img': '',  # 留空
        })


# 获取登录用户信息
class UserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'code': 200,
            'user': {
                'userId': user.id,
                'userName': user.username,
                'nickName': user.username,
                'avatar': '',
            },
            'roles': ['admin'] if user.is_superuser else ['common'],
            'permissions': [],
        })

# ===== 虎鲸 2026-08-29：修改密码功能（Django 自带密码三件套）=====
class UpdatePwdView(APIView):
    permission_classes = [IsAuthenticated]
    def put(self,request):
        user = request.user
        old_password = request.data.get('oldPassword')
        new_password = request.data.get('newPassword')

        # 1. 验证旧密码
        if not user.check_password(old_password):
            return Response({'msg':'旧密码不正确'},status=status.HTTP_400_BAD_REQUEST)

        # 2. 设置新密码（自动加密存储）
        user.set_password(new_password)
        user.save()

        return Response({'msg': '密码修改成功'})

# 简单返回
class LogoutView(APIView):
    def post(self, request):
        return Response({'code': 200, 'msg': '退出成功'})


class RoutersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 简单版：返回一个固定的菜单树（实际项目应该按角色动态返回）
        return Response({
            'code': 200,
            'msg': '操作成功',
            'data': [
                {
                    'name': 'Snack',
                    'path': '/snack',
                    'hidden': False,
                    'redirect': 'noRedirect',
                    'component': 'Layout',
                    'meta': {'title': '零食商城', 'icon': 'shopping'},
                    'children': [
                        {'name': 'Category', 'path': 'category', 'component': 'snack/category/index',
                         'meta': {'title': '零食分类', 'icon': 'list'}},
                        {'name': 'Product', 'path': 'product', 'component': 'snack/product/index',
                         'meta': {'title': '商品管理', 'icon': 'shopping-bag'}},
                        {'name': 'Cart', 'path': 'cart', 'component': 'snack/cart/index',
                         'meta': {'title': '购物车', 'icon': 'cart'}},
                        {'name': 'Order', 'path': 'order', 'component': 'snack/order/index',
                         'meta': {'title': '订单管理', 'icon': 'order'}},
                        {'name': 'Address', 'path': 'address', 'component': 'snack/address/index',
                         'meta': {'title': '收货地址', 'icon': 'address'}},
                        {'name': 'Banner', 'path': 'banner', 'component': 'snack/banner/index',
                         'meta': {'title': '轮播图', 'icon': 'image'}},
                    ]
                }
            ]
        })


# 自定义登录（返回前端要的 token 字段）
class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({'code': 500, 'msg': '用户名或密码错误'})

        refresh = RefreshToken.for_user(user)
        return Response({
            'code': 200,
            'msg': '登录成功',
            'token': str(refresh.access_token),  # ← 前端要的 token！
            'access': str(refresh.access_token),  # 兼容（以后可能用）
            'refresh': str(refresh),
        })

# ============ 支付宝支付（沙箱）============
from alipay import AliPay
from django.conf import settings

def get_alipay():
    '''创建支付宝客户端（沙箱模式）'''
    return AliPay(
        appid=settings.ALIPAY_APPID,                    # 沙箱 APPID
        app_notify_url=None,
        app_private_key_string=settings.ALIPAY_APP_PRIVATE_KEY,  # 应用私钥（签名用）
        alipay_public_key_string=settings.ALIPAY_PUBLIC_KEY,        # 支付宝公钥（验签用）
        sign_type='RSA2',                                            # 签名算法
        debug=True,                                                  # True=沙箱 False=正式
    )

class PayView(APIView):
    '''① 生成支付链接：POST /snack/pay  body: {"order_id": "xxx"}'''
    permission_classes = [IsAuthenticated]

    def post(self,request):
        # 1. 查订单（必须是自己的）
        order_id = request.data.get('order_id')
        order = Order.objects.filter(order_id=order_id,user=request.user).first()
        if not order:
            return Response({'code':500,'msg':'订单不存在'})

        # 2. SDK 生成支付参数（相当于把订单信息"盖章"）
        alipay = get_alipay()
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,                                      # 商户订单号（你的 order_id）
            total_amount=str(order.total_amount),                        # 金额（字符串！）
            subject='零食商城订单',                                        # 商品标题
            return_url='http://127.0.0.1:8000/pay/result',               # 付款后跳回页面（本地先用）
            notify_url='http://127.0.0.1:8000/snack/pay/callback',      # 异步回调（下面这个接口）
        )
        # 3. 拼完整链接：沙箱网关 + 参数（用 SDK 自带的网关，debug=True 自动选沙箱地址）
        pay_url = alipay._gateway + '?' + order_string
        return Response({'code':200,'pay_url':pay_url})

class  PayCallbackView(APIView):
    '''② 支付回调：POST /snack/pay/callback（支付宝自动来调）'''
    def post(self,request):
        alipay = get_alipay()
        # 1. 支付宝发来的数据 + 签名
        data = request.data.dict()
        signature = data.pop('sign','')
        # 2. 验证签名（防伪造：确认真是支付宝发的）
        if alipay.verify(data,signature) and data.get('trade_status') == 'TRADE_SUCCESS':
            # 3. 签名通过 + 支付成功 → 更新订单状态
            order_id = data.get('out_trade_no')
            Order.objects.filter(order_id=order_id).update(status='已支付')
            return Response('success')      # ⚠️ 必须返回 success，否则支付宝反复重发
        return Response('fail')