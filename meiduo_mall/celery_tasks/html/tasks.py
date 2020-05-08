import os

from django.conf import settings
from django.template import loader

from celery_tasks.main import celery_app
from goods.utils import get_categories, get_goods_and_spec


@celery_app.task(name='generate_static_sku_detail_html')
def generate_static_sku_detail_html(sku_id):
    """
    生成静态商品详情页面
    :param sku_id: 商品id值
    """
    # 商品分类菜单
    dict = get_categories()

    goods, specs, sku = get_goods_and_spec(sku_id)

    context = {'categories': dict,
               'goods': goods,
               'specs': specs,
               'sku': sku}

    template = loader.get_template('detail.html')

    html_text = template.render(context)

    file_path = os.path.join(settings.GENERATED_STATIC_HTML_FILES_DIR, 'goods/' + str(sku_id) + '.html')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_text)
