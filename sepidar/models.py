import datetime
from typing import Tuple

from django.db import models, connections, connection
from django.db.models import Q
from translator import get_text as _
from tools.form_tools import select_cquery
from django.conf import settings


class BaseData():
    current_year_ref_ = None
    @classmethod
    def current_year_ref(cls):
        if cls.current_year_ref_ == None:
            cls.current_year_ref_ = int(select_cquery("select max(FiscalYearId) as current_year from fmk.FiscalYear","sepidar").current_year)
        return cls.current_year_ref_


import core.models
import dw.models


class Dl(models.Model):
    DLId = models.BigIntegerField(primary_key=True)
    Code = models.CharField(max_length=40)
    Title = models.CharField(max_length=250)
    Title_En = models.CharField(max_length=250)

    @staticmethod
    def get_list(text):
        from extra_data.models import Customer
        if text.isdigit():
            customer_filter = Q(sepidar_dl_id__icontains=text) | Q(sepidar_dl_code__icontains=text) | Q(sepidar_party_id__icontains=text)
        else:
            customer_filter = Q(title__icontains=text) | Q(name__icontains=text) | Q(last_name__icontains=text)
        res = Customer.objects.filter(customer_filter).filter(active=True)
        return res
        res = Dl.objects.using('sepidar').raw(f"""
Select TOP 10 dl.Code as code,dl.Title as name,dl.DLId,p.* 
From [ACC].[DL] as dl 
Join [GNR].[Party] as p on dl.DLId = p.DLRef
Where (dl.Code like '%%{text}%%' or dl.Title like '%%{text}%%' ) and IsCustomer='True'""")
        return res

    @staticmethod
    def get_accounting_list(f):
        if f == 'mande_positive':
            return Dl.objects.using('sepidar').raw("""
            select 
                Cur.Title cur_ref,
                DL.Code DLId,
                VI.AccountSLRef,
                DL.Title dl_title,
            	sum(VI.CurrencyCredit) sum_credit,
            	sum(VI.CurrencyDebit) sum_debit, 
            	sum(VI.CurrencyDebit)-sum(VI.CurrencyCredit) in_line,
            	MAX(V.Date) last_voucher_date
            from [ACC].[VoucherItem] VI
            Join [ACC].[Voucher] V on V.VoucherId = VI.VoucherRef
            Join [ACC].[DL] DL on DL.DLId = VI.DLRef
            Join [GNR].[Currency] Cur on Cur.CurrencyID = VI.CurrencyRef
            where VI.AccountSLRef = 404 and VI.CurrencyRef > 1
            Group by Cur.Title,DL.Code,DL.Title,VI.AccountSLRef
            HAVING SUM(VI.CurrencyDebit) - SUM(VI.CurrencyCredit) > 0
            order by DL.Title
                    """)
        else:
            return Dl.objects.using('sepidar').raw("""
            SELECT
        Cur.Title AS cur_ref,
        DL.Code AS DLId,
        VI.AccountSLRef,
        DL.Title AS dl_title,
        SUM(VI.CurrencyCredit) AS sum_credit,
        SUM(VI.CurrencyDebit) AS sum_debit,
        SUM(VI.CurrencyDebit) - SUM(VI.CurrencyCredit) AS in_line,
        MAX(V.Date) AS last_voucher_date
    FROM [ACC].[VoucherItem] VI
    JOIN [ACC].[Voucher] V ON V.VoucherId = VI.VoucherRef
    JOIN [ACC].[DL] DL ON DL.DLId = VI.DLRef
    JOIN [GNR].[Currency] Cur ON Cur.CurrencyID = VI.CurrencyRef
    WHERE VI.AccountSLRef = 404 AND VI.CurrencyRef > 1
    GROUP BY Cur.Title, DL.Code, DL.Title, VI.AccountSLRef
    ORDER BY DL.Title;
    """)

    @staticmethod
    def get_sales_history_list(kwargs):
        customer_code = kwargs.get('customer_code')
        item_code = kwargs.get('item_code')
        part = kwargs.get('part')
        if not (customer_code or item_code or kwargs.get('g_p') or part):
            return None
        dl_filter = ""
        part_filter = ""
        if customer_code:
            try:
                s = float(customer_code)
                dl_filter = f" and dl.Code={customer_code}"
            except:
                dl_filter = " and dl.title like N'%%" + customer_code.replace('ی', 'ي').replace("ک", "ك") + "%%'"
        item_filter = ""
        if item_code:
            try:
                s = float(item_code)
                item_filter = f" and Item.Code={item_code}"
            except:
                pass

        if part:
            part_filter = " and Item.title like N'%%" + part.replace('ی', 'ي').replace("ك", "ک").replace('%', '%%') + "%%'"
        # if item_code:
        #     try:
        #         s = float(item_code)
        #         item_filter = f" and Item.Code={item_code}"
        #     except:
        #         item_filter = " and Item.title like N'%%" + item_code.replace('ی', 'ي').replace("ك", "ک") + "%%'"
        g_p = kwargs.get('g_p')
        if g_p:
            g_p = str(g_p).lower().replace('ی', 'ي').replace("ک", "ك")
        qry = f"""
select top 3000
        docs.Date,docs.Number,docs.coef,docs.doc_type,docs.Fee,docs.itemId,docs.NetPrice,docs.NetPriceInBaseCurrency,docs.Price,docs.PriceInBaseCurrency,docs.Quantity,docs.Rate
        ,st.Number sales_type_code, Convert(nvarchar(20),st.Title) sales_type
        ,p.CreationDate customer_creation_date,dl.Title customer_title,dl.Code customer_code ,dl.DLId
        ,g1.Code sales_user_code, g1.Title sales_user_group
        ,item.Code item_code, Item.Title item_title
        --,g_p.Code purchase_group_code, g_p.Title purchase_group, g_s.Code sales_group_code, g_s.Title sales_group
        ,fy.Title year_title
        ,curr.Title currency
from
(
select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
        ,II.ItemRef, II.Quantity,II.Fee,II.NetPrice,II.NetPriceInBaseCurrency,II.Price,II.PriceInBaseCurrency,II.InvoiceItemID itemId
        ,1 as coef,'invoice' as doc_type
from [SLS].[Invoice] as I Join [SLS].[InvoiceItem] as II on II.InvoiceRef = I.InvoiceId
union
select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
        ,II.ItemRef, II.Quantity,II.Fee,II.NetPrice,II.NetPriceInBaseCurrency,II.Price,II.PriceInBaseCurrency,II.QuotationItemID itemId
        ,0 as coef,'quotation' as doc_type
from [SLS].[Quotation] as I Join [SLS].[QuotationItem] as II on II.QuotationRef = I.QuotationId
union
select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
        ,II.ItemRef, II.Quantity,II.Fee,-II.NetPrice,-II.NetPriceInBaseCurrency,-II.Price,-II.PriceInBaseCurrency,II.ReturnedInvoiceItemID itemId
        ,-1 as coef,'returned_invoice' as doc_type
from [SLS].[ReturnedInvoice] as I Join [SLS].[ReturnedInvoiceItem] as II on II.ReturnedInvoiceRef = I.ReturnedInvoiceId
)as docs
join [SLS].[SaleType] as st on st.SaleTypeId = docs.SaleTypeRef
join [INV].[Item] as Item on Item.ItemID = docs.ItemRef
left join [GNR].[Grouping] as g_p on g_p.GroupingID = Item.PurchaseGroupRef
--left join [GNR].[Grouping] as g_s on g_s.GroupingID = Item.SaleGroupRef
join [GNR].[Party] as p on p.PartyId = docs.CustomerPartyRef join [ACC].[DL] as dl on dl.DLId = p.DLRef
left join [GNR].[Grouping] as g1 on g1.GroupingID = p.CustomerGroupingRef
join [FMK].[FiscalYear] as fy on fy.FiscalYearId = docs.FiscalYearRef
join [GNR].[Currency] as curr on curr.CurrencyID = docs.CurrencyRef
where 1=1 {dl_filter} 
          {item_filter}
          {part_filter}
          {" and g_p.Title like N'%%" + g_p +"%%'" if g_p else ''}
          {" and docs.doc_type like N'%%" + kwargs.get('doc_type') +"%%'" if kwargs.get('doc_type') else ''}

order by docs.Date desc
            """
        qs = Dl.objects.using('sepidar').raw(qry)
        return qs

    @staticmethod
    def get_sales_history_list_qi(kwargs):
        customer_code = kwargs.get('customer_code')
        item_code = kwargs.get('item_code')
        part = kwargs.get('part')
        if not (customer_code or item_code or kwargs.get('g_p') or part):
            return None
        dl_filter = ""
        part_filter = ""
        if customer_code:
            try:
                s = float(customer_code)
                dl_filter = f" and dl.Code={customer_code}"
            except:
                dl_filter = " and dl.title like N'%%" + customer_code.replace('ی', 'ي').replace("ك", "ک") + "%%'"
        item_filter = ""
        if item_code:
            try:
                s = float(item_code)
                item_filter = f" and Item.Code={item_code}"
            except:
                pass

        if part:
            part_filter = " and Item.title like N'%%" + part.replace('ی', 'ي').replace("ك", "ک") + "%%'"
        # if item_code:
        #     try:
        #         s = float(item_code)
        #         item_filter = f" and Item.Code={item_code}"
        #     except:
        #         item_filter = " and Item.title like N'%%" + item_code.replace('ی', 'ي').replace("ك", "ک") + "%%'"
        g_p = kwargs.get('g_p')
        if g_p:
            g_p = str(g_p).lower().replace('ی', 'ي').replace("ك", "ک")
        qry = f"""
    select top 3000
            docs.Date,docs.Number as pk,docs.coef,docs.doc_type,docs.Fee,docs.itemId as goods_code_fk,docs.NetPrice,docs.NetPriceInBaseCurrency,docs.Price,docs.PriceInBaseCurrency,docs.Quantity as quantity,docs.Rate
            ,st.Numb
            
            er sales_type_code, Convert(nvarchar(20),st.Title) sales_type
            ,p.CreationDate customer_creation_date,dl.Title customer_title,dl.Code customer_code ,dl.DLId
            ,g1.Code sales_user_code, g1.Title sales_user_group
            ,item.Code item_code, Item.Title item_title
            --,g_p.Code purchase_group_code, g_p.Title purchase_group, g_s.Code sales_group_code, g_s.Title sales_group
            ,fy.Title year_title
            ,curr.Title currency
    from
    (
    select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
            ,II.ItemRef, II.Quantity,II.Fee,II.NetPrice,II.NetPriceInBaseCurrency,II.Price,II.PriceInBaseCurrency,II.InvoiceItemID itemId
            ,1 as coef,'invoice' as doc_type
    from [SLS].[Invoice] as I Join [SLS].[InvoiceItem] as II on II.InvoiceRef = I.InvoiceId
    union
    select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
            ,II.ItemRef, II.Quantity,II.Fee,II.NetPrice,II.NetPriceInBaseCurrency,II.Price,II.PriceInBaseCurrency,II.QuotationItemID itemId
            ,0 as coef,'quotation' as doc_type
    from [SLS].[Quotation] as I Join [SLS].[QuotationItem] as II on II.QuotationRef = I.QuotationId
    union
    select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
            ,II.ItemRef, II.Quantity,II.Fee,-II.NetPrice,-II.NetPriceInBaseCurrency,-II.Price,-II.PriceInBaseCurrency,II.ReturnedInvoiceItemID itemId
            ,-1 as coef,'returned_invoice' as doc_type
    from [SLS].[ReturnedInvoice] as I Join [SLS].[ReturnedInvoiceItem] as II on II.ReturnedInvoiceRef = I.ReturnedInvoiceId
    )as docs
    join [SLS].[SaleType] as st on st.SaleTypeId = docs.SaleTypeRef
    join [INV].[Item] as Item on Item.ItemID = docs.ItemRef
    left join [GNR].[Grouping] as g_p on g_p.GroupingID = Item.PurchaseGroupRef
    --left join [GNR].[Grouping] as g_s on g_s.GroupingID = Item.SaleGroupRef
    join [GNR].[Party] as p on p.PartyId = docs.CustomerPartyRef join [ACC].[DL] as dl on dl.DLId = p.DLRef
    left join [GNR].[Grouping] as g1 on g1.GroupingID = p.CustomerGroupingRef
    join [FMK].[FiscalYear] as fy on fy.FiscalYearId = docs.FiscalYearRef
    join [GNR].[Currency] as curr on curr.CurrencyID = docs.CurrencyRef
    where 1=1 {dl_filter} 
              {item_filter}
              {part_filter}
              {" and g_p.Title like N'%%" + g_p + "%%'" if g_p else ''}
              {" and docs.doc_type like N'%%" + kwargs.get('doc_type') + "%%'" if kwargs.get('doc_type') else ''}

    order by docs.Date desc
                """
        qs = Dl.objects.using('sepidar').raw(qry)
        return qs

    @staticmethod
    def get_dl(code):
        res = Dl.objects.using('sepidar').raw(f"""
Select TOP 1 dl.Code as code,dl.Title as name,dl.DLId,p.* 
From [ACC].[DL] as dl 
Join [GNR].[Party] as p on dl.DLId = p.DLRef
Where (dl.Code = '{code}' and IsCustomer='True')""")
        return res

    @staticmethod
    def get_dl_phones(code):
        res = Dl.objects.using('sepidar').raw(f"""
select dl.Code,dl.Title,p.Name,p.LastName,p.Website,p.IsCustomer,pf.party_phones,pr.related_emails,pr.related_phones from 
  acc.dl as dl 
  left join gnr.Party p on p.DLRef = dl.DLId
  left join 
  (
  select distinct PartyRef,
  SUBSTRING(
        (
            SELECT ','+pf2.Phone  AS [text()]
            FROM gnr.PartyPhone pf2
            WHERE pf2.PartyRef = pf1.PartyRef
            ORDER BY pf2.PartyRef
            FOR XML PATH (''), TYPE
        ).value('text()[1]','nvarchar(max)'), 2, 1000) [party_phones]
		from GNR.PartyPhone as pf1
) as pf on pf.PartyRef = p.PartyId
left join 
(
  select distinct PartyRef,
  SUBSTRING(
        (
            SELECT ','+pr2.Name+'-'+pr2.Phone  AS [text()]
            FROM gnr.PartyRelated pr2
            WHERE pr2.PartyRef = pr1.PartyRef
            ORDER BY pr2.PartyRef
            FOR XML PATH (''), TYPE
        ).value('text()[1]','nvarchar(max)'), 2, 1000) [related_phones],
  SUBSTRING(
        (
            SELECT ','+pr2.Name+'-'+pr2.Email  AS [text()]
            FROM gnr.PartyRelated pr2
            WHERE pr2.PartyRef = pr1.PartyRef
            ORDER BY pr2.PartyRef
            FOR XML PATH (''), TYPE
        ).value('text()[1]','nvarchar(max)'), 2, 1000) [related_emails]
from GNR.PartyRelated as pr1) as pr on pr.PartyRef = p.PartyId
where dl.code = '{code}'        
        """)
    def get_qs(self, index_id, ):
        qs = self.objects.get_queryset()
        sql = "Dl.DLId IN (SELECT UNNEST(myapp_model_a.pk_values) FROM myapp_model_a WHERE myapp_model_a.id='%s')" % index_id
        return qs.extra(where=[sql])


