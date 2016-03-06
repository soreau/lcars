#!/usr/bin/env python

# Linux Command Active Recognition System
# Copyright (C) 2015-2016  Scott Moreau

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import sys
import select
from socket import *
from time import sleep
from random import randint
from Queue import Queue
from PyQt4.QtGui import *
from PyQt4.QtCore import Qt, QThread, SIGNAL, pyqtSignal
from threading import Thread
import functools

max_msg_size = 1024

sys.path.append("./common")
home_dir = os.environ['HOME']
sys.path.append(home_dir + "/.lcars/common")
import lcars_common as lcars

config_file = home_dir + "/.lcars/config"
socket_file = "/tmp/lcars_socket"

def load_config():
	section = None
	if os.path.exists(config_file):
		if debug:
			print("Using config file " + config_file)
		try:
			f = open(config_file, "r")
			data = f.readlines()
			i = 0
			while i < len(data):
				line = data[i]
				line = line.strip()
				if not len(line) or line[0] is "#":
					i += 1
					continue
				if "core" in line:
					section = "core"
				elif "plugins" in line:
					section = "plugins"
				elif section == "core":
					if not "=" in line:
						i += 1
						continue
					name, value = line.split("=")
					value = value.strip("\"")
					if name == "trigger":
						lcars.trigger = value
					elif name == "response":
						lcars.response = value
					elif name == "disable_trigger":
						lcars.disable_trigger = value
					elif name == "run_in_background":
						lcars.run_in_background = value
				elif section == "plugins":
					if "[" in line and "]" in line and not "=" in line:
						plugin = line.strip("[]")
						i += 1
						line = data[i].strip()
						name, value = line.split("=")
						value = value.strip("\"")
						if name == "enabled":
							if value == "true":
								lcars.plugins_loaded.append(plugin)
							else:
								lcars.plugins_disabled.append(plugin)
				i += 1
			f.close()
		except:
			lcars.trigger = "computer"
			lcars.response = "computer-beep-response.wav"
			lcars.disable_trigger = "false"
			lcars.run_in_background = "true"

def write_config():
	if not os.path.exists(home_dir + "/.lcars"):
		os.makedirs(home_dir + "/.lcars")
	try:
		f = open(config_file, "w")
		f.write("# Created by lcars-gui\n\n")
		f.write("core {\n")
		f.write("\ttrigger=\"" + lcars.trigger + "\"\n")
		f.write("\tresponse=\"" + lcars.response + "\"\n")
		f.write("\tdisable_trigger=\"" + lcars.disable_trigger + "\"\n")
		f.write("\trun_in_background=\"" + lcars.run_in_background + "\"\n")
		f.write("}\n\n")
		f.write("plugins {\n")
		for plugin in lcars.plugins_loaded:
			f.write("\t[" + plugin + "]\n")
			f.write("\t\tenabled=\"true\"\n")
		for plugin in lcars.plugins_disabled:
			f.write("\t[" + plugin + "]\n")
			f.write("\t\tenabled=\"false\"\n")
		f.write("}\n")
		f.close()
	except:
		print("Failed to write config to " + config_file)

