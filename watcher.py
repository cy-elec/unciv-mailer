import os, base64, gzip, json, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import subprocess
import logging
from datetime import datetime
import hashlib
import traceback, time


numeric_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % os.environ["LOG_LEVEL"))
logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(message)s"
)

# Required ENV
WATCH_DIR = os.environ["WATCH_DIR"]
MAIL_MAP_FILE = os.environ["MAIL_MAP_FILE"]
SMTP_USER = os.environ["SMTP_USER"]
SMTP_USER_FROM = f'{os.environ["SMTP_USER_FROM"]} <{SMTP_USER}>'
SMTP_PASS = os.environ["SMTP_PASS"]
SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = os.environ["SMTP_PORT"]
SMTP_ERROR_ADDR = os.environ["SMTP_ERROR_ADDR"]

mail_map_mtime = None

def load_mail_map(mmap):
    global mail_map_mtime
    if os.path.exists(MAIL_MAP_FILE):
        mtime = os.path.getmtime(MAIL_MAP_FILE)
        if mtime != mail_map_mtime:
            with open (MAIL_MAP_FILE, "r") as f:
                 mmap = json.load(f)
            mail_map_mtime = mtime
            logging.info(f"Reloaded Mail-Map")
        return mmap
    return {}

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def file_changed(file, known_hashes):
    if not os.path.isfile(file):
        return False
    hash = file_hash(file)
    if known_hashes.get(file) == hash:
        return False
    known_hashes[file] = hash
    return True

def process_file(filepath, mail_map, known_hashes):
    
    if not file_changed(filepath, known_hashes):
        logging.info(f"File unchanged, skipping: {filepath}")
        return

    with open(filepath, "rb") as f:
        decoded = gzip.decompress(base64.b64decode(f.read()))
        parsed = json.loads(decoded)
        
        currentPlayer = parsed.get("currentPlayer")
        civs = [ i for i in parsed.get("civilizations") if i["civName"] == currentPlayer ]
        logging.info(f"CurrentPlayer: {currentPlayer} Civs: {civs}")
        logging.debug(f"File data: {parsed}")
        player_id = civs[0].get("playerId");
        turn = parsed.get("turns")
        recipient = mail_map.get(player_id)
        
        # if data incomplete, try game file instead

        if recipient:
            logging.info(f"Sending mail to {player_id}")
            send_mail(filepath, parsed, recipient)
        else:
            logging.info(f"No email mapping found for Player-ID: {player_id}")


