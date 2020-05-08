# 导入所需要的依赖包
import os
import sys
sys.path.insert(0, '../../')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meiduo_mall.settings.dev')
import django
django.setup()
from django.http import JsonResponse
from django.template import loader
from django.conf import settings
from goods.utils import get_categories
from goods.models import SKU

# 复制 celery_tasks.html.tasks 中生成商品静态页面的函数:
def get_goods_and_spec(sku_id):

    # ======================== 获取该商品和该商品对应的规格选项id ===================================
    try:
        # 根据 sku_id 获取该商品(sku)
        sku = SKU.objects.get(id=sku_id)
        # 获取该商品的图片
        sku.images = sku.skuimage_set.all()
    except Exception as e:
        return JsonResponse({'code':400,
                             'errmsg':'获取数据失败'})

    # 获取该商品的所有规格: [颜色, 内存大小, ...]
    sku_specs = sku.skuspecification_set.order_by('spec_id')

    sku_key = []
    # 根据该商品的规格(例如颜色), 获取对应的规格选项id(例如黑色id)
    # 保存到 [] 中
    for spec in sku_specs:
        sku_key.append(spec.option.id)

    # ============================ 获取类别下所有商品对应的规格选项id================================

    # 获取该商品的类别(spu,这里的spu就是goods)
    goods = sku.goods

    # 获取该类别下面的所有商品
    skus = goods.sku_set.all()

    dict = {}
    for sku in skus:
        # 获取每一个商品(sku)的规格参数
        s_specs = sku.skuspecification_set.order_by('spec_id')

        # 根据该商品的规格(例如颜色), 获取对应的规格选项id(例如黑色id)
        # 保存到 [] 中
        key = []
        for spec in s_specs:
            key.append(spec.option.id)

        # 把 list 转为 () 拼接成 k : v 保存到dict中:
        dict[tuple(key)] = sku.id

    # ============================ 在每个选项上绑定对应的sku_id值 ===================================
    goods_specs = goods.goodsspecification_set.order_by('id')

    for index, spec in enumerate(goods_specs):
        # 复制当前sku的规格键
        key = sku_key[:]
        # 该规格的选项
        spec_options = spec.specificationoption_set.all()
        # spec_options = spec.options.all()
        for option in spec_options:
            # 在规格参数sku字典中查找符合当前规格的sku
            key[index] = option.id
            option.sku_id = dict.get(tuple(key))

        spec.spec_options = spec_options
    categories = get_categories()
    # 渲染模板，生成静态html文件
    context = {
        'categories': categories,
        'goods': goods,
        'specs': goods_specs,
        'sku': sku
    }

    template = loader.get_template('detail.html')
    html_text = template.render(context)
    file_path = os.path.join(settings.GENERATED_STATIC_HTML_FILES_DIR,
                             'goods/'+str(sku_id)+'.html')
    with open(file_path, 'w') as f:
        f.write(html_text)
if __name__ == '__main__':
    # 获取所有的商品信息
    skus = SKU.objects.all()
    # 遍历拿出所有的商品:
    for sku in skus:
        print(sku.id)
        # 调用我们之前在 celery_tasks.html.tasks 中写的生成商品静态页面的方法:
        # 我们最好把这个函数单独复制过来, 这样可以不依靠 celery, 否则必须要开启celery
        get_goods_and_spec(sku.id)