# Python 3
from Configuration import Configuration
from DevicesService import DevicesService
from ItemsService import ItemsService
from UsersService import UsersService

BASE_URL = 'http://192.168.1.120:7373/'
GENERATION_VERSION = '1000'
REGISTRATION__CODE = '10003b77'
USERNAME = 'DjangoUser'
PASSWORD = '123'

#device._public_key  = b'<RSAKeyValue><Modulus>rbaVb+XL9HQW9UDMzbgFaTQ8D3kG20LWC16GdTGBiluv4YLcl6VSn/c0Gh4CzziQ+CPHHeXfHwJOjorYhuHVJQ==</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>'

def main():
    config = Configuration(BASE_URL, GENERATION_VERSION)
    p = '<RSAKeyValue><Modulus>rbaVb+XL9HQW9UDMzbgFaTQ8D3kG20LWC16GdTGBiluv4YLcl6VSn/c0Gh4CzziQ+CPHHeXfHwJOjorYhuHVJQ==</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>'
    device = DevicesService(config, REGISTRATION__CODE)
    #device.register()
    device._public_key = p.encode('utf-8')
    device.DeviceName = "django app"

    print(f'Device Name: {device.DeviceName}')

    user = UsersService(device)
    user.login(USERNAME, PASSWORD)
    print(f'User Title: {user.UserTitle}')

    item_service = ItemsService(user)
    items = item_service.get_items()
    print('Items:')
    print(items)


if __name__ == '__main__':
    main()
