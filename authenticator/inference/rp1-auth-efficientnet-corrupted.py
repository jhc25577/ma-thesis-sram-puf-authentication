import socket
import time
import os
import model_inference as mi
import argparse
import ecies
from ecies.utils import generate_eth_key, generate_key
import base64
import secrets

def server_program():
    # get the hostname/ip address
    # host = "192.168.178.40" ## considering when static ip
    host = "132.231.14.165" # new static ip
    # host = "rp-labs1.local"
    port = 18000  #  port no above reserved ports (1024)

    server_socket = socket.socket()  # get socket instance
    server_socket.bind((host, port))  # bind host address and port together
    
    # starting server module
    print("Server started")

    # set metadata
    BUFFER_SIZE = 4096
    SEPARATOR = "<SEPARATOR>"
    ENCODING = "utf-8"

    # create a public and private key using ecies
    eth_k = generate_eth_key()
    # private key
    sk_hex = eth_k.to_hex()
    # sk_hex = "0xc82be1019b06e83b2544461c3b3d91e8eb44462e1dcaea6b7441af648a61a3b7"  # static private key
    # public key
    pk_hex = eth_k.public_key.to_hex()
    print("Private key: ", sk_hex)
    print("Public key: ", pk_hex)

    # configure how many client the server can listen simultaneously
    server_socket.listen(1)
    
    # add a timeout
    server_socket.settimeout(150.0)   # in seconds  
    
    # parse labels/device list
    parser = argparse.ArgumentParser()
    parser.add_argument(
    '-d',
    '--devices',
    default='../efficientnet/corrupted/5-boards/labels.txt',
    help='list of enrolled devices')
    args = parser.parse_args()
    
    with open(args.devices) as file:
        devices = [line.rstrip() for line in file]

    # accept a new connection 
    conn, address = server_socket.accept()

    print("Connection from: " + str(address))

    auth_req = conn.recv(BUFFER_SIZE).decode()
    print(auth_req)
    board = auth_req.split()[-1]
    print("Board name:", board)
    
    if board not in devices:
        print("Board is not present in the enrolled device list... Request rejected!!")
        conn.close()  # close the connection
        server_socket.close() # close the server socket
    
    if board in devices:
        time.sleep(2)
        
        # create a nonce (secure random number)
        nonce = secrets.randbits(32)
        # send public key and nonce
        conn.send(f"{pk_hex}{SEPARATOR}{nonce}".encode())
        # file related stuff
        msg = conn.recv(BUFFER_SIZE).decode()
        print("Message from client: ", msg)

        # file related stuff
        conn.send("Please send the board image".encode(ENCODING))
        received = conn.recv(BUFFER_SIZE).decode()
        filename, filesize, nonce_r = received.split(SEPARATOR)
        nonce_d = ecies.decrypt(sk_hex, nonce_r)
        # if nonce does not match, disconnect due to replay attack possibility
        if nonce_r != nonce:
            print("Nonce is incorrect. Breaking connection due to possible replay attack")
            conn.close()  # close the connection
            server_socket.close() # close the server socket
        else:
            # remove absolute path if there is
            filename = os.path.basename(filename)
            # informing the recived file 
            print("Receiving file:", filename)

            # store encrypted image as a byte array
            ecc = bytearray()
            with open(filename, "wb") as f:
                while True:
                    # read 1024 bytes from the socket (receive)
                    bytes_read = conn.recv(BUFFER_SIZE)
                    if not bytes_read:
                    # terminate file transmitting is done
                        break
                    # write to the file the bytes we just received
                    ecc.extend(bytes_read)
                # base64 decoding before/after decrypting
                print("Decrypting...")
                enc = base64.b64decode(bytes(ecc))
                dec = ecies.decrypt(sk_hex, enc)
                img = base64.b64decode(dec)
                f.write(img)

            print("File received. model being executed..")
            time.sleep(2)

            # calling efficientnet_lite model for classification
            #model = "/home/jojo755767/Documents/ma-thesis-sram-puf-authentication/authenticator/efficientnet/corrupted/bottom20/model.tflite"

            # calling efficientnet_lite model (with 5 boards) for classification
            model = "/home/jojo755767/Documents/ma-thesis-sram-puf-authentication/authenticator/efficientnet/corrupted/5-boards/model.tflite"

            image = filename
            score, label = mi.classify_image(model,image)  

            print("Image label detected:", label , "with confidence:", score*100, "%")
            
            if(score*100 > 80 and label.lower() == board.lower()):
                print("Predicted label by model from board image is correct.. authentication successful :)")
                conn.send("Device authenticated".encode(ENCODING))
            
            elif(score*100 < 80 and label.lower() == board.lower()):
                print("Predicted label has low confidence score.. authentication is not successfull")

            else:
                print("Board name and predicted image label mismatch...authentication not successful!")
                conn.send("Device not authenticated".encode(ENCODING))
            

            conn.close()  # close the connection
            server_socket.close() # close the server socket

if __name__ == '__main__':
    server_program()
