from django.db.models.manager import Manager
from django.db import connection
from django.db.models import Q

from micmod_base.base import *
from translator import get_text as _
import os
from itertools import islice

from tools.utils import read_excel_data, to_jalali_date
from datetime import datetime


def user_upload_file_path(instance, filename: str):
    """generate file path for user uploaded file"""
    now = datetime.now()
    name = '_'.join(filename.split(' '))
    name = f"{now.date()}_{now.hour}_{now.minute}_{name}"
    return os.path.join('uploads/', name)

from tools.utils import timer
class IMEIAllSearchManager(Manager):
    @timer
    def raw_as_qs(self, raw_query):
        """Execute a raw query and return a QuerySet.  The first column in the
        result set must be the id field for the model.
        :type raw_query: str | unicode
        :return: django.db.models.query.QuerySet
        """
        cursor = connection.cursor()
        try:
            cursor.execute(raw_query)
            return self.filter(id__in=(x[0] for x in cursor))
        except Exception as e:
            pass
        finally:
            cursor.close()


class IMEIListReg(BaseModel):
    packing = models.CharField(max_length=20)
    register_date = models.DateField(null=True, blank=True)
    sku = models.CharField(max_length=20)
    part_number = models.CharField(max_length=50, null=True, blank=True)
    brand = models.CharField(max_length=50, null=True, blank=True)
    source_file = models.FileField(upload_to=user_upload_file_path, null=True, blank=True)

    def get_related(self):
        return self.main_imei_list_reg.all()


class IMEIListRegDetail(models.Model):
    imei_list_reg = models.ForeignKey(IMEIListReg,on_delete=models.DO_NOTHING,related_name='main_imei_list_reg')
    # row = models.BigIntegerField(null=False,blank=False)
    row = models.CharField(max_length=64, null=False,blank=False)
    main_box = models.CharField(max_length=50,null=True,blank=True)
    internal_box = models.CharField(max_length=50,null=True,blank=True)
    version = models.CharField(max_length=100,null=True,blank=True)
    IMEI = models.CharField(max_length=20,null=False,blank=False, unique=True)

    @classmethod
    def create_from_excel(cls, file, action, id):
        batch_size = 100
        imei_list_reg_obj = IMEIListReg.objects.filter(id=id).first()

        if file and imei_list_reg_obj:
            excel_data = read_excel_data(file)
            objs = (cls(imei_list_reg=imei_list_reg_obj,
                        row=item['row'],
                        main_box=item['main box'],
                        internal_box=item['internal box'],
                        version=item['version'],
                        IMEI=item['IMEI'],
                        ) for item in excel_data)

            while True:
                batch = list(islice(objs, batch_size))
                if not batch:
                    break
                if action == '1':
                    cls.objects.bulk_create(batch, batch_size,
                                            update_conflicts=True,
                                            unique_fields=['IMEI'],
                                            update_fields=['row', 'main_box', 'internal_box', 'version', 'imei_list_reg'])
                if action == '2':
                    cls.objects.bulk_create(batch, batch_size, ignore_conflicts=True)

    # @classmethod
    # def get_all(cls, param=None):
    #     condition = '1=1'
    #     if param == 'submit' or param == '':
    #         return IMEIAllSearch.objects.all()
    #     elif param == 'register':
    #         condition = 'N."IMEI" IS NOT NULL'
    #         return IMEIAllSearch.objects.all().extra(where=[condition])
    #     elif param == 'sale':
    #         condition = 'S."IMEI" IS NOT NULL'
    #         return IMEIAllSearch.objects.all().extra(where=[condition])

        # query = f'''
        #             Select R.id, R."IMEI", R.packing, R.register_date,
        #                     R.main_box, R.internal_box, N.status,
        #                     N.code, S.invoice_code, S.customer_name,
        #                     S.customer_code
        #             from ((select r_.id,r_.packing,r_.register_date,r_d_.main_box,r_d_.internal_box,r_d_."IMEI" from "IMEI_imeilistregdetail" as r_d_
        #                 join "IMEI_imeilistreg" as r_ on r_d_.imei_list_reg_id = r_.id) as R
        #                 left outer join
        #                 (select s_.id,s_.invoice_code,s_.customer_name,s_.customer_code,s_d_."IMEI" from "IMEI_imeisaleregdetail" as s_d_
        #                 join "IMEI_imeisalereg" as s_ on s_d_.imei_sale_reg_id = s_.id) as S ON R."IMEI" = S."IMEI"
        #                 left outer join
        #                 (select n_.code,n_.status,n_d_."IMEI" from "IMEI_imeintswregdetail" as n_d_
        #                 join "IMEI_imeintswreg" as n_ on n_d_.imei_ntsw_reg_id = n_.id)as N on N."IMEI"=S."IMEI")
        #                 where 1=1 {condition} LIMIT 5;'''
        #
        # return IMEIAllSearch.objects.all().filter(IMEI=condition)
        # if query:
        #     return raw_

    def is_submit(self):
        return bool(IMEIListRegDetail.objects.filter(IMEI=self.IMEI))


