import datetime

import gspread
#from translator import get_text as _

scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class GSheet:
    def __init__(self, spreadSheetID, auth_file='tools/Files/token.json'):
        self.gc = gspread.oauth(
            credentials_filename='tools/Files/credintials.json',
            authorized_user_filename=auth_file)
        self.wb = self.gc.open_by_key(spreadSheetID)
        self.price_value = None
        self.price_b_date = None
        self.yuan_rate = None
        self.market = None
        self.last_update = None
        self.is_loadin = False
        #self.get_data()

    def read_sheet(self,sheet_name,header_rows=[1]):
        try:
            values = self.wb.worksheet(sheet_name).get_values()
        except Exception as e:
            print(e)
            values = ['']
        header = []
        for j in range(0,len(values[0])):
            m_str = ''
            for r in header_rows:
                m_str += values[r-1][j]
            header.append(m_str)
        data = []
        for r in range(len(header_rows),len(values)):
            d = {}
            i = 0
            for key in header:
                d[key] = values[r][i]
                i += 1
            data.append(d)
        return data

    def get_data(self):
        if self.is_loadin:
            print('currently loading')
            # return
        if not self.last_update or self.last_update < datetime.datetime.now() - datetime.timedelta(minutes=30):
            print('loading')
            self.is_loadin = True
            self.price_value = None
            self.price_b_date = None
            self.yuan_rate = None
            self.market = None
            self.last_update = None
            try:
                self.price_value = self.read_sheet('b_price', [1, 2])
                self.price_b_date = self.read_sheet('b_date')
                self.yuan_rate = float(list(self.wb.values_get('price!R11').values())[2][0][0])
                self.market = self.read_sheet('market', [1, 2])
                self.last_update = datetime.datetime.now()
            except Exception as e:
                print(str(e))
            finally:
                self.is_loadin = False
                print(f'load completed at {datetime.datetime.now()}')

    def get_sheet_price(self,sku):
        self.get_data()
        price = {'p': {}, 'market': {},'yuan_rate': self.yuan_rate}
        for p in self.price_value:
            if p['SKU'] == sku:
                price['p']['week1'] = float(p['2-3 weekRMB']) if p['2-3 weekRMB'] != '' else ''
                price['p']['week2'] = float(p['3-5 weekRMB']) if p['3-5 weekRMB'] != '' else ''
                price['p']['week3'] = float(p['12-14 weekRMB']) if p['12-14 weekRMB'] != '' else ''
                break
        for p in self.price_b_date:
            if p[''] == sku:
                price['p']['date'] = datetime.datetime.strptime(p['date'], '%Y-%m-%d').date() if p['date'] else ('not_defined')
                break
        for p in self.market:
            if p['4'] == sku:
                price['market']['price'] = float(p['قیمت (ریال)'])
                price['market']['date'] = datetime.datetime.strptime(p['زمان استعلام'], '%Y-%m-%d').date() if p['زمان استعلام'] else ('not_defined')
                break

        return price

price_wb = GSheet("1QaCzGf_sqELtWsK1hqmUGWftkGE4B8JPPbyrkt8ye3o")


if __name__ == '__main__':
    p = price_wb.get_sheet_price('255')
    p2 = price_wb.get_sheet_price('7925')
    print(p)