def send_mail(filepath, parsed, recipient):

    gameId = parsed.get("gameId", os.path.basename(filepath).replace("_Preview",""))
    nation = parsed.get("currentPlayer", "Unknown")
    turn = parsed.get("turns", "-")
    since = datetime.utcfromtimestamp(parsed.get("currentTurnStartTime", 0)/1000).strftime('%d.%m.%Y %H:%M:%S')
    
    msg = MIMEMultipart('alternative')
    msg["Subject"] = "Unciv - It's your turn!"
    msg["From"] = SMTP_USER_FROM
    msg["To"] = recipient

    plain = f"""It's your turn!

Your Nation: {nation}
Current Turn: {turn}
Since: {since}
Game ID: {gameId}

Launch Game: https://unciv.app/multiplayer?id={gameId}

Unciv on GitHub: https://github.com/yairm210/Unciv
My GitHub: https://github.com/cy-elec
    """
    html = f"""<html>
	<head></head>
	<body>
		<div stgle="text-align: center; font-size: 1.2em; font-weight: bold; color: #006398; margin-top: 20px; font-family: 'Segoe UI', Arial, Helvetica, sans-serif;">
			It's your turn!
		</div>
		<table style="border-collapse: collapse;
				margin: auto;
				margin-top: 25px;
				margin-bottom: 25px;
				font-size: 0.95em;
				font-family: 'Segoe UI', Arial, Helvetica, sans-serif;
				min-width: 50%;
				box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
				border-radius: 12px 12px 0 0;
				overflow: hidden;">
			<tr>
				<td style="padding: 14px 18px;font-weight: bold; font-family: 'Segoe UI', Arial, Helvetica, sans-serif;">Your Nation</td>
				<td style="padding: 14px 18px; font-family: 'Segoe UI', Arial, Helvetica, sans-serif;">{nation}</td>
			</tr>
			<tr style="background-color: #f6fafd;">
				<td style="padding: 14px 18px;font-weight: bold; font-family: 'Segoe UI', Arial, Helvetica, sans-serif;">Current Turn</td>
				<td style="padding: 14px 18px; font-family: 'Segoe UI', Arial, Helvetica, sans-serif;">{turn}</td>
			</tr>
			<tr style="border-bottom: 2px solid #006398;">
				<td style="padding: 14px 18px;font-weight: bold; font-family: 'Segoe UI', Arial, Helvetica, sans-serif;">Since</td>
				<td style="padding: 14px 18px; font-family: 'Segoe UI', Arial, Helvetica, sans-serif;">{since}</td>
			</tr>
			<tr style="background-color: #f6fafd;">
				<td style="padding: 14px 18px; font-weight: bold; font-family: 'Segoe UI', Arial, Helvetica, sans-serif;">Game ID</td>
				<td style="padding: 14px 18px; font-family: 'Segoe UI', Arial, Helvetica, sans-serif;">
					<span style="font-family: monospace; word-break: break-all;">{gameId}</span>
				</td>
			</tr>
		</table>
        <div style="width: 50%; min-width: 320px; margin: 0 auto; position: relative; font-family: 'Segoe UI', Arial, Helvetica, sans-serif; margin-top: 20px; margin-bottom: 320px">
            <a href="https://github.com/yairm210/Unciv" style="position: absolute; left: 0; top: 50%; transform: translateY(-50%); text-decoration: none;">
                <img src="cid:uncivlogo" 
                    alt="Unciv Logo"
                    style="height: 34px; width: 34px; vertical-align: middle; border: none;">
            </a>
            <div style="text-align: center;">
                <a href="https://unciv.app/multiplayer?id={gameId}" style="display: inline-block; background-color: #006398; color: #fff; padding: 12px 30px; text-decoration: none; font-size: 1em; font-family: 'Segoe UI', Arial, Helvetica, sans-serif; border-radius: 6px;"> Launch Game </a>
            </div>
            <a href="https://github.com/cy-elec" style="position: absolute; right: 0; top: 50%; transform: translateY(-50%); text-decoration: none;">
				<img src="cid:githublogo"
                    alt="My GitHub"
                    style="height: 34px; width: 34px; vertical-align: middle; border: none; font-size: 0;">
            </a>
        </div>
	</body>
</html>
    """

    unciv_img = """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"""
    github_img = """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"""

    plain_mime = MIMEText(plain, 'plain')
    html_mime = MIMEText(html, 'html')

    # last part is preffered
    msg.attach(plain_mime)
    msg.attach(html_mime)

    msgImageUnciv = MIMEBase('image', 'png')
    msgImageUnciv.set_payload(unciv_img)
    msgImageUnciv.add_header('Content-ID', '<uncivlogo>')
    msgImageUnciv.add_header('Content-Transfer-Encoding', 'base64')
    msg.attach(msgImageUnciv)
    msgImageGithub = MIMEBase('image', 'png')
    msgImageGithub.set_payload(github_img)
    msgImageGithub.add_header('Content-ID', '<githublogo>')
    msgImageGithub.add_header('Content-Transfer-Encoding', 'base64')
    msg.attach(msgImageGithub)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

def notify_admin(e):

    msg = EmailMessage()
    msg["Subject"] = "Critical Error Unciv-Mailer"
    msg["From"] = SMTP_USER_FROM
    msg["To"] = SMTP_ERROR_ADDR
    msg.set_content(f"A critical error occured in Unciv-Mailer:\n\n{e}")
    
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

def watch():
    known_hashes = {}
    mail_map = {}
    if not os.path.exists(MAIL_MAP_FILE):
        logging.warning(f"No mail_map configuration file found. Please add the file here: {MAIL_MAP_FILE}")
    try:
        proc = subprocess.Popen(["inotifywait", "-m", WATCH_DIR, "-e", "MODIFY,CLOSE_WRITE,CLOSE_NOWRITE", "--format", "%w%f %e"], stdout=subprocess.PIPE)
        for line in proc.stdout:
            try: 
                mail_map = load_mail_map(mail_map)
                parts = line.decode().strip().split()
                filepath = ' '.join(parts[:-1])
                event = parts[-1]
                if filepath.endswith("_Preview") and "CLOSE_WRITE" in event:
                    logging.info(f"Processing file: {filepath}")
                    process_file(filepath, mail_map, known_hashes)
                elif filepath.endswith("_Preview"):
                    logging.debug(f"Skipping file[{event}]: {filepath}")
            except Exception as e:
                logging.error(f"Subroutine failed with: {e}\n{traceback.format_exc()}");
    except Exception as e:
        logging.error(f"Watcher failed to start: {e}\n{traceback.format_exc()}")
        notify_admin(e)
    logging.error(f"Inotifywait quit unexpectedly: Halting watcher")
    while True:
        try:
            logging.error(f"Waiting for admin intervention, service down.")
            notify_admin(f"Inotifywait quit unexpectedly.\nManual intervention is required immediately!\n\nWatcher halted!")
        except Exception:
            pass
        time.sleep(7200)

if __name__ == "__main__":
    watch()
