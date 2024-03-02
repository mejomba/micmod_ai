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

    def clear_rows(self, sheet, start_row=2, end_row=50000):
        self.wb.worksheet(sheet).batch_clear([f"{start_row}:{end_row}"])

    def update_rows(self, sheet, data, row='new', expandColumns='no', cols=None):
        try:
            class result(object):
                pass

            if row == 'new':
                sheetdata = self.wb.worksheet(sheet).get_all_values()
                header = sheetdata[0]
                result.row_num = len(sheetdata) + 1
            else:
                header = self.wb.worksheet(sheet).row_values(1)
                result.row_num = int(row)

            newHeader = header.copy()
            values = []
            for record in data:
                keys = record.keys()
                # set values according header of sheet
                value = []# ['' for x in range(0, len(newHeader))]
                i = 0
                for key in newHeader:
                    if key in keys:
                        if isinstance(record[key], datetime.datetime) or isinstance(record[key], datetime.date):
                            record[key] = str(record[key])
                        value.append(record[key])
                        # value[i] = str(record[key])
                    i += 1
                # set extera column for new attributes
                if expandColumns == 'yes':
                    for key in keys:
                        if (key in newHeader) == False:
                            newHeader.append(key)
                            if isinstance(record[key], datetime.datetime) or isinstance(record[key], datetime.date):
                                record[key] = str(record[key])
                            value.append(record[key])
                values.append(value)
            # Write data to shet
            self.wb.worksheet(sheet).update(f'A{result.row_num}', values)
            if newHeader != header:
                self.wb.worksheet(sheet).update('A1', [newHeader])

            result.header = newHeader
            result.values = value
            return result
        except Exception as e:
            print(e)
            return None


# price_wb = GSheet("1QaCzGf_sqELtWsK1hqmUGWftkGE4B8JPPbyrkt8ye3o")


if __name__ == '__main__':
    g_sheet = GSheet("1LC3YoRdEbkP9ipxAB_c6k3l05FF7hNsMJ97hllLjXI8")
    price_wb = GSheet("1QaCzGf_sqELtWsK1hqmUGWftkGE4B8JPPbyrkt8ye3o")
    p = price_wb.get_sheet_price('255')
    p2 = price_wb.get_sheet_price('7925')
    print(p)

