import gspread, strings
from datetime import timezone, timedelta
from oauth2client.service_account import ServiceAccountCredentials


scope = [
	"https://spreadsheets.google.com/feeds",
	"https://www.googleapis.com/auth/drive"
	]

class Spreadsheet:
	def __init__(self, creds="gs_credentials"):
		credentials = ServiceAccountCredentials.from_json_keyfile_name(creds, scope)
		self.gc = gspread.authorize(credentials)
		self.sh = self.gc.open("attendance_bot")

	def new_attendance(self, attendance, users):
		self.gc.login()
		title = attendance["message"]
		deadline = attendance["deadline"] \
			.astimezone(timezone(timedelta(hours=8))) \
			.strftime(strings.disp_format_verbose)
		users = sorted(u["name"] for u in users.values())
		worksheet = self.sh.add_worksheet(title=deadline, rows=4+len(users), cols=3)
		self.load_template(worksheet, title, deadline, users)

	def load_template(self, worksheet, title, deadline, users):
		worksheet.update_acell("A1", "Title:")
		worksheet.update_acell("B1", title)
		worksheet.update_acell("A2", "Deadline:")
		worksheet.update_acell("B2", deadline)
		worksheet.update_acell("A4", "-Name-")
		worksheet.update_acell("B4", "-Attending-")
		worksheet.update_acell("C4", "-Note-")
		index = 5
		for user in users:
			worksheet.update_cell(index, 1, user)
			index += 1

	def update_response(self, deadline, name, attending, note):
		self.gc.login()
		deadline = deadline \
			.astimezone(timezone(timedelta(hours=8))) \
			.strftime(strings.disp_format_verbose)
		worksheet = self.sh.worksheet(deadline)
		cell = worksheet.find(name)
		worksheet.update_cell(cell.row, 2, str(attending))
		worksheet.update_cell(cell.row, 3, note)

	def add_user(self, deadline, name):
		self.gc.login()
		deadline = deadline \
			.astimezone(timezone(timedelta(hours=8))) \
			.strftime(strings.disp_format_verbose)
		worksheet = self.sh.worksheet(deadline)
		worksheet.append_row([name])
