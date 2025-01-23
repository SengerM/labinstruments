from labinstruments.Instrument import SCPIInstrument
import socket
import logging
import numpy
import array as arr

# Reference example: https://github.com/FermilabQuantumNetwork/CQNET-AWG
# Better example: http://microsoft.github.io/Qcodes/_modules/qcodes/instrument_drivers/tektronix/AWG5014.html#TektronixAWG5014

logger = logging.getLogger(__name__)

class TektronixAWG5014C(SCPIInstrument):
	def __init__(self, ip_address:str, port:int, timeout_seconds=1):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect((ip_address, port))
		self.socket.settimeout(timeout_seconds)
		self.filelike_socket = self.socket.makefile(mode='rw', encoding='UTF-8', newline='\n')

	def write_without_checking_errors(self, cmd:str)->None:
		"""This method has to be implemented by the inheriting classes."""
		logger.debug(f'Sending command: {cmd}')
		self.socket.sendall(bytes(cmd + '\n', 'UTF-8'))

	def read_without_checking_errors(self)->str:
		"""This method has to be implemented by the inheriting classes."""
		MESSAGE_ENDS_WITH = '\r\n'
		received = ' '
		while received[-len(MESSAGE_ENDS_WITH):] != MESSAGE_ENDS_WITH:
			try:
				received += self.socket.recv(1024).decode()
			except TimeoutError:
				received = ''
				break
		received = received[1:]
		received = received.rstrip(MESSAGE_ENDS_WITH)
		logger.debug(f'Received: {received}')
		return received

	def set_output(self, n_channel:int, status:str):
		"""Set the output of the channel `n_channel` to `'on'` or `'off'`."""
		self.write(f'OUTPUT{n_channel} {status}')

	def delete_waveform(self, name:str):
		self.write(f'WLISt:WAVeform:DELete "{name}"') # Delete any waveform that is already using the same name.

	def load_arbitrary_waveform_samples(self,
		name:str, # The name of the waveform.
		samples:list, # A list of `float` or `int` with the samples of the waveform.
		markers_1:list, # A list with the markers 1.
		markers_2:list, # A list with the markers 2.
		override:bool=False # If `True`, any waveform that is already in the memory of the AWG with the same name will be deleted before loading this new waveform.
	):
		if not len(markers_1) == len(markers_2) == len(samples):
			raise ValueError(f'`markers_1`, `markers_2` and `samples` must have the same length. ')

		if min(samples) < -1 or max(samples) > 1:
			raise TypeError('`samples` can only contain values between -1 and 1 (inclusive). ')
		if not set(markers_1) <= {0,1} or not set(markers_2) <= {0,1}:
			raise ValueError(f'`markers_1` and `markers_2` can only contain 0s and 1s, but they have {set(markers_1)} and {set(markers_2)}, respectively. ')

		if override:
			try:
				self.delete_waveform(name)
			except RuntimeError as e:
				if '4000, "Waveform editing error; E11110' in repr(e):
					# This happens when the waveform does not exist in the AWG memory.
					pass
		try:
			self.write(f'WLISt:WAVeform:NEW "{name}", {len(samples)}, INT') # Create a new empty waveform where the samples are going to be loaded.
		except RuntimeError as e:
			if '4000,"Waveform editing error; E11110' in repr(e):
				raise RuntimeError(f'A waveform with the name {repr(name)} already exists in the AWG. ')

		# The following block of code was copy-pasted from [the source code of Qcodes](http://microsoft.github.io/Qcodes/_modules/qcodes/instrument_drivers/tektronix/AWG5014.html#TektronixAWG5014.send_waveform_to_list). I'm sorry, but it was taking too much time.
		number = (2**13 - 1) + (2**13 - 1) * numpy.array(samples) + 2**14 * numpy.array(markers_1) + 2**15 * numpy.array(markers_2)
		number = number.astype("int")
		ws_array = arr.array("H", number)
		ws = ws_array.tobytes()
		s1_str = f'WLISt:WAVeform:DATA "{name}",'
		s1 = s1_str.encode("UTF-8")
		s3 = ws
		s2_str = "#" + str(len(str(len(s3)))) + str(len(s3))
		s2 = s2_str.encode("UTF-8")
		mes = s1 + s2 + s3 + b'\n'
		logger.debug(f'Sending command: {mes}')
		self.socket.sendall(mes)

		self.check_whether_error()

	def set_waveform_into_sequence(
		self,
		n_element_within_sequence:int,
		n_channel:int,
		waveform_name:str,
	):
		self.write(f'SEQuence:ELEMent{n_element_within_sequence}:WAVeform{n_channel} "{waveform_name}"')

def example():
	awg = TektronixAWG5014C(
		ip_address = '192.168.0.69',
		port = 1111,
	)
	awg.clear_errors_buffer()
	print(awg.idn)
	awg.load_arbitrary_waveform_samples(
		name = 'write_pot',
		samples =   [0,1,0],
		markers_1 = [0,0,0],
		markers_2 = [0,0,0],
		override = True,
	)
	awg.load_arbitrary_waveform_samples(
		name = 'write_dep',
		samples =   [0,-1,0],
		markers_1 = [0, 0,0],
		markers_2 = [0, 0,0],
		override = True,
	)
	awg.load_arbitrary_waveform_samples(
		name = 'read',
		samples =   [0] + [.5]*10 + [0],
		markers_1 = [0,1] + [0]*(10),
		markers_2 = [0]*(10+2),
		override = True,
	)
	awg.set_waveform_into_sequence(1,1,'read')
	awg.set_waveform_into_sequence(2,1,'write_dep')
	awg.set_waveform_into_sequence(3,1,'write_pot')
	awg.set_waveform_into_sequence(4,1,'read')
	awg.set_output(1, 'on')

if __name__ == '__main__':
	import sys
	import logging

	# ~ logging.basicConfig(
		# ~ stream = sys.stderr,
		# ~ level = logging.DEBUG,
		# ~ format = '%(asctime)s|%(levelname)s|%(message)s',
		# ~ datefmt = '%H:%M:%S',
	# ~ )

	example()
