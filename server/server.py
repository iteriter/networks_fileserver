import sys
import os
import socket
import time
import file_transfer_util
from os import listdir
from os.path import isfile, join

# server config
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 15000
CONTENTS_PATH = "files/"
# end server config

# net config
KILOBYTE = 1024
FILE_BUFFER_SIZE = KILOBYTE * 1024  # how much data will be read into memory from input file at once
SOCKET_BUFFER_SIZE = KILOBYTE * 1024  # how much data will be sent to socket for transmission at once
TIMEOUT = 5  # time in second that the client will wait until attempting to retransmit interrupted file
MAX_ATTEMPTS = 3  # maximum amount of attempts the client will attempt to retransmit file. values smaller than 1
                  # or urneasonably large will result in errors
# end net config

# PROGRAM START
# get server properties
server_address = socket.gethostbyname(socket.gethostname())
server_port = sys.argv[0]
if not str(server_port).isnumeric():
    server_port = DEFAULT_PORT

# create socket and bind to the desired port
srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv_sock.bind((DEFAULT_HOST, DEFAULT_PORT))
srv_sock.listen()

print("File server was started successfully!", "Server address: {}:{}".format(server_address, server_port),
      "Full path to the working directory: {}".format(os.path.dirname(os.path.realpath(__file__))), sep="\n")

while True:
    cli_sock, cli_address = srv_sock.accept()
    request = cli_sock.recv(1)  # receive the header byte

    print(request)
    request_type = ""
    if len(request) > 0:
        # check request type
        if request[0] == 1:
            request_type = "put"
        elif request[0] == 2:
            request_type = "get"
        elif request[0] == 3:
            request_type = "list"
        else:
            # request type is invalid
            request_type = None

        print("'{}' request received from {}".format(request_type, cli_address))
        if request_type == "put":
            print("Serving put request")
            # get data length and file name
            byte_data_len = cli_sock.recv(4)  # receive the data-size
            data_length = int.from_bytes(byte_data_len, "big")
            filename = CONTENTS_PATH + file_transfer_util.decode_filename(cli_sock)

            print("Request received: upload; filename: " + filename + " data length: ", data_length, sep='')
            if filename in os.listdir(os.getcwd()):
                print("File upload has failed, file already exists!")
                cli_sock.send(b"File already exists")
            else:
                file_transfer_util.write_from_socket(cli_sock, filename, data_length, SOCKET_BUFFER_SIZE)
                print("File upload has finished successfully!")
                cli_sock.send(b"Upload complete")

        elif request_type == "get":
            print("Serving get request")
            filename = file_transfer_util.decode_filename(cli_sock)
            filepath = CONTENTS_PATH + filename

            if not filename in os.listdir(os.getcwd() + "\\" + CONTENTS_PATH):
                cli_sock.send(b"Requested file does not exist")
            else:
                data_header = file_transfer_util.get_byte_data_length(filepath)\
                              + file_transfer_util.get_encoded_filename(filename)
                header_msg = b"\x01" + data_header

                file_transfer_util.attempt_socket_send(cli_sock, header_msg, len(header_msg))  # send header
                file_transfer_util.transmit_with_reconnect(cli_sock, filepath, FILE_BUFFER_SIZE, MAX_ATTEMPTS,
                                                           TIMEOUT)  # send body

        elif request_type == "list":
            print("Serving list request")
            files_list = [file_transfer_util.get_encoded_filename(f) for f in listdir(CONTENTS_PATH)
                                                                            if isfile(CONTENTS_PATH +f)]
            files_list = b''.join(files_list)

            try: byte_msg_len = len(files_list).to_bytes(4, "big")
            except OverflowError:
                raise OverflowError("Message length is too big (more than 4 bytes or 2^32)")

            msg = b'\x03' + byte_msg_len + files_list
            file_transfer_util.attempt_socket_send(cli_sock, msg, len(msg))

    # done with the socket, close connection
    #cli_sock.close()
