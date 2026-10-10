from types import SimpleNamespace

from django.test import SimpleTestCase

from api.supply_tracking.services import DeliveryEstimator, TrackingStatusResolver, normalize_phone


class NormalizePhoneTests(SimpleTestCase):
    def test_normalizes_iranian_mobile_variants(self):
        expected = "09123456789"
        self.assertEqual(normalize_phone("09123456789"), expected)
        self.assertEqual(normalize_phone("+989123456789"), expected)
        self.assertEqual(normalize_phone("00989123456789"), expected)
        self.assertEqual(normalize_phone("989123456789"), expected)
        self.assertEqual(normalize_phone("9123456789"), expected)

    def test_normalizes_persian_digits_and_separators(self):
        self.assertEqual(normalize_phone("۰۹۱۲-۳۴۵-۶۷۸۹"), "09123456789")


class DeliveryEstimatorTests(SimpleTestCase):
    def test_placeholder_contract_is_stable(self):
        result = DeliveryEstimator().estimate()
        self.assertEqual(result["health"], "unknown")
        self.assertEqual(result["source"], "not_implemented")
        self.assertIsNone(result["estimated_delivery_date"])


class StatusResolverTests(SimpleTestCase):
    def setUp(self):
        self.resolver = TrackingStatusResolver()

    def test_factor_document_is_supply_order_before_sepidar(self):
        factor = SimpleNamespace(sepidar_id=None)
        self.assertEqual(self.resolver.factor_document(factor)["code"], "SUPPLY_ORDER")

    def test_factor_document_is_factor_after_sepidar(self):
        factor = SimpleNamespace(sepidar_id=123)
        self.assertEqual(self.resolver.factor_document(factor)["code"], "FACTOR")

    def test_quotation_customer_approval_status(self):
        quotation = SimpleNamespace(
            cancel=False,
            last_work_flow=SimpleNamespace(current_state_name="تایید مشتری"),
        )
        self.assertEqual(
            self.resolver.quotation(quotation)["code"],
            "WAITING_CUSTOMER_APPROVAL",
        )

    def test_order_receipt_has_priority(self):
        order = SimpleNamespace(
            cancel=False,
            sales_admin_cancel=False,
            receipt_in_wh=True,
            is_wh=False,
            is_bazar=False,
            last_work_flow=None,
        )
        self.assertEqual(self.resolver.order(order)["code"], "AVAILABLE")


class OrderBreakdownTests(SimpleTestCase):
    def setUp(self):
        self.service = object.__new__(__import__(
            "api.supply_tracking.services",
            fromlist=["SupplyTrackingService"],
        ).SupplyTrackingService)
        self.service.status = TrackingStatusResolver()

    def test_partial_packing_gio_and_purchase_are_separate(self):
        order = SimpleNamespace(
            cancel=False,
            sales_admin_cancel=False,
            receipt_in_wh=False,
            is_wh=False,
            is_bazar=False,
            last_work_flow=SimpleNamespace(current_state_name="تایید تامین کننده"),
        )
        rows = self.service._order_status_breakdown(
            order,
            100,
            [{"quantity": 20}],
            [{"quantity": 30, "status": {"code": "SHIPPED"}}],
        )
        result = {row["code"]: row["quantity"] for row in rows}
        self.assertEqual(result["SHIPPED"], 30)
        self.assertEqual(result["CHINA_WAREHOUSE"], 20)
        self.assertEqual(result["FOREIGN_PURCHASE_CONFIRMED"], 50)

    def test_received_order_is_fully_available(self):
        order = SimpleNamespace(
            cancel=False,
            sales_admin_cancel=False,
            receipt_in_wh=True,
            is_wh=False,
            is_bazar=False,
            last_work_flow=None,
        )
        rows = self.service._order_status_breakdown(order, 80, [], [])
        self.assertEqual(rows, [{"code": "AVAILABLE", "title": "موجود", "quantity": 80.0}])
