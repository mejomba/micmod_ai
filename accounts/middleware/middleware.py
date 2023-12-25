class UserRoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_role_list = []
        if request.user.is_authenticated:
            for role in request.user.role.all():
                user_role_list.append(role.get_role_display())

        request.role = user_role_list

        response = self.get_response(request)
        return response
