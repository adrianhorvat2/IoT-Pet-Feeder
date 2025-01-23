from flask import Flask, render_template, Response, request, jsonify
import cv2
import urllib.request
import numpy as np
import time

app = Flask(__name__)

# Početna količina hrane (grami)
initial_food_quantity = 500
current_food_quantity = initial_food_quantity

# Brojači za životinje
animal_counts = {"dog": 0, "cat": 0, "bird": 0}

# Postavljanje IP adrese kamere
cam_ip = '192.168.5.18'
url = f'http://{cam_ip}:8080/cam-hi.jpg'

last_detection_time = 0
detection_delay = 180  # Pauza od 3 minute


# Postavljanje OpenCV modela za detekciju
classNames = []
classFile = 'coco.names'
with open(classFile, 'rt') as f:
    classNames = f.read().rstrip('\n').split('\n')

configPath = 'ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt'
weightsPath = 'frozen_inference_graph.pb'

net = cv2.dnn_DetectionModel(weightsPath, configPath)
net.setInputSize(320, 320)
net.setInputScale(1.0 / 127.5)
net.setInputMean((127.5, 127.5, 127.5))
net.setInputSwapRB(True)

last_detected_animal = None
last_portion_type = None

def gen_frames():
    global current_food_quantity, last_detected_animal, last_portion_type, animal_counts, last_detection_time
    while True:
        imgResponse = urllib.request.urlopen(url)
        imgNp = np.array(bytearray(imgResponse.read()), dtype=np.uint8)
        img = cv2.imdecode(imgNp, -1)

        classIds, confs, bbox = net.detect(img, confThreshold=0.5)

        current_time = time.time()
        if len(classIds) != 0 and (current_time - last_detection_time) >= detection_delay:
            for classId, confidence, box in zip(classIds.flatten(), confs.flatten(), bbox):
                label = classNames[classId - 1]

                if label in ["dog", "cat", "bird"]:
                    cv2.rectangle(img, box, color=(0, 255, 0), thickness=3)
                    cv2.putText(img, label, (box[0] + 10, box[1] + 30), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 0), 2)

                    if label == "dog":
                        food_amount = 50
                        portion_type = "LARGE"
                    elif label == "cat":
                        food_amount = 30
                        portion_type = "MEDIUM"
                    elif label == "bird":
                        food_amount = 15
                        portion_type = "SMALL"

                    if current_food_quantity >= food_amount:
                        current_food_quantity -= food_amount
                        last_detected_animal = label
                        last_portion_type = portion_type
                        animal_counts[label] += 1

                        # Pošalji komandu samo ako ima dovoljno hrane
                        send_feed_command(portion_type)

                        # Ažuriraj prikaz
                        cv2.putText(img, f"{label} detected, {portion_type} portion: {food_amount}g",
                                    (box[0] + 10, box[1] + 60), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
                        cv2.putText(img, f"Remaining food: {current_food_quantity}g",
                                    (10, img.shape[0] - 10), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)

                        last_detection_time = current_time
                    else:
                        cv2.putText(img, f"Not enough food for {label}!",
                                    (box[0] + 10, box[1] + 60), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 2)

        ret, buffer = cv2.imencode('.jpg', img)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        
        
@app.route('/last_detected')
def last_detected():
    return jsonify({
        "animal": last_detected_animal,
        "portion_type": last_portion_type,
        "remaining_food": current_food_quantity
    })

@app.route('/animal_counts')
def animal_counts_route():
    return jsonify(animal_counts)

@app.route('/refillFeeder', methods=['POST'])
def refillFeeder():
    global current_food_quantity 
    current_food_quantity = initial_food_quantity
    return jsonify({"remaining_food": current_food_quantity, "message": "Hranilica je napunjena."})

def send_feed_command(portion_type):
    if portion_type == "LARGE":
        command = "LARGE"
    elif portion_type == "MEDIUM":
        command = "MEDIUM"
    elif portion_type == "SMALL":
        command = "SMALL"

    # Pošalji POST zahtjev ESP32 serveru
    try:
        url = f'http://{cam_ip}:8080/'
        data = {'message': command}
        response = urllib.request.urlopen(url, data=urllib.parse.urlencode(data).encode())
        print(f'Sent {command} command to ESP32. Response: {response.read().decode()}')
    except Exception as e:
        print(f'Error sending {command} command: {e}')

@app.route('/')
def index():
    return render_template('index.html', food_quantity=current_food_quantity)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/feed', methods=['POST'])
def feed():
    global current_food_quantity
    portion_type = request.form.get('portion_type')

    if portion_type == "LARGE" and current_food_quantity >= 50:
        current_food_quantity -= 50
        send_feed_command("LARGE")
        message = "Velika porcija poslužena."
    elif portion_type == "MEDIUM" and current_food_quantity >= 30:
        current_food_quantity -= 30
        send_feed_command("MEDIUM")
        message = "Srednja porcija poslužena."
    elif portion_type == "SMALL" and current_food_quantity >= 15:
        current_food_quantity -= 15
        send_feed_command("SMALL")
        message = "Mala porcija poslužena."
    else:
        message = "Nema dovoljno hrane."

    return jsonify({"remaining_food": current_food_quantity, "message": message})


if __name__ == "__main__":
    app.run(host='192.168.5.18', port=5000, debug=True)
