from pickle import FALSE
from xmlrpc.client import Fault
from rest_framework.decorators import action
from django.shortcuts import render, HttpResponse
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from scripts.regsetup import description

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
from rest_framework.permissions import IsAuthenticated, IsAdminUser
import requests
from django.conf import settings
import json
from django.db.models import Q

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

    def get_permissions(self):
        # 读（列表/详情）→ 公开，小程序要浏览
        if self.action in ('list','retrieve'):
            return []
        # 写（增/删/改）→ 只有管理员
        return [IsAdminUser()]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = CustomPagination

    def list(self, request, *args, **kwargs):
        '''商品列表带缓存：先查 Redis → 没有就查 MySQL → 写回 Redis'''
        # 2026-10-14 修：参数名必须是 pageNum（和 CustomPagination 里的 page_query_param 一致）
        # 原来写 'page' 取不到值 → 永远返回 '1' → 所有页码共用同一个缓存 key → 翻页永远是第一页
        page = request.query_params.get('pageNum','1')      # 当前第几页（第1页/第2页缓存分开）
        page_size = request.query_params.get('pageSize', '10')
        cache_key = f'product_list_{page}_{page_size}'  # 顺便把 pageSize 也纳入 key   # 便签名：product_list_1 / product_list_2
        data = cache.get(cache_key)     # ① 先看便签板：有没有？
        if data is not None:              # ② 有！直接返回（秒回 ⚡）
            return Response(data)
        response = super().list(request,*args,**kwargs) # ③ 没有 → 查 MySQL（几十毫秒）
        cache.set(cache_key,response.data,300)  # ④ 写回便签板，300秒(5分钟)后自动过期
        return response

    def get_permissions(self):
        if self.action in ('list','retrieve'):
            return []
        return [IsAdminUser()]


class BannerViewSet(viewsets.ModelViewSet):
    queryset = Banner.objects.all()
    serializer_class = BannerSerializer

    def get_permissions(self):
        if self.action in ('list','retrieve'):
            return []
        return [IsAdminUser()]

'''要看数据 → 用 Serializer      只是做动作 → 不用'''
class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.all()  # 会返回所有的数据,张三也能看到别人
    serializer_class = CartSerializer
    '''permission_classes = [IsAuthenticated]   必须登录（有 token）才能访问，否则 401'''
    permission_classes = [IsAuthenticated]  #必须登录才能访问
    pagination_class = CustomPagination

    '''get_queryset(self)   	重写数据来源方法，用 self.request.user 过滤'''

    def get_queryset(self):
        if self.request.user.is_staff:
            return Cart.objects.all()
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

    # 虎鲸 2026-09-03：批量删除购物车（兼容前端 delCart([5,7]) → /snack/cart/5,7）
    # 原因：下单成功后，前端 confirm.vue 第 312 行 delCart(cartIds) 传数组 → URL = /snack/cart/5,7
    #      DRF 默认 detail 路由会进 destroy，但 pk='5,7' 是字符串，无法 cart_item = Cart.objects.get(pk=pk) → 报错 500
    #      解决方案：判断 pk 含逗号 → 拆成 ID 列表 → filter + delete
    def destroy(self, request, *args, **kwargs):
        pk = kwargs.get('pk', '')
        if ',' in str(pk):
            # 逗号分隔的多个 ID：批量删除
            ids = [int(i) for i in str(pk).split(',') if i.isdigit()]
            # 只删当前用户的（安全：防止删别人数据）
            deleted_count, _ = Cart.objects.filter(id__in=ids, user=request.user).delete()
            return Response({'code': 200, 'msg': f'已删除 {deleted_count} 条'})
        # 单个 ID：走默认逻辑（ModelViewSet.destroy → get_object → perform_destroy）
        return super().destroy(request, *args, **kwargs)


class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Address.objects.all()
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
        if self.request.user.is_staff:
            return Order.objects.all()
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