class InventoryPurchaseInvoice(models.Model):
    InventoryPurchaseInvoiceID = models.BigIntegerField(primary_key=True)

    @classmethod
    def get_buy_history_list(cls, param):

        creator_code = param.get('creator_code')
        item_code = param.get('item_code')
        part = param.get('part')

        # if not (creator_code or item_code or part):
        #     return None
        dl_filter = ""
        part_filter = ""
        if creator_code:
            try:
                s = float(creator_code)
                dl_filter = f" and u.UserID={creator_code}"
            except:
                dl_filter = " and u.Name like N'%%" + creator_code.replace('ی', 'ي').replace("ک", "ك") + "%%'"
        item_filter = ""
        if item_code:
            try:
                s = float(item_code)
                item_filter = f" and item.Code='{item_code}'"
            except:
                pass

        if part:
            part_filter = " and item.title like N'%%" + part.replace('ی', 'ي').replace("ك", "ک") + "%%'"


        "str".replace('ی', 'ي').replace("ک", "ك")
        condition = ''
        qry = f"""
            select top(5000) ipi.InventoryPurchaseInvoiceID, ipi.Number number, ipi.Date, cu.Title currencytitle, ipi.CurrencyRate currencyrate, 
            ipii.Quantity, ipii.Fee, dl.Title, dl.Code, item.Code, item.Title, u.Name creator
    From [Micromodern1400].[INV].[InventoryPurchaseInvoice] as ipi
    LEFT JOIN [Micromodern1400].[INV].[InventoryPurchaseInvoiceItem] as ipii on ipii.InventoryPurchaseInvoiceRef = ipi.InventoryPurchaseInvoiceID
    LEFT JOIN [Micromodern1400].ACC.DL as dl on dl.DLId = ipi.VendorDLRef
    LEFT JOIN [Micromodern1400].INV.Item as item on item.ItemID = ipii.ItemRef
    LEFT JOIN [Micromodern1400].GNR.Currency as cu on cu.CurrencyID = ipi.CurrencyRef
    LEFT JOIN [Micromodern1400].[FMK].[User] as u on u.UserID = ipi.Creator
    where 1=1 {dl_filter} 
          {item_filter}
          {part_filter}

    order by ipi.InventoryPurchaseInvoiceID desc
            """

        qs = cls.objects.using('sepidar').raw(qry)
        return qs

