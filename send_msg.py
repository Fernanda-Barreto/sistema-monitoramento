# -*- coding: utf-8 -*-
from dotenv import load_dotenv
import os, requests
load_dotenv()
url = f"https://api.telegram.org/bot{os.getenv('OLHARVIVO_TG_TOKEN')}/sendMessage"
r = requests.post(url, data={"chat_id": os.getenv("OLHARVIVO_TG_CHATID"),
                             "text": "Olhar Vivo ✅ teste de notificação"})
print("Status:", r.status_code, r.text[:200])