class ProductSearchView(APIView):

    # 我知道这是APIView，属于手动views，因此没有自动设置方法，我便要手动添加get方法，那么数据便是来自数据库的Product的数据，查询条件是请求的数据。
    # 翻译器就用productserializer翻译，翻译的数据就是刚才请求的数据，并且是多量数据。返回值，首先因为是自定义的，因此得手动返回需要的内容，code是
    # 业务状态码，msg是提示信息，rows其实就是data？或者说data.list？这里不太理解，total就是返回多少条目，说实话我觉得可以去除掉，似乎没什么作用

    def get(self,request):
        keyword = request.query_params.get('keyword','')            #不理解的地方，我知道要请求的是搜索的数据，但为什么这么写？
        products = Product.objects.filter(name__icontains=keyword)      #数据来源，但name__icontains是什么我忘了，这些__都是什么我都忘了，记得给我说说
        serializer = ProductSerializer(products,many=True)
        return Response({
            'code':200,
            'msg':'查询成功',
            'rows':serializer.data,
            'total':len(serializer.data),           #这行我认为没必要，毕竟翻译的数据长度还是那么长，因此返回的条目还是总共的
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

# ===== 验证码相关（2026-09-01 船长要求：不启用验证码，整段注释）=====
# 验证码接口（返回 captchaEnabled=false 表示不需要验证码）
# class CaptchaView(APIView):
#     def get(self, request):
#         return Response({
#             'captchaEnabled': False,  # 前端看到 false → 不显示验证码
#             'uuid': '',  # 留空
#             'img': '',  # 留空
#         })


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
            'roles': ['admin'] if user.is_staff else ['common'],
            # 2026-10-14 修：permissions 不能为空！
            # 前端按钮全都挂着 v-hasPermi="['snack:product:edit']" 这类指令，
            # 空数组 ⇒ 按钮被整个移除（操作列一片空白）。'*:*:*' 是若依给超级管理员的通配符。
            'permissions': ['*:*:*'] if user.is_staff else [],
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
        if not request.user.is_staff:
            return Response({'code': 200, 'msg': '操作成功', 'data': []})
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
            return_url='http://116.62.205.54/pay/result',               # 付款后跳回页面（本地先用）
            notify_url='http://116.62.205.54/snack/pay/callback',      # 异步回调（下面这个接口）
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

from django.http import HttpResponse

class PayResultView(APIView):
    '''支付宝支付成功后跳回的页面（用户浏览器看到的"支付成功"页）'''
    permission_classes = [] # 不需要登录（浏览器从支付宝跳转过来没 token）
    authentication_classes = []  # 同上

    def get(self, request):
        # 简单 HTML页面，显示支付成功
        #真实生产里通常跳到"我的订单"页，这里做个简单的提示页
        return HttpResponse('''
            <html>
            <head><meta charset="utf-8"><title>支付成功</title></head>
            <body style="text-align:center;padding-top:100px;font-family:sans-serif">
                <h1 style="color:#52c41a">✅ 支付成功！</h1>
                <p>订单支付已完成，可以关闭此页面了。</p>
                <p style="color:#999;font-size:14px">真实订单状态已通过异步通知更新</p>
            </body>
            </html>
        ''', content_type='text/html; charset=utf-8')

# ===== 2026-10-11：适配若依管理端模板的"系统类"接口 =====
# 背景：管理端前端是若依(Vue3)模板，它会调两个系统接口，而 Django 从来没有这两条路由 →
#       一直 404 → 页面顶部弹"系统接口404异常"。
# 下面两个类是它们的适配层：前端一行不改，只补后端。

# 字典数据表：键 = 字典类型，值 = 若依格式的选项列表
# ⚠️ 字段名是固定的（前端 utils/dict.js 里写死这么取）：
#    dictLabel=显示文字 / dictValue=实际值 / listClass=标签颜色 / cssClass=自定义样式

DICT_DATA = {
    'order_status':[
        {'dictLabel':'待收货','dictValue':'待收货','listClass':'primary','cssClass':''},
        {'dictLabel':'已支付','dictValue':'已支付','listClass':'success','cssClass':''},
        {'dictLabel':'已完成','dictValue':'已完成','listClass':'primary','cssClass':''},
        {'dictLabel':'已取消','dictValue':'已取消','listClass':'info','cssClass':''},
    ]
}

class SysDictDataView(APIView):
    '''
        若依模板的字典接口：GET /system/dict/data/type/<字典类型>
        前端的 useDict('order_status') 会调它，把每项转成 {label, value} 给下拉框和表格标签用。
        ⚠️ dictValue 必须和数据库里存的值一致 —— 本项目的 Order.status 存的是「中文」，
           所以这里 value 也用中文；若改成数字码，表格里的订单状态列会显示不出来。
    '''
    permission_classes = [IsAuthenticated]

    def get(self,request,dict_type:str):
        return Response({
            'code':200,
            'msg':'操作成功',
            'data':DICT_DATA.get(dict_type,[]),     # 没配的类型返回空列表（不是 404）  查不到 → 返回 []  → 接口正常返回空数据 ✅
        })

class SysUserInfoView(APIView):
    '''若依模板的"当前用户信息"接口：GET /system/user/
        管理端顶部导航栏（Navbar.vue）每次渲染都会调一次 —— 但它的返回值其实没被使用
        （模板里遗留的调用），补上这个接口是为了消掉 404 红条。
    '''
    permission_classes = [IsAuthenticated]

    def get(self,request):
        user = request.user
        return Response({
            'code':200,
            'msg':'操作成功',
            'data':{
                'userId':user.id,
                'userName':user.username,
                'nickName':user.username,
                'email': user.email or '',
                'phonenumber': '',
                'sex': '0',
                'avatar': '',
                'status': '0',
            },
            'roles':['admin'] if user.is_staff else [],
            # 2026-10-14 修：permissions 不能为空！
            # 前端按钮全都挂着 v-hasPermi="['snack:product:edit']" 这类指令，
            # 空数组 ⇒ 按钮被整个移除（操作列一片空白）。'*:*:*' 是若依给超级管理员的通配符。
            'permissions':['*:*:*'] if user.is_staff else [],
        })


# ===== 2026-10-13：AI 生成商品描述（第一个 LLM 业务接口）=====
class AiDescriptionView(APIView):
    '''
    AI 生成商品描述：POST /snack/product/aiDescription
        管理端商品表单点「AI 生成」→ 拿到文案填进描述框。
        权限用 IsAdminUser：因为每次调用都消耗 token（花钱），不能开放给所有人。
    '''
    permission_classes = [IsAdminUser]

    def post(self,request):
        # ① 取前端传来的商品信息
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'code':400,'msg':'商品名不能为空'})
        category = request.data.get('category') or '零食'
        price = request.data.get('price') or ''

        # ② 拼 prompt —— 这一步就是图里说的「数据注入」，
        #    是 AI 应用的业务价值所在：把「你的数据」塞进「通用模型」的嘴里
        prompt = (
            f'你是一个零食电商的文案专家，请为下面这个商品写一段吸引人的描述：\n'
            f'- 商品名称：{name}\n'
            f'- 所属分类：{category}\n'
            f'- 价格：{price} 元\n'
            f'要求：1) 100 字以内；2) 突出口感或卖点；3) 不要堆砌感叹号；'
            f'4) 只输出描述本身，不要任何前缀、解释或引号。'
        )

        # ③ 调大模型
        try:
            resp = requests.post(
                'https://api.siliconflow.cn/v1/chat/completions',
                headers = {'Authorization':f'Bearer {settings.SILICONFLOW_API_KEY}'},
                json = {
                    'model':'Qwen/Qwen2.5-7B-Instruct',
                    'messages':[{'role':'user','content':prompt}],
                    'max_tokens':300,                 # 限制输出长度 ⇒ 控成本，也防跑飞
                    'temperature':0.8,              # 稍高 = 更有创意（0 会非常死板）
                },
                timeout = 30,            # 模型可能慢，必须设超时，否则请求会一直挂着
            )
            data = resp.json()

        except Exception as e:
            # ④ 外部服务失败 ≠ 我们的接口崩了，要给它包一层友好返回
            return Response({'code':500,'msg':f'AI 调用失败：{e}'})

        # ⑤ 按 OpenAI 规范取出文案
        content = data['choices'][0]['message']['content'].strip()
        return Response({'code':200,'msg':'操作成功','data':content})

