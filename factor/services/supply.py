# services/supply.py
from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Sum, Value, ExpressionWrapper, FloatField, F, Q
from django.db.models.functions import Coalesce

from factor.models import FactorItem, FactorItemSupplyLocation
from order.models import Order, OrderBazar, WhReserve
from sepidar.models import SepidarItemStock  # متصل با using='sepidar'
from notifications.models import SupplyNotification
from extra_data.models import ItemStockSummary
from tools import const
from tools.utils import timer


class SupplyLocationService:
    """
    سرویس مرکزی مدیریت محل تامین ردیف‌های فاکتور.
    تمام نوشتن‌ها روی WhReserve / Order / OrderBazar / FactorItemSupplyLocation
    باید از این سرویس عبور کنند تا قواعد سپیدار، رزروها، و نوتیف رعایت شود.
    """

    def _sl_is_warehouse(self, sl):
        return sl.wh_reserve_id is not None

    def _sl_order_obj(self, sl):
        if sl.order_id:
            return sl.order  # سفارش خارجی
        if sl.order_bazar_id:
            return sl.order_bazar  # سفارش داخلی/بازار
        return None

    def _order_lock(self, order_obj):
        # Order → trade_lock_order ؛ OrderBazar → فعلاً قفل ندارد
        return bool(getattr(order_obj, 'trade_lock_order', False))

    def _ensure_item_deletable(self, factor_item):
        """
        ردیف فقط وقتی حذف‌شدنی است که هیچ محل تامین سفارشیِ قفل‌شده نداشته باشد.
        رزرو انبار همیشه آزاد است.
        """
        for sl in factor_item.factoritemsupplylocation_set.filter(is_deleted=False):
            if self._sl_is_warehouse(sl):
                continue
            order_obj = self._sl_order_obj(sl)
            if order_obj is not None and self._order_lock(order_obj):
                raise ValidationError(
                    "این ردیف به سفارش قفل‌شده متصل است و قابل حذف نیست. "
                    "ابتدا قفل سفارش را بردارید."
                )

    # ─── دروازه‌ها ─────────────────────────────────────

    def _ensure_editable(self, factor):
        """قبل از هر نوشتنی روی فاکتور صدا زده شود."""
        if factor.sepidar_id is not None:
            raise ValidationError(
                "این فاکتور به سپیدار ارسال شده و قابل ویرایش نیست"
            )

    def _can_take_from_others(self, user, source_sl):
        """نقطه‌ی توسعه‌ی مجوز در آینده. فعلاً همه مجازند."""
        return True

    # ─── محاسبات و موجودی سپیدار ───────────────────────

    @property
    def fiscalyearref(self):
        return settings.SEPIDAR_CONST_DATA["fiscalyearref"]

    def _refresh_stock(self, item, stockref):
        """
        موجودی item-stockref را از DB سپیدار می‌خواند و
        ItemStockSummary محلی را آپدیت می‌کند. خروجی: موجودی فعلی.
        قبل از محاسبه‌ی free_qty در عملیات نوشتاری فراخوانی شود.
        """
        fy = self.fiscalyearref
        row = (
            SepidarItemStock.objects.using('sepidar')
            .filter(
                itemref=item.sepidar_id_0,    # یا هر فیلدی که id سپیداری Item را نگه می‌دارد
                stockref=stockref,
                fiscalyearref=fy,
            )
            .first()
        )
        if row is None:
            ItemStockSummary.objects.filter(
                item=item, stockref=stockref, fiscalyearref=fy
            ).delete()
            return 0
        local, _ = ItemStockSummary.objects.update_or_create(
            item=item, stockref=stockref, fiscalyearref=fy,
            defaults={'quantity': row.quantity},
        )
        return local.quantity

    def _get_local_stock(self, item, stockref):
        """فقط از جدول محلی می‌خواند (سریع ولی ممکن است منسوخ باشد)."""
        s = ItemStockSummary.objects.filter(
            item=item, stockref=stockref, fiscalyearref=self.fiscalyearref
        ).first()
        return s.quantity if s else 0

    def warehouse_free_qty(self, item, stockref, *, fresh=False):
        """
        موجودی آزاد انبار سپیدار = موجودی فعلی − مجموع رزروهای فعال
        (رزروهای فاکتورهای ارسال‌شده به سپیدار حساب نمی‌شوند چون قبلاً کسر شده‌اند)
        fresh=True: قبل از محاسبه، از سپیدار refresh کن.
        """
        sepidar_qty = (self._refresh_stock(item, stockref)
                       if fresh else self._get_local_stock(item, stockref))
        active = (
            WhReserve.objects.filter(
                item=item,
                sepidar_wh_code=stockref,
                cancel=False,
                wh_reserve_fis__fi__factor__sepidar_id__isnull=True,
            )
            .aggregate(total=Sum('quantity'))['total'] or 0
        )
        return float(sepidar_qty) - float(active)

    def order_free_qty(self, order_obj):
        """
        موجودی آزاد یک سفارش = تعداد کل − مجموع رزروهای فعال روی آن.
        برای Order یا OrderBazar قابل استفاده.
        """
        fk = 'order' if isinstance(order_obj, Order) else 'order_bazar'
        active = (
            FactorItemSupplyLocation.objects
            .filter(**{fk: order_obj})
            .filter(fi__factor__sepidar_id__isnull=True)
            .aggregate(total=Sum('quantity'))['total'] or 0
        )
        return order_obj.quantity - active

    def _has_shortage(self, factor_item):
        """آیا مجموع رزروهای فعلی این ردیف کمتر از quantity آن است؟"""
        supplied = (
            FactorItemSupplyLocation.objects
            .filter(fi=factor_item)
            .aggregate(total=Sum('quantity'))['total'] or 0
        )
        return supplied < factor_item.quantity

    # ─── اطلاع‌رسانی ───────────────────────────────────

    def _notify_taken(self, source_sl, taker_user, qty):
        owner = source_sl.fi.factor.creator_user
        if owner == taker_user:
            return
        taker_display = (
            taker_user.get_full_name() if hasattr(taker_user, 'get_full_name')
            else str(taker_user)
        )
        SupplyNotification.objects.create(
            user=owner,
            actor=taker_user,
            kind=SupplyNotification.RESERVE_TAKEN,
            factor_item=source_sl.fi,
            qty=qty,
            message=(
                f"{taker_display} مقدار {qty} از رزرو شما در "
                f"فاکتور شماره {source_sl.fi.factor.id} برداشت کرد"
            ),
        )

    def _notify_returned(self, source_sl, qty):
        SupplyNotification.objects.create(
            user=source_sl.fi.factor.creator_user,
            actor=None,
            kind=SupplyNotification.RESERVE_RETURNED,
            factor_item=source_sl.fi,
            qty=qty,
            message=(
                f"مقدار {qty} رزرو شما در فاکتور "
                f"شماره {source_sl.fi.factor.id} بازگردانده شد"
            ),
        )

    # ─── عملیات‌های اتمی (فاز ۲) ───────────────────────

    # ─── A) رزرو از موجودی آزاد انبار ────────────────────
    def _reserve_from_warehouse_free(self, factor_item, stockref, qty, user):
        """
        یک WhReserve جدید روی انبار سپیدار می‌سازد و یک SupplyLocation به آن متصل.
        verify-on-write: قبل از محاسبه‌ی free_qty، از سپیدار refresh می‌کند.
        """
        if qty <= 0:
            raise ValidationError("تعداد رزرو باید مثبت باشد")

        item = factor_item.goods_code
        free = self.warehouse_free_qty(item, stockref, fresh=True)
        if free < qty:
            raise ValidationError(
                f"موجودی آزاد انبار کافی نیست. آزاد: {free}، درخواست: {qty}"
            )

        wh = WhReserve.objects.create(item=item, sepidar_wh_code=stockref, quantity=qty, creator_user=factor_item.creator_user, editor_user=factor_item.editor_user)
        return FactorItemSupplyLocation.objects.create(
            fi=factor_item, wh_reserve=wh, quantity=qty, creator_user=user, editor_user=user
        )

    # ─── B) رزرو از موجودی آزاد سفارش ────────────────────
    def _reserve_from_order_free(self, factor_item, order_obj, qty):
        """
        یک SupplyLocation روی یک Order/OrderBazar موجود می‌سازد.
        """
        if qty <= 0:
            raise ValidationError("تعداد رزرو باید مثبت باشد")
        if order_obj.cancel:
            raise ValidationError("این سفارش لغو شده است")
        if order_obj.item_id != factor_item.goods_code_id:
            raise ValidationError("کالای سفارش با ردیف فاکتور هم‌خوانی ندارد")

        free = self.order_free_qty(order_obj)
        if free < qty:
            raise ValidationError(
                f"موجودی آزاد سفارش کافی نیست. آزاد: {free}، درخواست: {qty}"
            )

        kwargs = {'fi': factor_item, 'quantity': qty}
        if isinstance(order_obj, Order):
            kwargs['order'] = order_obj
        elif isinstance(order_obj, OrderBazar):
            kwargs['order_bazar'] = order_obj
        else:
            raise ValidationError("نوع سفارش نامعتبر است")
        return FactorItemSupplyLocation.objects.create(creator_user=factor_item.creator_user,
                                                       editor_user=factor_item.editor_user,
                                                       **kwargs)

    # ─── C) برداشت از رزرو دیگران روی انبار ───────────────
    def _take_from_warehouse_reserve(self, factor_item, source_sl, qty, user):
        """
        از یک SupplyLocation که روی WhReserve نشسته، qty واحد برمی‌دارد:
          - quantity منبع و WhReserve منبع کم می‌شود (ممکن است به ۰ برسد)
          - یک WhReserve جدید + SupplyLocation جدید با taken_from می‌سازد
          - منشأ مطلع می‌شود
        """
        if not self._can_take_from_others(user, source_sl):
            raise PermissionDenied("شما اجازه‌ی برداشت از رزرو دیگران را ندارید")
        if source_sl.wh_reserve_id is None:
            raise ValidationError("منبع انتخاب‌شده یک رزرو انبار نیست")

        src_factor = source_sl.fi.factor
        if src_factor.sepidar_id is not None:
            raise ValidationError("منبع متعلق به فاکتوری است که به سپیدار ارسال شده")
        if src_factor.id == factor_item.factor_id:
            raise ValidationError("نمی‌توان از رزرو ردیف دیگری در همین فاکتور برداشت کرد")
        if source_sl.quantity < qty:
            raise ValidationError(
                f"رزرو منبع کافی نیست. موجود: {source_sl.quantity}، درخواست: {qty}"
            )

        # کاهش از منبع
        source_sl.wh_reserve.quantity -= qty
        source_sl.wh_reserve.save(update_fields=['quantity'])
        source_sl.quantity -= qty
        source_sl.save(update_fields=['quantity'])

        # افزودن به رزرو قبلی در صورت وجود
        if factor_item.factoritemsupplylocation_set.filter(wh_reserve__item=factor_item.goods_code).exists():
            preview_wh_reserve = factor_item.factoritemsupplylocation_set.filter(wh_reserve__item=factor_item.goods_code).first()
            preview_wh_reserve.quantity += qty
            preview_wh_reserve.save(update_fields=['quantity'])
            preview_wh_reserve.wh_reserve.quantity += qty
            preview_wh_reserve.wh_reserve.save(update_fields=['quantity'])
        else:
            # ایجاد رزرو جدید
            new_wh = WhReserve.objects.create(
                item=source_sl.wh_reserve.item,
                sepidar_wh_code=source_sl.wh_reserve.sepidar_wh_code,
                quantity=qty,
                creator_user=user, editor_user=user
            )
            new_sl = FactorItemSupplyLocation.objects.create(
                fi=factor_item,
                wh_reserve=new_wh,
                quantity=qty,
                taken_from=None,  #source_sl, # نیازی نیست بدانیم از چه کسی قرض گرفته ایم
                creator_user=user,
                editor_user=user,
            )

        self._notify_taken(source_sl, user, qty)
        # return new_sl

    # ─── D) برداشت از رزرو دیگران روی سفارش ───────────────
    def _take_from_order_reserve(self, factor_item, source_sl, qty, user):
        """
        از یک SupplyLocation که روی Order یا OrderBazar نشسته، qty واحد برمی‌دارد.
        یک SupplyLocation جدید روی همان سفارش با taken_from می‌سازد.
        """
        if not self._can_take_from_others(user, source_sl):
            raise PermissionDenied("شما اجازه‌ی برداشت از رزرو دیگران را ندارید")
        if source_sl.order_id is None and source_sl.order_bazar_id is None:
            raise ValidationError("منبع انتخاب‌شده یک رزرو سفارش نیست")

        src_factor = source_sl.fi.factor
        if src_factor.sepidar_id is not None:
            raise ValidationError("منبع متعلق به فاکتوری است که به سپیدار ارسال شده")
        if src_factor.id == factor_item.factor_id:
            raise ValidationError("نمی‌توان از رزرو ردیف دیگری در همین فاکتور برداشت کرد")
        if source_sl.quantity < qty:
            raise ValidationError(
                f"رزرو منبع کافی نیست. موجود: {source_sl.quantity}، درخواست: {qty}"
            )

        # کاهش از منبع
        source_sl.quantity -= qty
        source_sl.save(update_fields=['quantity'])

        # ساخت SL جدید روی همان سفارش
        kwargs = {
            'fi': factor_item,
            'quantity': qty,
            'taken_from': None,  #source_sl, # نیازی نیست بدانیم از چه کسی قرض گرفته ایم
            'creator_user': user,
            'editor_user': user
        }
        if source_sl.order_id:
            kwargs['order'] = source_sl.order
        else:
            kwargs['order_bazar'] = source_sl.order_bazar
        new_sl = FactorItemSupplyLocation.objects.create(**kwargs)

        self._notify_taken(source_sl, user, qty)
        return new_sl

    # ─── E) ثبت سفارش جدید (بازار یا خارجی) ───────────────
    def _create_new_order(self, factor_item, group, qty, user, **extras):
        """
        یک Order یا OrderBazar جدید می‌سازد و یک SupplyLocation روی آن.
        extras در صورت لزوم به سازنده‌ی Order/OrderBazar پاس می‌شود
        (مثل order_title، order_number، currency، qi، …).
        """
        if qty <= 0:
            raise ValidationError("تعداد سفارش باید مثبت باشد")

        if group == 'foreign':
            order = Order.objects.create(
                item=factor_item.goods_code, quantity=qty, creator_user=user, editor_user=user, **extras
            )
            sl_kwargs = {'order': order}
        elif group == 'market':
            order = OrderBazar.objects.create(
                item=factor_item.goods_code, creator_user=user, editor_user=user, **extras
            )
            # OrderBazar در مدل شما quantity ندارد — اضافه شده در پیشنهاد قبلی
            order.quantity = qty
            order.save(update_fields=['quantity'])
            sl_kwargs = {'order_bazar': order}
        else:
            raise ValidationError(f"گروه نامعتبر برای ثبت سفارش جدید: {group}")

        return FactorItemSupplyLocation.objects.create(
            fi=factor_item, quantity=qty, creator_user=user, editor_user=user, **sl_kwargs
        )

    # ─── F) آزادسازی با حفظ زنجیره ─────────────────────────
    # def _release(self, sl):
    #     """
    #     یک SupplyLocation را آزاد می‌کند:
    #       ۱) فرزندان (SLs که از این برداشته‌اند) → جد این (chain-update)
    #       ۲) qty به منشأ بازگردانده می‌شود اگر منشأ ویرایش‌پذیر است و کمبود دارد
    #       ۳) WhReserve مرتبط (اگر بود) و خود SL حذف می‌شوند
    #     """
    #     qty = sl.quantity
    #     src = sl.taken_from  # ممکن است None باشد
    #
    #     # ۱) فرزندان به جد منتقل می‌شوند
    #     FactorItemSupplyLocation.objects.filter(taken_from=sl).update(
    #         taken_from=src
    #     )
    #
    #     wh_to_delete = sl.wh_reserve if sl.wh_reserve_id else None
    #     sl.delete()
    #     if wh_to_delete:
    #         wh_to_delete.delete()

    def _release(self, sl):
        """
        آزادسازی نرم یک SupplyLocation:
          ۱) فرزندان زنجیره‌ی taken_from به جدِ این SL منتقل می‌شوند
          ۲) رزرو انبار: WhReserve حذف می‌شود → موجودی به آزاد برمی‌گردد
          ۳) سفارش: منشأ اصلی ثبت می‌شود؛ بازگشت موجودی از طریق محاسبه‌ی free
             (سفارش قفل‌شده موجودی‌اش آزاد نمی‌شود — به بخش ۶ رجوع کن)
          ۴) خود SL با is_deleted=True باقی می‌ماند و از ردیف جدا می‌شود
        """
        src = sl.taken_from

        # ۱) فرزندان به جد منتقل می‌شوند
        FactorItemSupplyLocation.objects.filter(
            taken_from=sl, is_deleted=False
        ).update(taken_from=src)

        if self._sl_is_warehouse(sl):
            # ۲) انبار: اول FK را null کن تا حذف WhReserve، SL را cascade نکند
            wh = sl.wh_reserve
            sl.wh_reserve = None
            sl.is_deleted = True
            sl.factor_item = None
            sl.save(update_fields=['wh_reserve', 'is_deleted', 'fi'])
            wh.delete()  # بازگشت موجودی به آزاد
            return

        # ۳) سفارشی: حفظ ردپای منبع برای پیگیری سفارش بی‌فاکتور
        order_obj = self._sl_order_obj(sl)
        if order_obj is not None and not sl.original_source_type:
            sl.original_source_type = 'foreign' if sl.order_id else 'bazar'
            sl.original_source_id = order_obj.pk

        sl.delete()
        # sl.is_deleted = True
        # sl.fi = None
        # sl.save(update_fields=[
        #     'is_deleted', 'fi',
        #     'original_source_type', 'original_source_id',
        # ])

    # ─── سطح بالا (فاز ۳) ──────────────────────────────

    # ─── تنظیم تعداد یک SL موجود ────────────────────────
    def _adjust_quantity(self, sl, new_qty, user):
        """
        تعداد یک SL موجود را تنظیم می‌کند بدون حذف‌و‌ساخت مجدد.
        رشد یا کاهش، با حفظ شناسه (و در نتیجه حفظ taken_from فرزندان).
        new_qty=0 معادل _release است.
        """
        if new_qty < 0:
            raise ValidationError("تعداد نمی‌تواند منفی باشد")
        if new_qty == sl.quantity:
            return sl
        if new_qty == 0:
            self._release(sl)
            return None

        delta = new_qty - sl.quantity
        if delta > 0:
            self._grow_sl(sl, delta, user)
        else:
            self._shrink_sl(sl, -delta)
        return sl

    def _grow_sl(self, sl, delta, user):
        """افزایش تعداد یک SL — نیاز به ظرفیت از منشأ یا free pool دارد."""
        if sl.taken_from_id is None:
            # از free pool منبع
            if sl.wh_reserve_id:
                item = sl.wh_reserve.item
                stockref = sl.wh_reserve.sepidar_wh_code
                free = self.warehouse_free_qty(item, stockref, fresh=True)
                if free < delta:
                    raise ValidationError(
                        f"موجودی آزاد انبار برای افزایش کافی نیست. آزاد: {free}، نیاز: {delta}"
                    )
                sl.wh_reserve.quantity += delta
                sl.wh_reserve.save(update_fields=['quantity'])
            else:
                order_obj = sl.order or sl.order_bazar
                free = self.order_free_qty(order_obj)
                if free < delta:
                    raise ValidationError(
                        f"موجودی آزاد سفارش برای افزایش کافی نیست. آزاد: {free}، نیاز: {delta}"
                    )
            sl.quantity += delta
            sl.save(update_fields=['quantity'])
        else:
            # از منشأ taken_from
            src = sl.taken_from
            if src.fi.factor.sepidar_id is not None:
                raise ValidationError("منبع متعلق به فاکتور ارسال‌شده است")
            if src.quantity < delta:
                raise ValidationError(
                    f"رزرو منبع برای افزایش کافی نیست. موجود: {src.quantity}، نیاز: {delta}"
                )
            # کاهش از منبع
            src.quantity -= delta
            src.save(update_fields=['quantity'])
            if src.wh_reserve_id:
                src.wh_reserve.quantity -= delta
                src.wh_reserve.save(update_fields=['quantity'])
            # رشد سمت ما
            sl.quantity += delta
            sl.save(update_fields=['quantity'])
            if sl.wh_reserve_id:
                sl.wh_reserve.quantity += delta
                sl.wh_reserve.save(update_fields=['quantity'])
            self._notify_taken(src, user, delta)

    def _shrink_sl(self, sl, delta):
        """کاهش تعداد یک SL — مازاد به منشأ بازمی‌گردد یا به free pool می‌رود."""
        if sl.taken_from_id is not None:
            src = sl.taken_from
            src_factor = src.fi.factor
            if src_factor.sepidar_id is None and self._has_shortage(src.fi):
                src.quantity += delta
                src.save(update_fields=['quantity'])
                if src.wh_reserve_id:
                    src.wh_reserve.quantity += delta
                    src.wh_reserve.save(update_fields=['quantity'])
                self._notify_returned(src, delta)

        sl.quantity -= delta
        sl.save(update_fields=['quantity'])
        if sl.wh_reserve_id:
            sl.wh_reserve.quantity -= delta
            sl.wh_reserve.save(update_fields=['quantity'])

    # ─── سطح بالا: sync_factor_item ──────────────────────

    @transaction.atomic
    def sync_factor_item(self, factor_item, new_selections, user):
        """
        نقطه‌ی ورودی اصلی برای ذخیره از فرم.
        new_selections: لیست JSON پارس‌شده از فیلد supply_locations.
        """
        self._ensure_editable(factor_item.factor)
        self._lock_relevant_rows(factor_item, new_selections)
        self._validate(factor_item, new_selections)

        current = self._index_current(factor_item)
        new_index, new_orders = self._index_new(new_selections)
        plan = self._diff(current, new_index)

        self._apply_plan(factor_item, plan, new_orders, user)

    def _lock_relevant_rows(self, factor_item, new_selections):
        """قفل‌گذاری روی همه‌ی منابع درگیر به ترتیب pk صعودی برای جلوگیری از deadlock."""
        # خود ردیف فاکتور
        FactorItem.objects.select_for_update(of=('self', )).filter(pk=factor_item.pk).first()

        wh_stockrefs = set()
        order_ids = set()
        bazar_ids = set()
        src_sl_ids = set()

        # از وضعیت فعلی
        for sl in factor_item.factoritemsupplylocation_set.select_related('wh_reserve').all():
            if sl.wh_reserve_id:
                wh_stockrefs.add(sl.wh_reserve.sepidar_wh_code)
            if sl.order_id:
                order_ids.add(sl.order_id)
            if sl.order_bazar_id:
                bazar_ids.add(sl.order_bazar_id)

        # از انتخاب‌های جدید
        for e in new_selections:
            if e['is_new']:
                continue
            sid = int(e['source_id']) if e['source_id'] else None
            if sid is None:
                continue
            if e['group'] == 'warehouse':
                wh_stockrefs.add(sid)
            elif e['group'] == 'foreign':
                order_ids.add(sid)
            elif e['group'] == 'market':
                bazar_ids.add(sid)
            for r in e.get('from_reserves', []):
                src_sl_ids.add(int(r['reserve_id']))

        # قفل‌ها (eval queryset برای trigger شدن SELECT FOR UPDATE)
        if wh_stockrefs:
            list(WhReserve.objects.select_for_update()
                 .filter(item=factor_item.goods_code, sepidar_wh_code__in=wh_stockrefs)
                 .order_by('pk'))
        if order_ids:
            list(Order.objects.select_for_update().filter(pk__in=order_ids).order_by('pk'))
        if bazar_ids:
            list(OrderBazar.objects.select_for_update().filter(pk__in=bazar_ids).order_by('pk'))
        if src_sl_ids:
            list(FactorItemSupplyLocation.objects.select_for_update()
                 .filter(pk__in=src_sl_ids).order_by('pk'))

    def _validate(self, factor_item, new_selections):
        """اعتبارسنجی‌های سراسری روی لیست جدید."""
        total = 0
        warehouse_count = 0
        for e in new_selections:
            free = e.get('qty_free', 0) or 0
            others = sum(r['qty'] for r in e.get('from_reserves', []) or [])
            total += free + others
            if e['group'] == 'warehouse' and (free > 0 or others > 0):
                warehouse_count += 1

        if warehouse_count > 1:
            raise ValidationError("فقط یک انبار در هر ردیف فاکتور مجاز است")
        if total > factor_item.quantity:
            raise ValidationError(
                f"مجموع رزروها ({total}) بیشتر از تعداد ردیف ({factor_item.quantity}) است"
            )
        # توضیح: total < quantity مجاز است (کمبود) — کاربر می‌تواند بعداً تکمیل کند

    def _index_current(self, factor_item):
        """SLs موجود را به دیکشنری key→sl نگاشت می‌کند."""
        result = {}
        for sl in factor_item.factoritemsupplylocation_set.select_related(
                'wh_reserve', 'order', 'order_bazar', 'taken_from'
        ).all():
            if sl.wh_reserve_id:
                group = 'warehouse'
                source_id = sl.wh_reserve.sepidar_wh_code
            elif sl.order_id:
                group = 'foreign'
                source_id = sl.order_id
            elif sl.order_bazar_id:
                group = 'market'
                source_id = sl.order_bazar_id
            else:
                continue  # SL خراب
            key = (group, source_id, sl.taken_from_id)
            result[key] = sl
        return result

    def _index_new(self, new_selections):
        """لیست JSON را به دیکشنری key→qty + لیست سفارش‌های جدید تبدیل می‌کند."""
        index = {}
        new_orders = []  # [(group, qty), ...]
        for e in new_selections:
            if e['is_new']:
                qty = (e.get('qty_free', 0) or 0)
                if qty > 0:
                    new_orders.append((e['group'], qty))
                continue
            sid = int(e['source_id']) if e['source_id'] else None
            qty_free = e.get('qty_free', 0) or 0
            if qty_free > 0:
                index[(e['group'], sid, None)] = qty_free
            for r in e.get('from_reserves', []) or []:
                rid = int(r['reserve_id'])
                index[(e['group'], sid, rid)] = r['qty']
        return index, new_orders

    def _diff(self, current, new_index):
        """
        لیست عملیات لازم برمی‌گرداند:
          [('release', sl), ('shrink', sl, new_qty),
           ('grow', sl, new_qty), ('create', key, qty)]
        """
        plan = []
        for key, sl in current.items():
            if key not in new_index:
                plan.append(('release', sl))
            else:
                new_qty = new_index[key]
                if new_qty < sl.quantity:
                    plan.append(('shrink', sl, new_qty))
                elif new_qty > sl.quantity:
                    plan.append(('grow', sl, new_qty))
                # مساوی → no-op
        for key, qty in new_index.items():
            if key not in current:
                plan.append(('create', key, qty))
        return plan

    def _apply_plan(self, factor_item, plan, new_orders, user):
        """اعمال plan در ترتیب: release → shrink → grow → create → new_orders."""
        for op in plan:
            if op[0] == 'release':
                self._release(op[1])
        for op in plan:
            if op[0] == 'shrink':
                self._adjust_quantity(op[1], op[2], user)
        for op in plan:
            if op[0] == 'grow':
                self._adjust_quantity(op[1], op[2], user)
        for op in plan:
            if op[0] == 'create':
                self._create_from_key(factor_item, op[1], op[2], user)
        for group, qty in new_orders:
            self._create_new_order(factor_item, group, qty, user)

    def _create_from_key(self, factor_item, key, qty, user):
        """dispatch به عملیات اتمی مناسب بر اساس key."""
        group, source_id, taken_from_id = key
        if taken_from_id is None:
            if group == 'warehouse':
                return self._reserve_from_warehouse_free(factor_item, source_id, qty, user)
            elif group == 'foreign':
                order = Order.objects.get(pk=source_id)
                return self._reserve_from_order_free(factor_item, order, qty)
            elif group == 'market':
                order = OrderBazar.objects.get(pk=source_id)
                return self._reserve_from_order_free(factor_item, order, qty)
        else:
            source_sl = FactorItemSupplyLocation.objects.get(pk=taken_from_id)
            if source_sl.wh_reserve_id:
                return self._take_from_warehouse_reserve(factor_item, source_sl, qty, user)
            else:
                return self._take_from_order_reserve(factor_item, source_sl, qty, user)
        raise ValidationError(f"ترکیب نامعتبر در plan: {key}")

    # ─── رسید سفارش به انبار ─────────────────────────────

    @transaction.atomic
    def receive_order(self, order_obj, stockref, user):
        """
        وقتی سفارش به انبار سپیدار رسید:
          - برای هر SL مرتبط (فقط فاکتورهای ویرایش‌پذیر) یک WhReserve می‌سازد
          - SL ها از order/order_bazar به wh_reserve منتقل می‌شوند
          - original_source_type/id ثبت می‌شود (اگر قبلاً نبوده)
          - خود سفارش با receipt_in_wh=True و sepidar_wh_code=stockref علامت می‌خورد
        """
        if order_obj.cancel:
            raise ValidationError("سفارش لغو شده قابل رسید نیست")

        is_foreign = isinstance(order_obj, Order)
        fk_name = 'order' if is_foreign else 'order_bazar'
        src_label = 'order' if is_foreign else 'order_bazar'

        # قفل و واکشی
        order_obj = order_obj.__class__.objects.select_for_update().get(pk=order_obj.pk)
        sls = list(
            FactorItemSupplyLocation.objects
            .select_for_update()
            .filter(**{fk_name: order_obj})
            .filter(fi__factor__sepidar_id__isnull=True)
            .order_by('pk')
        )

        for sl in sls:
            new_wh = WhReserve.objects.create(
                item=order_obj.item,
                sepidar_wh_code=stockref,
                quantity=sl.quantity,
            )
            update_fields = ['wh_reserve', fk_name]
            sl.wh_reserve = new_wh
            setattr(sl, fk_name, None)
            if not sl.original_source_type:
                sl.original_source_type = src_label
                sl.original_source_id = order_obj.pk
                update_fields += ['original_source_type', 'original_source_id']
            sl.save(update_fields=update_fields)

        order_obj.receipt_in_wh = True
        order_obj.sepidar_wh_code = stockref
        upd = ['receipt_in_wh', 'sepidar_wh_code']
        if is_foreign:
            order_obj.is_over = True
            upd.append('is_over')
        order_obj.save(update_fields=upd)

    # ─── لغو فاکتور ──────────────────────────────────────

    @transaction.atomic
    def cancel_factor(self, factor, user):
        """آزادسازی همه‌ی محل تامین‌های فاکتور و علامت‌گذاری به‌عنوان لغوشده."""
        self._ensure_editable(factor)
        FactorItem.objects.select_for_update().filter(factor=factor)  # eval برای lock

        for fi in factor.factoritem_set.all():
            sls = list(
                fi.factoritemsupplylocation_set.select_for_update().all()
            )
            for sl in sls:
                self._release(sl)

        factor.cancel = True
        factor.save(update_fields=['cancel'])

    @transaction.atomic
    def delete_factor_item(self, factor_item, user):
        self._ensure_editable(factor_item.factor)
        self._ensure_item_deletable(factor_item)

        sls = list(
            factor_item.factoritemsupplylocation_set
            .select_for_update()
            .filter(is_deleted=False)
        )
        for sl in sls:
            self._release(sl)  # اول محل تامین‌ها آزاد/جدا می‌شوند

        # factor_item.delete()  # حالا ردیف بدون cascade روی SLها حذف می‌شود
        factor_item.is_deleted = True
        factor_item.save(update_fields=['is_deleted'])

    EPS = 1e-6

    @transaction.atomic
    def migrate_bazar_order_to_warehouse(self, order_bazar, wh_code, received_qty):
        """
        پس از رسید سفارش بازار در انبار:
        همه‌ی SLهای متصل به این سفارش به‌صورت FIFO به رزرو انبار تبدیل می‌شوند.
        - تا جای موجودی رسید: SL با تعداد کامل خودش.
        - SLهای پایانی که موجودی نمی‌رسد: باز هم تبدیل می‌شوند، ولی با تعداد رسیده
          (کمبود) و از سفارش جدا می‌شوند. هیچ SLی روی سفارش باقی نمی‌ماند.
        """
        sls = list(
            FactorItemSupplyLocation.objects
            .select_for_update()
            .filter(order_bazar_id=order_bazar.pk, is_deleted=False)
            .filter(fi__isnull=False)  # SL یتیم را رد کن
            .filter(fi__factor__sepidar_id__isnull=True)  # فقط فاکتورهای ارسال‌نشده
            .order_by('pk')  # FIFO
        )
        if not sls:
            return

        budget = float(received_qty)

        for sl in sls:
            fi_wh_sl = FactorItemSupplyLocation.objects.filter(fi=sl.fi, wh_reserve__sepidar_wh_code=2).first()
            if fi_wh_sl:
                fi_wh_sl.quantity += sl.quantity
                fi_wh_sl.wh_reserve.quantity += sl.quantity
                sl.is_deleted = True
                order_bazar.is_over = True
                sl.save(update_fields=['is_deleted'])
                fi_wh_sl.save(update_fields=['quantity'])
                order_bazar.save(update_fields=['is_over'])
            else:
                # سهم این SL از موجودی رسیده (ممکن است کمتر از quantity باشد = کمبود)
                receipt = sl.quantity if sl.quantity <= budget else max(budget, 0.0)

                wh = WhReserve.objects.create(
                    item=order_bazar.item,
                    sepidar_wh_code=wh_code,
                    quantity=sl.quantity,  # رزرو به اندازه‌ی نیاز ردیف
                )

                sl.order_bazar = None  # جدا از سفارش
                sl.wh_reserve = wh
                sl.wh_code = wh_code
                sl.wh_receipt_quantity = receipt  # چقدر واقعاً رسید شد (کمبود اینجا دیده می‌شود)
                if not sl.original_source_type:
                    sl.original_source_type = 'bazar_order'
                    sl.original_source_id = order_bazar.pk
                sl.save(update_fields=[
                    'order_bazar', 'wh_reserve', 'wh_code', 'wh_receipt_quantity',
                    'original_source_type', 'original_source_id',
                ])

                budget = max(budget - receipt, 0.0)