class SocketThread(QThread):
	def __init__(self, in_q, out_q):
		QThread.__init__(self)
		self.in_q = in_q
		self.out_q = out_q
		self.running = True
		self.connected = False
		self.suppress_connecting_message = False
		self.receiving_plugin_data = False

	def stop(self):
		self.running = False

	def run(self):
		self.running = True
		self.connected = False
		self.suppress_connecting_message = False
		spinner = ["|", "/", "-", "\\"]
		spinner_count = 0
		while self.running:
			self.in_q.put("[connecting]")
			self.emit(SIGNAL("check_queue()"))
			if self.connected is False and self.suppress_connecting_message is False:
				self.in_q.put("Waiting for server connection  ")
				self.emit(SIGNAL("check_queue()"))
			while self.running:
				try:
					self.sock = socket(AF_UNIX, SOCK_STREAM)
					if self.connected is False and self.suppress_connecting_message is False:
						try:
							self.in_q.put("[delete_previous_char]")
							self.in_q.put(spinner[spinner_count])
							self.emit(SIGNAL("check_queue()"))
							spinner_count += 1
							if spinner_count > 3:
								spinner_count = 0
						except:
							pass
					self.sock.connect(socket_file)
					sleep(0.1)
					self.in_q.put("[connected]")
					self.emit(SIGNAL("check_queue()"))
					if not self.suppress_connecting_message:
						self.in_q.put("\n")
						self.emit(SIGNAL("check_queue()"))
					self.in_q.put("Connected!\nListening...\n")
					self.emit(SIGNAL("check_queue()"))
					self.connected = True
					break
				except:
					sleep(0.1)
					continue
			try:
				self.sock.send("Hello!")
				if debug:
					print("[client]: Initiated conversation with server daemon")
			except:
				if debug:
					print("[client]: Failed to initiate conversation with server daemon")
				self.sock.close()
				self.connected = False
				sleep(0.1)
				continue
			if debug:
				print("[client]: Waiting for message")
			while self.running:
				try:
					ready = select.select([self.sock,], [], [], 0.1)
				except:
					return
				if ready[0]:
					try:
						self.msg = self.sock.recv(max_msg_size)
						if not self.msg:
							break
					except:
						break
					try:
						msgs = str(self.msg).split("\x1F")
						for msg in msgs:
							if not msg:
								continue
							if debug:
								print("[client]: Recieved message from server:", msg)
							if "[plugins_loaded]: " in msg:
								self.receiving_plugin_data = True
							if not self.receiving_plugin_data:
								msg = msg[0:4] + msg[5].upper() + msg[6:] + "\n"
							elif " :[plugins_disabled]" in msg:
								self.receiving_plugin_data = False
							self.in_q.put(msg)
						self.emit(SIGNAL("check_queue()"))
					except:
						pass
				else:
					while not self.out_q.empty():
						data = str(self.out_q.get())
						if debug:
							print("[client]: From queue: " + data)
						try:
							self.sock.send(data + "\x1F")
							if debug:
								print("[client]: Data sent")
						except:
							self.sock.close()
							self.connected = False
							sleep(0.1)
							continue
					sleep(0.1)
					continue
			self.sock.close()
			self.connected = False
			sleep(0.1)
		if debug:
			print("Thread execution completed")

class TriggerLineEdit(QLineEdit):
	def __init__(self, w):
		QLineEdit.__init__(self)
		self.w = w

	def focusOutEvent(self, event):
		self.w.update_trigger()
		super(TriggerLineEdit, self).focusOutEvent(event)

class ResponseLineEdit(QLineEdit):
	def __init__(self, w):
		QLineEdit.__init__(self)
		self.w = w

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton:
			super(ResponseLineEdit, self).mousePressEvent(event)
			self.response_file_picker()
		else:
			super(ResponseLineEdit, self).mousePressEvent(event)

	def response_file_picker(self):
		selected_file = QFileDialog.getOpenFileName()
		if selected_file:
			self.setText(selected_file)
			self.setCursorPosition(len(self.text()))
			self.w.update_response()

def reset_trigger(w):
		trigger = "computer"
		w.trigger_textbox.setText(trigger)
		w.out_q.put("[trigger]: " + trigger)
		lcars.trigger = trigger
		write_config()

def reset_response(w):
		response = "computer-beep-response.wav"
		w.response_file_textbox.setText(response)
		w.out_q.put("[response]: " + response)
		lcars.response = response
		write_config()

def start_server(w):
	os.system("./lcars start")

def stop_server(w):
	if not w.socket_thread.suppress_connecting_message and not w.socket_thread.connected:
		w.in_q.put("\n")
		w.check_queue()
	w.user_clicked_stop = True
	w.socket_thread.suppress_connecting_message = True
	os.system("./lcars stop")
	w.status_label.setPalette(w.red)
	w.status_label.setText("Stopped")
	w.in_q.put("Stopped\n")
	w.check_queue()

