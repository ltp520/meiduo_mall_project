import base64
import json
import pickle

from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render

# Create your views here.
from django.views import View
from django_redis import get_redis_connection

from goods.models import SKU


class CartsView(View):
    # 添加购物车
    def post(self, request):
        # 1.接收参数
        request_dict = json.loads(request.body.decode())
        sku_id = request_dict.get('sku_id')
        count = request_dict.get('count')
        selected = request_dict.get('selected', True)
        # 2.判断参数格式
        if not all([sku_id, count]):
            return JsonResponse({'code': 400,
                                 'errmsg': '缺少必传参数'})
        # 判断sku_id是否存在
        try:
            SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return HttpResponseForbidden('商品不存在')

        # 判断count是否为数字
        try:
            count = int(count)
        except Exception:
            return HttpResponseForbidden('参数count有误')
        # 判断selected是否为bool值
        if selected:
            if not isinstance(selected, bool):
                return HttpResponseForbidden('参数selected有误')
        # 3.判断用户是否登录
        user = request.user
        if user.is_authenticated:
            # 4.登录用户：
            # 4.1 连接redis
            redis_conn = get_redis_connection('carts')
            # 4.2 使用hash存储用户id：{商品id：数量}
            pl = redis_conn.pipeline()
            pl.hincrby('carts_%s' % request.user.id, sku_id, count)
            # 4.3 使用set存储selected值
            pl.sadd('selected_%s' % request.user.id, sku_id)
            pl.execute()
            return JsonResponse({'code': 0,
                                 'errmsg': '添加购物车成功'})
        else:
            # 5.非登录用户
            # 判断商品是否已添加
            carts = request.COOKIES.get('carts')
            if carts:
                cart_dict = pickle.loads(base64.b64decode(carts))
            else:
                cart_dict = {}
            # 5.1 将数据做成固定格式
            if sku_id in cart_dict:
                count += carts[sku_id]['count']
            cart_dict[sku_id] = {'count': count, 'selected': selected}
            # 5.2 加密并写入cookie
            carts = base64.b64encode(pickle.dumps(cart_dict)).decode()
            response = JsonResponse({'code': 0,
                                     'errmsg': '添加购物车成功'})
            response.set_cookie('carts', carts)
            # 6.返回结果
            return response

    def get(self, request):
        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            cart_dict = {}
            redis_conn = get_redis_connection('carts')
            item_dict = redis_conn.hgetall('carts_%s' % user.id)
            cart_selected = redis_conn.smembers('selected_%s' % user.id)
            for sku_id, count in item_dict.items():
                cart_dict[int(sku_id)] = {'count': int(count),
                                          'selected': sku_id in cart_selected}
        else:
            carts = request.COOKIES.get('carts')
            if carts:
                cart_dict = pickle.loads(base64.b64decode(carts.encode()))
            else:
                cart_dict = {}

        sku_ids = cart_dict.keys()
        skus = SKU.objects.filter(id__in=sku_ids)
        cart_skus = []
        for sku in skus:
            cart_skus.append({
                'id': sku.id,
                'name': sku.name,
                'count': cart_dict.get(sku.id).get('count'),
                'selected': cart_dict.get(sku.id).get('selected'),
                'default_image_url': sku.default_image_url,
                'price': sku.price,
                'amount': sku.price * cart_dict.get(sku.id).get('count'),
            })

        return JsonResponse({'code': 0,
                             'errmsg': 'OK',
                             'cart_skus': cart_skus})

    def put(self, request):
        # 1.接收参数
        request_dict = json.loads(request.body.decode())
        sku_id = request_dict.get('sku_id')
        count = request_dict.get('count')
        selected = request_dict.get('selected', True)
        # 2.判断参数格式
        if not all([sku_id, count]):
            return JsonResponse({'code': 400,
                                 'errmsg': '缺少必传参数'})
        # 判断sku_id是否存在
        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return HttpResponseForbidden('商品不存在')

        # 判断count是否为数字
        try:
            count = int(count)
        except Exception:
            return HttpResponseForbidden('参数count有误')
        # 判断selected是否为bool值
        if selected:
            if not isinstance(selected, bool):
                return HttpResponseForbidden('参数selected有误')
        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            # 用户已登录，修改redis购物车
            # 4.1 连接redis
            redis_conn = get_redis_connection('carts')
            # 4.2 使用hash存储用户id：{商品id：数量}
            pl = redis_conn.pipeline()
            pl.hset('carts_%s' % user.id, sku_id, count)
            # 是否选中
            if selected:
                pl.sadd('selected_%s' % user.id, sku_id)
            else:
                pl.srem('selected_%s' % user.id, sku_id)
            pl.execute()
            # 创建响应对象
            cart_sku = {
                'id': sku_id,
                'count': count,
                'selected': selected,
            }
            return JsonResponse({'code': 0,
                                 'errmsg': '修改购物车成功',
                                 'cart_sku': cart_sku})
        else:
            # 用户未登录，修改cookie购物车
            cookie_cart = request.COOKIES.get('carts')
            if cookie_cart:
                # 将cookie_cart转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
                cart_dict = pickle.loads(base64.b64decode(cookie_cart.encode()))
            else:
                cart_dict = {}
            # 因为接口设计为幂等的，直接覆盖
            cart_dict[sku_id] = {
                'count': count,
                'selected': selected
            }
            # 将字典转成bytes,再将bytes转成base64的bytes,最后将bytes转字符串
            cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()

            # 创建响应对象
            cart_sku = {
                'id': sku_id,
                'count': count,
                'selected': selected
            }
            response = JsonResponse({'code': 0,
                                     'errmsg': '修改购物车成功',
                                     'cart_sku': cart_sku})
            # 响应结果并将购物车数据写入到cookie
            response.set_cookie('carts', cart_data)

            return response

    def delete(self, request):
        """删除购物车"""
        # 接收参数
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        # 判断sku_id是否存在
        try:
            SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return HttpResponseForbidden('商品不存在')

        # 判断用户是否登录
        user = request.user
        if user is not None and user.is_authenticated:
            # 用户已登录，删除redis购物车
            redis_conn = get_redis_connection('carts')
            pl = redis_conn.pipeline()
            # 删除键，就等价于删除了整条记录
            pl.hdel('carts_%s' % user.id, sku_id)
            pl.srem('selected_%s' % user.id, sku_id)
            pl.execute()

            # 删除结束后，没有响应的数据，只需要响应状态码即可
            return JsonResponse({'code': 0,
                                 'errmsg': '删除购物车成功'})
        else:
            # 用户未登录，删除cookie购物车
            # 用户未登录，删除cookie购物车
            cookie_cart = request.COOKIES.get('carts')
            if cookie_cart:
                # 将cookie_cart转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
                cart_dict = pickle.loads(base64.b64decode(cookie_cart.encode()))
            else:
                cart_dict = {}

            # 创建响应对象
            response = JsonResponse({'code': 0,
                                     'errmsg': '删除购物车成功'})
            if sku_id in cart_dict:
                del cart_dict[sku_id]
                # 将字典转成bytes,再将bytes转成base64的bytes,最后将bytes转字符串
                cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()
                # 响应结果并将购物车数据写入到cookie
                response.set_cookie('carts', cart_data)

            return response