@timer
def _wh_entry(sr, others_by_wh, own_wh_qty):
    stockref = sr.stockref
    others = others_by_wh.get(stockref, [])
    others_total = sum(o.quantity for o in others)

    WhReserve.objects.filter(item__sepidar_id_0=sr.pk)

    return {
        'id': stockref,
        'name': sr.display_name,  # هر چه که نام انبار را می‌دهد
        'sepidar_qty': sr.quantity,
        'free_qty': float(sr.quantity) - float(others_total),
        'other_reserves_total': others_total,
        # SL با taken_from=None → از موجودی آزاد
        'preselected_qty_free': own_wh_qty.get((stockref, None), 0),
        'other_reserves': [
            {
                'id': o.id,
                'qty': o.quantity,
                'owner': str(o.fi.factor.creator_user),
                # SL با taken_from=o.id → از رزرو این منشأ
                'preselected_qty': own_wh_qty.get((stockref, o.id), 0),
                'factor': o.fi.factor
            }
            for o in others
        ],
    }


@timer
def _order_entry(obj, others_by_id, own_qty_by_key, qty_field):
    others = others_by_id.get(obj.id, [])
    # others_total = sum(loc.quantity for loc in others)
    others_total = (getattr(obj, 'used', 0) or 0) - (getattr(obj, 'used_by_self', 0) or 0)
    total_qty = getattr(obj, qty_field)

    return {
        'id': obj.id,
        'name': obj.order_title or obj.order_number or f"سفارش {obj.id}",
        'total_qty': total_qty,
        'free_qty': total_qty - others_total,
        'other_reserves_total': others_total,
        'preselected_qty_free': own_qty_by_key.get((obj.id, None), 0),
        'other_reserves': [
            {
                'id': loc.id,
                'qty': loc.quantity,
                # 'owner': str(loc.factor_item.factor.creator_user),
                'owner': str(loc.fi.factor.creator_user),
                'preselected_qty': own_qty_by_key.get((obj.id, loc.id), 0),
                'factor': loc.fi.factor
            }
            for loc in [] #others  فعلا نمیخواییم از رزرو سفارش دیگران انتخاب کنیم
        ],
    }


