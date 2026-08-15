from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

'''一. 写自定义分页'''
# PageNumberPagination 基于页码的分页器
class CustomPagination(PageNumberPagination):
    page_size = 10                          # 每页10条
    page_query_param = 'pageNum'            # 前端传的页码参数名
    page_size_query_param = 'pageSize'      # 前端传的每页条数参数名
    max_page_size = 100

    def get_paginated_response(self, data):
        # 把 DRF 默认格式 改成 前端要的 RuoYi 格式
        return Response({
            'code':200,
            'msg':'查询成功',
            'rows':data,
            'total':self.page.paginator.count,
        })
