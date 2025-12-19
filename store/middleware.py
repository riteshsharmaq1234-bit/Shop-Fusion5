from django.contrib.auth.models import User
from django.utils.functional import SimpleLazyObject

from django.shortcuts import redirect


class ShopFusionAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.shop_user = SimpleLazyObject(lambda: self.__get_shop_user(request))
        response = self.get_response(request)
        return response

    def __get_shop_user(self, request):
        if 'shop_user_id' in request.session:
            try:
                return User.objects.using('default').get(pk=request.session['shop_user_id'])
            except User.DoesNotExist:
                pass
        return None


class AdminRestrictMiddleware:
    """Redirect authenticated non-staff users away from the Django admin.

    - If a request path starts with `/admin/` and the requesting user is
      authenticated but not `is_staff` (or `is_superuser`), redirect them
      to the site `home` view.
    - Anonymous users (not logged in) and staff/superusers can proceed.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''
        # Allow admin auth endpoints so superusers can reach the login page
        admin_auth_paths = ('/admin/login/', '/admin/logout/', '/admin/password_change/', '/admin/password_reset/')
        if path.startswith('/admin/'):
            # If this request is for the admin login/logout/password endpoints, allow it.
            for p in admin_auth_paths:
                if path.startswith(p):
                    return self.get_response(request)
            user = getattr(request, 'user', None)
            shop_user = getattr(request, 'shop_user', None)

            def _is_privileged(u):
                try:
                    return bool(u and (getattr(u, 'is_staff', False) or getattr(u, 'is_superuser', False)))
                except Exception:
                    return False

            # If Django user is authenticated but not privileged, block access.
            if user and getattr(user, 'is_authenticated', False):
                if not _is_privileged(user):
                    return redirect('home')

            # If there is a separate shop_user session (custom auth) and no privileged user,
            # prevent that shop user from accessing the admin as well.
            elif shop_user:
                if not _is_privileged(shop_user):
                    return redirect('home')
        return self.get_response(request)


class AdminSessionPreserveMiddleware:
    """Preserve shop-specific session keys across admin login/logout.

    The Django admin login/logout flow may call `logout()` which flushes
    the session. If a shop user is stored in the session under keys like
    `shop_user_id` we want to preserve those values so admin actions do
    not accidentally sign out the storefront user.

    This middleware stashes configured shop session keys before the
    view runs and restores them afterwards if they were removed.
    """
    PRESERVE_KEYS = ('shop_user_id', 'shop_user_authenticated')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only care about admin login/logout paths.
        path = request.path or ''
        stash = {}
        if path.startswith('/admin/'):
            session = getattr(request, 'session', None)
            if session is not None:
                for k in self.PRESERVE_KEYS:
                    if k in session:
                        stash[k] = session.get(k)

        # Run the view (which may flush/modify the session)
        response = self.get_response(request)

        # After view, restore any stashed shop session keys if missing.
        if stash:
            session = getattr(request, 'session', None)
            if session is not None:
                changed = False
                for k, v in stash.items():
                    if k not in session or session.get(k) != v:
                        session[k] = v
                        changed = True
                if changed:
                    try:
                        session.save()
                    except Exception:
                        # best-effort: if saving fails, continue
                        pass

        return response