class SalesHistory(models.Model):
    # id = models.BigIntegerField(primary_key=True)
    Date = models.DateField(verbose_name=_('date'))
    itemId = models.BigIntegerField(primary_key=True)
    Number = models.CharField(max_length=50)
    FiscalYearRef = models.IntegerField()
    CustomerPartyRef = models.IntegerField()
    SaleTypeRef = models.IntegerField()
    CurrencyRef = models.IntegerField()
    Rate = models.FloatField()
    ItemRef = models.CharField(max_length=150)
    Quantity = models.FloatField()
    Fee = models.FloatField()
    NetPrice = models.FloatField()
    NetPriceInBaseCurrency = models.FloatField()
    Price = models.FloatField()
    PriceInBaseCurrency = models.FloatField()
    coef = models.IntegerField()
    doc_type = models.CharField(max_length=50)
    sales_type_code = models.CharField(max_length=50)
    sales_type = models.CharField(max_length=50)
    customer_creation_date = models.CharField(max_length=50)
    customer_title = models.CharField(max_length=150)
    customer_code = models.BigIntegerField()
    DLId = models.IntegerField()
    sales_user_code = models.CharField(max_length=50)
    sales_user_group = models.CharField(max_length=50)
    item_code = models.BigIntegerField()
    item_title = models.CharField(max_length=250)
    purchase_group_code = models.CharField(max_length=50)
    purchase_group = models.CharField(max_length=50)
    sales_group_code = models.CharField(max_length=50)
    sales_group = models.CharField(max_length=50)
    year_title = models.CharField(max_length=50)

    class Meta:
        db_table = '[SalesHistory]'

    @staticmethod
    def get_sales_history_list(dl_code=10023,item_code=881):
        qry = """
select dl.DLId,docs.itemId id
    --docs.*
	--,st.Number sales_type_code, st.Title sales_type
	--,p.CreationDate customer_creation_date,dl.Title customer_title,dl.Code customer_code ,dl.DLId
	--,g1.Code sales_user_code, g1.Title sales_user_group
	--,item.Code item_code, Item.Title item_title
	--,g_p.Code purchase_group_code, g_p.Title purchase_group, g_s.Code sales_group_code, g_s.Title sales_group
	--,fy.Title year_title
from 
(
select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
	,II.ItemRef, II.Quantity,II.Fee,II.NetPrice,II.NetPriceInBaseCurrency,II.Price,II.PriceInBaseCurrency,II.InvoiceItemID itemId
	,1 as coef,'invoice' as doc_type
from [SLS].[Invoice] as I Join [SLS].[InvoiceItem] as II on II.InvoiceRef = I.InvoiceId
union
select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
	,II.ItemRef, II.Quantity,II.Fee,II.NetPrice,II.NetPriceInBaseCurrency,II.Price,II.PriceInBaseCurrency,II.QuotationItemID itemId
	,0 as coef,'quotation' as doc_type
from [SLS].[Quotation] as I Join [SLS].[QuotationItem] as II on II.QuotationRef = I.QuotationId
union
select I.Date,I.Number,I.FiscalYearRef,I.CustomerPartyRef,I.SaleTypeRef, I.CurrencyRef,I.Rate
	,II.ItemRef, II.Quantity,II.Fee,II.NetPrice,II.NetPriceInBaseCurrency,II.Price,II.PriceInBaseCurrency,II.ReturnedInvoiceItemID itemId
	,-1 as coef,'returned_invoice' as doc_type
from [SLS].[ReturnedInvoice] as I Join [SLS].[ReturnedInvoiceItem] as II on II.ReturnedInvoiceRef = I.ReturnedInvoiceId
)as docs
join [SLS].[SaleType] as st on st.SaleTypeId = docs.SaleTypeRef
join [INV].[Item] as Item on Item.ItemID = docs.ItemRef
join [GNR].[Grouping] as g_p on g_p.GroupingID = Item.PurchaseGroupRef
join [GNR].[Grouping] as g_s on g_s.GroupingID = Item.SaleGroupRef
join [GNR].[Party] as p on p.PartyId = docs.CustomerPartyRef join [ACC].[DL] as dl on dl.DLId = p.DLRef
join [GNR].[Grouping] as g1 on g1.GroupingID = p.CustomerGroupingRef
join [FMK].[FiscalYear] as fy on fy.FiscalYearId = docs.FiscalYearRef
            """
        # qs = self.objects.get_queryset()
        print(f'start qry{datetime.datetime.now()}')
        qs = SalesHistory.objects.using('sepidar_view').raw("select * from SalesHistory where customer_code=10023 and item_code = 881")#.filter(customer_code=10023,item_code=881)
        print([x for x in qs])
        print(f'end qry{datetime.datetime.now()}')
        # print(qs)
        # qs = qs.filter(DLId__in=RawSQL(qry,[]))
        return qs

