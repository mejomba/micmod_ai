import uuid

from django import template

from django.contrib.contenttypes.models import ContentType

from comments.models import Comments, CommentSeen
from extra_data.models import Item
from files.models import File, Image
from tools.utils import show_error
from num2fawords import words

register = template.Library()


@register.filter
def classname(obj):
    return obj.__class__.__name__

@register.filter
def set_suffix(value,suffix):
    return f"{value}{suffix}" if value else ""


@register.simple_tag
def has_access(user_role_list=None, valid_role_str=None):
    if valid_role_str:
        valid_role = valid_role_str.split(',')
        for role in user_role_list:
            if role.get_role_display() == valid_role:
                return True
    return False


@register.inclusion_tag('files/partial/image_gallery4.html', takes_context=True)
def show_image_gallery(context, obj, form=None, js=None, editable=None, create=None,
                       upload=True, detail=None, formset_idx=None, only_popup=None, group=None):
    context = {'js': js,
               'editable': editable,
               'groups': range(1, form.image_groups + 1) if form else 1,
               'create': create,
               'upload': upload,
               'form': form,
               'detail': detail,
               'formset_idx': formset_idx,
               'obj': obj,
               'crispy': form.crispy if form else True,
               'only_popup': only_popup}
    images = {}
    image_fields = {}
    context['images'] = []
    context['image_fields'] = []

    if hasattr(obj, '_meta'):
        content_type = ContentType.objects.filter(app_label=obj._meta.label.split('.')[0],
                                                  model=obj._meta.model_name.lower()).first()

        if form and form.image_groups:
            for g in range(1, form.image_groups + 1):
                images[f'image{g}'] = Image.objects.filter(object_id=obj.pk, content_type=content_type.id, group=g)
                image_fields[f'image_{g}'] = form.fields[f'image_{g}']
            context['images'].append(images)
            context['image_fields'].append(image_fields)

    return context


@register.inclusion_tag('files/partial/show_files.html')
def show_files(files=None, js=None, editable=None, group=None, create=None, upload=True, idx=None):
    context = {'files': files,
               'js': js,
               'editable': editable,
               'group': group,
               'create': create,
               'upload': upload,
               'idx': idx}
    return context


# @register.inclusion_tag('files/partial/show_modal.html')
@register.inclusion_tag('files/partial/show_modal2.html')
def show_modal(obj, field, target_model_name=None, editable=None):
    import re
    pattern = r'\d+'
    group = re.findall(pattern, field.html_name)[-1]
    try:
        group = int(group)
    except Exception as e:
        group = 0
        print(e)

    context = {}
    target = globals().get(target_model_name)
    if hasattr(obj, '_meta') and target:
        content_type = ContentType.objects.filter(app_label=obj._meta.label.split('.')[0],
                                                  model=obj._meta.model_name.lower()).first()

        for g in range(1, group + 1):
            context['contents'] = target.objects.filter(object_id=obj.pk, content_type=content_type.id, group=g)
            context['slider_id'] = uuid.uuid4()

    context['html_name'] = field.html_name
    context['editable'] = editable
    # print(context['contents'].__dict__)
    return context


"""***NEW***"""


@register.filter
def model_name(obj):
    return obj._meta.model_name


@register.filter
def app_label(obj):
    return obj._meta.app_label

@register.inclusion_tag('comment_tag.html')
def get_comments(obj, comment_form=None, button_text=None, button_style=None, comment_type=None):

    if button_text is None:
        button_text = 'نظر کاربران'
    if button_style is None:
        button_style = "btn btn-primary"
    if comment_type is None:
        comment_type = 'نظرات'
        comment_type_filter = 'O'
    else:
        comment_type_filter = 'C'

    comments = Comments.objects.none()
    if hasattr(obj, '_meta'):
        comments = Comments.objects.filter(object_id=obj.pk,
                                           content_type=ContentType.objects.get_for_model(obj._meta.model),
                                           comment_title=comment_type_filter)

    return {'comments': comments, 'button_text': button_text, 'comment_type': comment_type,
            'button_style': button_style, 'comment_form': comment_form, 'obj': obj}
    # return {'comments': new_comments}