# ===========================================================================
# AI 智能导购接口
class AiSearchView(APIView):
    '''POST /snack/product/aiSearch  {"question": "有什么不辣的零食"}

    2026-10-27：从「手搓」换成官方 tools 版
    - 不用再解析自由文本（tool_calls 是结构化的）
    - 不用再猜参数名（parameters.properties 已经限定）
    '''
    permission_classes = [IsAuthenticated]      # 导购是给用户的，不是管理员

    API = 'https://api.siliconflow.cn/v1/chat/completions'
    MODEL = 'Qwen/Qwen2.5-7B-Instruct'

    # ========== 工具说明书（给模型看的"菜单"）==========
    # 注意：这里声明的参数，必须和下面的 _search 完全一致
    TOOLS = [{
        'type': 'function',
        'function': {
            'name': 'search_product',
            'description': '按关键词/分类/价格查询【具体商品】，返回商品列表。'
                           '用户想看到买什么的时候用它，不要用 list_categories 代替',
            'parameters': {
                'type': 'object',
                'properties': {
                    'keyword':   {'type': 'string', 'description': '商品名或口味词，不确定就别传'},
                    'category':  {'type': 'string', 'description': '分类名，只能填一个'},
                    'max_price': {'type': 'number',
                                  'description': '价格上限。用户说"X元以内/不超过X/便宜点"时填'},
                    'min_price': {'type': 'number',
                                  'description': '价格下限。用户说"X元以上/至少X/超过X"时填'},
                    'order_by':  {'type': 'string',
                                  'enum': ['price_asc', 'price_desc'],
                                  'description': '排序方式。用户问"最便宜/最低价/哪个便宜"填 price_asc；'
                                                 '问"最贵/最高价"填 price_desc。'
                                                 '不要自己比较价格，传这个参数让我来排'},
                },
                'required': [],
            },
        },
    }, {                                    # ← 新增这道
            'type': 'function',
            'function': {
                'name': 'list_categories',
                'description': '列出店里所有商品分类及每类数量。用户问"有哪些分类/卖什么种类"时用'
                               '仅在用户明确问分类时用',
                'parameters': {'type': 'object', 'properties': {}, 'required': []},
            },
        },
    ]

    def post(self,request):
        question = (request.data.get('question') or '').strip()
        if not question:
            return Response({'code':400,'msg':'问题不能为空'})

        # ① 把"我库里有什么分类"告诉它 —— 不告诉，它就瞎猜
        cats = list(Category.objects.values_list('name',flat=True))

        system = (
            '你是零食商城的导购助手。\n'
            f'本店商品的分类只有这些：{cats}\n'
            '你有两个工具：search_product（按关键词/分类/价格查商品）、'
            'list_categories（查有哪些分类、各多少个）。\n'
            '【选工具的判断】\n'
            '- 用户问"有哪些分类/卖什么种类/都有什么类别" → 用 list_categories\n'
            '- 用户问"有什么零食/推荐点吃的/有没有XX/多少钱" → 用 search_product\n'
            '- 用户问得笼统、没给关键词时，search_product 一个参数都不传，直接把商品列表拿出来\n'
            '【硬规则】只要用户提到口味、价格、品类、推荐、有没有某种商品，'
            '你必须先调用工具查库。\n'
            '你【不许】凭记忆或常识回答商品问题 —— 你不知道店里有什么。\n'
            '只有在用户打招呼、或问题与商品完全无关时，才用中文直接回答。\n'
            '【回答长度】\n'
            '前端会把商品渲染成卡片，所以你【不要】逐条复述商品名和价格。\n'
            '回答只要一句话给结论：最便宜或最推荐的是哪个、多少钱。\n'
            '有商品时不超过 40 字；没有商品时（比如问分类）不超过 60 字。\n'
            '不要说"共几款"这类数字，前端卡片会显示总数。\n'
            '只有用户直接问"一共有多少/总共几款"时，才用 total 那个数回答。\n'
        )

        # ①.5 取这个用户的历史（存在 Redis 里，key 带 user.id ⇒ 天然隔离）
        # 会话号：前端传就按传的，没传就落到 default（旧调用不会坏）
        sid = str(request.data.get('session_id') or 'default').strip()[:32] or 'default'
        cache_key = f'ai_history:{request.user.id}:{sid}'
        history = cache.get(cache_key) or []

        msgs = ([{'role': 'system', 'content': system}]
                + history
                + [{'role': 'user', 'content': question}])
        '''
        完全等价于这种更好懂的写法：
        msgs = []
        msgs.append({'role': 'system', 'content': system})
        msgs.extend(history)                                   # ← 注意是 extend,里面的元素一个个倒进来（摊平）
        msgs.append({'role': 'user', 'content': question})
        '''

        # ② 分发表：工具名 → 方法（self. 已经绑定好了，可以直接调）
        handlers = {
            'search_product':self._search,
            'list_categories':self._list_categories,
        }

        products = []       # 最后要交给前端的那份
        total_count = 0      # ← 新增：符合条件的总数，前端显示"共 N 款"
        reply = ''

        # ③ 主循环：问 → 判 → 干 → 记
        for i in range(1,6):            # 最多 5 轮，保险丝
            try:
                msg = self._ask(msgs)
            except RuntimeError as e:
                print(f'[ai] 调用失败：{e}')  # 日志留痕，方便排查
                return Response({'code': 500, 'msg': 'AI 现在有点忙，稍后再试','total': total_count,
                                 'data': {'reply': '我这边暂时连不上，稍等一下再问我一次？',
                                          'products': products}})
            calls = msg.get('tool_calls')

            if not calls:               # 它答完了
                reply = msg.get('content') or ''
                break

            msgs.append(msg)            # 记：它这张单子

            for call in calls:          # 一轮可能点好几道菜
                name = call['function']['name']
                args = json.loads(call['function']['arguments'])
                '''
                json.loads() — 字符串 → Python 对象
                json.load() — 文件对象 → Python 对象
                json.dumps() — Python 对象 → 字符串
                json.dump() — Python 对象 → 写入文件
                '''

                if name not in handlers:  # 模型点了个菜单上没有的
                    result = {'error': f'没有这个工具：{name}'}
                else:
                    result = handlers[name](**args)

                if isinstance(result, dict) and 'products' in result:
                    products = result['products']
                    total_count = result['total']
                    print(f'[ai] {name}({args}) → 总共 {result["total"]} 条，显示 {result["shown"]} 条')
                else:
                    print(f'[ai] {name}({args}) → {len(result)} 项')

                msgs.append({
                    'role': 'tool',
                    'tool_call_id': call['id'],
                    'content': json.dumps(result, ensure_ascii=False),
                })
        # ④.5 存回去：去掉 system，只留最近 6 轮，30 分钟过期
        turns = msgs[1:]
        user_idx = [i for i,m in enumerate(turns) if m['role'] == 'user']
        if len(user_idx) > 6:
            turns = turns[user_idx[-6]:]
        cache.set(cache_key,turns,1800)
        '''
        enumerate(turns)
        # → (0, turns[0]), (1, turns[1]), (2, turns[2]) ...   给每个元素配上序号
        
        for i, m in enumerate(turns)
        # → i 拿序号，m 拿元素
        
        if m['role'] == 'user'
        # → 只要 role 是 user 的
        
        [i for ...]
        # → 把 i 收集成列表
        -------------------------------------
        更笨、但最不容易看错的写法：
        user_idx = []
        for i in range(len(turns)):
            if turns[i]['role'] == 'user':
                user_idx.append(i)
        '''

        # ④ 收尾：模型没给话，自己拼一句
        if not reply:
            if products:
                reply = '推荐：' + '、'.join(p['name'] for p in products)
            else:
                reply = f'没找到符合「{question}」的商品，换个说法试试？'

        return Response({'code': 200, 'msg': '操作成功',
                         'data': {'reply': reply,
                                  'products': products,
                                  'total': total_count}})

    def _search(self,keyword=None,category=None,max_price=None,min_price=None,order_by=None):
        '''工具本体：真的查数据库'''
        qs = Product.objects.select_related('category')

        if keyword:      # 模型传了 keyword 才进这个分支
            qs = qs.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
            '''
            Q(name__icontains=keyword) —— 商品名字里包含这个关键词（icontains = 不区分大小写的 LIKE '%keyword%'）
            Q(description__icontains=keyword) —— 或者描述里包含'''

        if category:
            # 模型可能给 "甜食,饼干" 这种逗号串 —— 拆开，多个分类用「或」
            names = [c.strip() for c in category.replace('，', ',').split(',') if c.strip()]
            if names:
                q = Q()
                for n in names:
                    q |= Q(category__name__icontains=n)   # 多个分类用「或」拼起来,链式 filter() = AND，这里必须用 OR。
                qs = qs.filter(q)
            '''
            为什么要这么写？因为模型填的 category 可能是各种格式：
            模型可能填的             你要的效果
            "饼干"                  查分类名含"饼干"的商品
            "甜食,饼干"             查分类是"甜食"或"饼干"的商品
            "甜食，饼干"             同上，但用了中文逗号
            " 饼干 , 薯片 "          有空格、多余逗号
            '''
            '''
            输入：category = "甜食，饼干, 薯片 "
            ① .replace('，', ',')    → "甜食,饼干, 薯片 "
            ② .split(',')            → ["甜食", "饼干", " 薯片 "]
            ③ c.strip()              → 去空格 → "薯片"
            ④ if c.strip()           → 过滤掉空字符串
            最终：names = ["甜食", "饼干", "薯片"]
            '''
        if max_price:       # 价格过滤
            qs = qs.filter(price__lte=max_price)
        if min_price:
            qs = qs.filter(price__gte=min_price)

        # 排序：只认白名单
        ORDER = {'price_asc':'price','price_desc':'-price'}
        if order_by in ORDER:       # ← 不在白名单，就当成没传，悄悄忽略
            qs = qs.order_by(ORDER[order_by])

        # 原来是 return qs[:5]
        #  返回"小票"而不是 QuerySet
        # 理由：工具结果要 json.dumps 回喂给模型，QuerySet 序列化不了
        # 返回"小票"+ 总量，而不是 QuerySet
        # 理由① QuerySet 没法 json.dumps
        # 理由② 必须告诉模型"总共多少 / 我只给你看了几条"，否则它以为这些就是全部
        items = [{'name': p.name, 'price': str(p.price), 'desc': p.description}
                     for p in qs[:5]]
        return {'total': qs.count(), 'shown': len(items), 'products': items}       # 只返回前 5 条结果。为什么？防止模型一次拿到几百条商品，token 爆炸。
    '''
    完整 SQL 长什么样,假设模型填了 {"keyword":"薯片","max_price":15,"category":"膨化"}：
    
    SELECT product.*, category.name
    FROM product
    LEFT JOIN category ON product.category_id = category.id
    WHERE (product.name LIKE '%薯片%' OR product.description LIKE '%薯片%')
      AND (category.name LIKE '%膨化%')
      AND product.price <= 15
    ORDER BY ...   -- Django 默认按主键
    LIMIT 5;
    '''

    def _list_categories(self):
        '''工具本体②：统计每个分类有多少商品'''
        stat = {}
        for name in Product.objects.values_list('category__name',flat=True):
            if name:             # 没分类的商品跳过
                stat[name] = stat.get(name, 0) + 1
        return stat

    # ========== 电话线：注意返回的是整个 message ==========
    def _ask(self, messages):
        try:
            r = requests.post(
                self.API,
                headers={'Authorization': f'Bearer {settings.SILICONFLOW_API_KEY}'},
                json={'model': self.MODEL,
                      'messages': messages,
                      'max_tokens': 400,
                      'temperature': 0.2,
                      'tools': self.TOOLS},
                timeout=30,
            )
            return r.json()['choices'][0]['message']
        except Exception as e:
            raise RuntimeError(f'AI 调用失败：{e}')
        '''
        整个方法的工作过程:
        
        假设前端发来：
        POST /snack/product/aiSearch
        {"question": "有什么不辣的零食推荐"}
        
        第一次请求:
        msg = self._ask(msgs)    # ← 第一次联网
        
        此时发给模型的 msgs：
            [{'role': 'system', 'content': '你是零食商城的导购助手。\n本店商品的分类只有这些：[\'膨化食品\', \'糖果\', \'饮料\', \'辣味零食\']\n
            【硬规则】只要用户提到口味、价格、品类、推荐……你必须先调用工具 search_product……'},
            {'role': 'user', 'content': '有什么不辣的零食推荐'}]
        还附带了 tools=self.TOOLS（工具菜单）。
        
        🧠 模型的"内心独白"（第一次请求）
        收到任务了。让我看看……
        system 说：我是导购，店里分类有膨化食品、糖果、饮料、辣味零食。硬规则是——只要用户提到口味、推荐，我必须先调 search_product 查库，不许凭记忆回答。
        用户问："有什么不辣的零食推荐"
        分析：
        "不辣" → 这是口味词 ✅
        "零食推荐" → 这是推荐请求 ✅
        触发硬规则 → 我必须调工具
        我能直接回答吗？不能。我不知道店里具体有哪些不辣的商品。system 明确说了"不许凭记忆回答商品问题"。
        那调什么工具？search_product。
        传什么参数？
        keyword：用户说"不辣"，传 "不辣" ← 模型不知道函数里怎么筛，但它知道 keyword 是"商品名或口味词"
        category：不确定，不传
        max_price / min_price：没提价格，不传
        好，填单。
        
        输出的msg:
            {
                'role': 'assistant',
                'content': None,          # ← 没有自然语言内容
                'tool_calls': [{
                    'id': 'call_abc123',
                    'type': 'function',
                    'function': {
                        'name': 'search_product',
                        'arguments': '{"keyword":"不辣"}'    # ← 模型填的单
                    }
                }]
            }
        注意：content 是 None。模型这次没说一句话，只填了工单。
        
        代码做了什么（两次请求之间）:
            call = calls[0]
            args = json.loads(call['function']['arguments'])
            # args = {'keyword': '不辣'}
            
            items = self._search(**args)
            # → Django ORM 查数据库
            # → SELECT * FROM product WHERE name LIKE '%不辣%' OR description LIKE '%不辣%' LIMIT 5
            # → 假设返回：[原味薯片(¥5), 草莓软糖(¥8)]
            
            brief = [{'name': '原味薯片', 'price': '5', 'desc': '...'},
                     {'name': '草莓软糖', 'price': '8', 'desc': '...'}]
        
        然后：
            msgs.append(msg)     # 把模型第一次的回复（含 tool_calls）原样放回
            msgs.append({
                'role': 'tool',
                'tool_call_id': 'call_abc123',
                'content': '[{"name":"原味薯片","price":"5",...},{"name":"草莓软糖","price":"8",...}]'
            })
                
        第二次请求
        此时 msgs 的完整内容
        [
            # ① system
            {'role': 'system', 'content': '你是零食商城的导购助手。\n本店商品的分类只有这些：[\'膨化食品\', \'糖果\', \'饮料\', \'辣味零食\']\n...'},
        
            # ② user
            {'role': 'user', 'content': '有什么不辣的零食推荐'},
        
            # ③ assistant（第一次回复，含 tool_calls）
            {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': 'call_abc123',
                'function': {'name': 'search_product', 'arguments': '{"keyword":"不辣"}'}
            }]},
        
            # ④ tool（代码执行结果）
            {'role': 'tool', 'tool_call_id': 'call_abc123', 'content': '[{"name":"原味薯片","price":"5","desc":"..."},
                {"name":"草莓软糖","price":"8","desc":"..."}]'}
        ]
        
        🧠 模型的"内心独白"（第二次请求）
            又收到请求了。让我看看完整上下文……
            system：我是导购，硬规则是必须先查库。
            user：有什么不辣的零食推荐
            我之前：调了 search_product，keyword="不辣"
            tool 返回：查到了 2 个商品——原味薯片（5元）、草莓软糖（8元）
            好，现在我有了真实数据。system 说不许凭记忆回答，现在我有库里的真实结果了，可以组织回答了。
            怎么组织？
            语气：导购应该热情、友好
            内容：推荐这两个商品，说明它们不辣，提一下价格
            格式：自然语言，不用 JSON
            写回答。
        
        📤 模型第二次请求的实际输出（final）
            {
                'role': 'assistant',
                'content': '为您推荐以下不辣的零食：\n1. 原味薯片（¥5）—— 经典原味，酥脆不辣\n2. 草莓软糖（¥8）—— 香甜草莓味，
                    不含辣味\n都是店里销量不错的不辣选择哦！',
                'tool_calls': None       # ← 这次没有 tool_calls，直接给答案
            }
        注意：这次 tool_calls 没了，content 有内容。模型"交卷"了。
        
        
        '''