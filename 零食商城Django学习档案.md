# 🍪 零食商城 Django 学习档案（完整版）

> 用途：把这段时间学的所有东西整理成"速查档案"，忘了就翻
> 记录时间：2026-08-08（第 5 个工作日）
> 目录：D:\PythonPractice\零食商城

---

## 一、这个项目在做什么（一句话）

用 **Django + DRF** 重写零食商城的后端（原项目是 Java SpringBoot），
前端（Vue 管理后台 + UniApp 小程序）直接用模板的，不改。
**你写的所有代码 = 前端要的数据接口。**

---

## 二、项目全景图（数据怎么流动）

```
前端(Vue, 90端口) → HTTP请求 → Django后端(8000端口) → MySQL数据库
        ↑                                      ↓
        └──────────── JSON数据 ←───────────────┘
```

**四个核心角色（对应四个文件）：**

| 角色 | 文件 | 一句话 |
|:----|:----|:------|
| 建表员 | models.py | 定义数据库长什么样（7张表） |
| 翻译官 | serializers.py | 数据库对象 ↔ JSON 互译 |
| 服务员 | views.py | 接请求 → 处理 → 返回数据 |
| 交通警察 | urls.py | 网址指向哪个 ViewSet |
| 包装员 | pagination.py | 列表变成前端要的 {code, rows, total} |
| 总开关 | settings.py | 注册 app / 连库 / 配 JWT+CORS |
| 遥控器 | manage.py | 所有命令入口 |

---

## 三、Django 基础（第 1 部分）

### 3.1 建表（models.py）
```python
class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # 金额必须用 Decimal
    create_time = models.DateTimeField(auto_now_add=True)
```
- 一个 `class` = 一张表；不写主键，Django 自动生成 `id`
- `ForeignKey` = 外键（关联另一张表）
- `related_name='products'` = 反查：`category.products.all()`

### 3.2 建表命令
```bash
python manage.py makemigrations   # 生成迁移文件
python manage.py migrate          # 真正建表
```

### 3.3 ORM 查询（你练过的）
```python
Product.objects.all()                             # 查所有
Product.objects.filter(category_id=1)             # 按条件
Product.objects.filter(name__contains='饼干')     # 模糊查询
product.category.name                             # 沿外键取关联数据
```

---

## 四、DRF 核心（第 2 部分）★★★ 最重要

### 4.1 三件套套路
```
Serializer（翻译） → ViewSet（服务） → Router（路由）
```

### 4.2 Serializer（翻译官）
```python
class ProductSerializer(serializers.ModelSerializer):
    # 前端要 productId，Model 叫 id → 用 source 翻译
    categoryId = serializers.CharField(source='category.id', read_only=True)
    class Meta:
        model = Product
        fields = ['id', 'categoryId', 'name', 'price', 'image']  # ⚠️ 是 fields 不是 field！
```
- **字段翻译**：`source='外键.字段'` 取关联表的数据
- **嵌套序列化**：`products = OrderProductSerializer(many=True, read_only=True)` 一对多时嵌列表

### 4.3 ViewSet（服务员）
```python
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()          # ① 登记用（Router 取名）
    serializer_class = ProductSerializer       # ② 用哪个翻译官
```
- `ModelViewSet` = 自动给你 5 个接口（GET查/POST增/PUT改/DELETE删）
- **登录权限版**：
```python
class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]     # 必须登录
    def get_queryset(self):                    # 只看自己的数据
        return Cart.objects.filter(user=self.request.user)
```

### 4.4 APIView（自定义动作，如注册）
```python
class RegisterView(APIView):
    def post(self, request):
        username = request.data.get('username')
        ...
        user = User.objects.create_user(username=username, password=password)
        refresh = RefreshToken.for_user(user)
        return Response({'msg': '注册成功', 'access': str(refresh.access_token), 'refresh': str(refresh)})
```

### 4.5 Router（交通警察）
```python
router = DefaultRouter()
router.register('product', views.ProductViewSet)
urlpatterns = [path('', include(router.urls))]
```
- **URL 路径由 register 的第一个参数决定，不是 app 名**

### 4.6 分页包装（前端要的格式）
```python
# pagination.py
class CustomPagination(PageNumberPagination):
    page_size = 10
    page_query_param = 'pageNum'
    page_size_query_param = 'pageSize'
    def get_paginated_response(self, data):
        return Response({'code': 200, 'msg': '查询成功', 'rows': data, 'total': self.page.paginator.count})
```
```python
# views.py 里加一行
class CategoryViewSet(viewsets.ModelViewSet):
    ...
    pagination_class = CustomPagination
```

---

## 五、JWT 认证（第 3 部分）

### 5.1 流程（身份证系统）
```
登录(用户名密码) → 服务器发两张证：
  access(30分钟有效) → 请求时带
  refresh(7天有效)   → 过期后换新的
请求带证：Header 加 Authorization: Bearer <access>
服务器验签 → 知道是谁 → 决定放不放行
```

