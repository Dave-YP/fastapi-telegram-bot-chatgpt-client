class StatusMessages:
    LOGIN_REQUIRED = (
        "Please log in to the website and return to the bot "
        "using the provided link."
    )
    SESSION_EXPIRED = (
        "Your session has expired. Please "
        "log in again to the website and return to the bot "
        "using the provided link."
    )
    VALIDATION_ERROR = (
        "Error 422: Invalid request. Please "
        "try again or contact support."
    )
    MESSAGE_LIMIT_REACHED = "Error 451: Daily message limit reached."
    FORBIDDEN = "Error 403: Forbidden. Your region is not supported."
    SERVER_ERROR = (
        "Error 500: Internal server error. "
        "Please try again later."
    )
    UNEXPECTED_ERROR = "Unexpected error: HTTP {status}"
    UNAUTHORIZED = "Unauthorized"

    @staticmethod
    def get_message_limit_text(limit):
        if limit % 10 == 1 and limit % 100 != 11:
            return f"Error 451: Daily limit of {limit} question reached."
        elif limit % 10 in [2, 3, 4] and not (limit % 100 in [12, 13, 14]):
            return f"Error 451: Daily limit of {limit} questions reached."
        else:
            return f"Error 451: Daily limit of {limit} questions reached."
