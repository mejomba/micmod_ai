from django.db import models, connection, connections
from django.db.models import Manager, Q

from tools.utils import to_jalali_date
from translator import get_text as _


class NewOrder(models.Model):
    code = models.CharField(max_length=20,verbose_name=_('code'), primary_key=True)

    @staticmethod
    def get_new_order(date_str=None):
        qry = f"""
select dl_data.Code as code,dl_data.IsCustomer,dl_data.LastName,dl_data.Name,dl_data.party_phones,dl_data.related_emails,
dl_data.related_phones,dl_data.Title,dl_data.Website, 
o.[Customer code],o.order_count from (
(select [Customer code], COUNT(*) as order_count from new_orders group by [Customer code]) as o
join 
(select dl.Code,dl.Title,p.Name,p.LastName,p.Website,p.IsCustomer,pf.party_phones,pr.related_emails,pr.related_phones from 
  [acc dl] as dl 
  left join [gnr Party] p on p.DLRef = dl.DLId
  left join 
  (
  select distinct PartyRef,
  SUBSTRING(
        (
            SELECT ','+pf2.Phone  AS [text()]
            FROM [gnr PartyPhone] pf2
            WHERE pf2.PartyRef = pf1.PartyRef
            ORDER BY pf2.PartyRef
            FOR XML PATH (''), TYPE
        ).value('text()[1]','nvarchar(max)'), 2, 1000) [party_phones]
		from [gnr PartyPhone] as pf1
) as pf on pf.PartyRef = p.PartyId
left join 
(
  select distinct PartyRef,
  SUBSTRING(
        (
            SELECT ','+pr2.Name+'-'+pr2.Phone  AS [text()]
            FROM [gnr PartyRelated] pr2
            WHERE pr2.PartyRef = pr1.PartyRef
            ORDER BY pr2.PartyRef
            FOR XML PATH (''), TYPE
        ).value('text()[1]','nvarchar(max)'), 2, 1000) [related_phones],
  SUBSTRING(
        (
            SELECT ','+pr2.Name+'-'+pr2.Email  AS [text()]
            FROM [gnr PartyRelated] pr2
            WHERE pr2.PartyRef = pr1.PartyRef
            ORDER BY pr2.PartyRef
            FOR XML PATH (''), TYPE
        ).value('text()[1]','nvarchar(max)'), 2, 1000) [related_emails]
from [gnr PartyRelated] as pr1) as pr on pr.PartyRef = p.PartyId
) as dl_data on dl_data.Code = o.[Customer code]
)"""
        res = NewOrder.objects.raw(qry, using='dw')
        return res

    @staticmethod
    def get_order_list(customer_code, order_number=None,min_status=1):
        qry =f"""
    SELECT [Order No] as code,[Create Date] create_date,[Part Number (S)] part_number,SKU sku,
    [Duty Date] duty_date,[Request Qty] request_qty,[total packed count] total_pack_count,[total arrived count] total_arrived_count,
case 
	when [status]=1 then N'تماس با کارشناس'
	when [status]=2 then N'کامل شده'
	when [status]=3 then N'نیاز به اطلاعات تکمیلی'
	when [status]=4 or [status]=5 then N'در حال ترخیص'
	when [status]=6 then N'ارسال شده به ایران'
	when [status]=7 then N'کالا در پورت مبدا'
	when [status]>7 then N'بررسی تامین کننده'
end as m_status,[pack numbers] pack_number
      FROM [DW].[dbo].[new_orders]
      where [Customer code] = '{customer_code}' and [status]>={min_status} {" and [Order No]='"+ order_number + "'" if order_number else ""}
  """
        res = NewOrder.objects.raw(qry, using='dw')
        return res