class Item(models.Model):
    code = models.CharField(primary_key=True,max_length=250)
    customer_qry = """
select 
d.DLId as code,
d.DLId as sepidar_dl_id,
d.Code as sepidar_dl_code,
p.PartyId as sepidar_party_id,
d.Title as title,
p.Name as name,
p.LastName as last_name,
p.Type as type,
p.IdentificationCode as national_code,
p.Email as email,
pf.Phone as phone,
p.CustomerGroupingRef as customer_group,
pr.Title as province,
isnull(l2.Title,l.Title) as location,
isnull(pa.address,l.Title) as address,
RTRIM(LTRIM(isnull(e.StringColumn2,p.Website))) as senf,
RTRIM(LTRIM(isnull(e.StringColumn3,null))) as sub_senf,
RTRIM(LTRIM(isnull(e.StringColumn4,null))) as introduction_method,
RTRIM(LTRIM(isnull(e.StringColumn5,null))) as marketer,
RTRIM(LTRIM(isnull(e.StringColumn6,null))) as introducer,
isnull(e.DateColumn1,null) as revival_date,
isnull(e.IntegerColumn1,p.MaximumCredit) as max_credit,
isnull(e.IntegerColumn2,null) as credit_with_doc

from acc.dl as d
join gnr.Party as p on p.DLRef = d.DLId
left join [FMK].[ExtraData] as e on e.EntityRef = p.PartyId
left join (select pf.PartyRef, max(pf.Phone) as phone from  gnr.PartyPhone as pf group by pf.PartyRef) as pf on pf.PartyRef = p.PartyId
left join (select pa.PartyRef, min(pa.PartyAddressId) as party_address_id from gnr.PartyAddress as pa group by pa.PartyRef) as paa on paa.PartyRef = p.PartyId
left join gnr.PartyAddress as pa on paa.party_address_id = pa.PartyAddressId
left join gnr.Location as l2 on l2.LocationId = pa.LocationRef
left join GNR.Location as l on l.Title = isnull(pa.Title,isnull(e.StringColumn1,p.EconomicCode)) and l.Code is not null
left join gnr.Location as pr on pr.LocationId = l.Parent
where EntityTypeName = 'SG.General.PartyManagement.Common.DsParty' and p.IsCustomer=1
    """

    @staticmethod
    def get_all_provience():
        return Item.objects.raw("select title, locationid as code, locationid as location_id from gnr.Location where code is not null", using="sepidar")


    @staticmethod
    def get_all_customer_groups():
        return Item.objects.raw("select GroupingID as code, * from gnr.Grouping as g  where g.EntityType = 'SG.General.PartyManagement.Common.PartyCustomerGroup'", using="sepidar")

    @staticmethod
    def get_all_senf(max_sepidar_party_id=0):
        return Item.objects.raw(
            f"select distinct p.senf as code from({Item.customer_qry} and p.PartyId > {max_sepidar_party_id}) as p where p.senf is not null and p.senf!=''", using="sepidar")

    @staticmethod
    def get_all_sub_senf(max_sepidar_party_id):
        return Item.objects.raw(
            f"select distinct p.sub_senf as code from({Item.customer_qry} and p.PartyId > {max_sepidar_party_id}) as p where p.sub_senf is not null and p.sub_senf!=''", using="sepidar")

    @staticmethod
    def get_all_introduction_method(max_sepidar_party_id):
        return Item.objects.raw(
            f"select distinct p.introduction_method as code from({Item.customer_qry} and p.PartyId > {max_sepidar_party_id}) as p where p.introduction_method is not null and p.introduction_method!=''", using="sepidar")

    @staticmethod
    def get_all_introducer(max_sepidar_party_id):
        return Item.objects.raw(
            f"select distinct p.introducer code from({Item.customer_qry} and p.PartyId > {max_sepidar_party_id}) as p where p.introducer is not null and p.introducer!=''", using="sepidar")

    @staticmethod
    def get_all_marketer(max_sepidar_party_id):
        return Item.objects.raw(
            f"select distinct p.marketer as code from({Item.customer_qry} and p.PartyId > {max_sepidar_party_id}) as p where p.marketer is not null and p.marketer!=''", using="sepidar")

    @staticmethod
    def get_all_customers(max_sepidar_party_id):
        return Item.objects.raw(
            f"{Item.customer_qry} and p.PartyId > {max_sepidar_party_id}",using="sepidar")

    @staticmethod
    def get_all_customers_in_range(max_sepidar_parties: Tuple):
        return Item.objects.raw(
            f"{Item.customer_qry} and p.PartyId IN {max_sepidar_parties}", using="sepidar")

    @staticmethod
    def get_all_items(from_id):
        qry = f"select Code as code, * from inv.item where itemid > {from_id}"
        res = Item.objects.raw(qry, using='sepidar')
        return res

    @staticmethod
    def get_all_purchase_groups():
        qry = f"select Code as code, * from gnr.Grouping where EntityType = 'SG.Inventory.ItemManagement.Common.ItemPurchaseGroup'"
        res = Item.objects.raw(qry, using='sepidar')
        return res

    @staticmethod
    def get_all_sales_groups():
        qry = f"select Code as code, * from gnr.Grouping where EntityType = 'SG.Inventory.ItemManagement.Common.ItemSaleGroup'"
        res = Item.objects.raw(qry, using='sepidar')
        return res

    @staticmethod
    def get_items(text, party_id=''):
        text = text.replace('%', '%%')
        qry =f"""
 item.Code AS code,item.ItemID as itemid, item.Title AS title, invoice_1.Date AS f_date_cust, invoice_1.Fee AS f_fee_cust, invoice_1.qty AS f_qty_cust, 
    						 invoice_2.avg_fee AS avg_price, invoice_2.min_fee AS min_price,invoice_2.max_fee AS max_price,
                             invoice_2.qty AS f_qty_all, sum_stock.total_quantity AS stock_qty, sum_stock_res.total_quantity as stock_res_qty,
							 quotation_1.Date as quotation_date, quotation_1.Fee as quotation_fee, quotation_1.Quantity as quotation_qty
    FROM            INV.Item AS item LEFT OUTER JOIN
                                 (SELECT        i_invoice.ItemRef, invoice.Date, i_invoice.Fee, i_invoice.Quantity as qty
                                   FROM            SLS.InvoiceItem AS i_invoice INNER JOIN
                                                             SLS.Invoice AS invoice ON i_invoice.InvoiceRef = invoice.InvoiceId INNER JOIN
                                                                 (SELECT        InvI.ItemRef, MAX(Inv.InvoiceId) AS max_id
                                                                   FROM            SLS.Invoice AS Inv INNER JOIN
                                                                                             SLS.InvoiceItem AS InvI ON Inv.InvoiceId = InvI.InvoiceRef AND Inv.CustomerPartyRef = {party_id}
                                                                   GROUP BY InvI.ItemRef) AS mx ON i_invoice.ItemRef = mx.ItemRef AND invoice.InvoiceId = mx.max_id) AS invoice_1 ON item.ItemID = invoice_1.ItemRef LEFT OUTER JOIN
                                 (SELECT        invi.ItemRef, AVG(invi.Fee) as avg_fee, sum(invi.Quantity) as qty,min(invi.Fee) as min_Fee, max(invi.Fee) as max_Fee
                                   FROM            SLS.Invoice AS inv INNER JOIN
                                                                 SLS.InvoiceItem AS InvI ON Inv.InvoiceId = InvI.InvoiceRef
    															 where inv.Date > DATEADD(DAY,-60,GETDATE())
                                                                   GROUP BY InvI.ItemRef) AS invoice_2 ON item.ItemID = invoice_2.ItemRef LEFT OUTER JOIN
                                 (SELECT        ItemRef, SUM(Quantity) AS total_quantity
                                   FROM            INV.ItemStockSummary
                                   WHERE        (FiscalYearRef = {settings.SEPIDAR_STOCK_NUMBER}) and StockRef in (2, 40)
                                   GROUP BY ItemRef) AS sum_stock ON sum_stock.ItemRef = item.ItemID LEFT OUTER JOIN
                                 (SELECT        ItemRef, SUM(Quantity) AS total_quantity
                                   FROM            INV.ItemStockSummary
                                   WHERE        (FiscalYearRef = {settings.SEPIDAR_STOCK_NUMBER}) and StockRef in (50,51,53,54,60,28,84,73,74,75,76,77,78,85)
                                   GROUP BY ItemRef) AS sum_stock_res ON sum_stock_res.ItemRef = item.ItemID LEFT OUTER JOIN
                                 (SELECT        InvI.ItemRef, SUM(InvI.Quantity) AS total_quantity
                                   FROM            SLS.Invoice AS Inv INNER JOIN
                                                             SLS.InvoiceItem AS InvI ON Inv.InvoiceId = InvI.InvoiceRef
                                   WHERE        (Inv.CustomerPartyRef = {party_id})
                                   GROUP BY InvI.ItemRef) AS sell_1 ON sell_1.ItemRef = item.ItemID LEFT OUTER JOIN
                                 (SELECT        InvI.ItemRef, SUM(InvI.Quantity) AS total_quantity
                                   FROM            SLS.Invoice AS Inv INNER JOIN
                                                             SLS.InvoiceItem AS InvI ON Inv.InvoiceId = InvI.InvoiceRef
                                   GROUP BY InvI.ItemRef) AS sell_2 ON sell_2.ItemRef = item.ItemID LEFT OUTER JOIN
                                 (SELECT        i_quotation.ItemRef, quotation.Date, i_quotation.Fee, i_quotation.Quantity
                                   FROM            SLS.QuotationItem AS i_quotation INNER JOIN
                                                             SLS.Quotation AS quotation ON i_quotation.QuotationRef = quotation.QuotationId INNER JOIN
                                                                 (SELECT        quI.ItemRef, MAX(qu.QuotationId) AS max_id
                                                                   FROM            SLS.Quotation AS qu INNER JOIN
                                                                                             SLS.QuotationItem AS quI ON qu.QuotationId = quI.QuotationRef AND qu.CustomerPartyRef = {party_id}
                                                                   GROUP BY quI.ItemRef) AS mx ON i_quotation.ItemRef = mx.ItemRef AND quotation.QuotationId = mx.max_id) AS quotation_1 ON item.ItemID = quotation_1.ItemRef

        """
        final_qry = f"""select * from ( (select top 1 {qry} WHERE (item.Code = '{text}')) union (""" if text.isnumeric() else ""
        final_qry += f"""
        select top 10 {qry}
        WHERE ((item.Title LIKE '%%{text}%%') OR (item.Code LIKE '%%{text}%%'))  
        ORDER BY f_date_cust desc,quotation_date desc,stock_qty DESC, f_qty_cust DESC, f_qty_all DESC    
        """
        if text.isnumeric():
            final_qry += ")) as qry ORDER BY f_date_cust desc,quotation_date desc,stock_qty DESC, f_qty_cust DESC, f_qty_all DESC "
        res = Item.objects.raw(final_qry, using='sepidar')
        return res

    @staticmethod
    def get_item(code, party_id=-1):
        party_id = party_id or -1
        qry = f"""
    SELECT        TOP (1) item.Code AS code,item.ItemID as itemid, item.Title AS title, invoice_1.Date AS f_date_cust, invoice_1.Fee AS f_fee_cust, invoice_1.qty AS f_qty_cust, 
    						 invoice_2.avg_fee AS avg_price, invoice_2.min_fee AS min_price,invoice_2.max_fee AS max_price,
                             invoice_2.qty AS f_qty_all, sum_stock.total_quantity AS stock_qty, sum_stock_res.total_quantity as stock_res_qty,
							 quotation_1.Date as quotation_date, quotation_1.Fee as quotation_fee, quotation_1.Quantity as quotation_qty
    FROM            INV.Item AS item LEFT OUTER JOIN
                                 (SELECT        i_invoice.ItemRef, invoice.Date, i_invoice.Fee, i_invoice.Quantity as qty
                                   FROM            SLS.InvoiceItem AS i_invoice INNER JOIN
                                                             SLS.Invoice AS invoice ON i_invoice.InvoiceRef = invoice.InvoiceId INNER JOIN
                                                                 (SELECT        InvI.ItemRef, MAX(Inv.InvoiceId) AS max_id
                                                                   FROM            SLS.Invoice AS Inv INNER JOIN
                                                                                             SLS.InvoiceItem AS InvI ON Inv.InvoiceId = InvI.InvoiceRef AND Inv.CustomerPartyRef = {party_id}
                                                                   GROUP BY InvI.ItemRef) AS mx ON i_invoice.ItemRef = mx.ItemRef AND invoice.InvoiceId = mx.max_id) AS invoice_1 ON item.ItemID = invoice_1.ItemRef LEFT OUTER JOIN
                                 (SELECT        invi.ItemRef, AVG(invi.Fee) as avg_fee, sum(invi.Quantity) as qty,min(invi.Fee) as min_Fee, max(invi.Fee) as max_Fee
                                   FROM            SLS.Invoice AS inv INNER JOIN
                                                                 SLS.InvoiceItem AS InvI ON Inv.InvoiceId = InvI.InvoiceRef
    															 where inv.Date > DATEADD(DAY,-60,GETDATE())
                                                                   GROUP BY InvI.ItemRef) AS invoice_2 ON item.ItemID = invoice_2.ItemRef LEFT OUTER JOIN
                                 (SELECT        ItemRef, SUM(Quantity) AS total_quantity
                                   FROM            INV.ItemStockSummary
                                   WHERE        (FiscalYearRef = {settings.SEPIDAR_STOCK_NUMBER}) and StockRef in (2, 40)
                                   GROUP BY ItemRef) AS sum_stock ON sum_stock.ItemRef = item.ItemID LEFT OUTER JOIN
                                 (SELECT        ItemRef, SUM(Quantity) AS total_quantity
                                   FROM            INV.ItemStockSummary
                                   WHERE        (FiscalYearRef = {settings.SEPIDAR_STOCK_NUMBER}) and StockRef in (50,51,53,54,60,28,84,73,74,75,76,77,78,85)
                                   GROUP BY ItemRef) AS sum_stock_res ON sum_stock_res.ItemRef = item.ItemID LEFT OUTER JOIN
                                 (SELECT        InvI.ItemRef, SUM(InvI.Quantity) AS total_quantity
                                   FROM            SLS.Invoice AS Inv INNER JOIN
                                                             SLS.InvoiceItem AS InvI ON Inv.InvoiceId = InvI.InvoiceRef
                                   WHERE        (Inv.CustomerPartyRef = {party_id})
                                   GROUP BY InvI.ItemRef) AS sell_1 ON sell_1.ItemRef = item.ItemID LEFT OUTER JOIN
                                 (SELECT        InvI.ItemRef, SUM(InvI.Quantity) AS total_quantity
                                   FROM            SLS.Invoice AS Inv INNER JOIN
                                                             SLS.InvoiceItem AS InvI ON Inv.InvoiceId = InvI.InvoiceRef
                                   GROUP BY InvI.ItemRef) AS sell_2 ON sell_2.ItemRef = item.ItemID LEFT OUTER JOIN
                                 (SELECT        i_quotation.ItemRef, quotation.Date, i_quotation.Fee, i_quotation.Quantity
                                   FROM            SLS.QuotationItem AS i_quotation INNER JOIN
                                                             SLS.Quotation AS quotation ON i_quotation.QuotationRef = quotation.QuotationId INNER JOIN
                                                                 (SELECT        quI.ItemRef, MAX(qu.QuotationId) AS max_id
                                                                   FROM            SLS.Quotation AS qu INNER JOIN
                                                                                             SLS.QuotationItem AS quI ON qu.QuotationId = quI.QuotationRef AND qu.CustomerPartyRef = {party_id}
                                                                   GROUP BY quI.ItemRef) AS mx ON i_quotation.ItemRef = mx.ItemRef AND quotation.QuotationId = mx.max_id) AS quotation_1 ON item.ItemID = quotation_1.ItemRef
    WHERE  (item.Code = '{code}')
    ORDER BY f_date_cust desc,quotation_date desc,stock_qty DESC, f_qty_cust DESC, f_qty_all DESC    
            """
        res = Item.objects.raw(qry, using='sepidar')
        # print(qry)
        return res

    @staticmethod
    def get_stock_qty(sku):
        qry = f"""
        with fis_year as (select max(FiscalYearId) as fis_year_id from fmk.FiscalYear)

SELECT i.code code, cast(SUM(Quantity) as float) AS quantity
FROM          INV.ItemStockSummary as inv_s
join inv.item as i on i.ItemID = inv_s.ItemRef
WHERE        (inv_s.FiscalYearRef = (select * from fis_year)) and StockRef in (2,50,51,53,54,60,84,   73,74,75,76,77,78,85) and i.code={sku}
GROUP BY i.code
    """
        res = Item.objects.raw(qry, using='sepidar')
        return res


