import json
from connection import Connection

if __name__ == "__main__":
    json_file = json.load(open('copy_db.json', 'r', encoding="utf8"))
    source_db = Connection(json_file.get("source_config"))
    destination_db = Connection(json_file.get("destination_config"))
    for table in json_file.get("tables"):
        maps = table.get("maps")
        source_table = table.get('source_table')
        destination_table = table.get('destination_table',source_table)
        datas = source_db.select(f"select * from {source_table}")
        for key in maps.keys():
            for data in datas:
                data[maps[key]] = data.get(key)
        destination_db.insert_data(destination_table,datas,source_columns=source_db.get_columns_name(source_table))