def restart_server(w):
	stop_server(w)
	start_server(w)

def create_plugin_checkbox(w, name, enabled):
	if name in w.plugin_checkboxes:
		return
	cb = QCheckBox(w)
	if enabled:
		cb.toggle()
	callback = functools.partial(w.toggle_plugin, name, cb)
	cb.stateChanged.connect(callback)
	row = QHBoxLayout()
	row.addWidget(QLabel(name))
	row.addStretch()
	row.addWidget(cb)
	w.plugin_tab_layout.addRow(row)
	w.plugin_checkboxes.append(name)

def create_window_widgets(w):
	# Create palettes
	w.red = QPalette()
	w.green = QPalette()
	w.yellow = QPalette()
	w.red.setColor(QPalette.Foreground, Qt.red)
	w.green.setColor(QPalette.Foreground, Qt.green)
	w.yellow.setColor(QPalette.Foreground, Qt.yellow)

	# Create labels
	status_desc_label = QLabel("Status:")
	w.status_label = QLabel("Connecting..")
	w.status_label.setPalette(w.yellow)

	# Create buttons
	w.start_button = QPushButton()
	w.start_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
	start_func = functools.partial(start_server, w)
	w.start_button.clicked.connect(start_func)
	start_icon = QIcon()
	start_icon.addPixmap(QPixmap("icons/start.png"), QIcon.Normal, QIcon.Off)
	w.start_button.setIcon(start_icon)
	w.stop_button = QPushButton()
	w.stop_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
	stop_func = functools.partial(stop_server, w)
	w.stop_button.clicked.connect(stop_func)
	stop_icon = QIcon()
	stop_icon.addPixmap(QPixmap("icons/stop.png"), QIcon.Normal, QIcon.Off)
	w.stop_button.setIcon(stop_icon)
	w.restart_button = QPushButton()
	w.restart_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
	restart_func = functools.partial(restart_server, w)
	w.restart_button.clicked.connect(restart_func)
	restart_icon = QIcon()
	restart_icon.addPixmap(QPixmap("icons/refresh.png"), QIcon.Normal, QIcon.Off)
	w.restart_button.setIcon(restart_icon)
	button_layout = QHBoxLayout()
	button_layout.addWidget(status_desc_label)
	button_layout.addWidget(w.status_label)
	button_layout.addStretch()
	button_layout.addWidget(w.restart_button)
	button_layout.addWidget(w.start_button)
	button_layout.addWidget(w.stop_button)

	# Create tabs
	tabs = QTabWidget()
	log = QWidget()
	general = QWidget()
	plugins = QWidget()
	log_tab_layout = QVBoxLayout(log)
	general_tab_layout = QVBoxLayout(general)
	plugins_tab_layout = QVBoxLayout(plugins)
	tabs.addTab(log, "Log")
	tabs.addTab(general, "General")
	tabs.addTab(plugins, "Plugins")

	# Create text edit box
	w.textedit = QTextEdit(w)
	w.textedit.setReadOnly(True)
	w.textedit.setText("Welcome to LCARS!\n")
	log_tab_layout.addWidget(w.textedit)

	# Create checkboxes
	w.disable_trigger_checkbox = QCheckBox(w)
	if lcars.disable_trigger == "true":
		w.disable_trigger_checkbox.setChecked(True)
	else:
		w.disable_trigger_checkbox.setChecked(False)
	w.disable_trigger_checkbox.stateChanged.connect(w.update_disable_trigger)
	w.run_in_bg_checkbox = QCheckBox(w)
	if lcars.run_in_background == "true":
		w.run_in_bg_checkbox.setChecked(True)
	else:
		w.run_in_bg_checkbox.setChecked(False)
	w.run_in_bg_checkbox.stateChanged.connect(w.update_run_in_bg)

	w.trigger_textbox = TriggerLineEdit(w)
	w.trigger_textbox.setFixedWidth(78)
	w.trigger_textbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
	w.trigger_textbox.setText(lcars.trigger)
	w.trigger_textbox.setAlignment(Qt.AlignRight)

	w.response_file_textbox = ResponseLineEdit(w)
	w.response_file_textbox.setFixedWidth(200)
	w.response_file_textbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
	w.response_file_textbox.setText(lcars.response)
	w.response_file_textbox.setAlignment(Qt.AlignRight)

	# Reset buttons
	reset_icon = QIcon()
	reset_icon.addPixmap(QPixmap("icons/refresh.png"), QIcon.Normal, QIcon.Off)
	reset_trigger_button = QPushButton()
	reset_trigger_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
	reset_func = functools.partial(reset_trigger, w)
	reset_trigger_button.clicked.connect(reset_func)
	reset_trigger_button.setIcon(reset_icon)
	reset_response_button = QPushButton()
	reset_response_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
	reset_func = functools.partial(reset_response, w)
	reset_response_button.clicked.connect(reset_func)
	reset_response_button.setIcon(reset_icon)

	general_group_box = QGroupBox()
	general_group_box.setStyleSheet("QGroupBox {border:0; background-color:#ddd;}")
	list_layout = QFormLayout(general_group_box)
	trigger_layout = QHBoxLayout()
	trigger_layout.addWidget(QLabel("Trigger Word"))
	trigger_layout.addStretch()
	trigger_layout.addWidget(w.trigger_textbox)
	trigger_layout.addWidget(reset_trigger_button)
	list_layout.addRow(trigger_layout)

	response_file_layout = QHBoxLayout()
	response_file_layout.addWidget(QLabel("Ready Response"))
	response_file_layout.addStretch()
	response_file_layout.addWidget(w.response_file_textbox)
	response_file_layout.addWidget(reset_response_button)
	list_layout.addRow(response_file_layout)

	disable_trigger_layout = QHBoxLayout()
	disable_trigger_layout.addWidget(QLabel("Disable Trigger"))
	disable_trigger_layout.addStretch()
	disable_trigger_layout.addWidget(w.disable_trigger_checkbox)
	list_layout.addRow(disable_trigger_layout)

	run_in_bg_layout = QHBoxLayout()
	run_in_bg_layout.addWidget(QLabel("Run in Background"))
	run_in_bg_layout.addStretch()
	run_in_bg_layout.addWidget(w.run_in_bg_checkbox)
	list_layout.addRow(run_in_bg_layout)

	general_scroll = QScrollArea()
	general_scroll.setMinimumWidth(350)
	general_scroll.setMinimumHeight(150)
	general_scroll.setWidgetResizable(True)
	general_scroll.setWidget(general_group_box)

	general_tab_layout.addWidget(general_scroll)
	general_tab_layout.addStretch()

	# Plugin tab layout
	plugin_group_box = QGroupBox()
	plugin_group_box.setStyleSheet("QGroupBox {border:0; background-color:#ddd;}")
	w.plugin_tab_layout = QFormLayout(plugin_group_box)
	w.plugin_tab_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
	plugin_list = lcars.plugins_loaded + lcars.plugins_disabled
	plugin_list.sort()
	for plugin in plugin_list:
		if plugin in lcars.plugins_loaded:
			create_plugin_checkbox(w, plugin, True)
		elif plugin in lcars.plugins_disabled:
			create_plugin_checkbox(w, plugin, False)

	plugin_scroll = QScrollArea()
	plugin_scroll.setWidgetResizable(True)
	plugin_scroll.setWidget(plugin_group_box)

	plugins_tab_layout.addWidget(plugin_scroll)

	central_widget = QWidget()

	main_layout = QVBoxLayout(central_widget)
	main_layout.addLayout(button_layout)
	main_layout.addWidget(tabs)

	w.setCentralWidget(central_widget)

