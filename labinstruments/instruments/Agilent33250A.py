from time import sleep, time
from labinstruments.Instrument import SCPISerialInstrument
import serial
import logging

class Agilent33250A(SCPISerialInstrument):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, instrument_manufacturer='Agilent', instrument_model='33250A', **kwargs)

	def apply(self, function:str, frequency:float, volt_pp:float, volt_offset:float):
		"""Send the `APPLY` command to the instrument. For details, see [page 144 of the user manual](https://www.keysight.com/se/en/assets/9018-03925/user-manuals/9018-03925.pdf?success=true)."""
		self.write('VOLT:UNIT VPP') # Make sure it will be volts peak to peak.
		self.write(f'APPLY:{function} {frequency:e}, {volt_pp:e}, {volt_offset:e}')

	def set_output(self, status:str):
		if status.lower() not in {'on','off'}:
			raise ValueError('`status` must be either "on" or "off". ')
		status = 1 if status.lower()=='on' else 0
		self.write(f'OUTP {status}')

	def set_burst(self, status:str):
		if status.lower() not in {'on','off'}:
			raise ValueError(f'`status` must be either "on" or "off", received {repr(status)}. ')
		status = 1 if status.lower()=='on' else 0
		self.write(f'BURS:STAT {status}')

	def set_burst_mode(self, mode:str):
		self.write(f'BURS:MODE {mode.upper()}')

	def set_burst_n_cycles(self, n:int):
		self.write(f'BURS:NCYC {int(n)}')

	def force_trigger(self, block_execution_timeout:float=None):
		self.write('*TRG')
		if block_execution_timeout is not None:
			self.wait_until_all_comands_have_been_executed(timeout=block_execution_timeout)

	def output_triggered(self, status:str):
		if status.lower() not in {'on','off'}:
			raise ValueError('`status` must be either "on" or "off". ')
		status = 1 if status.lower()=='on' else 0
		self.write(f'OUTP:TRIG {status}')

	def configure_arbitrary_waveform(self, samples_in_volt:list[float], frequency:float, send_in_binary_format:bool=False):
		# Compute normalized samples between -1 and 1:
		maximum_absolute_voltage = [abs(s) for s in samples_in_volt]
		maximum_absolute_voltage = max(maximum_absolute_voltage)
		samples = samples_in_volt
		samples = [s/maximum_absolute_voltage for s in samples]
		if send_in_binary_format == False:
			self.load_arbitrary_waveform_samples(samples)
		else:
			self.load_arbitrary_waveform_samples_in_binary_format([int(s*2047) for s in samples])
		self.write('FUNC:USER volatile') # From all the arbitrary waveforms, select the one in the volatile memory.
		self.apply(
			function = 'user',
			frequency = frequency,
			volt_pp = (max(samples_in_volt)-min(samples_in_volt))/2,
			volt_offset = 0,
		)

	def load_arbitrary_waveform_samples(self, samples:list[float]):
		MEMORY_SIZE = 65536 # https://www.keysight.com/se/en/assets/9018-03925/user-manuals/9018-03925.pdf?success=true#page=202
		if len(samples) > MEMORY_SIZE:
			raise ValueError(f'Received {len(samples)} to load to the instrument, which has a {MEMORY_SIZE} kSamples memory. They won\'t fit. ')

		self.write_without_checking_errors('DATA VOLATILE, ' + ', '.join([str(_) for _ in samples]))
		self.write_without_checking_errors('*WAI')
		self.check_whether_error()

	def load_arbitrary_waveform_samples_in_binary_format(self, samples:list[int]):
		MEMORY_SIZE = 65536 # https://www.keysight.com/se/en/assets/9018-03925/user-manuals/9018-03925.pdf?success=true#page=202
		if len(samples) > MEMORY_SIZE:
			raise ValueError(f'Received {len(samples)} to load to the instrument, which has a {MEMORY_SIZE} kSamples memory. They won\'t fit. ')
		if self.serial_port.xonxoff == True:
			raise RuntimeError(f'Cannot send binary data when XON/XOFF handshake is enabled, see [the user manual on page 201](https://www.keysight.com/se/en/assets/9018-03925/user-manuals/9018-03925.pdf?success=true#page=202). ')
		if self.serial_port.parity != serial.PARITY_NONE:
			raise RuntimeError(f'Cannot send binary data when parity is not "none", see [the user manual on page 201](https://www.keysight.com/se/en/assets/9018-03925/user-manuals/9018-03925.pdf?success=true#page=202). ')

		if any([not isinstance(s, int) or not -2047<=s<=2047 for s in samples]):
			raise ValueError(f'Samples must be int numbers and take values between -2047 and 2047. See [the user manual on page 201](https://www.keysight.com/se/en/assets/9018-03925/user-manuals/9018-03925.pdf?success=true#page=202). ')

		# The following procedure is explained in [the user manual on page 201](https://www.keysight.com/se/en/assets/9018-03925/user-manuals/9018-03925.pdf?success=true#page=202).
		self.write('FORM:BORD NORM') # Set the byte order in the AWG.
		bytes_per_sample = 2
		n_bytes_of_data = bytes_per_sample*len(samples)
		sleep(10e-3) # User manual says to sleep here.
		bytes_to_be_sent = f'DATA:DAC VOLATILE, #6{n_bytes_of_data:06d}'.encode('ASCII') + b''.join([s.to_bytes(length=2, byteorder='big', signed=True) for s in samples]) + self._message_termination_PC_to_instrument.encode('ASCII')
		logging.debug(f'Writing {repr(bytes_to_be_sent)} into {repr(self.serial_port.name)}')
		self.serial_port.write(bytes_to_be_sent)
		sleep(10e-3)
		self.check_whether_error()

def example():
	A = Agilent33250A(
		Serial_kwargs = dict(
			port = '/dev/ttyUSB1',
			timeout = 1,
			dsrdtr = True,
			baudrate = 9600,
		),
	)
	print(f'Connected with {A.idn}')

	A.set_output('off')

	A.configure_arbitrary_waveform([0,3,0,-2,0,0]*33, frequency=100e3)
	A.set_burst('on')
	A.set_burst_mode('triggered')
	A.write('BURSt:INTernal:PERiod 111') # I don't fully understand why we need this, but without this it does not let you to put many burst cycles...
	A.set_burst_n_cycles(1e5)
	A.write('TRIG:SOURCE BUS') # Select trigger source from software.
	A.set_output('on')
	print('Forcing trigger...')
	A.force_trigger()
	print('Done!')

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
