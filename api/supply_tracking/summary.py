from collections import defaultdict

from django.db.models import Q, Sum
from django.urls import reverse

from factor.models import FactorItem, FactorItemSupplyLocation
from micmod_base.models import CustomerRequestItem, QuotationItem
from order.models import GIOItem, Order, PackingItem

from .constants import STATUS_TITLES
from .services import DeliveryEstimator, TrackingStatusResolver, iso, status


class TrackingSummaryQueryService:
    """
    Bulk-only summary builder.

    This service intentionally does not construct the detail tree. Query count
    is bounded by the number of relation types, not by the number of tracking
    rows in the requested page.
    """

    def __init__(self, status_resolver=None, delivery_estimator=None):
        self.status = status_resolver or TrackingStatusResolver()
        self.delivery = delivery_estimator or DeliveryEstimator()

    def build(self, candidates):
        candidates = list(candidates)
        if not candidates:
            return []

        root_ids = defaultdict(list)
        for candidate in candidates:
            root_ids[candidate.source_type].append(candidate.source_id)

        cris = {
            obj.pk: obj
            for obj in CustomerRequestItem.objects.filter(pk__in=root_ids["cri"])
            .select_related("cr__customer")
        }

        root_qis = {
            obj.pk: obj
            for obj in self._qi_queryset().filter(pk__in=root_ids["qi"])
        }

        root_fis = {
            obj.pk: obj
            for obj in self._fi_queryset().filter(pk__in=root_ids["fi"])
        }

        root_orders = {
            obj.pk: obj
            for obj in self._order_queryset().filter(pk__in=root_ids["order"])
        }

        cri_ids = set(cris)
        qi_rows = list(
            self._qi_queryset().filter(customer_request_item_id__in=cri_ids)
        )
        qis = {**root_qis, **{obj.pk: obj for obj in qi_rows}}
        qis_by_cri = defaultdict(list)
        for qi in qi_rows:
            qis_by_cri[qi.customer_request_item_id].append(qi)

        qi_ids = set(qis)
        fi_rows = list(
            self._fi_queryset().filter(
                Q(qi_id__in=qi_ids)
                | Q(
                    customer_request_item_id__in=cri_ids,
                    qi__isnull=True,
                )
            ).distinct()
        )
        fis = {**root_fis, **{obj.pk: obj for obj in fi_rows}}
        fis_by_qi = defaultdict(list)
        fis_by_cri = defaultdict(list)
        for fi in fi_rows:
            if fi.qi_id:
                fis_by_qi[fi.qi_id].append(fi)
            elif fi.customer_request_item_id:
                fis_by_cri[fi.customer_request_item_id].append(fi)

        fi_ids = set(fis)
        locations = list(
            FactorItemSupplyLocation.objects
            .filter(fi_id__in=fi_ids)
            .select_related(
                "order",
                "order__last_work_flow",
                "order__item",
                "order__item_trade",
                "order_bazar",
                "order_bazar__item",
                "wh_reserve",
                "wh_reserve__item",
            )
        )
        locations_by_fi = defaultdict(list)
        linked_order_ids = set()
        for location in locations:
            locations_by_fi[location.fi_id].append(location)
            if location.order_id:
                linked_order_ids.add(location.order_id)

        legacy_order_ids = {
            fi.supply_locations_id
            for fi in fis.values()
            if fi.supply_locations_id
        }
        linked_order_ids.update(legacy_order_ids)

        direct_order_rows = list(
            self._order_queryset().filter(
                Q(qi_id__in=qi_ids)
                | Q(
                    customer_request_item_id__in=cri_ids,
                    qi__isnull=True,
                )
            ).exclude(pk__in=linked_order_ids).distinct()
        )
        direct_orders_by_qi = defaultdict(list)
        direct_orders_by_cri = defaultdict(list)
        for order in direct_order_rows:
            if order.qi_id:
                direct_orders_by_qi[order.qi_id].append(order)
            elif order.customer_request_item_id:
                direct_orders_by_cri[order.customer_request_item_id].append(order)

        all_orders = {**root_orders}
        for location in locations:
            if location.order_id:
                all_orders[location.order_id] = location.order
        for fi in fis.values():
            if fi.supply_locations_id:
                all_orders[fi.supply_locations_id] = fi.supply_locations
        for order in direct_order_rows:
            all_orders[order.pk] = order

        order_ids = set(all_orders)
        gio_qty = {
            row["order_id"]: row["total"]
            for row in (
                GIOItem.objects.filter(order_id__in=order_ids)
                .values("order_id")
                .annotate(total=Sum("quantity"))
            )
        }

        packing_rows = list(
            PackingItem.objects.filter(order_id__in=order_ids)
            .values(
                "order_id",
                "quantity",
                "packing_id",
                "packing__departure_date",
                "packing__last_work_flow__current_state_name",
            )
        )
        packing_by_order = defaultdict(list)
        for row in packing_rows:
            packing_by_order[row["order_id"]].append(row)

        context = {
            "cris": cris,
            "qis": qis,
            "fis": fis,
            "orders": all_orders,
            "qis_by_cri": qis_by_cri,
            "fis_by_qi": fis_by_qi,
            "fis_by_cri": fis_by_cri,
            "locations_by_fi": locations_by_fi,
            "direct_orders_by_qi": direct_orders_by_qi,
            "direct_orders_by_cri": direct_orders_by_cri,
            "gio_qty": gio_qty,
            "packing_by_order": packing_by_order,
        }

        return [self._build_candidate(candidate, context) for candidate in candidates]

    @staticmethod
    def _qi_queryset():
        return QuotationItem.objects.select_related(
            "quotation",
            "quotation__customer_party_id",
            "quotation__last_work_flow",
            "goods_code_fk",
        )

    @staticmethod
    def _fi_queryset():
        return FactorItem.objects.select_related(
            "factor",
            "factor__customer_party_id",
            "factor__q",
            "factor__q__customer_party_id",
            "factor__last_work_flow",
            "goods_code",
            "qi",
            "supply_locations",
            "supply_locations__last_work_flow",
            "supply_locations__item",
            "supply_locations__item_trade",
        )

    @staticmethod
    def _order_queryset():
        return Order.objects.select_related(
            "customer_party_id",
            "last_work_flow",
            "item",
            "item_trade",
            "qi",
        )

    def _build_candidate(self, candidate, ctx):
        if candidate.source_type == "cri":
            root = ctx["cris"].get(candidate.source_id)
            if not root:
                return None
            return self._summary_for_cri(root, ctx)

        if candidate.source_type == "qi":
            root = ctx["qis"].get(candidate.source_id)
            if not root:
                return None
            return self._summary_for_qi(root, ctx)

        if candidate.source_type == "fi":
            root = ctx["fis"].get(candidate.source_id)
            if not root:
                return None
            return self._summary_for_fi(root, ctx)

        root = ctx["orders"].get(candidate.source_id)
        if not root:
            return None
        return self._summary_for_order(root, ctx)

    def _summary_for_cri(self, cri, ctx):
        qis = ctx["qis_by_cri"].get(cri.pk, [])
        fis = list(ctx["fis_by_cri"].get(cri.pk, []))
        orders = list(ctx["direct_orders_by_cri"].get(cri.pk, []))
        for qi in qis:
            fis.extend(ctx["fis_by_qi"].get(qi.pk, []))
            orders.extend(ctx["direct_orders_by_qi"].get(qi.pk, []))

        return self._assemble_summary(
            tracking_id=f"cri:{cri.pk}",
            origin_type="REQUEST",
            origin_id=cri.pk,
            customer=cri.cr.customer,
            item={
                "id": None,
                "sku": cri.customer_sku,
                "part_number": cri.customer_part_number,
            },
            quantity=cri.quantity,
            request_id=cri.pk,
            quotation=qis[0] if qis else None,
            factor_item=fis[0] if fis else None,
            root_status=status("UNDER_REVIEW"),
            root_delivery=self.delivery.estimate(),
            fis=fis,
            direct_orders=orders,
            ctx=ctx,
        )

    def _summary_for_qi(self, qi, ctx):
        fis = list(ctx["fis_by_qi"].get(qi.pk, []))
        orders = list(ctx["direct_orders_by_qi"].get(qi.pk, []))
        return self._assemble_summary(
            tracking_id=f"qi:{qi.pk}",
            origin_type="QUOTATION",
            origin_id=qi.pk,
            customer=qi.quotation.customer_party_id,
            item=self._item(qi.goods_code_fk, qi.goods_code, qi.customer_goods_code),
            quantity=qi.quantity,
            request_id=qi.customer_request_item_id,
            quotation=qi,
            factor_item=fis[0] if fis else None,
            root_status=self.status.quotation(qi.quotation),
            root_delivery=self.delivery.estimate(
                qi.supply_date,
                qi.delivery_time or qi.quotation.delivery_time,
            ),
            fis=fis,
            direct_orders=orders,
            ctx=ctx,
        )

    def _summary_for_fi(self, fi, ctx):
        factor = fi.factor
        customer = factor.customer_party_id or (
            factor.q.customer_party_id if factor.q_id else None
        )
        return self._assemble_summary(
            tracking_id=f"fi:{fi.pk}",
            origin_type="FACTOR",
            origin_id=fi.pk,
            customer=customer,
            item=self._item(fi.goods_code, None, fi.part_number_show),
            quantity=fi.quantity,
            request_id=fi.customer_request_item_id,
            quotation=fi.qi,
            factor_item=fi,
            root_status=self.status.factor(factor),
            root_delivery=self.delivery.estimate(
                getattr(fi.qi, "supply_date", None) if fi.qi_id else None,
                fi.delivery_time or factor.delivery_time,
            ),
            fis=[fi],
            direct_orders=[],
            ctx=ctx,
        )

    def _summary_for_order(self, order, ctx):
        breakdown = self._order_breakdown(order, order.final_quantity, ctx)
        return {
            "tracking_id": f"order:{order.pk}",
            "customer": self._customer(order.customer_party_id),
            "origin": {
                "type": "ORDER",
                "id": order.pk,
                "number": order.order_number or order.pk,
            },
            "item": self._item(order.final_item),
            "quantity": order.final_quantity,
            "pricing": self._empty_pricing(),
            "delivery": self.delivery.estimate(order.commitment_date_to_customer),
            "supply": {
                "types": [{
                    "type": self._supply_type(order),
                    "quantity": float(order.final_quantity or 0),
                }]
            },
            "transportation": {
                "methods": [order.transportation_method] if order.transportation_method else []
            },
            "documents": {
                "request": (
                    {"id": order.customer_request_item_id}
                    if order.customer_request_item_id else None
                ),
                "quotation": (
                    self._quotation_document(order.qi)
                    if order.qi_id else None
                ),
                "factor": None,
            },
            "statuses": breakdown,
            "is_partial": len(breakdown) > 1,
        }

    def _assemble_summary(
        self,
        *,
        tracking_id,
        origin_type,
        origin_id,
        customer,
        item,
        quantity,
        request_id,
        quotation,
        factor_item,
        root_status,
        root_delivery,
        fis,
        direct_orders,
        ctx,
    ):
        statuses = []
        supply = defaultdict(float)
        methods = set()
        has_supply_children = False

        for fi in self._unique(fis):
            locations = ctx["locations_by_fi"].get(fi.pk, [])
            if locations:
                has_supply_children = True
                for location in locations:
                    if location.wh_reserve_id:
                        qty = float(location.quantity or 0)
                        statuses.append({**status("WAREHOUSE_STOCK"), "quantity": qty})
                        supply["WAREHOUSE"] += qty
                    elif location.order_bazar_id:
                        qty = float(location.quantity or 0)
                        code = "AVAILABLE" if location.order_bazar.receipt_in_wh else "DOMESTIC_SUPPLY"
                        statuses.append({**status(code), "quantity": qty})
                        supply["DOMESTIC"] += qty
                    elif location.order_id:
                        qty = float(location.quantity or 0)
                        statuses.extend(self._order_breakdown(location.order, qty, ctx))
                        supply[self._supply_type(location.order)] += qty
                        if location.order.transportation_method:
                            methods.add(location.order.transportation_method)
            elif fi.supply_locations_id:
                has_supply_children = True
                order = fi.supply_locations
                qty = float(fi.quantity or 0)
                statuses.extend(self._order_breakdown(order, qty, ctx))
                supply[self._supply_type(order)] += qty
                if order.transportation_method:
                    methods.add(order.transportation_method)

        for order in self._unique(direct_orders):
            has_supply_children = True
            qty = float(order.final_quantity or 0)
            statuses.extend(self._order_breakdown(order, qty, ctx))
            supply[self._supply_type(order)] += qty
            if order.transportation_method:
                methods.add(order.transportation_method)

        factor = factor_item.factor if factor_item else None
        if not has_supply_children:
            effective_status = self.status.factor(factor) if factor else root_status
            statuses = [{**effective_status, "quantity": float(quantity or 0)}]

        grouped_statuses = self._group_statuses(statuses)

        pricing = (
            self._factor_pricing(factor_item)
            if factor_item
            else self._quotation_pricing(quotation)
            if quotation
            else self._empty_pricing()
        )
        delivery = (
            self.delivery.estimate(
                getattr(factor_item.qi, "supply_date", None)
                if factor_item and factor_item.qi_id else None,
                factor_item.delivery_time or factor.delivery_time,
            )
            if factor_item
            else root_delivery
        )

        return {
            "tracking_id": tracking_id,
            "customer": self._customer(customer),
            "origin": {
                "type": origin_type,
                "id": origin_id,
                "number": (
                    factor.sepidar_number or factor.pk
                    if factor
                    else quotation.quotation.sepidar_number or quotation.quotation.pk
                    if quotation
                    else origin_id
                ),
            },
            "item": item,
            "quantity": quantity,
            "pricing": pricing,
            "delivery": delivery,
            "supply": {
                "types": [
                    {"type": key, "quantity": value}
                    for key, value in sorted(supply.items())
                ]
            },
            "transportation": {"methods": sorted(methods)},
            "documents": {
                "request": {"id": request_id} if request_id else None,
                "quotation": self._quotation_document(quotation),
                "factor": self._factor_document(factor),
            },
            "statuses": grouped_statuses,
            "is_partial": len(grouped_statuses) > 1,
        }

    def _order_breakdown(self, order, quantity, ctx):
        total = float(quantity or 0)
        if total <= 0:
            return []

        if order.cancel or order.sales_admin_cancel:
            return [{**status("CANCELED"), "quantity": total}]
        if order.receipt_in_wh:
            return [{**status("AVAILABLE"), "quantity": total}]
        if order.is_wh:
            return [{**status("WAREHOUSE_STOCK"), "quantity": total}]
        if order.is_bazar:
            return [{**status("DOMESTIC_SUPPLY"), "quantity": total}]

        packed = defaultdict(float)
        packed_total = 0.0
        remaining_for_packings = total
        for row in ctx["packing_by_order"].get(order.pk, []):
            code = self._packing_code(row)
            if not code:
                continue
            qty = min(float(row["quantity"] or 0), remaining_for_packings)
            if qty <= 0:
                continue
            packed[code] += qty
            packed_total += qty
            remaining_for_packings -= qty

        remaining_after_packing = max(total - packed_total, 0.0)
        gio_total = min(
            float(ctx["gio_qty"].get(order.pk) or 0),
            remaining_after_packing,
        )
        remaining = max(total - packed_total - gio_total, 0.0)

        rows = [
            {**status(code), "quantity": qty}
            for code, qty in packed.items()
            if qty
        ]
        if gio_total:
            rows.append({**status("CHINA_WAREHOUSE"), "quantity": gio_total})
        if remaining:
            base = self.status.order(order, packing_nodes=[], has_gio=False)
            rows.append({
                "code": base["code"],
                "title": base["title"],
                "quantity": remaining,
            })
        return self._group_statuses(rows)

    @staticmethod
    def _packing_code(row):
        state_name = row["packing__last_work_flow__current_state_name"]
        if state_name == "انبار":
            return "AVAILABLE"
        if state_name in {"اظهار گمرکی", "ترخیص گمرک"}:
            return "CUSTOMS"
        if state_name in {"DEP", "arrive", "10%", "تحویل اسناد"} or row["packing__departure_date"]:
            return "SHIPPED"
        return None

    @staticmethod
    def _group_statuses(rows):
        grouped = {}
        for row in rows:
            code = row["code"]
            if code not in grouped:
                grouped[code] = {
                    "code": code,
                    "title": row.get("title") or STATUS_TITLES.get(code, code),
                    "quantity": 0.0,
                }
            grouped[code]["quantity"] += float(row.get("quantity") or 0)
        return list(grouped.values())

    @staticmethod
    def _unique(objects):
        seen = set()
        result = []
        for obj in objects:
            if obj.pk in seen:
                continue
            seen.add(obj.pk)
            result.append(obj)
        return result

    def _factor_pricing(self, fi):
        if not fi:
            return self._empty_pricing()
        return {
            "agreed_amount": fi.total_price_after_discount,
            "unit_price": fi.price,
            "discount_per_item": fi.total_discount_per_item,
            "unit_price_after_discount": fi.fee_after_discount,
            "prepayment": {
                "has_pre_payment": bool(getattr(fi.qi, "pre_paid_amount", None)) if fi.qi_id else False,
                "amount": getattr(fi.qi, "pre_paid_amount", None) if fi.qi_id else None,
            },
        }

    def _quotation_pricing(self, qi):
        if not qi:
            return self._empty_pricing()
        unit = qi.final_price
        discount = qi.discount_per_item or 0
        after_discount = (unit - discount) if unit is not None else None
        amount = qi.final_amount
        if amount is None and after_discount is not None and qi.quantity is not None:
            amount = after_discount * qi.quantity
        return {
            "agreed_amount": amount,
            "unit_price": unit,
            "discount_per_item": discount,
            "unit_price_after_discount": after_discount,
            "prepayment": {
                "has_pre_payment": bool(qi.pre_paid_amount or qi.quotation.prepayment),
                "amount": qi.pre_paid_amount if qi.pre_paid_amount is not None else qi.quotation.prepayment,
            },
        }

    @staticmethod
    def _quotation_document(qi):
        if not qi:
            return None
        q = qi.quotation
        return {
            "id": q.pk,
            "number": q.sepidar_number or q.pk,
            "portal_url": reverse("micmod_base:quotations.view", kwargs={"pk": q.pk}),
        }

    def _factor_document(self, factor):
        if not factor:
            return None
        return {
            "id": factor.pk,
            "number": factor.sepidar_number or factor.pk,
            "document_type": self.status.factor_document(factor),
            "portal_url": reverse("factor:factor.view", kwargs={"pk": factor.pk}),
        }

    @staticmethod
    def _customer(customer):
        if not customer:
            return None
        return {
            "id": customer.pk,
            "title": customer.title,
            "shop_id": customer.shop_id,
        }

    @staticmethod
    def _item(item, fallback_sku=None, fallback_part=None):
        if not item:
            return {
                "id": None,
                "sku": fallback_sku,
                "part_number": fallback_part,
            }
        return {
            "id": item.pk,
            "sku": getattr(item, "sku", fallback_sku),
            "part_number": getattr(item, "part_number", fallback_part),
        }

    @staticmethod
    def _supply_type(order):
        if order.is_wh:
            return "WAREHOUSE"
        if order.is_bazar:
            return "DOMESTIC"
        return "FOREIGN"

    @staticmethod
    def _empty_pricing():
        return {
            "agreed_amount": None,
            "unit_price": None,
            "discount_per_item": None,
            "unit_price_after_discount": None,
            "prepayment": {
                "has_pre_payment": False,
                "amount": None,
            },
        }
