class AppError(Exception):
    """Base exception for application errors."""

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(self.message)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str = "Resource", id: str = ""):
        super().__init__(f"{resource} not found: {id}" if id else f"{resource} not found")


class ConflictError(AppError):
    """Raises on optimistic locking conflicts (stale version)."""

    def __init__(self, message: str = "Resource was modified by another user"):
        super().__init__(message)


class AuthenticationError(AppError):
    """Raised when credentials are invalid."""

    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message)


class AuthorizationError(AppError):
    """Raised when a user lacks permission for an action."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)
