thumbs = "👍"
invalid = "Sorry, this command is not available."
another_attendance = "You are currently adding another attendance. Please complete or cancel that attendance call first."
attendance_info = "Use /title <title> to set a title, /deadline <deadline> to set a deadline, and /reminder <reminder> to add a reminder."
enter_message = "Please enter a title.\nFor example: /title training on monday!~"
enter_deadline = "Please enter a deadline. Use this format: `DD MMM YYYY HH:MM AM/PM`\nFor example: /deadline 21 Sep 2034 12:00 AM"
enter_reminder = "Please enter a reminder. Simply specify the hours before the deadline to send a reminder.\nFor example: /reminder 10.5"
invalid_format = "The date and time format you have entered is invalid. Please use this format: `DD MMM YYYY HH:MM AM/PM`\nFor example: /deadline 21 Sep 2034 12:00 AM"
invalid_reminder = "Please enter a valid positive number for the reminder as the number of hours before the deadline.\nFor example: /reminder 10.5"
enter_delete_id = "Please enter the number of the reminder you wish to delete.\nFor example: /delete_reminder 2"
invalid_delete = "Please enter a valid number for the reminder you wish to delete.\nFor example: /delete_reminder 2"
attendance_cancelled = "Current attendance call cancelled."
no_attendance = "You are not currently adding a new attendance. Use /new to do so."
no_deadline = "Please specify a deadline for this attendance."
too_early = "Deadline and reminders cannot be in the past!"
ask_reason = "Please specify a reason. For example, /out im dying"
parse_format = "%d %b %Y %I:%M %p %z"
disp_format = "%a %-d %b %-I:%M %p"
disp_format_verbose = "%a %-d %b %Y %-I:%M %p"
need_info = "Please set a title and deadline."
attendance_sent = "Sending poll..."
no_attendance_call = "There are currently no active attendance polls."
multiple_prefix = "Oops, it looks like there is more than one ongoing poll. I'll need you to specify which one you'd like to reply to.\n\n"
multiple_suffix = "\nFor example, to reply to the second one, use /in 2 or /out 2 <reason>"
suffix_attendance_instruction = "\nReply with /in or /out <reason>."
out_of_index = "Please specify a number which corresponds to one of the polls."

def birthday(name):
	return "hpbd {}".format(name)

def attendance_call(db, uid):
	message, deadline, reminders = db.get_active_info(uid)
	return "New poll for attendance.\nTitle: {}\nDeadline: {}\nReminders: {}".format(message, deadline, reminders)

def reminder_call(name):
	return "Hey {}, remember to let me know whether you'll be coming for this!".format(name)

def help_admin(name):
	return "Hi {}!\n\nI'll assume that you already know how to respond to a poll.\n\nTo start a new poll, type */new*.\nEach poll has three parameters which you can set - the _title_, the _deadline_ (to respond to the poll), and _reminders_ (reminders will be sent to all users who have not responded to the poll). The title and deadline are required, but setting reminders is optional.\n\nUse */title <title>* to set the title.\nUse */deadline <deadline>* to set the deadline.\nNote that the deadline should be in the format `DD MMM YYYY HH:MM AM/PM` - for example,\n*/deadline 21 Sep 2034 12:00 AM*.\nCapitalization doesn't matter, but the spaces do! (If you're not sure what the `MMM` should be, just use the first three letters of the month)\nAlso note that you cannot have two polls with the exact same deadline.\nUse */reminder <reminder>* to add a reminder.\nYou can set as many reminders as you want for a poll, or none at all.\nThe reminder should be in the form of a number (decimals are allowed), in terms of hours before the deadline. For example, if you wanted a reminder to be sent out at 20 Sep 2034 10:00 PM and 7:30 PM, you'd send\n*/reminder 2*\nand\n*/reminder 4.5*.\nUse */delete_reminder <index>* to delete a reminder.\nI can also set default reminders for you so you don't have to type it every time - just let me know at @xxuliang.\n\nUse */send* to send the poll out to all users when you're done customizing it. Note that you can't change any of the poll parameters after sending it out!\n\nWhen the poll closes, its results will be automatically sent to you.\nUse */view* if you want to see the responses to all active polls.\n\nIf you spot any bugs or have any other questions, message @xxuliang.\n\nThat's all! 😊".format(name)

def help_pleb(name):
	return "Hi {}!\n\nFrom time to time, I'll send you a poll for attendance. When you see one of those, you just need to reply with \n*/in <note (optional)>*\nor\n*/out <reason (required)>*.\nYour response will then be updated in the original poll message.\n\nIf you spot any bugs or have any questions, message @xxuliang.\n\nThat's all! 😊".format(name)

def attendance_send(message, deadline, name, suffix=suffix_attendance_instruction):
	return "Hello {}!\n\n🎉 *{}* 🥏\nPlease indicate your attendance by {}.{}".format(name, message, deadline, suffix)

def suffix_attendance_in(note):
	if note:
		return "\n\n*You're /in ({}) for this! 😊*".format(note)
	else:
		return "\n\n*You're /in for this! 😊*"

def suffix_attendance_out(reason):
	return "\n\n*You're /out ({}) for this 😢*".format(reason)

def multiple_list(attendance):
	text = ""
	for ind, att in enumerate(attendance):
		text += "{}. *{}*\n".format(ind + 1, att[1]["message"])
	return text

def tally(title, slash_in, slash_out, no_reply):
	total_in = len(slash_in)
	total_out = len(slash_out)
	total_noreply = len(no_reply)
	text = "*{}*\n\n*/in* 😊 ({}👥)\n".format(title, total_in)
	for elm in slash_in:
		name, note = elm
		text += "{}".format(name)
		if note: text += " ({})".format(note)
		text += "\n"
	text += "\n*/out* 😢 ({}👥)\n".format(total_out)
	for elm in slash_out:
		name, note = elm
		text += "{} ({})\n".format(name, note)
	text += "\n*No response* 😡 ({}👥)\n".format(total_noreply)
	for name in no_reply:
		text += "{}\n".format(name)
	return text

def log():
	f = open("log.txt", "r")
	return f.read()