from django import template
from django.contrib.auth.models import Permission

register = template.Library()


@register.filter(name='has_group')
def has_group(user, group_name):
    if user.is_superuser:
        return True
    # print(f"{group_name in [gn[0] for gn in user.groups.values_list('name')]}, ({group_name}-{[gn[0] for gn in user.groups.values_list('name')]})")
    return group_name in [gn[0] for gn in user.groups.values_list('name')]

@register.filter(name='has_one_group')
def has_one_group(user, group_names):
    if user.is_superuser:
        return True
    has_group = False
    for group in group_names:
        has_group = has_group or (group in [gn[0] for gn in user.groups.values_list('name')])
    return has_group


@register.filter(name='has_groups')
def has_groups(user, group_names):
    if user.is_superuser:
        return True
    group_names = group_names.split(',')
    for group_name in group_names:
        if group_name in [gn[0] for gn in user.groups.values_list('name')]:
            return True


@register.filter(name='has_permission')
def has_permission(user, permission):
    try:
        if user.is_superuser:
            return True
        if user.has_perm(permission):
            return True
    except Exception as e:
        print(e)
        return


@register.filter(name='has_one_permission')
def has_one_permission(user, permissions):
    try:
        if user.is_superuser:
            return True
        has_perm = False
        for permission in permissions:
            has_perm = has_perm or user.has_perm(permission)
        return has_perm
    except Exception as e:
        print(e)
        return


@register.filter(name='has_permission_s')
def has_permission_s(user, permissions):
    try:
        if user.is_superuser:
            return True
        perm_list = list(map(lambda x: x.strip(), permissions.split(',')))
        if user.has_perms(perm_list):
            return True
    except Exception as e:
        print(e)
        return


@register.filter(name='has_one_group_or_permission')
def has_one_group_or_permission(user, permission):
    if user.is_superuser:
        return True
    has_perm = False
    for group in permission.get('groups'):
        has_perm = has_perm or (group in [gn[0] for gn in user.groups.values_list('name')])
    for permission_ in permission.get('permissions'):
        has_perm = has_perm or user.has_perm(permission_)
    return has_group
