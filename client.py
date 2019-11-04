import socket
import sys
from server import file_transfer_util
import os
import time

# net config
KILOBYTE = 1024
FILE_BUFFER_SIZE = KILOBYTE * 1024  # how much data will be read into memory from input file at once
SOCKET_BUFFER_SIZE = KILOBYTE * 1024  # how much data will be sent to socket for transmission at once
TIMEOUT = 5  # time in second that the client will wait until attempting to retransmit interrupted file
MAX_ATTEMPTS = 3  # maximum amount of attempts the client will attempt to retransmit file. values smaller than 1
                  # or urneasonably large will result in errors
# end net config

allowed_requests = ["put", "get", "list"]
try:
    target_host = sys.argv[1]
    target_port = int(sys.argv[2])
    request = sys.argv[3]
    if request not in allowed_requests:
        print("Request is invalid")
        sys.exit()
    if request in ["put", "get"]:
        filename = sys.argv[4]
except IndexError:
    print("You must provide all necessary arguments")
    sys.exit()

cli_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli_sock.connect((target_host, target_port))

if request == "put":
    # send file upload request
    data_header = file_transfer_util.get_byte_data_length(filename) + file_transfer_util.get_encoded_filename(filename)
    request = b"\x01" + data_header
    file_transfer_util.attempt_socket_send(cli_sock, request, len(request))

    # upload the file contents
    file_transfer_util.transmit_with_reconnect(cli_sock, filename, FILE_BUFFER_SIZE, MAX_ATTEMPTS, TIMEOUT)  # send body

elif request == "get":
    if filename in os.listdir(os.getcwd()):
        print("You cannot download the file!\n File {} already exists".format(filename))
        sys.exit()

    # send file download request
    request = b"\x02" + file_transfer_util.get_encoded_filename(filename)
    file_transfer_util.attempt_socket_send(cli_sock, request, len(request))

    header_byte = cli_sock.recv(1)
    if header_byte[0] and header_byte[0] != 1:
        print("Server returned unexpected answer, first 1024 bytes: ", cli_sock.recv(1024))

    # get data length and file name
    byte_data_len = cli_sock.recv(4)  # receive the data-size
    data_length = int.from_bytes(byte_data_len, "big")
    filename = file_transfer_util.decode_filename(cli_sock)
    print("filename:", filename)

    file_transfer_util.write_from_socket(cli_sock, filename, data_length, SOCKET_BUFFER_SIZE)
    print("File download has finished successfully!")

elif request == "list":
    # send files listing request
    request = b"\x03"
    file_transfer_util.attempt_socket_send(cli_sock, request, len(request))

    header_byte = cli_sock.recv(1)
    if header_byte[0] and header_byte[0] != 3:
        print("Server returned unexpected answer, first 1024 bytes: ", header_byte, cli_sock.recv(1024), sep='')

    byte_data_len = cli_sock.recv(4)  # receive the data-size
    data_length = int.from_bytes(byte_data_len, "big")

    files = []
    total_length = 0
    while total_length < data_length:
        byte_length = cli_sock.recv(2)
        filename_length = int.from_bytes(byte_length, "big")
        filename = cli_sock.recv(filename_length).decode()  # receive and decode filename
        files.append(filename)
        total_length += 2 + filename_length

    print(files)

print("Closing socket")
cli_sock.close()
