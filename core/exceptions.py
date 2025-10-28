class StockRefNotFoundError(Exception):
    def __init__(self, message=None):
        if message is None:
            message = "خطا در شناسایی انبار سپیدار"
        super().__init__(message)
