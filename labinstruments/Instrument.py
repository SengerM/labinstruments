import serial
from time import sleep, time
import logging

class SCPISerialInstrument:
	"""A class to communicate with any laboratory instrument accepting SCPI commands through the serial port. A nice reference of common SCPI commands can be found [here](https://helpfiles.keysight.com/csg/e5055a/Programming/GP-IB_Command_Finder/Common_Commands.htm). Each instrument then implements specific commands. For this, you can subclass this class.
	"""
	def __init__(self, Serial_kwargs:dict, message_termination_instrument_to_PC:str='\n', message_termination_PC_to_instrument:str='\n', instrument_manufacturer:str=None, instrument_model:str=None, instrument_serial_number:str=None):
		"""
		Arguments
		---------
		Serial_kwargs: dict
			A dictionary with keyword arguments for [`serial.Serial`](https://pyserial.readthedocs.io/en/latest/pyserial_api.html#serial.Serial)
		message_termination_instrument_to_PC: str
			The termination sequence for messages sent from the instrument to the PC.
		message_termination_PC_to_instrument: str
			The termination sequence for messages sent from the PC to the instrument.
		instrument_manufacturer: str, optional
			The name of the manufacturer of the instrument. Once the connection with the instrument is established, this will be used to check that the instrument is the one supposed to be.
		instrument_model: str, optional
			The model of the manufacturer of the instrument. Once the connection with the instrument is established, this will be used to check that the instrument is the one supposed to be.
		instrument_serial_number: str, optional
			The serial number of the instrument. Once the connection with the instrument is established, this will be used to check that the instrument is the one supposed to be.
		"""
		self._message_termination_instrument_to_PC = message_termination_instrument_to_PC
		self._message_termination_PC_to_instrument = message_termination_PC_to_instrument

		self.serial_port = serial.Serial(**Serial_kwargs) # Open serial connection.

		self.clear_errors_buffer()

		# Check that we are connected with the correct instrument:
		if instrument_manufacturer is not None:
			if instrument_manufacturer.lower() not in self.idn.lower():
				raise RuntimeError(f'Not connected with an instrument manufactured by {instrument_manufacturer}, I am connected with {self.idn}. ')
		if instrument_model is not None:
			if instrument_model.lower() not in self.idn.lower():
				raise RuntimeError(f'Not connected with an instrument model {instrument_model}, I am connected with {self.idn}. ')
		if instrument_serial_number is not None:
			if instrument_serial_number.lower() not in self.idn.lower():
				raise RuntimeError(f'Not connected with an instrument with serial number {instrument_serial_number}, I am connected with {self.idn}. ')

	def write_without_checking_errors(self, cmd:str)->None:
		"""Send a message to the instrument.

		Arguments
		---------
		cmd: str
			A string with the command to be sent.
		"""
		send_this = cmd + self._message_termination_PC_to_instrument
		logging.debug(f'Writing {repr(send_this)} into {repr(self.serial_port.name)}')
		self.serial_port.write(send_this.encode('ASCII'))
		while self.serial_port.out_waiting > 0: # Wait until we have sent everything to the instrument.
			sleep(.01)

	def read_without_checking_errors(self)->str:
		"""Read what the instrument has said."""
		response = self.serial_port.readline()
		response = (response
			.decode('ASCII')
			.rstrip(self._message_termination_instrument_to_PC)
		)
		logging.debug(f'Read {repr(response)} from {repr(self.serial_port.name)}')
		return response

	def query_without_checking_errors(self, cmd:str)->str:
		"""Write and read automatically.

		Arguments
		---------
		cmd: str
			The command to be sent to the instrument.
		"""
		self.write_without_checking_errors(cmd)
		return self.read_without_checking_errors()

	def write(self, cmd:str)->None:
		"""Send a message to the instrument and check that there were no errors reported by the instrument. To send a message without checking for errors use `write_without_checking_errors`."""
		self.write_without_checking_errors(cmd)
		self.check_whether_error()

	def read(self)->str:
		"""Read the response of the instrument to the last command and check whether there was an error. To read without error checking, use `read_without_checking_errors`."""
		response = self.read_without_checking_errors()
		self.check_whether_error()
		return response

	def query(self, cmd:str)->str:
		"""Write and read the response of the instrument, and check whether there was any error in the process. To query without error checking, use `query_without_checking_errors`."""
		self.write_without_checking_errors(cmd)
		response = self.read_without_checking_errors()
		self.check_whether_error()
		return response

	def check_whether_error(self)->None:
		"""Check whether there was an error to be reported from the instrument. If so, this function raises `RuntimeError` and prints the message of the error received from the instrument."""
		msg = self.query_without_checking_errors('SYST:ERR?')
		if '"No error"'.lower() not in msg.lower():
			raise RuntimeError(f'The instrument says: {msg}')

	def clear_errors_buffer(self, timeout:float=1)->None:
		"""Clear the errors buffer in the instrument. Error messages in the buffer, if any, are simply deleted.

		Arguments
		---------
		timeout: float = 1
			A timeout for clearing the buffer, in seconds.
		"""
		self.clear_status()
		# ~ t_start = time()
		# ~ while True:
			# ~ try:
				# ~ self.check_whether_error()
				# ~ return
			# ~ except RuntimeError:
				# ~ if time() - t_start > timeout:
					# ~ raise RuntimeError('Timeout trying to clear errors buffer. ')

	@property
	def idn(self)->str:
		"""Ask the instrument who he is. Expected response is a string containing the name, manufacturer, serial number, etc."""
		if not hasattr(self, '_idn'):
			self._idn = self.query('*IDN?')
		return self._idn

	def reset(self, sleep_time:float=2)->None:
		"""Reset the instrument."""
		self.write_without_checking_errors('*RST')
		sleep(sleep_time) # Give it a bit of time to reset.

	def clear_status(self)->None:
		"""Clears the instrument status byte by emptying the error queue and clearing all event registers. Also cancels any preceding *OPC command or query."""
		self.write('*CLS')

	def wait(self)->None:
		"""Prohibits the instrument from executing any new commands until all pending overlapped commands have been completed."""
		self.write('*WAI')
