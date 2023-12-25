from django import forms


def get_choice_field(items, selected_item=None):
    field = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}),choices=items)
    # if selected_item:
    # field.initial = selected_item
    return field


def get_obj_from_dict(model, m_dict):
    dict_ = dict()
    for key in model._meta.fields:
        dict_[key] = m_dict.get(key)
    return dict_

def get_dif_percentage(dict1, dict2):
    dict_ = dict()
    for key in dict1.keys():
        if key in dict2.keys():
            dict_[key] = 100 * dict1[key]/dict2[key] -  100
    return dict_
