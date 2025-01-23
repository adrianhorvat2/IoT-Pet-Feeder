#include <Arduino.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp32cam.h>
#include <WiFiManager.h>
#include <Stepper.h>

const int ledPin = 4;

// Initialize webserver on port 8080
WebServer server(8080);

// Set stepper motor pins
const int stepsPerRevolution = 2048; 
const int motorPin1 = 14;
const int motorPin2 = 12;
const int motorPin3 = 13;
const int motorPin4 = 15;

// Create Stepper object
Stepper myStepper(stepsPerRevolution, motorPin1, motorPin3, motorPin2, motorPin4);

static auto loRes = esp32cam::Resolution::find(320, 240);
static auto midRes = esp32cam::Resolution::find(350, 530);
static auto hiRes = esp32cam::Resolution::find(800, 600);

void serveJpg()
{
  auto frame = esp32cam::capture();
  if (frame == nullptr) {
    Serial.println("CAPTURE FAIL");
    server.send(503, "", "");
    return;
  }
  Serial.printf("CAPTURE OK %dx%d %db\n", frame->getWidth(), frame->getHeight(),
                static_cast<int>(frame->size()));

  server.setContentLength(frame->size());
  server.send(200, "image/jpeg");
  WiFiClient client = server.client();
  frame->writeTo(client);
}

void handleJpgLo()
{
  if (!esp32cam::Camera.changeResolution(loRes)) {
    Serial.println("SET-LO-RES FAIL");
  }
  serveJpg();
}

void handleJpgHi()
{
  if (!esp32cam::Camera.changeResolution(hiRes)) {
    Serial.println("SET-HI-RES FAIL");
  }
  serveJpg();
}

void handleJpgMid()
{
  if (!esp32cam::Camera.changeResolution(midRes)) {
    Serial.println("SET-MID-RES FAIL");
  }
  serveJpg();
}

void setup(){
  Serial.begin(115200);
  Serial.println();
  {
    using namespace esp32cam;
    Config cfg;
    cfg.setPins(pins::AiThinker);
    cfg.setResolution(hiRes);
    cfg.setBufferCount(2);
    cfg.setJpeg(80);

    bool ok = Camera.begin(cfg);
    Serial.println(ok ? "CAMERA OK" : "CAMERA FAIL");
  }

  // Initialize stepper motor speed (you can adjust the speed if needed)
  myStepper.setSpeed(10); // Speed in RPM

  // Set station mode
  WiFi.mode(WIFI_STA);

  WiFiManager wm;
  bool res;
  res = wm.autoConnect("PetFeederCam");
  if(!res) {
    Serial.println("Failed to connect to Pet Cam");
  }
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }

  // Print out information once connected to WiFi
  Serial.print("Server IP address: ");
  Serial.println(WiFi.localIP());

  Serial.print("http://");
  Serial.println(WiFi.localIP());
  Serial.println("  /cam-lo.jpg");
  Serial.println("  /cam-hi.jpg");
  Serial.println("  /cam-mid.jpg");

  server.on("/cam-lo.jpg", handleJpgLo);
  server.on("/cam-hi.jpg", handleJpgHi);
  server.on("/cam-mid.jpg", handleJpgMid);

  server.on("/", handleRoot);
  server.begin();
  Serial.println("HTTP server started");

  // Initialise with flash off
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);
}

void loop()
{
  // Call functions set with server.on()
  server.handleClient();
}

void rotateStepper(int durationInSeconds) {

  unsigned long startTime = millis();
  
  while (millis() - startTime < durationInSeconds * 1000) {
    myStepper.step(-1); 
  }
}

void handleRoot() {
  // Check for POST request, get message, and print it
  if (server.method() == HTTP_POST) {
    String message = server.arg("message");
    Serial.print("Received message: ");
    Serial.println(message);

    if (message.equals("SMALL")) {
      Serial.println("Rotating stepper for small portion");
      server.send(200, "text/plain", "ESP32: Feeding small portion");
      rotateStepper(4);

    } else if (message.equals("MEDIUM")) {
      Serial.println("Rotating stepper for medium portion");
      server.send(200, "text/plain", "ESP32: Feeding medium portion");
      rotateStepper(8);

    } else if (message.equals("LARGE")) {
      Serial.println("Rotating stepper for large portion");
      server.send(200, "text/plain", "ESP32: Feeding large portion");
      rotateStepper(12);

    } else {
      Serial.println("Invalid message received");
    }

    server.send(200, "text/plain", "Message received. ESP32 CAM Connected");
  
  // Send Hello message to show connection
  } else {
    server.send(200, "text/plain", "Hello from ESP32 CAM!");
  }
}