class IMEIAllSearch(models.Model):
    id = models.BigIntegerField(primary_key=True)
    IMEI = models.CharField(max_length=10)
    packing = models.CharField(max_length=20)
    register_date = models.DateField(null=True, blank=True)
    main_box = models.CharField(max_length=50,null=True,blank=True)
    internal_box = models.CharField(max_length=50,null=True,blank=True)
    status = models.BooleanField(default=1)
    code = models.CharField(max_length=10)
    invoice_code = models.CharField(max_length=20, verbose_name=_('invoice code'))
    customer_code = models.CharField(max_length=10, verbose_name=_('customer code'))
    customer_name = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('customer name'))

    objects = IMEIAllSearchManager()

    class Meta:
        managed = False
        db_table = 'imei_all'

    @classmethod
    def get_all(cls, param=None):
        query = f'''
                    Select R.id, R."IMEI", R.packing, R.register_date,
                            R.main_box, R.internal_box, N.status,
                            N.code, S.invoice_code, S.customer_name,
                            S.customer_code
                    from ((select r_d_.id,r_.packing,r_.register_date,r_d_.main_box,r_d_.internal_box,r_d_."IMEI" from "IMEI_imeilistregdetail" as r_d_
                        join "IMEI_imeilistreg" as r_ on r_d_.imei_list_reg_id = r_.id) as R
                        left outer join
                        (select s_.id,s_.invoice_code,s_.customer_name,s_.customer_code,s_d_."IMEI" from "IMEI_imeisaleregdetail" as s_d_
                        join "IMEI_imeisalereg" as s_ on s_d_.imei_sale_reg_id = s_.id) as S ON R."IMEI" = S."IMEI"
                        left outer join
                        (select n_.code,n_.status,n_d_."IMEI" from "IMEI_imeintswregdetail" as n_d_
                        join "IMEI_imeintswreg" as n_ on n_d_.imei_ntsw_reg_id = n_.id)as N on N."IMEI"=S."IMEI")
                        where 1=1 and   '''

        limit = ' limit 10000000'
        if param == 'submit' or param == 'all' or param == '':
            return IMEIAllSearch.objects.all()
            condition = '1=1'
            query += ' ' + condition + limit
            return IMEIAllSearch.objects.raw_as_qs(query)
        elif param == 'register':
            condition = 'N."IMEI" IS NOT NULL'
            query += ' ' + condition
            q = IMEIAllSearch.objects.raw_as_qs(query)
            return q
        elif param == 'sale':
            condition = 'S."IMEI" IS NOT NULL'
            query += ' ' + condition
            return IMEIAllSearch.objects.raw_as_qs(query)

    @property
    def jalali_register_date(self):
        return to_jalali_date(self.register_date)


class IMEINTSWReg(BaseModel):
    STATUS = (('new', _('new')), ('in progress', _('in progress')), ('final approval', _('final approval')))
    register_date = models.DateField(null=True, blank=True)
    goods_id = models.CharField(max_length=20, null=True, blank=True)
    goods_description = models.CharField(max_length=200, null=True, blank=True)
    source_file = models.FileField(upload_to=user_upload_file_path, null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS, default='new')


