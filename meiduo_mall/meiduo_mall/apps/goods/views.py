# 导入: 
from django.core.paginator import Paginator, EmptyPage
from django.views import View
from goods.models import SKU, GoodsCategory
from django.http import JsonResponse

from goods.utils import get_breadcrumb


class ListView(View):
    """商品列表页"""

    def get(self, request, category_id):
        # 接收数据
        page = request.GET.get('page')
        page_size = request.GET.get('page_size')
        sort = request.GET.get('ordering')
        # 根据category_id获取对象
        # 判断category_id是否正确
        try:
            # 获取三级菜单分类信息:
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return JsonResponse({'code': 400,
                                 'errmsg': '获取mysql数据出错'})

        # 根据该对象获取所有关联sku，并根据排序方式进行排序
        # 排序方式:
        try:
            skus = SKU.objects.filter(category=category,
                                      is_launched=True).order_by(sort)
        except SKU.DoesNotExist:
            return JsonResponse({'code':400,
                                 'errmsg':'获取mysql数据出错'})
        # 调用Paginator函数将sku分页
        paginator = Paginator(skus, page_size)
        # 根据前端发送页数获取单页sku
        try:
            page_skus = paginator.page(page)
        except EmptyPage:
            # 如果page_num不正确，默认给用户400
            return JsonResponse({'code': 400,
                                 'errmsg': 'page数据出错'})
        count = paginator.num_pages
        # 定义list，将单页数据写入该列表
        sku_list = []
        for sku in page_skus:
            sku_list.append({
                'id': sku.id,
                'default_image_url': sku.default_image_url,
                'name': sku.name,
                'price': sku.price
        })
        # 返回数据

        breadcrumb = get_breadcrumb(category)

        return JsonResponse({
            "code": 0,
            "errmsg": "ok",
            "breadcrumb": breadcrumb,  # 面包屑数据
            "list": sku_list,
            "count": count  # 分页总数
        })

class HotGoodsView(View):
    """商品热销排行"""

    def get(self, request, category_id):
        """提供商品热销排行 JSON 数据"""
        # 根据销量倒序
        try:
            skus = SKU.objects.filter(category_id=category_id,
                                  is_launched=True).order_by('-sales')[:2]
        except Exception as e:
            return JsonResponse({'code':400,
                                 'errmsg':'获取商品出错'})
        # 转换格式:
        hot_skus = []
        for sku in skus:
            hot_skus.append({
                'id':sku.id,
                'default_image_url':sku.default_image_url,
                'name':sku.name,
                'price':sku.price
            })

        return JsonResponse({'code':0,
                             'errmsg':'OK',
                             'hot_skus':hot_skus})


from haystack.views import SearchView

class MySearchView(SearchView):
    '''重写SearchView类'''
    def create_response(self):
        page = self.request.GET.get('page')
        # 获取搜索结果
        context = self.get_context()
        data_list = []
        for sku in context['page'].object_list:
            data_list.append({
                'id':sku.object.id,
                'name':sku.object.name,
                'price':sku.object.price,
                'default_image_url':sku.object.default_image_url,
                'searchkey':context.get('query'),
                'page_size':context['page'].paginator.num_pages,
                'count':context['page'].paginator.count
            })
        # 拼接参数, 返回
        return JsonResponse(data_list, safe=False)