class ItemModel(models.Model):
    sku = models.IntegerField(primary_key=True)

    @staticmethod
    def get_item(sku):
        qry =F"""
select o.sku,
			 CASE
				 When o.clearance > 0 Then N'6-ترخیص' 
				 When o.packing_number<>'' Then N'5-ثبت پکینگ'
				 When o.gio_qty1+o.gio_qty2 > 0 Then N'4-دفتر چین'
				 When o.paid > 0 or o.pre_paid>0 Then N'3-پرداخت/پیش پرداخت'
				 When o.sent_to_vendor>0 Then N'2-ارسال برای تامین کننده'
				 Else N'1-ارسال برای تایید مهندس'
			 End as o_status, 
			 CONVERT(Char(7),o.[est_delivery_date],120) as req_date,
			 IIF(CHARINDEX('کسری انبار',o.customer) >0,N'کسری انبار',N'مشتری خاص') as customer_status,
			 sum(o.requset_qty) as req_qty, sum(o.order_qty) as ord_qty, sum(o.gio_qty1 + o.gio_qty2) as gio_qty, 
			 sum(o.reciept_part1+o.reciept_part2+o.reciept_part3+o.reciept_part4+o.reciept_part5) as rec_qty,
			 sum(o.remain_qty) as remain_qty
	from orders as o
	where o.completed = 0 and o.canceled = 0 and o.HK='' and o.sku = {sku}
	group by o.sku,
			 CASE
				 When o.clearance > 0 Then N'6-ترخیص' 
				 When o.packing_number<>'' Then N'5-ثبت پکینگ'
				 When o.gio_qty1+o.gio_qty2 > 0 Then N'4-دفتر چین'
				 When o.paid > 0 or o.pre_paid>0 Then N'3-پرداخت/پیش پرداخت'
				 When o.sent_to_vendor>0 Then N'2-ارسال برای تامین کننده'
				 Else N'1-ارسال برای تایید مهندس'
			 End, 
			 CONVERT(Char(7),o.[est_delivery_date],120), 
			 IIF(CHARINDEX('کسری انبار',o.customer) >0,N'کسری انبار',N'مشتری خاص')   
	order by o_status, req_date    
        """
        res = ItemModel.objects.raw(qry, using='dw')
        # res = [x for x in res]
        return res

    @staticmethod
    def get_items_extra_data(list=False):
        qry = """
SELECT [ردیف] sku ,[پارت نامبر] title,[گروه خرید] purchase_group ,[گروه فروش] sales_group ,[گروه کالا] goods_group ,[پکیج] package ,[کد مادر] parent_code 
	  ,[زمان تولید کارخانه] production_date ,[سرگروه] group_head ,[اولویت فروش] sales_perority
  FROM [DW].[dbo].[MM Component]        
        """
        items = ItemModel.objects.raw(qry,using='dw')
        if list:
            list_items = {}
            for item in items:
                list_items[item.sku] = item
            items = list_items
        return items


class OrderListDatatableModelManager(Manager):
    def get_queryset(self):
        return super(OrderListDatatableModelManager, self).get_queryset().all().using('dw')

    def raw_as_qs(self, raw_query, params=()):
        """Execute a raw query and return a QuerySet.  The first column in the
        result set must be the id field for the model.
        :type raw_query: str | unicode
        :type params: tuple[T] | dict[str | unicode, T]
        :rtype: django.db.models.query.QuerySet
        """
        print('raw as queryset')
        cursor = connections['dw'].cursor()
        try:
            cursor.execute(raw_query)
            return self.filter(id__in=(x[0] for x in cursor))
        finally:
            cursor.close()


