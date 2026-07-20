import time
import logging

from django.http import HttpResponseForbidden
import ipaddress
import zlib

logger = logging.getLogger(__name__)


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = (time.time() - start_time)

        logger.debug(f"special log for response time: {request.method} {request.path} - {duration:.2f} s")

        return response


class InternalIPRestrictionMiddleware:
    ALLOWED_NETWORKS = [
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("127.0.0.1/32"),  # localhost
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        client_ip = self.get_client_ip(request)
        try:
            print(request.user)
        except Exception as e:
            print(e)
        print(client_ip)

        if not self.is_internal_ip(client_ip, request):
            return HttpResponseForbidden("Access denied: External IP not allowed.")

        return self.get_response(request)

    def get_client_ip(self, request):
        """به‌دست آوردن IP واقعی کاربر (در صورت وجود reverse proxy مثل nginx)"""
        print(f"cload: {request.META.get('HTTP_CF_CONNECTING_IP')}")
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        print("x_forwarded_for: ", x_forwarded_for)
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")

        if not ip:
            ip = x_forwarded_for.split(",")[1].strip()

        print('ip: ', ip)
        return ip

    def is_internal_ip(self, ip, request):
        try:
            print(f"rrr: {ip}")
            ip_addr = ipaddress.ip_address(ip)
            print('ip addr ', ip_addr)
            ip_is_valid = any(ip_addr in network for network in self.ALLOWED_NETWORKS)
            if request.user.is_authenticated:
                if request.user.external_access:
                    return True
                elif '172.' in ip:
                    return True
                elif '192.' in ip:
                    return True
                elif '127.0.0' in ip:  # access when run project local
                    return True
                else:
                    return False
                # return ip_is_valid or request.user.external_access
            else:
                return True
        except ValueError:
            return False


class WebSocketCompressMiddleware:
    async def receive(self, app, scope, receive, send):
        async def compressed_send(message):
            if message['type'] == 'websocket.send' and len(message.get('text', '')) > 1000:
                # فشرده‌سازی پیام‌های بزرگ
                compressed = zlib.compress(message['text'].encode())
                message['bytes'] = compressed
                del message['text']
            await send(message)

        return await app(scope, receive, compressed_send)