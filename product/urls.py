from product import views
from django.urls import path,include
from rest_framework.routers import DefaultRouter
# JWT   TokenObtainPairView:获取 Token的视图     TokenRefreshView:刷新 Token的视图
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView

app_name = 'product'

'''
JWT 认证流程（身份证系统）:
1. 用户登录: POST /api/login/ 传 {username, password}
2. 服务器验证密码正确 → 发两张"身份证":
   - access token(30分钟有效)  → 请求时带
   - refresh token(7天有效)    → access过期后换新的
3. 请求受保护接口: Header 里带  Authorization: Bearer <access>
4. 服务器验签 → 通过则从 token 里解析出 user_id → 知道是谁
5. 没有 token 或 token 过期 → 401 拒绝访问

关键代码（settings.py）:
   REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication']}
   SIMPLE_JWT = {'ACCESS_TOKEN_LIFETIME': 30分钟, 'REFRESH_TOKEN_LIFETIME': 7天}

用户角度: 登录一次 → 拿token → 一直带着用 → 过期续签
为什么用JWT: 服务器不存登录状态(无状态), 适合前后端分离/小程序
'''
'''
简化为核心的5个动作:登录 → 发证 → 带证 → 验证 → 放行
'''

router = DefaultRouter()
router.register('snack/category',views.CategoryViewSet)
router.register('snack/product',views.ProductViewSet)
router.register('snack/banner',views.BannerViewSet)
router.register('snack/cart',views.CartViewSet)
router.register('snack/address',views.AddressViewSet)
# router.register('orderproduct',views.OrderProductViewSet)
router.register('snack/order',views.OrderViewSet)

urlpatterns = [
    path('',include(router.urls)),
    path('login',views.LoginView.as_view(),name='token_obtain_pair'),   # 登录（2026-08-09 注释，改回 simplejwt）
    # path('login',TokenObtainPairView.as_view(),name='token_obtain_pair'),   # 登录（simplejwt 自带）
    path('refresh',TokenRefreshView.as_view(),name='token_refresh'),        # 续签
    path('register',views.RegisterView.as_view(),name='register'),         # 注册
    path('snack/category/list',views.CategoryViewSet.as_view({'get':'list'})),
    path('snack/product/list',views.ProductViewSet.as_view({'get':'list'})),
    path('snack/banner/list', views.BannerViewSet.as_view({'get': 'list'})),
    path('snack/cart/list', views.CartViewSet.as_view({'get': 'list'})),
    path('snack/cart/selectMyCartList', views.CartViewSet.as_view({'get': 'selectMyCartList'})),
    path('snack/cart/addProductToCart/<int:product_id>',views.CartViewSet.as_view({'put':'addProductToCart'})),
    path('snack/cart/increaseQuantity/<int:cart_id>',views.CartViewSet.as_view({'put':'increaseQuantity'})),
    path('snack/cart/reduceQuantity/<int:cart_id>',views.CartViewSet.as_view({'put':'reduceQuantity'})),
    path('snack/address',views.AddressViewSet.as_view({'get': 'list','post': 'create'})),
    path('snack/address/list', views.AddressViewSet.as_view({'get': 'list'})),
    path('snack/address/selectMyAddressList',views.AddressViewSet.as_view({'get':'selectMyAddressList'})),
    path('snack/order/list', views.OrderViewSet.as_view({'get': 'list'})),
    path('snack/order/selectMyOrderList', views.OrderViewSet.as_view({'get':'selectMyOrderList'})),  # ← 新增：2026-08-28 修复 404
    path('snack/order', views.OrderViewSet.as_view({'post': 'create'})),  # ← 新增：APPEND_SLASH=False 下需要手动挂 POST
    path('home/page/selectDataInfo', views.HomePageView.as_view()),
    path('home/page/selectCategoryChart', views.HomePageView.as_view()),
    path('home/page/selectOrderStatusCount', views.HomePageView.as_view()),
    path('snack/category/selectAllCategoryNameList',views.CategoryNameListView.as_view()),
    path('snack/recommendation/advanced',views.RecommendationView.as_view()),
    # ====== 详情路由（无斜杠版，匹配小程序前端调用）======
    path('snack/product/<int:pk>', views.ProductViewSet.as_view({'get':'retrieve', 'put':'update', 'delete':'destroy'})),
    path('snack/category/<int:pk>', views.CategoryViewSet.as_view({'get':'retrieve', 'put':'update', 'delete':'destroy'})),
    path('snack/banner/<int:pk>', views.BannerViewSet.as_view({'get':'retrieve', 'put':'update', 'delete':'destroy'})),
    path('snack/cart/<int:pk>', views.CartViewSet.as_view({'get':'retrieve', 'put':'update', 'delete':'destroy'})),
    path('snack/address/<int:pk>', views.AddressViewSet.as_view({'get':'retrieve', 'put':'update', 'delete':'destroy'})),
    path('snack/order/<str:order_id>', views.OrderViewSet.as_view({'get':'retrieve', 'put':'update', 'delete':'destroy'})),
    # ------------------------------------------------------------------------------------------
    path('captchaImage',views.CaptchaView.as_view(),name='captcha'),        # 验证码（已注释）
    path('system/user/profile/updatePwd', views.UpdatePwdView.as_view()),   # ← 新增：修改密码
    path('getInfo', views.UserInfoView.as_view()),      # 登录后返回用户信息（已注释）
    path('logout', views.LogoutView.as_view()),         # 退出（已注释）
    path('getRouters', views.RoutersView.as_view()),        # 菜单（已注释）

    path('snack/pay', views.PayView.as_view()),                       # 生成支付链接
    path('snack/pay/callback', views.PayCallbackView.as_view()),      # 支付回调

]