class IMEINTSWRegDetail(models.Model):
    imei_ntsw_reg = models.ForeignKey(IMEINTSWReg,on_delete=models.DO_NOTHING,related_name='main_imei_ntsw_reg')
    row = models.BigIntegerField(null=False, blank=False)
    IMEI = models.CharField(max_length=20, null=False, blank=False, unique=True)
    activation_code = models.CharField(max_length=20, null=False, blank=False)

    @classmethod
    def create_from_excel(cls, file, action, id):
        batch_size = 100
        imei_ntsw_reg_obj = IMEINTSWReg.objects.filter(id=id).first()
        if file and imei_ntsw_reg_obj:
            excel_data = read_excel_data(file)
            objs = (
                cls(
                    imei_ntsw_reg=imei_ntsw_reg_obj,
                    row=item['row'],
                    IMEI=item['IMEI'],
                    activation_code=item['activation code']
                ) for item in excel_data
            )

            while True:
                batch = list(islice(objs, batch_size))
                valid_imei = IMEIListRegDetail.objects.in_bulk([i.IMEI for i in batch], field_name='IMEI').keys()
                valid_batch = []
                if not batch:
                    break
                if not valid_imei:
                    valid_batch = []
                else:
                    valid_batch = [x for x in batch if str(x.IMEI) in valid_imei]
                if action == '1':
                    cls.objects.bulk_create(valid_batch, batch_size,
                                            update_conflicts=True,
                                            unique_fields=['IMEI'],
                                            update_fields=['row', 'activation_code','imei_ntsw_reg'])
                if action == '2':
                    cls.objects.bulk_create(valid_batch, batch_size, ignore_conflicts=True)

    def is_submit(self):
        return bool(IMEIListRegDetail.objects.filter(IMEI=self.IMEI))


class IMEISaleReg(BaseModel):
    invoice_date = models.DateField(verbose_name=_('invoice date'))
    invoice_code = models.CharField(max_length=20, verbose_name=_('invoice code'))
    invoice_year = models.CharField(max_length=4, null=True, blank=True, verbose_name=_('invoice year'))
    customer_code = models.CharField(max_length=10, verbose_name=_('customer code'))
    customer_name = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('customer name'))
    pack_numbers = models.TextField(max_length=1000, verbose_name='شماره کارتن(ها) با علامت منها (-) از هم جدا کنید.', null=True, blank=True)
    warning = models.CharField(max_length=255, verbose_name='هشدار', null=True, blank=True)
    source_file = models.FileField(upload_to=user_upload_file_path, null=True, blank=True)

    def has_detail(self):
        return bool(IMEISaleReg.objects.filter(id=self.id).first().main_imei_sale_reg.all())

    def is_complete(self):
        IMEI_sell_all_box = None
        try:
            boxs = self.pack_numbers.split('-')
        except Exception as e:
            print(e)
            boxs = None
        if boxs:
            IMEI_sell_all_box = [item.IMEI for item in IMEIListRegDetail.objects.filter(Q(internal_box__in=boxs) | Q(main_box__in=boxs))]

        IMEI_sell_now = [item.IMEI for item in IMEISaleReg.objects.filter(id=self.id).first().main_imei_sale_reg.all()]

        for item in IMEI_sell_all_box:
            if item not in IMEI_sell_now:
                return False
            else:
                return True
        else:
            return False


class IMEISaleRegDetail(models.Model):
    imei_sale_reg = models.ForeignKey(IMEISaleReg, on_delete=models.DO_NOTHING, related_name='main_imei_sale_reg')
    row = models.BigIntegerField(null=False, blank=False)
    IMEI = models.CharField(max_length=20, null=False, blank=False, unique=True)

    @classmethod
    def create_from_excel(cls, file, action, id):
        batch_size = 100
        imei_sale_reg_obj = IMEISaleReg.objects.filter(id=id).first()
        if file and imei_sale_reg_obj:
            excel_data = read_excel_data(file)
            objs = (
                cls(
                    imei_sale_reg=imei_sale_reg_obj,
                    row=item['row'],
                    IMEI=item['IMEI']
                ) for item in excel_data
            )

            while True:
                batch = list(islice(objs, batch_size))
                if not batch:
                    break
                if action == '1':
                    cls.objects.bulk_create(batch, batch_size,
                                            update_conflicts=True,
                                            unique_fields=['IMEI'],
                                            update_fields=['row', 'imei_sale_reg'])
                if action == '2':
                    cls.objects.bulk_create(batch, batch_size, ignore_conflicts=True)

    def is_submit(self):
        return bool(IMEIListRegDetail.objects.filter(IMEI=self.IMEI))


class IMEIErrReg(BaseModel):
    IMEI = models.CharField(max_length=20, null=False, blank=False, unique=True)
    reason = models.CharField(max_length=100, null=False, blank=False)
    description = models.CharField(max_length=1000, null=False, blank=False)

    def is_submit(self):
        return bool(IMEIListRegDetail.objects.filter(IMEI=self.IMEI))
