from django import forms

from core.forms import CustomBaseModelForm
from .models import Comments


class CommentsForm(CustomBaseModelForm):
    submit_type = 'save_comment'

    class Meta:
        model = Comments
        fields = ['comment_title', 'comment_content', 'object_id', 'content_type']
        # fields = ['comment_title', 'comment_content']

    def __init__(self, *args, **kwargs):
        super(CommentsForm, self).__init__(*args, **kwargs)
        self.fields['comment_content'].widget.attrs.update({'rows': 3, 'placeholder': 'توضیحات خود را بنویسید :)'})
        self.initial['comment_title'] = 'C'  # initial as cancel
        # self.fields['comment_title'] = forms.ChoiceField(choices=[['C', 'نشون میده'], ['O', 'اینم نشون میده']])
        self.submit_type = self.initial.get('submit_type') or 'save_comment'

        if self.submit_type == 'save_comment':
            self.initial['comment_title'] = 'O'  # initial as other <simple comment>

        self.make_hidden(['object_id', 'content_type'])
