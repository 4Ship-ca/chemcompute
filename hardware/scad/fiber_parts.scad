// WetStack-0 fiber parts (Phase 7). part = "led" prints the LED-to-fiber coupler,
// part = "cap" prints the light-tight cap that holds a fiber over the AS7341 sensor.
// Clone AS7341 boards vary: measure yours and edit the board block.

part = "led";            // "led" or "cap"
fiber_d = 1.2;           // bore for 1.0 mm PMMA fiber
$fn = 64;

// LED coupler: 5 mm LED pushed in from one end, fiber from the other, tip to tip
led_d = 5.1;  led_len = 8.6;  flange_d = 6.0;  flange_h = 1.2;  body_d = 12;  body_h = 16;

// AS7341 board (Adafruit defaults)
board_x = 25.4;  board_y = 17.8;  board_t = 1.6;
sensor_x = 12.7; sensor_y = 8.9;          // sensor centre from the board's lower-left corner
hole_inset = 2.54;  hole_d = 2.7;
cap_h = 12;  skirt_h = 4;  wall = 2;

module led_coupler() {
  difference() {
    cylinder(d = body_d, h = body_h);
    translate([0, 0, -0.01]) cylinder(d = flange_d, h = flange_h);
    translate([0, 0, -0.01]) cylinder(d = led_d, h = led_len);
    translate([0, 0, led_len - 0.5]) cylinder(d = fiber_d, h = body_h);
    translate([0, 0, body_h - 2]) cylinder(d1 = fiber_d, d2 = fiber_d + 1.6, h = 2.01); // lead-in
  }
}

module sensor_cap() {
  difference() {
    translate([-wall, -wall, 0]) cube([board_x + 2*wall, board_y + 2*wall, cap_h]);
    translate([0, 0, -0.01]) cube([board_x, board_y, skirt_h]);                       // board pocket
    translate([sensor_x, sensor_y, -1]) cylinder(d = fiber_d, h = cap_h + 2);          // fiber bore
    translate([sensor_x, sensor_y, cap_h - 3]) cylinder(d1 = fiber_d, d2 = fiber_d + 2, h = 3.01);
    translate([sensor_x, sensor_y, skirt_h - 0.01]) cylinder(d = 3.0, h = 1.5);        // clear the sensor package
    for (x = [hole_inset, board_x - hole_inset], y = [hole_inset, board_y - hole_inset])
      translate([x, y, -1]) cylinder(d = hole_d, h = cap_h + 2);
  }
}

if (part == "led") led_coupler(); else sensor_cap();