@register.inclusion_tag('core/partial/comment_user_list.html')
def get_comment_user_list(form, current_user, cancel=None, comment_type=None):
    # seen_comment = list()
    unseen_comment = list()

    comments_info = list()
    unseen_comment_count = 0


    # creator_users = set()
    creator_users = dict()
    # obj = form.instance if form else None
    if form:
        obj = form.instance
        comments = obj.comments.all().filter(~Q(comment_title="C")) if obj else None
    else:
        obj = None
        comments = None
    comment_seen = CommentSeen.objects.all()
    if comments is None:
        return {}
    for comment in comments:
        try:
            # creator_users.add(comment.creator_user.profile.get_user_image)
            if comment_seen.filter(creator_user=current_user, comment=comment, editor_user=current_user).exists():
                comment.seen = True
                creator_users[comment.creator_user] = comment.creator_user.profile.get_user_image
                # seen_comment.append(comment)
                comments_info.append([comment,
                                     comment.creator_user,
                                     comment.creator_user.profile.get_user_image])


            if not comment_seen.filter(creator_user=current_user, comment=comment, editor_user=current_user).exists():
                comment.seen = False
                comments_info.append([comment,
                                      comment.creator_user,
                                      comment.creator_user.profile.get_user_image])
                creator_users[comment.creator_user] = comment.creator_user.profile.get_user_image
                unseen_comment.append(comment)
                unseen_comment_count += 1
        except Exception as e:
            creator_users[comment.creator_user] = '/assets/media/auth/no_image.png'

        if comments_info:
            comments_info.reverse()

    context = {'comments_info': comments_info,
               'obj': obj,
               'unseen_comment_count': unseen_comment_count,
               'cancel': cancel,
               'user': current_user,
               'comment_type': comment_type if comment_type else 'comment'}
    return context
@register.filter
def get_comment_link(comment_str):
    import re
    from django.urls import reverse_lazy
    from django.utils.safestring import mark_safe
    pattern_sku = r'sku_\d+'
    pattern_pk = r'sku_(\d+)'

    comment_str_lower = comment_str.lower()
    pks = re.findall(pattern_pk, comment_str, flags=re.IGNORECASE)
    for pk in pks:
        url = reverse_lazy('extra_data:sku.update', kwargs={'pk': pk})
        link = f'<a href="{url.__str__()}" target=_blank>{pk}</a>'
        comment_str = re.sub(pattern_sku, link, comment_str, count=1, flags=re.IGNORECASE)
        comment_str = mark_safe(comment_str)

    return comment_str

"""***NEW***"""

"""***NEW***"""
@register.inclusion_tag('addition_tag.html')
def get_additions(obj):
    from additions.models import Additions
    addition = Additions.objects.none()
    if hasattr(obj, '_meta'):
        addition = Additions.objects.filter(object_id=obj.pk,
                                            contenttype=ContentType.objects.get_for_model(obj._meta))

    return {'addition': addition}

"""***NEW***"""


@register.inclusion_tag('micmod-base/quotation/partial/inquiry_report_filter.html')
def get_inquiry_report():
    from micmod_base.models import QuotationItem
    qi_filter = QuotationItem.get_inquiry_report()

    return {'quotationitem_filters': qi_filter}


@register.simple_tag()
def inquiry_not_started(user):
    from micmod_base.models import QuotationItem
    return QuotationItem.inquiry_not_started(user)



@register.inclusion_tag('core/partial/render_field.html')
def render_field(field, crispy=None):
    context = {'field': field, 'crispy': crispy}
    return context


@register.inclusion_tag('core/partial/render_field_by_order.html')
def render_field_by_order(form, *fields, crispy=None, margin_b=None, html_tag=None, label=None,
                          label_text=None, disable=None, no_input=None, css=None, id=None, title=None):
    if form and crispy is None:
        crispy = getattr(form, 'crispy', None)
    context = {'form': form, 'fields': fields, 'crispy': crispy,
               'html_tag': html_tag, 'margin_b': margin_b,
               'label': label, 'label_text': label_text, 'disable': disable,
               'no_input': no_input, 'css': css, 'id': id,'title': title
               }
    return context

@register.inclusion_tag('core/partial/render_field_group.html')
def render_field_group(*fields, title='', label_type=None, attrs='', classes='',
                       field_attrs='', field_classes='', label_classes='', cols=None):
    attrs_split = field_attrs.split(" ") if field_attrs else []
    if not cols:
        cols = len(fields)
    for field in fields:
        if field.field:
            field.field.widget.attrs['class'] += f' {field_classes}'
            for attr in attrs_split:
                values = attr.split("=")
                field.field.widget.attrs[values[0]] = values[1] if len(values) > 1 else values[0]
    context = {'fields': fields, 'title': title,
               'label_type': label_type, 'attrs': attrs,
               'classes': classes, 'fields_attr': field_attrs, 'fields_classes': field_classes,
               'cols': cols,'label_classes':label_classes}
    return context