class WhereHouse(models.Model):
    stock_id = models.CharField(primary_key=True, verbose_name='stock id', max_length=200)

    @classmethod
    def get_list(cls):
        query = """
            Select StockID AS stock_id, Code AS code, Title AS title From [INV].[Stock] WHERE IsActive=1
        """
        res = cls.objects.raw(query, using='sepidar')

        return res

    @classmethod
    def get_item(cls, stock_id):
        query = f"""
                    Select StockID AS stock_id, Code AS code, Title AS title From [INV].[Stock] WHERE (IsActive=1) AND (StockID={stock_id})
                """
        res = cls.objects.raw(query, using='sepidar')

        return res


from .scripts.Configuration import Configuration
from .scripts.DevicesService import DevicesService
from .scripts.UsersService import UsersService
import requests


class Method(models.TextChoices):
    Get = "1", _("Get")
    Post = "2", _("Post")
    Put = "3", _("Put")
    Del = "4", _("Del")


class Device(core.models.AbsBaseModel):
    base_url = models.URLField(verbose_name=_('base_url'))
    generation_version = models.CharField(max_length=20,verbose_name=_('generation_version'))
    registration_code = models.CharField(max_length=20,verbose_name=_('registration_code'))
    user_name = models.CharField(max_length=20,verbose_name=_('user_name'))
    password = models.CharField(max_length=20,verbose_name=_('password'))
    public_key = models.CharField(max_length=500,verbose_name=_('public_key'),null=True,blank=True)
    name = models.CharField(max_length=20, verbose_name=_('name'))
    _user = None

    def register(self):
        config = Configuration(self.base_url, self.generation_version)
        client = DevicesService(config, self.registration_code)
        client.register()
        self.public_key = client._public_key.decode('utf-8')
        self.name = client.DeviceName
        self.save()
        user = UsersService(client)
        user.login(self.user_name, self.password)
        self._user = user

    @property
    def user(self):
        if not self._user:
            config = Configuration(self.base_url, self.generation_version)
            client = DevicesService(config, self.registration_code)
            client._public_key = self.public_key.encode('utf-8')
            client.DeviceName = self.name
            user = UsersService(client)
            user.login(self.user_name, self.password)
            self._user = user
        return self._user


