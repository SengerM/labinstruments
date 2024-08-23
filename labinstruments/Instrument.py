import serial
from time import sleep, time
import logging

class SCPISerialInstrument:
	def __init__(self, Serial_kwargs:dict, message_termination_instrument_to_PC='\n', message_termination_PC_to_instrument='\n'):
		self._message_termination_instrument_to_PC = message_termination_instrument_to_PC
		self._message_termination_PC_to_instrument = message_termination_PC_to_instrument

		self.serial_port = serial.Serial(**Serial_kwargs) # Open serial connection.

		self.clear_errors_buffer()

	def write_without_checking_errors(self, cmd:str):
		send_this = cmd + self._message_termination_PC_to_instrument
		logging.debug(f'Writing {repr(send_this)} into {repr(self.serial_port.name)}')
		self.serial_port.write(send_this.encode('ASCII'))
		while self.serial_port.out_waiting > 0: # Wait until we have sent everything to the instrument.
			sleep(.01)

	def read_without_checking_errors(self):
		response = self.serial_port.readline()
		response = (response
			.decode('ASCII')
			.rstrip(self._message_termination_instrument_to_PC)
		)
		logging.debug(f'Read {repr(response)} from {repr(self.serial_port.name)}')
		return response

	def query_without_checking_errors(self, cmd:str):
		self.write_without_checking_errors(cmd)
		return self.read_without_checking_errors()

	def write(self, cmd:str):
		self.write_without_checking_errors(cmd)
		self.check_whether_error()

	def read(self):
		response = self.read_without_checking_errors()
		self.check_whether_error()
		return response

	def query(self, cmd:str):
		self.write_without_checking_errors(cmd)
		response = self.read_without_checking_errors()
		self.check_whether_error()
		return response

	def check_whether_error(self):
		msg = self.query_without_checking_errors('SYST:ERR?')
		if msg not in {'0,"No error"'}:
			raise RuntimeError(f'The instrument says: {msg}')

	def clear_errors_buffer(self, timeout:float=1):
		t_start = time()
		while True:
			response = self.query_without_checking_errors('SYST:ERR?')
			if response == '0,"No error"':
				break
			if time() - t_start > timeout:
				raise RuntimeError('Timeout trying to clear errors buffer. ')

	@property
	def idn(self):
		if not hasattr(self, '_idn'):
			self._idn = self.query('*IDN?')
		return self._idn

	def reset(self):
		self.write_without_checking_errors('*RST')
		sleep(2) # Give it a bit of time to reset.