class MainWindow(QMainWindow):
	def __init__(self):
		super(self.__class__, self).__init__()
		self.setWindowTitle("LCARS")
		self.in_q = Queue()
		self.out_q = Queue()
		self.socket_thread = SocketThread(self.in_q, self.out_q)
		self.connect(self.socket_thread, SIGNAL("check_queue()"), self.check_queue)
		self.receiving_plugin_data = False
		self.user_clicked_stop = False
		self.plugin_checkboxes = []
		load_config()
		create_window_widgets(self)
		self.trigger_textbox.returnPressed.connect(self.update_trigger)
		self.socket_thread.start()
		os.system("./lcars start")

	def check_queue(self):
		while not self.in_q.empty():
			msg = str(self.in_q.get())
			if not msg:
				continue
			if "[connected]" in msg:
				self.status_label.setPalette(self.green)
				self.status_label.setText("Running")
				self.user_clicked_stop = False
				self.socket_thread.suppress_connecting_message = False
				continue
			elif "[connecting]" in msg:
				if self.user_clicked_stop is False:
					self.status_label.setPalette(self.yellow)
					self.status_label.setText("Connecting")
					self.socket_thread.suppress_connecting_message = False
				else:
					self.status_label.setPalette(self.red)
					self.status_label.setText("Stopped")
				continue
			elif "[delete_previous_char]" in msg:
				self.textedit.textCursor().deletePreviousChar()
			elif "[plugins_loaded]: " in msg:
				self.receiving_plugin_data = True
			elif " :[plugins_disabled]" in msg:
				self.receiving_plugin_data = False
			elif " :[plugins_loaded]" in msg or "[plugins_disabled]: " in msg:
				continue
			elif self.receiving_plugin_data:
				self.plugin_checkboxes.sort()
				if msg not in self.plugin_checkboxes:
					create_plugin_checkbox(self, msg, True)
				if msg not in lcars.plugins_loaded:
					lcars.plugins_loaded.append(msg)
				if msg in lcars.plugins_disabled:
					lcars.plugins_disabled.remove(msg)
			else:
				self.textedit.moveCursor(QTextCursor.End)
				self.textedit.insertPlainText(msg)
			self.textedit.moveCursor(QTextCursor.End)

	def update_trigger(self):
		trigger = self.trigger_textbox.text()
		self.out_q.put("[trigger]: " + trigger)
		lcars.trigger = trigger
		write_config()

	def update_response(self):
		response = self.response_file_textbox.text()
		self.out_q.put("[response]: " + response)
		lcars.response = response
		write_config()

	def update_disable_trigger(self):
		if self.disable_trigger_checkbox.isChecked():
			self.out_q.put("[disable_trigger]: true")
			lcars.disable_trigger = "true"
		else:
			self.out_q.put("[disable_trigger]: false")
			lcars.disable_trigger = "false"
		write_config()

	def update_run_in_bg(self):
		if self.run_in_bg_checkbox.isChecked():
			lcars.run_in_background = "true"
		else:
			lcars.run_in_background = "false"
		write_config()

	def toggle_plugin(self, p, cb):
		if cb.isChecked():
			self.out_q.put("[plugin]: " + p + "=" + "enable")
			for plugin in lcars.plugins_loaded + lcars.plugins_disabled:
				if plugin == p:
					if p not in lcars.plugins_loaded:
						lcars.plugins_loaded.append(p)
					if p in lcars.plugins_disabled:
						lcars.plugins_disabled.remove(p)
		else:
			self.out_q.put("[plugin]: " + p + "=" + "disable")
			for plugin in lcars.plugins_loaded + lcars.plugins_disabled:
				if plugin == p:
					if p in lcars.plugins_loaded:
						lcars.plugins_loaded.remove(p)
					if p not in lcars.plugins_disabled:
						lcars.plugins_disabled.append(p)
		write_config()

def main():
	global debug
	debug = False
	if len(sys.argv) > 1:
		if sys.argv[1] == "--debug":
			print("Debug enabled")
			debug = True
		else:
			print "Usage: " + sys.argv[0] + " [--debug]"
			return
	app = QApplication(sys.argv)
	win = MainWindow()
	win.show()
	app.exec_()
	if lcars.run_in_background == "false":
		os.system("./lcars stop")

if __name__ == "__main__":
    main()
