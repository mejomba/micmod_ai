from typing import Optional
import jdatetime
import requests


# f'{protocol}://{host}:{port}/sepidar_api/itemstocksummary?itemref=5550&fiscalyearref__title=1403'
class SepidarApiCall:
    protocol = 'http'
    host = '192.168.1.80'
    port = '3030'
    token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzM0NTMxOTA5LCJpYXQiOjE3MzM2Njc5MDksImp0aSI6IjFlODI2ZWM0ZDRiMTRhNTE4YTBlYmFmZDU1YzA5OGJhIiwidXNlcl9pZCI6MSwidXNlcm5hbWUiOiJhbGkifQ.Vl1zCHSXem_lkYomG8ObovrqiDO8dS9sdIwkD6eg6jI'
    headers = {
        "Authorization": f"Bearer {token}"
    }
    endpoints = {
        'login': f'{protocol}://{host}:{port}/api_log/token/',
        'stock_quantity': f'{protocol}://{host}:{port}/sepidar_api/itemstocksummary/',
    }

    @classmethod
    def get_token(cls):
        url = cls.endpoints.get('login')
        data = {'username': 'ali', 'password': '123456'}
        res = requests.post(url, data=data)
        if res.ok:
            res = res.json()
            return res
        else:
            return {}

    @classmethod
    def get_stock_quantity(cls, itemref, year: Optional[str] = None, *args, **kwargs):
        if year is None:
            year = jdatetime.date.today().year
        endpoint = cls.endpoints.get('stock_quantity')
        endpoint += f'?itemref={itemref[0]}&fiscalyearref__title={str(year)}'
        res = requests.get(endpoint, headers=cls.headers)
        out = dict()
        if res.ok:
            response = res.json()
            r = {item.get('stockref_str'): item.get('quantity') for item in response.get('results') if float(item.get('quantity')) > 0}
            out['res'] = r

        return out
