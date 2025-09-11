// Processing code for generative art triggered by Arduino
// Make sure to install the Serial library if not already available

import processing.serial.*;

Serial arduino;
ArrayList<ArtElement> artElements;
color[] palette;
boolean triggerReceived = false;

void setup() {
  size(800, 600);
  colorMode(HSB, 360, 100, 100, 100);
  
  // Initialize art elements list
  artElements = new ArrayList<ArtElement>();
  
  // Create a color palette
  generateNewPalette();
  
  // Initialize serial communication
  // Print available ports first
  println("Available serial ports:");
  printArray(Serial.list());
  
  // Try to connect to Arduino
  arduino = null; // Initialize as null
  
  if (Serial.list().length > 0) {
    try {
      arduino = new Serial(this, Serial.list()[0], 9600);
      arduino.bufferUntil('\n');
      println("Successfully connected to Arduino on port: " + Serial.list()[0]);
    } catch (Exception e) {
      println("Could not connect to Arduino on port: " + Serial.list()[0]);
      println("Error: " + e.getMessage());
      arduino = null;
    }
  } else {
    println("No serial ports available!");
  }
  
  background(0);
}

void draw() {
  // Fade background slightly for trail effect
  fill(0, 0, 0, 10);
  rect(0, 0, width, height);
  
  // Update and display art elements
  for (int i = artElements.size() - 1; i >= 0; i--) {
    ArtElement element = artElements.get(i);
    element.update();
    element.display();
    
    // Remove dead elements
    if (element.isDead()) {
      artElements.remove(i);
    }
  }
  
  // Check if we received a trigger
  if (triggerReceived) {
    createRandomArt();
    triggerReceived = false;
  }
  
  // Display connection status
  fill(0, 0, 100);
  text("Art Elements: " + artElements.size(), 10, 20);
  
  // Show Arduino connection status
  if (arduino != null) {
    text("Arduino: Connected", 10, 40);
    text("Press 'c' to clear, 'p' for new palette, SPACE to test trigger", 10, 60);
  } else {
    fill(0, 100, 100); // Red color for error
    text("Arduino: Not Connected - Check port!", 10, 40);
    fill(0, 0, 100); // Back to white
    text("Press 'c' to clear, 'p' for new palette, SPACE to test trigger", 10, 60);
  }
}

void createRandomArt() {
  // Generate random art based on different patterns
  int artType = int(random(5));
  
  switch(artType) {
    case 0:
      createSpiral();
      break;
    case 1:
      createBurst();
      break;
    case 2:
      createWave();
      break;
    case 3:
      createParticleSystem();
      break;
    case 4:
      createGeometricPattern();
      break;
  }
  
  // Sometimes change the palette
  if (random(100) < 30) {
    generateNewPalette();
  }
}

void createSpiral() {
  float centerX = random(width);
  float centerY = random(height);
  int numPoints = int(random(20, 100));
  
  for (int i = 0; i < numPoints; i++) {
    float angle = map(i, 0, numPoints, 0, TWO_PI * 3);
    float radius = map(i, 0, numPoints, 0, random(50, 150));
    float x = centerX + cos(angle) * radius;
    float y = centerY + sin(angle) * radius;
    
    artElements.add(new ArtElement(x, y, palette[i % palette.length], "circle"));
  }
}

void createBurst() {
  float centerX = random(width);
  float centerY = random(height);
  int numRays = int(random(8, 24));
  
  for (int i = 0; i < numRays; i++) {
    float angle = map(i, 0, numRays, 0, TWO_PI);
    float length = random(50, 200);
    
    for (int j = 0; j < 10; j++) {
      float distance = map(j, 0, 9, 0, length);
      float x = centerX + cos(angle) * distance;
      float y = centerY + sin(angle) * distance;
      
      artElements.add(new ArtElement(x, y, palette[i % palette.length], "line"));
    }
  }
}

void createWave() {
  float amplitude = random(50, 150);
  float frequency = random(0.01, 0.05);
  float yOffset = random(height);
  
  for (int x = 0; x < width; x += 5) {
    float y = yOffset + sin(x * frequency) * amplitude;
    artElements.add(new ArtElement(x, y, palette[x % palette.length], "wave"));
  }
}

void createParticleSystem() {
  float centerX = random(width);
  float centerY = random(height);
  int numParticles = int(random(30, 80));
  
  for (int i = 0; i < numParticles; i++) {
    float angle = random(TWO_PI);
    float speed = random(1, 5);
    float x = centerX + random(-20, 20);
    float y = centerY + random(-20, 20);
    
    artElements.add(new ParticleElement(x, y, angle, speed, palette[i % palette.length]));
  }
}

