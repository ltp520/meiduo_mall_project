from collections import OrderedDict

from django.http import JsonResponse

from goods.models import SKU, SKUImage, SKUSpecification, GoodsSpecification, SpecificationOption, GoodsCategory, \
    GoodsChannel


def get_breadcrumb(category):
    """
    封装面包屑导航代码:
    :param category: 商品类别
    :return: 面包屑导航字典
    """

    # 定义一个字典:
    breadcrumb = {
        'cat1':'',
        'cat2':'',
        'cat3':''
    }
    # 判断 category 是哪一个级别的.
    # 注意: 这里的 category 是 GoodsCategory对象
    if category.parent is None:
        # 当前类别为一级类别
        breadcrumb['cat1'] = category.name
    # 因为当前这个表示自关联表, 所以关联的对象还是自己:
    elif category.parent.parent is None:
        # 当前类别为二级
        breadcrumb['cat2'] = category.name
        breadcrumb['cat1'] = category.parent.name
    else:
        # 当前类别为三级
        breadcrumb['cat3'] = category.name
        cat2 = category.parent
        breadcrumb['cat2'] = cat2.name
        breadcrumb['cat1'] = cat2.parent.name

    return breadcrumb


def get_goods_and_spec(sku_id):
    # ======== 获取该商品和该商品对应的规格选项id ========
    try:
        # 根据 sku_id 获取该商品(sku)
        sku = SKU.objects.get(id=sku_id)
        # 获取该商品的图片
        sku.images = SKUImage.objects.filter(sku=sku)
    except Exception as e:
        return JsonResponse({'code':400,
                             'errmsg':'获取数据失败'})

    # 获取该商品的所有规格: [颜色, 内存大小, ...]
    sku_specs =SKUSpecification.objects.filter(sku=sku).order_by('spec_id')

    sku_key = []
    # 获取该商品的所有规格后,遍历,拿取一个规格

    for spec in sku_specs:
        # 规格 ----> 规格选项 ----> 选项id  ---> 保存到[]
        sku_key.append(spec.option.id)

    # ======== 获取类别下所有商品对应的规格选项id ========
    # 根据sku对象,获取对应的类别
    goods = sku.goods

    # 获取该类别下面的所有商品
    skus = SKU.objects.filter(goods=goods)

    dict = {}
    for temp_sku in skus:
        # 获取每一个商品(temp_sku)的规格参数
        s_specs = SKUSpecification.objects.filter(sku=temp_sku).order_by('spec_id')

        key = []
        for spec in s_specs:
            # 规格 ---> 规格选项 ---> 规格选项id ----> 保存到[]
            key.append(spec.option.id)

        # 把 list 转为 () 拼接成 k : v 保存到dict中:
        dict[tuple(key)] = temp_sku.id

    # ======== 在每个选项上绑定对应的sku_id值 ========
    specs = GoodsSpecification.objects.filter(goods=goods).order_by('id')

    for index, spec in enumerate(specs):
        # 复制当前sku的规格键
        key = sku_key[:]
        # 该规格的选项
        spec_options = SpecificationOption.objects.filter(spec=spec)

        for option in spec_options:
            # 在规格参数sku字典中查找符合当前规格的sku
            key[index] = option.id
            option.sku_id = dict.get(tuple(key))

        spec.spec_options = spec_options

    return goods, specs, sku


def get_categories():

    # ======== 生成上面字典格式数据 ========
    # 第一部分: 从数据库中取数据:
    # 定义一个有序字典对象
    dict = OrderedDict()

    # 对 GoodsChannel 进行 group_id 和 sequence 排序, 获取排序后的结果:
    channels = GoodsChannel.objects.order_by('group_id', 'sequence')

    # 遍历排序后的结果: 得到所有的一级菜单( 即,频道 )
    for channel in channels:
        # 从频道中得到当前的 组id
        group_id = channel.group_id

        # 判断: 如果当前 组id 不在我们的有序字典中:
        if group_id not in dict:
            # 我们就把 组id 添加到 有序字典中
            # 并且作为 key值, value值是
            # {'channels': [], 'sub_cats': []}
            dict[group_id] =  {
                                 'channels': [],
                                 'sub_cats': []
                               }

        # 获取当前频道的分类名称
        cat1 = channel.category

        # 给刚刚创建的字典中, 追加具体信息:
        # 即, 给'channels' 后面的 [] 里面添加如下的信息:
        dict[group_id]['channels'].append({
            'id':   cat1.id,
            'name': cat1.name,
            'url':  channel.url
        })
        cat2s = GoodsCategory.objects.filter(parent=cat1)
        # 根据 cat1 的外键反向, 获取下一级(二级菜单)的所有分类数据, 并遍历:
        for cat2 in cat2s:
            # 创建一个新的列表:
            cat2.sub_cats = []
            # 获取所有的三级菜单
            cat3s = GoodsCategory.objects.filter(parent=cat2)
            # 遍历
            for cat3 in cat3s:
                # 把三级菜单保存到cat2对象的属性中.
                cat2.sub_cats.append(cat3)
            # 把cat2对象保存到对应的列表中
            dict[group_id]['sub_cats'].append(cat2)

    return dict