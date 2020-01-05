import telegram, logging
from telegram.ext import Updater
from database import Database
from spreadsheet import Spreadsheet


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO, filename="log.txt", filemode="a")

logging.info("Application started")

db = Database()
logging.info("Database initialized")

ss = Spreadsheet()
logging.info("Spreadsheet initialized")

with open("TOKEN", "r") as f:
	TOKEN = f.readline().strip()

bot = telegram.Bot(TOKEN)
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher
job_queue = updater.job_queue
logging.info("Bot initialized")

import handlers
import callbacks

# reschedule jobs to send reminder and close poll
# in case bot closed with active jobs
attendances = db.get_attendances()
for att_id, att in attendances.items():
	callbacks.schedule(att_id)
# callbacks.schedule_birthday()
logging.info("Job scheduling OK")

job_queue.run_repeating(callbacks.backdoor, interval=5, first=10)


logging.info("Beginning Bot polling")
updater.start_polling()
