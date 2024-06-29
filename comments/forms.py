from django import forms

from core.forms import CustomBaseModelForm
from files.models import Image, File
from .models import Comments


class CommentsForm(CustomBaseModelForm):
    submit_type = 'save_comment'
    image_groups = 1
    file_groups = 1
    image_model = Image
    file_model = File
    has_file = True
    has_image = True
    crispy = True

    class Meta:
        model = Comments
        fields = ['comment_title', 'comment_content', 'object_id', 'content_type']
        # fields = ['comment_title', 'comment_content']

    def __init__(self, *args, **kwargs):
        super(CommentsForm, self).__init__(*args, **kwargs)
        self.fields['comment_content'].widget.attrs.update({'rows': 3, 'placeholder': 'توضیحات خود را بنویسید :)'})
        self.fields['comment_title'].widget.attrs.update({'name': "jafar"})
        self.submit_type = self.initial.get('submit_type') or 'save_comment'

        if self.submit_type == 'save_comment':
            self.initial['comment_title'] = 'O'
            self.fields['comment_title'].choices = (
                ('O', 'کامنت ساده'),
            )  # initial as other <simple comment>
        if self.submit_type == 'trade_inquiry':
            self.initial['comment_title'] = 'O'
            self.fields['comment_title'].choices = (
                ('L', 'قیمت کمتر'),
                ('M', 'آیتم جایگزین'),
                ('N', 'زمان تحویل'),
                ('O', 'کامنت ساده'),
            )
        if self.submit_type == 'cancel':
            self.fields['comment_title'].choices = (
                ('C', 'کنسلی'),
                ('D', 'تاخیر در استعلام بازرگانی'),
                ('E', 'تاخیر در استعلام تدارکات داخل'),
                ('F', 'تاخیر در ارسال پیش فاکتور'),
                ('G', 'قیمت بالای استعلام خارج'),
                ('H', 'قیمت بالای استعلام داخل'),
                ('I', 'زمان تحویل استعلام خارج'),
                ('J', 'پیدا نشدن کالای مد نظر مشتری'),
                ('K', 'عدم پاسخگویی مشتری نسبت به سوالات مطرح شده'),
                ('P', 'برآورد قیمت'),
            )
            self.initial['comment_title'] = 'C'  # initial as cancel

        self.make_hidden(['object_id', 'content_type'])
        self.make_optional(['image_1', 'file_1'])
