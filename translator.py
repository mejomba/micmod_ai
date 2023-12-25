import json
try:
    fa = json.load(open('assets/lang/fa.json','r', encoding="utf8"))
    en = json.load(open('assets/lang/en.json','r', encoding="utf8"))
except Exception as e:
    print(str(e))

def get_text(data_key,lang='fa'):
    try:
        if lang == 'fa':
            return fa.get(data_key,data_key)
        elif lang == 'en':
            return en.get(data_key,data_key)
    except:
        return data_key