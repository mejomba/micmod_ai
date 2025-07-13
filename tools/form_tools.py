import pandas as pd
from django import forms
from django.db import connections
import importlib

def select_cquery(query, using_db='default'):
    with connections[using_db].cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchall()
        columns = cursor.description
        cursor.close()
        column = []
        for col in columns:
            column.append(col[0])
        df = pd.DataFrame(result, columns=column)
        df.to_html()
        return df

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
    # x = {k: {**v, 'price': v.get("price", 0) + 1)} for k, v in dict2.items()}
    dict_ = dict()
    for key in dict1.keys():
        dict_[key] = dict()
        if key in dict2.keys():
            # dict_[key] = 100 * dict1[key]/dict2[key] -  100
            dict_[key] = {**dict1[key], 'percentage': 100 * dict1[key]['price']/dict2[key]['price'] - 100}
    return dict_

def get_function(function_string):
    mod_name, func_name = function_string.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    func = getattr(mod, func_name)
    return func
