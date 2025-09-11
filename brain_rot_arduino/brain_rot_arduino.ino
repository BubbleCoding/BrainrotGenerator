// Arduino code for button only - no distance sensor
// Components needed:
// - Push button
// - 10kΩ pull-down resistor for button

// Pin definitions
const int buttonPin = 2;

const int trigPin = 9;
const int echoPin = 10;


// Variables
int buttonState = 0;
int lastButtonState = 0;
float duration, distance;

void setup() {
  // Initialize serial communication
  Serial.begin(9600);
  
  // Set pin modes
  pinMode(buttonPin, INPUT);
  
  Serial.println("Arduino ready - Button only mode");
}

void loop() {
  // Read button state
  buttonState = digitalRead(buttonPin);
  
  // Debug: Show button state continuously
  Serial.print("Button: ");
  Serial.println(buttonState);
  Serial.print(distanceSensor());
  
  // Check if button was pressed (rising edge detection)
  if (buttonState != lastButtonState && distanceSensor() < 15) {
    Serial.println("BUTTON_PRESSED");
    // Always send trigger since we don't have distance sensor
    Serial.println("TRIGGER");
    delay(50); // Debounce delay
  }
  
  lastButtonState = buttonState;
  
  delay(200); // Slower delay for easier reading
}

float distanceSensor(){
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  duration = pulseIn(echoPin, HIGH);
  distance = (duration*.0343)/2;
  return distance;
}