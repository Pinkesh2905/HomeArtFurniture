class NoCacheAuthenticatedMiddleware:
    """
    Middleware to prevent browser and proxy caching (bfcache) of pages
    served to authenticated users.

    Sets Cache-Control: no-store, no-cache, must-revalidate, Pragma: no-cache,
    and Expires: 0 on every response where request.user is authenticated.

    This ensures that when a staff member logs out and clicks the browser's
    'Back' button, the browser makes a fresh request to the server (which redirects
    to the login screen) rather than displaying a stale, cached copy of the
    dashboard or other internal records.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response
