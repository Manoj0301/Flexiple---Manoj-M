class AppError(Exception):
    def __init__(self, code: str, message: str, retryable: bool, status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status = status
