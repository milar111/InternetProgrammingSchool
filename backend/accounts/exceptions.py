from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, dict) and "errors" not in response.data:
            response.data = {"errors": response.data}
        elif isinstance(response.data, list):
            response.data = {"errors": {"non_field_errors": response.data}}
    return response