void createGeometricPattern() {
  float centerX = random(width);
  float centerY = random(height);
  int sides = int(random(3, 8));
  float radius = random(30, 100);
  
  for (int i = 0; i < sides; i++) {
    float angle = map(i, 0, sides, 0, TWO_PI);
    float x = centerX + cos(angle) * radius;
    float y = centerY + sin(angle) * radius;
    
    artElements.add(new ArtElement(x, y, palette[i % palette.length], "polygon"));
  }
}

void generateNewPalette() {
  palette = new color[5];
  float baseHue = random(360);
  
  for (int i = 0; i < palette.length; i++) {
    float hue = (baseHue + i * 60) % 360;
    float sat = random(60, 100);
    float bright = random(70, 100);
    palette[i] = color(hue, sat, bright);
  }
}

void serialEvent(Serial port) {
  // Check if arduino is not null and if it's the correct port
  if (arduino != null && port == arduino) {
    String data = port.readStringUntil('\n');
    if (data != null) {
      data = trim(data);
      println("Received: " + data);
      
      if (data.equals("TRIGGER")) {
        triggerReceived = true;
        println("Art trigger activated!");
      } else if (data.equals("NO_OBJECT")) {
        println("Button pressed but no object detected");
      }
    }
  }
}

void keyPressed() {
  if (key == 'c' || key == 'C') {
    // Clear all art elements
    artElements.clear();
    background(0);
  } else if (key == 'p' || key == 'P') {
    // Generate new palette
    generateNewPalette();
  } else if (key == ' ') {
    // Test trigger without Arduino
    createRandomArt();
  } else if (key == 'd' || key == 'D') {
    // Debug: Check if serial data is available (safe version)
    if (arduino != null) {
      if (arduino.available() > 0) {
        println("Serial data available: " + arduino.available() + " bytes");
      } else {
        println("No serial data available");
      }
    } else {
      println("Arduino not connected - cannot check serial data");
    }
  }
}

// Art Element Class
class ArtElement {
  float x, y;
  color col;
  String type;
  float life;
  float maxLife;
  float size;
  
  ArtElement(float x, float y, color col, String type) {
    this.x = x;
    this.y = y;
    this.col = col;
    this.type = type;
    this.life = 255;
    this.maxLife = 255;
    this.size = random(5, 20);
  }
  
  void update() {
    life -= 2;
  }
  
  void display() {
    pushMatrix();
    translate(x, y);
    
    fill(hue(col), saturation(col), brightness(col), map(life, 0, maxLife, 0, 100));
    noStroke();
    
    switch(type) {
      case "circle":
        ellipse(0, 0, size, size);
        break;
      case "line":
        stroke(hue(col), saturation(col), brightness(col), map(life, 0, maxLife, 0, 100));
        strokeWeight(3);
        line(-size/2, 0, size/2, 0);
        noStroke();
        break;
      case "wave":
        ellipse(0, 0, size/2, size/2);
        break;
      case "polygon":
        beginShape();
        for (int i = 0; i < 6; i++) {
          float angle = map(i, 0, 6, 0, TWO_PI);
          float px = cos(angle) * size/2;
          float py = sin(angle) * size/2;
          vertex(px, py);
        }
        endShape(CLOSE);
        break;
    }
    
    popMatrix();
  }
  
  boolean isDead() {
    return life <= 0;
  }
}

// Particle Element Class (extends ArtElement)
class ParticleElement extends ArtElement {
  float vx, vy;
  float angle;
  
  ParticleElement(float x, float y, float angle, float speed, color col) {
    super(x, y, col, "particle");
    this.angle = angle;
    this.vx = cos(angle) * speed;
    this.vy = sin(angle) * speed;
    this.maxLife = random(100, 200);
    this.life = maxLife;
  }
  
  void update() {
    super.update();
    x += vx;
    y += vy;
    
    // Add some gravity and friction
    vy += 0.1;
    vx *= 0.99;
    vy *= 0.99;
  }
  
  void display() {
    pushMatrix();
    translate(x, y);
    rotate(angle);
    
    fill(hue(col), saturation(col), brightness(col), map(life, 0, maxLife, 0, 100));
    noStroke();
    ellipse(0, 0, size, size);
    
    popMatrix();
  }
}