class CartSelectAllView(View):
    # 全选购物车
    def put(self, request):
        # 接收参数
        json_dict = json.loads(request.body.decode())
        selected = json_dict.get('selected', True)

        # 校验参数
        if selected:
            if not isinstance(selected, bool):
                return HttpResponseForbidden('参数selected有误')

        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            # 用户已登录，操作redis购物车
            # 连接redis
            redis_conn = get_redis_connection('carts')
            # 从hash中获取sku_id
            skus = redis_conn.hgetall('carts_%s' % user.id)
            sku_ids = skus.keys()
            # 如果selected为True，往set中添加sku_id
            if selected:
                redis_conn.sadd('selected_%s' % user.id, *sku_ids)
            # 如果selected为False，删除set
            else:
                redis_conn.srem('selected_%s' % user.id, *sku_ids)
        else:
            # 用户未登录，操作 cookie 购物车
            cookie_cart = request.COOKIES.get('carts')
            response = JsonResponse({'code': 0,
                                     'errmsg': '全选购物车成功'})
            if cookie_cart:
                cart_dict = pickle.loads(base64.b64decode(cookie_cart.encode()))

                for sku_id in cart_dict.keys():
                    cart_dict[sku_id]['selected'] = selected

                cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()

                response.set_cookie('carts', cart_data)

            return response


class CartsSimpleView(View):
    """商品页面右上角购物车"""

    def get(self, request):
        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            cart_dict = {}
            redis_conn = get_redis_connection('carts')
            item_dict = redis_conn.hgetall('carts_%s' % user.id)
            cart_selected = redis_conn.smembers('selected_%s' % user.id)
            for sku_id, count in item_dict.items():
                cart_dict[int(sku_id)] = {'count': int(count),
                                          'selected': sku_id in cart_selected}
        else:
            carts = request.COOKIES.get('carts')
            if carts:
                cart_dict = pickle.loads(base64.b64decode(carts.encode()))
            else:
                cart_dict = {}

        sku_ids = cart_dict.keys()
        skus = SKU.objects.filter(id__in=sku_ids)
        cart_skus = []
        for sku in skus:
            cart_skus.append({
                'id': sku.id,
                'name': sku.name,
                'count': cart_dict.get(sku.id).get('count'),
                'default_image_url': sku.default_image_url,
            })

        return JsonResponse({'code': 0,
                             'errmsg': 'OK',
                             'cart_skus': cart_skus})