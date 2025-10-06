class StockRefNotFoundError(Exception):
    def __init__(self):
        self.message = "خطا در شناسایی انبار سپیدار"
