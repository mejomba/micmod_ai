import time
import logging

from django.http import HttpResponseForbidden
import ipaddress

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

        if not self.is_internal_ip(client_ip, request):
            return HttpResponseForbidden("Access denied: External IP not allowed.")

        return self.get_response(request)

    def get_client_ip(self, request):
        """به‌دست آوردن IP واقعی کاربر (در صورت وجود reverse proxy مثل nginx)"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def is_internal_ip(self, ip, request):
        try:
            ip_addr = ipaddress.ip_address(ip)
            ip_is_valid = any(ip_addr in network for network in self.ALLOWED_NETWORKS)
            if request.user.is_authenticated:
                return ip_is_valid or request.user.external_access
            else:
                return True
        except ValueError:
            return False
