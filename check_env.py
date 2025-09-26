from dotenv import load_dotenv
import os
ok = load_dotenv(dotenv_path=".env", override=True)
print("load_dotenv ok?", ok)
print("TOKEN set?", bool(os.getenv("OLHARVIVO_TG_TOKEN")))
print("CHATID:", os.getenv("OLHARVIVO_TG_CHATID"))
