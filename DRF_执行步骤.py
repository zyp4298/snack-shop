"""
零食商城项目 — DRF 完整执行步骤
====================================
打开这个文件照着做，就能跑通第一个 DRF 接口
最后更新：2026-08-02
====================================
"""


# ==== 步骤 1: 装 DRF ====
# pip install djangorestframework


# ==== 步骤 2: settings.py 注册 ====
# 在 INSTALLED_APPS 里加 'rest_framework'


# ==== 步骤 3: product/serializers.py（翻译官） ====
# from rest_framework import serializers
# from product.models import Category, Product
#
# class CategorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Category
#         fields = '__all__'
#
# class ProductSerializer(serializers.ModelSerializer):
#     categoryId = serializers.CharField(source='category.id', read_only=True)
#     class Meta:
#         model = Product
#         fields = ['id', 'categoryId', 'name', 'description', 'price', 'image']


# ==== 步骤 4: product/views_api.py（视图集） ====
# from rest_framework import viewsets
# from product.models import Category, Product
# from product.serializers import CategorySerializer, ProductSerializer
#
# class CategoryViewSet(viewsets.ModelViewSet):
#     queryset = Category.objects.all()
#     serializer_class = CategorySerializer
#
# class ProductViewSet(viewsets.ModelViewSet):
#     queryset = Product.objects.all()
#     serializer_class = ProductSerializer


# ==== 步骤 5: 零食商城/urls.py（路由） ====
# from django.contrib import admin
# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from product.views_api import CategoryViewSet, ProductViewSet
#
# router = DefaultRouter()
# router.register('category', CategoryViewSet)
# router.register('product', ProductViewSet)
#
# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('api/', include(router.urls)),
# ]


# ==== 步骤 6: 启动 + 验证 ====
# python manage.py runserver 8000
# 访问：http://localhost:8000/api/category/


# ==== 5 个 RESTful 接口（自动生成） ====
# GET    /api/category/         查所有
# GET    /api/category/1/       查单个
# POST   /api/category/         新增
# PUT    /api/category/1/       修改
# DELETE /api/category/1/       删除


# ==== 常见报错排查 ====
# No module named 'rest_framework' → 装 DRF
# 'POST' is not defined          → DATABASES 里 PORT 拼写错了
# name 'User' is not defined     → models.py 顶部没 import User
# 404 Not Found                  → urls.py 没配 Router
# 看不到 productId 字段           → Serializer 里没加 categoryId