class OrderListDatatableModel(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    customer = models.CharField(max_length=150, null=True, verbose_name=_('customer'))
    status_icon = models.CharField(max_length=5, null=True, verbose_name=_('status icon'))
    status = models.CharField(max_length=20, null=True, verbose_name=_('status'))
    sku = models.CharField(max_length=10, null=True, verbose_name=_('sku'))
    part_number = models.TextField(max_length=300, null=True, verbose_name=_('part number'))
    pre_invoice_number = models.CharField(max_length=20, null=True, verbose_name=_('pre invoice number'))
    create_date = models.DateField(null=True, verbose_name=_('create date'))
    duty_date = models.DateField(null=True, verbose_name=_('duty date'))
    order_quantity = models.FloatField(null=True, verbose_name=_('order quantity'))
    total_packed_count = models.FloatField(null=True, verbose_name=_('total packed count'))
    total_arrived_count = models.FloatField(null=True, verbose_name=_('total arrived count'))
    pack_numbers = models.TextField(max_length=700, null=True, verbose_name=_('pack numbers'))

    objects = OrderListDatatableModelManager()

    @classmethod
    def select_all(cls):
        return cls.objects.all()

    class Meta:
        managed = False
        db_table = 'OrderListView3'

    @property
    def jalali_create_date(self):
        # return self.create_date
        return to_jalali_date(self.create_date)

    @property
    def jalali_duty_date(self):
        # return self.duty_date
        return to_jalali_date(self.duty_date)


class CargoListDatatableModelManager(Manager):
    def get_queryset(self):
        return super(CargoListDatatableModelManager, self).get_queryset().all().using('dw')

    def raw_as_qs(self, raw_query, params=()):
        """Execute a raw query and return a QuerySet.  The first column in the
        result set must be the id field for the model.
        :type raw_query: str | unicode
        :type params: tuple[T] | dict[str | unicode, T]
        :rtype: django.db.models.query.QuerySet
        """
        print('raw as queryset')
        cursor = connections['dw'].cursor()
        try:
            cursor.execute(raw_query)
            return self.filter(id__in=(x[0] for x in cursor))
        finally:
            cursor.close()


class CargoListDatatableModel(models.Model):
    id = models.IntegerField(primary_key=True)
    active = models.BooleanField(blank=True, null=True, verbose_name=_('active'))
    invoice_number = models.CharField(max_length=50, null=True, verbose_name=_('invoice_number'))
    new_doc_date = models.DateField(null=True, verbose_name=_('new_dock_date'))
    in_person = models.BooleanField(null=True, verbose_name=_('in_person'))
    in_office = models.BooleanField(null=True, verbose_name=_('in_office'))
    force = models.BooleanField(null=True, verbose_name=_('force'))
    delete_doc = models.BooleanField(null=True, verbose_name=_('delete_doc'))
    delete_doc_date = models.DateField(null=True, verbose_name=_('delete_doc_date'))
    financial_cond = models.CharField(max_length=50, null=True, verbose_name=_('financial_cond'))
    financial_confirm = models.BooleanField(null=True, verbose_name=_('financial_confirm'))
    paking = models.BooleanField(null=True, verbose_name=_('paking'))
    final_check = models.BooleanField(null=True, verbose_name=_('final_check'))
    official_number = models.CharField(max_length=50, null=True, verbose_name=_('official_number'))
    send_delivery = models.BooleanField(null=True, verbose_name=_('send_delivery'))
    send_delivery_date = models.DateField(null=True, verbose_name=_('send_delivery_date'))
    confirmed_based_7_day = models.BooleanField(null=True, verbose_name=_('confirmed_based_7_day'))
    confirm_date = models.DateField(null=True, verbose_name=_('confirm_date'))
    collector = models.CharField(max_length=50, null=True, verbose_name=_('collector'))

    objects = OrderListDatatableModelManager()

    @classmethod
    def select_all(cls, param=None):
        if not param:
            return cls.objects.all().using('dw')
        elif param == 'filter1':
            return cls.packing__not_delete()
        elif param == 'filter2':
            return cls.packing__not_delete__not_send()
        elif param == 'filter3':
            return cls.financial_confirm__not_delete__not_packing__date_create_over4()
        elif param == 'filter4':
            return cls.need_financial_confirm__not_confirm__not_delete()

    @classmethod
    def packing__not_delete(cls):
        return cls.objects.filter(paking=1, delete_doc=0).using('dw')

    @classmethod
    def packing__not_delete__not_send(cls):
        return cls.objects.filter(paking=1, delete_doc=0, send_delivery=0).using('dw')

    @classmethod
    def financial_confirm__not_delete__not_packing__date_create_over4(cls):
        import datetime
        from django.utils.timezone import utc
        now = datetime.datetime.utcnow().replace(tzinfo=utc)
        four_day = datetime.timedelta(days=4)
        timediff = now - four_day
        return cls.objects.filter(Q(financial_confirm=1) | Q(financial_cond="نیاز به تایید مالی ندارد"),
                                  paking=0, delete_doc=0, new_doc_date__lt=timediff).using('dw')

    @classmethod
    def need_financial_confirm__not_confirm__not_delete(cls):
        return cls.objects.filter(financial_cond='نیاز به تایید مالی دارد', financial_confirm=0, delete_doc=0).using('dw')

    @property
    def jalali_delete_doc_date(self):
        return to_jalali_date(self.delete_doc_date)

    @property
    def jalali_new_doc_date(self):
        return to_jalali_date(self.new_doc_date)

    @property
    def jalali_send_delivery_date(self):
        return to_jalali_date(self.send_delivery_date)

    @property
    def jalali_confirm_date(self):
        return to_jalali_date(self.confirm_date)

    class Meta:
        managed = False
        db_table = 'CargoListView'


class DimOrderModelManager(Manager):
    def get_queryset(self):
        return super(DimOrderModelManager, self).get_queryset().all().using('micmod_dw')


class DimOrder(models.Model):
    order_id = models.CharField(max_length=100, primary_key=True)

    objects = DimOrderModelManager()

    class Meta:
        managed = False
        db_table = "dim_order"

    @classmethod
    def order_inway(cls, sku_):
        qry = f'''
        select order_id, sku, sum(cast(remaining_qty as int)) as customer_inway, sum(cast(kasri_remained as int)) as kasri_inway from dim_order
        where sku = {sku_} and status_coef>2
        group by sku, order_id
        '''



        qry = f'''
        SELECT 
    ROW_NUMBER() OVER (ORDER BY customer_type) AS order_id,
    customer_type,
    SUM(remaining_qty) AS total_remaining_qty
FROM [MicmodDW].[dbo].[dim_order]
WHERE sku = {sku_} 
  AND status_str = N'جاری'
GROUP BY customer_type
'''

        order_inway_list = [x for x in cls.objects.raw(qry)]
        return order_inway_list
        for item in cls.objects.raw(qry):
            return item


class DimCustomerModelManager(Manager):
    def get_queryset(self):
        return super(DimCustomerModelManager, self).get_queryset().all().using('micmod_dw')


class DimCustomer(models.Model):
    customer_id = models.CharField(max_length=100, primary_key=True)

    objects = DimCustomerModelManager()

    class Meta:
        managed = False
        db_table = "dim_order"

    @classmethod
    def get_customer(cls, party_id):
        qry = f'''
        select * from dim_customer
        where party_id = {party_id}
        '''

        return cls.objects.raw(qry)
