class ClariQException(Exception):
    """Base exception for ClariQ backend."""
    def __init__(self, message: str = "An internal error occurred", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DatabaseConnectionError(ClariQException):
    """Raised when database connection cannot be established."""
    def __init__(self, message: str = "Database connection failed"):
        super().__init__(message=message, status_code=503)


class EntityNotFoundError(ClariQException):
    """Raised when a requested resource does not exist."""
    def __init__(self, entity_name: str, identifier: str or int):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' was not found",
            status_code=404,
        )


class FileValidationError(ClariQException):
    """Raised when file validation fails (type, size, or extension)."""
    def __init__(self, message: str):
        super().__init__(message=message, status_code=400)
