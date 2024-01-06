from base64 import b64encode
from uuid import uuid4

import requests

from sepidar.scripts.Configuration import Configuration
from sepidar.scripts.CryptoHelper import aes_encrypt, aes_decrypt, rsa_encrypt


class DevicesService:
    def __init__(self, config: Configuration, code: str):
        self._config = config
        self._registration_code = code
        self._integration_id = code[0:4]
        self._public_key = ''
        self.DeviceName = ''

    def register(self):
        url = self.get_absolute_url('/api/Devices/Register/')
        aes_key = self._registration_code * 2
        encrypted_data = aes_encrypt(aes_key, self._integration_id)
        data = {
            'Cypher': encrypted_data['cipher'],
            'IV': encrypted_data['iv'],
            'IntegrationID': self._integration_id
        }

        response = requests.post(url, json=data)

        if response.status_code == 200 or response.status_code == 201:
            json = response.json()
            self._public_key = aes_decrypt(aes_key, json['Cypher'], json['IV'])
            self.DeviceName = json['DeviceTitle']
        else:
            raise Exception(response.json()['Message'])

    def get_absolute_url(self, endpoint: str):
        return self._config.get_absolute_url(endpoint)

    def create_headers(self):
        headers = self._config.create_headers()
        headers['IntegrationID'] = self._integration_id
        uuid = uuid4()
        headers['ArbitraryCode'] = uuid.__str__()
        headers['EncArbitraryCode'] = b64encode(rsa_encrypt(self._public_key, uuid.bytes)).decode('utf-8')
        return headers
