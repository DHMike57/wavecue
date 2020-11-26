#!/usr/bin/python3

import sys
import os
import struct
import io

def convert_to_hms( s ):
	seconds = s
	hour = s // 3600
	seconds %= 3600
	minutes = seconds // 60
	seconds %= 60
	millisecs = (s % 1) * 1000
	duration = "%02d:%02d:%02d.%03d" % (hour, minutes, seconds, millisecs)
	return duration

if len(sys.argv) <= 1:
	print("Usage: python3 %s <filename>" % (sys.argv[0]))
	sys.exit(1)

file = sys.argv[1]
if not os.path.exists(file):
	print("File does not exist!")
	sys.exit(1)

cue_dict = {}
with io.open(file, 'rb') as f:
	riff, size, fformat = struct.unpack('<4sI4s', f.read(12))
	print("Riff: %s, Chunk Size: %i, format: %s" % (riff, size, fformat))

	chunk_header = f.read(8)
	subchunk_id, subchunk_size = struct.unpack('<4sI', chunk_header)
	print(subchunk_id)
	if subchunk_id == b'fmt ':
		aformat, channels, samplerate, byterate, blockalign, bps = struct.unpack('HHIIHH', f.read(16))
		bitrate = (samplerate * channels * bps) / 1024
		print("Format: %i, Channels %i, Sample Rate: %i, Kbps: %i, BytesPerSec: %i" % (aformat, channels, samplerate, bitrate, byterate))
		sample_size = int(channels * bps / 8)
		print("Sample size: %s" % (sample_size))
		if aformat == 65534: # WaveFormatExtensible
			# Then we have extension size and extra fields
			extension_size, valid_bits_per_sample, channel_mask, sub_fmt_guid = struct.unpack('<HHI16s', f.read(24))
			print("Extention Size: %i, Valid Bps: %i, ChannelMask: %i, GUID: %s" % (extension_size, valid_bits_per_sample, channel_mask, sub_fmt_guid))
		chunk_offset = f.tell()
		while chunk_offset < size:
			f.seek(chunk_offset)
			subchunk2_id, subchunk2_size = struct.unpack('<4sI', f.read(8))
			print("Chunk: %s, size: %i" % (subchunk2_id.decode(), subchunk2_size))
			if subchunk2_id.decode() == 'data':
				duration = convert_to_hms( subchunk2_size / byterate )
				total_samples = int ((subchunk2_size * 8) / (channels * bps))
				print("Total duration: %s" % duration)
				print("Total samples: %s" % (total_samples))
			elif subchunk2_id == b'LIST':
				listtype = struct.unpack('<4s', f.read(4))[0]
				print("\tList Type: %s, List Size: %i" % (listtype.decode(), subchunk2_size))

				list_offset = 0
				do_print = True
				while (subchunk2_size - 8) >= list_offset:
					item_id, item_size = struct.unpack('<4sI', f.read(8))
					list_offset = list_offset + item_size + 8
					listdata = f.read(item_size)
					try:
						data = listdata.decode().rstrip('\0')
					except Exception as e:
						None
					if item_id.decode('ascii') in ['ltxt']:
						do_print = False
						cue_id, sample_length, purpose_id, country, lang, dialect, code_page = struct.unpack('<IIIhhhh', listdata)
						data = "CueID: %s | Sample Len: %s " % (cue_id, sample_length)
						if not cue_id in cue_dict:
							cue_dict[cue_id] = {}
						cue_dict[cue_id]['sample_len'] = sample_length
					elif item_id.decode('ascii') == 'labl':
						# There are the marker label with cue point IDs
						do_print = False
						cue_id, cue_label = struct.unpack('<I%ss' % (item_size - 4), listdata)
						cue_label = cue_label.decode().rstrip('\0')
						data = "CueID: %s, Cue Label: %s" % (cue_id, cue_label)
						if not cue_id in cue_dict:
							cue_dict[cue_id] = {}
						cue_dict[cue_id]['label'] = cue_label

					if list_offset <= (subchunk2_size -8) and do_print:
						print("\t\tID: %s, size: %i, offset: %s, data: %s" % (item_id.decode('ascii'), item_size, list_offset, data))

			elif subchunk2_id == b'cue ':
				total_cues = struct.unpack('<I', f.read(4))
				print("\tTotal cues: %s" % (total_cues))
				# Each cue is 24 bytes of data
				for i in range(total_cues[0]):
					cue_id, cue_pos, cue_chunk_id, cue_chunk_start, cue_block_start, cue_sample_start = struct.unpack('<II4sIII', f.read(24))
					byte_pos = cue_pos * sample_size
					time_pos = convert_to_hms( byte_pos / byterate )
					if not cue_id in cue_dict:
						cue_dict[cue_id] = {}
					cue_dict[cue_id]['position'] = cue_pos
					cue_dict[cue_id]['chunk_id'] = cue_chunk_id
					cue_dict[cue_id]['chunk_start'] = cue_chunk_start
					cue_dict[cue_id]['block_start'] = cue_block_start
					cue_dict[cue_id]['sample_start'] = cue_sample_start
					cue_dict[cue_id]['time_start'] = time_pos
					#print("""\t\tID: %s, Pos: %s, CID: %s, CStart: %s, BStart: %s, SStart: %s, Time Position: %s""" % (cue_id, 
					#	cue_pos, cue_chunk_id, cue_chunk_start, cue_block_start, cue_sample_start, time_pos))

			chunk_offset = chunk_offset + subchunk2_size + 8

print("\nCUE Data")
for cue_id, cue_data in cue_dict.items():
	if not 'time_end' in cue_data:
		cue_data['time_end'] = ''
	if 'sample_len' in cue_data:
		cue_data['time_end'] = convert_to_hms( (cue_data['sample_start'] + cue_data['sample_len']) * sample_size  / byterate )
		cue_data['duration'] = convert_to_hms( cue_data['sample_len'] * sample_size / byterate )
	else: 
		#This means the file does not have any 'ltxt' chunks indiciating sample len for these cue ids, 
		#as such these indicate redundant or useless cues 
		cue_data['time_end'] = ''
		cue_data['duration'] = ''
	if 'label' in cue_data:
		print("CueID: %3s | Label: %15s | Pos: %10s | SStart: %10s | TimeStart: %12s | TimeEnd: %12s | Duraton: %12s" % (cue_id, cue_data['label'], 
			cue_data['position'], cue_data['sample_start'], cue_data['time_start'], cue_data['time_end'], cue_data['duration']) )
	else:
		print("CueID: %3s | Label: %15s | Pos: %10s | SStart: %10s | TimeStart: %12s | TimeEnd: %12s | Duraton: %12s" % (cue_id, '', cue_data['position'], 
			cue_data['sample_start'], cue_data['time_start'], cue_data['time_end'], cue_data['duration']) )