### 5.2 配置（settings.py）
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
}
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),   # ⚠️ 是 LIFETIME 不是 LIFTIME！
}
```

### 5.3 路由（urls.py）
```python
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
path('login', TokenObtainPairView.as_view()),     # 登录（自带的）
path('refresh', TokenRefreshView.as_view()),      # 续签（自带的）
```

### 5.4 测试（ApiPost）
```
POST http://localhost:8000/api/login/   body: {"username":"张三","password":"123456"}
→ 返回 access + refresh
GET /api/cart/  Headers: Authorization: Bearer <access>
⚠️ 用 access，不是 refresh！贴错了报 "Token has wrong type"
```

---

## 六、前端联调（第 4 部分，进行中）

### 6.1 联调 = 4 件事（固定套路）
```
① CORS（端口不同，浏览器拦）     ✅ 已做
② Proxy（前端 → Django 转发）   ✅ 已做
③ 路径对齐（前端路径→后端路径）  ✅ category 已做
④ 字段对齐（前端字段→后端字段）  ⏳ 待做
```

### 6.2 CORS（settings.py）
```python
INSTALLED_APPS += ['corsheaders']
MIDDLEWARE 顶部加 'corsheaders.middleware.CorsMiddleware'   # 必须最顶
CORS_ALLOW_ALL_ORIGINS = True   # 开发用；上线改具体域名
CORS_ALLOW_CREDENTIALS = True
ALLOWED_HOSTS = ['*']           # 开发用
```

### 6.3 Proxy（vite.config.js）
```javascript
const baseUrl = 'http://localhost:8000'   // 改：8080→8000（原来指 Spring Boot）
proxy: { '/dev-api': { target: baseUrl, changeOrigin: true, rewrite: p => p.replace(/^\/dev-api/, '') } }
```

### 6.4 路径对齐（urls.py）★ 今天学的关键
```python
# 主项目 零食商城/urls.py：⚠️ 不能带 /api/ 前缀！
path('', include('product.urls'))     # 不是 path('api/', ...)

# product/urls.py：
router.register('snack/category', views.CategoryViewSet)   # 前端路径
urlpatterns += [path('snack/category/list', views.CategoryViewSet.as_view({'get':'list'}))]
```

### 6.5 前端要的返回格式（RuoYi 风格）
```json
{ "code": 200, "msg": "查询成功", "rows": [...], "total": 11 }
```
- `code`：200=成功，401=未登录，500=服务器错误
- 列表用 `rows` + `total`（前端读 response.rows / response.total）

---

## 七、7 张表 + 接口清单

| 表 | 前端路径 | 状态 |
|:---|:--------|:----:|
| category 分类 | /snack/category/list | ✅ 已通 |
| product 商品 | /snack/product/list | ⏳ 待对齐 |
| banner 轮播 | /snack/banner/list | ⏳ 待对齐 |
| cart 购物车 | /snack/cart/list | ⏳ 待对齐 |
| address 地址 | /snack/address/list | ⏳ 待对齐 |
| order 订单 | /snack/order/list | ⏳ 待对齐 |
| （order_products 明细）| 不单独开放 | ✅ 已嵌套 |

---

## 八、踩坑记录（全是要背的教训）

| 坑 | 原因 | 教训 |
|:---|:-----|:-----|
| `field` 少写 s | DRF 拼写 | 是 `fields`（复数） |
| `REFRESH_TOKEN_LIFTIME` | 少个 E | 是 `LIFETIME` |
| `'POST':'3306'` | 拼写 | 是 `'PORT'` |
| `User` not defined | 漏 import | 检查文件顶部 import |
| queryset 报错 | 注释掉了 | **queryset 和 get_queryset 都要有** |
| token has wrong type | 贴了 refresh | 用 **access** |
| 改 urls 没生效 | 没重启 | **改 urls 必须重启服务** |
| /snack 404 | 主项目带 /api/ 前缀 | include 时 `path('', ...)` |

---

## 九、常用命令速查

```bash
python manage.py runserver 8000       # 启动
python manage.py makemigrations       # 生成迁移
python manage.py migrate              # 建表
python manage.py createsuperuser      # 建管理员
python manage.py shell                # 交互式调试
python import_data.py                 # 导入数据（scripts 目录）
pip install 包名                      # 装包
```

---

## 十、求职进度

```
项目完成度：约 40%（后端全完成，联调进行中，认证权限完成）
已学葫芦：13+ 个（见上面各节）
待做：其余5接口对齐 → 字段对齐 → 登录对齐 → 前端跑通 → Redis → Git → 部署 → 简历
目标：上海 Python 后端，10k 左右
```

---

## 十一、学习方法提醒（重要）

```
① 不用背代码，背"套路"（每个葫芦一句话）
② 照葫芦画瓢 = 正确学习方式，不是缺点
③ 新内容觉得"难" = 其实只是"新"，多见几次就熟了
④ 自己手打代码 > 复制粘贴（记忆更深）
⑤ 前端是"合同"，后端迁就它（不改前端）
```
