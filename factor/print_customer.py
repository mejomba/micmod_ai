"""Resolve the customer profile shown on a printed factor, without saving it."""


def customer_print_context(customer, selected_index=None):
    buyer = {
        'name': getattr(customer, 'title', None) or '-',
        'address': getattr(customer, 'address', None) or '-',
        'economical_number': getattr(customer, 'national_code', None) or '-',
        'national_number': getattr(customer, 'national_code', None) or '-',
        'postal_code': '-',
        'phone': getattr(customer, 'phone', None) or '-',
        'type': '',
        'is_legal_profile': False,
    }
    profiles = getattr(customer, 'legal_profiles', []) if customer else []
    if not isinstance(profiles, list):
        profiles = []
    options, indexed = [], {}
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict) or not isinstance(profile.get('name'), str):
            continue
        name = profile['name'].strip()
        if not name:
            continue
        key = str(index)
        indexed[key] = profile
        options.append({'value': key, 'label': name, 'selected': key == selected_index})

    if selected_index not in (None, ''):
        if (not isinstance(selected_index, str) or not selected_index.isascii()
                or not selected_index.isdecimal() or selected_index not in indexed):
            raise ValueError('پروفایل حقوقی انتخاب‌شده برای این مشتری معتبر نیست.')
        profile = indexed[selected_index]
        buyer.update({
            'name': profile.get('name') or '-',
            'address': profile.get('address') or '-',
            'economical_number': '-',  # Legal national ID is not an economic number.
            'national_number': profile.get('national_id') or '-',
            'postal_code': profile.get('postal_code') or '-',
            'type': profile.get('type') or '-',
            'is_legal_profile': True,
        })
    return {
        'buyer_info': buyer,
        'legal_profile_options': options,
        'selected_legal_profile': selected_index or None,
    }


def apply_bulk_customer_profiles(documents, selections):
    """Resolve one print-only profile selection per customer across documents.

    Documents contain a print_customer reference to the actual customer.
    Selected indices are validated against that customer's own JSON records.
    """
    groups = {}
    for document in documents:
        customer = document.get('print_customer')
        if customer is None:
            continue
        key = str(customer.pk)
        if key not in groups:
            field_name = 'legal_profile_' + key
            selection = selections.get(field_name)
            context = customer_print_context(customer, selection)
            groups[key] = {
                'key': key,
                'field_name': field_name,
                'name': customer.title or ('مشتری ' + key),
                'options': context['legal_profile_options'],
                'selected': context['selected_legal_profile'],
                'buyer_info': context['buyer_info'],
            }
        group = groups[key]
        document['buyer_info'] = group['buyer_info']
        document['selected_legal_profile'] = group['selected']
        document['legal_profile_options'] = group['options']
    return [group for group in groups.values() if group['options']]