class APILogs(core.models.AbsBaseModel):
    device = models.ForeignKey(Device, on_delete=models.DO_NOTHING,verbose_name=_('device'))
    status = models.IntegerField(blank=True, null=True, verbose_name=_('status'))
    api_url = models.URLField(verbose_name=_('api_url'))
    api_method = models.CharField(verbose_name=_('api_method'), max_length=20)
    api_payload = models.JSONField(verbose_name=_('api_payload'),null=True,blank=True)
    api_result = models.JSONField(verbose_name=_('api_result'))
    api_response = models.JSONField(verbose_name=_('api_response'), null=True, blank=True)

    @staticmethod
    def new_call( url, device: Device, method: Method = Method.Get, data=None, save=True):
        if not device:
            device = Device.objects.all().first()
        _user = device.user
        headers = _user.create_headers()
        url = _user.get_absolute_url(url)
        if method == Method.Get:
            response = requests.get(url, headers=headers, data=data)
        elif method == Method.Post:
            response = requests.post(url, headers=headers, data=data)
        elif method == Method.Put:
            response = requests.put(url, headers=headers, data=data)
        elif method == Method.Del:
            response = requests.delete(url, headers=headers, data=data)
        else:
            response = None

        log_data = {'device': device, 'status': response.status_code,
                    'api_url': url, 'api_method': method, 'api_payload': data}
        if response and response.status_code == 201:
            log_data['api_result'] = response.json()
        elif response and response.status_code == 200 and method == Method.Get:
            log_data['api_result'] = response.json()
        elif response and response.status_code == 200 and method == Method.Del:
            log_data['api_result'] = f'delete quotation {url.split("/")[-1]}'
        else:
            log_data['api_result'] = response.reason

        try:
            response_json = response.json()
        except Exception as e:
            response_json = {'res': 'not_json'}

        log_data['api_response'] = response_json
        log = APILogs.objects.create(**log_data) if save else None
        return response.status_code, response_json, log
