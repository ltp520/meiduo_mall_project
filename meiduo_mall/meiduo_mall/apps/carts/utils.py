import base64
import pickle

from django_redis import get_redis_connection


def merge_cart_cookie_to_redis(request, user, response):
    # 1.获取cookie中的购物车信息
    cookie_cart = request.COOKIES.get('carts')
    if not cookie_cart:
        return response
    carts = pickle.loads(base64.b64decode(cookie_cart.encode()))
    carts_sku = {}
    carts_add = []
    carts_remove = []
    for sku_id, values in carts.items():
        carts_sku[sku_id] = values['count']
        if values['selected']:
            carts_add.append(sku_id)
        else:
            carts_remove.append(sku_id)
    # 2.连接redis
    redis_conn = get_redis_connection('carts')
    # 3.在redis中排山倒海
    if carts_sku:
        redis_conn.hmset('carts_%s' % user.id, carts_sku)
    if carts_add:
        redis_conn.sadd('selected_%s' % user.id, *carts_add)
    if carts_remove:
        redis_conn.srem('selected_%s' % user.id, *carts_remove)
    # 4.清除cookie信息
    response.delete_cookie('carts')
    # 5.返回response
    return response
