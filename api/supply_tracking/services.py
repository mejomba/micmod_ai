from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Sum

from extra_data.models import CustomerExpert
from factor.models import FactorItem, FactorItemSupplyLocation
from micmod_base.models import CustomerRequestItem, QuotationItem
from order.models import GIOItem, Order, PackingItem
from workflow.models import WorkFlow

from .constants import (
    DOCUMENT_TITLES,
    FACTOR_PACKING_STATES,
    ORDER_SUPPLIER_CONFIRMED_STATES,
    PACKING_CUSTOMS_STATES,
    PACKING_SHIPPED_STATES,
    STATUS_TITLES,
)


def normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    translation = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    value = str(value).translate(translation).strip()
    for token in (" ", "-", "(", ")"):
        value = value.replace(token, "")

    if value.startswith("0098"):
        value = "0" + value[4:]
    elif value.startswith("+98"):
        value = "0" + value[3:]
    elif value.startswith("98") and len(value) >= 12:
        value = "0" + value[2:]
    elif value.startswith("9") and len(value) == 10:
        value = "0" + value

    return value


def status(code: str, *, raw=None) -> dict:
    out = {"code": code, "title": STATUS_TITLES.get(code, code)}
    if raw is not None:
        out["raw"] = raw
    return out


def iso(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class ShopCustomerScopeResolver:
    @classmethod
    def resolve(cls, mobile: str):
        mobile = normalize_phone(mobile)
        if not mobile:
            return []

        tail = mobile[-10:]
        qs = (
            CustomerExpert.objects
            .filter(access_to_shop_info=True, phone__endswith=tail)
            .select_related("customer")
        )
        customers = []
        seen = set()
        for expert in qs:
            if normalize_phone(expert.phone) != mobile:
                continue
            if expert.customer_id in seen:
                continue
            seen.add(expert.customer_id)
            customers.append(expert.customer)
        return customers


@dataclass(frozen=True)
class TrackingCandidate:
    tracking_id: str
    source_type: str
    source_id: int
    created_at: Optional[datetime]


class DeliveryEstimator:
    """Stable API boundary for the future delivery prediction formula."""

    def estimate(self, commitment_date=None, delivery_time=None) -> dict:
        return {
            "delivery_time": delivery_time,
            "commitment_date": iso(commitment_date),
            "estimated_delivery_date": None,
            "confirmed_delivery_date": None,
            "delay_days": None,
            "health": "unknown",
            "source": "not_implemented",
        }


class TrackingStatusResolver:
    def quotation(self, quotation) -> dict:
        if quotation.cancel:
            return status("CANCELED")
        wf = getattr(quotation, "last_work_flow", None)
        state_name = getattr(wf, "current_state_name", None)
        if state_name == "استعلام قیمت":
            return status("PRICE_INQUIRY", raw={"source": "quotation_workflow", "state": state_name})
        if state_name == "تایید مشتری":
            return status("WAITING_CUSTOMER_APPROVAL", raw={"source": "quotation_workflow", "state": state_name})
        return status("UNDER_REVIEW", raw={"source": "quotation_workflow", "state": state_name})

    def factor_document(self, factor) -> dict:
        code = "FACTOR" if factor.sepidar_id else "SUPPLY_ORDER"
        return {"code": code, "title": DOCUMENT_TITLES[code]}

    def factor(self, factor) -> dict:
        if factor.cancel:
            return status("CANCELED")
        wf = getattr(factor, "last_work_flow", None)
        state_name = getattr(wf, "current_state_name", None)

        if state_name in {"تایید تحویل", "مرحله نهایی"}:
            return status("DELIVERY_CONFIRMED", raw={"source": "factor_workflow", "state": state_name})
        if state_name == "ارسال یا تحویل":
            code = "DELIVERED" if factor.deliver_to_customer else "SENT"
            return status(code, raw={"source": "factor_workflow", "state": state_name})
        if state_name in FACTOR_PACKING_STATES:
            return status("PACKING", raw={"source": "factor_workflow", "state": state_name})
        if (
            state_name == "چک نهایی"
            and factor.need_financial_approval
            and not factor.accounting_confirm
        ):
            return status("WAITING_FINANCIAL_APPROVAL", raw={"source": "factor", "state": state_name})

        code = "FACTOR" if factor.sepidar_id else "SUPPLY_ORDER"
        return status(code, raw={"source": "factor", "state": state_name})

    def packing(self, packing):
        wf = getattr(packing, "last_work_flow", None)
        state_name = getattr(wf, "current_state_name", None)
        if state_name == "انبار":
            return status("AVAILABLE", raw={"source": "packing_workflow", "state": state_name})
        if state_name in PACKING_CUSTOMS_STATES:
            return status("CUSTOMS", raw={"source": "packing_workflow", "state": state_name})
        if state_name in PACKING_SHIPPED_STATES or packing.departure_date:
            return status("SHIPPED", raw={"source": "packing_workflow", "state": state_name})
        return None

    def order(self, order, packing_nodes=None, has_gio=False) -> dict:
        if order.cancel or order.sales_admin_cancel:
            return status("CANCELED")
        if order.receipt_in_wh:
            return status("AVAILABLE", raw={"source": "order", "state": "receipt_in_wh"})

        packing_nodes = packing_nodes or []
        packing_codes = {
            x["status"]["code"]
            for x in packing_nodes
            if x.get("status")
        }
        if "AVAILABLE" in packing_codes:
            return status("AVAILABLE")
        if "CUSTOMS" in packing_codes:
            return status("CUSTOMS")
        if "SHIPPED" in packing_codes:
            return status("SHIPPED")
        if has_gio:
            return status("CHINA_WAREHOUSE")

        if order.is_wh:
            return status("WAREHOUSE_STOCK")
        if order.is_bazar:
            return status("DOMESTIC_SUPPLY")

        wf = getattr(order, "last_work_flow", None)
        state_name = getattr(wf, "current_state_name", None)
        if state_name in ORDER_SUPPLIER_CONFIRMED_STATES:
            return status("FOREIGN_PURCHASE_CONFIRMED", raw={"source": "order_workflow", "state": state_name})
        return status("FOREIGN_SUPPLY", raw={"source": "order_workflow", "state": state_name})


class TrackingDiscoveryService:
    def __init__(self, customers):
        self.customer_ids = [c.pk for c in customers]

    def candidates(self) -> list[TrackingCandidate]:
        if not self.customer_ids:
            return []

        out = []

        cri_qs = (
            CustomerRequestItem.objects
            .filter(cr__customer__pk__in=self.customer_ids)
            .select_related("cr")
        )
        for obj in cri_qs:
            out.append(TrackingCandidate(f"cri:{obj.pk}", "cri", obj.pk, obj.created_date))

        qi_qs = (
            QuotationItem.objects
            .filter(
                quotation__customer_party_id__pk__in=self.customer_ids,
                customer_request_item__isnull=True,
            )
            .select_related("quotation")
        )
        for obj in qi_qs:
            out.append(TrackingCandidate(f"qi:{obj.pk}", "qi", obj.pk, obj.created_date))

        fi_qs = (
            FactorItem.objects
            .filter(
                Q(factor__customer_party_id__pk__in=self.customer_ids)
                | Q(factor__q__customer_party_id__pk__in=self.customer_ids),
                qi__isnull=True,
                customer_request_item__isnull=True,
            )
            .select_related("factor")
            .distinct()
        )
        for obj in fi_qs:
            out.append(TrackingCandidate(f"fi:{obj.pk}", "fi", obj.pk, obj.created_date))

        order_qs = (
            Order.objects
            .filter(
                Q(customer_party_id__pk__in=self.customer_ids)
                | Q(qi__quotation__customer_party_id__pk__in=self.customer_ids)
                | Q(customer_request_item__cr__customer__pk__in=self.customer_ids)
            )
            .filter(qi__isnull=True, customer_request_item__isnull=True)
            .exclude(Q(order_fis__isnull=False) | Q(factor_items__isnull=False))
            .distinct()
        )
        for obj in order_qs:
            out.append(TrackingCandidate(f"order:{obj.pk}", "order", obj.pk, obj.created_date))

        return sorted(out, key=lambda x: iso(x.created_at) or "", reverse=True)


class SupplyTrackingService:
    def __init__(self, mobile: str):
        self.mobile = normalize_phone(mobile)
        self.customers = ShopCustomerScopeResolver.resolve(self.mobile)
        self.customer_ids = [c.pk for c in self.customers]
        self.discovery = TrackingDiscoveryService(self.customers)
        self.status = TrackingStatusResolver()
        self.delivery = DeliveryEstimator()

    def list_summaries(self):
        return [self._summary(self._build_candidate(candidate, include_events=False))
                for candidate in self.discovery.candidates()]

    def get_detail(self, tracking_id: str):
        candidate = next((x for x in self.discovery.candidates() if x.tracking_id == tracking_id), None)
        if not candidate:
            return None
        tree = self._build_candidate(candidate, include_events=True)
        return {
            "tracking_id": tracking_id,
            "summary": self._summary(tree),
            "tree": tree,
            "timeline": self._timeline(tree),
        }

    def _build_candidate(self, candidate: TrackingCandidate, include_events: bool):
        if candidate.source_type == "cri":
            obj = CustomerRequestItem.objects.select_related("cr__customer").get(pk=candidate.source_id)
            return self._request_node(obj, include_events)
        if candidate.source_type == "qi":
            obj = QuotationItem.objects.select_related(
                "quotation__customer_party_id", "goods_code_fk", "customer_request_item"
            ).get(pk=candidate.source_id)
            return self._quotation_node(obj, include_events)
        if candidate.source_type == "fi":
            obj = FactorItem.objects.select_related(
                "factor__customer_party_id", "factor__q__customer_party_id", "goods_code", "qi"
            ).get(pk=candidate.source_id)
            return self._factor_node(obj, include_events)
        obj = Order.objects.select_related(
            "customer_party_id", "item", "item_trade", "qi"
        ).get(pk=candidate.source_id)
        return self._order_node(obj, include_events=include_events)

    def _request_node(self, cri, include_events):
        customer = cri.cr.customer
        node = {
            "id": f"request_item:{cri.pk}",
            "type": "REQUEST",
            "source_id": cri.pk,
            "customer": self._customer(customer),
            "item": {
                "id": None,
                "sku": cri.customer_sku,
                "part_number": cri.customer_part_number,
            },
            "quantity": cri.quantity,
            "status": status("UNDER_REVIEW"),
            "created_at": iso(cri.created_date),
            "pricing": self._empty_pricing(),
            "delivery": self.delivery.estimate(),
            "children": [],
        }

        quotation_items = (
            cri.customer_quotation_items
            .select_related("quotation__customer_party_id", "goods_code_fk")
            .all()
        )
        for qi in quotation_items:
            node["children"].append(self._quotation_node(qi, include_events))

        direct_fis = (
            cri.customer_factor_items
            .filter(qi__isnull=True)
            .select_related("factor__customer_party_id", "factor__q__customer_party_id", "goods_code")
        )
        for fi in direct_fis:
            node["children"].append(self._factor_node(fi, include_events))

        linked_order_ids = FactorItemSupplyLocation.objects.filter(
            fi__customer_request_item=cri
        ).exclude(order__isnull=True).values_list("order_id", flat=True)

        direct_orders = (
            cri.customer_order_items
            .filter(qi__isnull=True)
            .exclude(pk__in=linked_order_ids)
            .select_related("customer_party_id", "item")
        )
        for order in direct_orders:
            node["children"].append(self._order_node(order, include_events=include_events))

        return node

    def _quotation_node(self, qi, include_events):
        q = qi.quotation
        customer = q.customer_party_id
        unit = qi.final_price if qi.final_price is not None else None
        discount = qi.discount_per_item or 0
        after_discount = (unit - discount) if unit is not None else None
        amount = qi.final_amount
        if amount is None and after_discount is not None and qi.quantity is not None:
            amount = after_discount * qi.quantity

        node = {
            "id": f"quotation_item:{qi.pk}",
            "type": "QUOTATION",
            "source_id": qi.pk,
            "document": {
                "id": q.pk,
                "number": q.sepidar_number or q.pk,
            },
            "customer": self._customer(customer),
            "item": self._item(qi.goods_code_fk, fallback_sku=qi.goods_code, fallback_part=qi.customer_goods_code),
            "quantity": qi.quantity,
            "status": self.status.quotation(q),
            "created_at": iso(qi.created_date),
            "pricing": {
                "agreed_amount": amount,
                "unit_price": unit,
                "discount_per_item": discount,
                "unit_price_after_discount": after_discount,
                "prepayment": {
                    "has_pre_payment": bool(qi.pre_paid_amount or q.prepayment),
                    "amount": qi.pre_paid_amount if qi.pre_paid_amount is not None else q.prepayment,
                },
            },
            "delivery": self.delivery.estimate(
                qi.supply_date,
                qi.delivery_time or q.delivery_time,
            ),
            "children": [],
        }
        if include_events:
            node["events"] = self._workflow_events(q, node["id"])

        factor_items = (
            qi.qi
            .select_related("factor__customer_party_id", "factor__q__customer_party_id", "goods_code")
            .all()
        )
        factor_item_ids = list(factor_items.values_list("pk", flat=True))
        for fi in factor_items:
            node["children"].append(self._factor_node(fi, include_events))

        supplied_order_ids = set(
            FactorItemSupplyLocation.objects.filter(fi_id__in=factor_item_ids)
            .exclude(order__isnull=True).values_list("order_id", flat=True)
        )
        supplied_order_ids.update(
            FactorItem.objects.filter(pk__in=factor_item_ids)
            .exclude(supply_locations__isnull=True).values_list("supply_locations_id", flat=True)
        )

        direct_orders = (
            Order.objects
            .filter(qi=qi)
            .exclude(pk__in=supplied_order_ids)
            .select_related("item", "item_trade", "customer_party_id")
        )
        for order in direct_orders:
            node["children"].append(self._order_node(order, include_events=include_events))

        return node

    def _factor_node(self, fi, include_events):
        factor = fi.factor
        customer = factor.customer_party_id or (factor.q.customer_party_id if factor.q_id else None)
        node = {
            "id": f"factor_item:{fi.pk}",
            "type": "FACTOR",
            "source_id": fi.pk,
            "document": {
                "id": factor.pk,
                "number": factor.sepidar_number or factor.pk,
                "document_type": self.status.factor_document(factor),
            },
            "customer": self._customer(customer),
            "item": self._item(fi.goods_code, fallback_part=fi.part_number_show),
            "quantity": fi.quantity,
            "status": self.status.factor(factor),
            "created_at": iso(fi.created_date),
            "pricing": {
                "agreed_amount": fi.total_price_after_discount,
                "unit_price": fi.price,
                "discount_per_item": fi.total_discount_per_item,
                "unit_price_after_discount": fi.fee_after_discount,
                "prepayment": {
                    "has_pre_payment": bool(getattr(fi.qi, "pre_paid_amount", None)) if fi.qi_id else False,
                    "amount": getattr(fi.qi, "pre_paid_amount", None) if fi.qi_id else None,
                },
            },
            "delivery": self.delivery.estimate(
                getattr(fi.qi, "supply_date", None) if fi.qi_id else None,
                fi.delivery_time or factor.delivery_time,
            ),
            "children": [],
        }
        if include_events:
            node["events"] = self._workflow_events(factor, node["id"])

        locations = (
            fi.factoritemsupplylocation_set
            .select_related(
                "order",
                "order__item",
                "order__item_trade",
                "order_bazar",
                "order_bazar__item",
                "wh_reserve",
                "wh_reserve__item",
            )
            .all()
        )
        if locations:
            for location in locations:
                node["children"].append(self._location_node(location, include_events))
        elif fi.supply_locations_id:
            node["children"].append(
                self._order_node(fi.supply_locations, quantity=fi.quantity, include_events=include_events, legacy=True)
            )
        return node

    def _location_node(self, location, include_events):
        if location.wh_reserve_id:
            wh = location.wh_reserve
            return {
                "id": f"supply:{location.pk}",
                "type": "WAREHOUSE",
                "source_id": location.pk,
                "quantity": location.quantity,
                "status": status("WAREHOUSE_STOCK"),
                "item": self._item(wh.item),
                "warehouse_code": wh.sepidar_wh_code,
                "delivery": self.delivery.estimate(),
                "children": [],
            }

        if location.order_bazar_id:
            order = location.order_bazar
            code = "AVAILABLE" if order.receipt_in_wh else "DOMESTIC_SUPPLY"
            return {
                "id": f"market_order:{order.pk}",
                "type": "ORDER",
                "source_id": order.pk,
                "supply_type": "DOMESTIC",
                "number": order.order_number or order.pk,
                "quantity": location.quantity,
                "status": status(code),
                "item": self._item(order.item),
                "transportation": {"method": None},
                "delivery": self.delivery.estimate(),
                "gios": [],
                "packings": [],
                "children": [],
            }

        return self._order_node(
            location.order,
            quantity=location.quantity,
            include_events=include_events,
        )

    def _order_node(self, order, quantity=None, include_events=False, legacy=False):
        if order is None:
            return {
                "id": "order:none",
                "type": "ORDER",
                "quantity": quantity,
                "status": status("FOREIGN_SUPPLY"),
                "children": [],
            }

        gio_items = list(
            GIOItem.objects.filter(order=order)
            .select_related("gio")
            .order_by("gio__gio_date", "pk")
        )
        gios = [
            {
                "id": x.gio_id,
                "quantity": x.quantity,
                "date": iso(x.gio.gio_date),
            }
            for x in gio_items
        ]

        packing_qs = (
            PackingItem.objects
            .filter(order=order)
            .select_related("packing")
            .order_by("packing_id", "pk")
        )
        packing_map = {}
        for pi in packing_qs:
            p = pi.packing
            entry = packing_map.setdefault(p.pk, {
                "id": p.pk,
                "number": p.packing_number,
                "quantity": 0,
                "shipment_type": p.shipment_type,
                "status": self.status.packing(p),
                "raw_state": getattr(getattr(p, "last_work_flow", None), "current_state_name", None),
                "departure_date": iso(p.departure_date),
                "arrival_date": iso(p.arrival_date),
                "delivery": self.delivery.estimate(order.commitment_date_to_customer),
            })
            entry["quantity"] += pi.quantity or 0
        packings = list(packing_map.values())

        supply_type = "WAREHOUSE" if order.is_wh else ("DOMESTIC" if order.is_bazar else "FOREIGN")
        effective_quantity = quantity if quantity is not None else order.final_quantity
        status_breakdown = self._order_status_breakdown(
            order,
            effective_quantity,
            gios,
            packings,
        )
        node = {
            "id": f"order:{order.pk}",
            "type": "ORDER",
            "source_id": order.pk,
            "number": order.order_number or order.pk,
            "supply_type": supply_type,
            "legacy_supply_link": bool(legacy),
            "quantity": effective_quantity,
            "item": self._item(order.final_item),
            "status": self.status.order(order, packings, bool(gios)),
            "status_breakdown": status_breakdown,
            "created_at": iso(order.created_date),
            "transportation": {"method": order.transportation_method},
            "prepayment": {"has_pre_payment": bool(order.has_customer_prepaid)},
            "delivery": self.delivery.estimate(order.commitment_date_to_customer),
            "gios": gios,
            "packings": packings,
            "children": [],
        }
        if include_events:
            node["events"] = self._workflow_events(order, node["id"])
        return node

    def _order_status_breakdown(self, order, quantity, gios, packings):
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
            code = "AVAILABLE" if order.receipt_in_wh else "DOMESTIC_SUPPLY"
            return [{**status(code), "quantity": total}]

        packed_by_status = defaultdict(float)
        packed_total = 0.0
        remaining_for_packings = total
        for packing in packings:
            if not packing.get("status"):
                continue
            qty = min(float(packing.get("quantity") or 0), remaining_for_packings)
            if qty <= 0:
                continue
            code = packing["status"]["code"]
            packed_by_status[code] += qty
            packed_total += qty
            remaining_for_packings -= qty

        remaining_after_packing = max(total - packed_total, 0.0)

        gio_total = min(
            sum(float(gio.get("quantity") or 0) for gio in gios),
            remaining_after_packing,
        )
        remaining = max(total - packed_total - gio_total, 0.0)

        rows = []
        for code, qty in packed_by_status.items():
            if qty:
                rows.append({**status(code), "quantity": qty})

        if gio_total:
            rows.append({**status("CHINA_WAREHOUSE"), "quantity": gio_total})

        if remaining:
            base = self.status.order(order, packing_nodes=[], has_gio=False)
            rows.append({
                "code": base["code"],
                "title": base["title"],
                "quantity": remaining,
            })

        return rows or [{**self.status.order(order, packings, bool(gios)), "quantity": total}]

    def _summary(self, tree):
        statuses = self._leaf_statuses(tree)
        grouped = {}
        for row in statuses:
            key = row["code"]
            if key not in grouped:
                grouped[key] = {**row, "quantity": 0}
            grouped[key]["quantity"] += row.get("quantity") or 0

        nodes = list(self._walk(tree))
        factor_node = next((n for n in nodes if n.get("type") == "FACTOR"), None)
        quotation_node = next((n for n in nodes if n.get("type") == "QUOTATION"), None)
        pricing_node = factor_node or quotation_node or tree

        order_nodes = [n for n in nodes if n.get("type") == "ORDER"]
        transportation_methods = sorted({
            n.get("transportation", {}).get("method")
            for n in order_nodes
            if n.get("transportation", {}).get("method")
        })

        supply_rows = defaultdict(float)
        for n in nodes:
            if n.get("type") == "WAREHOUSE":
                supply_rows["WAREHOUSE"] += float(n.get("quantity") or 0)
            elif n.get("type") == "ORDER" and n.get("supply_type"):
                supply_rows[n["supply_type"]] += float(n.get("quantity") or 0)

        documents = {"request": None, "quotation": None, "factor": None}
        request_node = next((n for n in nodes if n.get("type") == "REQUEST"), None)
        if request_node:
            documents["request"] = {"id": request_node.get("source_id")}
        if quotation_node:
            documents["quotation"] = quotation_node.get("document")
        if factor_node:
            documents["factor"] = factor_node.get("document")

        return {
            "tracking_id": self._tracking_id_from_tree(tree),
            "customer": tree.get("customer"),
            "origin": {
                "type": tree.get("type"),
                "id": tree.get("source_id"),
                "number": tree.get("document", {}).get("number") if tree.get("document") else tree.get("source_id"),
            },
            "item": tree.get("item"),
            "quantity": tree.get("quantity"),
            "pricing": pricing_node.get("pricing", self._empty_pricing()),
            "delivery": (factor_node or quotation_node or tree).get(
                "delivery",
                self.delivery.estimate(),
            ),
            "supply": {
                "types": [
                    {"type": key, "quantity": value}
                    for key, value in sorted(supply_rows.items())
                ]
            },
            "transportation": {"methods": transportation_methods},
            "documents": documents,
            "statuses": list(grouped.values()),
            "is_partial": len(grouped) > 1,
        }

    def _leaf_statuses(self, node):
        children = node.get("children") or []
        if not children:
            if node.get("type") == "ORDER" and node.get("status_breakdown"):
                return node["status_breakdown"]
            return [{
                "code": node["status"]["code"],
                "title": node["status"]["title"],
                "quantity": node.get("quantity") or 0,
            }]
        out = []
        for child in children:
            out.extend(self._leaf_statuses(child))
        return out

    def _timeline(self, tree):
        events = []
        for node in self._walk(tree):
            events.extend(node.get("events") or [])
            if node.get("type") == "ORDER":
                for gio in node.get("gios") or []:
                    events.append({
                        "type": "GIO",
                        "title": STATUS_TITLES["CHINA_WAREHOUSE"],
                        "at": gio.get("date"),
                        "node_id": node["id"],
                    })
                for packing in node.get("packings") or []:
                    if not packing.get("status"):
                        continue
                    events.append({
                        "type": packing["status"]["code"],
                        "title": packing["status"]["title"],
                        "at": packing.get("departure_date") or packing.get("arrival_date"),
                        "node_id": node["id"],
                    })

        events = [x for x in events if x.get("at")]
        return sorted(events, key=lambda x: x["at"])

    def _workflow_events(self, obj, node_id):
        if not getattr(obj, "pk", None):
            return []
        ct = ContentType.objects.get_for_model(obj, for_concrete_model=False)
        return [
            {
                "type": "WORKFLOW",
                "title": wf.current_state_name or wf.state,
                "at": iso(wf.created_date),
                "node_id": node_id,
                "raw": {
                    "state": wf.state,
                    "current_state_name": wf.current_state_name,
                },
            }
            for wf in WorkFlow.objects.filter(content_type=ct, object_id=obj.pk).order_by("created_date", "pk")
        ]

    def _tracking_id_from_tree(self, tree):
        prefix = {
            "REQUEST": "cri",
            "QUOTATION": "qi",
            "FACTOR": "fi",
            "ORDER": "order",
        }.get(tree["type"], tree["type"].lower())
        return f"{prefix}:{tree['source_id']}"

    @staticmethod
    def _walk(node):
        yield node
        for child in node.get("children") or []:
            yield from SupplyTrackingService._walk(child)

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
