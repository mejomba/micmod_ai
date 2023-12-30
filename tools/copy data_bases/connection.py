import psycopg2
from psycopg2.extras import execute_batch


class Connection:
    def __init__(self,config):
        self.config = config
        self.cnx = None
        self.cursor = None
        self.connect()

    def connect(self):
        # self.cnx = pyodbc.connect(**self.config)
        self.cnx = psycopg2.connect(**self.config)
        self.cursor = self.cnx.cursor()
        # self.cursor.fast_executemany = True

    def execute_qry(self,qry, retry=True):
        cursor = self.cnx.cursor()
        cursor.execute(qry)
        self.cnx.commit()
        return cursor

    def select(self,qry):
        cursor = self.execute_qry(qry)
        if cursor:
            data = cursor.fetchall()
            cursor.close()
            return data
        return []

    def __get_columns(self, table):
        columns = []
        query = f"SELECT * FROM {table} limit 1"
        self.cursor = self.execute_qry(query)
        for c in self.cursor.description:
            columns.append({'name':c[0],'type':'int' if c[1] == int or c[1] == float else 'str','len':c[3]})
        return columns

    def get_columns_name(self, table):
        return [col['name'] for col in self.__get_columns(table)]

    def insert_data(self, table, datas, source_columns):
            if len(datas) == 0:
                return
            destination_columns = self.get_columns_name(table)
            cols = ''
            # values_str = ''
            values_str_psg = ''
            for c in source_columns:
                if c in destination_columns:
                    cols += f'"{c}", '
                    # values_str += f"?, "
                    values_str_psg +=f'%s, '
            cols = cols[:-2]
            # values_str = values_str[:-2]
            values_str_psg = values_str_psg[:-2]
            # qry = f"INSERT INTO {table}\n({cols}) \n VALUES \n({values_str});"
            # qry = f"INSERT INTO {table}\n values({values_str_psg});"
            qry = f"INSERT INTO {table}\n ({cols}) values({values_str_psg});"
            execute_batch(self.cnx.cursor(), qry, datas)
            # for data in datas:
            #     self.cnx.cursor().execute(qry, data)
            self.cnx.commit()