@timer
def attach_supply(factor_items):
    """
    به ازای هر FactorItem در لیست، .supply را پر می‌کند.
    فرض: factor_items از قبل با factoritemsupplylocation_set
    و select_related روی wh_reserve/order/bazar_order پری‌فچ شده‌اند.

    تعداد کوئری اضافه: ۴ تا (مستقل از تعداد ردیف فاکتور)
    """
    items = list(factor_items)
    if not items:
        return

    sepidar_id_and_portal_item_id = {(fi.goods_code.sepidar_id, fi.goods_code.pk) for fi in items if fi.goods_code}
    sepidar_ids = {i[0] for i in sepidar_id_and_portal_item_id}
    portal_item_ids = {i[1] for i in sepidar_id_and_portal_item_id}
    own_item_ids = [fi.id for fi in items]

    sepidar_qs = (SepidarItemStock.objects.using('sepidar')
                  .filter(itemref_id__in=sepidar_ids, quantity__gt=0, fiscalyearref=settings.SEPIDAR_CONST_DATA['fiscalyearref']))
    wh_by_goods = defaultdict(list)
    for r in sepidar_qs:
        wh_by_goods[r.itemref_id].append(r)

    bo_qs = OrderBazar.objects.filter(
                item_id__in=portal_item_ids,
                is_over=False,
                receipt_in_wh=False,
            ).annotate(
                used=Coalesce(Sum('order_bazar_fis__quantity'), Value(0.0),),
                used_by_self=Coalesce(
                    Sum(
                        'order_bazar_fis__quantity',
                        filter=Q(order_bazar_fis__fi_id__in=own_item_ids),
                    ),
                    Value(0.0),
                ),
            ).filter(
                Q(used__lt=F('quantity')) | Q(used_by_self__gt=0)
            )

    bo_by_goods = defaultdict(list)
    for o in bo_qs:
        bo_by_goods[o.item].append(o)

    fo_qs = Order.objects.filter(
                item_id__in=portal_item_ids,
                is_over=False,
                is_wh=False
            ).annotate(
                used=Coalesce(Sum('order_fis__quantity'), Value(0.0)),
                used_by_self=Coalesce(
                    Sum(
                        'order_fis__quantity',
                        filter=Q(order_fis__fi_id__in=own_item_ids),
                    ),
                    Value(0.0),
                ),
            ).filter(
                Q(used__lt=F('quantity')) | Q(used_by_self__gt=0)
            )
    fo_by_goods = defaultdict(list)
    for o in fo_qs:
        fo_by_goods[o.final_item].append(o)

    # سفارش‌هایی که تمام ظرفیتشان رزرو شده‌اند
    fully_used_bo = (
        OrderBazar.objects
        .annotate(total_used=Sum('order_bazar_fis__quantity'))
        .filter(total_used__gte=F('quantity'))
        .values('id')
    )
    fully_used_fo = (
        Order.objects
        .annotate(total_used=Sum('order_fis__quantity'))
        .filter(total_used__gte=F('quantity'))
        .values('id')
    )

    others_qs = (
        FactorItemSupplyLocation.objects
        .filter(
            fi__goods_code__in=portal_item_ids,
            quantity__gt=0,
            fi__factor__sepidar_id__isnull=True,
            # fi__factor__last_work_flow__current_state_name__in=const.FACTOR_OPEN_FOR_RESERVE_STATE
        )
        .exclude(fi_id__in=own_item_ids)
        .exclude(order_bazar_id__in=fully_used_bo)  # سفارش‌های بازار پر
        .exclude(order_id__in=fully_used_fo)  # سفارش‌های خارجی پر
        .select_related(
            'fi__factor__creator_user',
            'wh_reserve',
        )
    ).distinct()

    others_by_wh = defaultdict(list)
    others_by_bo = defaultdict(list)
    others_by_fo = defaultdict(list)
    for loc in others_qs:
        if loc.wh_reserve_id:
            # رزرو روی انبار: کلید را warehouse_id بگیرید
            others_by_wh[loc.wh_reserve.sepidar_wh_code].append(loc)
        elif loc.order_bazar_id:
            others_by_bo[loc.order_bazar_id].append(loc)
        elif loc.order_id:
            others_by_fo[loc.order_id].append(loc)

    # ─── ۳) ساخت supply برای هر ردیف ───
    for fi in items:
        # انتخاب‌های خود این ردیف (از پری‌فچ، بدون کوئری اضافه)
        own_locs = list(fi.factoritemsupplylocation_set.all() if fi.pk else [])
        own_wh_qty = {}
        own_bo_qty = {}
        own_fo_qty = {}
        for loc in own_locs:
            if loc.quantity <= 0:
                continue  # SL خالی‌شده (ghost) را نادیده بگیر
            if loc.wh_reserve_id:
                key = (loc.wh_reserve.sepidar_wh_code, loc.taken_from_id)
                own_wh_qty[key] = own_wh_qty.get(key, 0) + loc.quantity
            elif loc.order_bazar_id:
                key = (loc.order_bazar_id, loc.taken_from_id)
                own_bo_qty[key] = own_bo_qty.get(key, 0) + loc.quantity
            elif loc.order_id:
                key = (loc.order_id, loc.taken_from_id)
                own_fo_qty[key] = own_fo_qty.get(key, 0) + loc.quantity

        fi.supply = {
            'warehouses': [
                _wh_entry(sr, others_by_wh, own_wh_qty)
                for sr in wh_by_goods.get(fi.goods_code.sepidar_id, [])
            ],
            'market_orders': [
                _order_entry(o, others_by_bo, own_bo_qty, 'quantity')
                for o in bo_by_goods.get(fi.goods_code, [])
            ],
            'foreign_orders': [
                _order_entry(o, others_by_fo, own_fo_qty, 'quantity')
                for o in fo_by_goods.get(fi.goods_code, [])
            ],
        }