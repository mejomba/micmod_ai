# Python 3
from dataclasses import field,dataclass
from typing import Annotated

from Configuration import Configuration
from DevicesService import DevicesService
from ItemsService import ItemsService
from UsersService import UsersService
# from pydantic import BaseModel

BASE_URL = 'http://192.168.1.120:7373/'
GENERATION_VERSION = '1000'
REGISTRATION__CODE = '10044a33'
USERNAME = 'DjangoUser'
PASSWORD = '123'


def main():
    config = Configuration(BASE_URL, GENERATION_VERSION)

    device = DevicesService(config, REGISTRATION__CODE)
    device.register()
    print(f'Device Name: {device.DeviceName}')

    user = UsersService(device)
    user.login(USERNAME, PASSWORD)
    print(f'User Title: {user.UserTitle}')

    item_service = ItemsService(user)
    items = item_service.get_items()
    print('Items:')
    print(items)



class Test:
    def __init__(self,x):
        self.x = x

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self._x = Test.m_setter(int, value,"x")

    @staticmethod
    def m_setter(m_type, value,prop_name=None):
        if isinstance(value,m_type):
            return value
        else:
            raise AttributeError(f"not valid data type {prop_name}: {m_type}")





if __name__ == '__main__':
    main()
    t = Test(x=2134)
    #t.x = 123
    t.x = "12"
    print(t.x)