@register.inclusion_tag('core/partial/render_field_by_order_for_quotation.html')
def render_field_by_order_for_quotation(form, *fields, crispy=None, html_tag=None):
    if form and not crispy:
        crispy = form.crispy
    context = {'form': form, 'fields': fields, 'crispy': crispy, 'html_tag': html_tag}
    return context


@register.inclusion_tag('core/partial/render_field_by_order_v2.html')
def render_field_by_order_v2(form, parent_template_col_num, template_col_num, inner_template_col_num, crispy=None):
    template_col_num = template_col_num.split(',')
    inner_template_col_num = inner_template_col_num.split(',')
    context = {'form': form, 'template_col_num': template_col_num,
               'parent_template_col_num': parent_template_col_num,
               'inner_template_col_num': inner_template_col_num, 'crispy': crispy}
    print("==============", form)
    return context


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def remove_n_index(iterable_obj, idx):
    if len(iterable_obj) > 1:
        return iterable_obj[idx:]
    return ''


@register.filter
def remove_question_mark(string: str):
    x = remove_n_index(string, 1)
    idx = x.find('&')
    return x[idx+1:]


@register.inclusion_tag('changelog/partial/compare_log.html')
def compare_log(log):
    context = {'log': log,}
    return context


@register.filter
def get_list_item(lst, position):
    try:
        position = int(position)
        return lst[position]
    except Exception as e:
        pass

@register.filter
def field_name(obj, model):
    print(obj, model._meta)
    return 'salam'


@register.inclusion_tag('dw/partial/show_order_list_detail.html')
def show_order_list_detail(obj, model):
    from translator import get_text as _
    context = {'data': {}}
    fields = [f.name for f in model._meta.get_fields() if f.concrete]
    for field in fields:
        context['data'].update({_(field): getattr(obj, field, None)})
    return context


@register.filter
def is_select2(field):
    return getattr(field, 'select2', None)


@register.filter
def mul(a, b):
    try:
        return (a or 0) * (b or 0)
    except Exception as e:
        print('error ', __file__, e.__traceback__.tb_lineno, e)


@register.filter
def get_field_name(field):
    """
    Returns name for a field.
    """
    try:
        if getattr(field, '__dict__', None):
            return field.__dict__.get('name')
    except Exception as e:
        print(show_error(e, __file__))
        return None


from django.db.models import ForeignKey, Q


@register.simple_tag
def get_fk_model(model, fieldname):
    """Returns None if not foreignkey, otherswise the relevant model"""
    field_object, model, direct, m2m = model._meta.get_field_by_name(fieldname)
    if not m2m and direct and isinstance(field_object, ForeignKey):
        return field_object.rel.to
    return None


@register.simple_tag
def get_inquiry_result_description(quotation_item):
    from inquiry.models import PriceInquiryResult
    inquiry_result = PriceInquiryResult.objects.filter(sku=quotation_item.goods_code, active=True)
    try:
        return ''.join([f'({iqr.inquiry_type}: {iqr.description})' for iqr in inquiry_result if 'خارج' not in iqr.inquiry_type.title])
    except Exception as e:
        return ''


@register.simple_tag
def item_count(page_obj):
    per_page = page_obj.paginator.per_page
    return page_obj.number * per_page - (per_page - len(page_obj.object_list))

@register.simple_tag
def num_to_fa_words(num):
    return words(num)


@register.simple_tag
def parent_code_data(goods_code):
    item = Item.objects.filter(sku=goods_code).first()
    return item.parent if item else None


@register.inclusion_tag('micmod-base/quotation/partial/quotation_item_all_prices.html')
def get_quotation_item_all_prices(sku):
    context = dict()
    item_sku = Item.objects.filter(sku=sku).first()
    if not item_sku:
        return

    all_trade_active_prices = item_sku.all_trade_active_price_
    all_bazar_active_prices = item_sku.all_bazar_active_price_

    context['all_trade_prices'] = all_trade_active_prices
    context['all_bazar_prices'] = all_bazar_active_prices
    return context