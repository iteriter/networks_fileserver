import os
import time


def get_byte_data_length(filepath):
    """Given filename return a 4-byte sequence, representing file contents size in bytes, as big-endian encoded integer
    """
    # get file contents size as integer and convert it to bytes, big-endian format
    try:
        byte_msg_len = os.stat(filepath).st_size.to_bytes(4, "big")
    except OverflowError:
        raise OverflowError("Message length is too big (more than 4 bytes or 2^32)")

    return byte_msg_len


def get_encoded_filename(filename):
    """Given filename return a byte sequence containing filename size and actual filename
        2 bytes     - filename size in bytes, as big-endian encoded integer
        1-255 bytes - ascii filename encoded as bytes
    """
    # encode filename in binary, get its size as integer and convert it bytes, big-endian format
    byte_filename = str(filename).encode("ascii")
    try:
        byte_filename_len = len(byte_filename).to_bytes(2, "big")
    except OverflowError:
        raise OverflowError("Filename length is too big (more than 2 bytes or 2^16)")
    return byte_filename_len + byte_filename


def attempt_socket_send(socket, fragment, data_size):
    """Attempts to send all provided data"""
    bytes_sent = 0
    while bytes_sent < data_size:
        sent = 0
        sent += socket.send(fragment[bytes_sent:])
        if sent == 0:
            raise RuntimeError("Connection broken")
        bytes_sent += sent
    return True


def send_over_socket(socket, filename, file_buffer_size, offset = 0):
    """
    Transmit file over socket in form of bytes

    Read maximum *file_buffer_size* bytes at once from them given *filename*, attempt to transmit the fragment read
    over provided *socket*. If *offset is provided*

    Args:
        socket              - socket for the file transmission
        filename            - string, name of the file to be transmitted
        file_buffer_size    - int, max amount of bytes to be read at once from the file
        offset              - int, used when attempting to re-transmit files whose transmission was interrupted
    Return:
        True    if file transmitted fully, raises RuntimeError otherwise, with error message specifying number
                of bytes transmitted successfully
    """

    with open(filename, "rb") as f:
        # if offset is provided, start reading file from the given byte
        if offset != 0:
            f.seek(offset)

        total_sent = 0  # amount of bytes that were actually transmitted only by successful chunks
        fragment = f.read(file_buffer_size) # first fragment

        # when file end is reached fragment == b'' and iteration stops
        while fragment:
            fragment_len = len(fragment)
            print("Sending fragment of len {}".format(fragment_len))
            try:
                # try to send fragment, if no exception increase the total send
                attempt_socket_send(socket, fragment, fragment_len)
                total_sent += fragment_len
            except RuntimeError:
                # error occurred during transmission of the last fragment, return sent bytes number apart last fragment
                raise RuntimeError("Transmission broken, total bytes sent: " + total_sent)
            fragment = f.read(file_buffer_size)

    print("Transmission over, total bytes sent: {}".format(total_sent))
    return True


def transmit_with_reconnect(socket, filename, file_buffer_size, max_attempts, timeout):
    attempt = 0
    offset = 0
    result = False
    while attempt < max_attempts and result is not True:
        attempt += 1
        try:
            result = send_over_socket(socket, filename, file_buffer_size, offset)
            if result is True:
                break
        except RuntimeError as e:
            print("Transmission was broker")
            prefix = "Transmission broken, total bytes sent:"
            if str(e).startswith(prefix, 0):
                bytes_sent = e[len(prefix):]
                offset += bytes_sent
                for i in range(timeout):
                    print("Transmission will be re-attempted in: {} seconds".format(timeout - i))
                    time.sleep(1)
                print("Re-attempting transmission, attempts remaining: {}".format(max_attempts - attempt))


def decode_filename(socket):
    """Get filename size N from the first 2 bytes received from socket, then read
    filename from N consecutive bytes received from socket"""
    byte_length = socket.recv(2)
    filename_length = int.from_bytes(byte_length , "big")
    filename = socket.recv(filename_length).decode()  # receive and decode filename
    return filename


def write_from_socket(socket, filename, data_length, buffer_size):
    bytes_received = 0

    with open(filename, "ab") as f:
        while bytes_received < data_length:
            fragment = socket.recv(buffer_size)
            print("Receiving data chunk, size ", len(fragment))
            print("Transmission progress: {}% ({} / {})".format(round(bytes_received / data_length * 100, 2),
                                                                bytes_received, data_length))
            if len(fragment) > data_length - bytes_received:
                raise RuntimeError("Msg length ({}) exceeded the specified data length".format(len(fragment)))  # todo: drop the excess data?
            bytes_received += len(fragment)
            print("Fragment received, total bytes: {}".format(bytes_received))
            f.write(fragment)
