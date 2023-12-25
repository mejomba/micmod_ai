import requests

from CryptoHelper import md5_hash
from DevicesService import DevicesService


class UsersService:
    def __init__(self, device: DevicesService):
        self._device = device
        self._token = ''
        self.UserTitle = ''

    def login(self, username: str, password: str):
        url = self.get_absolute_url('/api/users/login')
        headers = self._device.create_headers()
        data = {
            'UserName': username,
            'PasswordHash': md5_hash(password)
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200 or response.status_code == 201:
            json = response.json()
            self._token = json['Token']
            self.UserTitle = json['Title']
        else:
            raise Exception(response.json()['Message'])

    def logout(self):
        self._token = ''
        self.UserTitle = ''

    def get_absolute_url(self, endpoint: str):
        return self._device.get_absolute_url(endpoint)

    def create_headers(self):
        headers = self._device.create_headers()

        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'

        return headers
